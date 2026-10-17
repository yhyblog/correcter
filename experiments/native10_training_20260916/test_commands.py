import numpy as np
import pytest
from .commands import preserve_raw_anchor


def test_raw_anchor_and_zero_correction_are_exact():
    raw = np.zeros((50, 4), np.float32)
    raw[0] = [1.2, -1.3, -0., 2.1]
    bounded = np.clip(raw, -1, 1)
    result = preserve_raw_anchor(raw, bounded, bounded)
    assert result.tobytes() == raw.tobytes()


def test_only_feasible_delta_changes_and_true_amplitude_matches():
    raw = np.full((50, 4), .2, np.float32)
    raw[0] = [1.2, -1.3, 0., 2.1]
    bounded = np.clip(raw, -1, 1)
    candidate = bounded.copy()
    candidate[1:10, :3] += .03
    result = preserve_raw_anchor(raw, bounded, candidate)
    np.testing.assert_array_equal(result[0], raw[0])
    np.testing.assert_array_equal(result.astype(float)-raw, candidate.astype(float)-bounded)


def test_saturated_coordinate_cannot_be_changed_by_projection():
    raw = np.zeros((50, 4), np.float32)
    raw[0, 3] = 2
    bounded = np.clip(raw, -1, 1)
    candidate = bounded.copy()
    candidate[0, 3] = .9
    with pytest.raises(ValueError, match='saturated'):
        preserve_raw_anchor(raw, bounded, candidate)


def test_near_boundary_mask_is_enforced_without_saturation():
    raw=np.zeros((50,4),np.float32)
    raw[0,0]=.97
    candidate=raw.copy()
    candidate[0,0]=.96
    with pytest.raises(ValueError,match='mask'):
        preserve_raw_anchor(raw,raw.copy(),candidate)
