"""Numerical checks for the isolated frozen-critic mechanism experiment."""
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from ac_tmil.ogg.core import ActionTransform, GuidanceError
from ac_tmil.ogg_flow.guidance import FrozenObjective, FlowHook, flow_update
from ac_tmil.ogg_research_v3.learning import TenStepCritic


def identity_transform():
    return ActionTransform([-1.] * 4, [1.] * 4)


def settings(mode, alpha=.2):
    return dict(mode=mode, alpha=alpha, times=[.3, .2, .1])


def models_and_observed():
    torch.manual_seed(617)
    preparation = dict(norm_mean=torch.zeros(4096), norm_std=torch.ones(4096),
                       residual_scale=torch.tensor([.15, .15, .15, .4]),
                       visual_center=torch.zeros(8192), visual_basis=torch.randn(8192, 16) / 100,
                       visual_scale=torch.ones(16), language_center=torch.zeros(2048),
                       language_basis=torch.randn(2048, 8) / 100, language_scale=torch.ones(8))
    models = [TenStepCritic(preparation).eval().requires_grad_(False) for _ in range(4)]
    observed = dict(history=torch.randn(5, 4096, requires_grad=True), history_mask=torch.ones(5),
                    proprio=torch.randn(5, 4), proprio_mask=torch.ones(5),
                    past_actions=torch.randn(4, 4), language=torch.randn(2048), remaining=torch.tensor([.8]))
    return models, observed


def test_reverse_time_sign_velocity_factor_and_full_ten_step_window():
    x = torch.zeros(1, 50, 32)
    v = torch.zeros_like(x)
    objective = lambda commands: commands.sum() / 40
    tau = .2
    direct, direct_row = flow_update(x, v, tau, identity_transform(), objective, settings('direct'))
    velocity, velocity_row = flow_update(x, v, tau, identity_transform(), objective, settings('velocity'))
    expected = torch.zeros_like(v)
    expected[:, :10, :4] = -.2 / 40
    torch.testing.assert_close(direct, expected, rtol=0, atol=1e-8)
    torch.testing.assert_close(velocity, tau * direct, rtol=0, atol=1e-8)
    assert (x - .1 * direct)[:, :10, :4].gt(0).all()
    assert direct[:, 10:].eq(0).all() and direct[:, :, 4:].eq(0).all()
    assert direct[:, 9, :4].ne(0).all(), 'Last half of ten-step window must receive gradients'
    assert direct_row['objective_after'] > direct_row['objective_before']
    assert velocity_row['objective_after'] > velocity_row['objective_before']
    assert direct_row['direct_gradient_outside_mask'] == 0


def test_action_denormalization_scale_and_true_clamp_derivative():
    transform = ActionTransform([-.8, -.6, -.4, -.2], [.2, .6, .4, 1.])
    clean = torch.zeros(1, 10, 32, requires_grad=True)
    actual = transform(clean)
    torch.testing.assert_close(actual[0, 0], torch.tensor([-.3, 0., 0., .4]), rtol=0, atol=1e-7)
    gradient = torch.autograd.grad(actual.sum(), clean)[0]
    torch.testing.assert_close(gradient[0, 0, :4], torch.tensor([.5, .6, .4, .6]), rtol=0, atol=1e-7)
    assert gradient[..., 4:].eq(0).all()
    outside = torch.full((1, 10, 32), 5., requires_grad=True)
    clipped = transform(outside)
    boundary_gradient = torch.autograd.grad(clipped.sum(), outside)[0]
    assert clipped.eq(1).all() and boundary_gradient.eq(0).all()


def test_saturated_flow_has_zero_gradient_and_no_straight_through_update():
    x = torch.full((1, 50, 32), 2.)
    v = torch.zeros_like(x)
    for mode in ['velocity', 'direct']:
        after, row = flow_update(x, v, .2, identity_transform(), lambda a: a.sum(), settings(mode))
        torch.testing.assert_close(after, v, rtol=0, atol=0)
        assert row['clipping_fraction'] == 1. and row['zero_gradient_fraction'] == 1.


