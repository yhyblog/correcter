"""CPU-only contract checks; no simulator, policy or archived output imports."""
import copy
import hashlib
import json

import numpy as np
import pytest

from .candidates13 import CANDIDATE_ORDER, construct_candidates13


def fixture():
    raw = np.full((50, 4), .2, dtype=np.float32)
    raw[0] = [1.2, -1.3, -0., 2.1]
    raw[1] = [.96, -.96, .4, -.3]
    raw[20] = [1.4, -.0, -1.5, 2.]
    delta = np.zeros((10, 4), dtype=np.float32)
    delta[2:10, :3] = [.02, -.03, .01]
    delta[2:10, 3] = .07
    matched = {}
    for name, sign in [('velocity', -1), ('direct', .5), ('post', 1)]:
        plan = raw.copy()
        changed = delta != 0
        prefix = plan[:10]
        prefix[changed] = (raw[:10]+sign*delta)[changed]
        matched[name] = plan
    return raw, matched, np.ones((10, 4), dtype=np.float32)


def build(scale=1., seed=42):
    raw, formal, gradient = fixture()
    return raw, formal, construct_candidates13(raw, formal, gradient, seed, scale)


def delta(raw, plan):
    return plan[:10].astype(np.float64)-raw[:10].astype(np.float64)


def test_thirteen_retained_slots_and_exact_native_formal_identity():
    raw, formal, (plans, metadata, _) = build()
    assert tuple(plans) == CANDIDATE_ORDER
    assert len(plans) == metadata['candidate_count'] == 13
    assert metadata['a0_slot'] == 0
    assert plans['a0'].tobytes() == raw.tobytes()
    for name in formal:
        assert plans[name].tobytes() == formal[name].tobytes()
    for name, plan in plans.items():
        assert plan[10:].tobytes() == raw[10:].tobytes()
        assert plan[0].tobytes() == raw[0].tobytes() or name.startswith('random_')
        assert plan[:10][np.abs(raw[:10]) >= 1].tobytes() == raw[:10][np.abs(raw[:10]) >= 1].tobytes()
        assert metadata['candidates'][name]['retained'] is True
    json.dumps(metadata, allow_nan=False)


def test_channel_full_radius_is_exact_component_isolation_of_post():
    raw, formal, (plans, metadata, _) = build()
    np.testing.assert_array_equal(plans['xyz_positive'][:10, :3], formal['post'][:10, :3])
    np.testing.assert_array_equal(plans['xyz_positive'][:, 3], raw[:, 3])
    np.testing.assert_array_equal(plans['gripper_positive'][:10, 3], formal['post'][:10, 3])
    np.testing.assert_array_equal(plans['gripper_positive'][:, :3], raw[:, :3])
    assert not metadata['channels']['xyz']['fallback']
    assert not metadata['channels']['gripper']['fallback']


def test_channel_half_radius_changes_only_channels_not_formal_methods():
    raw, _, (full, _, _) = build(1.)
    _, formal, (half, metadata, _) = build(.5)
    for name in ('xyz_positive', 'xyz_negative', 'gripper_positive', 'gripper_negative'):
        np.testing.assert_allclose(delta(raw, half[name]), .5*delta(raw, full[name]), atol=3e-8, rtol=0)
    for name in formal:
        assert half[name].tobytes() == full[name].tobytes()
    for name in ('random_half_positive', 'random_full_positive'):
        assert half[name].tobytes() == full[name].tobytes()
    assert metadata['channel_radius_scale'] == .5


def test_all_pairs_and_actual_caps_with_clearance_and_raw_saturation():
    raw, _, (plans, metadata, _) = build()
    for pair in metadata['pair_symmetry']:
        np.testing.assert_allclose(delta(raw, plans[pair['positive']]), -delta(raw, plans[pair['negative']]), atol=1e-7, rtol=0)
        assert pair['passed']
    mask = np.asarray(metadata['clearance_mask'])
    for plan in plans.values():
        assert plan[:10][~mask].tobytes() == raw[:10][~mask].tobytes()
        d = delta(raw, plan)
        assert np.abs(d[:, :3]).max() <= .150001
        assert np.abs(d[:, 3]).max() <= .400001
        assert np.sqrt(np.mean(d[:, :3]**2)) <= .050001
        assert np.sqrt(np.mean(d[:, 3]**2)) <= .100001
    for sign in ('positive', 'negative'):
        np.testing.assert_allclose(delta(raw, plans['random_half_'+sign]), .5*delta(raw, plans['random_full_'+sign]), atol=3e-8, rtol=0)


