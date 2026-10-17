"""Completed-heldout independent reaggregation using only stdlib and NumPy.

Import/AST inspection performs no artifact reads.  main() requires successful
whole-wave exit, all 32 sealed workers, all 100 completed logical slots and a
complete primary audit BEFORE reading any source or branch outcome.  This does
not call the production reducer or select a policy, and never starts compute.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CONFIG = ROOT/'heldout_protocols/heldout_v1/config.json'
FREEZE = CONFIG.with_name('freeze.json')
CONFIG_SHA = 'd86dc14afddf81a37587ff020cd36cc07e85869bf315502dc1778a97bda8f795'
FREEZE_SHA = 'a2db97fd0c76650e730b58836b0cd6059d25c76f42e5da4e2ce06611784d11b8'
WAVE = ROOT/'heldout_execution/heldout/heldout_policy_v1/heldout_v1_01'
PRIMARY = ROOT/'heldout_audits/heldout_v1'
STAGE, BANK = 'heldout', 'heldout_policy_v1'
METHODS = ('continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post')
TASKS = ('disassemble-v3', 'pick-place-wall-v3', 'shelf-place-v3', 'stick-pull-v3', 'stick-push-v3')
PAIRS = ((1, 0), (2, 1), (3, 1), (4, 1), (2, 0), (3, 0), (4, 0))
PRIMARY_COMPARISON = 'post_minus_alarm_replan10'
REPEATS = 4
INPUTS = {}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(2**20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read(path, expected=None):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Artifact outside the isolated workflow: '+str(path))
    digest = sha(path)
    if expected is not None and digest != expected:
        raise ValueError('Input SHA mismatch: '+str(path))
    if str(path) in INPUTS and INPUTS[str(path)] != digest:
        raise ValueError('Input changed during aggregation: '+str(path))
    INPUTS[str(path)] = digest
    return json.loads(path.read_text())


def sealed_json(folder, name, expected_seal=None, *, role=None, protocol=None):
    folder = Path(folder).resolve(); path = (folder/name).resolve()
    if not path.is_relative_to(folder):
        raise ValueError('Artifact member escapes its sealed directory')
    complete = read(folder/'complete.json', expected_seal)
    if (complete.get('status') != 'complete' or role is not None and complete.get('role') != role
            or protocol is not None and complete.get('protocol_sha256') != protocol):
        raise ValueError('Matching complete artifact seal required')
    return read(path, complete['files'][name])


def completed_gate():
    """Only completion/disposition metadata is read in this function."""
    cfg, frozen = read(CONFIG, CONFIG_SHA), read(FREEZE, FREEZE_SHA)
    if frozen.get('config_sha256') != CONFIG_SHA or frozen['files'].get(str(CONFIG)) != CONFIG_SHA:
        raise ValueError('Frozen configuration identity differs')
    registration = cfg['main_collection']['banks'][BANK]; ids = registration['episode_ids']
    expected = [f'{TASKS[i % 5]}__{start+i}' for start in (2026111750, 2026111850) for i in range(50)]
    lookup = {row['episode_id']: row for row in cfg['episode_manifest']}
    if (ids != expected or registration['stage'] != STAGE
            or cfg['split_replicates']['heldout'] != REPEATS
            or Counter(lookup[key]['task'] for key in ids) != Counter({task: 20 for task in TASKS})):
        raise ValueError('Original heldout source identity/order/repeats differ')
    launch, spec = read(WAVE/'launch_result.json'), read(WAVE/'wave_spec.json')
    if (launch.get('status') != 'complete' or type(launch.get('returncode')) is not int
            or launch['returncode'] != 0 or launch.get('lifecycle_covers_entire_wave') is not True
            or launch.get('hold_idle') is not False or launch.get('next_stage_automatically_started') is not False
            or spec.get('config_sha256') != CONFIG_SHA or spec.get('freeze_sha256') != FREEZE_SHA
            or spec.get('stage') != STAGE or spec.get('bank_version') != BANK
            or spec.get('workers') != 32 or spec.get('original_primary_slots') != 100
            or spec.get('paired_suffixes_per_state') != REPEATS
            or spec.get('physical_arms') != list(METHODS)
            or spec.get('fixed_main_injection') != 'post'
            or spec.get('primary_policy_fixed_before_heldout') is not True
            or spec.get('selection_after_heldout_allowed') is not False
            or spec.get('final_selection') != cfg['heldout_collection']['final_selection']):
        raise ValueError('Complete successful frozen heldout wave required before outcome access')
    primary_seal = read(PRIMARY/'complete.json')
    if (primary_seal.get('status') != 'complete'
            or primary_seal.get('role') != 'native10_heldout_readonly_audit'
            or not isinstance(primary_seal.get('files', {}).get('result.json'), str)):
        raise ValueError('Complete primary audit required before independent label access')
    folders = [WAVE/'workers'/f'worker_{rank:02d}' for rank in range(32)]
    if not all((folder/'complete.json').is_file() for folder in folders):
        raise ValueError('All 32 workers must finish before outcome access')
    protocol = cfg['analysis_approval']['protocol_sha256']; slots = {}
    for rank, folder in enumerate(folders):
        status = sealed_json(folder, 'status.json', role='guarded_heldout_worker', protocol=protocol)
        if (status.get('status') != 'complete' or status.get('assigned_slot_ids') != ids[rank::32]
                or status.get('missing_slot_ids') != [] or status.get('workers') != 32
                or status.get('rank') != rank or status.get('stage') != STAGE
                or status.get('bank_version') != BANK or status.get('config_sha256') != CONFIG_SHA
                or status.get('freeze_sha256') != FREEZE_SHA
                or status.get('completed_slot_records') != len(ids[rank::32])
                or status.get('selection_after_heldout_allowed') is not False
                or (folder/'failure.json').exists()):
            raise ValueError('Incomplete worker or changed frozen source assignment')
        for identity in ids[rank::32]:
            row = sealed_json(folder, f'slots/{identity}.json', protocol=protocol)
            chain = [identity]+cfg['main_collection']['replacement_candidates'][identity]
            actual = row.get('resolved_episode_id')
            if (row.get('status') != 'complete' or row.get('planned_slot_id') != identity
                    or actual not in chain or identity in slots
                    or [x['episode_id'] for x in row.get('ordered_rejections', [])] != chain[:chain.index(actual)]
                    or any(x.get('reason') not in ('initialization_failed', 'duplicate_initial_scene')
                           or x.get('before_first_action') is not True for x in row['ordered_rejections'])):
                raise ValueError('Unresolved logical source or invalid pre-action replacement chain')
            collection = ROOT/'collections'/STAGE/BANK/actual
            if Path(row['completion_path']).resolve() != collection or not (collection/'complete.json').is_file():
                raise ValueError('Every primary slot needs its completed collection')
            slots[identity] = row
    if len(slots) != 100 or len({row['resolved_episode_id'] for row in slots.values()}) != 100:
        raise ValueError('Missing/repeated sources cannot be imputed as zero differences')
    return cfg, ids, lookup, slots, INPUTS[str(PRIMARY/'complete.json')]


def collect_labels(cfg, ids, lookup, slots):
    """Only called after completed_gate; trajectories remain the primary audit's responsibility."""
    labels, rows = [], []; protocol = cfg['analysis_approval']['protocol_sha256']
    for identity in ids:
        slot = slots[identity]; actual = slot['resolved_episode_id']; case = lookup[actual]
        if case['split'] != STAGE or case['task'] != lookup[identity]['task']:
            raise ValueError('Cross-split/task actual source')
        collection = Path(slot['completion_path'])
        record = sealed_json(collection, 'summary.json', slot['completion_sha256'], protocol=protocol)
        if (record.get('status') != 'complete' or record.get('case') != case
                or record.get('planned_slot_id') != identity or record.get('stage') != STAGE
                or record.get('bank_version') != BANK or record.get('methods') != list(METHODS)
                or record.get('replicates') != REPEATS or record.get('logical_branch_count') != 20
                or record.get('protocol_sha256') != protocol or type(record.get('no_cut')) is not bool):
            raise ValueError('Collection source identity or five-by-four label contract changed')
        y = np.empty((5, REPEATS), dtype=bool)
        source = ROOT/'sources'/case['case_id']
        source_summary = sealed_json(source, 'summary.json', record['source_seal_sha256'], protocol=protocol)
        if (source_summary.get('case') != case or source_summary.get('planned_slot_id') != identity
                or source_summary.get('cuts') != record['cuts']
                or source_summary.get('actual_cut') != record['actual_cut']):
            raise ValueError('Source anchor identity differs from its collection')
        if record['no_cut']:
            if (record['cuts'] or record['actual_cut'] is not None or record['branch_records']
                    or record['actual_branch_count'] != 0 or record.get('common_outcome_available') is not True
                    or type(record.get('common_outcome')) is not bool
                    or source_summary.get('no_alarm') is not True
                    or source_summary.get('full_episode_outcome_available') is not True
                    or type(source_summary.get('success')) is not bool
                    or source_summary['success'] != record['common_outcome']):
                raise ValueError('No-cut source lacks its real common full-episode outcome')
            y[:] = source_summary['success']
        else:
            refs = record['branch_records']; by_pair = {(r['method'], r['repeat']): r for r in refs}
            cut = record['actual_cut']
            if (type(cut) is not int or cut % 10 != 5 or not 5 <= cut <= 285 or record['cuts'] != [cut]
                    or len(refs) != len(by_pair) or len(refs) != 20 or record['actual_branch_count'] != 20
                    or set(by_pair) != {(method, repeat) for method in METHODS for repeat in range(REPEATS)}):
                raise ValueError('Incomplete five-arm four-repeat physical branches')
            for arm, method in enumerate(METHODS):
                for repeat in range(REPEATS):
                    ref = by_pair[(method, repeat)]
                    branch = ROOT/'rollouts'/STAGE/BANK/actual/f'cut{cut:03d}'/method/f'repeat_{repeat}'
                    if Path(ref['summary_path']).resolve() != branch/'summary.json':
                        raise ValueError('Collection points to another source/method/repeat')
                    observed = sealed_json(branch, 'summary.json', ref['seal_sha256'], protocol=protocol)
                    wanted = dict(status='complete', episode_id=actual, planned_slot_id=identity,
                        method=method, repeat=repeat, cut_step=cut, stage=STAGE, bank_version=BANK,
                        source_seal_sha256=record['source_seal_sha256'],
                        candidate_bank_sha256=record['candidate_bank_sha256'],
                        paired_suffix_id=f'{actual}:cut{cut}:repeat{repeat}')
                    if (any(observed.get(k) != v for k, v in wanted.items())
                            or type(observed.get('success')) is not bool or type(ref.get('success')) is not bool
                            or observed['success'] != ref['success']):
                        raise ValueError('Actual sealed branch label or paired identity changed')
                    y[arm, repeat] = observed['success']
        labels.append(y)
        rows.append(dict(planned_slot_id=identity, resolved_episode_id=actual, task=case['task'],
            no_cut=record['no_cut'], actual_cut=record['actual_cut'],
            outcomes={method: y[index].tolist() for index, method in enumerate(METHODS)}))
    return np.stack(labels), rows