def test_a0_is_fixed_slot_zero_and_state_has_no_gradient():
    models, observed = models_and_observed()
    external_a0 = torch.zeros(50, 4, requires_grad=True)
    objective = FrozenObjective(observed, external_a0, models=models)
    assert float(objective(objective.a0)) == 0.
    baseline = objective.last_member_probabilities[:, 0].copy()
    candidate = torch.full((1, 10, 4), .15, requires_grad=True)
    value = objective(candidate)
    gradient = torch.autograd.grad(value, candidate)[0]
    assert gradient.shape == (1, 10, 4) and gradient.abs().max() > 0
    np.testing.assert_array_equal(objective.last_member_probabilities[:, 0], baseline)
    assert observed['history'].grad is None and external_a0.grad is None
    with torch.no_grad():
        external_a0.fill_(.3)
        observed['history'].fill_(99.)
    assert objective.a0.eq(0).all()
    np.testing.assert_array_equal(objective.evaluate(candidate.detach())['member_probabilities'], objective.last_member_probabilities)
    assert objective.verify()
    assert objective.backward_calls == 1
    assert all(p.grad is None for model in models for p in model.parameters())


def test_actual_v3_architecture_gradient_matches_directional_finite_difference():
    models, observed = models_and_observed()
    objective = FrozenObjective(observed, np.zeros((10, 4), np.float32), models=models)
    gradient, diagnostics = objective.gradient()
    direction = gradient / gradient.norm()
    epsilon = .005
    with torch.no_grad():
        difference = (objective(epsilon * direction) - objective(-epsilon * direction)) / (2 * epsilon)
    torch.testing.assert_close(difference, (gradient * direction).sum(), rtol=.015, atol=3e-6)
    assert diagnostics['gradient_norm'] > 0
    assert objective.stats()['critic_member_backward_calls'] == 4
    assert objective.verify()


def test_hash_verification_detects_data_mutation_without_version_increment():
    models, observed = models_and_observed()
    objective = FrozenObjective(observed, np.zeros((10, 4), np.float32), models=models)
    next(models[0].parameters()).data.add_(.001)
    with pytest.raises(ValueError, match='SHA changed'):
        objective.verify()


def sample(model, noise):
    current = noise.clone()
    for index in range(10, 0, -1):
        current = current - .1 * model.denoise_step(x_t=current, timestep=torch.tensor([index / 10]))
    return current


def test_zero_strength_sampler_is_bit_identical_and_times_and_noise_persist():
    original = lambda **kwargs: kwargs['x_t'] * .07 + .003
    model = SimpleNamespace(denoise_step=original)
    noise = torch.randn(1, 50, 32)
    baseline = sample(model, noise)
    hook = FlowHook(model, identity_transform(), settings('direct', alpha=0))
    hook.begin(lambda commands: (_ for _ in ()).throw(AssertionError('zero strength must not call critic')))
    guided = sample(model, noise)
    torch.testing.assert_close(baseline, guided, rtol=0, atol=0)
    assert len(hook.times) == 10 and hook.logs == [] and hook.objective_calls == 0
    noise_sha = hook.last_noise_sha
    assert isinstance(noise_sha, str) and len(noise_sha) == 64
    hook.begin(None)
    assert hook.last_noise_sha == noise_sha
    hook.close()
    assert model.denoise_step is original


def test_hook_only_calls_registered_times_and_raises_guidance_error_on_nan():
    model = SimpleNamespace(denoise_step=lambda **kwargs: torch.zeros_like(kwargs['x_t']))
    hook = FlowHook(model, identity_transform(), settings('direct'))
    hook.begin(lambda commands: commands.sum() / 40)
    final = sample(model, torch.zeros(1, 50, 32))
    assert len(hook.logs) == 3 and hook.objective_calls == 6
    assert final[:, :10, :4].gt(0).all()
    np.testing.assert_allclose([row['tau'] for row in hook.logs], [.3, .2, .1], atol=1e-6)
    hook.begin(lambda commands: commands.sum() * float('nan'))
    with pytest.raises(GuidanceError, match='nonfinite'):
        model.denoise_step(x_t=torch.zeros(1, 50, 32), timestep=torch.tensor([.1]))
    hook.close()


def test_cpu_thread_count_is_restored_after_forward_and_backward():
    models, observed = models_and_observed()
    previous = torch.get_num_threads()
    try:
        torch.set_num_threads(3)
        objective = FrozenObjective(observed, np.zeros((10, 4), np.float32), models=models)
        objective.gradient()
        objective.evaluate(objective.a0)
        assert torch.get_num_threads() == 3
    finally:
        torch.set_num_threads(previous)
