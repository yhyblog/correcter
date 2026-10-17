"""CPU reporting from saved terminal JSON only; never imports experiment code."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import os

M = Path(__file__).resolve().parent
B = M.parents[2]
N = B / 'deadline_20260924/A'
RECEIPTS = B / 'receipts/A'
THREAD = '01a0b91f-7443-71b1-915d-6cdb6d6a1a13'
EVENT = M / 'outbox/chain_terminal.json'
ACK = M / 'notifications/chain_terminal/HANDLER_ACK.json'
UTC = datetime.now(timezone.utc).isoformat()

def read(p):
    return json.loads(p.read_text())

def dt(s):
    return datetime.fromisoformat(s)

def write(p, value):
    raw = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())

def csv_text(rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    s = io.StringIO(newline='')
    w = csv.DictWriter(s, fieldnames=keys)
    w.writeheader()
    w.writerows(rows)
    return s.getvalue()

event = read(EVENT)
assert event['event_id'] == 'D24_A_main_once_chain_terminal_v1'
assert event['synthetic'] is False
if ACK.exists():
    existing = read(ACK)
    assert existing['event_id'] == event['event_id']
    assert existing['executor_thread_id'] == THREAD
    assert existing['handled'] is True
    print(json.dumps({'deduplicated': True, 'ack': str(ACK)}))
    raise SystemExit(0)

summary, baseline = read(M / 'SUMMARY.json'), read(N / 'SUMMARY.json')
chain = read(M / 'chain/CHAIN_RESULT.json')
manager = read(M / 'chain/MANAGER_EXIT.json')
release = read(M / 'chain/BEFORE_RESERVATION_RELEASE.json')
command = read(M / 'CHAIN_COMMAND.json')
aux = read(M / 'chain/AUXILIARY_EXIT_BEFORE_RELEASE.json')
util = read(M / 'chain/UTILIZATION_SUMMARY.json')
assert chain['raw_lifecycle_exit'] == 0 and chain['fatal'] is None
assert manager['all_owned_processes_exited'] is True
assert len(manager['workers']) == 8 and all(v == 0 for v in manager['workers'].values())

episodes, jobs, per_cell, sources = [], [], {}, defaultdict(set)
for p in sorted((M / 'runs').glob('*/RESULT.json')):
    job = read(p)
    cell = f"{job['method']}_H{job['H']}"
    agg = per_cell.setdefault(cell, {
        'jobs': 0, 'episodes': 0, 'successes': 0, 'technical_failures': 0,
        'interventions_histogram': Counter(), 'episode_counters': Counter(),
        'job_numeric_delta': Counter(), 'timing_sums_seconds': Counter(), 'steps': 0,
    })
    agg['jobs'] += 1
    agg['job_numeric_delta'].update(job['numeric_delta'])
    agg['timing_sums_seconds']['job_elapsed'] += job['elapsed_seconds']
    agg['timing_sums_seconds']['job_environment_initialization'] += job['environment_initialization_seconds']
    jobs.append({'cell': cell, 'task': job['task'], 'path': str(p), 'status': job['status']})
    for ep in job['episodes']:
        row = {'cell': cell, 'job_id': job['job_id'], 'result_path': str(p)}
        row.update({k: v for k, v in ep.items() if not isinstance(v, (list, dict))})
        row.update({'counter_' + k: v for k, v in ep['counters'].items()})
        episodes.append(row)
        agg['episodes'] += 1
        agg['successes'] += int(ep['success'] is True)
        agg['technical_failures'] += int(ep['technical_failure'] is not None)
        agg['interventions_histogram'][str(ep['interventions'])] += 1
        agg['episode_counters'].update(ep['counters'])
        agg['steps'] += ep['steps']
        for key in ('elapsed_seconds', 'elapsed_control_seconds', 'reset_seconds', 'environment_seconds', 'inference_seconds'):
            agg['timing_sums_seconds'][key] += ep[key]
        sources[cell].add((ep['task'], ep['source_id'], ep['ordinal'], ep['repeat'], ep['env_seed'], ep['policy_seed']))

assert len(jobs) == 550 and len(episodes) == 5500
for cell, agg in per_cell.items():
    saved = summary['cells'][cell]
    assert agg['jobs'] == saved['jobs'] == 50
    assert agg['episodes'] == saved['terminals'] == 500
    assert agg['successes'] == saved['successes']
    assert agg['technical_failures'] == saved['technical_failures'] == 0
    assert set(agg['interventions_histogram']).issubset({'0', '1'})
    assert len(sources[cell]) == 500
assert len(set.union(*sources.values())) == 500

cells = []
for origin, data in [('existing_N', baseline), ('main_once', summary)]:
    for cell, s in data['cells'].items():
        method, h = cell.rsplit('_H', 1)
        row = {'cell': cell, 'method': method, 'H': int(h), 'origin': origin,
               'tasks': s['jobs'], 'attempts': s['attempts'], 'terminal_episodes': s['terminals'],
               'successes': s['successes'], 'success_percent': 100 * s['successes'] / s['terminals'],
               'technical_failures': s['technical_failures'],
               'delta_vs_N_percentage_points': round(100 * (s['successes'] - baseline['cells']['N_H' + h]['successes']) / 500, 1)}
        cells.append(row)
cells.sort(key=lambda x: (x['H'], ['N', 'R', 'Post', 'Velocity'].index(x['method'])))

worker_load = []
for i in range(8):
    p = M / f'chain/workers/{i}/MODEL_READY.json'
    x = read(p)
    worker_load.append({'worker': i, 'gpu_uuid': x['GPU']['gpu_uuid'], 'model_load_seconds': x['model_load_seconds'], 'ready_utc': x['utc'], 'reference': str(p)})

aux_records = aux['records']
aux_by_gpu = {}
for r in aux_records:
    g = aux_by_gpu.setdefault(r['GPU_uuid'], {'sessions': 0, 'manager_interval_seconds_sum': 0.0})
    g['sessions'] += 1
    g['manager_interval_seconds_sum'] += r['holder_manager_interval_seconds']
aux_exit_before_release = all(dt(r['all_descendants_exit_observed_utc']) < dt(release['utc']) for r in aux_records)
assert aux_exit_before_release
total_counters, total_numeric, total_timing = Counter(), Counter(), Counter()
for agg in per_cell.values():
    total_counters.update(agg['episode_counters'])
    total_numeric.update(agg['job_numeric_delta'])
    total_timing.update(agg['timing_sums_seconds'])

resources = {
    'utc': UTC, 'scope': 'saved main-chain results only; no new hardware/model/environment calls',
    'per_cell': per_cell, 'episode_counters_sum': total_counters,
    'job_numeric_delta_sum': total_numeric, 'timing_sums_seconds': total_timing,
    'worker_model_loads': worker_load,
    'command_utc': command['utc'], 'terminal_utc': chain['utc'],
    'command_to_terminal_wall_seconds': (dt(chain['utc']) - dt(command['utc'])).total_seconds(),
    'timing_scope_notes': [
        'Per-episode and per-job timing sums overlap and are not added to each other.',
        'Sums across parallel workers are not elapsed wall time or measured GPU kernel time.',
        'inference_seconds covers generation/correction only; context and D/G0 are included in episode wall time.',
        'Job numeric_delta excludes resident-worker initialization; model-load time is listed separately.',
        'Context, D/G0 and Q counter categories are saved runtime counts, not one shared public cost ledger.',
    ],
    'auxiliary_occupancy': {
        'sessions': len(aux_records), 'per_gpu': aux_by_gpu,
        'manager_interval_seconds_sum': sum(r['holder_manager_interval_seconds'] for r in aux_records),
        'interval_scope': 'GO permission to observed own-session descendant exit; not GPU kernel time or energy',
        'configured_duty_values': sorted(set(r['configured_duty'] for r in aux_records)),
        'measured_holder_utilization': None,
        'all_owned_sessions_exited': all(r['status'] == 'all_owned_holder_session_processes_exited' for r in aux_records),
        'all_exit_before_reservation_release': aux_exit_before_release,
        'last_descendant_exit_utc': max(r['all_descendants_exit_observed_utc'] for r in aux_records),
        'reasons': dict(Counter(r['reason'] for r in aux_records)),
        'no_unrelated_process_signals': all(r['no_unrelated_process_signals'] for r in aux_records),
        'raw_reference': str(M / 'chain/AUXILIARY_EXIT_BEFORE_RELEASE.json'),
        'entire_formal_wave_all_holders_off': False,
        'policy_note': 'Actual terminal interval used the deployed idle-card auxiliary override; it did not satisfy the latest whole-wave all-holder-off wording. Preserve actual evidence; no rerun or retroactive correction.',
    },
    'utilization': {
        'saved_query_attempts': aux['utilization_query_attempts'],
        'sample_mean_percent_across_eight_GPUs': sum(v['utilization_percent_sum'] for v in util['GPUs'].values()) / sum(v['valid_utilization_samples'] for v in util['GPUs'].values()),
        'per_gpu': util['GPUs'], 'raw_reference': str(M / 'chain/UTILIZATION_SUMMARY.json'),
        'scope': 'Sample mean includes the late auxiliary interval, not pure scientific utilization; does not prove continuously >=50% or a platform-specific averaging window.',
        'actual_GPU_kernel_idle_seconds': None,
    },
}
final = {
    'utc': UTC, 'status': 'MAIN_ONCE_5500_COMPLETE', 'event_id': event['event_id'],
    'main_jobs': 550, 'main_episodes': 5500, 'main_cells': 11,
    'main_technical_failures': 0, 'main_source_identities': 500,
    'combined_with_existing_N': {'cells': 16, 'episodes': 8000, 'independent_planned_test_source_identities': 500, 'pilot_included': False},
    'cells': cells, 'models': 'pi05-MT50 SFT030000; frozen D/G0/Q trained on historical five tasks, evaluated across MT50; no new MT50 critic adaptation',
    'interventions_max': 1, 'repeat': 0,
    'new_formal_launches_this_callback': 0, 'scientific_compute_this_callback': 0,
    'N_or_pilot_rerun': False, 'remaining475_collection': False,
    'raw_lifecycle_exit': chain['raw_lifecycle_exit'], 'worker_exits': manager['workers'],
    'cleanup': chain['cleanup'], 'restoration': chain['restoration'],
    'auxiliary_occupancy_policy_note': resources['auxiliary_occupancy']['policy_note'],
    'source_summary': str(M / 'SUMMARY.json'), 'source_N_summary': str(N / 'SUMMARY.json'),
    'resource_summary': str(M / 'FINAL_RESOURCE_SUMMARY.json'),
    'main_episode_csv': str(M / 'FINAL_EPISODES.csv'),
    'comparison_cells_csv': str(M / 'FINAL_CELLS.csv'),
    'next': 'No additional experiment started; original occupancy guard continues. Analysis decides the next scientific stage.',
}

write(M / 'FINAL_EPISODES.csv', csv_text(episodes))
write(M / 'FINAL_CELLS.csv', csv_text(cells))
write(M / 'FINAL_RESOURCE_SUMMARY.json', resources)
write(M / 'FINAL_SUMMARY.json', final)

report_lines = [
    '主评测整链完成：11格/5500条，技术失败0；原命令仅一次，8个常驻worker全部exit0，lifecycle exit0。既有N的5格/2500条直接引用，合计16格/8000条评测，共用500个预定test源身份；旧20源pilot另计，未重跑。',
    '', '| H | N | R | Post | Velocity |', '|---|---:|---:|---:|---:|',
]
by_cell = {r['cell']: r for r in cells}
for h in [10, 20, 30, 40, 50]:
    values = []
    for method in ['N', 'R', 'Post', 'Velocity']:
        c = by_cell.get(f'{method}_H{h}')
        values.append(f"{c['successes']}/500 ({c['success_percent']:.1f}%)" if c else '未安排')
    report_lines.append('| ' + str(h) + ' | ' + ' | '.join(values) + ' |')
report_lines += [
    '',
    '底座为π0.5-MT50 SFT030000；D/G0/Q沿用历史五任务训练的冻结模块，以上为跨MT50测试，不是新MT50训练完成。所有方法固定repeat0、自然触发、最多一次干预；未根据test更换模型/阈值/seed。',
    '',
    f"保存计量合计：{total_counters['sampling']}次sampling、{total_counters['flow']}次flow、{sum(a['steps'] for a in per_cell.values())}控制步、{total_counters['interventions']}次干预；D/G0分别{total_counters['D_forward']}/{total_counters['G0_forward']}次，Q ensemble {total_counters['Q_ensemble_forward']}次，动作梯度{total_counters['action_gradients']}次。按格细目、encoder等job delta和8worker加载时间见FINAL_RESOURCE_SUMMARY.json。", 
    f"命令至整链退出/恢复为{resources['command_to_terminal_wall_seconds']:.3f}秒（{resources['command_to_terminal_wall_seconds']/60:.2f}分钟）；不是纯推理时间。逐episode推理计时仅覆盖generation/correction，context及D/G0包含于episode总时长。并行worker累计时间不能作为整链墙钟时间。",
    '',
    f"终局进程组全部退出，{chain['restoration']['observed_at']['utc']}保存的恢复证据为8/8 holder。末段实际存在{len(aux_records)}个辅助holder会话，GO至自有进程族退出累计{resources['auxiliary_occupancy']['manager_interval_seconds_sum']:.3f}秒，退出早于预约释放；因此不宣称整波holder全停，这与当前全波全停条款不一致，保留为执行偏差。该时间不是GPU kernel时间，configured duty .95不是实测利用率。",
    f"已有监测每卡297点、跨卡样本均值{resources['utilization']['sample_mean_percent_across_eight_GPUs']:.3f}%，包含末段辅助占卡，不能证明持续达到平台50%阈值。原r3中辅助START=0仅为18:03快照，不替代本终局记录。",
    '',
    '本回调仅从保存的550个job RESULT提取5500行小字段，并核对总数与既有SUMMARY；没有新模型/环境/硬件查询、重试或实验启动。未改旧回执、分析CONTROL/任务板。发布后保持原guard占卡，下一科学阶段由分析端决定。',
    '', '产物：FINAL_SUMMARY.json、FINAL_CELLS.csv、FINAL_EPISODES.csv、FINAL_RESOURCE_SUMMARY.json；原始退出/恢复/占卡记录均保留在chain/。',
]
report = RECEIPTS / 'A_D24_MAIN_ONCE_V1_REPORT_r4.md'
result = RECEIPTS / 'A_D24_MAIN_ONCE_V1_RESULT_r4.json'
write(report, '\n'.join(report_lines) + '\n')
write(result, {'task_id': 'A_D24_SPRINT_V1', 'stage': 'A_D24_MAIN_ONCE_V1',
               **final, 'report': str(report), 'final_publication': str(M / 'FINAL_PUBLICATION.json')})
publication_paths = [M / name for name in ['FINAL_REPORT_AGGREGATION.py', 'FINAL_EPISODES.csv', 'FINAL_CELLS.csv', 'FINAL_RESOURCE_SUMMARY.json', 'FINAL_SUMMARY.json']]
publication_paths += [report, result, EVENT, M / 'SUMMARY.json', M / 'chain/CHAIN_RESULT.json', M / 'chain/MANAGER_EXIT.json', M / 'chain/BEFORE_RESERVATION_RELEASE.json', M / 'chain/AUXILIARY_EXIT_BEFORE_RELEASE.json', M / 'chain/UTILIZATION_SUMMARY.json']
write(M / 'FINAL_PUBLICATION.json', {'utc': UTC, 'scope': 'small final publication and terminal evidence only; no per-frame/tree/model hash', 'artifacts': [
    {'path': str(p), 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in publication_paths
]})
write(ACK, {'event_id': event['event_id'], 'executor_thread_id': THREAD, 'synthetic': False,
            'handled': True, 'scientific_compute': 0, 'callback_received_as_message': True,
            'utc': datetime.now(timezone.utc).isoformat(), 'result_receipt': str(result),
            'report': str(report), 'chain_complete': True, 'main_episodes': 5500,
            'technical_failures': 0, 'relaunch': False})
print(json.dumps({'result': str(result), 'ack': str(ACK), 'main_episodes': 5500,
                  'counters': total_counters, 'auxiliary_sessions': len(aux_records),
                  'auxiliary_manager_seconds': resources['auxiliary_occupancy']['manager_interval_seconds_sum'],
                  'utilization_sample_mean_percent': resources['utilization']['sample_mean_percent_across_eight_GPUs']}, ensure_ascii=False))
