"""Action-only gradients inside the two *unchanged native* sampling loops.

Smol emits velocity and uses dt=-.1 Euler. X emits clean predictions and
remixes the fixed noise at the next descending time. X's velocity coordinate
v=(x_t-u)/t is modified, then mapped back to the clean head: u'=u+alpha*t²*g.
This preserves X's native remixer; it is not claimed to be an Euler solver.
"""
import hashlib
import numpy as np
import torch


class NativeVelocityBridge:
    def __init__(self, policy, post, kind):
        self.policy, self.post, self.kind = policy, post, kind
        self.gradient_rpc = None
        if policy.config.n_obs_steps != 1:
            raise ValueError('Repeated current observation requires native n_obs_steps=1')
        if kind == 'smolvla':
            if policy.config.adapt_to_pi_aloha or policy.model._rtc_enabled():
                raise ValueError('Unapproved Smol coordinate/RTC transform')
            original = policy.model.denoise_step
            def denoise(*args, **kw):
                velocity = original(*args, **kw)
                return self.smol(kw['x_t'], velocity, kw['timestep'])
            policy.model.denoise_step = denoise
        elif kind == 'xvla':
            if policy.config.action_mode != 'auto' or policy.model.action_space.real_dim != 4:
                raise ValueError('X bridge requires the frozen auto four-dimensional space')
            self.handle = policy.model.transformer.register_forward_hook(self.x_hook, with_kwargs=True)
        else:
            raise ValueError(kind)
        self.begin()

    def begin(self, gradient_rpc=None):
        self.gradient_rpc = gradient_rpc
        self.times, self.updates, self.noise_sha256 = [], [], None

    def observe(self, x, t):
        tau = float(t.reshape(-1)[0])
        if x.ndim != 3 or x.shape[0] != 1 or not torch.isfinite(x).all():
            raise ValueError('Invalid native flow state')
        if not self.times:
            self.noise_sha256 = hashlib.sha256(x.detach().float().cpu().numpy().tobytes()).hexdigest()
        index = len(self.times)
        if index >= 10 or abs(tau - (1-index/10)) > 1e-5:
            raise ValueError('Native time schedule changed')
        self.times.append(tau)
        return tau, self.gradient_rpc is not None and index >= 7

    def gradient(self, clean, tau):
        # Network outputs are detached. Only native action -> saved inverse
        # normalization -> true clamp is differentiated. No VLA Jacobian.
        with torch.inference_mode(False), torch.enable_grad(), torch.autocast('cuda', enabled=False):
            leaf = clean.detach().float().clone().requires_grad_(True)
            for step in self.post.steps:
                for stats in getattr(step, '_tensor_stats', {}).values():
                    for name, tensor in list(stats.items()):
                        if torch.is_tensor(tensor) and torch.is_inference(tensor):
                            stats[name] = tensor.clone()
            physical = self.post(leaf[0, :10, :4])
            if physical.shape != (10, 4) or not torch.isfinite(physical).all():
                raise ValueError('Invalid native inverse-normalized action')
            command = physical.clamp(-1, 1)
            reply = self.gradient_rpc(command.detach().cpu().numpy())
            ga = torch.as_tensor(reply['gradient'], device=command.device, dtype=command.dtype)
            gu = torch.autograd.grad(command, leaf, ga, allow_unused=False)[0]
            if not torch.isfinite(gu).all():
                raise ValueError('Nonfinite native action gradient')
            if torch.count_nonzero(gu[:, 10:]) or torch.count_nonzero(gu[:, :, 4:]):
                raise ValueError('Action gradient leaked into tail or padded channels')
        self.updates.append(dict(tau=tau, alpha=10., command_gradient_norm=float(ga.norm()),
            native_gradient_norm=float(gu.norm()), true_clamp=True, native_inverse_normalization=True,
            action_only_backward=True, objective_value=reply['value']))
        return gu.detach()

    def smol(self, x, velocity, time):
        tau, guide = self.observe(x, time)
        if not torch.isfinite(velocity).all():
            raise ValueError('Nonfinite native Smol velocity')
        if not guide:
            return velocity
        clean = x.detach().float() - tau * velocity.detach().float()
        return (velocity.detach().float() - 10. * tau * self.gradient(clean, tau)).to(dtype=velocity.dtype).detach()

    def x_hook(self, module, args, kw, clean):
        tau, guide = self.observe(kw['action_with_noise'], kw['t'])
        if not torch.isfinite(clean).all():
            raise ValueError('Nonfinite native X clean prediction')
        if not guide:
            return clean
        # Exact inverse of v'=(x-u)/tau-alpha*tau*g. Preserve the native
        # clean-prediction output dtype before the original next-time remixer.
        updated = clean.detach().float() + 10. * tau * tau * self.gradient(clean, tau)
        return updated.to(dtype=clean.dtype).detach()

    def finish(self):
        if len(self.times) != 10 or (self.gradient_rpc is not None and len(self.updates) != 3):
            raise ValueError('Incomplete native sampling or guidance schedule')
        if any(p.requires_grad or p.grad is not None for p in self.policy.parameters()):
            raise ValueError('Base model was not frozen')
        return dict(flow_calls=len(self.times), times=self.times, updates=self.updates,
            noise_sha256=self.noise_sha256, native_time_delta=-.1,
            integration='negative-dt Euler' if self.kind=='smolvla' else 'native fixed-noise clean-prediction remixer',
            x_velocity_reparameterization=None if self.kind=='smolvla' else '(x_t-u)/tau; u_guided=u+alpha*tau²*grad_u')
