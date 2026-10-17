"""Native raw commands remain the anchor; only feasible matched deltas change."""
import numpy as np


def preserve_raw_anchor(raw_a0, bounded_a0, bounded_candidate):
    raw = np.asarray(raw_a0, dtype=np.float32)
    base = np.asarray(bounded_a0, dtype=np.float32)
    candidate = np.asarray(bounded_candidate, dtype=np.float32)
    if raw.shape != (50, 4) or candidate.shape != raw.shape or base.shape != raw.shape:
        raise ValueError('Expected 50 x 4 plans')
    if not all(np.isfinite(x).all() for x in (raw, base, candidate)):
        raise ValueError('Nonfinite command')
    np.testing.assert_array_equal(base, np.clip(raw, -1, 1))
    if (np.abs(candidate) > 1).any():
        raise ValueError('Candidate matcher must remain bounded')
    delta = candidate.astype(np.float64) - base.astype(np.float64)
    if np.any(delta[10:] != 0):
        raise ValueError('Only the ten-step prefix can be changed')
    allowed = 1-np.abs(base.astype(np.float64)) >= .05
    if np.any(delta[~allowed] != 0):
        raise ValueError('Native saturated/near-boundary commands outside mask must be unchanged')
    # Copy the candidate only where it changes. Re-adding a zero delta can alter
    # signed zero; exact identity at zero correction is part of the contract.
    result = raw.copy()
    changed = delta != 0
    result[changed] = candidate[changed]
    np.testing.assert_array_equal(np.clip(result, -1, 1), candidate)
    return result
