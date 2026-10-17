"""Aggregate only the new native-feedback + Q timing case, using stdlib on CPU.

Usage: /usr/bin/python analyze.py [--config CONFIG.json] [--output DIRECTORY]
Prior N/no-intervention measurements are cited separately and never re-counted.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path


CASE = 'parallel_feedback_with_Q'
METRICS = ('wall_seconds', 'policy_seconds', 'feedback_seconds', 'q_seconds')
BUDGET = 1 / 3


def number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def stats(values):
    if not values:
        return dict(n=0, mean_seconds=None, p95_seconds=None)
    ordered = sorted(values)
    position = (len(ordered) - 1) * .95
    lower, upper = math.floor(position), math.ceil(position)
    return dict(n=len(values), mean_seconds=math.fsum(values) / len(values),
                p95_seconds=ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower))


def read_json(path, issues, required=False):
    if not path.exists() and not required:
        return None
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError('expected JSON object')
        return value
    except (ValueError, OSError) as error:
        issues.append(dict(issue='unreadable_json', path=str(path), error=str(error)))
        return None


def resolve(value, parent):
    path = Path(value)
    return path if path.is_absolute() else (parent / path).resolve()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(text)
    temp.replace(path)


def main(config_path, output=None):
    config_path = Path(config_path).resolve()
    issues = []
    config = read_json(config_path, issues, required=True)
    if config is None:
        raise ValueError('Cannot read configuration: ' + str(config_path))
    root = config_path.parent
    destination = Path(output).resolve() if output else root
    reference_path = resolve(config.get('reference_summary',
        '../smol_x_native_feedback_latency_20260926/SUMMARY.json'), root)
    previous = read_json(reference_path, issues, required=True) or {}
    samples, workers, source_records = [], [], []
    counts, counts_by_kind = Counter(), defaultdict(Counter)
    seen = set()
    for index, entry in enumerate(config.get('workers', [])):
        if isinstance(entry, str):
            worker_path = resolve(entry, root)
            cfg = read_json(worker_path, issues, required=True)
        elif isinstance(entry, dict) and 'output' in entry:
            cfg, worker_path = entry, config_path
        else:
            worker_path = resolve(entry.get('config', entry.get('config_path')), root)
            cfg = read_json(worker_path, issues, required=True)
        if cfg is None:
            continue
        out = resolve(cfg['output'], worker_path.parent)
        terminal = read_json(out / 'RESULT.json', issues) or {}
        identity = dict(kind=cfg.get('kind', 'unknown'), worker_id=cfg.get('worker_id', index),
                        gpu_index=cfg.get('gpu_index', index), gpu_uuid=cfg.get('gpu_uuid') or 'unknown',
                        host=cfg.get('host', config.get('host', 'unknown')))
        worker = dict(**identity, status=terminal.get('status', 'missing'),
                      error=terminal.get('error'), output=str(out), config=str(worker_path),
                      result_path=str(out / 'RESULT.json'), timings_path=str(out / 'latency.jsonl'),
                      rows=0, warmups=0, included=0, excluded=0)
        workers.append(worker)
        timing = out / 'latency.jsonl'
        if not timing.exists():
            continue
        local_sources = defaultdict(Counter)
        for line_no, text in enumerate(timing.read_text().splitlines(), 1):
            if not text.strip():
                continue
            worker['rows'] += 1
            counts['latency_rows'] += 1
            counts_by_kind[identity['kind']]['latency_rows'] += 1
            try:
                row = json.loads(text)
                if not isinstance(row, dict):
                    raise ValueError('expected object')
            except (ValueError, TypeError) as error:
                issues.append(dict(issue='malformed_timing', path=str(timing), line=line_no, error=str(error)))
                worker['excluded'] += 1
                counts['malformed_rows'] += 1
                continue
            rep = row.get('repetition')
            sid = row.get('context_id')
            if bool(row.get('warmup')) or (isinstance(rep, int) and rep < 0):
                worker['warmups'] += 1
                counts['warmup_rows'] += 1
                counts_by_kind[identity['kind']]['warmup_rows'] += 1
                local_sources[sid]['warmups'] += 1
                continue
            key = (identity['kind'], sid, rep)
            reason = None
            if row.get('case') != CASE:
                reason = 'unplanned_case'
            elif row.get('kind') != identity['kind'] or str(row.get('gpu_index')) != str(identity['gpu_index']):
                reason = 'identity_mismatch'
            elif sid is None or not isinstance(rep, int) or isinstance(rep, bool):
                reason = 'invalid_context_or_repetition'
            elif key in seen:
                reason = 'duplicate_kind_context_repetition'
            elif not number(row.get('wall_seconds')):
                reason = 'missing_measured_outer_wall'
            if reason:
                issues.append(dict(issue=reason, path=str(timing), line=line_no, context_id=sid, repetition=rep))
                worker['excluded'] += 1
                counts['excluded_rows'] += 1
                local_sources[sid]['excluded'] += 1
                continue
            seen.add(key)
            for metric in METRICS[1:]:
                if not number(row.get(metric)):
                    issues.append(dict(issue='missing_or_invalid_component', metric=metric,
                                       kind=identity['kind'], context_id=sid, repetition=rep))
            samples.append(dict(**identity, context_id=sid, repetition=rep, case=CASE,
                                **{metric: row.get(metric) for metric in METRICS}))
            worker['included'] += 1
            counts['included_latency_rows'] += 1
            counts_by_kind[identity['kind']]['included_latency_rows'] += 1
            local_sources[sid]['included'] += 1
        for sid, value in sorted(local_sources.items(), key=lambda item: str(item[0])):
            source_records.append(dict(**identity, context_id=sid, worker_status=worker['status'],
                                       counts=dict(value), timings_path=str(timing)))
    kinds = sorted({w['kind'] for w in workers})
    expected = config.get('expected_latency_samples_per_case_per_kind', 100)
    for kind in kinds:
        actual = sum(r['kind'] == kind for r in samples)
        if actual != expected:
            issues.append(dict(issue='sample_coverage_mismatch', kind=kind, expected=expected, actual=actual))
    latency = []
    for kind in kinds:
        for worker in [None] + [w for w in workers if w['kind'] == kind]:
            selected = [r for r in samples if r['kind'] == kind
                        and (worker is None or r['worker_id'] == worker['worker_id'])]
            identity = dict(scope='all_queries', kind=kind, worker_id='', gpu_index='', gpu_uuid='', host='') if worker is None else dict(
                scope='worker', **{k: worker[k] for k in ('kind', 'worker_id', 'gpu_index', 'gpu_uuid', 'host')})
            for metric in METRICS:
                values = [r[metric] for r in selected if number(r.get(metric))]
                row = dict(**identity, batch='new_Q_only', case=CASE, metric=metric,
                           contexts=len({r['context_id'] for r in selected}), **stats(values),
                           within_333ms_count=None, within_333ms_fraction=None)
                if metric == 'wall_seconds':
                    row['within_333ms_count'] = sum(v <= BUDGET for v in values)
                    row['within_333ms_fraction'] = row['within_333ms_count'] / len(values) if values else None
                latency.append(row)
    historical = []
    for kind in kinds:
        for case in ('N', 'parallel_feedback_no_intervention'):
            records = [r for r in previous.get('latency', []) if r.get('scope') == 'all_queries'
                       and r.get('kind') == kind and r.get('case') == case and r.get('metric') == 'wall_seconds']
            if len(records) != 1:
                issues.append(dict(issue='missing_or_ambiguous_historical_reference', kind=kind, case=case))
                continue
            historical.append(dict(records[0], batch='historical_reused_not_counted',
                                   source_summary=str(reference_path), source_status=previous.get('status')))
    status = 'complete' if workers and all(w['status'] == 'complete' for w in workers) and not issues else 'partial'
    summary = dict(schema_version=1, generated_utc=datetime.now(timezone.utc).isoformat(), status=status,
                   config=str(config_path), case=CASE, counts=dict(counts),
                   counts_by_kind={kind: dict(c) for kind, c in counts_by_kind.items()},
                   expected_samples_per_kind=expected, workers=workers, sources=source_records,
                   latency=latency, historical_comparisons=historical, issues=issues,
                   measured_wall='Outer wall_seconds only; never reconstructed as sum/max of components',
                   q_time='Measured q_seconds from the same new query; not inferred from batch-to-batch latency differences',
                   feedback_time='Includes native visual/DG monitoring and may include feature CPU transfer before Q',
                   quantile='numpy-compatible linear interpolation at (n-1)*0.95', threshold_seconds=BUDGET,
                   partial_policy='Retain valid measured rows from partial/failed workers, disclose status and coverage',
                   Q=dict(members=4, hidden_width=512, parameters_per_member=3781122,
                          total_parameters=15124488, device='CPU', dtype='float32', threads=2,
                          initialization='random, no training', input_features='16 visual + 8 language + 37 other =61',
                          residual_scale=[.15, .15, .15, .4] * 10,
                          S_source='each native saved postprocessor derivative/std, not pi05',
                          correction='Q action gradient, native saved action std S squared, project_solo'),
                   random_DG0=True, native_features=True, training_updates=0)
    write(destination / 'SUMMARY.json', json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    columns = ['batch', 'scope', 'kind', 'worker_id', 'host', 'gpu_index', 'gpu_uuid', 'case', 'metric',
               'contexts', 'n', 'mean_seconds', 'p95_seconds', 'within_333ms_count', 'within_333ms_fraction', 'source_summary']
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(latency + historical)
    write(destination / 'LATENCY.csv', stream.getvalue())

    def fmt(value, scale=1):
        return 'NR' if value is None else f'{value * scale:.3f}'

    lines = ['# SmolVLA / X-VLA 原生并行反馈＋Q延时', '',
             f'汇总时间：{summary["generated_utc"]}；状态：{status}。', '',
             f'本次仅新增 `{CASE}`：有效查询{counts["included_latency_rows"]}条，预热{counts["warmup_rows"]}条。未重跑N、monitor、无纠偏并行或频率实验。', '',
             '策略与原生完整D/G0反馈同卡并行，二者完成后执行CPU Q纠偏。主指标是外层直接实测墙钟；P95按逐条墙钟linear插值，未以分项和或最大值替代。feedback_seconds可包含供Q使用的特征CPU传输；q_seconds是本条查询实际计时的Q段，不能由新旧批次总耗时之差替代。', '',
             'D/G0沿用上轮随机网络与本底座原生特征。Q新建四个随机w512成员，各3,781,122参数，CPU FP32、2线程；16维视觉＋8维语言＋37维其余输入的预处理也未训练。残差尺度为[0.15,0.15,0.15,0.4]重复10步。Q段包含动作梯度、各自原生保存的postprocessor导数/std构成的S²及project_solo投影，不使用π0.5动作尺度。全部训练0步。', '',
             '两个底座复用相同20个π0.5轨迹保存的真实RGB/本体/原始动作快照，重新计算原生特征，不读取π特征。本结果仅验证此随机网络结构的计算延时，不证明成功率、预测准确性或纠偏有效性。', '',
             '## 本次实测', '', '| 底座 | 指标 | n | contexts | 均值 ms | P95 ms | ≤333.333ms比例 |',
             '|---|---|---:|---:|---:|---:|---:|']
    for row in latency:
        if row['scope'] == 'all_queries':
            within = fmt(row['within_333ms_fraction'], 100) + '%' if row['within_333ms_fraction'] is not None else '—'
            lines.append(f"| {row['kind']} | {row['metric']} | {row['n']} | {row['contexts']} | {fmt(row['mean_seconds'],1000)} | {fmt(row['p95_seconds'],1000)} | {within} |")
    lines.extend(['', '## 上轮对照：历史批次复用，不计入本次样本数', '',
                  f'来源：[上轮SUMMARY]({reference_path})。仅并列不同批次的实际墙钟，不将其差值解释为单独Q成本。', '',
                  '| 底座 | 历史case | n（历史） | 均值 ms | P95 ms |', '|---|---|---:|---:|---:|'])
    for row in historical:
        lines.append(f"| {row['kind']} | {row['case']} | {row['n']} | {fmt(row['mean_seconds'],1000)} | {fmt(row['p95_seconds'],1000)} |")
    lines.extend(['', '## 每worker新查询墙钟', '', '| 底座/worker/GPU | n | 均值 ms | P95 ms |',
                  '|---|---:|---:|---:|'])
    for row in latency:
        if row['scope'] == 'worker' and row['metric'] == 'wall_seconds':
            lines.append(f"| {row['kind']}/{row['worker_id']}/{row['gpu_index']} | {row['n']} | {fmt(row['mean_seconds'],1000)} | {fmt(row['p95_seconds'],1000)} |")
    lines.extend(['', '## 完成状态与证据', '',
                  f'数据问题{len(issues)}项，详见SUMMARY.issues。技术失败/partial状态保留；已写出的有效计时保留，缺测NR不填0。', '',
                  '[SUMMARY](SUMMARY.json) · [LATENCY.csv](LATENCY.csv) · [CONFIG](CONFIG.json)', '',
                  '| 底座/worker | 终局 | 纳入/预热/排除 | 原始计时 | RESULT |', '|---|---|---:|---|---|'])
    for worker in workers:
        lines.append(f"| {worker['kind']}/{worker['worker_id']} | {worker['status']} | {worker['included']}/{worker['warmups']}/{worker['excluded']} | [latency]({worker['timings_path']}) | [RESULT]({worker['result_path']}) |")
    write(destination / 'REPORT.md', '\n'.join(lines) + '\n')
    print(json.dumps(dict(status=status, output=str(destination), counts=dict(counts), issues=len(issues)), ensure_ascii=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(Path(__file__).with_name('CONFIG.json')))
    parser.add_argument('--output')
    args = parser.parse_args()
    main(args.config, args.output)
