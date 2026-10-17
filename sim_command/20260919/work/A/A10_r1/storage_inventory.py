"""Known VLA paths only. No deletions or guesses that shared inputs are unused."""
from pathlib import Path
import json
from campaign_io import BASE, WORK, atomic, now, heartbeat

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')


def logical_bytes(path):
    if path.is_file(): return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())


def main():
    heartbeat('preparing exact-path storage candidates for analysis; no deletion release exists')
    assets = json.loads((BASE / 'receipts/A/A00_ASSETS.json').read_text())['assets']
    selected = {'pi05_mt50_sft_030000', 'vla_corrector_best_cosine', 'Q_selected_bundle', 'smolvla_partial_50000'}
    candidates = []
    for asset in assets:
        if asset['asset_id'] not in selected: continue
        path = Path(asset['path']); real = path.resolve(strict=True)
        candidates.append({'absolute_path': str(path), 'realpath': str(real),
            'project': 'vla-corrector' if real.is_relative_to(ROOT / 'vla-corrector') else 'Corrector' if real.is_relative_to(ROOT / 'Corrector') else 'vla-baselines/SmolVLA (inventory-confirmed experiment input)',
            'type': 'directory' if real.is_dir() else 'file', 'logical_bytes': logical_bytes(real),
            'purpose': asset['asset_id'], 'completed_or_unused_evidence': 'Completed asset, explicitly required by INVENTORY_DECISIONS_V1; no evidence it is unused',
            'dependency_checks': ['A00_ASSETS.json', 'contracts/INVENTORY_DECISIONS_V1.md', 'current P00 preparation inputs'],
            'replacement_retained_asset': None, 'recommendation': 'keep',
            'risk': 'Deletion removes an explicitly retained model/input; historical audit and future experiments depend on it'})
    checkpoints = ROOT / 'embodied-ai-workspace/artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints'
    for step in range(5000, 50000, 5000):
        path = checkpoints / f'{step:06d}'
        if not path.exists(): continue
        candidates.append({'absolute_path': str(path), 'realpath': str(path.resolve()),
            'project': 'vla-baselines/SmolVLA (ownership needs explicit cleanup-manifest inclusion)',
            'type': 'directory', 'logical_bytes': logical_bytes(path),
            'purpose': f'Historical intermediate SmolVLA step{step}',
            'completed_or_unused_evidence': 'Checkpoint exists; queue previously stopped at 50000. Continued selection/recovery or B dependencies not ruled out.',
            'dependency_checks': ['Final step50000 selected as E8 candidate by analysis',
                                  'Not proven absent from historical seals or B references; no delete recommendation'],
            'replacement_retained_asset': str(checkpoints / '050000'), 'recommendation': 'defer',
            'risk': 'Must check recovery/selection and historical manifest references on both nodes before analysis can approve deletion'})
    atomic(BASE / 'receipts/A/STORAGE_CANDIDATES.json', {'campaign_id': 'corrector-sim-20260919',
        'role': 'A', 'checked_at_utc': now(), 'scope': 'known experiment model paths only; no non-VLA scan',
        'active_deletion_release': None, 'deleted_paths': [], 'deleted_bytes': 0,
        'capacity_receipt': str(WORK / 'node_capacity.json'), 'candidates': candidates,
        'protected_elsewhere': ['MT50/LIBERO raw data', 'all native10/standalone seals and referenced raw trees',
            'D/G0/Q/PCA/normalizers', 'X-VLA initialization', 'LIBERO final inference bundle', 'runtime environments and tokenizer caches'],
        'note': 'keep/defer are executor evidence-based recommendations; only analysis can publish an exact deletion manifest'})
    print({'keep': sum(r['recommendation']=='keep' for r in candidates), 'defer': sum(r['recommendation']=='defer' for r in candidates),
           'deferred_bytes': sum(r['logical_bytes'] for r in candidates if r['recommendation']=='defer'), 'deleted_bytes': 0})


if __name__ == '__main__': main()
