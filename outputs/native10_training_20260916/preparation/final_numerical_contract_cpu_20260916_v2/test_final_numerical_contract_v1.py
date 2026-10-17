"""Synthetic CPU numerical evidence only; never read actual weights or datasets.

All models, PCA input matrices and canonical observations below are fabricated.
No formal preflight, optimizer, simulator, GPU or shared workflow output runs.
The dense-batch comparison is a measured diagnostic, not a relaxed acceptance
tolerance: the existing singleton export/reload contract remains bit exact.
"""
from copy import deepcopy
import json

import numpy as np
import pytest
import torch

from corrector.critic import STATE_KEYS, TenStepCritic, observed_features
from corrector.guidance import FrozenObjective
from experiments.native10_training_20260916 import storage, training
from experiments.native10_training_20260916 import training_pipeline as pipeline


@pytest.fixture
def synthetic():
    with training.cpu_threads(), torch.random.fork_rng(devices=[]):
        torch.manual_seed(2026091607)
        prep = dict(norm_mean=torch.randn(4096) * .02, norm_std=torch.ones(4096),
            visual_center=torch.randn(8192) * .02,
            visual_basis=torch.randn(8192, 16) / 100, visual_scale=torch.ones(16),
            language_center=torch.randn(2048) * .02,
            language_basis=torch.randn(2048, 8) / 100, language_scale=torch.ones(8),
            residual_scale=torch.tensor([.15, .15, .15, .4]))
        # Exercise the preserved near-zero scale without saturating every value.
        for name in ('visual', 'language'):
            prep[name + '_scale'][0] = 1e-3
            prep[name + '_basis'][:, 0] *= 1e-3
        models = [TenStepCritic(prep).eval().requires_grad_(False) for _ in range(4)]
        n = 5
        arrays = dict(history=torch.randn(n, 5, 4096),
            history_mask=torch.ones(n, 5, dtype=torch.bool),
            proprio=torch.randn(n, 5, 4), proprio_mask=torch.ones(n, 5, dtype=torch.bool),
            past_actions=torch.randn(n, 4, 4), language=torch.randn(n, 2048),
            remaining=torch.linspace(.9, .2, n), actions=torch.rand(n, 13, 10, 4) * 1.6 - .8)
        arrays['history_mask'][0, :3] = False
        arrays['proprio_mask'][1, :2] = False
    rows = [dict(episode_id=f'synthetic_only_{i}') for i in range(n)]
    return models, arrays, rows


def difference(left, right):
    left, right = torch.as_tensor(left).detach(), torch.as_tensor(right).detach()
    assert left.shape == right.shape and left.dtype == right.dtype
    return dict(shape=list(left.shape), dtype=str(left.dtype),
        exact_equal=torch.equal(left, right),
        finite=bool(torch.isfinite(left).all() and torch.isfinite(right).all()),
        mismatched_elements=int((left != right).sum()),
        max_abs_difference=float((left - right).abs().max()))


def test_cpu_two_threads_restored_on_exception():
    before = torch.get_num_threads()
    with pytest.raises(RuntimeError, match='synthetic exception'):
        with training.cpu_threads():
            assert torch.get_num_threads() == 2
            raise RuntimeError('synthetic exception')
    assert torch.get_num_threads() == before


def test_observed_features_preserve_mask_clamps_and_temporal_definition(synthetic):
    models, arrays, _ = synthetic
    model = models[0]
    data = {key: arrays[key].clone() for key in STATE_KEYS}
    data['history'][0, 0] = 1e6  # masked history cannot enter masked mean
    data['history'][0, -1, 0] = 1e6
    with training.cpu_threads():
        visual, language, other = observed_features(data, model.norm_mean, model.norm_std)
        h = ((data['history'] - model.norm_mean) / model.norm_std.clamp_min(1e-6)).clamp(-8, 8)
        mask = data['history_mask'][..., None]
        expected = torch.cat([h[:, -1], (h * mask).sum(1) / mask.sum(1).clamp_min(1)], -1)
        assert torch.equal(visual, expected)
        assert visual[0, 0] == 8
        assert torch.equal(language, torch.nn.functional.layer_norm(data['language'], (2048,)))
        assert torch.equal(other[:, :20], (data['proprio'] * data['proprio_mask'][..., None]).flatten(1))
        assert torch.equal(other[:, 20:36], data['past_actions'].flatten(1))
        assert torch.equal(other[:, -1], data['remaining'])


