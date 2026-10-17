"""Outcome-blind thirteen-action bank in final raw environment commands.

This module neither calls a policy nor simulates. The three supplied deployment
plans have already been matched; they are validated and kept unchanged. Channel
ablations extract the actual post delta. Independent random pairs use their own
groupwise symmetric feasible radii, never a minimum over all thirteen actions.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping

import numpy as np


CANDIDATE_ORDER = (
    'a0', 'xyz_positive', 'xyz_negative',
    'gripper_positive', 'gripper_negative',
    'random_half_positive', 'random_half_negative',
    'random_full_positive', 'random_full_negative',
    'velocity', 'direct', 'post', 'reverse_post',
)
PAIRS = (
    ('xyz_positive', 'xyz_negative'),
    ('gripper_positive', 'gripper_negative'),
    ('random_half_positive', 'random_half_negative'),
    ('random_full_positive', 'random_full_negative'),
    ('post', 'reverse_post'),
)
DEFAULT_CONFIG = dict(
    xyz_rms=.05, gripper_rms=.10, xyz_linf=.15, gripper_linf=.40,
    boundary_clearance=.05, zero_threshold=1e-10, tolerance=1e-6,
)
_GROUPS = (('xyz', slice(0, 3)), ('gripper', slice(3, 4)))


def _sha(array):
    """Hash fixed-shape, little-endian float32 raw commands, including signed 0."""
    return hashlib.sha256(np.asarray(array, dtype='<f4').tobytes(order='C')).hexdigest()


def _plan(value, name):
    value = np.asarray(value)
    if value.shape != (50, 4) or value.dtype != np.dtype(np.float32):
        raise ValueError(f'{name} must be a float32 50 x 4 raw command plan')
    if not np.isfinite(value).all():
        raise ValueError(f'{name} contains nonfinite commands')
    return value.copy()


def _rms(value):
    return float(np.sqrt(np.mean(np.asarray(value, dtype=np.float64)**2)))


def _radii(delta):
    result = {}
    for group, indices in _GROUPS:
        result[group+'_rms'] = _rms(delta[:, indices])
        result[group+'_linf'] = float(np.abs(delta[:, indices]).max())
    return result


def _settings(cfg):
    settings = dict(DEFAULT_CONFIG)
    if cfg is not None:
        unknown = set(cfg) - set(settings)
        if unknown:
            raise ValueError(f'Unknown matching settings: {sorted(unknown)}')
        settings.update(cfg)
    for key, value in settings.items():
        if isinstance(value, (bool, np.bool_)) or not np.isfinite(value):
            raise ValueError(f'Invalid setting {key}')
        settings[key] = float(value)
    if settings['boundary_clearance'] != DEFAULT_CONFIG['boundary_clearance']:
        raise ValueError('Approved boundary_clearance is fixed at .05')
    for key in ('xyz_rms', 'gripper_rms', 'xyz_linf', 'gripper_linf',
                'zero_threshold', 'tolerance'):
        if settings[key] <= 0:
            raise ValueError(f'{key} must be positive')
    for key in ('xyz_rms', 'gripper_rms', 'xyz_linf', 'gripper_linf'):
        if settings[key] > DEFAULT_CONFIG[key]:
            raise ValueError(f'{key} exceeds the approved command cap')
    if settings['tolerance'] > 1e-5 or settings['zero_threshold'] > settings['tolerance']:
        raise ValueError('Numerical tolerances are too loose')
    return settings


def _smooth_direction(child_seed):
    knots = np.random.default_rng(child_seed).normal(size=(3, 4))
    direction = np.stack([
        np.interp(np.arange(10), [0., 4.5, 9.], knots[:, index])
        for index in range(4)
    ], axis=-1)
    return direction, knots


def _project_group(direction, bounded, mask, group, indices, cfg):
    """Scale one entire direction; ± share boundary and per-group caps."""
    selected = np.asarray(direction[:, indices], dtype=np.float64)*mask[:, indices]
    norm = _rms(selected)
    bounds = np.minimum(1-np.abs(bounded[:, indices]), cfg[group+'_linf'])
    if norm <= cfg['zero_threshold']:
        return np.zeros_like(selected), dict(
            masked_direction_rms=norm, requested_rms=cfg[group+'_rms'],
            feasible_radius=0., target_rms=0., zero_group=True, shrunk=True,
        )
    unit = selected/norm
    active = np.abs(unit) > cfg['zero_threshold']
    feasible = float(np.min(bounds[active]/np.abs(unit[active]))) if active.any() else 0.
    radius = max(0., min(cfg[group+'_rms'], feasible))*(1-1e-6)
    return radius*unit, dict(
        masked_direction_rms=norm, requested_rms=cfg[group+'_rms'],
        feasible_radius=feasible, target_rms=radius, zero_group=radius == 0.,
        shrunk=radius < cfg[group+'_rms']*(1-2e-6),
    )


def _emit(raw, delta):
    result = raw.copy()
    changed = delta != 0
    # Preserve the raw native anchor, including saturation and signed zeros.
    prefix = result[:10]
    prefix[changed] = (raw[:10].astype(np.float64)+delta)[changed].astype(np.float32)
    return result


def _validate_delta(raw, plan, name, mask, cfg):
    if plan[10:].tobytes() != raw[10:].tobytes():
        raise ValueError(f'{name} changes the unexecuted tail')
    fixed = ~mask
    if plan[:10][fixed].tobytes() != raw[:10][fixed].tobytes():
        raise ValueError(f'{name} changes a saturated or clearance-masked coordinate')
    delta = plan[:10].astype(np.float64)-raw[:10].astype(np.float64)
    radii = _radii(delta)
    for key, value in radii.items():
        if value > cfg[key]+cfg['tolerance']:
            raise ValueError(f'{name} exceeds {key} cap')
    bounded = np.clip(raw[:10].astype(np.float64), -1, 1)
    if np.any(np.abs(delta) > 1-np.abs(bounded)+cfg['tolerance']):
        raise ValueError(f'{name} lacks symmetric boundary feasibility')
    critic_delta = np.clip(plan[:10].astype(np.float64), -1, 1)-bounded
    if np.max(np.abs(critic_delta-delta)) > cfg['tolerance']:
        raise ValueError(f'{name} raw and critic command deltas disagree')
    return delta


def construct_candidates13(raw_a0, matched_plans, post_internal_metric_gradient,
                           random_seed, channel_radius_scale, cfg=None):
    """Return ``(plans, metadata, directions)`` with a0 permanently in slot 0.

    ``matched_plans`` supplies raw ``velocity``, ``direct`` and ``post`` plans;
    the existing ``*_matched`` names are also accepted. Extra legacy arms are
    ignored. The post gradient is the existing S²∇R direction, shape (10, 4),
    used for provenance/degeneracy diagnostics, never to renormalize post again.

    ``random_seed`` is a preregistered nonnegative integer. SeedSequence children
    0/1/2 respectively define the independent joint, XYZ fallback and gripper
    fallback streams. ``channel_radius_scale`` must be exactly .5 or 1.; the
    caller preregisters its source-balanced assignment before outcome access.

    Arrays remain float32 raw environment commands. SHA/alias equality uses the
    complete ten-step command prefix, not the clipped critic proxy. All thirteen
    entries are retained; inverse alias-group sizes permit later deduplication
    of absolute candidate losses without inventing independent samples. Physical
    outcome reuse additionally requires identical state, suffix seeds and seals.
    """
    settings = _settings(cfg)
    raw = _plan(raw_a0, 'raw_a0')
    gradient = np.asarray(post_internal_metric_gradient, dtype=np.float64)
    if gradient.shape != (10, 4) or not np.isfinite(gradient).all():
        raise ValueError('post_internal_metric_gradient must be finite 10 x 4')
    if isinstance(random_seed, (bool, np.bool_)) or not isinstance(random_seed, (int, np.integer)) or random_seed < 0:
        raise ValueError('random_seed must be a nonnegative integer')
    if isinstance(channel_radius_scale, (bool, np.bool_)) or channel_radius_scale not in (.5, 1.):
        raise ValueError('channel_radius_scale must be .5 or 1.')
    if not isinstance(matched_plans, Mapping):
        raise ValueError('matched_plans must be a mapping')
    scale = float(channel_radius_scale)
    bounded = np.clip(raw[:10].astype(np.float64), -1, 1)
    mask = (1-np.abs(bounded) >= settings['boundary_clearance']) & (np.abs(raw[:10]) < 1)
    formal, formal_delta = {}, {}
    for name in ('velocity', 'direct', 'post'):
        keys = [key for key in (name, name+'_matched') if key in matched_plans]
        if not keys:
            raise ValueError(f'Missing matched {name} plan')
        formal[name] = _plan(matched_plans[keys[0]], name)
        if len(keys) == 2 and formal[name].tobytes() != _plan(matched_plans[keys[1]], keys[1]).tobytes():
            raise ValueError(f'Conflicting aliases for {name}')
        formal_delta[name] = _validate_delta(raw, formal[name], name, mask, settings)

    seed_sequence = np.random.SeedSequence(int(random_seed))
    children = seed_sequence.spawn(3)
    streams = [_smooth_direction(child) for child in children]
    joint, joint_knots = streams[0]
    random_delta = np.zeros((10, 4), dtype=np.float64)
    channel_deltas, channel_stats, random_stats = {}, {}, {}
    for group_index, (group, indices) in enumerate(_GROUPS):
        random_delta[:, indices], random_stats[group] = _project_group(
            joint, bounded, mask, group, indices, settings)
        extracted = formal_delta['post'][:, indices].copy()
        fallback = _rms(extracted) <= settings['zero_threshold']
        projection = None
        if fallback:
            extracted, projection = _project_group(
                streams[group_index+1][0], bounded, mask, group, indices, settings)
        delta = np.zeros((10, 4), dtype=np.float64)
        delta[:, indices] = extracted*scale
        channel_deltas[group] = delta
        channel_stats[group] = dict(
            radius_scale=scale, source='independent_smooth_random_fallback' if fallback else 'final_post_delta_component',
            fallback=fallback, fallback_reason='post_actual_channel_rms_at_or_below_zero_threshold' if fallback else None,
            post_actual_rms=_rms(formal_delta['post'][:, indices]),
            post_gradient_rms=_rms(gradient[:, indices]),
            post_masked_gradient_rms=_rms(gradient[:, indices]*mask[:, indices]),
            fallback_projection=projection, requested_delta=_radii(delta),
        )

    # Use the already-realized full random delta for both smaller-radius arms.
    # This makes float32 rounding, rather than a second projection, the sole
    # possible discrepancy from exact one-half relationships.
    full_random = _emit(raw, random_delta)
    realized_random = full_random[:10].astype(np.float64)-raw[:10].astype(np.float64)
    plans = {'a0': raw.copy()}
    for group in ('xyz', 'gripper'):
        plans[group+'_positive'] = _emit(raw, channel_deltas[group])
        positive_delta = plans[group+'_positive'][:10].astype(np.float64)-raw[:10].astype(np.float64)
        plans[group+'_negative'] = _emit(raw, -positive_delta)
    plans.update(
        random_half_positive=_emit(raw, realized_random*.5),
        random_half_negative=_emit(raw, -realized_random*.5),
        random_full_positive=full_random,
        random_full_negative=_emit(raw, -realized_random),
        **formal,
        reverse_post=_emit(raw, -formal_delta['post']),
    )
    plans = {name: plans[name] for name in CANDIDATE_ORDER}
    actual = {name: _validate_delta(raw, plan, name, mask, settings)
              for name, plan in plans.items()}
    aliases, canonical_by_hash, members = {}, {}, {}
    records = {}
    for index, (name, plan) in enumerate(plans.items()):
        sha = _sha(plan[:10])
        canonical = canonical_by_hash.setdefault(sha, name)
        aliases[name] = canonical
        members.setdefault(canonical, []).append(name)
        records[name] = dict(
            slot=index, retained=True, command_sha256=sha, plan_sha256=_sha(plan),
            alias=canonical, duplicate_of=canonical if canonical != name else None,
            actual=_radii(actual[name]), zero_delta=not bool(np.any(actual[name])),
            changed_coordinates=int(np.count_nonzero(actual[name])),
            critic_mapping_delta_max_error=float(np.abs(
                np.clip(plan[:10].astype(np.float64), -1, 1)-bounded-actual[name]
            ).max()),
        )
    for name, record in records.items():
        record['alias_group_size'] = len(members[aliases[name]])
        record['deduplication_weight'] = 1./record['alias_group_size']
    pairs = []
    for positive, negative in PAIRS:
        error = float(np.abs(actual[positive]+actual[negative]).max())
        if error > settings['tolerance']:
            raise ValueError(f'Asymmetric realized pair {positive}/{negative}: {error}')
        pairs.append(dict(positive=positive, negative=negative,
                          max_abs_sum_delta=error, passed=True,
                          distinct=aliases[positive] != aliases[negative]))
    half_errors = {
        sign: float(np.abs(actual['random_half_'+sign]-.5*actual['random_full_'+sign]).max())
        for sign in ('positive', 'negative')
    }
    if max(half_errors.values()) > settings['tolerance']:
        raise ValueError('Random half/full radius relation changed')
    metadata = dict(
        schema='native10_candidates13_v1', a0_slot=0, candidate_order=list(CANDIDATE_ORDER),
        candidate_count=13, unique_count=len(members), candidates=records,
        aliases=aliases, alias_groups=members, canonical_candidates=list(members),
        channel_radius_scale=scale, channels=channel_stats, random_groups=random_stats,
        pair_symmetry=pairs, random_half_full_max_error=half_errors,
        raw_a0_sha256=_sha(raw), settings=settings,
        matching_scope='formal velocity/direct/post unchanged; channel and random pairs separately feasible',
        native_saturated_coordinates_unchanged=True, tail_bit_identical=True,
        masked_fraction=float((~mask).mean()), clearance_mask=mask.tolist(),
        retained_all=True, actual_command_space='raw float32 environment commands; no additional clipping',
        random_provenance=dict(seed=int(random_seed), generator='numpy.default_rng(SeedSequence child)',
            numpy_version=np.__version__, interpolation_steps=[0., 4.5, 9.],
            stream_names=['joint', 'xyz_fallback', 'gripper_fallback'],
            spawn_keys=[list(child.spawn_key) for child in children]),
        simulator_calls=0,
    )
    directions = dict(
        raw_a0=raw.copy(), post_internal_metric_gradient=gradient.copy(),
        critic_a0=np.clip(raw, -1, 1), clearance_mask=mask.copy(),
        critic_candidates=np.stack([np.clip(plans[name], -1, 1) for name in CANDIDATE_ORDER]),
        actual_deltas=np.stack([actual[name] for name in CANDIDATE_ORDER]),
        post_actual_delta=formal_delta['post'].copy(), random_full_requested_delta=random_delta,
        random_full_actual_delta=actual['random_full_positive'].copy(),
        xyz_requested_delta=channel_deltas['xyz'], gripper_requested_delta=channel_deltas['gripper'],
        random_joint_knots=joint_knots, random_xyz_fallback_knots=streams[1][1],
        random_gripper_fallback_knots=streams[2][1],
    )
    return plans, metadata, directions
