"""Bounded, CPU-only audit of the existing autorecovery terminal event.

Uses prior scientific audits and small control records; never launches work,
signals a process, queries a GPU, delivers a notification or acknowledges it.
"""
import datetime
import json
import socket
import sys
import time
from pathlib import Path

WORK = Path(__file__).resolve().parent
C = WORK.parents[2]
sys.path.insert(0, str(C/'work/C/C_D24_QUOTA_INDEPENDENT_QUEUE_V1_r1'))
import queue_common as q

TASK = 'C_D24_AUTORECOVERY_QUEUE_RULE_V1'
ROOT = C/'results/C'/TASK
EVENT = 'C_8194823fbf3495a8e74dbd439db53358'
STATE = C/'persistent_queue/nodes/C/wakeup'
AUDIT = ROOT/'evidence'/('TERMINAL_AUDIT_'+EVENT+'.json')
FIX = ROOT/'evidence/TERMINAL_HEARTBEAT_FIX'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def handler_ack(eid, outcome):
    path = STATE/'handler_acks'/(eid+'.json')
    row = q.read(path)
    require(row['outcome'] == outcome and row['actual_original_handler_verified'],
            'existing handler ACK mismatch: '+eid)
    return q.ref(path)


def main():
    q.authority()
    if AUDIT.exists():
        print(json.dumps({'status': 'existing_audit_no_repeat', 'audit': str(AUDIT)}))
        return
    event_path = STATE/'outbox'/(EVENT+'.json')
    event = q.read(event_path)
    require(event['event_id'] == EVENT and event['node'] == 'C'
            and event['hostname'] == socket.gethostname()
            and event['executor_thread_id'] == q.policy.EXECUTOR
            and event['synthetic'] is False, 'event identity')
    job = event['job']
    require(job['task_id'] == TASK and job['attempt'] == 1 and job['revision'] == 1,
            'event task/attempt')
    q.verify(job['claim_identity'])
    claim = q.read(ROOT/'CLAIM.json')
    owner = q.read(ROOT/'PROCESS.json')
    require(claim['process'] == owner == job['process_identity'], 'unique process identity')
    require(claim['CPU_only'] and claim['scientific_claims'] == 0
            and claim['authorization_sha256'] == q.policy.AUTH_SHA, 'CPU claim authorization')
    registration = q.read(ROOT/'WAKEUP_REGISTRATION.json')
    require(all(registration[k] == job[k] for k in registration), 'registered terminal job')
    result_ref = q.ref(ROOT/'RESULT.json')
    result = q.read(ROOT/'RESULT.json')
    require(result == event['result'] and result['status'] == 'monitored_tasks_terminal'
            and result['fatal'] is None, 'terminal result')
    for key in ['new_GPU_calls', 'scientific_launches', 'queue_processes_signalled']:
        require(result[key] == 0, 'nonzero control-task count: '+key)
    require(result['all_owned_descendants_exited'] and result['occupancy_handoff_complete']
            and result['original_task_terminals_unmodified'], 'terminal cleanup evidence')
    initial_ack = handler_ack('C_6346d45db738c2eae7e57e6286cf20d2', 'claimed')

    host_path = ROOT/'evidence'/('TERMINAL_HOST_SNAPSHOT_'+EVENT+'.json')
    host = q.read(host_path)
    require(host['host'] == socket.gethostname()
            and host['boot_id'] == owner['boot_id']
            and not host['ops_owner_alive'] and not host['ops_remaining']
            and not q.live(owner), 'CPU owner/family exit')
    require((datetime.datetime.now(datetime.timezone.utc)
             - datetime.datetime.fromisoformat(host['utc'])).total_seconds() < 1800,
            'host exit evidence too old')
    for name, proof in host['science_families'].items():
        require(proof['exited'] and not proof['remaining'], 'science family remains: '+name)

    issue_paths = sorted(p for p in (C/'nodes/C/issues').glob('C_recovery_*.json')
                         if not p.name.endswith('_DECISION.json'))
    require(len(issue_paths) == 1, 'unexpected issue inventory; inspect before proceeding')
    issue_path = issue_paths[0]
    issue = q.read(issue_path)
    require(issue['analysis_response_due_unix'] - issue['reported_at_unix'] == 1800,
            'issue timer changed')
    require(issue['status'] == 'resolved_by_dependency_progress'
            and datetime.datetime.fromisoformat(issue['resolved_at']).timestamp()
            < issue['analysis_response_due_unix'], 'issue resolution')
    require(not Path(issue['response_path']).exists(), 'new decision needs inspection')
    transport_path = ROOT/'transport'/issue_path.name
    transport = q.read(transport_path)
    require(transport['attempts'] == 1 and not transport['automatic_resend']
            and not transport['handler_ACK'] and transport['exit_code'] == 1
            and transport['status'] == 'transport_failed_outbox_retained'
            and transport['target_thread'] == q.policy.ANALYSIS, 'delivery evidence')
    outbox = C/'nodes/C/outbox'/issue_path.name
    require(outbox.exists(), 'failed delivery outbox not retained')

    metadata = q.read(ROOT/'CPU_METADATA_RECOVERY_VERIFIED.json')
    require(metadata['actual_CPU_metadata_recovery_verified']
            and not metadata['scientific_worker_restart_recovery_tested']
            and metadata['new_GPU_calls_by_control_task'] == 0
            and metadata['scientific_compute_added_by_control_task'] == 0,
            'metadata recovery scope')
    for key in ['native_selection_repair', 'native_policy_actually_consumed',
                'pi05_transfer', 'pi05_transfer_repair']:
        q.verify(metadata[key])
    native = q.read(ROOT/'NATIVE_SELECTION_COMPAT_APPLIED.json')
    for key in ['Post_only_selection', 'consumed', 'original_claim']:
        q.verify(native[key])
    require(native['original_waiter'] == q.read(q.X/'PROCESS.json')
            and metadata['pi05_process'] == q.read(q.P/'PROCESS.json'),
            'healthy original waiters not preserved')
    selections = {}
    for root in [q.X, q.P]:
        selection = q.read(root/'SELECTION_CONSUMED.json')
        q.verify(selection['A_selection']); q.verify(selection['A_lock'])
        require(selection['chosen_loss'] == 'L01' and selection['fixed_fit_seed'] == 9101
                and selection['local_test_used'] is False, 'locked Post selection')
        selections[root.name] = q.ref(root/'SELECTION_CONSUMED.json')
    transfer = q.read(q.P/'TRANSFER_CONSUMED.json')
    require(transfer['first_count'] == 2000 and transfer['jobs'] == 400
            and transfer['excluded_A_units'] == [], 'consumed exact transfer scope')

    queues = []
    science_events = [(q.X, 1000, 'C_cbcb4949aa0ac02654a12702a75e95fa'),
                      (q.P, 2000, 'C_0b8e67baac47ec45c382138d97fd5891')]
    for root, expected, eid in science_events:
        inventory_path = ROOT/'terminal_inventories'/(root.name+'.json')
        inventory = q.read(inventory_path)
        terminal = q.read(root/'RESULT.json')
        prior_path = root/'evidence'/('TERMINAL_AUDIT_'+eid+'.json')
        prior = q.read(prior_path)
        require(inventory['expected'] == inventory['legal_terminals_preserved'] == expected
                and not inventory['remaining'] and inventory['launch'] is False,
                'unreconciled units: '+root.name)
        require(terminal['status'] == 'complete' and terminal['all_owned_descendants_exited']
                and prior['status'] == 'audited_complete', 'prior terminal audit: '+root.name)
        q.verify(prior['claim'])
        queues.append(dict(task_id=root.name, legal_terminals=expected, remaining=0,
                           claim=q.ref(root/'CLAIM.json'), result=q.ref(root/'RESULT.json'),
                           inventory=q.ref(inventory_path), prior_audit=q.ref(prior_path),
                           prior_handler_ACK=handler_ack(eid, 'audited')))
    require(q.counts() == (1000, 2000, 14943), 'scientific attempt counters changed')

    guard = q.snapshot('/tmp/gpu_occupancy_guard/status.json')
    require(set(guard.get('gpus', {})) == {str(i) for i in range(8)}
            and time.time()-guard['updated'] < 30, 'guard cache not fresh')
    holders = []
    for gpu, row in sorted(guard['gpus'].items()):
        actual = q.process_identity(row['manager_pid'])
        require(row['state'] == 'holder' and actual is not None and actual['state'] != 'Z',
                'holder manager not alive: '+gpu)
        holders.append(dict(gpu=gpu, cached=row, actual_manager=actual))
    services = {}
    for name, path in [('quota', q.ROOT/'PROCESS.json'), ('notifier', STATE/'PROCESS.json')]:
        process = q.read(path)
        require(q.live(process), 'existing CPU service not alive: '+name)
        services[name] = dict(process=process, alive=True)
    quota_heart = q.read(q.ROOT/'HEARTBEAT.json')
    require(quota_heart['continuations'] == [] and quota_heart['LLM_required'] is False,
            'unexpected quota continuation')

    # Reconcile only the dead companion's stale heartbeat. Keep the terminal
    # RESULT and all scientific publications byte-for-byte unchanged.
    source = WORK/'supervisor.py'
    compile(source.read_text(), str(source), 'exec')
    before = q.read(FIX/'HEARTBEAT.before.json')
    require(before['status'] == 'monitoring' and before['process'] == owner,
            'heartbeat pre-repair evidence')
    if not (FIX/'RESULT.json').exists():
        require(q.sha(ROOT/'HEARTBEAT.json') == q.sha(FIX/'HEARTBEAT.before.json'),
                'heartbeat changed since backup')
        heartbeat = dict(before, utc=q.utc(), status='terminal',
                         terminal_status=result['status'], result=str(ROOT/'RESULT.json'),
                         last_monitoring_utc=before['utc'], terminal_result_utc=result['utc'],
                         reconciled_by_event=EVENT, original_process_exited=True)
        q.atomic_json(ROOT/'HEARTBEAT.json', heartbeat)
        q.new_json(FIX/'RESULT.json', dict(
            utc=q.utc(), status='CPU_terminal_heartbeat_reconciled',
            cause='Supervisor wrote RESULT then exited without updating monitoring heartbeat',
            code_before=q.ref(FIX/'supervisor.before.py'), code_after=q.ref(source),
            heartbeat_before=q.ref(FIX/'HEARTBEAT.before.json'),
            heartbeat_after=q.ref(ROOT/'HEARTBEAT.json'),
            original_RESULT=result_ref, original_RESULT_unchanged=True,
            code_syntax_checked=True, service_restarted=False,
            new_GPU_calls=0, scientific_launches=0, signals_sent=0))
    q.verify(result_ref)
    require(q.read(ROOT/'HEARTBEAT.json')['status'] == 'terminal', 'heartbeat repair')
    for row in queues:
        q.verify(row['claim']); q.verify(row['result'])

    audit = dict(
        utc=q.utc(), status='audited_complete', task_id=TASK, event_id=EVENT,
        CPU_only=True, authorization=q.ref(q.policy.AUTH), event=q.ref(event_path),
        claim=q.ref(ROOT/'CLAIM.json'), process=owner, terminal=result_ref,
        initial_handler_ACK=initial_ack, process_exit=q.ref(host_path),
        claim_preserved=True, control_service_family_exited=True,
        issues=[dict(issue=q.ref(issue_path), status=issue['status'],
                     response_deadline_seconds=1800,
                     original_reported_at=issue['reported_at'],
                     original_response_due_at=issue['analysis_response_due_at'],
                     resolved_at=issue['resolved_at'], deadline_reset=False,
                     delivery=q.ref(transport_path), outbox=q.ref(outbox),
                     analysis_delivery_succeeded=False, analysis_handler_ACK=False,
                     issue_resolved_independently=True, retries_in_this_audit=0)],
        Post_compatibility=dict(
            real_CPU_repairs=q.ref(ROOT/'CPU_METADATA_RECOVERY_VERIFIED.json'),
            selection_rule=q.ref(C/'deadline_20260924/POST_LED_SELECTION_OVERRIDE_V1.json'),
            runtime_compatibility=q.ref(C/'deadline_20260924/AUTORUN_LIVE_CHAIN_COMPATIBILITY_V1.json'),
            selected_loss='L01', fixed_fit_seed=9101, selections=selections,
            transfer=q.ref(q.P/'TRANSFER_CONSUMED.json'), original_waiters_preserved=True),
        scientific_queues=queues, scientific_terminal_total=3000,
        scientific_attempt_counters=dict(X=1000, Pi05=2000, node=14943),
        actual_scientific_failure_recovery_tested=False,
        historical_CPU_checks=q.ref(ROOT/'CPU_CHECK.json'),
        CPU_check_scope='Existing isolated fixtures; not live scientific-worker recovery',
        healthy_CPU_services_preserved=services,
        quota_heartbeat_at_audit=quota_heart,
        occupancy=dict(cached_guard=guard, actual_holder_managers=holders,
                       probe='CPU /proc and existing guard cache only',
                       new_GPU_queries=0, measured_current_SM=None),
        CPU_repair=q.ref(FIX/'RESULT.json'),
        new_GPU_calls=0, new_scientific_compute=0, new_training_updates=0,
        completed_source_replays=0, queue_processes_signalled=0,
        service_restarts=0, new_notification_events=0, recursive_wakeup=False,
        limitation='Analysis issue delivery failed (target rollout absent); outbox retained. '
                   'The dependency issue resolved independently; no analysis ACK or '
                   'unattended scientific-worker fault recovery is claimed.')
    q.new_json(AUDIT, audit)
    summary = ROOT/'TERMINAL_AUDIT.md'
    summary.write_text(
        '# C CPU 自主恢复监督任务终局审计\n\n'
        f'事件 `{EVENT}` 已审计；唯一 claim、注册事件与终局 RESULT 一致。'
        '控制服务及原 X / π0.5 正式进程族已退出。\n\n'
        'X 的 1000 条、π0.5 的 2000 条合法终局沿用既有审计，剩余 0；'
        '本轮未重跑、重训或调用 GPU。原 claim、科学 RESULT 和额度保持不变。\n\n'
        '唯一 issue 的原始时限为 1800 秒，17:37:05 UTC 因依赖就绪解除，'
        '早于 18:03:34 UTC 截止。向指定分析线程的一次投递失败（目标 rollout 不存在），'
        'outbox 保留；没有分析 ACK，也未以投递失败阻塞队列或重置计时。\n\n'
        'Post-only L01 / fit9101 选择、原 X 等待器兼容和 π0.5 精确所有权消费证据有效；'
        '两项真实 CPU 元数据修复已被原队列消费。未测试真实科学 worker 故障恢复。\n\n'
        '修复了服务退出后残留 monitoring 心跳，并补齐私有监督代码的终局心跳写入；'
        '保留原代码及心跳，语法检查通过，没有重启服务。\n\n'
        '后续 quota CPU 监督器与通知服务继续运行。缓存及 /proc 确认八卡 holder 管理进程存活；'
        '本轮未测量 SM 利用率。未新增唤醒事件。\n\n'
        f'机器审计：[{AUDIT.name}]({AUDIT})\n')
    receipt = C/'receipts/C'/('C_D24_AUTORECOVERY_QUEUE_RULE_V1_TERMINAL_AUDIT_r1.json')
    q.new_json(receipt, dict(utc=q.utc(), task_id=TASK, event_id=EVENT,
                            status='audited_complete', audit=q.ref(AUDIT), summary=q.ref(summary),
                            new_GPU_calls=0, new_scientific_compute=0, recursive_wakeup=False))
    print(json.dumps(dict(status='audited_complete', audit=str(AUDIT),
                         summary=str(summary), GPU_calls=0, scientific_replays=0)))


if __name__ == '__main__':
    main()