def test_canonical_cache_calls_singleton_for_every_source(synthetic, monkeypatch):
    models, arrays, rows = synthetic
    model, sizes = models[0], []
    original = model.features
    def tracked(values):
        sizes.append((len(values['history']), torch.get_num_threads()))
        return original(values)
    monkeypatch.setattr(model, 'features', tracked)
    cache = training.canonical_features(model, arrays)
    assert sizes == [(1, 2)] * len(rows)
    assert cache.shape == (len(rows), 61) and not cache.requires_grad


def test_predictions_keep_detached_anchor_and_two_candidate_slots(synthetic):
    models, arrays, rows = synthetic
    model, shapes = models[0], []
    handle = model.register_forward_pre_hook(lambda _, args: shapes.append(tuple(args[1].shape)))
    result = pipeline.predict_member(model, arrays)
    handle.remove()
    assert shapes == [(1, 2, 10, 4)] * (len(rows) * 13)
    assert result.shape == (len(rows), 13) and result.dtype == np.float32
    objective = FrozenObjective({k: arrays[k][0] for k in STATE_KEYS}, arrays['actions'][0, 0], models=models)
    assert objective.evaluate(arrays['actions'][0, 0])['mean_gain'] == 0
    for slot in range(13):
        pair = objective.evaluate(arrays['actions'][0, slot])['member_probabilities'][0]
        assert result[0, slot] == np.float32(pair[0 if slot == 0 else 1])
    gradient, _ = objective.gradient(arrays['actions'][0, 11])
    assert torch.isfinite(gradient).all() and objective.verify()
    assert all(p.grad is None for model in models for p in model.parameters())


def test_synthetic_export_reload_all_thirteen_and_gradients_remain_bit_exact(synthetic, tmp_path, monkeypatch):
    models, arrays, rows = synthetic
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    states = [training.checkpoint_state(model) for model in models]
    selector = pipeline.export_ensemble(states, tmp_path / 'synthetic_only_export', provenance={'synthetic': True})
    audit = pipeline.audit_reload(models, selector, arrays, rows)
    assert audit['source_count'] == len(rows) and audit['episode_ids'] == [r['episode_id'] for r in rows]
    assert all(audit[key] is True for key in (
        'feature_cache_bit_exact', 'thirteen_candidate_member_probability_bit_exact',
        'member_and_ensemble_gradient_bit_exact', 'a0_anchor_exactly_zero', 'state_and_anchor_immutable'))
    assert audit['gradient_slots'] == [0, 11]
    assert audit['ensemble_summary_difference_is_report_only'] is True
    print('SYNTHETIC_RELOAD ' + json.dumps(audit, sort_keys=True))


def test_single_ulp_changed_cache_is_rejected_without_allclose(synthetic, monkeypatch):
    models, arrays, rows = synthetic
    selector = type('SyntheticSelector', (), {})()
    selector.models = deepcopy(models)
    selector.ranking = dict(model_hashes={str(i): 'synthetic' for i in range(4)})
    selector.verify = lambda **kwargs: True
    original = selector.models[0].features
    def perturbed(values):
        output = original(values).clone()
        output[:, 0] = torch.nextafter(output[:, 0], torch.full_like(output[:, 0], float('inf')))
        return output
    monkeypatch.setattr(selector.models[0], 'features', perturbed)
    with pytest.raises(ValueError, match='probabilities changed|cache differs'):
        pipeline.audit_reload(models, selector, arrays, rows)


