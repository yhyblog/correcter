"""Post-completion supplement to the frozen five-arm development audit.

This file is deliberately independent of the collection/model implementations.
It never creates an environment, evaluates a model, reserves compute, or chooses
a policy. Only an already sealed, successful, complete 100-source audit unlocks
artifact reads. Its statistics are descriptive; the frozen primary audit owns
confidence intervals and comparison rules. Run --self-test for synthetic checks.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[2] / 'outputs/native10_training_20260916'
METHODS = ('continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post')
CORRECTIONS = METHODS[2:]
COMPARISONS = ((1, 0), (2, 1), (3, 1), (4, 1), (2, 0), (3, 0), (4, 0))
SCHEMA = 'native10_policy5_cost_diagnostic_v1'


def _hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text())


def _inside(path, parent):
    path, parent = Path(path).resolve(), Path(parent).resolve()
    if not path.is_relative_to(parent):
        raise ValueError('Input path escapes its declared root: '+str(path))
    return path


def _seal(folder, *, role=None, protocol=None):
    """Validate a small seal and all its files, including exact inventory."""
    folder = Path(folder).resolve()
    seal = _read(folder/'complete.json')
    if (seal.get('status') != 'complete' or role is not None and seal.get('role') != role
            or protocol is not None and seal.get('protocol_sha256') != protocol):
        raise ValueError('Missing or mismatched completed artifact seal: '+str(folder))
    files = seal.get('files')
    actual = {str(p.relative_to(folder)) for p in folder.rglob('*')
              if p.is_file() and p != folder/'complete.json'}
    if not isinstance(files, dict) or set(files) != actual:
        raise ValueError('Sealed inventory differs: '+str(folder))
    for name, expected in files.items():
        if _hash(_inside(folder/name, folder)) != expected:
            raise ValueError('Sealed file SHA differs: '+name)
    return seal


def validate_gate(config, result, bank_version):
    """No artifact access: reject partial results before loading any bank."""
    registration = config['main_collection']['banks'][bank_version]
    ids = registration['episode_ids']
    rows = result.get('per_source', [])
    if (registration.get('kind') != 'policy5'
            or registration.get('stage') != 'round1_development_policy'
            or len(ids) != 100 or len(set(ids)) != 100
            or result.get('status') != 'passed' or result.get('planned_slots') != 100
            or result.get('technical_missing') != 0
            or result.get('source_capture_attempts_added') != 0
            or result.get('new_attempts') != 1995
            or result.get('bank_version') != bank_version
            or result.get('stage') != registration['stage']
            or result.get('config_content_sha256') != _canonical(config)
            or result.get('selected_training') != config['policy_deployment']['selected_training']
            or len(rows) != 100 or [row.get('episode_id') for row in rows] != ids):
        raise ValueError('Require the matching complete 100-slot formal policy5 audit')
    values = []
    for row in rows:
        labels = row.get('paired_outcomes', {})
        if (type(row.get('no_cut')) is not bool or not row.get('task')
                or set(labels) != set(METHODS)
                or any(len(labels[name]) != 4 or any(type(v) is not bool for v in labels[name])
                       for name in METHODS)):
            raise ValueError('Audit requires five arms and four paired boolean outcomes per source')
        value = np.array([labels[name] for name in METHODS], dtype=bool)
        if row['no_cut'] and (row.get('actual_cut') is not None or not np.all(value == value.flat[0])):
            raise ValueError('No-cut common outcome must be broadcast to all five arms')
        if not row['no_cut'] and (type(row.get('actual_cut')) is not int or row['actual_cut'] < 0):
            raise ValueError('Cut source has no actual integer cut')
        if row.get('success_counts') != dict(zip(METHODS, value.sum(1).tolist())):
            raise ValueError('Audited success counts disagree with paired labels')
        values.append(value)
    if sum(row['no_cut'] for row in rows) != 5:
        raise ValueError('This frozen policy wave requires exactly 95 cut and 5 no-cut sources')
    attempts = result.get('attempt_numbers', [])
    if len(attempts) != 1995 or len(set(attempts)) != 1995 or any(type(n) is not int or n <= 0 for n in attempts):
        raise ValueError('Formal audit does not close the 1995 distinct stage attempts')
    return np.asarray(values, dtype=bool)


def describe(values):
    """Missing is never imputed to zero. Nonfinite costs are invalid."""
    supplied = list(values)
    array = np.array([v for v in supplied if v is not None], dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError('Nonfinite diagnostic input')
    result = dict(records=len(supplied), observed=len(array), missing=len(supplied)-len(array))
    if len(array):
        result.update(sum=float(array.sum()), mean=float(array.mean()), median=float(np.median(array)),
                      p90=float(np.quantile(array, .9)), minimum=float(array.min()), maximum=float(array.max()))
    return result


def _numeric(record, key):
    value = record.get(key)
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                              or not np.isfinite(value) or value < 0):
        raise ValueError('Invalid nonnegative cost: '+key)
    return value


def _radii(delta):
    delta = np.asarray(delta, dtype=np.float64)
    if not len(delta):
        return {k: None for k in ('xyz_rms', 'gripper_rms', 'xyz_linf', 'gripper_linf')}
    return dict(xyz_rms=float(np.sqrt(np.mean(delta[:, :3]**2))),
                gripper_rms=float(np.sqrt(np.mean(delta[:, 3:]**2))),
                xyz_linf=float(np.abs(delta[:, :3]).max()),
                gripper_linf=float(np.abs(delta[:, 3:]).max()))


def command_diagnostics(plans, matching):
    """Recompute final raw10 amplitudes, not native intermediate flow updates."""
    if set(plans) != set(METHODS[1:]):
        raise ValueError('Expected exactly the four intervention plans')
    for plan in plans.values():
        if plan.dtype != np.dtype('float32') or plan.shape != (50, 4) or not np.isfinite(plan).all():
            raise ValueError('Raw command plan must be finite float32 [50,4]')
    a0 = plans['alarm_replan10']
    clipped = np.clip(a0[:10], -1, 1)
    mask = 1 - np.abs(clipped) >= matching['boundary_clearance']
    rows, raw_groups, proxy_groups = {}, {}, {}
    tolerance = float(matching['tolerance'])
    for name in METHODS[1:]:
        raw = np.ascontiguousarray(plans[name][:10])
        proxy = np.ascontiguousarray(np.clip(raw, -1, 1))
        delta = raw.astype(np.float64) - a0[:10].astype(np.float64)
        raw_hash, proxy_hash = hashlib.sha256(raw.tobytes()).hexdigest(), hashlib.sha256(proxy.tobytes()).hexdigest()
        raw_groups.setdefault(raw_hash, []).append(name)
        proxy_groups.setdefault(proxy_hash, []).append(name)
        radii = _radii(delta)
        rows[name] = dict(raw10_sha256=raw_hash, clipped10_sha256=proxy_hash, actual_delta=radii,
            zero_xyz=not np.any(delta[:, :3]), zero_gripper=not np.any(delta[:, 3:]),
            raw_alias_of_a0=raw.tobytes() == a0[:10].tobytes(),
            raw_outside_unit_fraction=float(np.mean(np.abs(raw) > 1)),
            grip_outside_unit_fraction=float(np.mean(np.abs(raw[:, 3]) > 1)),
            raw_max_abs=float(np.abs(raw).max()), grip_max_abs=float(np.abs(raw[:, 3]).max()),
            raw_tail_bit_exact=plans[name][10:].tobytes() == a0[10:].tobytes(),
            outside_mask_bit_exact=raw[~mask].tobytes() == a0[:10][~mask].tobytes(),
            raw_delta_equals_critic_delta=bool(np.allclose(delta, proxy.astype(np.float64)-clipped,
                                                         atol=tolerance, rtol=0)),
            caps_within_frozen_tolerance=all(radii[key] <= matching[key]+tolerance for key in radii))
    spreads = {channel: max(rows[name]['actual_delta'][channel+'_rms'] for name in CORRECTIONS)
                       - min(rows[name]['actual_delta'][channel+'_rms'] for name in CORRECTIONS)
               for channel in ('xyz', 'gripper')}
    return dict(methods=rows, mask_fraction=float(np.mean(~mask)), raw_alias_groups=list(raw_groups.values()),
        clipped_proxy_groups=list(proxy_groups.values()), raw_unique_groups=len(raw_groups),
        clipped_unique_groups=len(proxy_groups), clipped_collision_of_distinct_raw=len(raw_groups)>len(proxy_groups),
        correction_rms_spread=spreads,
        correction_rms_matched=all(value <= tolerance for value in spreads.values()),
        tolerance=tolerance, amplitude_scope='final first ten raw commands; intermediate flow queries are not bounded by this')


def paired_summary(values):
    values = np.asarray(values, dtype=np.int8)
    if values.ndim != 3 or values.shape[1:] != (5, 4) or not np.isin(values, [0, 1]).all():
        raise ValueError('Expected source x five-arm x four-repeat binary outcomes')
    if not len(values):
        return dict(sources=0, logical_pairs_per_comparison=0)
    comparisons = {}
    for candidate, baseline in COMPARISONS:
        c, b = values[:, candidate], values[:, baseline]
        delta = (c-b).mean(1)
        comparisons[METHODS[candidate]+'_minus_'+METHODS[baseline]] = dict(
            mean_gain=float(delta.mean()), gain_pp=float(100*delta.mean()),
            rescues=int(((c == 1) & (b == 0)).sum()), harms=int(((c == 0) & (b == 1)).sum()),
            positive_sources=int((delta > 0).sum()), negative_sources=int((delta < 0).sum()),
            zero_sources=int((delta == 0).sum()))
    return dict(sources=len(values), logical_pairs_per_comparison=4*len(values),
        success_counts=dict(zip(METHODS, values.sum((0, 2)).tolist())),
        success_rates=dict(zip(METHODS, values.mean((0, 2)).tolist())), comparisons=comparisons)


def _ranks(values):
    array = np.asarray(values)
    return np.array([np.count_nonzero(array < v) + (np.count_nonzero(array == v)-1)/2 for v in array])


def association(predicted, observed):
    p, o = np.asarray(predicted, float), np.asarray(observed, float)
    if p.shape != o.shape or p.ndim != 1 or not np.isfinite(p).all() or not np.isfinite(o).all():
        raise ValueError('Q and source-mean gain must be paired finite vectors')
    def correlation(a, b):
        return float(np.corrcoef(a, b)[0, 1]) if len(a)>1 and np.ptp(a)>0 and np.ptp(b)>0 else None
    return dict(sources=len(p), predicted_gain=describe(p), actual_gain=describe(o),
        pearson=correlation(p, o), spearman=correlation(_ranks(p), _ranks(o)),
        sign_table={ps+'_'+os: int(((np.sign(p) == pv) & (np.sign(o) == ov)).sum())
                    for ps, pv in (('q_negative', -1), ('q_zero', 0), ('q_positive', 1))
                    for os, ov in (('actual_negative', -1), ('actual_zero', 0), ('actual_positive', 1))})


def _npz(path):
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key].copy() for key in archive.files}


def run(config_path, audit_path, *, freeze_path=None, root=ROOT):
    """Return diagnostics only after the primary sealed all-100 audit gate."""
    root, config_path, audit_path = Path(root).resolve(), Path(config_path).resolve(), Path(audit_path).resolve()
    freeze_path = Path(freeze_path).resolve() if freeze_path else config_path.parent/'freeze.json'
    _seal(audit_path, role='native10_policy5_readonly_audit')
    config, result, freeze = _read(config_path), _read(audit_path/'result.json'), _read(freeze_path)
    digest = _hash(config_path)
    if freeze.get('config_sha256') != digest or freeze.get('files', {}).get(str(config_path)) != digest:
        raise ValueError('Frozen config SHA is not bound in its freeze inventory')
    bank_version = result['bank_version']
    values = validate_gate(config, result, bank_version)  # Must precede bank/branch/source reads.
    protocol, stage = config['analysis_approval']['protocol_sha256'], result['stage']
    registration = config['main_collection']['banks'][bank_version]
    manifest = {row['episode_id']: row for row in config['episode_manifest']}
    artifact_map = {}
    for row in result.get('artifacts', []):
        path = _inside(row['path'], root)
        if str(path) in artifact_map:
            raise ValueError('Primary audit repeats an artifact identity')
        artifact_map[str(path)] = row['sha256']
    used = {str(config_path): digest, str(freeze_path): _hash(freeze_path),
            str(audit_path/'result.json'): _hash(audit_path/'result.json'),
            str(audit_path/'complete.json'): _hash(audit_path/'complete.json'),
            str(Path(__file__).resolve()): _hash(__file__)}

    def bound(path, *, arrays=False):
        path = _inside(path, root)
        expected = artifact_map.get(str(path))
        if not expected or _hash(path) != expected:
            raise ValueError('Input absent from primary audit or changed since that audit: '+str(path))
        used[str(path)] = expected
        return _npz(path) if arrays else _read(path)

    sources, generations, branches, commands, gradients = [], [], [], [], []
    for i, audit_row in enumerate(result['per_source']):
        episode = audit_row['episode_id']; case = manifest[episode]
        if case['task'] != audit_row['task'] or case.get('split') != 'development':
            raise ValueError('Audited source is not the registered development identity')
        source = dict(episode_id=episode, task=case['task'], no_cut=audit_row['no_cut'],
            actual_cut=audit_row['actual_cut'], logical_outcomes_per_arm=4,
            success_counts=audit_row['success_counts'], common_outcome_broadcast=audit_row['no_cut'])
        if source['no_cut']:
            source.update(command_diagnostic=None, q=None, physical_branches=0)
            sources.append(source)
            continue
        cut = source['actual_cut']; base = root/'banks'/bank_version/case['case_id']/f'cut{cut:03d}'
        bank_seal = bound(base/'complete.json')
        generation, plans = bound(base/'generation.json'), bound(base/'plans.npz', arrays=True)
        identity = dict(episode_id=episode, cut_step=cut, bank_version=bank_version,
                        stage=stage, protocol_sha256=protocol, model_hashes=registration['model_hashes'])
        if (bank_seal.get('status') != 'complete' or bank_seal.get('protocol_sha256') != protocol
                or any(generation.get(k) != v for k, v in identity.items())):
            raise ValueError('Generation provenance disagrees with primary audit configuration')
        guard_folder = root/'policy_guard'/stage/bank_version/episode
        _seal(guard_folder, role='policy_deployment_bank_check', protocol=protocol)
        guard = _read(guard_folder/'bank_check.json')
        for name in ('complete.json', 'bank_check.json'):
            used[str(guard_folder/name)] = _hash(guard_folder/name)
        if (guard.get('status') != 'passed' or guard.get('episode_id') != episode
                or guard.get('bank_seal_sha256') != used[str(base/'complete.json')]
                or guard.get('source_seal_sha256') != generation.get('source_seal_sha256')
                or guard.get('checked_before_branch') is not True):
            raise ValueError('Before-branch guard does not bind the audited bank')
        diagnostic = command_diagnostics(plans, config['matching'])
        predictions = generation.get('bank_predictions', {})
        if set(predictions) != set(METHODS[1:]):
            raise ValueError('Final command bank predictions are missing')
        q = {}
        for name in METHODS[1:]:
            prediction = predictions[name]
            gain = float(prediction['mean_gain'])
            probability = float(prediction['candidate_mean_probability'])
            anchor_probability = float(prediction['a0_mean_probability'])
            if not np.isfinite([gain, probability, anchor_probability]).all() or not (0<=probability<=1 and 0<=anchor_probability<=1):
                raise ValueError('Nonfinite or invalid saved final-bank Q')
            if name == 'alarm_replan10' and gain != 0:
                raise ValueError('Fixed slot-zero anchor score must be exactly zero')
            actual_gain = float((values[i, METHODS.index(name)].astype(int)-values[i, 1].astype(int)).mean())
            q[name] = dict(predicted_gain=gain, candidate_probability=probability,
                           a0_probability=anchor_probability, actual_source_gain=actual_gain)
            commands.append(dict(episode_id=episode, task=case['task'], method=name,
                **diagnostic['methods'][name]['actual_delta'],
                raw_alias_of_a0=diagnostic['methods'][name]['raw_alias_of_a0'],
                predicted_gain=gain, actual_source_gain=actual_gain))
        generation_cost = dict(episode_id=episode, task=case['task'])
        for key in ('generation_wall_seconds', 'restore_seconds', 'candidate_bank_seconds'):
            generation_cost[key] = _numeric(generation, key)
        components = {'base': generation.get('base_generation', {}),
                      **generation.get('guidance', {}), 'post': generation.get('post_gradient', {}),
                      'objective': generation.get('objective_stats', {})}
        for name, record in components.items():
            for key in ('seconds', 'policy_calls', 'objective_forward_calls', 'backward_calls',
                        'critic_member_forward_calls', 'critic_member_backward_calls', 'critic_forward_seconds',
                        'peak_cuda_allocated_mib', 'peak_cuda_reserved_mib', 'incremental_peak_cuda_allocated_mib'):
                generation_cost[name+'_'+key] = _numeric(record, key)
        generation_cost['fallbacks'] = {name: record.get('fallback') for name, record in components.items() if name in ('base','velocity','direct')}
        generations.append(generation_cost)
        for name in ('velocity', 'direct'):
            gradients.append(dict(episode_id=episode, method=name,
                                  updates=generation.get('guidance', {}).get(name, {}).get('updates', [])))
        source.update(command_diagnostic=diagnostic, q=q, physical_branches=20,
            matching_groups=generation.get('matching', {}).get('groups'), generation_cost=generation_cost,
            post_gradient=generation.get('post_gradient'), guard_matched_rms=guard.get('matched_rms'))
        for method in METHODS:
            for repeat in range(4):
                folder = root/'rollouts'/stage/bank_version/case['case_id']/f'cut{cut:03d}'/method/f'repeat_{repeat}'
                row = bound(folder/'summary.json')
                bound(folder/'complete.json')
                if (any(row.get(k) != v for k, v in identity.items()) or row.get('method') != method
                        or row.get('repeat') != repeat or row.get('status') != 'complete'
                        or row.get('candidate_bank_sha256') != used[str(base/'complete.json')]
                        or row.get('success') is not bool(values[i, METHODS.index(method), repeat])):
                    raise ValueError('Branch metadata differs from the complete audit')
                cost = dict(episode_id=episode, task=case['task'], method=method, repeat=repeat)
                for key in ('restore_seconds','policy_calls','policy_seconds','environment_seconds','wall_seconds',
                            'requested_prefix_steps','actual_prefix_steps','terminal_step'):
                    cost[key] = _numeric(row, key)
                n = row.get('actual_prefix_steps')
                if type(n) is not int or not 0 <= n <= (5 if method == METHODS[0] else 10):
                    raise ValueError('Branch actual prefix count is invalid')
                cost['executed_prefix_delta'] = None
                if method != METHODS[0]:
                    if row.get('command_sha256') != diagnostic['methods'][method]['raw10_sha256']:
                        raise ValueError('Final raw10 command SHA differs from audited branch command')
                    cost['executed_prefix_delta'] = _radii(plans[method][:n].astype(float)-plans[METHODS[1]][:n].astype(float))
                branches.append(cost)
        sources.append(source)

    task_names = sorted({row['task'] for row in sources})
    cut_mask = np.array([not row['no_cut'] for row in sources])
    stats = dict(overall=paired_summary(values), alarm_conditioned=paired_summary(values[cut_mask]),
        no_cut_common_outcomes=paired_summary(values[~cut_mask]),
        per_task={task: dict(full_denominator=paired_summary(values[[r['task']==task for r in sources]]),
            alarm_conditioned=paired_summary(values[[r['task']==task and not r['no_cut'] for r in sources]])) for task in task_names})
    # Cross-check the means/counts with the primary result; do not create new CIs.
    primary = result['statistics']
    if stats['overall']['success_counts'] != primary['overall']['success_counts']:
        raise ValueError('Supplement count disagrees with the primary audit')
    for name, row in stats['overall']['comparisons'].items():
        original = primary['comparisons'][name]
        if abs(row['mean_gain']-original['gain']) > 1e-12 or any(row[k] != original[k] for k in ('rescues','harms','positive_sources','negative_sources','zero_sources')):
            raise ValueError('Supplement comparison disagrees with primary audit')
    cut_sources = [row for row in sources if not row['no_cut']]
    q_vs_actual = {}
    for name in CORRECTIONS:
        def group(rows):
            return association([row['q'][name]['predicted_gain'] for row in rows],
                               [row['q'][name]['actual_source_gain'] for row in rows])
        q_vs_actual[name] = dict(all_cut_sources=group(cut_sources),
            nonalias_to_a0=group([row for row in cut_sources if not row['command_diagnostic']['methods'][name]['raw_alias_of_a0']]),
            per_task={task: group([row for row in cut_sources if row['task']==task]) for task in task_names})
    generation_keys = sorted({key for row in generations for key in row if key not in ('episode_id','task','fallbacks')})
    branch_keys = ('restore_seconds','policy_calls','policy_seconds','environment_seconds','wall_seconds','actual_prefix_steps','terminal_step')
    cost_summary = dict(generation={key: describe(row.get(key) for row in generations) for key in generation_keys},
        branches_by_method={name: {key: describe(row.get(key) for row in branches if row['method']==name)
                                  for key in branch_keys} for name in METHODS},
        guidance_fallback_counts={name: dict(Counter(str(row['fallbacks'].get(name)) for row in generations))
                                  for name in ('base','velocity','direct')},
        partial_prefix_branches_by_method={name: sum(row['actual_prefix_steps'] < row['requested_prefix_steps']
                                                   for row in branches if row['method']==name) for name in METHODS},
        interpretation='Timing components overlap. Sums are cumulative worker seconds, not wave elapsed time; GPU peaks are descriptive, not additive. Original source capture is reused and excluded.')
    amplitude = {name: {key: describe(row[key] for row in commands if row['method']==name)
                        for key in ('xyz_rms','gripper_rms','xyz_linf','gripper_linf')} for name in METHODS[1:]}
    quality = dict(raw_unique_group_distribution=dict(Counter(row['command_diagnostic']['raw_unique_groups'] for row in cut_sources)),
        clipped_collision_sources=sum(row['command_diagnostic']['clipped_collision_of_distinct_raw'] for row in cut_sources),
        unmatched_final_rms_sources=sum(not row['command_diagnostic']['correction_rms_matched'] for row in cut_sources),
        zero_channel_counts={name: {channel: sum(row['command_diagnostic']['methods'][name]['zero_'+channel] for row in cut_sources)
                                   for channel in ('xyz','gripper')} for name in CORRECTIONS},
        aliases_of_a0={name: sum(row['command_diagnostic']['methods'][name]['raw_alias_of_a0'] for row in cut_sources) for name in CORRECTIONS},
        matching_group_flags={group: {flag: sum((row.get('matching_groups') or {}).get(group, {}).get(flag) is True for row in cut_sources)
                                     for flag in ('zero_group','shrunk')} for group in ('xyz','gripper')})
    return dict(schema=SCHEMA, status='complete', descriptive_only=True, new_scientific_acceptance_rules=False,
        simulator_attempts=0, optimizer_updates=0, model_calls=0, independent_validation_success=False,
        stage=stage, bank_version=bank_version, source_denominator=100, command_q_denominator=95,
        logical_outcomes_per_arm=400, physical_branches=len(branches),
        config_sha256=digest, config_content_sha256=_canonical(config), protocol_sha256=protocol,
        selected_training=result['selected_training'], primary_statistics=primary, statistics=stats,
        cost=cost_summary, final_raw_amplitude=amplitude, quality=quality, q_vs_actual=q_vs_actual,
        per_source=sources, command_rows=commands, branch_cost_rows=branches, flow_updates=gradients,
        inputs=[dict(path=path, sha256=sha) for path, sha in sorted(used.items())],
        limitations=[
            'Only the new five arms are paired here. No historical sixth arm or old/new suffix equivalence is inferred.',
            'Four repeats remain dependent measurements within each source; no-cut sources retain their common outcome.',
            'Q is scored on C(raw)=clip(raw), while the raw plan is executed. Commands with equal proxy may differ physically.',
            'Final ten-command amplitude does not bound intermediate flow queries. Matching can expand native directions.',
            'Actual prefix amplitude uses each branch executed prefix length; it does not assert identical termination times.',
            'Q association is descriptive on generated candidates and development sources; it proves neither calibration nor causal score quality.',
            'No new bootstrap, winner, acceptance threshold, retraining rule, or independent-validation claim is introduced.',
            'Primary audit performed full trajectory/seed/physics verification; this supplement rehashes only consumed artifacts.',
        ])


def write_outputs(result, output, *, root=ROOT):
    output = _inside(output, Path(root)/'policy5_cost_diagnostics')
    output.mkdir(parents=True, exist_ok=False)
    def dump(name, value):
        with (output/name).open('x') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    dump('result.json', result)
    for name, rows in (('commands.csv', result['command_rows']), ('branch_costs.csv', result['branch_cost_rows'])):
        columns = sorted({key for row in rows for key in row})
        with (output/name).open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader()
            writer.writerows({key: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v for key, v in row.items()} for row in rows)
    text = ['# Policy5 完整开发集补充诊断', '',
        f"固定 {result['source_denominator']} 源、每臂 {result['logical_outcomes_per_arm']} 个配对结局；",
        f"其中 {result['command_q_denominator']} 源有干预命令，{result['physical_branches']} 个真实分支。无 cut 共同结局保留在分母。", '',
        '这是完整主审计之后的描述性补充。原主审计的 CI 与比较规则原样保存在 result.json 的 primary_statistics；本模块不新增接受标准。', '',
        '| 比较 | 平均增益 pp | 救回 | 损害 | 正/负/零源 |', '|---|---:|---:|---:|---:|']
    for name, row in result['statistics']['overall']['comparisons'].items():
        text.append(f"| {name} | {row['gain_pp']:.2f} | {row['rescues']} | {row['harms']} | {row['positive_sources']}/{row['negative_sources']}/{row['zero_sources']} |")
    text += ['', '逐任务完整/报警条件比较见 statistics.per_task；成本见 cost；最终 raw 幅度见 final_raw_amplitude；别名/零组见 quality；Q 与真实源均值增益关系见 q_vs_actual。', '',
        '成本分量可能重叠，累加 worker 秒不等于波次 elapsed。显存峰值不能相加。未记录的字段保留缺失。', '',
        '最终局部 raw 幅度不限制 flow 中间查询；同幅投影可以放大原生方向，不能将 matched 当作原生 QGF。只比较当前五臂内部配对，不构造旧数据第六臂。', '',
        '开发集结果与 Q 相关性都不能称为独立验证成功。完整输入 SHA、逐源记录和限制见 result.json。', '']
    with (output/'report.md').open('x') as stream:
        stream.write('\n'.join(text))
    dump('complete.json', dict(status='complete', role=SCHEMA, simulator_attempts=0, optimizer_updates=0,
         files={path.name: _hash(path) for path in sorted(output.iterdir()) if path.is_file()}))


def self_test():
    """Pure CPU, in-memory/temp synthetic inputs; never opens ROOT artifacts."""
    class Checks(unittest.TestCase):
        def setUp(self):
            self.matching = dict(boundary_clearance=.05, tolerance=1e-6, xyz_rms=.05, gripper_rms=.1, xyz_linf=.15, gripper_linf=.4)
            self.plans = {name: np.zeros((50, 4), np.float32) for name in METHODS[1:]}
            self.ids = [f'task__{i}' for i in range(100)]
            self.config = dict(main_collection=dict(banks=dict(v=dict(kind='policy5', stage='round1_development_policy', episode_ids=self.ids))), policy_deployment=dict(selected_training={}))
            self.result = dict(status='passed', planned_slots=100, technical_missing=0, source_capture_attempts_added=0,
                new_attempts=1995, bank_version='v', stage='round1_development_policy', config_content_sha256=_canonical(self.config), selected_training={},
                attempt_numbers=list(range(1,1996)), per_source=[dict(episode_id=identity,task='task',no_cut=i>=95,actual_cut=None if i>=95 else 5,
                    paired_outcomes={name:[False]*4 for name in METHODS},success_counts={name:0 for name in METHODS}) for i,identity in enumerate(self.ids)])

        def test_complete_gate(self):
            self.assertEqual(validate_gate(self.config,self.result,'v').shape,(100,5,4))
        def test_partial_gate(self):
            self.result['per_source'].pop()
            with self.assertRaises(ValueError): validate_gate(self.config,self.result,'v')
        def test_no_cut_common(self):
            self.result['per_source'][-1]['paired_outcomes']['post'][0]=True
            with self.assertRaises(ValueError): validate_gate(self.config,self.result,'v')
        def test_config_and_attempt_identity(self):
            self.result['attempt_numbers'][-1]=1
            with self.assertRaises(ValueError): validate_gate(self.config,self.result,'v')
        def test_repeat_not_source(self):
            x=np.zeros((2,5,4),np.int8);x[0,2,:]=1
            s=paired_summary(x)['comparisons']['velocity_minus_alarm_replan10']
            self.assertEqual((s['mean_gain'],s['rescues'],s['positive_sources']),(.5,4,1))
        def test_raw_alias(self):
            d=command_diagnostics(self.plans,self.matching)
            self.assertEqual(d['raw_unique_groups'],1)
            self.assertTrue(d['methods']['post']['raw_alias_of_a0'])
        def test_raw_vs_clipped_collision(self):
            self.plans['velocity'][0,3]=2; self.plans['post'][0,3]=3
            d=command_diagnostics(self.plans,self.matching)
            self.assertTrue(d['clipped_collision_of_distinct_raw'])
            self.assertEqual(d['raw_unique_groups'],3)
        def test_unchanged_saturated_raw(self):
            for plan in self.plans.values(): plan[0,3]=2
            self.plans['post'][1,0]=.01
            d=command_diagnostics(self.plans,self.matching)
            self.assertTrue(d['methods']['post']['outside_mask_bit_exact'])
            self.assertEqual(d['methods']['post']['grip_outside_unit_fraction'],.1)
        def test_final_amplitude_not_recorded(self):
            self.plans['post'][:10,0]=.03
            d=command_diagnostics(self.plans,self.matching)
            self.assertAlmostEqual(d['methods']['post']['actual_delta']['xyz_rms'],.03/np.sqrt(3),places=8)
            self.assertFalse(d['correction_rms_matched'])
        def test_missing_not_zero(self):
            d=describe([None,2]);self.assertEqual((d['missing'],d['mean']),(1,2))
        def test_undefined_correlation(self):
            self.assertIsNone(association([0,0],[0,1])['pearson'])
            self.assertEqual(association([],[])['sources'],0)
        def test_rank_ties(self):
            self.assertTrue(np.array_equal(_ranks([2,1,1]),[2,.5,.5]))
        def test_q_sign_information(self):
            d=association([1,-1,0],[.25,-.25,0]);self.assertEqual(d['pearson'],1)
            self.assertEqual(d['sign_table']['q_positive_actual_positive'],1)
        def test_seal_rejects_changed_content(self):
            with tempfile.TemporaryDirectory() as directory:
                p=Path(directory);(p/'x').write_text('a')
                (p/'complete.json').write_text(json.dumps(dict(status='complete',files={'x':_hash(p/'x')})))
                _seal(p);(p/'x').write_text('b')
                with self.assertRaises(ValueError): _seal(p)
        def test_seal_rejects_escape(self):
            with tempfile.TemporaryDirectory() as directory:
                p=Path(directory);q=p/'sub';q.mkdir();(p/'outside').write_text('a')
                (q/'x').symlink_to(p/'outside')
                (q/'complete.json').write_text(json.dumps(dict(status='complete',files={'x':_hash(q/'x')})))
                with self.assertRaises(ValueError): _seal(q)
        def test_no_execution_prefix(self):
            self.assertTrue(all(v is None for v in _radii(np.zeros((0,4))).values()))
        def test_end_to_end_temporary_fixtures(self):
            # Entirely synthetic 100-source provenance tree. No workspace data.
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory); protocol='1'*64; artifacts=[]
                def dump(path,value):
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_text(json.dumps(value))
                def sealed(folder,role=None,track=False):
                    record=dict(status='complete',files={str(p.relative_to(folder)):_hash(p)
                        for p in folder.rglob('*') if p.is_file()})
                    if role: record['role']=role
                    record['protocol_sha256']=protocol
                    dump(folder/'complete.json',record)
                    if track:
                        artifacts.extend(dict(path=str(p),sha256=_hash(p)) for p in folder.iterdir() if p.is_file())
                config=self.config
                config.update(analysis_approval=dict(protocol_sha256=protocol),matching=self.matching,
                    episode_manifest=[dict(episode_id=identity,case_id=identity,task='task',split='development') for identity in self.ids])
                config['main_collection']['banks']['v']['model_hashes']={'critic_0':'2'*64}
                config_path=root/'protocol/config.json';dump(config_path,config)
                dump(root/'protocol/freeze.json',dict(config_sha256=_hash(config_path),files={str(config_path):_hash(config_path)}))
                result=self.result;result['config_content_sha256']=_canonical(config)
                stats=paired_summary(np.zeros((100,5,4),bool))
                result['statistics']=dict(overall=dict(success_counts=stats['success_counts']),comparisons={})
                for name,row in stats['comparisons'].items():
                    result['statistics']['comparisons'][name]=dict(row,gain=row['mean_gain'],source_95ci=[0,0])
                for episode in self.ids[:95]:
                    stage='round1_development_policy';base=root/'banks/v'/episode/'cut005'
                    base.mkdir(parents=True)
                    np.savez(base/'plans.npz',**self.plans)
                    identity=dict(episode_id=episode,cut_step=5,bank_version='v',stage=stage,
                        protocol_sha256=protocol,model_hashes={'critic_0':'2'*64})
                    generation=dict(identity,source_seal_sha256='3'*64,
                        bank_predictions={name:dict(mean_gain=0,candidate_mean_probability=.5,a0_mean_probability=.5)
                                          for name in METHODS[1:]})
                    dump(base/'generation.json',generation);sealed(base,track=True)
                    guard=root/'policy_guard'/stage/'v'/episode
                    dump(guard/'bank_check.json',dict(status='passed',episode_id=episode,
                        bank_seal_sha256=_hash(base/'complete.json'),source_seal_sha256='3'*64,checked_before_branch=True))
                    sealed(guard,'policy_deployment_bank_check')
                    for method in METHODS:
                        for repeat in range(4):
                            folder=root/'rollouts'/stage/'v'/episode/'cut005'/method/f'repeat_{repeat}'
                            row=dict(identity,method=method,repeat=repeat,status='complete',success=False,
                                candidate_bank_sha256=_hash(base/'complete.json'),
                                command_sha256=hashlib.sha256(self.plans[METHODS[1]][:10].tobytes()).hexdigest(),
                                actual_prefix_steps=5 if method==METHODS[0] else 10,
                                requested_prefix_steps=5 if method==METHODS[0] else 10,wall_seconds=2)
                            dump(folder/'summary.json',row);sealed(folder,track=True)
                result['artifacts']=artifacts
                audit=root/'audit';dump(audit/'result.json',result);sealed(audit,'native10_policy5_readonly_audit')
                supplement=run(config_path,audit,root=root)
                self.assertEqual((supplement['source_denominator'],supplement['physical_branches']),(100,1900))
                self.assertEqual(supplement['cost']['branches_by_method']['post']['wall_seconds']['sum'],760)
                self.assertEqual(supplement['quality']['aliases_of_a0']['post'],95)
                output=root/'policy5_cost_diagnostics/synthetic'
                write_outputs(supplement,output,root=root);_seal(output,role=SCHEMA)
                with self.assertRaises(FileExistsError): write_outputs(supplement,output,root=root)
                changed=root/'banks/v'/self.ids[0]/'cut005/generation.json'
                changed.write_text('{}')
                with self.assertRaises(ValueError): run(config_path,audit,root=root)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--audit', type=Path, help='Existing sealed policy5 audit directory; all 100 sources required')
    parser.add_argument('--freeze', type=Path, help='Defaults to config directory/freeze.json')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, help='New directory under ROOT/policy5_cost_diagnostics')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        if any((args.config,args.audit,args.freeze,args.output)):
            parser.error('--self-test cannot open experiment inputs or outputs')
        self_test(); return
    if not all((args.config,args.audit,args.output)):
        parser.error('--config, --audit and --output are required')
    if args.output.exists():
        raise FileExistsError('Supplement output must be a new directory')
    result = run(args.config,args.audit,freeze_path=args.freeze,root=args.root)
    write_outputs(result,args.output,root=args.root)
    print(json.dumps(dict(status=result['status'],sources=result['source_denominator'],
        physical_branches=result['physical_branches'],output=str(args.output),descriptive_only=True)))


if __name__ == '__main__':
    main()
