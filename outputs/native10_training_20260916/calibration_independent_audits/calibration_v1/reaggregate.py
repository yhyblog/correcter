"""One-shot completed-calibration reaggregation; stdlib/NumPy, no frozen reducer."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CONFIG = ROOT/'calibration_protocols/calibration_v1/config.json'
FREEZE = CONFIG.with_name('freeze.json')
WAVE = ROOT/'calibration_execution/calibration/calibration_policy_v1/calibration_v1_01'
PRIMARY = ROOT/'calibration_audits/calibration_v1'
METHODS = ('continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post')
TASKS = ('disassemble-v3', 'pick-place-wall-v3', 'shelf-place-v3', 'stick-pull-v3', 'stick-push-v3')
PAIRS = ((1, 0), (2, 1), (3, 1), (4, 1), (2, 0), (3, 0), (4, 0))
INPUTS = {}


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(2**20), b''):
            value.update(chunk)
    return value.hexdigest()


def read(path, expected=None):
    path = Path(path).resolve(); digest = sha(path)
    if expected is not None and digest != expected:
        raise ValueError('Input SHA mismatch: '+str(path))
    if str(path) in INPUTS and INPUTS[str(path)] != digest:
        raise ValueError('Input changed during aggregation')
    INPUTS[str(path)] = digest
    return json.loads(path.read_text())


def sealed_json(folder, name, expected_seal=None):
    complete = read(folder/'complete.json', expected_seal)
    if complete.get('status') != 'complete':
        raise ValueError('Complete seal required before labels')
    return read(folder/name, complete['files'][name])


def comparison(candidate, baseline, bootstrap=None):
    signed = candidate.astype(np.int64)-baseline.astype(np.int64)
    difference = signed.sum(axis=1)/2
    result = dict(gain=float(difference.mean()), rescues=int((signed == 1).sum()),
        harms=int((signed == -1).sum()), positive_sources=int((difference > 0).sum()),
        negative_sources=int((difference < 0).sum()), zero_sources=int((difference == 0).sum()))
    if bootstrap is not None:
        result['source_95ci'] = np.quantile(difference[bootstrap].mean(axis=1), [.025, .975], method='linear').tolist()
    return result


def write(name, value):
    with (OUT/name).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def main():
    if (OUT/'result.json').exists() or (OUT/'complete.json').exists():
        raise FileExistsError('Independent result version is immutable')
    cfg = read(CONFIG); frozen = read(FREEZE)
    if sha(CONFIG) != frozen['config_sha256']:
        raise ValueError('Frozen config changed')
    registration = cfg['main_collection']['banks']['calibration_policy_v1']
    ids = registration['episode_ids']
    expected_ids = [f'{TASKS[i % 5]}__{start+i}' for start in (2026111700, 2026111800) for i in range(50)]
    if ids != expected_ids or registration['stage'] != 'calibration':
        raise ValueError('Original calibration primary identity/order differs')
    lookup = {row['episode_id']: row for row in cfg['episode_manifest']}
    if Counter(lookup[key]['task'] for key in ids) != Counter({task: 20 for task in TASKS}):
        raise ValueError('Need 20 original primaries per task')
    launch = read(WAVE/'launch_result.json'); spec = read(WAVE/'wave_spec.json')
    if (launch.get('status') != 'complete' or launch.get('returncode') != 0
            or launch.get('lifecycle_covers_entire_wave') is not True
            or spec['config_sha256'] != sha(CONFIG) or spec['freeze_sha256'] != sha(FREEZE)):
        raise ValueError('Full frozen lifecycle wave must finish before label access')
    if not (PRIMARY/'complete.json').is_file():
        raise ValueError('Primary audit must be sealed before independent comparison')
    folders = [WAVE/'workers'/f'worker_{rank:02d}' for rank in range(32)]
    if not all((folder/'complete.json').is_file() for folder in folders):
        raise ValueError('All 32 workers must complete')
    slots = {}
    for rank, folder in enumerate(folders):
        status = sealed_json(folder, 'status.json')
        if (status['status'] != 'complete' or status['assigned_slot_ids'] != ids[rank::32]
                or status['missing_slot_ids'] or status['workers'] != 32):
            raise ValueError('Incomplete worker/slot assignment')
        for identity in ids[rank::32]:
            row = sealed_json(folder, f'slots/{identity}.json')
            chain = [identity]+cfg['main_collection']['replacement_candidates'][identity]
            if (row['status'] != 'complete' or row['planned_slot_id'] != identity
                    or row['resolved_episode_id'] not in chain
                    or [x['episode_id'] for x in row['ordered_rejections']] !=
                        chain[:chain.index(row['resolved_episode_id'])]):
                raise ValueError('Logical/actual source or replacement chain incomplete')
            collection = ROOT/'collections/calibration/calibration_policy_v1'/row['resolved_episode_id']
            if Path(row['completion_path']).resolve() != collection or not (collection/'complete.json').is_file():
                raise ValueError('Missing completed source collection')
            slots[identity] = row
    if len(slots) != 100:
        raise ValueError('Missing source cannot be imputed')
    # Only after the full 100-slot gate do we parse collection outcomes.
    labels, rows, actual_ids = [], [], set()
    for identity in ids:
        slot = slots[identity]; actual = slot['resolved_episode_id']; case = lookup[actual]
        if actual in actual_ids or case['split'] != 'calibration' or case['task'] != lookup[identity]['task']:
            raise ValueError('Repeated or cross-split resolved source')
        actual_ids.add(actual)
        collection = Path(slot['completion_path'])
        record = sealed_json(collection, 'summary.json', slot['completion_sha256'])
        if (record['status'] != 'complete' or record['case'] != case or record['planned_slot_id'] != identity
                or record['methods'] != list(METHODS) or record['replicates'] != 2
                or record['logical_branch_count'] != 10
                or record['protocol_sha256'] != cfg['analysis_approval']['protocol_sha256']):
            raise ValueError('Collection label/source identity changed')
        y = np.empty((5, 2), dtype=bool)
        if record['no_cut']:
            source = ROOT/'sources'/case['case_id']
            summary = sealed_json(source, 'summary.json', record['source_seal_sha256'])
            if (record['cuts'] or record['branch_records'] or record['actual_branch_count'] != 0
                    or record['common_outcome_available'] is not True
                    or type(record['common_outcome']) is not bool
                    or summary['case'] != case or summary['no_alarm'] is not True
                    or summary['full_episode_outcome_available'] is not True
                    or type(summary['success']) is not bool or summary['success'] != record['common_outcome']):
                raise ValueError('No-alarm source lacks its original common full outcome')
            y[:] = summary['success']
        else:
            records = record['branch_records']; by_pair = {(r['method'], r['repeat']): r for r in records}
            if (len(record['cuts']) != 1 or len(records) != len(by_pair)
                    or len(records) != 10 or record['actual_branch_count'] != 10
                    or set(by_pair) != {(method, repeat) for method in METHODS for repeat in range(2)}):
                raise ValueError('Incomplete five-arm two-repeat actual branches')
            for arm, method in enumerate(METHODS):
                for repeat in range(2):
                    success = by_pair[(method, repeat)]['success']
                    if type(success) is not bool:
                        raise ValueError('Physical outcome must be an observed boolean')
                    y[arm, repeat] = success
        labels.append(y)
        rows.append(dict(planned_slot_id=identity, resolved_episode_id=actual, task=case['task'],
            no_cut=record['no_cut'], actual_cut=record['actual_cut'],
            outcomes={method: y[index].tolist() for index, method in enumerate(METHODS)}))
    y = np.stack(labels); tasks = np.asarray([row['task'] for row in rows])
    no_cut = np.asarray([row['no_cut'] for row in rows], dtype=bool)
    rng = np.random.default_rng(2026091622)
    bootstrap = np.concatenate([rng.choice(np.flatnonzero(tasks == task), size=(10000, 20), replace=True)
                                for task in TASKS], axis=1)
    def group(mask, intervals=False):
        data = y[mask]; n = len(data)
        if not n:
            return dict(sources=0, logical_outcomes_per_arm=0, success_counts=None, success_rates=None, comparisons=None)
        counts = data.sum(axis=(0, 2), dtype=np.int64)
        return dict(sources=n, logical_outcomes_per_arm=2*n, success_counts=dict(zip(METHODS, counts.tolist())),
            success_rates=dict(zip(METHODS, (counts/(2*n)).tolist())),
            comparisons={METHODS[a]+'_minus_'+METHODS[b]:comparison(data[:, a], data[:, b],
                bootstrap if intervals else None) for a, b in PAIRS})
    statistics = dict(overall=group(np.ones(100, dtype=bool), True),
        per_task={task: group(tasks == task) for task in TASKS},
        alarm_conditioned=group(~no_cut), no_cut_common_outcomes=group(no_cut))
    # Primary outcomes/statistics are read only after independently computing ours.
    primary = sealed_json(PRIMARY, 'result.json')
    if (primary['status'] != 'passed' or primary['planned_slots'] != 100 or primary['technical_missing'] != 0
            or primary['config_sha256'] != sha(CONFIG)):
        raise ValueError('Primary audit completion/config differs')
    for key, value in statistics.items():
        if primary['statistics'][key] != value:
            raise ValueError('Independent statistical mismatch: '+key)
    if len(primary['per_source']) != 100:
        raise ValueError('Primary result omitted sources')
    for row, other in zip(rows, primary['per_source']):
        if any(other[key] != row[key] for key in row):
            raise ValueError('Independent source/repeat mismatch: '+row['planned_slot_id'])
    net = int(y[:, 4].sum(dtype=np.int64)-y[:, 1].sum(dtype=np.int64))
    method = 'post' if net > 0 else 'alarm_replan10'
    proposal = primary['selection_proposal']
    if (proposal['method'] != method or proposal['paired_success_difference'] != net
            or proposal['mean_source_post_minus_replan'] != net/200
            or proposal['status'] != 'proposal_only' or proposal['ci_used'] or proposal['q_used']
            or proposal['selection_release_authorized'] or proposal['selection_seal_created']):
        raise ValueError('Unsealed global rule proposal differs from the fixed strict-zero arithmetic')
    result = dict(status='passed', role='native10_calibration_independent_reaggregation',
        created_utc=datetime.now(timezone.utc).isoformat(), statistics=statistics, per_source=rows,
        planned_slots=100, resolved_sources=100, reached_sources=int((~no_cut).sum()),
        no_cut_sources=int(no_cut.sum()), logical_outcomes_per_arm=200,
        primary_audit_comparison=dict(exact=True, path=str(PRIMARY/'result.json'), sha256=sha(PRIMARY/'result.json'),
                                     seal_sha256=sha(PRIMARY/'complete.json')),
        global_rule_arithmetic_check=dict(exact=True, net_success_difference=net,
            mean_source_difference=net/200, expected_unsealed_proposal=method, choice_seal_authorized=False),
        bootstrap=dict(draws=10000, seed=2026091622, task_order=list(TASKS), source_order=ids,
            sampling='NumPy default_rng.choice within task, retaining all five arms and both repeats',
            unit='whole logical primary source', percentile=[2.5, 97.5], quantile_method='linear',
            multiplicity_adjusted=False, per_source_confidence_intervals=False),
        code=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)), numpy_version=np.__version__,
        dependencies=INPUTS, physical_trajectory_audit_repeated=False, production_reducer_called=False,
        model_calls=0, simulator_calls=0, optimizer_updates=0, heldout_reads=0, heldout_mutations=0,
        selection_seal_created=False, independent_validation_success=False,
        limitations=['Reaggregation reads sealed collection branch references; primary audit verifies raw trajectories/ledger.',
            'Two repeats remain paired within a source; source-bootstrap intervals are descriptive and unadjusted.',
            'The strict positive global arithmetic is checked, not released or sealed for deployment.'])
    write('result.json', result)
    with (OUT/'paired_outcomes.npz').open('xb') as stream:
        np.savez_compressed(stream, outcomes=y, primary_ids=np.asarray(ids), methods=np.asarray(METHODS))
    files = {p.name: sha(p) for p in OUT.iterdir() if p.is_file()}
    write('complete.json', dict(status='complete', role=result['role'], files=files,
        model_calls=0, simulator_calls=0, optimizer_updates=0, selection_seal_created=False))
    print(json.dumps(dict(status='passed', path=str(OUT), seal_sha256=sha(OUT/'complete.json'),
        result_sha256=sha(OUT/'result.json'), overall=statistics['overall'],
        no_cut_sources=int(no_cut.sum()), global_rule_arithmetic_check=result['global_rule_arithmetic_check']), indent=2))


if __name__ == '__main__':
    main()
