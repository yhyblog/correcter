"""Resolve A's published Full dependency without launching or modifying A work."""
import json
from pathlib import Path


def resolve(campaign):
    root = Path(campaign) / 'results/A/A_D24_LIBERO_FULL_NATIVE_V1'
    path = root / 'FINAL_SUMMARY.json'
    delivery_path = root / 'FINAL_DELIVERY.json'
    delivery = None
    if delivery_path.exists():
        delivery = json.loads(delivery_path.read_text())
        if delivery.get('task_id') != 'A_D24_LIBERO_FULL_NATIVE_V1':
            raise ValueError('A Full delivery task mismatch')
        path = Path(delivery['artifacts']['FINAL_SUMMARY'])
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('A Full summary outside its result directory')
    data = json.loads(path.read_text()) if path.exists() else None
    if delivery and (not data or data.get('task_id') != delivery['task_id']
                     or data.get('status') != delivery['status']):
        raise ValueError('A Full delivery and summary do not agree')
    return path, data


def rows(data, path):
    data = data or {}
    gap = data.get('status') == 'SCIENTIFIC_GAP' and bool(data.get('scientific_gap'))
    result = []
    for method in ('Full-Post', 'Full-Velocity'):
        phase = data.get('phases', {}).get(method, {})
        n = phase.get('valid', 0)
        wins = phase.get('successes', 0)
        accepted = bool(data.get('Full_claimed'))
        status = ('scientific_gap_Full_unavailable' if gap else
                  'published_full' if accepted and n == 400 else
                  'pending_or_unavailable_Full')
        result.append(dict(
            setting='pi05 official / LIBERO native Full', method=method, planned=400,
            valid=n, successes=wins if n else None,
            success_rate_pct=100 * wins / n if n else None, status=status,
            observed_snapshot_status=data.get('status', 'not_published'),
            Full_claimed=accepted,
            protocol=data.get('protocol', 'D2/age2/G0 old3-fresh3_then_native5/C5/nativeK5'),
            source_path=str(path)))
    return result


def report_note(data, path):
    note = ('A 的 native Full-LIBERO 独立列在 E8_FULL_NATIVE_TABLE.csv，采用 '
            'D2/age2/G0-execute3_then_native5/C5 等原生时距。按 FINAL_DELIVERY.json '
            '引用的版本读取发布结果；保留实际 status/valid/Full_claimed，不用 B 算子结果替代。')
    if data and data.get('status') == 'SCIENTIFIC_GAP' and data.get('scientific_gap'):
        reasons = '; '.join(data['scientific_gap'].get('reasons', []))
        note += (f'本次 A 发布为 SCIENTIFIC_GAP：{reasons}。Full 单元的有效数为 0 时'
                 f'成功数和成功率留空，未进入测试不计为任务失败。来源：{path}。')
    return note
