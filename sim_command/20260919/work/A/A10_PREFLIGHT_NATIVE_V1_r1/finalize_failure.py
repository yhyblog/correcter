"""Read-only reconciliation of the one failed diagnostic; publish its audit last."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORK = Path(__file__).resolve().parent
PUB = BASE / 'results/A/A10_PREFLIGHT_REVISION_R2'
RECEIPTS = BASE / 'receipts/A'
TASK = 'A10_PREFLIGHT_NATIVE_V1'
sys.path.insert(0, str(PUB / 'code_snapshot_v4'))
from core.accounting import summarize
from core.initialization import summarize_initialization
from core.validation import validate


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def ref(path):
    return {'path': str(path), 'sha256': sha(path)}


def publish(path, value, replace=False):
    assert replace or not path.exists(), str(path)
    pending = path.with_name(path.name + '.pending')
    pending.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(pending, path)


release = json.loads((WORK / 'inputs/P10_A_NATIVE_PREFLIGHT_V1.json').read_text())
ack = json.loads((RECEIPTS / f'{TASK}_ACK.json').read_text())
exit_record = json.loads((WORK / 'COMMAND_EXIT.json').read_text())
assert exit_record['returncode'] == 1 and exit_record['launcher_invocations'] == 1
launch_dir = BASE / 'results/A/P10_launcher_runs' / release['run_id']
launch = json.loads((launch_dir / 'LAUNCH_RESULT.json').read_text())
run_dir = Path(json.loads((launch_dir / 'diagnostic_link.json').read_text())['path'])
assert run_dir.is_relative_to(BASE / 'results/A/P10_diagnostic_runs')
events = [json.loads(x) for x in (run_dir / 'events.jsonl').read_text().splitlines()]
init_rows = [json.loads(x) for x in (run_dir / 'initialization_events.jsonl').read_text().splitlines()]
schema = json.loads((BASE / 'results/A/A10/interface_v1/interface.schema.json').read_text())
for row in events:
    validate(row, schema)
ledger = summarize(events)
initialization = summarize_initialization(init_rows, release['initialization_caps'])
raw_receipt = json.loads((run_dir / 'resource_receipt.json').read_text())
failure = json.loads((run_dir / 'failure.json').read_text())
assert ledger == launch['resources']['public_events']
assert initialization == launch['resources']['initialization'] == raw_receipt['initialization_accounting']
assert ledger['counts'] == raw_receipt['counts']
assert ledger['counts']['simulator_attempts'] == 1
assert all(value == 0 for key, value in ledger['counts'].items() if key != 'simulator_attempts')
assert ledger['failed_events'] == 1 and not ledger['incomplete_events']
for key, cap in release['initialization_caps'].items():
    expected = 0 if key.startswith('policy_') else cap
    assert initialization['entered_budget_usage'][key] == expected
    assert initialization['returned_operation_units'][key] == expected
assert not initialization['incomplete_event_ids'] and initialization['failed_events'] == 0
assert failure['error_type'] == 'ImportError' and 'EGL device display' in failure['error']
assert not (run_dir / 'COMPLETE.json').exists()
assert not (run_dir / 'observation_step0.npz').exists()
assert not (run_dir / 'transition.json').exists()
log = (WORK / 'command.log').read_text(errors='replace')
assert 'All keys loaded successfully!' in log
assert 'Warning: Could not load state dict:' not in log
assert 'Missing keys when loading state dict:' not in log
assert 'Unexpected keys when loading state dict:' not in log
assert launch['restoration']['status'] == 'occupancy_resolved'
assert all(x['state'] == 'holder' for x in launch['restoration']['guard_status']['gpus'].values())

marks = {r['phase']: r for r in map(json.loads, (launch_dir / 'wave_timing.jsonl').read_text().splitlines())}
start = marks['timed_process_started']['monotonic_seconds']
end = marks['timed_process_exited']['monotonic_seconds']
samples = [r for r in map(json.loads, (WORK / 'GPU_OBSERVATIONS.jsonl').read_text().splitlines())
           if start <= r['monotonic_seconds'] <= end and r['query_returncode'] == 0]
peaks = {}
for row in samples:
    for line in row['stdout'].splitlines():
        index, memory, utilization = map(int, (s.strip() for s in line.split(',')))
        peaks[index] = max(peaks.get(index, 0), memory)
assert all(peaks[i] == 0 for i in range(1, 8)), peaks
ram_gib = exit_record['child_rusage_maxrss_KiB'] / 1024 ** 2
plan_actual = []
for key, cap in release['resource_caps'].items():
    entered = [r for r in events if r['phase'] == 'entered']
    returned = [r for r in events if r['phase'] == 'returned']
    failed = [r for r in events if r['phase'] == 'failed']
    plan_actual.append({'resource': key, 'planned_cap': cap,
        'entered': sum(r['resource_units'][key] for r in entered),
        'returned': sum(r['resource_units'][key] for r in returned),
        'failed': sum(r['resource_units'][key] for r in failed), 'missing_terminal': 0})
audit = {'status': 'failed_run_reconciled', 'audited_at_utc': now(),
    'public_records_validated': len(events), 'initialization_records_reconciled': len(init_rows),
    'planned_entered_returned_failed': plan_actual, 'initialization': initialization,
    'planned_diagnostic_count': 1, 'entered_diagnostic_count': 1, 'completed_diagnostic_count': 0,
    'technical_failed_diagnostic_count': 1, 'incomplete_event_count': 0,
    'task_success': None, 'task_success_missing_reason': 'Technical render failure before any policy step; no task-success label',
    'checkpoint_loaded_all_keys': True, 'model_call_scope': 'one initialization only; no sampling/inference forward entered',
    'diagnostic_native_reset_returned': 1, 'full_diagnostic_observation_returned': 0,
    'usable_initial_observation_artifacts': 0,
    'raw_receipt_naming_correction': {
        'field': 'resource_receipt.json.diagnostic_initial_states_returned', 'raw_value': 1,
        'actual_meaning': 'Counted successful native diagnostic reset from private counter. Backend.reset_episode failed while formatting/rendering; this is not a successfully returned RGB observation or usable diagnostic artifact.',
        'recommended_future_name': 'diagnostic_native_resets_returned',
        'raw_receipt_changed': False,
    },
    'timing': launch['timing'], 'sampled_NVML_peak_MiB_by_gpu_during_timed_child': peaks,
    'NVML_samples_in_timed_child': len(samples), 'NVML_peak_is_sampled_lower_bound_not_allocator_peak': True,
    'CUDA_allocator_peak_bytes': None, 'CUDA_peak_missing_reason': 'Failure before checks.json; no unreported allocator peak invented',
    'child_family_maxrss_GiB': ram_gib, 'RAM_scope': exit_record['RAM_measurement_scope'],
    'actual_GPU_compute_seconds': None, 'GPU_seconds_missing_reason': 'No device-time events; timed process wall includes CPU/hash/load/initialization and is not a GPU-utilization integral',
    'holder_restored_count': 8, 'retries': 0, 'deletions': 0,
    'read_only_probe_failure': {'kind': 'sandbox_proc_io_permission_denied', 'operation': 'read launcher /proc/PID/io',
                                'impact': 'No runtime impact; observed progress via owned heartbeat/event files; no retry of the experiment'},
}
publish(WORK / 'FINAL_AUDIT.json', audit)
actual_counts = {**ledger['counts'], 'completed_rollouts': 0, 'gpu_seconds': None,
                 'model_gpu_inference_calls': 0, **initialization['entered_budget_usage'],
                 'diagnostic_observations_returned': 0, 'deleted_paths': 0, 'deleted_bytes': 0}
timing = launch['timing']
report = f'''# A10 有限原生预检：技术失败，已停止

| 项目 | 实际结果 |
|---|---|
| 一次执行 | P10_A_NATIVE_PREFLIGHT_V1 / v4；exit1；无重试、换源或协议回退 |
| SFT底座 | 加载完成，日志明确All keys loaded successfully，无missing/unexpected keys |
| 环境初始化 | 2物理实例+1包装器；51初始化+1诊断native reset=52全部返回；104reset_model /5200do_simulation /26000初始化物理子步 |
| 诊断 attempt | 计划1、进入1、完成0、技术失败1；完整观测未返回，初态图像产物0 |
| 采样 / 策略步 | 计划5采样/50flow/1策略步；实际均0，尚未进入 |
| 其他 | 完整rollout、反向、monitor、训练更新、自动重试、删除均0；success=null，不制造任务失败标签 |
| 占卡 | 8张H100 holder全部恢复，guard27508；17:06:35 UTC再次只读核实 |

失败点为 backend.reset_episode → 观测格式化 → render → MuJoCo EGL GLContext：`Cannot initialize a EGL device display`。异常发生在native reset已返回后、第一张RGB图像生成前；两条公共操作事件为模型加载返回、restore失败。4条公共phase记录与10724条初始化phase记录一致，末事件无缺失，已进入成本不清零。

只读环境线索：NVIDIA_DRIVER_CAPABILITIES=`compute,utility`，`/usr/share/glvnd/egl_vendor.d`无vendor JSON，ldconfig缓存未列libEGL/libnvidia-egl；只见libGLdispatch。优先由分析安排容器graphics/EGL驱动暴露与库查找链核查。这些元数据尚不能断言宿主GPU或驱动不支持EGL。未安装库、未改环境、未切换renderer，也未再创建EGL context。

实测分段墙钟：准备{timing['preparation_seconds']:.2f}s，预约/释放holder {timing['reservation_and_holder_release_seconds']:.2f}s，诊断子进程{timing['timed_diagnostic_process_seconds']:.2f}s，预约释放{timing['reservation_release_overhead_seconds']:.3f}s，恢复观察{timing['restoration_observation_seconds']:.2f}s；launcher端到端{timing['end_to_end_observed_seconds']:.2f}s。未触发1800+30超时。子进程族OS最大RSS约{ram_gib:.2f}GiB；受控子进程期间GPU0总显存采样峰值{peaks[0]:,}MiB，GPU1–7采样显存均0。NVML峰值只是采样下界，CUDA allocator峰值及实际GPU计算秒数未知，不拿CPU/加载墙钟冒充。

命名审计：原runtime资源回执`diagnostic_initial_states_returned=1`来自native reset返回计数；完整backend观测返回实际为0。原回执保持原样，本次FINAL_AUDIT明确更正解释，建议下一代码版本改名为diagnostic_native_resets_returned，并单独统计完整观测成功返回。

诊断目录：`{run_dir}`；launcher目录：`{launch_dir}`；执行/监控/静态EGL证据：`{WORK}`。所有实际文件SHA见本任务ARTIFACT_MANIFEST.json。没有生成raw5计划、step0/1图像、transition或queue_checks；原因是此前渲染失败，不补假数据。

请分析关闭此已消耗的一次release，决定EGL修复的具体CPU工程任务及任何后续独立有限release。原v1、旧A10/v3/v4及封存实验均未修改；不以剩余5采样/1策略步预算自行重跑。存储定向回执已另交，B依赖回执尚待，删除仍为0。
'''
report_path = RECEIPTS / f'{TASK}_REPORT.md'
assert len(report.splitlines()) <= 60
publish(report_path, report)
manifest = WORK / 'ARTIFACT_MANIFEST.json'
paths = sorted({p for root in (WORK, launch_dir, run_dir) for p in root.rglob('*') if p.is_file()})
publish(manifest, {'task_id': TASK, 'created_at_utc': now(), 'files': [
    {**ref(p), 'bytes': p.stat().st_size} for p in paths],
    'logical_output_bytes': sum(p.stat().st_size for p in paths), 'contains_copied_model_weights': False})
result = {'campaign_id': release['campaign_id'], 'task_id': TASK, 'revision': 1, 'role': 'A',
    'hostname': platform.node(), 'session_id': ack['executor_session_id'], 'status': 'failed',
    'started_at_utc': ack['started_at_utc'], 'finished_at_utc': now(), 'release_id': release['release_id'],
    'run_id': release['run_id'], 'wave_id': release['wave_id'], 'shard_id': release['shard_id'],
    'input_identity': {'launch_inputs': ack['inputs_checked'],
        'protocol': ref(WORK / 'inputs/A10_PREFLIGHT_NATIVE_V1.md'),
        'code': ref(Path(release['code_manifest_path'])), 'config': ref(Path(release['proposal_path'])),
        'data': release['source_manifest'],
        'model': {'path': json.loads(Path(release['proposal_path']).read_text())['checkpoint'] + '/model.safetensors',
                  'sha256': 'dff338a91dbe534ca3c4525ba82df9324662e3c87131f42ed6e3d1b7bf0e94d4',
                  'verification': 'Full SHA verified by both launcher and diagnostic authorization before model entry; loader reports all keys loaded'}},
    'artifacts': [ref(p) for p in (report_path, manifest, WORK / 'FINAL_AUDIT.json', WORK / 'COMMAND_EXIT.json',
        launch_dir / 'LAUNCH_RESULT.json', run_dir / 'failure.json', run_dir / 'resource_receipt.json', WORK / 'EGL_STATIC_METADATA.json')],
    'resource_counts': actual_counts, 'GPU_seconds_missing_reason': audit['GPU_seconds_missing_reason'],
    'planned_vs_actual': plan_actual,
    'outcome': {'planned': 1, 'entered': 1, 'completed': 0, 'technical_failed': 1,
                'missing_terminal_events': 0, 'success': None, 'success_missing_reason': audit['task_success_missing_reason']},
    'failures_and_retries': [{'command': exit_record['command'], 'exit_code': 1, 'stage': 'first_RGB_render_after_native_reset',
        'error_type': failure['error_type'], 'error': failure['error'], 'retry_count': 0,
        'recovery': 'Lifecycle released reservation; all8 holders restored; no scientific retry/renderer fallback'}],
    'findings': [
        'Persistent SFT all keys loaded; no native sample or policy control was entered',
        '2native instances/52resets/104reset_model/26000initialization substeps actually entered and returned, within v4 caps',
        'First RGB render failed to initialize EGL device display; no usable initial observation, plans or transition published',
        'One diagnostic attempt charged despite failure; successnull, completedrollouts0, training0, all incomplete-event counts0',
        'Container metadata suggests graphics/EGL exposure needs investigation; no runtime repair or extra graphics probe performed',
        'Raw diagnostic_initial_states_returned field counts native reset only; audit explicitly records full observation return0',
        'Process timings and sampled memory peaks measured separately; actual GPU compute seconds/allocator peak remain unknown',
        'All8 holders restored; one-shot release consumed, no retry or deletion',
    ],
    'blockers': [{'task': 'native_render_and_fiveH_queue_preflight', 'gap': failure['error'],
                  'resolution': 'Analysis-owned CPU EGL/container dependency task, then a distinct explicit bounded compute release if appropriate'}],
    'next_task_proposal': 'Close the consumed one-shot release; wait for analysis. No P/V, D/G0/Q, training, full episodes or cleanup.',
}
publish(RECEIPTS / f'{TASK}_HEARTBEAT.json', {'task_id': TASK, 'status': 'failed_reported', 'updated_at_utc': now(),
    'actual_simulator_attempts': 1, 'actual_environment_reset_calls': 52, 'actual_vla_sampling_calls': 0,
    'holder_restored_count': 8, 'retries': 0}, replace=True)
result_path = RECEIPTS / f'{TASK}_RESULT.json'
publish(result_path, result)
print(json.dumps({'result': str(result_path), 'sha256': sha(result_path), 'status': 'failed',
                  'sampled_GPU0_peak_MiB': peaks[0], 'RAM_maxrss_GiB': ram_gib, 'output_bytes': sum(p.stat().st_size for p in paths),
                  'holder_restored_count': 8}))
