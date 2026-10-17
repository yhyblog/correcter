"""CPU-only reconciliation of the already exited, single graphics attempt."""
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORK = Path(__file__).resolve().parent
TASK = 'A10_EGL_GRAPHICS_PROBE_V1'
RUN = BASE / 'results/A/EGL_graphics_runs/A10_EGL_GRAPHICS_PROBE_V1_r1_A_wave02'
PUB = BASE / 'results/A/A10_EGL_CPU_REPAIR_V1'
RECEIPTS = BASE / 'receipts/A'
CLAIM = RUN.parent / 'release_claims/P10_A_EGL_GRAPHICS_PROBE_V1.json'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(path):
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def publish(path, obj, *, text=False, replace=False):
    if not replace and path.exists():
        raise RuntimeError(f'Existing evidence is immutable: {path}')
    tmp = path.with_name(path.name + '.pending')
    with tmp.open('x') as stream:
        stream.write(obj if text else json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


now = datetime.datetime.now(datetime.timezone.utc).isoformat()
ack = read(RECEIPTS / f'{TASK}_ACK.json')
release = read(WORK / 'inputs/releases/P10_A_EGL_GRAPHICS_PROBE_V1.json')
launch = read(RUN / 'LAUNCH_RESULT.json')
runtime = read(RUN / 'graphics/RESULT.json')
mapping = read(RUN / 'graphics/device_mapping.json')
cleanup = read(RUN / 'graphics/cleanup.json')
process = read(WORK / 'PROCESS.json')
exited = read(WORK / 'COMMAND_EXIT.json')
actual_identity = read(RUN / 'launch_identity.json')
snapshot = read(WORK / 'POST_EXIT_DEVICE_AND_PROCESS_SNAPSHOT.json')
cap = release['resource_caps']
events = [json.loads(row) for row in (RUN / 'graphics/events.jsonl').read_text().splitlines()]
by_id = collections.defaultdict(list)
for row in events:
    by_id[row['event_id']].append(row)
counts = {key: dict(planned=value, entered=0, returned=0, failed=0, incomplete=0)
          for key, value in cap.items()}
assert len(by_id) == 30 and len(events) == 60
assert all(a['monotonic_ns'] <= b['monotonic_ns'] for a, b in zip(events, events[1:]))
for event_id, rows in by_id.items():
    entered = [r for r in rows if r['phase'] == 'entered']
    terminal = [r for r in rows if r['phase'] in ('returned', 'failed')]
    assert len(entered) == 1 and len(terminal) <= 1
    op = entered[0]['operation']
    assert op in cap and rows[0]['phase'] == 'entered'
    assert all(r['operation'] == op and r['resource_units'] == {op: 1} for r in rows)
    counts[op]['entered'] += 1
    counts[op][terminal[0]['phase'] if terminal else 'incomplete'] += 1
actual = {key: value['entered'] for key, value in counts.items()}
assert all(0 <= actual[key] <= cap[key] for key in cap)
assert actual == launch['resources']['entered_budget_usage'] == runtime['resources']['entered_budget_usage']
phase_totals = {phase: sum(row[phase] for row in counts.values())
                for phase in ('entered', 'returned', 'failed', 'incomplete')}
assert phase_totals == dict(entered=30, returned=29, failed=1, incomplete=0)
assert runtime['status'] == launch['status'] == 'failed'
assert launch['returncode'] == exited['returncode'] == 1
assert exited['launcher_invocations'] == process['launcher_invocations'] == 1
assert read(CLAIM)['run_id'] == release['run_id']
assert read(CLAIM)['release_sha256'] == sha(WORK / 'inputs/releases/P10_A_EGL_GRAPHICS_PROBE_V1.json')
assert len(mapping['devices']) == 8
assert all(r['mapping'] is None and not r['mapping_evidence'] and not r['mapping_errors']
           for r in mapping['devices'])
assert cleanup['errors'] == []
assert all(not (RUN / 'graphics' / name).exists() for name in ('rgb.npy', 'rgb.ppm', 'renderer_identity.json'))
assert snapshot['launch_pid_current'] is None and snapshot['matching_processes'] == []
assert actual_identity['actual_gpu'] == {key: release[key] for key in
    ('gpu_uuid', 'gpu_index', 'gpu_model', 'driver', 'pci_bus_id')}
checked_inputs = []
for entry in ack['inputs_checked']:
    path = Path(entry.get('frozen_copy', entry['path']))
    assert sha(path) == entry['sha256'], path
    checked_inputs.append(identity(path))
assert sha(PUB / 'EXTERNAL_SOURCE_MANIFEST.json') == release['external_source_manifest_sha256']

timing_rows = [json.loads(row) for row in (RUN / 'wave_timing.jsonl').read_text().splitlines()]
timing = {row['phase']: row for row in timing_rows}
start = timing['timed_process_started']['monotonic_seconds']
stop = timing['timed_process_exited']['monotonic_seconds']
samples = [json.loads(row) for row in (WORK / 'GPU_OBSERVATIONS.jsonl').read_text().splitlines()]
inside = [s for s in samples if start <= s['query_started_monotonic_seconds'] <= s['monotonic_seconds'] <= stop]
assert len(inside) == 14 and all(s['query_returncode'] == 0 for s in inside)
gpu_peaks = {str(i): {'NVML_memory_used_MiB': 0, 'sampled_utilization_percent': 0} for i in range(8)}
for sample in inside:
    rows = [line.split(',') for line in sample['stdout'].splitlines()]
    assert {int(row[0]) for row in rows} == set(range(8))
    for row in rows:
        index, memory, utilization = map(int, row)
        gpu_peaks[str(index)]['NVML_memory_used_MiB'] = max(gpu_peaks[str(index)]['NVML_memory_used_MiB'], memory)
        gpu_peaks[str(index)]['sampled_utilization_percent'] = max(gpu_peaks[str(index)]['sampled_utilization_percent'], utilization)
before = read(WORK / 'OCCUPANCY_BEFORE.json')
after = read(WORK / 'OCCUPANCY_AFTER.json')
assert before['returncode'] == after['returncode'] == 0
guard_after, _ = json.JSONDecoder().raw_decode(after['stdout'][after['stdout'].index('{'):])
assert len(guard_after['gpus']) == 8 and all(g['state'] == 'holder' for g in guard_after['gpus'].values())
assert launch['restoration']['status'] == 'occupancy_resolved'
run_files = [p for p in sorted(RUN.rglob('*')) if p.is_file()]
run_bytes = sum(p.stat().st_size for p in run_files)
memory = {
    'child_family_maxrss_KiB': exited['child_rusage_maxrss_KiB'],
    'child_family_maxrss_MiB': exited['child_rusage_maxrss_KiB'] / 1024,
    'RAM_scope': 'Linux RUSAGE_CHILDREN maximum per-child RSS, including launcher, graphics descendant and read-only observer subprocesses; not simultaneous aggregate RAM or graphics-only RSS',
    'timed_process_NVML_sample_count': len(inside),
    'all_observer_NVML_sample_count': len(samples),
    'GPU_sample_interval_rule': 'query start and query end both inside timed child; excludes holder release and restoration',
    'GPU_sampled_peaks_by_physical_index': gpu_peaks,
    'GPU_allocator_peak_bytes': None,
    'GPU_allocator_peak_missing_reason': 'No allocator/event instrumentation; rounded NVML samples can miss short allocations',
    'gpu_seconds': None,
    'GPU_seconds_missing_reason': 'No GPU event timing or utilization integral; zero sampled memory/utilization is not proof of zero GPU work',
    'runtime_output_bytes': run_bytes,
    'runtime_output_scope': 'All regular files in the new immutable run directory; excludes pre-existing bundle and CPU audit/observer evidence',
}
audit = {
    'task_id': TASK, 'audited_at_utc': now, 'audit_mode': 'stdlib CPU reconciliation only; no graphics calls or command rerun',
    'command_invocations': 1, 'retries': 0, 'command_returncode': 1,
    'runtime_status': 'failed', 'failure_stage': 'physical EGL device mapping before getPlatformDisplay/initialize',
    'error': runtime['error'], 'phase_totals': phase_totals, 'planned_vs_actual': counts,
    'billing': 'Only entered charges; terminal resource_units repeat metadata and add zero. All 30 events have one terminal.',
    'zero_cap_dimensions_remained_zero': True, 'all_caps_respected': True,
    'device': actual_identity['actual_gpu'], 'enumerated_EGL_devices': 8, 'selected_EGL_index': None,
    'DRM_query_interpretation': '24 returned calls = 8 extension + 16 DRM strings. All 16 DRM calls yielded no usable path by source/data inference; raw NULL versus empty was not recorded, and no eglGetError was authorized/called.',
    'EGL_index_to_physical_GPU_mapping': 'unresolved; never assume EGL 0 equals physical GPU 0',
    'graphics_outputs': {name: {'value': None, 'missing_reason': 'Mapping guard stopped before display/context/render'}
                         for name in ('GL_vendor', 'GL_renderer', 'GL_version', 'RGB_shape', 'RGB_dtype', 'RGB_sha256')},
    'cleanup': cleanup, 'timing': launch['timing'], 'memory_and_disk': memory,
    'occupancy': {'launcher_restoration': launch['restoration'], 'fresh_status': identity(WORK / 'OCCUPANCY_AFTER.json'),
                  'fresh_holder_count': 8, 'guard_pid': guard_after['pid'],
                  'holder_manager_pids': [g['manager_pid'] for g in guard_after['gpus'].values()],
                  'during_timed_child': '14 complete all-GPU NVML samples show 0 MiB and 0 percent on all eight; internal formal reservation spans child exit',
                  'post_exit_process_snapshot': identity(WORK / 'POST_EXIT_DEVICE_AND_PROCESS_SNAPSHOT.json'),
                  'launcher_pid_absent': True, 'matching_probe_processes': []},
    'input_small_artifact_SHA_checks': checked_inputs,
    'identity_check_scope': 'Frozen launcher performed full bundle/external-source checks; this audit rechecks small identities and outputs only; no standalone checker or weight hash',
    'run_artifacts': [identity(p) for p in run_files],
    'release_consumed': True, 'release_closure_owner': 'analysis', 'no_remaining_budget_reuse': True,
    'old_native_release_reused': False, 'v5_native_executed': False, 'B_participated': False,
    'deleted_files': 0, 'shared_library_or_device_changes': 0,
}
publish(WORK / 'FINAL_AUDIT.json', audit)
tsv = 'resource\tplanned_cap\tentered\treturned\tfailed\tincomplete\n'
tsv += ''.join(key + '\t' + '\t'.join(str(row[p]) for p in ('planned','entered','returned','failed','incomplete')) + '\n'
               for key, row in counts.items())
publish(WORK / 'COUNTS.tsv', tsv, text=True)
repair = '''已证实：隔离 EGL 入口可枚举 8 个设备；所有设备的 DRM 路径映射为空，容器 /dev/dri 不存在。目标 PCI/内核 UUID/NVML 三者一致，sysfs 的 card1 和 renderD128 指向该物理卡。当前证据不足以断言 EGL context 本身不能运行，也不足以要求重建容器。

原实现未保存 DRM 查询原始 NULL/空串，也未查询 EGL error；报告只断言“无可用路径”。后续 CPU 修订宜保留 token、原始空值类别及失败阶段，新增查询必须明确计费。

供分析端决定的优先候选：CPU 审查 EGL_EXT_device_persistent_id 路线。8 个已枚举设备均宣告此扩展。规范提供 eglQueryDeviceBinaryEXT(EGL_DEVICE_UUID_EXT, 16-byte buffer)；固定长度无需再做长度探测。按目标 UUID 字节与已核对的内核/NVML PCI 身份做唯一匹配；结合 driver identity 消歧，拒绝任何零匹配、多匹配或不一致。不能把扩展声明当作实际 UUID 已验证，也不能假定 NVIDIA 字符串与二进制对应而跳过核对。此路线本轮未实现、未调用；如采纳，须另发 CPU 修订及带显式 binary-query/driver-query caps 的新 graphics release。
[Khronos persistent-id 规范](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_device_persistent_id.txt)

替代候选：如分析端坚持 DRM 路线，由平台先确认主机目标 /dev/dri/card1、/dev/dri/renderD128 的 PCI、字符设备 major/minor 与权限，再决定精确挂载与设备 cgroup 放行。容器缺节点是事实，但尚不能证明单独补节点必能恢复查询或 context；不自行 mknod、不改共享驱动、不重启容器。EGL DRM 扩展允许设备无关联节点时返回 NULL，不能仅凭宣告扩展推断一定可得路径。
[Khronos DRM render-node 规范](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_device_drm_render_node.txt)

以上仅为修复建议，未改变本次冻结 bundle/命令/设备/库；一次 release 已消耗，未执行第二次查询、枚举或渲染。
'''
publish(WORK / 'REPAIR_OPTIONS.md', repair, text=True)
report_path = RECEIPTS / f'{TASK}_REPORT.md'
report = f'''| 项目 | 可用 / 缺口 |
|---|---|
| 一次真实执行 | 已完成，技术失败，rc=1；release 已消耗，待分析端关闭 |
| 固定物理设备 | GPU 0 / `{release['gpu_uuid']}` / PCI `{release['pci_bus_id']}` / driver {release['driver']}，入口核对一致 |
| EGL 映射 | 1 次枚举返回 8 设备；8 次扩展 + 16 次 DRM 查询未建立任何物理映射，拒绝进入 display |
| context / RGB | 均未进入；vendor/renderer/version、RGB shape/dtype/hash 为 null，有缺失原因 |
| cleanup / occupancy | releaseThread 1 次成功、cleanup 无错误；进程退出后全 A 8 holder 恢复，18:02:41 UTC 再确认 |

实际命令按任务书执行一次，ACK 在先，入口自带完整身份校验；没有独立 CPU checker、重试、换设备/库/renderer或 B 参与。失败不是 episode 任务失败率。

| 资源 | planned cap | entered | returned | failed | incomplete |
|---|---:|---:|---:|---:|---:|
| graphics attempt | 1 | 1 | 0 | 1 | 0 |
| EGL enumeration | 1 | 1 | 1 | 0 | 0 |
| device string query | 48 | 24 | 24 | 0 | 0 |
| explicit getProcAddress | 4 | 3 | 3 | 0 | 0 |
| releaseThread | 1 | 1 | 1 | 0 | 0 |
| display / initialize / EGL context / render / RGB（各） | 1 | 0 | 0 | 0 | 0 |
| VLA / MetaWorld / reset / 物理推进 / rollout / 更新（各） | 0 | 0 | 0 | 0 | 0 |

总事件 entered=30、returned=29、failed=1、incomplete=0；terminal 不重复计费，全部 caps 满足。完整查询、清理与零项逐行见 [COUNTS.tsv]({WORK / 'COUNTS.tsv'})。没有 native reset 返回或完整观测返回。

墙钟：准备 5.410 s；预约/停止 holders 66.293 s；wrapper 0.005 s；定时子进程 5.841 s；释放 0.018 s；恢复观察 21.007 s；launcher 端到端 98.574 s（外层观察 98.667 s）。未触发 timeout；120+10 s 仅约束子进程，前置与恢复另计。

实测 RAM 最大单个子进程 RSS 47.523 MiB（含 observer 子命令，不是并发 RAM 总和）。定时区间 14 次完整 NVML 采样，8 卡 sampled memory peak 均 0 MiB、utilization 均 0%；采样可能漏短时分配，allocator peak 与 GPU-seconds 未知，写 null。run 产物 {run_bytes} bytes；估计上限不冒充实测。

容器 `/dev/dri` 缺失，而 sysfs card1/renderD128→PCI→内核 UUID 与目标一致。当前 DRM 返回的 NULL/空串没有分开记录；只断言“无可用路径”，不推断 context 不可运行。建议分析端先决定 CPU 审查已宣告的 persistent-device UUID 映射路线；或核对主机节点后决定精确挂载。依据、限制及另一方案见 [REPAIR_OPTIONS.md]({WORK / 'REPAIR_OPTIONS.md'})，本轮不实施。

证据：[runtime RESULT]({RUN / 'graphics/RESULT.json'})、[device_mapping]({RUN / 'graphics/device_mapping.json'})、[LAUNCH_RESULT]({RUN / 'LAUNCH_RESULT.json'})、[FINAL_AUDIT]({WORK / 'FINAL_AUDIT.json'})、[holder 恢复]({WORK / 'OCCUPANCY_AFTER.json'})；完整 SHA 见 [manifest]({WORK / 'FINAL_ARTIFACT_MANIFEST.json'})。

请分析端关闭 `P10_A_EGL_GRAPHICS_PROBE_V1`，剩余未进入额度不复用。旧 native release 保持关闭，v5 未执行。全部新产物保留，无删除、共享库修改或容器重启；等待下一任务。
'''
publish(report_path, report, text=True)
publish(RECEIPTS / f'{TASK}_HEARTBEAT.json', {
    'task_id': TASK, 'status': 'failed_command_audit_complete', 'updated_at_utc': now,
    'launcher_invocations': 1, 'returncode': 1, 'phase_totals': phase_totals,
    'actual_resource_counts': actual, 'holder_count_restored': 8, 'release_consumed': True,
    'result_path': str(RECEIPTS / f'{TASK}_RESULT.json')}, replace=True)
inventory = {
    'task_id': TASK, 'created_at_utc': now, 'retention_decision': 'keep pending analysis; no delete authority',
    'created_roots': [str(WORK), str(RUN)], 'created_singletons': [str(CLAIM)],
    'receipt_prefix': str(RECEIPTS / TASK),
    'receipt_files': [str(RECEIPTS / f'{TASK}_{suffix}') for suffix in
                      ('ACK.json','HEARTBEAT.json','REPORT.md','RESULT.json','QUEUE_MESSAGE.txt','QUEUE.json')],
    'delete_candidates_submitted': [], 'actual_deletions': 0,
    'note': 'Retain CPU snapshots, logs, scripts, manifests, failed runtime, receipt and queue artifacts; no cleanup executed',
}
publish(WORK / 'NEW_ARTIFACTS_INVENTORY.json', inventory)
files = {p for root in (WORK, RUN) for p in root.rglob('*') if p.is_file()}
files.update([CLAIM, RECEIPTS / f'{TASK}_ACK.json', RECEIPTS / f'{TASK}_HEARTBEAT.json', report_path])
manifest = {'task_id': TASK, 'created_at_utc': now,
    'scope': 'Complete runtime/claim/CPU observer/audit/source snapshots/report/ACK/final heartbeat; manifest self and final RESULT excluded to avoid cycles; later queue receipt retained separately',
    'files': [identity(p) for p in sorted(files)]}
manifest['file_count'] = len(manifest['files'])
manifest['total_file_bytes'] = sum(p['bytes'] for p in manifest['files'])
publish(WORK / 'FINAL_ARTIFACT_MANIFEST.json', manifest)
result = {
    'campaign_id': release['campaign_id'], 'task_id': TASK, 'revision': 1, 'role': 'A',
    'hostname': ack['hostname'], 'session_id': ack['executor_session_id'], 'status': 'failed',
    'started_at_utc': ack['started_at_utc'], 'finished_at_utc': now,
    'release_id': release['release_id'], 'run_id': release['run_id'],
    'wave_id': release['wave_id'], 'shard_id': release['shard_id'],
    'input_identity': {
        'protocol': [identity(WORK / 'inputs' / rel) for rel in
                     ('CONTROL.json','TASK_BOARD.json','tasks/A10_EGL_GRAPHICS_PROBE_V1.md',
                      'releases/P10_A_EGL_GRAPHICS_PROBE_V1.json','contracts/REPORT_CONTRACT.md')],
        'code': [identity(PUB / name) for name in ('BUNDLE_MANIFEST.json','EXTERNAL_SOURCE_MANIFEST.json','commands/run_proposed_graphics_probe.sh')],
        'config': identity(PUB / 'proposal/PROPOSAL.json'),
        'data': {'path': None, 'sha256': None, 'reason': 'No dataset read; static scene construction was not reached'},
        'model': {'path': None, 'sha256': None, 'reason': 'No policy model initialization or weight read authorized/executed'},
        'verification_scope': audit['identity_check_scope'],
    },
    'artifacts': {key: identity(path) for key, path in {
        'short_report': report_path, 'complete_manifest': WORK / 'FINAL_ARTIFACT_MANIFEST.json',
        'audit': WORK / 'FINAL_AUDIT.json', 'counts_table': WORK / 'COUNTS.tsv',
        'runtime_result': RUN / 'graphics/RESULT.json', 'LAUNCH_RESULT': RUN / 'LAUNCH_RESULT.json',
        'device_mapping': RUN / 'graphics/device_mapping.json', 'cleanup': RUN / 'graphics/cleanup.json',
        'events': RUN / 'graphics/events.jsonl', 'command_log': WORK / 'command.log',
        'command_exit': WORK / 'COMMAND_EXIT.json', 'occupancy_after': WORK / 'OCCUPANCY_AFTER.json',
        'repair_options': WORK / 'REPAIR_OPTIONS.md', 'retention_inventory': WORK / 'NEW_ARTIFACTS_INVENTORY.json',
    }.items()},
    'resource_counts': {**actual, 'gpu_seconds': None},
    'GPU_seconds_missing_reason': memory['GPU_seconds_missing_reason'],
    'planned_vs_actual': counts, 'phase_totals': phase_totals,
    'timing': launch['timing'], 'memory_and_disk': memory,
    'outcome': {'type': 'technical_failure', 'failure_stage': audit['failure_stage'],
                'episode_success_rate': None, 'episode_failure_rate': None,
                'selected_EGL_index': None, 'enumerated_devices': 8,
                'fixed_physical_device': actual_identity['actual_gpu'],
                'RGB': None, 'renderer_identity': None,
                'missing_reason': 'Physical mapping guard stopped before display/context/render; no task episodes attempted'},
    'failures_and_retries': [{'command': process['command'], 'cwd': str(PUB), 'exit_code': 1,
        'error_type': runtime['error']['error_type'], 'error': runtime['error']['error'],
        'retries': 0, 'failure_charged': True, 'recovery': 'cleanup releaseThread returned; integrated lifecycle released after child exit; all 8 holders restored'}],
    'findings': [
        'Exactly one frozen real command ran after ACK and exclusive release claim; no standalone checker or rerun.',
        'NVML and kernel PCI/UUID match the fixed target; no EGL index was selected or assumed from CUDA ordinals.',
        'One EGL enumeration returned 8 devices; 24 string queries comprised 8 extension and 16 DRM requests, none supplying a usable mapping.',
        'Mapping guard raised Refused before any platform display, initialize, EGL context, static scene, render or readback.',
        '30 entered events reconcile to 29 returned, 1 failed, 0 incomplete; every dimension remains within its cap.',
        'VLA, MetaWorld, reset, physics advancement, policy step, rollout and training counts are all 0.',
        'Cleanup completed without errors; process family exited and all 8 A holders restored; fresh status confirms restoration.',
        'Sampled memory and timing are reported with observation scope; actual allocator peak and GPU-seconds remain unknown.',
        'Missing DRM nodes are confirmed; persistent-device UUID or verified node exposure are repair candidates only, subject to analysis decision and new release.',
        'Old native release was not reused; v5/B were not run; no artifacts, data, weights or shared libraries were deleted/modified.',
    ],
    'blockers': [{'gap': 'EGL handle to fixed physical UUID mapping unavailable through current DRM strings',
                  'impact': 'Cannot safely initialize the authorized display/context',
                  'proposed_resolution': 'Analysis decides CPU review of persistent-device UUID mapping or host-verified DRM node exposure; no further graphics work under consumed release',
                  'evidence': str(WORK / 'REPAIR_OPTIONS.md')}],
    'next_task_proposal': {'owner': 'analysis', 'action': 'Close consumed P10_A_EGL_GRAPHICS_PROBE_V1 and decide a separate bounded CPU mapping repair task; any future graphics/native command requires its own release',
                           'automatically_started': False},
    'release_consumed': True, 'analysis_close_requested': True,
    'all_new_artifacts_retained': True, 'deleted_files': 0,
}
assert len(result['findings']) <= 10
publish(RECEIPTS / f'{TASK}_RESULT.json', result)
print(json.dumps({'result': identity(RECEIPTS / f'{TASK}_RESULT.json'),
                  'audit': identity(WORK / 'FINAL_AUDIT.json'),
                  'manifest': identity(WORK / 'FINAL_ARTIFACT_MANIFEST.json'),
                  'phase_totals': phase_totals, 'memory': memory}, ensure_ascii=False))
