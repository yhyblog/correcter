"""CPU-only terminal audit from frozen source records; never launches evaluation."""
import collections
import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

C = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK = 'C_D24_R_H40_H50_V1'
ROOT = C / 'results/C' / TASK
R = ROOT / 'r2'
EID = 'C_20efac354dbe58e31fe85df0c5de9337'
EVENT = C / 'persistent_queue/nodes/C/wakeup/outbox' / (EID + '.json')
AUDIT = C / 'receipts/C/events' / (EID + '_AUDIT.json')


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def csvrows(path):
    with Path(path).open(newline='') as f:
        return list(csv.DictReader(f))


def close(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-10), (a, b)


def main():
    event, claim, result = read(EVENT), read(R / 'CLAIM.json'), read(R / 'RESULT.json')
    assert event['event_id'] == EID and event['job']['task_id'] == TASK
    assert event['executor_thread_id'] == '01a0c793-10d2-7791-a250-fd65d88e1ccb'
    assert event['synthetic'] is False and event['result'] == result
    assert event['job']['claim_identity']['path'] == str(R / 'CLAIM.json')
    assert event['job']['claim_identity']['sha256'] == sha(R / 'CLAIM.json')
    assert event['job']['process_identity'] == claim['process']
    assert claim['config']['sha256'] == sha(claim['config']['path'])
    assert claim['authorization_sha256'] == sha(C / 'deadline_20260924/R_H_SWEEP_AUTHORIZATION_V1.json')
    assert result['status'] == 'complete' and result['exit_code'] == 0
    assert result['fatal'] is None and result['new_automatic_retries'] == 0
    source_path = R / 'config/TEST_SOURCES_V1.json'
    assert sha(source_path) == sha(C / 'deadline_20260924/A/config/TEST_SOURCES_V1.json')
    sources = {x['source_id']: x for x in read(source_path)['rows'] if x['ordinal'] < 10}
    assert len(sources) == 500
    tasks = sorted({x['task'] for x in sources.values()})
    assert len(tasks) == 50 and all(sum(x['task'] == t for x in sources.values()) == 10 for t in tasks)
    order = sorted(sources, key=lambda k: (sources[k]['task'], sources[k]['ordinal']))
    claims = sorted(R.glob('unit_claims/*.json'))
    assert len(claims) == 1000 and len(list(R.glob('claims/*.json'))) == 100
    terminals = {}
    intervention_count = collections.Counter()
    for path in claims:
        admission = read(path)
        h, source = admission['H'], admission['source']
        key = (h, source['source_id'])
        assert key not in terminals and h in (40, 50)
        assert admission['method'] == 'R' and admission['attempt'] == 1 and admission['retry'] is False
        assert source == sources[source['source_id']]
        out = Path(admission['output'])
        assert out.is_relative_to(R / 'runs') and (out / 'ENTERED.json').exists()
        ep = read(out / 'RESULT.json')
        for field in ['source_id', 'task', 'ordinal', 'env_seed', 'policy_seed', 'split']:
            assert ep[field] == source[field], (key, field)
        assert ep['H'] == h and ep['method'] == 'R' and ep['status'] == 'complete'
        assert type(ep['success']) is bool and ep['terminal'] is True and ep['technical_failure'] is None
        assert ep['repeat'] == 0 and 0 < ep['steps'] <= 300
        assert (ep['control_hz'], ep['physics_hz'], ep['action_scale'], ep['action_dim']) == (30, 400, .015, 4)
        assert ep['max_interventions'] == 1 and ep['interventions'] in (0, 1)
        assert ep['flow_calls'] == 10 * ep['policy_calls'] == 10 * ep['sampling_calls']
        fired = [x for x in ep['events'] if x['intervention_executed']]
        assert len(fired) == ep['interventions']
        for ev in fired:
            assert ev['history_mature'] and ev['legal_cut'] and ev['true_G0_trigger'] and ev['gate'] > .05
            assert ev['gate_threshold'] == .05 and ev['commit_until'] == ev['step'] + 10
            assert not ev['forced_intervention'] and not ev['synthetic']
            assert ev['generation']['method'] == 'R' and ev['generation']['Q_acceptance_gate'] is False
        assert ep['first_cut'] == (fired[0]['step'] if fired else None)
        for field in ['elapsed_seconds', 'inference_seconds', 'environment_seconds']:
            assert math.isfinite(ep[field]) and ep[field] >= 0
        terminals[key] = ep
        intervention_count[h, ep['interventions']] += 1
    assert set(terminals) == {(h, sid) for h in (40, 50) for sid in sources}
    for path in R.glob('runs/*/RESULT.json'):
        job = read(path)
        assert job['status'] == 'complete' and job['technical_failures'] == 0
        assert job['entered_episodes'] == job['terminal_episodes'] == len(job['episodes']) == 10
        assert len({ep['source_id'] for ep in job['episodes']}) == 10
        for ep in job['episodes']:
            assert ep == terminals[job['H'], ep['source_id']]
        assert job['successes'] == sum(ep['success'] for ep in job['episodes'])
    assert len(list(R.glob('runs/*/RESULT.json'))) == 100
    summary = read(R / 'SUMMARY.json')
    for h in (40, 50):
        eps = [terminals[h, sid] for sid in order]
        cell = summary['cells'][f'R_H{h}']
        assert cell['attempts'] == cell['valid'] == cell['planned'] == 500
        assert cell['successes'] == sum(x['success'] for x in eps)
        close(cell['terminal_success_rate'], cell['successes'] / 500)
        assert cell['technical_failures'] == cell['unknown_entered'] == cell['not_started'] == 0
        assert cell['interventions'] == {str(i): intervention_count[h, i] for i in (0, 1)}
        for field in ['elapsed_seconds', 'inference_seconds', 'environment_seconds', 'flow_calls', 'policy_calls']:
            close(cell[field], sum(x[field] for x in eps))
    csv_eps = csvrows(R / 'EPISODES.csv')
    assert len(csv_eps) == len({(x['H'], x['source_id']) for x in csv_eps}) == 1000
    for row in csv_eps:
        ep = terminals[int(row['H']), row['source_id']]
        for field in ['source_id', 'task', 'ordinal', 'env_seed', 'policy_seed', 'success', 'status', 'steps', 'interventions']:
            assert row[field] == str(ep[field])
    task_rows = csvrows(R / 'TASK_RESULTS.csv')
    assert len(task_rows) == len({(x['H'], x['task']) for x in task_rows}) == 100
    for row in task_rows:
        eps = [ep for (h, _), ep in terminals.items() if h == int(row['H']) and ep['task'] == row['task']]
        assert len(eps) == int(row['valid']) == int(row['attempts']) == int(row['planned']) == 10
        assert int(row['successes']) == sum(x['success'] for x in eps)
        assert all(int(row[x]) == 0 for x in ['technical_failures', 'unknown_entered', 'not_started'])

    # Rebuild all joins from the published baseline sources, without importing report.py.
    comparisons = read(R / 'PAIRED_COMPARISONS.json')
    a_rows = csvrows(comparisons['existing_A_main'])
    paired = {}
    rng = np.random.default_rng(20260921)
    selections = rng.integers(0, 10, size=(2000, 50, 10))
    recomputed = []
    for h in (40, 50):
        paired['R'] = {sid: terminals[h, sid] for sid in sources}
        n_rows = [ep for task in tasks for ep in read(Path(comparisons['existing_N']) / f'N_H{h}_{task}/RESULT.json')['episodes']]
        for method, rows in [('N', n_rows)] + [(m, [x for x in a_rows if int(x['H']) == h and x['method'] == m]) for m in ['Post', 'Velocity']]:
            assert len(rows) == 500 and len({x['source_id'] for x in rows}) == 500
            paired[method] = {x['source_id']: x for x in rows}
            assert set(paired[method]) == set(sources)
            for sid, ep in paired[method].items():
                assert ep['status'] == 'complete' and ep['success'] in (True, False, 'True', 'False')
                for field in ['env_seed', 'policy_seed', 'ordinal']:
                    assert int(ep[field]) == sources[sid][field]
                assert ep['task'] == sources[sid]['task']
        for left, right in [('R', 'N'), ('Post', 'R'), ('Velocity', 'R')]:
            a = np.array([paired[left][sid]['success'] in (True, 'True') for sid in order], dtype=np.int64)
            b = np.array([paired[right][sid]['success'] in (True, 'True') for sid in order], dtype=np.int64)
            difference = (a - b).reshape(50, 10)
            # Gather each task's resampled columns, then average over all 500 pairs.
            draws = np.take_along_axis(np.broadcast_to(difference, (2000, 50, 10)), selections, axis=2).sum((1, 2)) / 5
            low, high = np.quantile(draws, [.025, .975])
            rec = dict(H=h, comparison=f'{left}-{right}', paired_valid=500, left_successes=int(a.sum()), right_successes=int(b.sum()),
                       rescued=int(((a == 1) & (b == 0)).sum()), harmed=int(((a == 0) & (b == 1)).sum()),
                       delta_percentage_points=float((a - b).sum() / 5), bootstrap95_low_percentage_points=float(low), bootstrap95_high_percentage_points=float(high))
            existing = [x for x in comparisons['comparisons'] if x['H'] == h and x['comparison'] == rec['comparison']]
            assert len(existing) == 1
            for k, v in rec.items():
                if k != 'comparison': close(existing[0][k], v)
            assert existing[0]['seed'] == 20260921 and existing[0]['replicates'] == 2000
            recomputed.append(rec)
    pair_csv = csvrows(R / 'PAIRED_COMPARISONS.csv')
    assert len(pair_csv) == len(comparisons['comparisons']) == len(recomputed) == 6
    for rec in recomputed:
        row = next(x for x in pair_csv if int(x['H']) == rec['H'] and x['comparison'] == rec['comparison'])
        for k, v in rec.items():
            if k != 'comparison': close(row[k], v)

    runtime = read(R / 'evidence/TERMINAL_RUNTIME_AUDIT.json')
    assert runtime['all_recorded_formal_identities_absent'] and runtime['formal_group_empty']
    assert runtime['all8_guard_states_holder'] and runtime['all8_holder_managers_live']
    assert runtime['nvidia_smi']['exit_code'] == 0
    manager = read(R / 'chain/MANAGER_EXIT.json')
    assert manager['all_jobs_complete'] and manager['all_owned_processes_exited']
    assert manager['auxiliary_holder_launches'] == 0
    workers = [read(p) for p in sorted(R.glob('chain/workers/*/WORKER_EXIT.json'))]
    models = [read(p) for p in sorted(R.glob('chain/workers/*/MODEL_READY.json'))]
    assert len(workers) == len(models) == 8 and all(w['fatal'] is None for w in workers)
    assert sum(w['method_counts']['sampling'] for w in workers) == sum(ep['policy_calls'] for ep in terminals.values())
    assert not list(ROOT.glob('unit_claims/*.json')) and not list(ROOT.glob('runs/*/episodes/*/ENTERED.json'))
    assert summary['prior_C_attempts'] == 1013 and summary['cumulative_C_attempts'] == 2013 <= summary['cumulative_cap'] == 2400
    assert summary['attempts'] == 1000 <= summary['stage_cap'] == 1100
    assert summary['automatic_retries'] == summary['optimizer_updates'] == summary['training_updates'] == 0
    previous_cost = read(R / 'PREVIOUS_STARTUP_COST.json')
    first = dt.datetime.fromisoformat(read(ROOT / 'CLAIM.json')['utc'])
    last = dt.datetime.fromisoformat(result['utc'])
    resource = dict(task_id=TASK, startup_revision=2, current_supervisor_elapsed_seconds=result['elapsed_seconds'],
                    previous_startup=previous_cost, wall_seconds_original_claim_to_terminal=(last-first).total_seconds(),
                    current_model_loads=8, current_model_load_seconds_sum=sum(m['model_load_seconds'] for m in models),
                    episode_wall_seconds_sum=sum(ep['elapsed_seconds'] for ep in terminals.values()),
                    policy_calls=sum(ep['policy_calls'] for ep in terminals.values()), flow_calls=sum(ep['flow_calls'] for ep in terminals.values()),
                    scientific_budget_attempts=1000, prior_C_attempts=1013, cumulative_C_attempts=2013,
                    holder_policy='all holders off during whole formal wave; restored after group exit', auxiliary_holder_launches=0,
                    utilization=read(R / 'chain/UTILIZATION_SUMMARY.json'), runtime_audit=str(R / 'evidence/TERMINAL_RUNTIME_AUDIT.json'),
                    limitation='Sampled utilization is not continuous busy time. Model/episode summed durations overlap in wall time. A comparison runs used another host and different occupancy conditions; no controlled speed claim.')
    write(R / 'RESOURCE_SUMMARY.json', resource)
    audit = dict(event_id=EID, task_id=TASK, utc=dt.datetime.now(dt.timezone.utc).isoformat(), outcome='audited', status='passed',
                 original_thread=event['executor_thread_id'], event_path=str(EVENT), event_sha256=sha(EVENT),
                 claim_path=str(R / 'CLAIM.json'), claim_sha256=sha(R / 'CLAIM.json'), existing_claim_verified=True,
                 terminal_result=str(R / 'RESULT.json'), summary=str(R / 'SUMMARY.json'), source_table_sha256=sha(source_path),
                 unique_claims=1000, unique_valid_terminals=1000, job_terminals=100, per_H={str(h):summary['cells'][f'R_H{h}'] for h in (40,50)},
                 technical_failures=0, unknown_entered=0, not_started=0, per_source_attempts=1, scientific_retries=0,
                 previous_startup_entered_sources=0, previous_startup_cost_retained=True, cumulative_C_attempts=2013,
                 independently_recomputed_pairs=recomputed, runtime_audit=str(R / 'evidence/TERMINAL_RUNTIME_AUDIT.json'),
                 all_owned_formal_descendants_exited=True, all8_holders_restored=True, resource_summary=str(R / 'RESOURCE_SUMMARY.json'),
                 verification_scope='All 1000 scalar terminal records and unique claims, 100 job results, frozen source/seed joins, published CSV totals, 6 independent paired recalculations with fixed-task bootstrap, saved lifecycle evidence and one host runtime check. No trajectory, pixel, full-weight or historical replay audit.',
                 uncertainty='Pointwise 95% within-task bootstrap over fixed 50 tasks; no multiplicity correction or training-seed/task-population uncertainty. Cross-host timing is not a controlled speed comparison.',
                 replayed_prior_Velocity_sources=0, replayed_prior_N_repairs=0, replayed_unknown_sources=0,
                 scientific_launches_in_callback=0, wakeup_events_in_callback=0, script=str(Path(__file__).resolve()), script_sha256=sha(__file__),
                 ACK_to_be_written_by_original_handler=True)
    write(R / 'FINAL_AUDIT.json', audit)
    write(AUDIT, audit)
    print(json.dumps({'status':'passed','audit':str(AUDIT),'sources':1000,'comparisons':recomputed}, indent=2))


if __name__ == '__main__':
    main()