def test_saved_critic_mapping_agrees_with_every_actual_raw_delta():
    raw, _, (plans, metadata, directions) = build()
    np.testing.assert_array_equal(directions['critic_a0'], np.clip(raw, -1, 1))
    for index, name in enumerate(CANDIDATE_ORDER):
        critic = directions['critic_candidates'][index]
        np.testing.assert_array_equal(critic, np.clip(plans[name], -1, 1))
        np.testing.assert_array_equal(directions['actual_deltas'][index], delta(raw, plans[name]))
        np.testing.assert_array_equal(critic[:10].astype(float)-directions['critic_a0'][:10].astype(float), delta(raw, plans[name]))
        assert metadata['candidates'][name]['critic_mapping_delta_max_error'] == 0


def test_near_boundary_direction_shrinks_symmetrically_without_clipping():
    raw = np.full((50, 4), .949, dtype=np.float32)
    formal = {name: raw.copy() for name in ('velocity', 'direct', 'post')}
    plans, metadata, _ = construct_candidates13(raw, formal, np.zeros((10, 4)), 3, 1.)
    assert all(metadata['random_groups'][group]['shrunk'] for group in ('xyz', 'gripper'))
    for sign in ('positive', 'negative'):
        assert np.max(np.abs(plans['random_full_'+sign][:10])) <= 1
    np.testing.assert_allclose(delta(raw, plans['random_full_positive']), -delta(raw, plans['random_full_negative']), atol=1e-7, rtol=0)


def test_random_stream_independent_of_critic_and_deterministic():
    raw, formal, gradient = fixture()
    one = construct_candidates13(raw, formal, gradient, 42, 1.)
    two = construct_candidates13(raw, formal, gradient*7, 42, 1.)
    changed = construct_candidates13(raw, formal, gradient, 43, 1.)
    for name in ('random_half_positive', 'random_half_negative', 'random_full_positive', 'random_full_negative'):
        assert one[0][name].tobytes() == two[0][name].tobytes()
    assert one[0]['random_full_positive'].tobytes() != changed[0]['random_full_positive'].tobytes()
    np.testing.assert_array_equal(one[2]['random_joint_knots'], two[2]['random_joint_knots'])
    assert one[1]['random_provenance']['spawn_keys'] == [[0], [1], [2]]


def test_zero_post_channel_uses_separate_fallback_without_zeroing_other_arms():
    raw, formal, gradient = fixture()
    formal['post'][:, 3] = raw[:, 3]
    plans, metadata, directions = construct_candidates13(raw, formal, gradient, 42, 1.)
    assert not metadata['channels']['xyz']['fallback']
    assert metadata['channels']['gripper']['fallback']
    assert metadata['channels']['gripper']['post_gradient_rms'] == 1
    assert np.any(delta(raw, plans['gripper_positive'])[:, 3] != 0)
    assert np.any(delta(raw, plans['random_full_positive'])[:, :3] != 0)
    assert np.any(delta(raw, plans['random_full_positive'])[:, 3] != 0)
    assert plans['post'].tobytes() == plans['xyz_positive'].tobytes()
    assert metadata['aliases']['post'] == 'xyz_positive'
    assert not np.array_equal(directions['random_joint_knots'], directions['random_gripper_fallback_knots'])


def test_all_zero_post_still_has_independent_random_and_fallback_pairs():
    raw = np.zeros((50, 4), dtype=np.float32)
    formal = {name: raw.copy() for name in ('velocity', 'direct', 'post')}
    plans, metadata, _ = construct_candidates13(raw, formal, np.zeros((10, 4)), 3, 1.)
    assert all(metadata['channels'][group]['fallback'] for group in ('xyz', 'gripper'))
    assert metadata['aliases']['post'] == metadata['aliases']['reverse_post'] == 'a0'
    assert metadata['unique_count'] == 9
    assert np.any(plans['xyz_positive']) and np.any(plans['gripper_positive'])
    assert np.any(plans['random_full_positive'])


def test_all_saturated_is_retained_one_unique_action_with_zero_direction():
    raw = np.full((50, 4), 1.2, dtype=np.float32)
    formal = {name: raw.copy() for name in ('velocity', 'direct', 'post')}
    plans, metadata, _ = construct_candidates13(raw, formal, np.ones((10, 4)), 3, .5)
    assert metadata['unique_count'] == 1 and metadata['retained_all']
    assert list(metadata['alias_groups']) == ['a0']
    assert len(metadata['alias_groups']['a0']) == 13
    for name in CANDIDATE_ORDER:
        assert plans[name].tobytes() == raw.tobytes()
        item = metadata['candidates'][name]
        assert item['alias'] == 'a0' and item['zero_delta'] and item['retained']
        assert item['deduplication_weight'] == 1/13
    assert sum(x['deduplication_weight'] for x in metadata['candidates'].values()) == pytest.approx(1)


def test_saturated_gripper_does_not_collapse_xyz_random_radius():
    raw = np.zeros((50, 4), dtype=np.float32)
    raw[:, 3] = 1.2
    formal = {name: raw.copy() for name in ('velocity', 'direct', 'post')}
    plans, metadata, _ = construct_candidates13(raw, formal, np.zeros((10, 4)), 3, 1.)
    assert metadata['random_groups']['gripper']['zero_group']
    assert not metadata['random_groups']['xyz']['zero_group']
    assert np.any(plans['random_full_positive'][:, :3] != raw[:, :3])
    assert metadata['aliases']['gripper_positive'] == 'a0'


