"""CPU-only final publication for the original B H20 completion event."""
import csv
import io
import json
import os
import socket
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import quota_runtime as q


def main():
    eid = 'B_bf89afc3215f1a51200a2a27282672ad'
    c, p, queue = q.C, q.P, q.Q
    wave = queue / 'waves/H20_01'
    state = c / 'persistent_queue/nodes/B/wakeup'
    receipts = c / 'receipts/B'
    audit_path = receipts / 'events' / (eid + '_AUDIT.json')
    if audit_path.exists():
        raise RuntimeError('Audit already exists; inspect it before any replacement')
    q.authority()
    event_path = state / 'outbox' / (eid + '.json')
    event = q.read(event_path)
    assert event['event_id'] == eid and event['outcome'] == 'complete'
    assert event['executor_thread_id'] == q.THREAD == os.environ['CODEX_THREAD_ID']
    assert event['hostname'] == socket.gethostname()
    assert q.sha(wave / 'CLAIM.json') == event['claim_identity']['sha256']
    assert Path(event['result_path']) == wave / 'RESULT.json'
    result, final = q.read(wave / 'RESULT.json'), q.read(wave / 'FINAL_SUMMARY.json')
    assert result['status'] == 'complete' and result['exit_code'] == 0
    assert result['publication_completed'] and not result['publication_error']
    assert final['attempts'] == 976 and final['status'] == 'complete'

    csv_paths = [p / 'H20_r1/FINAL_EPISODES.csv', wave / 'FINAL_EPISODES.csv',
                 p / 'H30_r1/FINAL_EPISODES.csv']
    parts = []
    for path in csv_paths:
        with path.open() as handle:
            parts.append([r for r in csv.DictReader(handle) if r['status'] == 'complete'])
    assert [len(x) for x in parts] == [24, 976, 1000]
    ids = [{r['unit_id'] for r in part} for part in parts]
    assert all(len(x) == len(part) for x, part in zip(ids, parts))
    assert not (ids[0] & ids[1]) and not ((ids[0] | ids[1]) & ids[2])

    transfer_path = q.gates.AH / 'TRANSFER_READY.json'
    transfer = q.read(transfer_path)
    expected = {}
    for job in transfer['nodes']['B']['jobs']:
        for source in job['sources']:
            uid = job['cell_id'] + '__' + source['source_id']
            assert uid not in expected
            expected[uid] = (job, source)
    rows = parts[0] + parts[1] + parts[2]
    assert {r['unit_id'] for r in rows} == set(expected)
    assert len(rows) == 2000
    selected = q.gates.selection()
    assert selected['chosen_loss'] == 'L01' and selected['ensemble']['fit_seed'] == 9101
    assert final['selection'] == q.sha(q.gates.A / 'SELECTION.json')
    for row in rows:
        job, source = expected[row['unit_id']]
        assert row['success'] in ('True', 'False') and row['terminal'] == 'True'
        assert not row['technical_failure']
        assert row['method'] == job['method'] and int(row['H']) == job['H']
        for key in ('source_id', 'task', 'split'):
            assert row[key] == source[key], (row['unit_id'], key)
        for key in ('env_seed', 'policy_seed'):
            assert int(row[key]) == source[key], (row['unit_id'], key)
        assert row['selected_loss'] == 'L01' and int(row['fit_seed']) == 9101
        assert int(row['action_dim']) == 4 and float(row['action_scale']) == .015
        assert int(row['control_hz']) == 30 and int(row['physics_hz']) == 400
        assert Path(row['result_path']).is_file()

    aggregate = q.read(queue / 'AGGREGATE.json')
    assert not aggregate['missing'] and len(aggregate['rows']) == 3500
    selected_rows = {r['unit_id']: r for r in aggregate['rows'] if r['stage'] in ('H20', 'H30')}
    assert len(selected_rows) == 2000 and set(selected_rows) == set(expected)
    for row in rows:
        merged = selected_rows[row['unit_id']]
        assert isinstance(merged['success'], bool)
        assert merged['success'] == (row['success'] == 'True')
        assert merged['result'] == row['result_path'] and merged['status'] == 'complete'
    assert q.read(queue / 'FINAL_MISSING.json') == []

    checks = [{'root': str(root), 'alive': q.alive(root), 'clean_exit': q.clean_exit(root)}
              for root in q.all_roots()]
    assert all(not x['alive'] and x['clean_exit'] for x in checks)
    queue_result = q.read(queue / 'RESULT.json')
    assert queue_result['status'] == 'complete' and not q.alive(queue)
    assert q.gates.family_exited(p)
    observer = q.read(state / 'PROCESS.json')
    assert q.same_process(q.normalized(observer))
    heartbeat = q.read(state / 'HEARTBEAT.json')
    observer_age = time.time() - datetime.fromisoformat(heartbeat['at_utc']).timestamp()
    assert observer_age < 120 and heartbeat['state'] == 'supervising'
    assert q.read(state / 'SERVICE_REGISTRATION.json')['executor_thread_id'] == q.THREAD
    guard = q.read(Path('/tmp/gpu_occupancy_guard/status.json'))
    guard_process = q.process_identity(guard['pid'])
    assert guard_process and time.time() - guard['updated'] < 120
    assert len(guard['gpus']) == 8 and all(x['state'] == 'holder' for x in guard['gpus'].values())
    for value in guard['gpus'].values():
        assert q.process_identity(value['manager_pid'])
    triggers = [state / 'jobs/D24_B_QUOTA_H20_01__D24_B_QUOTA_H20_01__1.json',
                state / 'jobs/D24_B_QUOTA_INDEPENDENT_r1__D24_B_QUOTA_INDEPENDENT_r1__1.json']
    for path in triggers:
        item = q.read(path)
        assert item['process_identity']['hostname'] == socket.gethostname()
        assert Path(item['result_path']).is_file()
    control, qc = q.read(c / 'CONTROL.json'), q.read(c / 'persistent_queue/CONTROL.json')
    assert not control['stop_requested'] and not qc['global_stop'] and qc['nodes']['B']['enabled']

    cells = []
    for h in (20, 30):
        for method in ('Post', 'Velocity'):
            cell = [r for r in rows if int(r['H']) == h and r['method'] == method]
            assert len(cell) == 500
            successes = sum(r['success'] == 'True' for r in cell)
            cells.append(dict(H=h, method=method, planned=500, valid=500, missing=0,
                              successes=successes, success_rate=successes / 500,
                              current_paper=method == 'Post'))
    counts = Counter((r['stage'], r['method']) for r in aggregate['rows'])
    totals = [dict(stage=k[0], method=k[1], valid=v,
                   successes=sum(r['success'] for r in aggregate['rows']
                                 if (r['stage'], r['method']) == k))
              for k, v in sorted(counts.items())]
    table_path = p / 'FINAL_RECOVERED_CELLS_r2.csv'
    csv_text = io.StringIO()
    writer = csv.DictWriter(csv_text, fieldnames=list(cells[0]))
    writer.writeheader()
    writer.writerows(cells)
    with table_path.open('x') as handle:
        handle.write(csv_text.getvalue())
    summary_path = p / 'FINAL_RECOVERED_SUMMARY_r2.json'
    summary = dict(schema='B_selected_H20_H30_recovered_final_v2', status='complete',
                   task_id='B_D24_PI05_SELECTED_H20_H30_V1', revision=2, utc=q.utc(),
                   publication_only=True, valid=2000, planned=2000, missing=0, cells=cells,
                   selected_loss='L01', fit_seed=9101, Post_only_development_selection=True,
                   selection=q.ref(q.gates.A / 'SELECTION.json'), exact_transfer=q.ref(transfer_path),
                   source_tables=[q.ref(x) for x in csv_paths], table=q.ref(table_path),
                   H20_preserved_valid=24, H20_continuation_valid=976,
                   original_H20_valid_false_preserved=sum(r['success'] == 'False' for r in parts[0]),
                   no_duplicate_units=True, complete_expected_source_seed_metadata=True,
                   original_partial_result=q.ref(p / 'RESULT.json'),
                   continuation_result=q.ref(wave / 'RESULT.json'),
                   H30_result=q.ref(p / 'H30_r1/RESULT.json'),
                   aggregate=q.ref(queue / 'AGGREGATE.json'),
                   cumulative_B_attempts=aggregate['cumulative_B_attempts'],
                   H20_attempts=q.stage_attempts('H20'), H30_attempts=q.stage_attempts('H30'),
                   stage_attempt_cap_each=1100, node_attempt_cap=22000,
                   new_training_updates=0, new_collection=0, new_handler_scientific_launches=0,
                   missing_not_failure=True, occupancy_cost_excluded=True,
                   original_failures_and_results_preserved=True,
                   all_owned_descendants_exited=True, occupancy_handoff_complete=True,
                   evidence_scope='Saved terminal CSV metadata and merged terminal result index; no new scientific runs')
    assert summary['H20_attempts'] == summary['H30_attempts'] == 1000
    assert summary['cumulative_B_attempts'] <= 22000
    q.new_json(summary_path, summary)
    receipt_path = receipts / 'B_D24_PI05_SELECTED_H20_H30_V1_RESULT_r2.json'
    q.new_json(receipt_path, dict(summary, final_summary=q.ref(summary_path), A_waits_for_B=False))
    q.atomic_json(p / 'RESULT_LATEST.json', dict(status='complete', revision=2, utc=q.utc(),
                  final_summary=q.ref(summary_path), receipt=q.ref(receipt_path),
                  original_RESULT_json_preserved=True))
    no_run_path = queue / ('NO_RUNNABLE_TASKS_' + eid + '.json')
    q.new_json(no_run_path, dict(status='NO_RUNNABLE_TASKS', reason='All current B quota stages completed',
               utc=q.utc(), completed_counts=totals, remaining_units=0, blocked_units=[],
               queue_result=q.ref(queue / 'RESULT.json'), CONTROL_revision=control['revision'],
               queue_CONTROL_revision=qc['revision'],
               stale_task_board_labels_do_not_authorize_replay=True,
               dependency_monitor=observer, holder_policy='all_off_during_formal; restored_after_all_family_exit'))
    audit = dict(schema='B_H20_continuation_terminal_audit_v1', event_id=eid, node='B',
                 utc=q.utc(), executor_thread_id=q.THREAD, handler_outcome='audited_complete',
                 audit_complete=True, event=q.ref(event_path), claim=q.ref(wave / 'CLAIM.json'),
                 claim_verified=True, small_result=q.ref(wave / 'RESULT.json'),
                 CONTROL=q.ref(c / 'CONTROL.json'), CONTROL_revision=control['revision'],
                 queue_CONTROL=q.ref(c / 'persistent_queue/CONTROL.json'), queue_CONTROL_revision=qc['revision'],
                 TASK_BOARD=q.ref(c / 'TASK_BOARD.json'), final_summary=q.ref(summary_path),
                 final_receipt=q.ref(receipt_path), no_duplicate_launch=True,
                 new_handler_scientific_launches=0, new_GPU_preflights=0,
                 all_current_quota_science_complete=True, valid_quota_units=3500,
                 valid_selected_H20_H30_units=2000, missing=0, completed_counts=totals,
                 runtime_family_checks=checks, original_parent_exited=True, quota_supervisor_exited=True,
                 queue_result=q.ref(queue / 'RESULT.json'), background_stable=True,
                 observer_process=q.process_identity(observer['pid']), observer_heartbeat_age_seconds=observer_age,
                 terminal_triggers=[q.ref(x) for x in triggers], terminal_triggers_registered=True,
                 holder_exit_evidence=q.ref(wave / 'chain/HOLDER_EXIT_ACK.json'),
                 cleanup_evidence=q.ref(wave / 'chain/CHAIN_RESULT.json'),
                 guard_status=guard, guard_process=guard_process, restored_holder_count=8,
                 occupancy_is_host_local=True, no_continuous_utilization_guarantee=True,
                 no_runnable_tasks=q.ref(no_run_path), A_waits_for_B=False,
                 action='Publish final merged results; keep original partial evidence; leave completed queues exited and existing dependency observer and occupancy guard active.')
    q.new_json(audit_path, audit)
    handoff_path = queue / ('STABLE_HANDOFF_' + eid + '.json')
    q.new_json(handoff_path, dict(status='STABLE_HANDOFF', utc=q.utc(), event_id=eid,
               phase='all_current_assigned_stages_complete_idle_monitoring',
               audit=q.ref(audit_path), final_receipt=q.ref(receipt_path),
               observer=observer, terminal_triggers_registered=True, restored_holder_count=8,
               active_scientific_families=0, no_runnable_tasks=q.ref(no_run_path), A_waits_for_B=False))
    q.atomic_json(state / 'STABLE_HANDOFF.json', dict(status='STABLE_HANDOFF', utc=q.utc(),
                  event_id=eid, audit=q.ref(audit_path), current=q.ref(handoff_path)))
    print(json.dumps(dict(status='audited_complete', audit=str(audit_path), receipt=str(receipt_path),
                          cells=cells, quota_valid=3500, missing=0,
                          observer_alive=True, restored_holders=8), ensure_ascii=False))


if __name__ == '__main__':
    main()
