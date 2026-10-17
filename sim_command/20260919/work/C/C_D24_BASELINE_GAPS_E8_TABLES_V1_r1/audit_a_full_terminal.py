"""CPU-only audit and dependency-table correction for the existing E8 callback."""
import ast
import csv
import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import time

import a_full_publication

C = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R = C / 'results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1'
W = Path(__file__).resolve().parent
EID = 'C_1f806df15871b1592af76f8329f91c0a'
OUT = R / 'event_audits' / EID
HOST = socket.gethostname()
BOOT = Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def read(path):
    return json.loads(Path(path).read_text())


def ref(path):
    path = Path(path)
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                size_bytes=path.stat().st_size)


def write(path, value):
    path = Path(path)
    temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    temp.write_text(text)
    os.replace(temp, path)


def process(pid):
    try:
        root = Path('/proc') / str(pid)
        fields = (root / 'stat').read_text().rsplit(') ', 1)[1].split()
        return dict(hostname=HOST, boot_id=BOOT, pid=int(pid), state=fields[0],
                    ppid=int(fields[1]), pgid=int(fields[2]), session_id=int(fields[3]),
                    start_ticks=int(fields[19]),
                    argv=(root / 'cmdline').read_bytes().decode(errors='replace').split('\0')[:-1])
    except (FileNotFoundError, ProcessLookupError):
        return None


def alive(expected):
    actual = process(expected['pid'])
    return bool(actual and actual['state'] != 'Z' and all(
        actual[k] == expected[k] for k in ('hostname', 'boot_id', 'pid', 'start_ticks')))