def comparison(candidate, baseline, bootstrap=None):
    signed = candidate.astype(np.int64)-baseline.astype(np.int64)
    difference = signed.sum(axis=1)/REPEATS
    result = dict(gain=float(difference.mean()), rescues=int((signed == 1).sum()), harms=int((signed == -1).sum()),
        positive_sources=int((difference > 0).sum()), negative_sources=int((difference < 0).sum()),
        zero_sources=int((difference == 0).sum()))
    if bootstrap is not None:
        result['source_95ci'] = np.quantile(difference[bootstrap].mean(axis=1), [.025, .975], method='linear').tolist()
    return result


def aggregate(y, rows):
    """Independent arithmetic; no import or invocation of the production reducer."""
    if y.shape != (100, 5, REPEATS) or y.dtype != np.dtype('bool') or len(rows) != 100:
        raise ValueError('Require all 100 source-by-five-arm-by-four-repeat observed booleans')
    tasks = np.asarray([row['task'] for row in rows]); no_cut = np.asarray([row['no_cut'] for row in rows], bool)
    if Counter(tasks) != Counter({task: 20 for task in TASKS}):
        raise ValueError('Whole-source resampling requires 20 registered sources per task')
    rng = np.random.default_rng(2026091622)
    bootstrap = np.concatenate([rng.choice(np.flatnonzero(tasks == task), size=(10000, 20), replace=True)
                                for task in TASKS], axis=1)
    def group(mask, intervals=False):
        data = y[mask]; n = len(data)
        if not n:
            return dict(sources=0, logical_outcomes_per_arm=0, success_counts=None, success_rates=None, comparisons=None)
        counts = data.sum(axis=(0, 2), dtype=np.int64)
        return dict(sources=n, logical_outcomes_per_arm=REPEATS*n, success_counts=dict(zip(METHODS, counts.tolist())),
            success_rates=dict(zip(METHODS, (counts/(REPEATS*n)).tolist())),
            comparisons={METHODS[a]+'_minus_'+METHODS[b]: comparison(data[:, a], data[:, b],
                bootstrap if intervals else None) for a, b in PAIRS})
    statistics = dict(overall=group(np.ones(100, dtype=bool), True),
        per_task={task: group(tasks == task) for task in TASKS},
        alarm_conditioned=group(~no_cut), no_cut_common_outcomes=group(no_cut))
    main = statistics['overall']['comparisons'][PRIMARY_COMPARISON]
    net = main['rescues']-main['harms']
    assessment = dict(comparison=PRIMARY_COMPARISON, method_fixed_before_heldout='post',
        paired_success_difference=net, point_estimate=net/400, practical_target=.05,
        point_estimate_target_met=net >= 20, source_95ci=list(main['source_95ci']),
        ci_supports_positive_gain=main['source_95ci'][0] > 0,
        true_gain_at_least_target_guaranteed=False,
        nonpositive_or_crossing_ci_does_not_prove_ineffectiveness=True,
        posthoc_method_selection=False, selection_rule_changed=False,
        interpretation='Report point target attainment and interval evidence separately; neither guarantees a true gain of at least five percentage points.')
    return statistics, assessment


