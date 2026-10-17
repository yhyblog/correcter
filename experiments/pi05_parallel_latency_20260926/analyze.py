"""Read-only CPU aggregation of measured parallel-query and frequency records.

Usage: /usr/bin/python analyze.py [--config CONFIG.json] [--output DIRECTORY]
No model imports, CUDA calls, benchmark launches, or edits to raw data.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path


CASES = ('N', 'parallel_feedback_no_intervention', 'parallel_feedback_with_Q',
         'feedback_then_replan_Q')
MODES = ('policy_only_3Hz', 'feedback_alone_max', 'feedback_6Hz', 'feedback_30Hz',
         'feedback_saturated_with_policy')
LATENCY_FIELDS = ('wall_seconds', 'policy_seconds', 'feedback_seconds', 'q_seconds')
THRESHOLD = 1 / 3


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def quantile(values, p=.95):
    if not values:
        return None
    ordered = sorted(values)
    x = (len(ordered) - 1) * p
    lo, hi = math.floor(x), math.ceil(x)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (x - lo)


def stats(values):
    return dict(n=len(values), mean_seconds=math.fsum(values) / len(values) if values else None,
                p95_seconds=quantile(values))


def read_json(path, issues, required=False):
    path = Path(path)
    if not path.exists() and not required:
        return None
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError('expected JSON object')
        return data
    except (OSError, ValueError) as error:
        issues.append(dict(path=str(path), issue='unreadable_json', error=str(error)))
        return None


def read_jsonl(path, issues):
    if not path.exists():
        return []
    records = []
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError('expected JSON object')
            records.append(value)
        except (ValueError, TypeError) as error:
            issues.append(dict(path=str(path), line=line_no, issue='malformed_jsonl', error=str(error)))
    return records


def resolve(path, parent):
    path = Path(path)
    return path if path.is_absolute() else (parent / path).resolve()


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(text)
    temporary.replace(path)


def write_csv(path, rows, columns):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)
    write_text(path, stream.getvalue())


def main(config_path, output=None):
    config_path = Path(config_path).resolve()
    issues = []
    config = read_json(config_path, issues, required=True)
    if config is None:
        raise ValueError('Cannot read ' + str(config_path))
    root = config_path.parent
    destination = Path(output).resolve() if output else root
    contexts = read_json(resolve(config.get('contexts_path', 'contexts.json'), root), issues) or {}
    assets = read_json(resolve(config.get('assets_path', 'assets.json'), root), issues) or {}
    workers, latency_samples, frequency_samples = [], [], []
    counts = Counter()
    for index, item in enumerate(config.get('workers', [])):
        if isinstance(item, str):
            worker_path = resolve(item, root)
            cfg = read_json(worker_path, issues, required=True)
        elif isinstance(item, dict) and 'output' in item and ('contexts' in item or 'gpu_index' in item):
            cfg, worker_path = item, config_path
        elif isinstance(item, dict) and (item.get('config') or item.get('config_path')):
            worker_path = resolve(item.get('config') or item['config_path'], root)
            cfg = read_json(worker_path, issues, required=True)
        else:
            issues.append(dict(issue='invalid_worker_config_entry', index=index))
            continue
        if cfg is None:
            continue
        out = resolve(cfg.get('output', f'workers/worker_{index}'), worker_path.parent)
        terminal = read_json(out / 'RESULT.json', issues) or {}
        identity = dict(worker_id=cfg.get('worker_id', index), host=cfg.get('host', config.get('host', 'unknown')),
                        gpu_index=cfg.get('gpu_index', index), gpu_uuid=cfg.get('gpu_uuid') or 'unknown')
        worker = dict(**identity, output=str(out), config=str(worker_path),
                      role=cfg.get('role', 'both'),
                      status=terminal.get('status', 'missing'), error=terminal.get('error'),
                      result_path=str(out / 'RESULT.json'),
                      latency_path=str(out / 'latency.jsonl'), frequency_path=str(out / 'frequency.jsonl'),
                      counts=Counter(), context_ids=set())
        workers.append(worker)
        seen = set()
        for row in read_jsonl(out / 'latency.jsonl', issues):
            counts['latency_rows'] += 1
            worker['counts']['latency_rows'] += 1
            rep = row.get('repetition')
            warmup = bool(row.get('warmup')) or (numeric(rep) and rep < 0)
            if warmup:
                counts['warmup_rows'] += 1
                worker['counts']['warmup_rows'] += 1
                continue
            case, context_id = row.get('case'), row.get('context_id')
            key = (case, context_id, rep)
            invalid = None
            if case not in CASES or context_id is None or not isinstance(rep, int):
                invalid = 'invalid_latency_identity'
            elif str(row.get('gpu_index')) != str(identity['gpu_index']):
                invalid = 'gpu_identity_mismatch'
            elif key in seen:
                invalid = 'duplicate_latency_identity'
            elif not numeric(row.get('wall_seconds')) or row['wall_seconds'] < 0:
                invalid = 'missing_or_invalid_measured_wall'
            if invalid:
                counts['excluded_latency_rows'] += 1
                worker['counts']['excluded_latency_rows'] += 1
                issues.append(dict(issue=invalid, worker_id=identity['worker_id'], case=case,
                                   context_id=context_id, repetition=rep))
                continue
            seen.add(key)
            worker['context_ids'].add(context_id)
            worker['counts']['included_latency_rows'] += 1
            counts['included_latency_rows'] += 1
            latency_samples.append(dict(**identity, **{k: row.get(k) for k in LATENCY_FIELDS},
                                        case=case, context_id=context_id, repetition=rep,
                                        intervals={k: row.get(k) for k in ('policy_start_s', 'policy_end_s',
                                                                          'feedback_start_s', 'feedback_end_s')}))
        for window_index, row in enumerate(read_jsonl(out / 'frequency.jsonl', issues)):
            duration = row.get('duration_seconds')
            mode = row.get('mode')
            counts['frequency_windows'] += 1
            if mode not in MODES or not numeric(duration) or duration <= 0 or str(row.get('gpu_index')) != str(identity['gpu_index']):
                issues.append(dict(issue='invalid_frequency_window', worker_id=identity['worker_id'], window_index=window_index))
                continue
            for role in ('policy', 'feedback'):
                events = row.get(role)
                if not isinstance(events, list):
                    issues.append(dict(issue='missing_frequency_role_records', worker_id=identity['worker_id'], mode=mode, role=role))
                    events = []
                hz = row.get('planned_' + role + '_hz')
                deadline = THRESHOLD if role == 'policy' else (1 / hz if numeric(hz) and hz > 0 else None)
                valid, pending, invalid = [], 0, 0
                for event in events:
                    if not isinstance(event, dict):
                        invalid += 1
                        continue
                    release, start, end, service = (event.get(k) for k in ('release_s', 'start_s', 'end_s', 'service_seconds'))
                    if not numeric(release) or release < 0 or release >= duration:
                        invalid += 1
                        continue
                    if end is None:
                        pending += 1
                        continue
                    if not all(numeric(v) for v in (start, end, service)) or not release <= start <= end or service < 0:
                        invalid += 1
                        continue
                    valid.append(dict(release_s=release, start_s=start, end_s=end, service_seconds=service))
                if invalid:
                    issues.append(dict(issue='invalid_frequency_events', worker_id=identity['worker_id'], mode=mode,
                                       role=role, count=invalid, window_index=window_index))
                frequency_samples.append(dict(**identity, mode=mode, role=role, window_index=window_index,
                                              duration_seconds=duration, planned_hz=hz, deadline_seconds=deadline,
                                              events=valid, pending=pending, invalid=invalid,
                                              scheduled_count=row.get(role + '_scheduled_count'),
                                              skipped_releases=row.get(role + '_skipped_releases'),
                                              control_hz=row.get('control_hz')))
            if row.get('context_id') is not None:
                worker['context_ids'].add(row['context_id'])
        worker['context_ids'] = sorted(worker['context_ids'])
        worker['counts'] = dict(worker['counts'])

    latency_rows = []
    for worker in [None] + [w for w in workers if w['role'] in ('latency', 'both')]:
        relevant = latency_samples if worker is None else [r for r in latency_samples if r['worker_id'] == worker['worker_id']]
        identity = dict(scope='all_queries', worker_id='', host='', gpu_index='', gpu_uuid='') if worker is None else dict(
            scope='worker', **{k: worker[k] for k in ('worker_id', 'host', 'gpu_index', 'gpu_uuid')})
        for case in CASES:
            samples = [r for r in relevant if r['case'] == case]
            for metric in LATENCY_FIELDS:
                values = [r[metric] for r in samples if numeric(r.get(metric)) and r[metric] >= 0]
                row = dict(**identity, case=case, metric=metric, contexts=len({r['context_id'] for r in samples}),
                           **stats(values), within_333ms_count=None, within_333ms_fraction=None)
                if metric == 'wall_seconds':
                    row['within_333ms_count'] = sum(v <= THRESHOLD for v in values)
                    row['within_333ms_fraction'] = row['within_333ms_count'] / len(values) if values else None
                latency_rows.append(row)
    # Service/deadline statistics include drained completions released inside each window.
    # Throughput counts only completions whose end falls inside that same window.
    grouped = defaultdict(list)
    for sample in frequency_samples:
        grouped[(sample['worker_id'], sample['mode'], sample['role'])].append(sample)
    frequency_rows = []
    for worker in [w for w in workers if w['role'] in ('frequency', 'both')]:
        for mode in MODES:
            for role in ('policy', 'feedback'):
                windows = grouped[(worker['worker_id'], mode, role)]
                durations = [w['duration_seconds'] for w in windows]
                total_duration = math.fsum(durations)
                events = [(e, w) for w in windows for e in w['events']]
                within = [(e, w) for e, w in events if e['end_s'] <= w['duration_seconds']]
                service = stats([e['service_seconds'] for e, _ in events])
                within_service = stats([e['service_seconds'] for e, _ in within])
                deadline_pairs = [(e, w) for e, w in events if w['deadline_seconds'] is not None]
                misses = sum(e['end_s'] - e['release_s'] > w['deadline_seconds'] for e, w in deadline_pairs)
                rates = {w['planned_hz'] for w in windows}
                scheduled = (sum(w['scheduled_count'] for w in windows)
                             if windows and all(numeric(w['scheduled_count']) for w in windows) else None)
                skipped = (sum(w['skipped_releases'] for w in windows)
                           if windows and all(numeric(w['skipped_releases']) for w in windows) else None)
                frequency_rows.append(dict(scope='worker', **{k: worker[k] for k in ('worker_id', 'host', 'gpu_index', 'gpu_uuid')},
                    mode=mode, role=role, windows=len(windows), duration_seconds=total_duration if windows else None,
                    planned_hz=next(iter(rates)) if len(rates) == 1 else None,
                    n=service['n'], in_window_completed=len(within), after_window_completed=len(events) - len(within),
                    pending=sum(w['pending'] for w in windows), invalid=sum(w['invalid'] for w in windows),
                    scheduled_count=scheduled, skipped_releases=skipped,
                    skipped_fraction=skipped / scheduled if skipped is not None and scheduled else None,
                    scheduled_in_window_completion_fraction=len(within) / scheduled if scheduled else None,
                    actual_throughput_hz=len(within) / total_duration if total_duration else None,
                    mean_seconds=service['mean_seconds'], p95_seconds=service['p95_seconds'],
                    within_window_service_n=within_service['n'],
                    within_window_service_mean_seconds=within_service['mean_seconds'],
                    within_window_service_p95_seconds=within_service['p95_seconds'],
                    deadline_n=len(deadline_pairs), deadline_miss_count=misses if deadline_pairs else None,
                    deadline_miss_fraction=misses / len(deadline_pairs) if deadline_pairs else None))
    cross_worker = []
    for mode in MODES:
        for role in ('policy', 'feedback'):
            rows = [r for r in frequency_rows if r['mode'] == mode and r['role'] == role and r['windows']]
            entry = dict(scope='cross_worker', worker_id='', host='', gpu_index='', gpu_uuid='',
                         mode=mode, role=role, worker_n=len(rows))
            for key in ('actual_throughput_hz', 'mean_seconds', 'p95_seconds', 'deadline_miss_fraction', 'skipped_fraction'):
                values = [r[key] for r in rows if numeric(r[key])]
                entry[key + '_worker_mean'] = math.fsum(values) / len(values) if values else None
                entry[key + '_worker_min'] = min(values) if values else None
                entry[key + '_worker_max'] = max(values) if values else None
            cross_worker.append(entry)

    overlap = []
    for case in CASES[1:]:
        vals, causal_violations = [], 0
        for row in latency_samples:
            if row['case'] != case:
                continue
            ps, pe, fs, fe = (row['intervals'][k] for k in ('policy_start_s', 'policy_end_s', 'feedback_start_s', 'feedback_end_s'))
            if all(numeric(v) for v in (ps, pe, fs, fe)) and ps <= pe and fs <= fe:
                vals.append(max(0, min(pe, fe) - max(ps, fs)))
                if case == 'feedback_then_replan_Q' and ps + 1e-9 < fe:
                    causal_violations += 1
        overlap.append(dict(case=case, **stats(vals), positive_overlap_count=sum(v > 0 for v in vals),
                            causal_policy_before_feedback_finished=causal_violations))
    missing_latency_cases = [c for c in CASES if not any(r['case'] == c for r in latency_samples)]
    missing_frequency = [dict(worker_id=w['worker_id'], mode=m) for w in workers for m in MODES
                         if w['role'] in ('frequency', 'both')
                         if not grouped[(w['worker_id'], m, 'policy')]]
    expected_per_case = config.get('expected_latency_samples_per_case')
    if numeric(expected_per_case):
        for case in CASES:
            actual = sum(row['case'] == case for row in latency_samples)
            if actual != expected_per_case:
                issues.append(dict(issue='latency_sample_coverage_mismatch', case=case,
                                   expected=expected_per_case, actual=actual))
    expected = {k: v for k, v in config.items() if 'expected' in k or 'repetition' in k or 'warmup' in k}
    complete = (bool(workers) and all(w['status'] == 'complete' for w in workers) and not issues
                and not missing_latency_cases and not missing_frequency)
    summary = dict(schema_version=1, generated_utc=datetime.now(timezone.utc).isoformat(),
                   status='complete' if complete else 'partial', config=str(config_path),
                   counts=dict(counts), workers=workers, expected_metadata=expected,
                   context_metadata={k: contexts.get(k) for k in ('count', 'tasks', 'selection', 'all_cut5', 'scope')},
                   Q_metadata={k: assets.get('Q', {}).get(k) for k in ('requested_hidden_width', 'parameters_per_member',
                                                                                    'members', 'total_parameters', 'training', 'device')},
                   latency=latency_rows, frequency=frequency_rows, frequency_cross_worker=cross_worker,
                   measured_interval_overlap=overlap, issues=issues,
                   missing_latency_cases=missing_latency_cases, missing_frequency_windows=missing_frequency,
                   latency_wall_source='recorded outer wall_seconds only; no sum/max reconstruction',
                   quantile='linear at (n-1)*0.95', threshold_seconds=THRESHOLD,
                   partial_worker_policy='valid recorded nonwarmup samples retained; worker statuses and missing coverage disclosed',
                   throughput='per worker: sum(count(end_s<=duration_seconds))/sum(duration_seconds); never sum GPUs into one GPU',
                   service_deadline_population='valid completed tasks released inside window, including completions drained after window',
                   training_updates=0)
    write_text(destination / 'SUMMARY.json', json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    identity_columns = ['scope', 'worker_id', 'host', 'gpu_index', 'gpu_uuid']
    write_csv(destination / 'LATENCY.csv', latency_rows, identity_columns + ['case', 'metric', 'contexts', 'n',
              'mean_seconds', 'p95_seconds', 'within_333ms_count', 'within_333ms_fraction'])
    frequency_columns = identity_columns + ['mode', 'role', 'windows', 'duration_seconds', 'planned_hz', 'n',
        'in_window_completed', 'after_window_completed', 'pending', 'invalid', 'scheduled_count',
        'skipped_releases', 'skipped_fraction', 'scheduled_in_window_completion_fraction', 'actual_throughput_hz',
        'mean_seconds', 'p95_seconds', 'within_window_service_n', 'within_window_service_mean_seconds',
        'within_window_service_p95_seconds', 'deadline_n', 'deadline_miss_count', 'deadline_miss_fraction', 'worker_n']
    frequency_columns += [key + suffix for key in ('actual_throughput_hz', 'mean_seconds', 'p95_seconds', 'deadline_miss_fraction', 'skipped_fraction')
                          for suffix in ('_worker_mean', '_worker_min', '_worker_max')]
    write_csv(destination / 'FREQUENCY.csv', frequency_rows + cross_worker, frequency_columns)

    def fmt(value, scale=1):
        return 'NR' if value is None else f'{value * scale:.3f}'

    lines = ['# π0.5 并发墙钟与反馈频率补测', '', f'汇总时间：{summary["generated_utc"]}；状态：{summary["status"]}。', '',
             '查询延迟直接来自外层实测 wall_seconds；均值/P95均从逐条墙钟计算，未用分项之和或最大值估算。预热排除，P95使用linear插值。各行≤1/3秒比例表示本批查询满足333.333毫秒预算的比例。', '',
             '`parallel_feedback_no_intervention` 与 `parallel_feedback_with_Q` 在正常计划更新点共时发起策略与反馈，不额外投机采样；`feedback_then_replan_Q` 从中途反馈发起计时，先反馈再fresh采样及Q，是单独的因果串联路径。', '',
             '频率吞吐按每worker自身窗口内完成数/窗口时长计算；跨worker只报告单卡数值的均值与范围，不把多卡完成数当成单卡吞吐。service和deadline统计纳入窗口内释放、窗口后排空完成的任务，另提供仅窗内完成任务的service分布；因此最慢越界完成不会从deadline统计中消失。', '',
             '策略deadline为 end−release>1/3秒；6/30Hz反馈分别为 end−release>1/6或1/30秒。无反馈目标周期的饱和模式不定义反馈deadline。未记录结束的pending不冒充已完成或按零耗时计入。', '',
             '调度采用latest-due，跳过过期release且不堆积旧输入；跳过数和计划release数另列。deadline miss比例的分母是实际完成调用，跳过的release未混入该分母，需同时看跳过比例。policy_only_3Hz为无反馈的真实3Hz对照；30Hz是预录输入到达时钟，不执行env.step。', '',
             '此处使用真实cut5快照重复查询，非成功率评测。w512 Q为四个随机初始化成员，每成员3,781,122参数，仅测速、无训练；D/G0沿用既有π0.5权重。Q在CPU，含动作梯度、S²及投影。每卡共享模型、两个CUDA streams的实测协议以worker记录为准。', '',
             f'预定上下文：{contexts.get("count", "NR")}；实际纳入不同context_id：{len({r["context_id"] for r in latency_samples})}；非预热查询：{counts["included_latency_rows"]}；预热：{counts["warmup_rows"]}。', '',
             '## 查询墙钟', '', '| case | n | context数 | 均值 ms | P95 ms | ≤333.333ms比例 |',
             '|---|---:|---:|---:|---:|---:|']
    for row in latency_rows:
        if row['scope'] == 'all_queries' and row['metric'] == 'wall_seconds':
            lines.append(f"| {row['case']} | {row['n']} | {row['contexts']} | {fmt(row['mean_seconds'],1000)} | {fmt(row['p95_seconds'],1000)} | {fmt(row['within_333ms_fraction'],100)}% |")
    lines.extend(['', '## 每worker频率与deadline', '',
                  '| worker/GPU | mode | role | 窗内完成 | 窗后完成 | 跳过/计划 | 吞吐 Hz | service均值/P95 ms | deadline miss/n |',
                  '|---|---|---|---:|---:|---:|---:|---:|---:|'])
    for row in frequency_rows:
        lines.append(f"| {row['worker_id']}/{row['gpu_index']} | {row['mode']} | {row['role']} | {row['in_window_completed']} | {row['after_window_completed']} | {row['skipped_releases'] if row['skipped_releases'] is not None else 'NR'}/{row['scheduled_count'] if row['scheduled_count'] is not None else 'NR'} | {fmt(row['actual_throughput_hz'])} | {fmt(row['mean_seconds'],1000)} / {fmt(row['p95_seconds'],1000)} | {row['deadline_miss_count'] if row['deadline_miss_count'] is not None else 'NR'}/{row['deadline_n']} |")
    lines.extend(['', '## 跨worker单卡吞吐分布', '', '| mode | role | worker数 | 均值 Hz | 范围 Hz |',
                  '|---|---|---:|---:|---:|'])
    for row in cross_worker:
        lines.append(f"| {row['mode']} | {row['role']} | {row['worker_n']} | {fmt(row['actual_throughput_hz_worker_mean'])} | {fmt(row['actual_throughput_hz_worker_min'])}–{fmt(row['actual_throughput_hz_worker_max'])} |")
    lines.extend(['', '## 覆盖、缺测与来源', '',
                  f'数据问题 {len(issues)} 项；缺失case：{missing_latency_cases or "无"}；缺失worker/mode窗口：{len(missing_frequency)}。缺测NR不填零，部分worker已记录的有效查询仍保留。', '',
                  '[SUMMARY](SUMMARY.json) · [LATENCY](LATENCY.csv) · [FREQUENCY](FREQUENCY.csv) · [CONFIG](CONFIG.json) · [上下文](contexts.json) · [资产](assets.json)', '',
                  '| worker | 主机/GPU/UUID | 终局 | contexts | 原始latency | 原始frequency |',
                  '|---|---|---|---:|---|---|'])
    for worker in workers:
        lines.append(f"| {worker['worker_id']} | {worker['host']} / {worker['gpu_index']} / {worker['gpu_uuid']} | {worker['status']} | {len(worker['context_ids'])} | [latency]({worker['latency_path']}) | [frequency]({worker['frequency_path']}) |")
    write_text(destination / 'REPORT.md', '\n'.join(lines) + '\n')
    print(json.dumps(dict(status=summary['status'], output=str(destination), counts=dict(counts),
                          issues=len(issues)), ensure_ascii=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(Path(__file__).with_name('CONFIG.json')))
    parser.add_argument('--output')
    arguments = parser.parse_args()
    main(arguments.config, arguments.output)
