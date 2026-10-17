# Extracted from ACT-RECAP/tests/test_ogg_flow_matching.py
# Source SHA256: cc2a3004290c1cc9813af1d1d55b327fd4a50952ef22126388ae39bb925cbd36
"""Check executed command contracts, independently of critic or rollout outcomes."""
import numpy as np
import pytest

from corrector.candidates import construct
from corrector.config import MATCHED


@pytest.fixture
def settings():
    return dict(xyz_rms=.05, gripper_rms=.10, xyz_linf=.15,
                gripper_linf=.4, boundary_clearance=.05,
                tolerance=1e-6, zero_threshold=1e-10)


def inputs():
    base = np.zeros((50, 4), dtype=np.float32)
    base[10:] = np.random.default_rng(1).uniform(-1, 1, (40, 4))
    velocity = base.copy()
    direct = base.copy()
    velocity[:10] = [.025, -.04, .06, -.03]
    direct[:10] = [-.06, -.03, .02, .08]
    post = np.tile([.7, -.2, .1, .4], (10, 1))
    return base, velocity, direct, post


def actual_delta(plans, base, name):
    # Measure saved float32 environment commands, not unrounded latent deltas.
    return plans[name][:10].astype(np.float64) - base[:10].astype(np.float64)


def test_actual_command_group_rms_and_reverse_symmetry(settings):
    base, velocity, direct, post = inputs()
    originals = [x.copy() for x in [base, velocity, direct, post]]
    plans, info = construct(base, velocity, direct, post, 7, settings)
    for name in MATCHED:
        delta = actual_delta(plans, base, name)
        assert np.sqrt(np.mean(delta[:, :3] ** 2)) == pytest.approx(.05, abs=2e-7)
        assert np.sqrt(np.mean(delta[:, 3] ** 2)) == pytest.approx(.10, abs=2e-7)
        np.testing.assert_array_equal(plans[name][10:], base[10:])
    np.testing.assert_allclose(
        actual_delta(plans, base, 'direct_matched'),
        -actual_delta(plans, base, 'reverse_matched'), atol=1e-7, rtol=0)
    np.testing.assert_array_equal(plans['replan'], base)
    for original, current in zip(originals, [base, velocity, direct, post]):
        np.testing.assert_array_equal(original, current)
    assert not info['groups']['xyz']['zero_group']
    assert not info['groups']['gripper']['zero_group']


def test_common_mask_preserves_saturated_and_near_boundary_coordinates(settings):
    base, velocity, direct, post = inputs()
    base[:2] = [[1, -1, .97, -.97], [-.951, .951, .99, -.99]]
    velocity[:2] = 0
    direct[:2] = .2
    plans, info = construct(base, velocity, direct, post, 7, settings)
    for name in MATCHED:
        np.testing.assert_array_equal(plans[name][:2], base[:2])
        assert np.max(np.abs(plans[name])) <= 1
        np.testing.assert_array_equal(plans[name][10:], base[10:])
    assert not np.asarray(info['mask'])[:2].any()
    assert info['masked_fraction'] == pytest.approx(8 / 40)
    np.testing.assert_allclose(
        plans['direct_matched'][:10].astype(float) + plans['reverse_matched'][:10],
        2 * base[:10].astype(float), atol=1e-7, rtol=0)


def test_common_radius_shrinks_for_executed_coordinate_caps(settings):
    base, velocity, direct, post = inputs()
    velocity[:10, :3] = 0
    velocity[0, 0] = .01  # Concentrated direction: RMS alone does not bound Linf.
    base[:10, 3] = .925  # Both signs must fit a clearance of only .075.
    velocity[:10, 3] = .95
    direct[:10, 3] = .9
    plans, info = construct(base, velocity, direct, post, 7, settings)
    xyz_radii, gripper_radii = [], []
    for name in MATCHED:
        delta = actual_delta(plans, base, name)
        xyz_radii.append(np.sqrt(np.mean(delta[:, :3] ** 2)))
        gripper_radii.append(np.sqrt(np.mean(delta[:, 3] ** 2)))
        assert np.max(np.abs(delta[:, :3])) <= .15 + 1e-7
        assert np.max(np.abs(delta[:, 3])) <= .075 + 1e-7
        assert np.max(np.abs(plans[name])) <= 1
    np.testing.assert_allclose(xyz_radii, .15 / np.sqrt(30), atol=1e-7, rtol=0)
    assert max(gripper_radii) - min(gripper_radii) < 1e-7
    assert max(gripper_radii) < .075
    assert info['groups']['xyz']['shrunk']
    assert info['groups']['gripper']['shrunk']


@pytest.mark.parametrize('zero_group', ['xyz', 'gripper'])
def test_one_zero_direction_causes_common_group_fallback(settings, zero_group):
    base, velocity, direct, post = inputs()
    group = slice(0, 3) if zero_group == 'xyz' else slice(3, 4)
    other = slice(3, 4) if zero_group == 'xyz' else slice(0, 3)
    post[:, group] = 0
    plans, info = construct(base, velocity, direct, post, 7, settings)
    for name in MATCHED:
        np.testing.assert_array_equal(plans[name][:10, group], base[:10, group])
        assert np.linalg.norm(actual_delta(plans, base, name)[:, other]) > 0
        np.testing.assert_array_equal(plans[name][10:], base[10:])
    assert info['groups'][zero_group]['zero_group']
    assert info['groups'][zero_group]['achieved_target'] == 0


def test_fully_saturated_plan_is_retained_as_common_noop(settings):
    base, velocity, direct, post = inputs()
    base[:10] = np.where(np.arange(40).reshape(10, 4) % 2, -1., 1.)
    plans, info = construct(base, velocity, direct, post, 7, settings)
    for name in MATCHED:
        np.testing.assert_array_equal(plans[name], base)
    assert info['masked_fraction'] == 1
    assert all(info['groups'][group]['zero_group'] for group in ['xyz', 'gripper'])


def test_seeded_random_control_and_native_arms_remain_distinct(settings):
    base, velocity, direct, post = inputs()
    first, _ = construct(base, velocity, direct, post, 7, settings)
    repeated, _ = construct(base, velocity, direct, post, 7, settings)
    different, _ = construct(base, velocity, direct, post, 8, settings)
    for name in first:
        np.testing.assert_array_equal(first[name], repeated[name])
    assert not np.array_equal(first['random_matched'], different['random_matched'])
    np.testing.assert_array_equal(first['velocity_native'], velocity)
    np.testing.assert_array_equal(first['direct_native'], direct)
    assert not np.array_equal(first['velocity_matched'], first['velocity_native'])
    assert not np.array_equal(first['direct_matched'], first['direct_native'])
