"""LIBERO-native head and physical-command Post operator; NumPy only."""
from pathlib import Path
import numpy as np

FEATURE_DIM = 329


def action_norm(stats):
    q0 = np.asarray(stats['actions']['q01'], dtype=np.float64)
    q1 = np.asarray(stats['actions']['q99'], dtype=np.float64)
    return (q0 + q1) / 2, (q1 - q0) / 2


def dev_candidate(reference, candidate_id, seed, spec):
    """Reference plus two antithetic, parent-seeded exploratory directions."""
    reference = np.asarray(reference, dtype=np.float32)
    result = reference.copy()
    if candidate_id == 0:
        return result
    pair = (int(candidate_id) - 1) // 2
    sign = 1 if int(candidate_id) % 2 else -1
    rng = np.random.Generator(np.random.PCG64(int(seed) + 1009 * pair))
    direction = rng.normal(size=3)
    direction /= max(np.linalg.norm(direction), 1e-12)
    # One coherent displacement direction over the five committed commands.
    delta = sign * spec['dev_xyz_command_amplitude'] * direction
    result[:5, :3] = np.clip(reference[:5, :3] + delta, -1, 1)
    if pair == 1:
        result[:5, 6] = float(sign)
    assert np.array_equal(result[:, 3:6], reference[:, 3:6])
    assert np.array_equal(result[5:], reference[5:])
    return result


class Head:
    def __init__(self, path):
        with np.load(str(path), allow_pickle=False) as z:
            self.a = {k: z[k].astype(np.float64) for k in z.files}
        self.members = int(self.a['members'])
        assert self.a['feature_mean'].shape == (FEATURE_DIM,)

    def q_grad(self, feature, candidate, reference):
        a = self.a
        s = a['action_scale']
        x = np.concatenate(((np.asarray(feature) - a['feature_mean']) / a['feature_std'],
                            ((np.asarray(candidate) - a['action_mid']) / s).reshape(-1),
                            ((np.asarray(reference) - a['action_mid']) / s).reshape(-1)))
        assert x.shape == (FEATURE_DIM + 70,)
        qsum, gsum = 0., np.zeros(35, dtype=np.float64)
        for m in range(self.members):
            p = 'm%d_' % m
            u = a[p+'w0'] @ x + a[p+'b0']
            v = a[p+'w1'] @ np.maximum(u, 0) + a[p+'b1']
            logit = float((a[p+'w2'] @ np.maximum(v, 0) + a[p+'b2'])[0])
            q = float(1 / (1 + np.exp(-np.clip(logit, -60, 60))))
            gv = a[p+'w2'][0] * q * (1-q) * (v > 0)
            gu = (gv @ a[p+'w1']) * (u > 0)
            gx = gu @ a[p+'w0']
            qsum += q
            gsum += gx[FEATURE_DIM:FEATURE_DIM+35]
        return qsum/self.members, gsum.reshape(5, 7) / s / self.members

    def correct(self, feature, reference, spec):
        reference = np.asarray(reference, dtype=np.float32)
        anchor = reference[:5].astype(np.float64)
        q0, grad = self.q_grad(feature, anchor, anchor)
        direction = grad * self.a['action_scale'] ** 2
        return self.project(feature, reference, direction, spec)

    def project(self, feature, reference, direction, spec):
        reference = np.asarray(reference, dtype=np.float32)
        anchor = reference[:5].astype(np.float64)
        direction = np.asarray(direction, dtype=np.float64)
        if direction.shape != (5, 7) or not np.isfinite(direction).all():
            raise ValueError('Expected finite native physical direction5x7')
        q0, _ = self.q_grad(feature, anchor, anchor)
        delta = np.zeros_like(anchor)
        for indices, radius, cap in (([0,1,2], spec['post_xyz_command_rms'], spec['post_xyz_command_cap']),
                                     ([6], spec['post_grip_command_rms'], spec['post_grip_command_cap'])):
            values = direction[:, indices].copy()
            # Symmetric feasible interval: never drag an out-of-range raw anchor.
            room = np.maximum(0, 1 - np.abs(anchor[:, indices]))
            values[room < spec['boundary_margin']] = 0
            norm = np.sqrt(np.mean(values ** 2))
            if norm > 1e-12:
                values *= radius / norm
            limit = np.minimum(cap, room)
            values = np.clip(values, -limit, limit)
            delta[:, indices] = values
        result = reference.copy()
        for indices in ([0,1,2], [6]):
            result[:5, indices] = (anchor[:, indices] + delta[:, indices]).astype(np.float32)
        assert np.array_equal(result[:, 3:6], reference[:, 3:6])
        assert np.array_equal(result[5:], reference[5:])
        applied = result[:5].astype(np.float64) - anchor
        if np.max(np.abs(applied[:,:3])) > spec['post_xyz_command_cap'] + 1e-6:
            raise ValueError('XYZ Post exceeded frozen cap')
        if np.max(np.abs(applied[:,6])) > spec['post_grip_command_cap'] + 1e-6:
            raise ValueError('Gripper Post exceeded frozen cap')
        q1, _ = self.q_grad(feature, result[:5], anchor)
        return result, dict(q_before=q0, q_after=q1, applied=bool(np.any(applied)),
            xyz_command_rms=float(np.sqrt(np.mean(applied[:,:3]**2))),
            xyz_delta_m_rms=float(.05*np.sqrt(np.mean(applied[:,:3]**2))),
            xyz_command_max=float(np.max(np.abs(applied[:,:3]))),
            gripper_command_rms=float(np.sqrt(np.mean(applied[:,6]**2))),
            rotations_unchanged=True, tail_unchanged=True)
