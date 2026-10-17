"""Read-only raw-command, prediction and cost descriptions after the full audit.

Nothing here constructs a model, generates candidates, computes a gradient,
changes a gate, selects a method, or reads partially completed new results.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import protocol, storage
from .statistics import SOLO_METHODS, REGISTERED_PRIMARY_IDS

FULL = dict(solo_velocity='velocity', solo_direct='direct', solo_post='post')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def describe(values):
    values = np.asarray(values, float)
    require(values.ndim == 1 and np.isfinite(values).all(), 'Cost/metric summaries require finite scalar inputs')
    if not len(values):
        return dict(count=0, mean=None, median=None, p95=None, minimum=None, maximum=None, sum=None)
    return dict(count=len(values), mean=float(values.mean()), median=float(np.median(values)),
        p95=float(np.quantile(values, .95, method='linear')), minimum=float(values.min()),
        maximum=float(values.max()), sum=float(values.sum()))


def _ranks(values):
    order = np.argsort(values, kind='stable'); ranks = np.empty(len(values), float)
    start = 0
    while start < len(values):
        end = start+1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = (start+end-1)/2
        start = end
    return ranks


def association(predicted, actual):
    x, y = np.asarray(predicted, float), np.asarray(actual, float)
    require(x.shape == y.shape and x.ndim == 1, 'Paired source prediction arrays required')
    valid = np.isfinite(x) & np.isfinite(y); x, y = x[valid], y[valid]
    estimable = len(x) >= 2 and np.ptp(x) > 0 and np.ptp(y) > 0
    return dict(pairs=int(valid.sum()), excluded_nonfinite=int((~valid).sum()),
        mean_predicted_gain=float(x.mean()) if len(x) else None,
        mean_actual_source_gain=float(y.mean()) if len(y) else None,
        mean_prediction_minus_observed_gain=float((x-y).mean()) if len(x) else None,
        pearson=float(np.corrcoef(x, y)[0, 1]) if estimable else None,
        spearman_average_ties=float(np.corrcoef(_ranks(x), _ranks(y))[0, 1]) if estimable else None,
        correlation_defined=bool(estimable), descriptive_only=True, q_acceptance_rule_added=False)


def _angle(first, second, threshold):
    a, b = np.asarray(first, float).ravel(), np.asarray(second, float).ravel()
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na <= threshold or nb <= threshold:
        return None
    return float(np.degrees(np.arccos(np.clip(np.dot(a, b)/(na*nb), -1., 1.))))


def method_diagnostic(method, saved, meta, old_formal, old_generation, outcomes, cfg):
    """Pure arithmetic on already audited arrays and four paired labels."""
    full = FULL[method]; raw = np.asarray(saved['raw_a0']); plan = np.asarray(saved['raw_plan'])
    delta = plan[:10].astype(float)-raw[:10].astype(float)
    old = np.asarray(old_formal[full+'_matched_actual_delta'], float)
    require(delta.shape == old.shape == (10, 4) and np.isfinite(delta).all() and np.isfinite(old).all(),
        'Finite ten-command raw perturbations required')
    zero, tolerance = cfg['zero_threshold'], cfg['tolerance']
    mask = np.asarray(saved['mask']); require(mask.shape == (10, 4) and mask.dtype == np.dtype('bool'), 'Audited mask required')
    caps_passed = all(np.max(np.abs(delta[:, indices])) <= cfg[name+'_linf']+tolerance
        for name, indices in (('xyz', slice(0,3)), ('gripper', slice(3,4))))
    mask_passed = not np.any(delta[~mask] != 0)
    require(caps_passed and mask_passed, 'Previously audited cap/mask invariants changed')
    groups = {}
    for name, indices in (('xyz', slice(0,3)), ('gripper', slice(3,4))):
        a, b = delta[:, indices], old[:, indices]
        new_rms, old_rms = float(np.sqrt(np.mean(a*a))), float(np.sqrt(np.mean(b*b)))
        new_zero, old_zero = new_rms <= zero, old_rms <= zero
        new_radius = float(meta['matching']['groups'][name]['achieved_target'])
        old_radius = float(old_generation['matching']['groups'][name]['achieved_target'])
        groups[name] = dict(solo_actual_rms=new_rms, old_matched_actual_rms=old_rms,
            new_over_old_rms=None if old_zero else new_rms/old_rms,
            old_actual_zero=old_zero, new_actual_zero=new_zero,
            old_zero_recovered=old_zero and not new_zero,
            old_matching_zero=bool(old_generation['matching']['groups'][name]['zero_group']),
            new_matching_zero=bool(meta['matching']['groups'][name]['zero_group']),
            solo_radius=new_radius, old_common_radius=old_radius,
            shared_capacity_constraint_released=new_radius > old_radius+tolerance,
            actual_rms_increased=new_rms > old_rms+tolerance,
            actual_delta_angle_degrees=_angle(a, b, zero),
            solo_linf=float(np.abs(a).max()), old_matched_linf=float(np.abs(b).max()))
    candidate = np.asarray(outcomes[method], bool); baseline = np.asarray(outcomes['alarm_replan10'], bool)
    previous = np.asarray(outcomes[full], bool)
    require(candidate.shape == baseline.shape == previous.shape == (4,), 'Four paired source repeats required')
    predicted = float(meta['predictions'][method]['mean_gain'])
    old_predicted = float(old_generation['bank_predictions'][full]['mean_gain'])
    require(np.isfinite([predicted, old_predicted]).all(), 'Audited saved Q gains must be finite')
    calls = meta['actual_policy_calls']; wanted = 1 if method == 'solo_post' else 2
    require(type(calls) is int and calls == wanted and meta['includes_own_a0_generation'] is True
        and meta['cached_a0_used'] is False and meta['restore_included'] is False
        and meta['model_loading_included'] is False, 'Independent entry cost is missing its own a0 or overlaps restore/loading')
    full_entry = float(meta['full_entry_seconds'])
    require(np.isfinite(full_entry) and full_entry >= 0, 'Finite nonnegative complete entry timer required')
    return dict(method=method, old_method=full, groups=groups,
        whole_actual_delta_angle_degrees=_angle(delta, old, zero),
        angle_interpretation='between executed raw perturbations; undefined at zero, not proof of historical native V/D identity',
        mask_and_cap_audit_passed=True, masked_coordinate_fraction=float((~mask).mean()),
        predicted_solo_minus_replan=predicted, predicted_old_matched_minus_replan=old_predicted,
        predicted_solo_minus_old_matched=predicted-old_predicted,
        actual_solo_minus_replan=float((candidate.astype(int)-baseline.astype(int)).mean()),
        actual_old_matched_minus_replan=float((previous.astype(int)-baseline.astype(int)).mean()),
        actual_solo_minus_old_matched=float((candidate.astype(int)-previous.astype(int)).mean()),
        cost=dict(actual_policy_calls=calls, full_entry_seconds=full_entry,
            own_a0_seconds=float(meta['component_seconds']['base_wall_seconds']),
            component_seconds=meta['component_seconds'], includes_own_a0_generation=True,
            diagnostic_scoring_included=meta['diagnostic_scoring_included'], cached_a0_used=False,
            component_timers_overlap_and_must_not_be_added=True,
            excludes_model_loading_and_environment_restore=True))


def aggregate_sources(rows):
    """Aggregate descriptive source records; caller owns the complete-cohort gate."""
    result = {}
    for method in SOLO_METHODS:
        records = [row['methods'][method] for row in rows]; groups = {}
        for name in ('xyz', 'gripper'):
            vals = [row['groups'][name] for row in records]
            ratio = [v['new_over_old_rms'] for v in vals if v['new_over_old_rms'] is not None]
            angles = [v['actual_delta_angle_degrees'] for v in vals if v['actual_delta_angle_degrees'] is not None]
            groups[name] = dict(solo_actual_rms=describe([v['solo_actual_rms'] for v in vals]),
                old_matched_actual_rms=describe([v['old_matched_actual_rms'] for v in vals]),
                new_over_old_rms_on_nonzero_old=describe(ratio), ratio_undefined_old_zero=sum(v['old_actual_zero'] for v in vals),
                old_zero_recovered_sources=sum(v['old_zero_recovered'] for v in vals),
                new_zero_sources=sum(v['new_actual_zero'] for v in vals),
                old_matching_zero_sources=sum(v['old_matching_zero'] for v in vals),
                new_matching_zero_sources=sum(v['new_matching_zero'] for v in vals),
                released_capacity_sources=sum(v['shared_capacity_constraint_released'] for v in vals),
                increased_actual_rms_sources=sum(v['actual_rms_increased'] for v in vals),
                actual_delta_angle_degrees_on_nonzero_pairs=describe(angles), angle_undefined_sources=len(vals)-len(angles))
        result[method] = dict(cut_sources=len(records), groups=groups,
            whole_actual_delta_angle_degrees=describe([r['whole_actual_delta_angle_degrees'] for r in records
                if r['whole_actual_delta_angle_degrees'] is not None]),
            q_vs_actual_solo_minus_replan=association([r['predicted_solo_minus_replan'] for r in records],
                [r['actual_solo_minus_replan'] for r in records]),
            q_vs_actual_old_matched_minus_replan=association([r['predicted_old_matched_minus_replan'] for r in records],
                [r['actual_old_matched_minus_replan'] for r in records]),
            q_change_vs_actual_solo_minus_old_matched=association([r['predicted_solo_minus_old_matched'] for r in records],
                [r['actual_solo_minus_old_matched'] for r in records]),
            actual_policy_calls=describe([r['cost']['actual_policy_calls'] for r in records]),
            full_entry_seconds_including_own_a0=describe([r['cost']['full_entry_seconds'] for r in records]),
            own_a0_seconds=describe([r['cost']['own_a0_seconds'] for r in records]),
            amortized_shared_a0_cost_used=False)
    return result


class Reader:
    def __init__(self, artifacts):
        self.refs = {str(Path(row['path']).resolve()):row['sha256'] for row in artifacts}
        require(len(self.refs) == len(artifacts), 'Diagnostic input audit contains repeated file references')
        self.used = {}

    def path(self, path):
        path = Path(path).resolve(); key = str(path)
        require(key in self.refs, 'Diagnostic read was not covered by the completed artifact audit: '+key)
        storage.checked(path, self.refs[key]); self.used[key] = self.refs[key]
        return path

    def json(self, path):
        return json.loads(self.path(path).read_text())

    def arrays(self, path):
        with np.load(self.path(path), allow_pickle=False) as archive:
            return {name:archive[name].copy() for name in archive.files}


def _cost(rows, name):
    values = [row[name] for row in rows]
    require(all(isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 for v in values),
        'Cost fields must be observed nonnegative values: '+name)
    return describe(values)


def _preflight_reference_cost(config):
    folder = storage.ROOT/'preflight_audits'/config['protocol_version']
    seal = storage.sealed(folder); result_path = folder/'result.json'; result = storage.read(result_path)
    require(seal.get('role') == 'standalone_preflight_audit' and result.get('status') == 'passed'
        and result.get('protocol_sha256') == config['analysis_approval']['protocol_sha256'],
        'Separate passed preflight audit required for reference costs')
    reader = Reader(result['artifacts']); banks, entries = [], []
    for identity in config['execution_plans'][protocol.PREFLIGHT]['episode_ids']:
        cut = config['inputs']['sources'][identity]['actual_cut']
        path = storage.ROOT/'banks'/protocol.PREFLIGHT/identity/f'cut{cut:03d}'/'reference/generation.json'
        bank = reader.json(path); banks.append(bank); entries.append(bank['independent_entries']['reference'])
    return dict(stage=protocol.PREFLIGHT, sources=len(banks), diagnostic_only=True,
        independent_of_formal_generation=True, solo_success_aggregated=False,
        reference_complete_entry_seconds=_cost(entries, 'reference_full_entry_seconds'),
        reference_actual_policy_calls=_cost(entries, 'actual_policy_calls'),
        reference_restore_seconds=_cost(banks, 'restore_seconds'),
        reference_bundle_wall_including_restore_seconds=_cost(banks, 'wall_seconds'),
        audit=dict(path=str(folder), seal_sha256=storage.sha256(folder/'complete.json'), result_sha256=storage.sha256(result_path)),
        files_read=reader.used)


def summarize(config, audited):
    """Inspect SHA-bound metadata only AFTER formal trajectories/statistics pass."""
    stats = audited.get('statistics', {}); gate = audited.get('wave_gate', {})
    require(audited.get('status') == 'passed' and audited.get('stage') == protocol.FORMAL
        and audited.get('role') == 'standalone_ablation_full_static_audit_v1'
        and audited.get('completed_sources') == 100 and audited.get('reached_sources') == 98
        and audited.get('no_cut_sources') == 2 and audited.get('loaded_workers') == 32
        and gate.get('all_slots_complete') is True and gate.get('lifecycle_returncode') == 0
        and stats.get('status') == 'complete_fixed_ablation_statistics'
        and stats.get('logical_outcomes_per_arm') == 400
        and stats.get('primary_ids') == list(REGISTERED_PRIMARY_IDS),
        'Diagnostics require the full formal audit; preflight and partial effects are forbidden')
    rows = audited['per_source']
    require([r['planned_slot_id'] for r in rows] == list(REGISTERED_PRIMARY_IDS), 'Original source order changed')
    reader = Reader(audited['artifacts']); sources, bundles, old_bundles = [], [], []
    branch_costs = {method:[] for method in SOLO_METHODS}
    for row in rows:
        if row['no_cut']:
            continue
        identity = row['planned_slot_id']; bound = config['inputs']['sources'][identity]; cut = row['actual_cut']
        old_path = Path(bound['old_bank_path']); old_formal = reader.arrays(old_path/'formal_directions.npz')
        old_generation = reader.json(old_path/'generation.json'); old_bundles.append(old_generation)
        bank = storage.ROOT/'banks'/protocol.FORMAL/identity/f'cut{cut:03d}'/'solo'
        bundles.append(reader.json(bank/'generation.json')); methods = {}
        for method in SOLO_METHODS:
            saved = reader.arrays(bank/'methods'/method/'arrays.npz')
            meta = reader.json(bank/'methods'/method/'generation.json')
            methods[method] = method_diagnostic(method, saved, meta, old_formal, old_generation, row['outcomes'], config['matching'])
            for repeat in range(4):
                path = storage.ROOT/'rollouts'/protocol.FORMAL/identity/f'cut{cut:03d}'/method/f'repeat_{repeat}/summary.json'
                branch_costs[method].append(reader.json(path))
        sources.append(dict(planned_slot_id=identity, resolved_episode_id=row['resolved_episode_id'],
            task=row['task'], actual_cut=cut, methods=methods))
    require(len(sources) == 98 and all(len(rows) == 392 for rows in branch_costs.values()), 'Full cut cost coverage required')
    wave = Path(gate['wave_path']); workers = [reader.json(wave/'workers'/f'worker_{i:02d}'/'status.json') for i in range(32)]
    launch = reader.json(wave/'launch_result.json')
    branches = {method:dict(branches=len(rows),
        branch_wall_including_restore_seconds=_cost(rows, 'wall_seconds'),
        branch_restore_seconds=_cost(rows, 'restore_seconds'),
        continuation_wall_excluding_restore_seconds=describe([r['wall_seconds']-r['restore_seconds'] for r in rows]),
        suffix_policy_calls=_cost(rows, 'policy_calls'), suffix_policy_seconds=_cost(rows, 'policy_seconds'),
        environment_seconds_including_restore_replay=_cost(rows, 'environment_seconds'))
        for method, rows in branch_costs.items()}
    reference = _preflight_reference_cost(config)
    return dict(schema='standalone_ablation_raw_q_cost_diagnostics_v1', status='complete_descriptive_diagnostics',
        sources=100, cut_sources=98, no_cut_sources=2, no_cut_q_and_perturbation_not_fabricated=True,
        method_summaries=aggregate_sources(sources), per_source=sources,
        cost=dict(formal_workers=32, gpus=8, workers_per_gpu=4,
            worker_model_loading_seconds=_cost(workers, 'loading_seconds'),
            worker_wall_seconds=_cost(workers, 'wall_seconds'),
            solo_bundle_restore_seconds=_cost(bundles, 'restore_seconds'),
            solo_bundle_generation_audit_and_persistence_seconds=_cost(bundles, 'candidate_generation_seconds'),
            old_joint_bank_restore_seconds=_cost(old_bundles, 'restore_seconds'),
            old_joint_generation_seconds_shared_fullbank=_cost(old_bundles, 'candidate_bank_seconds'),
            old_joint_wall_including_restore_seconds=_cost(old_bundles, 'generation_wall_seconds'),
            branch_costs=branches, reference_preflight_only=reference,
            whole_wave_seconds_including_lifecycle=launch['wall_seconds_including_lifecycle'],
            worker_sums_are_not_elapsed_wall_time=True, formal_entry_cost_includes_each_own_a0=True,
            component_and_parent_timers_overlap=True, realtime_hardware_claim=False),
        evidence=dict(formal_files_read=reader.used, preflight_files_read=reference['files_read']),
        code_sha256={str(Path(__file__).resolve()):storage.sha256(__file__)},
        model_calls=0, simulator_calls=0, optimizer_updates=0, q_gate_added=False, winner_selected=False,
        limitations=['Q correlations use the 98 cut-source means of four repeats and are descriptive, not a new acceptance rule or causal attribution.',
            'Old zero RMS has no finite new/old ratio; zero perturbations have no direction angle. Counts are reported instead of infinity or invented values.',
            'Angles compare actual raw perturbations. The historical bank did not save native V/D arrays; their all-source byte identity is not claimed.',
            'Standalone entry time includes its separately generated a0, diagnostic scoring and checks; no shared-a0 amortization is reported.',
            'Branch wall time includes restore; environment time also includes restored-prefix replay. These overlapping timers must not be added.',
            'Old fullbank and new standalone timing were observed in their respective concurrent waves; differences are not controlled hardware benchmarks.',
            'Preflight reference generation costs are separate and never added as ordinary standalone deployment requirements.',
            'All output is from the already revealed cohort structure ablation; no new independent heldout or method selection claim.'])
