"""Candidate-only gradients for the frozen v3 critic and reverse-time flow.

All objectives here are *maximized*.  This differs from the minimization
convention of the historical ogg.core.DenoiseHook.  No intermediate trust-region
projection is applied: final command matching belongs to the experiment driver.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import math
import time

import numpy as np
import torch

from ac_tmil.ogg.core import GuidanceError
from ac_tmil.ogg_research.critic_data import STATE_KEYS


@contextmanager
def critic_threads():
    """Preserve the canonical v3 singleton CPU arithmetic during backward too."""
    previous = torch.get_num_threads()
    try:
        if previous != 2:
            torch.set_num_threads(2)
        yield
    finally:
        if previous != 2:
            torch.set_num_threads(previous)


def _tensor_hash(tensor):
    value = tensor.detach().cpu().contiguous()
    return hashlib.sha256(value.numpy().tobytes()).hexdigest()


def _model_hash(model):
    digest = hashlib.sha256()
    for name, value in model.state_dict().items():
        digest.update(name.encode())
        digest.update(str(value.dtype).encode())
        digest.update(str(tuple(value.shape)).encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


class FrozenObjective:
    """R(a) = mean_i [sigmoid C_i(s,a;a0) - sigmoid C_i(s,a0;a0)].

    ``observed`` is one unbatched canonical saved context. ``a0`` is either its
    specified 10x4 prefix or the complete 50x4 plan; only the first ten commands
    enter this objective. Pass a shared FrozenSelector to avoid reloading models.
    The optional four ``models`` argument is useful for analytic CPU tests.
    """

    def __init__(self, observed, a0, selector=None, models=None):
        if selector is not None and models is not None:
            raise ValueError('Supply selector or models, not both')
        if selector is None and models is None:
            from ac_tmil.ogg_research_v3.learning import FrozenSelector
            selector = FrozenSelector()
        self.selector = selector
        self.models = list(selector.models if selector is not None else models)
        if len(self.models) != 4:
            raise ValueError('The experiment requires exactly four frozen v3 members')
        self.weight_file_hashes = dict(selector.ranking['model_hashes']) if selector is not None else {}
        self.forward_calls = self.member_forward_calls = self.backward_calls = 0
        self.forward_seconds = 0.
        self.last_member_probabilities = None
        with torch.inference_mode(False), critic_threads(), torch.no_grad():
            base = torch.as_tensor(a0).detach().cpu().float().clone()
            if base.shape not in ((10, 4), (50, 4)):
                raise ValueError('Specified a0 must be 10x4 or 50x4')
            self._a0 = base[:10].clone()
            self._validate_commands(self._a0)
            obs = {key: torch.as_tensor(observed[key]).detach().cpu().clone()[None] for key in STATE_KEYS}
            if obs['history'].shape != (1, 5, 4096):
                raise ValueError('Observed context must be a single unbatched source')
            if any(not torch.isfinite(value).all() for value in obs.values()):
                raise ValueError('Nonfinite observed context')
            self.features = []
            for model in self.models:
                if model.training or any(p.requires_grad or p.grad is not None or p.device.type != 'cpu' for p in model.parameters()):
                    raise ValueError('Critics must already be frozen CPU eval models')
                self.features.append(model.features(obs).detach().clone())
        self.versions = [(value, value._version) for model in self.models
                         for value in list(model.parameters()) + list(model.buffers())]
        self.model_hashes = [_model_hash(model) for model in self.models]
        self.a0_hash = _tensor_hash(self._a0)
        self.feature_hashes = [_tensor_hash(value) for value in self.features]

    @property
    def a0(self):
        return self._a0.clone()

    @staticmethod
    def _validate_commands(commands):
        if not torch.isfinite(commands).all() or float(commands.detach().abs().max()) > 1.:
            raise ValueError('Expected finite actual environment commands in [-1, 1]')

    def _backward_seen(self, gradient):
        self.backward_calls += 1
        return gradient

    def __call__(self, commands):
        """Return a differentiable scalar, preserving an input CPU/CUDA graph."""
        begin = time.perf_counter()
        with critic_threads():
            candidate = torch.as_tensor(commands).to(device='cpu', dtype=torch.float32)
            if candidate.shape == (10, 4):
                candidate = candidate[None]
            if candidate.shape != (1, 10, 4):
                raise ValueError('Candidate must be 10x4 or 1x10x4')
            self._validate_commands(candidate)
            # Slot zero is always the same detached a0, never the optimized input.
            actions = torch.stack((self._a0[None], candidate), dim=1)
            probabilities = torch.stack([model(features, actions).sigmoid()[0]
                                         for model, features in zip(self.models, self.features)])
            result = (probabilities[:, 1] - probabilities[:, 0]).mean()
            if not torch.isfinite(result):
                raise GuidanceError('nonfinite_objective')
            self.last_member_probabilities = probabilities.detach().numpy().copy()
            self.forward_calls += 1
            self.member_forward_calls += len(self.models)
            self.forward_seconds += time.perf_counter() - begin
            if result.requires_grad:
                result.register_hook(self._backward_seen)
            return result

    def evaluate(self, commands):
        with torch.no_grad():
            value = self(commands)
        return dict(mean_gain=float(value), member_probabilities=self.last_member_probabilities.tolist(),
                    a0_mean_probability=float(self.last_member_probabilities[:, 0].mean()),
                    candidate_mean_probability=float(self.last_member_probabilities[:, 1].mean()))

    def gradient(self, commands=None):
        """Return the environment-command gradient at a0 (or a given candidate)."""
        with torch.inference_mode(False), torch.enable_grad(), critic_threads():
            leaf = torch.as_tensor(self._a0 if commands is None else commands).detach().cpu().float().clone()
            if leaf.shape == (1, 10, 4):
                leaf = leaf[0]
            if leaf.shape != (10, 4):
                raise ValueError('Gradient point must be 10x4 or 1x10x4')
            leaf.requires_grad_(True)
            value = self(leaf)
            gradient = torch.autograd.grad(value, leaf, allow_unused=False)[0]
            if not torch.isfinite(gradient).all():
                raise GuidanceError('nonfinite_gradient')
        return gradient.detach(), dict(value=float(value.detach()),
                                      member_probabilities=self.last_member_probabilities.tolist(),
                                      **_gradient_summary(gradient))

    def stats(self):
        return dict(objective_forward_calls=self.forward_calls,
                    critic_member_forward_calls=self.member_forward_calls,
                    objective_backward_calls=self.backward_calls,
                    critic_member_backward_calls=4 * self.backward_calls,
                    critic_forward_seconds=self.forward_seconds)

    def verify(self, check_hashes=True):
        if self.selector is not None:
            self.selector.verify()
        if any(value._version != version for value, version in self.versions):
            raise ValueError('Frozen critic parameter or buffer changed')
        if any(model.training or any(p.requires_grad or p.grad is not None for p in model.parameters()) for model in self.models):
            raise ValueError('Frozen critic gradient/eval invariant changed')
        if any(value.requires_grad for value in self.features) or self._a0.requires_grad:
            raise ValueError('Observed state or specified a0 became differentiable')
        if check_hashes:
            if [_model_hash(model) for model in self.models] != self.model_hashes:
                raise ValueError('Frozen critic state SHA changed')
            if _tensor_hash(self._a0) != self.a0_hash or [_tensor_hash(value) for value in self.features] != self.feature_hashes:
                raise ValueError('Frozen state or a0 SHA changed')
        return True


def _gradient_summary(gradient):
    value = gradient.detach().float().reshape(10, 4)
    return dict(gradient_norm=float(value.norm()), gradient_linf=float(value.abs().max()),
                gradient_xyz_rms=float(value[:, :3].square().mean().sqrt()),
                gradient_grip_rms=float(value[:, 3].square().mean().sqrt()),
                gradient_per_dimension_rms=value.square().mean(0).sqrt().tolist(),
                zero_gradient_fraction=float(value.eq(0).float().mean()))


def _distance(commands, objective):
    if not hasattr(objective, 'a0'):
        return {}
    delta = commands.detach().cpu().reshape(10, 4) - objective.a0.cpu()
    return dict(clean_a0_xyz_rms=float(delta[:, :3].square().mean().sqrt()),
                clean_a0_grip_rms=float(delta[:, 3].square().mean().sqrt()),
                clean_a0_linf=float(delta.abs().max()))


def flow_update(x, velocity, tau, transform, objective, settings):
    """Differentiate velocity or clean action, preserving the same true clamp.

    With tau decreasing and R maximized, velocity mode computes dR/dv=-tau*g
    and takes v+alpha*dR/dv. Direct mode takes v-alpha*g. Both therefore add
    positive-g movement to the Euler state when its time step is negative.
    """
    if x.shape != velocity.shape or x.ndim != 3 or x.shape[0] != 1 or x.shape[1:] != (50, 32):
        raise GuidanceError('invalid_velocity_shape')
    tau = float(tau)
    alpha = float(settings['alpha'])
    mode = settings['mode']
    if mode not in ('velocity', 'direct') or not 0 < tau <= 1.000001 or not math.isfinite(alpha) or alpha < 0:
        raise GuidanceError('invalid_guidance_settings')
    if not torch.isfinite(x).all() or not torch.isfinite(velocity).all():
        raise GuidanceError('nonfinite_flow_input')
    with torch.inference_mode(False), torch.enable_grad(), critic_threads():
        fixed_x = x.detach().float().clone()
        fixed_v = velocity.detach().float().clone()
        leaf = (fixed_v if mode == 'velocity' else fixed_x - tau * fixed_v).clone().requires_grad_(True)
        clean = fixed_x - tau * leaf if mode == 'velocity' else leaf
        before_unclipped = transform(clean[:, :10], clip=False)
        before = transform(clean[:, :10], clip=True)
        value = objective(before)
        if value.ndim or not torch.isfinite(value):
            raise GuidanceError('nonfinite_or_nonscalar_objective')
        try:
            derivative = torch.autograd.grad(value, leaf, allow_unused=False)[0]
        except RuntimeError as error:
            raise GuidanceError('objective_backward_failed: ' + str(error)) from error
        if not torch.isfinite(derivative).all():
            raise GuidanceError('nonfinite_gradient')
        mask = torch.zeros_like(derivative)
        mask[:, :10, :4] = 1
        outside = float((derivative * (1 - mask)).abs().max())
        if outside != 0:
            raise GuidanceError('gradient_outside_ten_step_command_window')
        clean_gradient = -derivative / tau if mode == 'velocity' else derivative
        updated = fixed_v + alpha * derivative if mode == 'velocity' else fixed_v - alpha * derivative
        if not torch.isfinite(updated).all():
            raise GuidanceError('nonfinite_updated_velocity')
        with torch.no_grad():
            after = transform((fixed_x - tau * updated)[:, :10], clip=True)
            after_value = objective(after)
        if after_value.ndim or not torch.isfinite(after_value) or not torch.isfinite(after).all():
            raise GuidanceError('nonfinite_updated_objective')
        delta = after - before.detach()
        row = dict(mode=mode, tau=tau, alpha=alpha, accepted=True, halvings=0,
                   objective_before=float(value.detach()), objective_after=float(after_value),
                   loss_before=float(value.detach()), loss_after=float(after_value),
                   objective_semantics='maximize_mean_member_relative_success_probability',
                   objective_forward_calls=2, backward_calls=1,
                   injection_gradient_norm=float(derivative.norm()),
                   velocity_delta_norm=float((updated - fixed_v).norm()),
                   direct_gradient_outside_mask=outside,
                   clipping_fraction=float((before_unclipped.abs() > 1).float().mean()),
                   boundary_fraction=float((before.abs() >= 1).float().mean()),
                   clipping_fraction_per_dimension=(before_unclipped.abs() > 1).float().mean((0, 1)).tolist(),
                   clean_unclipped_linf=float(before_unclipped.detach().abs().max()),
                   command_delta_linf=float(delta.abs().max()),
                   command_delta_per_dimension=delta.abs().amax((0, 1)).tolist(),
                   **_gradient_summary(clean_gradient[:, :10, :4]), **_distance(before, objective))
        return updated.detach().to(dtype=velocity.dtype), row


class FlowHook:
    """Engine.propose-compatible hook; the supplied callable maximizes R."""

    def __init__(self, model, transform, settings):
        self.model = model
        self.original = model.denoise_step
        self.transform = transform
        self.settings = settings
        self.loss_fn = None
        self.objective = None
        self.logs = []
        self.times = []
        self.objective_calls = self.failed_backward_calls = 0
        self.last_noise_sha = None

        def wrapped(*args, **kwargs):
            value = self.original(*args, **kwargs)
            tau = float(kwargs['timestep'][0])
            self.times.append(tau)
            if math.isclose(tau, 1., abs_tol=1e-6):
                noise = kwargs['x_t'].detach().cpu().contiguous().view(torch.uint8)
                self.last_noise_sha = hashlib.sha256(noise.numpy().tobytes()).hexdigest()
            if self.loss_fn is None or float(self.settings['alpha']) == 0:
                return value
            if not any(math.isclose(tau, point, abs_tol=1e-6) for point in self.settings['times']):
                return value
            backward_before = getattr(self.objective, 'backward_calls', None)
            try:
                result, row = flow_update(kwargs['x_t'], value, tau, self.transform, self.loss_fn, self.settings)
            except GuidanceError:
                backward_after = getattr(self.objective, 'backward_calls', None)
                if backward_before is not None:
                    self.failed_backward_calls += backward_after - backward_before
                raise
            self.logs.append(row)
            return result

        self.wrapped = wrapped
        model.denoise_step = wrapped

    def begin(self, loss_fn=None):
        self.logs = []
        self.times = []
        self.objective_calls = self.failed_backward_calls = 0
        self.objective = loss_fn

        def counted(commands):
            self.objective_calls += 1
            try:
                return loss_fn(commands)
            except ValueError as error:
                raise GuidanceError('invalid_objective_input: ' + str(error)) from error

        # Retain the fixed a0 solely for distance diagnostics, never for gradients.
        if loss_fn is not None and hasattr(loss_fn, 'a0'):
            counted.a0 = loss_fn.a0
        self.loss_fn = counted if loss_fn is not None else None

    def close(self):
        if self.model.denoise_step is self.wrapped:
            self.model.denoise_step = self.original
