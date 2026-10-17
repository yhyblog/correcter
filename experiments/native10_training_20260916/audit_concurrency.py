"""Posthoc, CPU/read-only audit of the sealed P0 concurrency32 probe.

Writes only concurrency32/audit.json and report.md when --write is requested.
No simulator, model, GPU, optimizer or reservation code is imported or called.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np

PACKAGE = Path(__file__).resolve().parents[2]
ROOT = PACKAGE/'outputs/native10_training_20260916'
OUT = ROOT/'p0/concurrency32'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def stats(values):
    value = np.asarray(values, np.float64)
    if not len(value) or not np.isfinite(value).all():
        raise ValueError('Invalid timing/resource records')
    return dict(n=len(value), minimum=float(value.min()), mean=float(value.mean()),
                median=float(np.median(value)), p95=float(np.percentile(value, 95)), maximum=float(value.max()))


def audit():
    inputs, checks, errors = {}, [], []
    def check(name, condition, **detail):
        row = dict(name=name, passed=bool(condition), **detail)
        checks.append(row)
        if not condition:
            errors.append(row)
    def tracked(path):
        path = Path(path).resolve();inputs[str(path)] = sha(path);return path
    def sealed(folder, expected=None):
        folder = Path(folder).resolve();path = tracked(folder/'complete.json');seal = read(path)
        check(str(folder)+':status', seal.get('status') == 'complete')
        if expected is not None:
            check(str(folder)+':registered_seal', sha(path) == expected)
        actual = {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p != path}
        check(str(folder)+':sealed_file_set', actual == set(seal['files']))
        for relative, digest in seal['files'].items():
            target = (folder/relative).resolve()
            valid = target.is_relative_to(folder) and target.is_file() and sha(target) == digest
            check(str(folder)+':'+relative, valid)
            if valid:
                inputs[str(target)] = digest
        return seal
    def archive_pair(current, baseline, *, trajectory=False):
        result = {}
        with np.load(tracked(current), allow_pickle=False) as actual, np.load(tracked(baseline), allow_pickle=False) as expected:
            check(str(current)+':array_keys', set(actual.files) == set(expected.files))
            for name in expected.files:
                left, right = actual[name], expected[name]
                same_shape_dtype = left.shape == right.shape and left.dtype == right.dtype
                bit_exact = same_shape_dtype and left.tobytes() == right.tobytes()
                if trajectory and name in ('physics_states', 'rewards') and same_shape_dtype:
                    difference = float(np.max(np.abs(left-right))) if left.size else 0.
                    tolerance = 1e-10 if name == 'physics_states' else 1e-8
                    passed = bool(np.isfinite(left).all() and np.isfinite(right).all() and difference <= tolerance)
                else:
                    difference = 0. if bit_exact else None;tolerance = 0.;passed = bit_exact
                check(str(current)+':'+name, passed)
                result[name] = dict(shape=list(left.shape), dtype=str(left.dtype), bit_exact=bit_exact,
                                    maximum_absolute_difference=difference, absolute_tolerance=tolerance)
        return result

    registration = read(tracked(OUT/'registration.json'))
    config = read(tracked(ROOT/'p0/config.json'))
    freeze = read(tracked(ROOT/'p0/freeze.json'))
    baseline_audit = ROOT/'p0/audit_native20.json'
    check('baseline_audit_unchanged_and_passed', sha(tracked(baseline_audit)) == registration['baseline_audit_sha256'] and read(baseline_audit)['status'] == 'passed')
    for name, digest in freeze['files'].items():
        check('p0_frozen:'+name, sha(tracked(name)) == digest)
    for name, identity in freeze.get('large_files_verified_once_then_stat', {}).items():
        stat = Path(name).stat()
        check('p0_large_checkpoint_stat:'+name,
              all(getattr(stat, attribute) == identity[key] for attribute, key in
                  (('st_size', 'bytes'), ('st_mtime_ns', 'mtime_ns'), ('st_ino', 'inode'), ('st_dev', 'device'))))
    for name, digest in registration['files'].items():
        check('registered_probe_code:'+name, sha(tracked(name)) == digest)
    check('registered_analysis_authority_unchanged', sha(tracked(PACKAGE/'coordination/NATIVE10_ANALYSIS_LEAD.md')) == registration['analysis_authority_sha256'])
    expected_cases = [case['case_id'] for case in config['episode_manifest'][:8]]
    check('registered_first_eight_no_outcome_filter', registration['case_ids'] == expected_cases and registration['workers'] == 32 and registration['workers_per_gpu'] == 4 and registration['attempts'] == 64)
    for path, digest in registration['references'].items():
        sealed(Path(path).parent, digest)
    wave = read(tracked(OUT/'wave.json'))
    check('wave_eight_gpu_assignments_and_no_idle_holders', len(wave['jobs']) == 8 and wave['hold_idle'] is False and sorted(job['devices'] for job in wave['jobs']) == [[i] for i in range(8)])

    ledger_path = tracked(ROOT/'budget/attempts.jsonl')
    ledger = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    numbers = [row['number'] for row in ledger]
    check('ledger_unique_contiguous_ids', numbers == list(range(1, len(ledger)+1)))
    lookup = {row['number']: row for row in ledger}
    simulation_total = sum(row['amount'] for row in ledger if row['resource'] == 'simulator_attempts')
    p0_total = sum(row['amount'] for row in ledger if row['resource'] == 'simulator_attempts' and row['stage'] == 'p0')
    probe_attempts = [row for row in ledger if row['kind'].startswith('concurrency_')]
    check('exact_64_new_attempts_total564_limit600', len(probe_attempts) == 64 and sum(row['amount'] for row in probe_attempts) == 64 and p0_total == 564 and simulation_total == 564 and p0_total <= 600)
    check('probe_budget_registration_matches', registration['budget_before'] == 500 and registration['budget_after_max'] == 564 and {row['number'] for row in probe_attempts} == set(range(501, 565)))
    check('probe_budget_kinds', Counter(row['kind'] for row in probe_attempts) == Counter(concurrency_candidate_restore=32, concurrency_branch_including_restore=32))
    check('exact_32_worker_and_ready_records', {path.name for path in OUT.glob('worker_*')} == {f'worker_{i:02d}' for i in range(32)} and {path.name for path in (OUT/'ready').glob('*.json')} == {f'{i:02d}.json' for i in range(32)})
    ready = [read(tracked(OUT/'ready'/f'{rank:02d}.json')) for rank in range(32)]
    last_ready = max(row['unix'] for row in ready)
    workers, baseline, per_worker, consumed = [], {}, [], []
    for rank in range(32):
        folder = OUT/f'worker_{rank:02d}';sealed(folder)
        row = read(folder/'result.json');generation = read(folder/'generation.json')
        case = expected_cases[rank % 8]
        check(f'worker{rank}:identity_status', row['rank'] == rank and row['case_id'] == case and row['status'] == 'passed' and row['errors'] == [])
        check(f'worker{rank}:load_barrier', ready[rank]['rank'] == rank and ready[rank]['loading_seconds'] == row['loading_seconds'] and row['work_started_unix'] >= last_ready)
        for field, filename, kind in (('bank_attempt','bank_attempt.json','concurrency_candidate_restore'), ('branch_attempt','branch_attempt.json','concurrency_branch_including_restore')):
            attempt = read(folder/filename);number = row[field];consumed.append(number)
            check(f'worker{rank}:{field}', attempt == lookup.get(number) and attempt['number'] == number and attempt['identity'] == str(folder) and attempt['kind'] == kind and attempt['resource'] == 'simulator_attempts' and attempt['amount'] == 1 and attempt['stage'] == 'p0' and attempt['protocol_sha256'] == config['analysis_approval']['protocol_sha256'] and row['work_started_unix'] <= attempt['unix'] <= row['work_finished_unix'])
        check(f'worker{rank}:bank_reserved_before_branch', lookup[row['bank_attempt']]['unix'] < lookup[row['branch_attempt']]['unix'])
        source = ROOT/'sources'/case;cut = read(source/'summary.json')['cuts'][0]
        bank = ROOT/'candidates'/case/f'cut{cut:03d}'
        branch = ROOT/'rollouts/p0'/case/f'cut{cut:03d}'/'alarm_replan10/repeat_0'
        old_gen, old_branch = read(bank/'generation.json'), read(branch/'summary.json')
        plan_comparison = archive_pair(folder/'plans.npz', bank/'plans.npz')
        trajectory_comparison = archive_pair(folder/'trajectory.npz', branch/'trajectory.npz', trajectory=True)
        check(f'worker{rank}:candidate_seed_noise_hashes', generation['base_seed'] == old_gen['base_seed'] and generation['noise_hashes'] == old_gen['noise_hashes'] and generation['same_noise'] is True and len(set(generation['noise_hashes'].values())) == 1)
        check(f'worker{rank}:no_candidate_fallback', generation['base_generation'].get('fallback') is None and all(generation['guidance'][mode].get('fallback') is None for mode in ('velocity', 'direct')))
        for mode in ('velocity', 'direct'):
            check(f'worker{rank}:{mode}_sampler_times_and_noise', generation['guidance'][mode]['times'] == old_gen['guidance'][mode]['times'] and generation['guidance'][mode]['noise_sha256'] == old_gen['guidance'][mode]['noise_sha256'])
        with np.load(folder/'trajectory.npz', allow_pickle=False) as trajectory:
            saved_seeds = trajectory['actual_sampling_seeds'].tolist()
            saved_steps = trajectory['actual_sampling_steps'].tolist()
            check(f'worker{rank}:saved_suffix_schedule_vs_reference', saved_seeds == [item['seed'] for item in old_branch['suffix_seeds']] and saved_steps == [item['step'] for item in old_branch['suffix_seeds']] and [item['decision_index'] for item in old_branch['suffix_seeds']] == list(range(len(saved_seeds))))
            check(f'worker{rank}:success_terminal_steps_calls', bool(trajectory['success_flags'].any()) == old_branch['success'] and len(trajectory['actions']) == row['branch_steps'] == old_branch['terminal_step'] and row['policy_calls'] == old_branch['policy_calls'] == len(saved_seeds))
            success = bool(trajectory['success_flags'].any())
        # Actual per-suffix noise hashes and endpoint image hash are NOT persisted
        # by the probe. The sealed worker's mandatory comparison and passed status
        # establish their execution check, not an independent re-read of raw hashes.
        per_worker.append(dict(rank=rank, gpu=rank % 8, case_id=case, success=success,
            plans=plan_comparison, trajectory=trajectory_comparison,
            independently_recomputed_suffix_seeds_and_plans=True,
            suffix_noise_hash_and_endpoint_image_evidence='frozen probe runtime equality assertion plus sealed passed result; actual hash list/image was not separately persisted'))
        workers.append(dict(row, candidate_engine_seconds=generation['candidate_bank_seconds']))
        baseline[case] = dict(case_id=case, cut=cut, bank_engine_seconds=old_gen['candidate_bank_seconds'],
            bank_recorded_total_seconds=old_gen['generation_wall_seconds'], bank_restore_seconds=old_gen['restore_seconds'],
            branch_recorded_total_seconds=old_branch['wall_seconds'], branch_restore_seconds=old_branch['restore_seconds'],
            suffix_policy_seconds=old_branch['policy_seconds'], suffix_policy_calls=old_branch['policy_calls'],
            branch_steps=old_branch['terminal_step'], bank_attempt=old_gen['budget_attempt'], branch_attempt=old_branch['budget_attempt'])
    check('every_probe_attempt_claimed_once', len(consumed) == len(set(consumed)) == 64 and set(consumed) == {row['number'] for row in probe_attempts})
    check('each_registered_case_four_replicas', Counter(row['case_id'] for row in workers) == Counter({case: 4 for case in expected_cases}))
    error_files = list((OUT/'errors').rglob('failure.json')) if (OUT/'errors').exists() else []
    check('complete_32_worker_logs', {path.name for path in (OUT/'logs').glob('worker_*.log')} == {f'worker_{i:02d}.log' for i in range(32)})
    fatal_logs = []
    for log in sorted((OUT/'logs').glob('*.log')):
        body = tracked(log).read_text(errors='replace')
        if re.search(r'out of memory|CUDA error:|Traceback \(most recent call last\)|Segmentation fault|Killed', body, re.I):
            fatal_logs.append(str(log))
    check('no_failed_workers_or_oom_logs', not error_files and not fatal_logs)

    active_span = max(row['work_finished_unix'] for row in workers)-min(row['work_started_unix'] for row in workers)
    worker_started = [row['work_finished_unix']-row['wall_seconds'] for row in workers]
    worker_envelope = max(row['work_finished_unix'] for row in workers)-min(worker_started)
    columns = ('loading_seconds','candidate_restore_and_bank_seconds','candidate_engine_seconds',
               'branch_wall_seconds','branch_restore_seconds','wall_seconds','policy_seconds',
               'peak_allocated_mib','peak_reserved_mib')
    latency = {key: stats([row[key] for row in workers]) for key in columns}
    baseline_rows = [baseline[case] for case in expected_cases]
    old_pair = [row['bank_recorded_total_seconds']+row['branch_recorded_total_seconds'] for row in baseline_rows]
    old_policy_rate = sum(row['suffix_policy_seconds'] for row in baseline_rows)/sum(row['suffix_policy_calls'] for row in baseline_rows)
    new_policy_rate = sum(row['policy_seconds'] for row in workers)/sum(row['policy_calls'] for row in workers)
    modeled_same_assignment = 4*max(old_pair)
    modeled_work_conservation = 4*sum(old_pair)/8
    performance = dict(latency=latency, baseline_same_eight_sources=baseline_rows,
        active_work_span_seconds=active_span,
        measured_worker_start_to_finish_envelope_seconds=worker_envelope,
        measured_work_pairs=32, simulator_attempts=64,
        active_work_pairs_per_second=32/active_span,
        full_worker_envelope_pairs_per_second=32/worker_envelope,
        active_attempts_per_second=64/active_span,
        paired_policy_calls_total=sum(row['policy_calls'] for row in workers),
        old_policy_seconds_per_call=old_policy_rate, new_policy_seconds_per_call=new_policy_rate,
        same_source_policy_latency_ratio=new_policy_rate/old_policy_rate,
        old_bank_engine_seconds=stats([row['bank_engine_seconds'] for row in baseline_rows]),
        bank_engine_latency_ratio=latency['candidate_engine_seconds']['mean']/np.mean([row['bank_engine_seconds'] for row in baseline_rows]),
        equal_workload_8worker_model=dict(work_pairs=32, old_repetitions_per_case=4,
            identical_static_case_per_gpu_seconds=modeled_same_assignment,
            work_conservation_ideal_lower_bound_seconds=modeled_work_conservation,
            implied_active_span_speedup_static=modeled_same_assignment/active_span,
            implied_active_span_speedup_ideal=modeled_work_conservation/active_span,
            observed_8worker_matching_probe=False,
            formula_static='4 * max_i(old bank generation_wall_seconds_i + old branch wall_seconds_i)',
            formula_ideal='4 * sum_i(old bank generation_wall_seconds_i + old branch wall_seconds_i) / 8',
            limitation='Historical timings came from different technical/native20 waves; these are modeled equal-workload comparisons, not observed paired 8-vs32 throughput.'),
        timing_boundary_caveats=[
            'Same engine candidate_bank_seconds and suffix policy_seconds have matched timer definitions.',
            'Old bank generation_wall_seconds includes preview13 construction/file IO; probe outer bank timer includes reserve/dump/context overhead but excludes later plan-file write.',
            'Old branch wall_seconds excludes reserve and includes trajectory-file write; probe branch timer includes reserve/dump but stops before trajectory-file write.',
            'Active span starts after all32 models loaded, ends before final trajectory/result/seal writes; it is neither entire command wall time nor long-run steady-state throughput.',
            'Worker wall timer starts after registration/freeze verification; startup, those checks, final file writes and supervisor cleanup are not all represented in the worker envelope.',
            'Historical first5 reference branches came from technical wave, later3 from native20; no contemporaneous equal-workload eight-worker probe was run.'])
    resources = dict(worker_processes=32, workers_per_gpu=4, gpu_count=8,
        cpu_worker_threads=config['cpu']['worker_threads'], critic_cpu_threads=config['cpu']['critic_threads'],
        cpu_core_utilization_measured=False, no_oom_in_completed_probe=not fatal_logs and not error_files,
        memory_measurement='Per-process PyTorch peak reset on every propose; final recorded peak describes last proposal, not whole-wave NVML/high-water mark.',
        observed_last_proposal_allocated_mib=latency['peak_allocated_mib'],
        observed_last_proposal_reserved_mib=latency['peak_reserved_mib'],
        four_process_reserved_sum_gib=4*latency['peak_reserved_mib']['maximum']/1024,
        full_gpu_memory_including_driver_egl_and_other_processes_measured=False,
        occupancy_after_wave='Parent executor reported all8 holders restored; this CPU audit did not inspect NVML.')
    return dict(schema='native10_concurrency32_posthoc_audit_v1', utc=datetime.now(timezone.utc).isoformat(),
        status='passed' if not errors else 'failed', checks=checks, errors=errors,
        budget=dict(before=500, probe=64, p0_total=p0_total, global_simulator_total=simulation_total,
                    p0_hard_limit=600, p0_remaining=600-p0_total, attempt_numbers=sorted(consumed)),
        input_sha256=inputs, auditor_sha256=sha(__file__), per_worker=per_worker,
        performance=performance, resources=resources,
        decision=dict(four_workers_per_gpu_supported_for_registered_implementation=not errors,
            permission_scope='Technical support to freeze32 persistent workers; main READY and actual main13/policy workload gates remain independent.',
            thirteen_candidate_steady_state_benchmark=False, effectiveness_evidence=False,
            standalone_independent_effectiveness_validation=False,
            retain_worker_models_across_many_jobs=True),
        no_new_simulation_or_training_performed_by_audit=True)


def report(result):
    p=result['performance'];l=p['latency'];m=p['equal_workload_8worker_model'];r=result['resources'];b=result['budget']
    lines=[
        '# P0 32-worker 并发复核', '',
        f"审计结果：**{result['status']}**。32 个 worker、每卡4个，覆盖预登记前8源各4份；新增64次仿真尝试，P0累计 **{b['p0_total']}/600**，余{b['p0_remaining']}。本审计新增仿真/训练均为0。", '',
        '32份worker封存与24份原source/bank/branch封存均逐文件核验；P0冻结依赖、探针代码、原native20审计SHA保持。每个worker候选计划所有数组精确一致；replan rep0完整轨迹中的动作、生成计划、采样种子/步、success/done flags精确一致，物理状态按1e-10、reward按1e-8复核。64个账本号唯一且全部被对应worker认领，32模型ready齐备后才开始各自已计数的restore。', '',
        '候选初始噪声hash直接从生成记录独立比较。实际后缀种子/计划可从trajectory独立比较；后缀噪声hash和前缀图像hash未另存第二份实际值，因此该项证据是封存探针内强制相等断言与sealed passed结果，不冒充后验原始hash重算。', '',
        '| 本次32-worker指标 | 均值 | 中位数 | P95 |', '|---|---:|---:|---:|']
    for title,key in [('模型加载秒','loading_seconds'),('候选restore+bank外层秒','candidate_restore_and_bank_seconds'),('相同engine bank函数秒','candidate_engine_seconds'),('replan分支外层秒','branch_wall_seconds'),('分支restore段秒','branch_restore_seconds'),('单worker总记录秒','wall_seconds')]:
        v=l[key];lines.append(f"| {title} | {v['mean']:.3f} | {v['median']:.3f} | {v['p95']:.3f} |")
    lines += ['',f"全部模型加载后的实际工作跨度为 **{p['active_work_span_seconds']:.3f}秒**，完成32个“1次bank+1次分支”工作对，即 **{p['active_work_pairs_per_second']:.3f} 对/秒**。含模型加载的worker起止包络约{p['measured_worker_start_to_finish_envelope_seconds']:.3f}秒，对应{p['full_worker_envelope_pairs_per_second']:.3f}对/秒。前者截止于最终轨迹/结果写盘前；后者由各worker记录反推，不等同于完整外层命令墙钟。", '',
        f"相同8源的engine bank均值（每源等权）由{p['old_bank_engine_seconds']['mean']:.3f}秒升至{l['candidate_engine_seconds']['mean']:.3f}秒，单worker延迟为原来的{p['bank_engine_latency_ratio']:.2f}倍；后缀policy耗时/调用（按实际调用数加权）由{p['old_policy_seconds_per_call']:.3f}升至{p['new_policy_seconds_per_call']:.3f}秒，为{p['same_source_policy_latency_ratio']:.2f}倍。并发总处理能力与单worker延迟是不同指标。", '',
        f"同等32工作对的8-worker参考只能建模：按旧同源耗时、每GPU固定源连续4次，估计{m['identical_static_case_per_gpu_seconds']:.3f}秒；理想无空闲工作量下界为{m['work_conservation_ideal_lower_bound_seconds']:.3f}秒。对比本次{p['active_work_span_seconds']:.3f}秒，模型比值分别为{m['implied_active_span_speedup_static']:.2f}倍和{m['implied_active_span_speedup_ideal']:.2f}倍。**这不是实测8-vs32配对吞吐增益**：旧前5源来自technical、后3源来自native20，且bank/分支外层计时的ledger与写盘边界不同；相同timer的engine bank/policy调用延迟更可比。", '',
        f"32个进程全部完成，未见OOM或失败日志；可据此将**4 worker/GPU作为已通过本次技术探针的并发配置冻结**，但不替代主流程READY。配置每worker CPU线程{r['cpu_worker_threads']}、critic线程{r['critic_cpu_threads']}，不能把32进程称作32个CPU核，也没有CPU利用率的连续测量。", '',
        f"每进程末次propose记录allocated {l['peak_allocated_mib']['maximum']:.2f} MiB、reserved {l['peak_reserved_mib']['maximum']:.2f} MiB；4份reserved相加约{r['four_process_reserved_sum_gib']:.2f} GiB。**每次propose会重置PyTorch峰值**，这不是全波次峰值/NVML实测，也不包括所有driver/EGL开销；无OOM仅证明本次32份模型与探针能够完成。占卡恢复由主执行端报告八卡完成，本CPU审计未另行读NVML。", '',
        '模型应保持常驻以摊薄约175秒的加载。worker总记录还未覆盖计时开始前的注册/冻结验证、全部最终写盘与supervisor清理。这里只重复8个已知source，四份复制不构成32个独立源，实际执行的是replan rep0；bank生成命令已验证，但没有执行13候选×4后缀的完整主负载。短探针不能作为13候选长时间稳态吞吐/峰值内存基准，也不构成算法正收益证据。', '',
        '逐worker/逐数组结果、完整输入SHA、64个账本号、公式与计时边界见同目录 `audit.json`。复现：', '',
        '```bash',
        'cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector',
        'PYTHONDONTWRITEBYTECODE=1 python -m experiments.native10_training_20260916.audit_concurrency',
        '```', '',
        '无参数只读重算并输出摘要；`--write`只允许首次创建audit.json/report.md，不替换已有审计。', '']
    if result['errors']:
        lines.insert(4, '存在失败检查，以上并发冻结建议不成立；以audit.json.errors为准。')
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--write', action='store_true');args=parser.parse_args()
    result=audit()
    if args.write:
        if (OUT/'audit.json').exists() or (OUT/'report.md').exists():
            raise FileExistsError('Preserve existing posthoc audit; read-only rerun without --write')
        with (OUT/'audit.json').open('x') as stream:
            json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
        with (OUT/'report.md').open('x') as stream:
            stream.write(report(result))
    print(json.dumps(dict(status=result['status'], checks=len(result['checks']), errors=result['errors'],
        budget=result['budget'], active_span=result['performance']['active_work_span_seconds']),ensure_ascii=False))
    if result['errors']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