def write(name, value):
    with (OUT/name).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False); stream.write('\n')


def main():
    if (OUT/'result.json').exists() or (OUT/'complete.json').exists():
        raise FileExistsError('Independent result version is immutable')
    cfg, ids, lookup, slots, primary_seal_sha = completed_gate()
    labels, rows = collect_labels(cfg, ids, lookup, slots)
    statistics, assessment = aggregate(labels, rows)
    # Open main statistical output only AFTER independent aggregation.
    primary = sealed_json(PRIMARY, 'result.json', primary_seal_sha, role='native10_heldout_readonly_audit')
    if (primary.get('status') != 'passed' or primary.get('planned_slots') != 100
            or primary.get('technical_missing') != 0 or primary.get('config_sha256') != CONFIG_SHA
            or primary.get('freeze_sha256') != FREEZE_SHA or primary.get('logical_outcomes_per_arm') != 400
            or primary.get('final_selection') != cfg['heldout_collection']['final_selection']
            or primary.get('selection_seal_created') is not False
            or primary.get('selection_release_authorized') is not False):
        raise ValueError('Primary audit completion/config/fixed-selection contract differs')
    main_stats = primary['statistics']
    if (main_stats.get('status') != 'complete_statistics_fixed_policy'
            or main_stats.get('fixed_method') != 'post' or main_stats.get('primary_comparison') != PRIMARY_COMPARISON
            or main_stats.get('primary_ids') != ids or main_stats.get('replicates') != REPEATS
            or main_stats.get('source_denominator') != 100 or main_stats.get('calibration_outcomes_pooled') is not False
            or 'selection_proposal' in main_stats or 'selection_proposal' in primary):
        raise ValueError('Heldout cannot change the fixed primary, pool calibration or propose another policy')
    for key, value in statistics.items():
        if main_stats[key] != value:
            raise ValueError('Independent statistical mismatch: '+key)
    if primary.get('primary_assessment') != assessment or main_stats.get('primary_assessment') != assessment:
        raise ValueError('Fixed P-minus-R assessment differs from independent arithmetic')
    if len(primary['per_source']) != 100:
        raise ValueError('Primary result omitted sources')
    for row, other in zip(rows, primary['per_source']):
        if any(other[key] != row[key] for key in row):
            raise ValueError('Independent source/repeat mismatch: '+row['planned_slot_id'])
    reached = sum(not row['no_cut'] for row in rows)
    if primary['physical_branches'] != reached*20 or main_stats['physical_branch_count'] != reached*20:
        raise ValueError('Physical branches differ from all-cut five-by-four outcomes')
    # Ensure every consumed metadata input remained immutable through the computation.
    if any(sha(path) != digest for path, digest in INPUTS.items()):
        raise ValueError('Consumed sealed metadata changed during independent aggregation')
    result = dict(status='passed', role='native10_heldout_independent_reaggregation',
        created_utc=datetime.now(timezone.utc).isoformat(), statistics=statistics, primary_assessment=assessment,
        per_source=rows, planned_slots=100, resolved_sources=100, reached_sources=reached,
        no_cut_sources=100-reached, logical_outcomes_per_arm=400, physical_branches=reached*20,
        primary_comparison=PRIMARY_COMPARISON, final_selection=cfg['heldout_collection']['final_selection'],
        primary_audit_comparison=dict(exact=True, path=str(PRIMARY/'result.json'), sha256=sha(PRIMARY/'result.json'),
                                     seal_sha256=primary_seal_sha, seven_comparisons_exact=True,
                                     all_groups_and_source_outcomes_exact=True, primary_assessment_exact=True),
        bootstrap=dict(draws=10000, seed=2026091622, task_order=list(TASKS), source_order=ids,
            sampling='NumPy default_rng.choice within task, retaining all five arms and four repeats',
            unit='whole logical primary source', percentile=[2.5, 97.5], quantile_method='linear',
            multiplicity_adjusted=False, per_source_confidence_intervals=False),
        code=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)),
        runtime=dict(sys_executable=sys.executable, python_version=sys.version, numpy_version=np.__version__),
        dependencies=INPUTS, physical_trajectory_audit_repeated=False, production_reducer_called=False,
        model_calls=0, simulator_calls=0, optimizer_updates=0, heldout_outcomes_read_after_full_completion=True,
        heldout_mutations=0, selection_seal_created=False, new_selection_proposed=False,
        limitations=['Sealed branch summaries and no-cut source summaries independently supply outcomes; primary audit owns trajectory/scene/ledger verification.',
            'Four suffixes remain paired within a source; the 100 initial sources are the inference units.',
            'Seven percentile intervals are unadjusted; only preregistered post-minus-replan is primary.',
            'Point estimate >=5pp is separate from interval support for positive gain; true gain >=5pp is never guaranteed.',
            'Calibration is not pooled; no task/source/method is chosen after observing heldout.'])
    write('result.json', result)
    with (OUT/'paired_outcomes.npz').open('xb') as stream:
        np.savez_compressed(stream, outcomes=labels, primary_ids=np.asarray(ids), methods=np.asarray(METHODS))
    files = {p.name: sha(p) for p in OUT.iterdir() if p.is_file()}
    write('complete.json', dict(status='complete', role=result['role'], files=files,
        model_calls=0, simulator_calls=0, optimizer_updates=0, selection_seal_created=False))
    print(json.dumps(dict(status='passed', path=str(OUT), seal_sha256=sha(OUT/'complete.json'),
        result_sha256=sha(OUT/'result.json'), overall=statistics['overall'], primary_assessment=assessment,
        reached_sources=reached, no_cut_sources=100-reached), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