def main():
    if (OUT / 'AUDIT.json').exists():
        print(json.dumps(dict(status='existing_audit_no_repeat', audit=str(OUT / 'AUDIT.json'))))
        return
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    event_path = C / 'persistent_queue/nodes/C/wakeup/outbox' / (EID + '.json')
    event = read(event_path)
    node = read(C / 'nodes/C/identity.json')
    assert HOST == node['hostname'] == event['hostname'] and BOOT == node['boot_id']
    assert event['event_id'] == EID and event['synthetic'] is False
    assert event['job']['task_id'] == 'C_D24_BASELINE_GAPS_E8_TABLES_V1'
    claim_ref = event['job']['claim_identity']
    assert ref(claim_ref['path'])['sha256'] == claim_ref['sha256']
    claim = read(claim_ref['path'])
    assert claim['scientific_launches'] == 0 and claim['maximum_registrations'] == 1
    assert claim['process'] == event['job']['process_identity']
    registration = C / 'persistent_queue/nodes/C/wakeup/jobs/C_E8_A_FULL_APPEND_V1.json'
    assert read(registration)['claim_identity'] == claim_ref
    assert read(event['job']['result_path']) == event['result']
    assert event['result']['scientific_launches'] == 0
    assert not alive(claim['process'])

    old_audit = read(R / 'FINAL_AUDIT.json')
    gap = read(R / 'N_GAP_DISPOSITION.json')
    units = sorted((R / 'unit_claims').glob('*.json'))
    assert len(units) == len(list((R / 'claims').glob('*.json'))) == 5
    unit_records = [read(p) for p in units]
    claimed_sources = [x['source']['source_id'] for x in unit_records]
    assert len(set(claimed_sources)) == 5
    assert all(x['C_attempt'] == 1 and x['attempt'] == 2 and x['method'] == 'N' for x in unit_records)
    terminals, unknown = [], []
    for row in gap['entries']:
        source = row['source']
        if row['disposition'] == 'unknown_do_not_replay':
            assert row['C_attempts'] == 0 and row['current_success'] is None
            assert source['source_id'] not in claimed_sources
            unknown.append(source)
            continue
        assert row['C_attempts'] == 1 and row['retry_opportunities_remaining'] == 0
        result = read(row['C_result'])
        assert result['status'] == 'complete' and type(result['success']) is bool
        assert result['source_id'] == source['source_id'] in claimed_sources
        assert result['success'] == row['current_success']
        assert all(result[k] == source[k] for k in ('reset_seed', 'policy_seed'))
        terminals.append(dict(source=source, status=result['status'], success=result['success'],
                              result=ref(row['C_result']), C_attempts=1))
    assert len(terminals) == len(unknown) == 5
    velocity_root = C / 'results/C/C_D24_MW_VELOCITY_V1'
    velocity_claims = {}
    for name, expected in [('unit_claims', 1000), ('unit_retry_claims', 8)]:
        names = sorted(str(p.relative_to(velocity_root)) for p in (velocity_root / name).rglob('*.json'))
        assert len(names) == expected
        velocity_claims[name] = dict(count=len(names), relative_path_list_sha256=hashlib.sha256(
            '\n'.join(names).encode()).hexdigest())

    processes = {int(p.name): process(int(p.name)) for p in Path('/proc').iterdir() if p.name.isdigit()}
    processes = {pid: p for pid, p in processes.items() if p}
    formal = [dict(record, alive_now=alive(record['identity']))
              for record in old_audit['formal_process_identities']]
    assert len(formal) == 17 and not any(x['alive_now'] for x in formal)
    groups = {x['identity']['session_id'] for x in formal} | {claim['process']['session_id']}
    remaining = [p for p in processes.values() if p['state'] != 'Z'
                 and (p['session_id'] in groups or p['pgid'] in groups)]
    assert not remaining
    guard_path = Path('/tmp/gpu_occupancy_guard/status.json')
    guard = read(guard_path)
    age = time.time() - guard['updated']
    assert 0 <= age < 30 and set(guard['gpus']) == {str(i) for i in range(8)}
    guard_process = process(guard['pid'])
    assert guard_process and guard_process['state'] != 'Z'
    holders = []
    for gpu, state in sorted(guard['gpus'].items()):
        manager = process(state['manager_pid'])
        assert state['state'] == 'holder' and manager and manager['state'] != 'Z'
        assert manager['ppid'] == guard['pid'] and state['driver_pids']
        args = manager['argv']
        assert args[args.index('--devices') + 1] == gpu
        duty = float(args[args.index('--target-util') + 1])
        descendants = [p for p in processes.values() if p['pid'] != manager['pid']
                       and p['session_id'] == manager['session_id'] and p['state'] != 'Z']
        assert descendants
        gpu_uuid = next(x['uuid'] for x in node['gpus'] if x['index'] == gpu)
        holders.append(dict(gpu=gpu, gpu_uuid=gpu_uuid, manager=manager,
                            descendants=descendants, target_duty=duty,
                            cached_driver_pids=state['driver_pids']))
    live = dict(utc=now, hostname=HOST, boot_id=BOOT, watcher_exited=True,
                formal_identities=formal, remaining_formal_group=remaining,
                cached_guard=guard, cached_guard_age_seconds=age, guard_process=guard_process,
                holders=holders, all_eight_holder_managers_alive=True,
                new_GPU_probe_calls=0, measured_SM_percent=None,
                duty_is_not_measured_utilization=True)

    a_path, a = a_full_publication.resolve(C)
    a_root = C / 'results/A/A_D24_LIBERO_FULL_NATIVE_V1'
    delivery = read(a_root / 'FINAL_DELIVERY.json')
    fit = read(delivery['artifacts']['FIT_SUMMARY'])
    data = read(delivery['artifacts']['DATA_STATUS'])
    a_receipt = read(delivery['receipt'])
    assert a['status'] == fit['status'] == a_receipt['status'] == 'SCIENTIFIC_GAP'
    assert a['Full_claimed'] is False and fit['optimizer_updates'] == fit['test_attempts'] == 0
    assert len(data['G0_train_targets']) == 7 and len(data['G0_validation_targets']) == 4
    assert set(data['G0_train_targets'] + data['G0_validation_targets']) == {0.0}
    assert a['development_cumulative_attempts'] == a['development_cumulative_cap'] == 200
    a_rows = a_full_publication.rows(a, a_path)
    assert all(row['valid'] == 0 and row['successes'] is None and row['success_rate_pct'] is None
               and row['status'] == 'scientific_gap_Full_unavailable' for row in a_rows)
    assert all(a['phases'][method]['entered'] == 0 for method in ('Full-Post', 'Full-Velocity'))

    # Preserve the original callback, watcher result, claims and scientific tables.
    before = read(OUT / 'BEFORE.json')
    changed = {str(R / x) for x in ('A_FULL_SNAPSHOT.json', 'E8_FULL_NATIVE_TABLE.csv', 'E8_REPORT.md')}
    changed.add(str(W / 'build_tables.py'))
    protected = [x for x in before['files'] if x['path'] not in changed]
    assert all(ref(x['path'])['sha256'] == x['sha256'] for x in protected)
    for name in ('a_full_publication.py', 'build_tables.py', 'audit_a_full_terminal.py'):
        ast.parse((W / name).read_text())
    report = (R / 'E8_REPORT.md').read_text()
    start = report.index('A 的 native Full-LIBERO 独立列在')
    end = report.index('\n\n10 槽处置：', start)
    section = a_full_publication.report_note(a, a_path)
    section += ('\n\nA 的最后一轮为 40 个开发尝试（30 有效、10 技术故障），累计 200/200；'
                '7 个训练与 4 个验证 G0 配对收益均为 0。D/G0/Q 本轮训练更新为 0，'
                'Full-Post/Full-Velocity 测试尝试均为 0。开发结果不作为 Full 测试成功率。'
                'A 发布保留采样 931、flow 9310、特征 4529 次调用及含前序的 24 次模型加载；'
                '这些是 A 的既有开发成本，C 本回调新增科学计算为 0。')
    section += '\n\n| A 原生 Full 单元 | 有效 / 计划 | 状态 |\n|---|---:|---|\n'
    section += '\n'.join(f"| {x['method']} | {x['valid']}/{x['planned']} | {x['status']}（快照 {x['observed_snapshot_status']}） |" for x in a_rows)
    report = report[:start] + section + report[end:]
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(a_rows[0]))
    writer.writeheader()
    writer.writerows(a_rows)
    write(R / 'E8_FULL_NATIVE_TABLE.csv', buffer.getvalue())
    write(R / 'A_FULL_SNAPSHOT.json', a)
    write(R / 'E8_REPORT.md', report)
    assert all(ref(x['path'])['sha256'] == x['sha256'] for x in protected)
    assert len(list(csv.DictReader((R / 'E8_TABLE.csv').open()))) == 21
    assert len(list(csv.DictReader((R / 'E8_PAIRED.csv').open()))) == 21
    assert read(event['job']['result_path']) == event['result']
    input_refs = [ref(p) for p in [a_root / 'FINAL_DELIVERY.json', a_path,
        delivery['artifacts']['DATA_STATUS'], delivery['artifacts']['FIT_SUMMARY'],
        delivery['artifacts']['RESULT'], delivery['receipt'], event_path, registration, claim_ref['path']]]
    resolution = dict(utc=now, status='audited_dependency_scientific_gap', event_id=EID,
        original_watcher_status=event['result']['status'], canonical_A_publication=ref(a_path),
        publication_inputs=input_refs, Full_claimed=False, full_test_attempts=0,
        full_success_rate=None, scientific_gap=a['scientific_gap'],
        cause='Watcher observed stale top-level FINAL_SUMMARY; FINAL_DELIVERY points to launch_r6.',
        fix='Resolve FINAL_DELIVERY for C table publication; ended watcher and scientific work are not restarted.',
        new_scientific_launches=0, new_wakeup_events=0)
    write(R / 'A_FULL_DEPENDENCY/PUBLICATION_RESOLVED.json', resolution)
    write(OUT / 'LIVE_EXIT_AND_OCCUPANCY.json', live)
    write(OUT / 'SOURCE_TERMINALS.json', dict(terminals=terminals, unknown_preserved=unknown,
        unit_claims=[ref(p) for p in units], velocity_claim_inventory=velocity_claims,
        retry_policy='Five eligible N sources already consumed one corrected attempt; no more replay.'))
    output_refs = [ref(R / name) for name in ('E8_FULL_NATIVE_TABLE.csv', 'A_FULL_SNAPSHOT.json', 'E8_REPORT.md', 'A_FULL_DEPENDENCY/PUBLICATION_RESOLVED.json')]
    audit = dict(utc=now, status='passed', task_id=event['job']['task_id'], event_id=EID,
        scope='CPU-only E8 A Full dependency closure', event=ref(event_path),
        original_claim=claim_ref, unique_existing_CPU_registration=True,
        old_scientific_audit=ref(R / 'FINAL_AUDIT.json'), terminal_N_sources=5,
        unknown_sources_preserved=5, original_Velocity_units=1000, original_Velocity_retries=8,
        source_audit=ref(OUT / 'SOURCE_TERMINALS.json'), live_audit=ref(OUT / 'LIVE_EXIT_AND_OCCUPANCY.json'),
        formal_family_exited=True, all_eight_holders_restored=True,
        holder_duty=[x['target_duty'] for x in holders], holder_measured_SM=None,
        dependency_status='SCIENTIFIC_GAP', Full_claimed=False, full_test_attempts=0,
        full_success_rate=None, source_publications=input_refs, outputs=output_refs,
        protected_artifacts_unchanged=protected, baseline_table_rows=21, paired_rows=21,
        code=[ref(W / name) for name in ('a_full_publication.py', 'build_tables.py', 'audit_a_full_terminal.py')],
        original_event_result_and_attempt_history_preserved=True,
        new_scientific_launches=0, new_GPU_calls=0, new_collection=0, new_training_updates=0,
        valid_terminal_replays=0, unknown_replays=0, new_claims=0, new_retries=0,
        new_wakeup_events=0, callback_completion_does_not_emit_event=True)
    write(OUT / 'AUDIT.json', audit)
    write(OUT / 'REPORT.md',
        '本事件是 E8 的 CPU 依赖检查终局，审计通过。已有唯一 claim 和注册匹配，未重启 watcher。\n\n'
        '原检查器只读 A 顶层旧汇总而漏掉 FINAL_DELIVERY 的 launch_r6 发布；现已按正式发布指针修正 C 的 Full 表、快照与报告，并修正 CPU 表格构建器的解析路径。'
        'A 状态 SCIENTIFIC_GAP：7 个训练和 4 个验证 G0 收益目标全为 0；开发累计 200/200，未训练、未进入 Full 测试。'
        'Full-Post 与 Full-Velocity 各有效 0/计划 400，成功率留空，未执行不计为失败。\n\n'
        '5 条 C N 补跑均保留合法终局，每条已用一次修正；其余 5 条未知保持未知。旧 Velocity 1000 个唯一 claim 和 8 个历史修正 claim 数量未变。'
        'E8 主表 21 行、配对表 21 行和原图哈希保持不变；原事件、旧汇总、原始结果与历史成本保留。\n\n'
        'CPU watcher 和 17 个原正式进程身份已退出，原进程组为空。八卡 holder 管理进程及后代存活，使用现有 duty 0.915；未测量 SM，不能把 duty 当实测利用率。'
        '本回调新增 GPU 调用、科学计算、claim、重试和唤醒事件均为 0。\n')
    receipt = C / 'receipts/C/C_D24_BASELINE_GAPS_E8_TABLES_V1_A_FULL_DEPENDENCY_AUDIT_r1.json'
    assert not receipt.exists()
    write(receipt, dict(utc=now, task_id=event['job']['task_id'], event_id=EID,
        status='audited_dependency_scientific_gap', audit=ref(OUT / 'AUDIT.json'),
        report=ref(OUT / 'REPORT.md'), full_table=ref(R / 'E8_FULL_NATIVE_TABLE.csv'),
        new_scientific_launches=0, full_test_attempts=0, full_success_rate=None))
    print(json.dumps(dict(status='passed', audit=str(OUT / 'AUDIT.json'),
                          dependency='SCIENTIFIC_GAP', N_valid=5, unknown=5, holders=8,
                          new_scientific_launches=0)))


if __name__ == '__main__':
    main()