def test_aliases_are_exact_raw_command_hashes_and_inputs_not_mutated():
    raw, formal, gradient = fixture()
    originals = copy.deepcopy((raw, formal, gradient))
    legacy = {name+'_matched': value for name, value in formal.items()}
    legacy['replan'] = raw
    plans, metadata, _ = construct_candidates13(raw, legacy, gradient, 3, 1.)
    assert raw.tobytes() == originals[0].tobytes()
    assert gradient.tobytes() == originals[2].tobytes()
    for name in formal:
        assert formal[name].tobytes() == originals[1][name].tobytes()
    for name, plan in plans.items():
        expected = hashlib.sha256(plan[:10].astype('<f4').tobytes()).hexdigest()
        assert metadata['candidates'][name]['command_sha256'] == expected
        assert plan[:10].tobytes() == plans[metadata['aliases'][name]][:10].tobytes()
    plans['a0'][0, 0] = 0
    assert raw.tobytes() == originals[0].tobytes()


@pytest.mark.parametrize('change,message', [
    ('tail', 'tail'), ('saturated', 'saturated'), ('clearance', 'clearance'),
    ('cap', 'cap'), ('nonfinite', 'nonfinite'), ('conflict', 'Conflicting'),
])
def test_invalid_formal_plans_fail_closed(change, message):
    raw, formal, gradient = fixture()
    if change == 'tail':
        formal['post'][20, 1] = .1
    elif change == 'saturated':
        formal['post'][0, 0] = 1.
    elif change == 'clearance':
        formal['post'][1, 0] = .97
    elif change == 'cap':
        formal['post'][2:10, :3] = .4
    elif change == 'nonfinite':
        formal['post'][0, 0] = np.nan
    elif change == 'conflict':
        formal['post_matched'] = raw.copy()
    with pytest.raises(ValueError, match=message):
        construct_candidates13(raw, formal, gradient, 42, 1.)


@pytest.mark.parametrize('scale', [0, .25, 2, True, np.nan])
def test_unregistered_channel_radius_rejected(scale):
    raw, formal, gradient = fixture()
    with pytest.raises(ValueError, match='channel_radius_scale'):
        construct_candidates13(raw, formal, gradient, 42, scale)


@pytest.mark.parametrize('seed', [-1, 1.5, True])
def test_invalid_random_seed_rejected(seed):
    raw, formal, gradient = fixture()
    with pytest.raises(ValueError, match='random_seed'):
        construct_candidates13(raw, formal, gradient, seed, 1.)


def test_float64_anchor_and_nonfinite_gradient_rejected():
    raw, formal, gradient = fixture()
    with pytest.raises(ValueError, match='float32'):
        construct_candidates13(raw.astype(np.float64), formal, gradient, 42, 1.)
    gradient[0, 0] = np.nan
    with pytest.raises(ValueError, match='gradient'):
        construct_candidates13(raw, formal, gradient, 42, 1.)


@pytest.mark.parametrize('cfg', [{'boundary_clearance': 0}, {'xyz_rms': .1}, {'gripper_linf': .5}])
def test_approved_clearance_and_caps_cannot_be_relaxed(cfg):
    raw, formal, gradient = fixture()
    with pytest.raises(ValueError, match='Approved|approved'):
        construct_candidates13(raw, formal, gradient, 42, 1., cfg)


def test_existing_formal_matcher_and_raw_wrapper_integrate_without_new_projection():
    from corrector.candidates import construct
    from corrector.config import DEFAULT_MATCHING
    from .commands import preserve_raw_anchor

    rng = np.random.default_rng(601)
    for seed in range(20):
        raw = rng.normal(0, .7, (50, 4)).astype(np.float32)
        raw[0, 3] = 1.6
        raw[1, 0] = .97
        base = np.clip(raw, -1, 1)
        velocity = np.clip(base+rng.normal(0, .1, (50, 4)), -1, 1).astype(np.float32)
        direct = np.clip(base+rng.normal(0, .1, (50, 4)), -1, 1).astype(np.float32)
        gradient = rng.normal(size=(10, 4))
        old, _ = construct(base, velocity, direct, gradient, seed, DEFAULT_MATCHING)
        formal = {name: preserve_raw_anchor(raw, base, old[name+'_matched'])
                  for name in ('velocity', 'direct', 'post')}
        plans, metadata, directions = construct_candidates13(raw, formal, gradient, seed, .5 if seed % 2 else 1.)
        for name in formal:
            assert plans[name].tobytes() == formal[name].tobytes()
            assert metadata['candidates'][name]['critic_mapping_delta_max_error'] == 0
        np.testing.assert_array_equal(directions['clearance_mask'], 1-np.abs(base[:10].astype(float)) >= .05)
