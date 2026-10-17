"""CPU-only aggregation of the finite inference benchmark; standard library only.

Usage: /usr/bin/python analyze.py [--config CONFIG.json] [--output DIRECTORY]
Raw records are never modified. Only terminal complete sources enter latency tables.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path


QUERY_METRICS = ('policy_seconds', 'query_seconds', 'query_wall_seconds')
POST_METRICS = ('objective_seconds', 'gradient_seconds', 'projection_seconds',
                'post_extra_seconds')
METHODS = ('N', 'R', 'Post')


def quantile_linear(values, q=.95):
    """Equivalent to numpy.quantile(values, q, method='linear')."""
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def load(path, issues, required=False):
    if not path.exists() and not required:
        return None
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError('expected a JSON object')
        return value
    except (OSError, ValueError) as error:
        issues.append(dict(path=str(path), issue='unreadable_json', error=str(error)))
        return None


def resolve(value, parent):
    path = Path(value)
    return path if path.is_absolute() else (parent / path).resolve()


def atomic_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(value)
    temporary.replace(path)


def csv_text(rows):
    columns = ['scope', 'kind', 'method', 'host', 'gpu_index', 'gpu_uuid',
               'component', 'n', 'sources', 'tasks', 'mean_seconds', 'p95_seconds']
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def main(config_path, output=None):
    config_path = Path(config_path).resolve()
    issues = []
    config = load(config_path, issues, required=True)
    if config is None:
        raise ValueError('Cannot read benchmark configuration: ' + str(config_path))
    destination = Path(output).resolve() if output else config_path.parent
    workers, source_records, accepted, monitor_records = [], [], [], []
    all_kinds, gpu_groups = set(), set()
    sample_counts = defaultdict(Counter)
    global_sources = set()
    for index, entry in enumerate(config.get('workers', [])):
        if isinstance(entry, dict) and 'sources' in entry and 'output' in entry:
            worker_config, worker_path = entry, config_path
        else:
            value = entry if isinstance(entry, str) else next(
                (entry[k] for k in ('config', 'config_path', 'path') if entry.get(k)), None)
            if value is None:
                issues.append(dict(issue='invalid_worker_config_entry', worker_index=index))
                continue
            worker_path = resolve(value, config_path.parent)
            worker_config = load(worker_path, issues, required=True)
        if worker_config is None:
            continue
        kind = worker_config.get('kind', worker_config.get('base', 'unknown'))
        host = worker_config.get('host') or config.get('host') or 'unknown'
        gpu = worker_config.get('gpu_index', 'unknown')
        uuid = worker_config.get('gpu_uuid') or 'unknown'
        group = (kind, host, str(gpu), uuid)
        all_kinds.add(kind)
        gpu_groups.add(group)
        worker_out = resolve(worker_config['output'], worker_path.parent)
        worker_result = load(worker_out / 'RESULT.json', issues)
        workers.append(dict(config=str(worker_path), output=str(worker_out), kind=kind,
                            host=host, gpu_index=gpu, gpu_uuid=uuid,
                            result_status=(worker_result or {}).get('status', 'missing'),
                            result_path=str(worker_out / 'RESULT.json')))
        planned = {s['source_id']: s for s in worker_config.get('sources', [])}
        observed = set()
        source_dir = worker_out / 'sources'
        if source_dir.exists():
            for name in ('RESULT.json', 'timings.jsonl', 'CONTEXT.json'):
                observed.update(str(p.parent.relative_to(source_dir)) for p in source_dir.rglob(name))
        for sid in sorted(set(planned) | observed):
            folder = source_dir / sid
            terminal = load(folder / 'RESULT.json', issues)
            context = load(folder / 'CONTEXT.json', issues)
            raw_status = (terminal or {}).get('status')
            status = raw_status or ('partial' if folder.exists() else 'unstarted')
            duplicate_source = (kind, sid) in global_sources
            global_sources.add((kind, sid))
            if duplicate_source:
                issues.append(dict(issue='duplicate_source_identity_excluded', kind=kind,
                                   source_id=sid, path=str(folder)))
            record = dict(kind=kind, source_id=sid, task=planned.get(sid, {}).get('task'),
                          planned=sid in planned, host=host, gpu_index=gpu, gpu_uuid=uuid,
                          status=status, reported_status=raw_status,
                          expected_repetitions=worker_config.get('repetitions', 5),
                          result_path=str(folder / 'RESULT.json'),
                          timings_path=str(folder / 'timings.jsonl'),
                          context_path=str(folder / 'CONTEXT.json'),
                          eligible=(context or {}).get('eligible'),
                          error=(terminal or {}).get('error'),
                          rows_total=0, rows_warmup=0, rows_nonwarmup=0,
                          rows_included=0, rows_excluded=0, malformed_rows=0)
            source_records.append(record)
            timing_path = folder / 'timings.jsonl'
            if not timing_path.exists():
                continue
            seen_queries, monitors = set(), {}
            for line_number, line in enumerate(timing_path.read_text().splitlines(), 1):
                if not line.strip():
                    continue
                record['rows_total'] += 1
                try:
                    row = json.loads(line)
                    rep = row['repetition']
                    method = row['method']
                    if not isinstance(rep, int) or isinstance(rep, bool):
                        raise ValueError('repetition must be integer')
                    warmup = bool(row.get('warmup', rep < 0)) or rep < 0
                except (ValueError, KeyError, TypeError) as error:
                    record['malformed_rows'] += 1
                    sample_counts[kind]['malformed_rows'] += 1
                    issues.append(dict(issue='malformed_timing_row', path=str(timing_path),
                                       line=line_number, error=str(error)))
                    continue
                record['rows_warmup' if warmup else 'rows_nonwarmup'] += 1
                sample_counts[kind]['warmup_rows' if warmup else 'nonwarmup_rows'] += 1
                exclusion = None
                if warmup:
                    exclusion = 'warmup'
                elif status != 'complete':
                    exclusion = 'source_' + status
                elif sid not in planned or duplicate_source:
                    exclusion = 'unplanned_or_duplicate_source'
                elif row.get('source_id') != sid or row.get('kind') != kind or str(row.get('gpu_index')) != str(gpu):
                    exclusion = 'identity_mismatch'
                elif method not in METHODS or not 0 <= rep < record['expected_repetitions']:
                    exclusion = 'unplanned_method_or_repetition'
                elif (rep, method) in seen_queries:
                    exclusion = 'duplicate_query'
                if exclusion:
                    record['rows_excluded'] += 1
                    sample_counts[kind]['excluded_' + exclusion] += 1
                    continue
                seen_queries.add((rep, method))
                record['rows_included'] += 1
                sample_counts[kind]['included_queries'] += 1
                accepted.append(dict(row=row, group=group, source_id=sid,
                                     task=row.get('task') or record['task']))
                monitor = row.get('monitor')
                if isinstance(monitor, dict):
                    if rep in monitors:
                        sample_counts[kind]['monitor_duplicate_copies_not_recounted'] += 1
                        if monitor != monitors[rep]:
                            issues.append(dict(issue='inconsistent_monitor_copies', kind=kind,
                                               source_id=sid, repetition=rep))
                            monitors[rep] = None
                    else:
                        monitors[rep] = monitor
                else:
                    sample_counts[kind]['rows_missing_monitor'] += 1
            for rep, monitor in monitors.items():
                if monitor is not None:
                    monitor_records.append(dict(group=group, source_id=sid, task=record['task'],
                                                repetition=rep, monitor=monitor))
                    sample_counts[kind]['unique_monitor_measurements'] += 1
            if status == 'complete':
                expected = record['expected_repetitions'] * len(METHODS)
                record['missing_measured_queries'] = max(0, expected - len(seen_queries))
                if len(seen_queries) != expected:
                    issues.append(dict(issue='complete_source_query_coverage_mismatch', kind=kind,
                                       source_id=sid, expected=expected, actual=len(seen_queries)))

    # Each bucket retains the source and task associated with every measurement.
    buckets = defaultdict(list)
    expected_buckets = set()
    monitor_names = {key for item in monitor_records for key, value in item['monitor'].items()
                     if key.endswith('_seconds') and isinstance(value, (int, float))
                     and not isinstance(value, bool)}
    ignored_monitor_array_fields = sorted({key for item in monitor_records
                                           for key, value in item['monitor'].items()
                                           if key.endswith('_seconds') and isinstance(value, (list, tuple))})
    for kind in all_kinds:
        for scope, host, gpu, uuid in [('all', '', '', '')] + [
                ('gpu', h, g, u) for k, h, g, u in sorted(gpu_groups) if k == kind]:
            for method in METHODS:
                for metric in QUERY_METRICS:
                    expected_buckets.add(('query', scope, kind, method, host, gpu, uuid, metric))
            for metric in POST_METRICS:
                expected_buckets.add(('component', scope, kind, 'Post', host, gpu, uuid, metric))
            for metric in monitor_names:
                expected_buckets.add(('component', scope, kind, 'monitor', host, gpu, uuid, metric))

    def add(category, item, method, metric, value):
        kind, host, gpu, uuid = item['group']
        if not number(value):
            sample_counts[kind]['missing_or_invalid_' + method + '_' + metric] += 1
            return
        for scope, h, g, u in [('all', '', '', ''), ('gpu', host, gpu, uuid)]:
            key = (category, scope, kind, method, h, g, u, metric)
            buckets[key].append((float(value), item['source_id'], item['task']))

    for item in accepted:
        row, method = item['row'], item['row']['method']
        for metric in QUERY_METRICS:
            add('query', item, method, metric, row.get(metric))
        if method == 'Post':
            components = row.get('post') or {}
            for metric in POST_METRICS[:-1]:
                add('component', item, method, metric, components.get(metric))
            extra = (row['query_seconds'] - row['policy_seconds']) if (
                number(row.get('query_seconds')) and number(row.get('policy_seconds'))) else None
            add('component', item, method, 'post_extra_seconds', extra)
    for item in monitor_records:
        for metric in monitor_names:
            add('component', item, 'monitor', metric, item['monitor'].get(metric))
    query_rows, component_rows = [], []
    for key in sorted(expected_buckets | set(buckets)):
        category, scope, kind, method, host, gpu, uuid, metric = key
        values = buckets[key]
        data = [v[0] for v in values]
        row = dict(scope=scope, kind=kind, method=method, host=host, gpu_index=gpu,
                   gpu_uuid=uuid, component=metric, n=len(data),
                   sources=len({v[1] for v in values}), tasks=len({v[2] for v in values}),
                   mean_seconds=math.fsum(data) / len(data) if data else None,
                   p95_seconds=quantile_linear(data))
        (query_rows if category == 'query' else component_rows).append(row)
    source_counts = {}
    for kind in sorted(all_kinds):
        records = [r for r in source_records if r['kind'] == kind]
        statuses = Counter(r['status'] for r in records)
        source_counts[kind] = dict(planned=sum(r['planned'] for r in records),
                                  observed=sum(r['status'] != 'unstarted' for r in records),
                                  complete=statuses['complete'],
                                  early_terminal=statuses['ineligible_cut'],
                                  technical_failure=statuses['technical_failure'],
                                  partial=statuses['partial'], unstarted=statuses['unstarted'],
                                  status_counts=dict(statuses),
                                  completed_tasks=sorted({r['task'] for r in records
                                                          if r['status'] == 'complete' and r['task']}),
                                  nonwarmup_rows_from_incomplete_sources=sum(r['rows_nonwarmup'] for r in records
                                                                          if r['status'] != 'complete'))
    has_missing = (bool(issues) or not monitor_names
                   or any(r['status'] not in ('complete', 'ineligible_cut') for r in source_records)
                   or any(key.startswith('missing_or_invalid_') and value
                          for counts in sample_counts.values() for key, value in counts.items()))
    summary = dict(schema_version=1, generated_utc=datetime.now(timezone.utc).isoformat(),
                   config=str(config_path), status='partial' if has_missing or not accepted else 'complete',
                   analysis_only=True, training_updates=0,
                   quantile='linear: sorted[(n-1)*0.95], interpolating adjacent order statistics',
                   inclusion='planned sources with RESULT.status complete; nonwarmup unique method/repetition rows',
                   monitor_deduplication='one observation per kind/source/repetition; inconsistent copies excluded',
                   SOURCE_COUNTS=source_counts, SAMPLE_COUNTS={k: dict(v) for k, v in sample_counts.items()},
                   workers=workers, sources=source_records, query_latency=query_rows,
                   component_latency=component_rows, issues=issues,
                   missing_monitor_components=not bool(monitor_names),
                   ignored_monitor_array_fields=ignored_monitor_array_fields)
    atomic_text(destination / 'SUMMARY.json', json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    atomic_text(destination / 'QUERY_LATENCY.csv', csv_text(query_rows))
    atomic_text(destination / 'COMPONENT_LATENCY.csv', csv_text(component_rows))

    def milliseconds(value):
        return 'NR' if value is None else f'{value * 1000:.3f}'

    lines = ['# 小批量推理效率补测', '',
             f'汇总时间：{summary["generated_utc"]}；数据状态：{summary["status"]}。', '',
             '仅纳入源 RESULT.json 标记 complete 的非预热查询；技术失败或未结束源已经写出的计时保留在原始文件，排除数量另列。缺测为 NR，不填零。', '',
             '统计量为逐查询算术均值和 P95（与 NumPy quantile 的 linear 插值一致）。重复查询不是独立环境初态；源覆盖与查询 n 同时报告。', '',
             'N/R 计算时间覆盖原生预处理、完整采样与反归一化；Post 另含 Q objective、动作梯度及投影。Post extra 为每条 Post 记录的 query_seconds − policy_seconds 后再汇总，不是不同方法均值相减。', '',
             '监测单独报告，每个源、每次 repetition 在 N/R/Post 中重复存储的 monitor 只计一次。Post 查询不含前置监测，完整辅助开销需结合监测表；分项可能包含/重叠，不能全部机械相加，更不能相加 P95。wall 是逐查询完整调用墙钟，包含该调用通信，不含单独 monitor。', '',
             '模型加载、环境步进、渲染和预热不计入查询分布。Q 在 CPU，原生 GPU 计时边界同步。每卡 batch size 1，当前批次的每 GPU 汇总用于观察设备/上下文差异，不作跨主机性能校正。', '',
             '## 源覆盖', '',
             '| 底座 | 计划 | 完成 | cut前终止 | 技术失败 | partial | 未开始 | 未完整源非预热行 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for kind, counts in source_counts.items():
        lines.append('| ' + ' | '.join(str(v) for v in [kind, counts['planned'], counts['complete'],
                     counts['early_terminal'], counts['technical_failure'], counts['partial'],
                     counts['unstarted'], counts['nonwarmup_rows_from_incomplete_sources']]) + ' |')
    for title, rows in [('查询耗时', query_rows), ('纠偏与监测组件', component_rows)]:
        lines.extend(['', '## ' + title, '', '| 底座 | 方法/组件 | n | 源数 | 均值 ms | P95 ms |',
                      '|---|---|---:|---:|---:|---:|'])
        for row in rows:
            if row['scope'] == 'all':
                lines.append(f"| {row['kind']} | {row['method']} / {row['component']} | {row['n']} | {row['sources']} | {milliseconds(row['mean_seconds'])} | {milliseconds(row['p95_seconds'])} |")
    if not monitor_names:
        lines.extend(['', '监测组件：NR，尚无来自完整源的可用 monitor 计时。'])
    if ignored_monitor_array_fields:
        lines.extend(['', '成员时间数组仅保留在原始记录，不作为标量时延分项汇总：'
                      + '、'.join(ignored_monitor_array_fields) + '。D/G0整组的标量耗时仍正常汇总。'])
    lines.extend(['', '## 每 GPU 查询摘要', '',
                  '| 主机 | GPU | UUID | 底座 | 方法 | n | 均值 ms | P95 ms |',
                  '|---|---|---|---|---|---:|---:|---:|'])
    for row in query_rows:
        if row['scope'] == 'gpu' and row['component'] == 'query_seconds':
            lines.append(f"| {row['host']} | {row['gpu_index']} | {row['gpu_uuid']} | {row['kind']} | {row['method']} | {row['n']} | {milliseconds(row['mean_seconds'])} | {milliseconds(row['p95_seconds'])} |")
    lines.extend(['', '## 原始证据与缺测', '',
                  f'[CONFIG]({config_path}) · [SUMMARY.json](SUMMARY.json) · [查询 CSV](QUERY_LATENCY.csv) · [组件 CSV](COMPONENT_LATENCY.csv) · [协议](PROTOCOL.md)', '',
                  f'数据问题记录 {len(issues)} 项，逐项见 SUMMARY.json 的 issues；各类排除/缺字段计数见 SAMPLE_COUNTS。', '',
                  '| 底座 | 源 | 任务 | 状态 | 纳入查询 | 原始计时 | 终局 |',
                  '|---|---|---|---|---:|---|---|'])
    for record in source_records:
        timing_link = f"[timings]({record['timings_path']})" if Path(record['timings_path']).exists() else 'NR'
        result_link = f"[RESULT]({record['result_path']})" if Path(record['result_path']).exists() else 'NR'
        lines.append(f"| {record['kind']} | {record['source_id']} | {record['task']} | {record['status']} | {record['rows_included']} | {timing_link} | {result_link} |")
    atomic_text(destination / 'REPORT.md', '\n'.join(lines) + '\n')
    print(json.dumps(dict(status=summary['status'], output=str(destination),
                          included_queries=len(accepted), monitor_measurements=len(monitor_records),
                          source_counts=source_counts, issues=len(issues)), ensure_ascii=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(Path(__file__).with_name('CONFIG.json')))
    parser.add_argument('--output', help='Defaults to the directory containing CONFIG.json')
    arguments = parser.parse_args()
    main(arguments.config, arguments.output)