def test_synthetic_rank_deficient_pca_keeps_exact_registered_floor():
    # No real PCA is performed: every entry is a fabricated constant.
    with training.cpu_threads():
        (_, _, scale), diag = training.fit_pca(torch.full((20, 19), .125), 16, return_diagnostics=True)
    assert torch.equal(scale, torch.full((16,), 1e-3))
    assert diag['scale_floor'] == 1e-3 and diag['scale_floor_count'] == 16
    assert diag['projected_clip_fraction'] == 0


def test_dense_batch_differences_are_measured_without_new_acceptance_tolerance(synthetic):
    models, arrays, rows = synthetic
    state = {key: arrays[key] for key in STATE_KEYS}
    actions = arrays['actions']
    report = dict(synthetic=True, seed=2026091607, torch=str(torch.__version__),
        numpy=np.__version__, device='cpu', threads=2, n_sources=len(rows),
        batch_shape=[len(rows), 2, 10, 4], gradient_slots=[0, 11],
        no_new_tolerance=True, scientific_acceptance_not_decided=True, members=[])
    caches = [training.canonical_features(model, arrays) for model in models]
    with training.cpu_threads(), torch.no_grad():
        batch_features = [model.features(state) for model in models]
        for member, model in enumerate(models):
            observed_batch = observed_features(state, model.norm_mean, model.norm_std)
            observed_single = [observed_features({key: value[i:i+1] for key, value in state.items()},
                model.norm_mean, model.norm_std) for i in range(len(rows))]
            batch_p = torch.empty(len(rows), 13)
            for slot in range(13):
                pair = torch.stack([actions[:, 0].detach(), actions[:, slot]], 1)
                probabilities = model(batch_features[member], pair).sigmoid()
                batch_p[:, slot] = probabilities[:, 0 if slot == 0 else 1]
            report['members'].append(dict(member=member,
                observed={name:difference(observed_batch[index], torch.cat([v[index] for v in observed_single]))
                    for index, name in enumerate(('visual', 'language', 'other'))},
                features=difference(batch_features[member], caches[member]),
                probabilities=difference(batch_p, pipeline.predict_member(model, arrays)), gradients={}))
    report['ensemble_gradients'] = {}
    with training.cpu_threads(), torch.enable_grad():
        for slot in (0, 11):
            for member, model in enumerate(models):
                leaf = actions[:, slot].detach().clone().requires_grad_(True)
                pair = torch.stack([actions[:, 0].detach(), leaf], 1)
                probabilities = model(batch_features[member], pair).sigmoid()
                batch_gradient = torch.autograd.grad((probabilities[:, 1] - probabilities[:, 0]).sum(), leaf)[0]
                singleton = torch.stack([pipeline._member_gradient(model, caches[member][i:i+1], actions[i, 0], actions[i, slot])
                    for i in range(len(rows))])
                report['members'][member]['gradients'][str(slot)] = difference(batch_gradient, singleton)
            leaf = actions[:, slot].detach().clone().requires_grad_(True)
            pair = torch.stack([actions[:, 0].detach(), leaf], 1)
            probabilities = torch.stack([model(feature, pair).sigmoid() for model, feature in zip(models, batch_features)])
            batch_gradient = torch.autograd.grad((probabilities[:, :, 1] - probabilities[:, :, 0]).mean(0).sum(), leaf)[0]
            singleton = torch.stack([FrozenObjective({key: arrays[key][i] for key in STATE_KEYS}, actions[i, 0],
                models=models).gradient(actions[i, slot])[0] for i in range(len(rows))])
            report['ensemble_gradients'][str(slot)] = difference(batch_gradient, singleton)
    values = [v for record in report['members'] for v in
        [*record['observed'].values(), record['features'], record['probabilities'], *record['gradients'].values()]]
    values.extend(report['ensemble_gradients'].values())
    assert all(value['finite'] for value in values)
    # No bit-exactness or allclose tolerance is asserted for a new batch path.
    # Report actual differences; this does not release that path for production.
    print('SYNTHETIC_DENSE_BATCH ' + json.dumps(report, sort_keys=True))
