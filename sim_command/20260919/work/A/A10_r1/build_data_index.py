"""Read-only historical index. Existing success timing, no image reconstruction."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import zipfile
import numpy as np
from campaign_io import WORK, RESULTS, atomic, heartbeat, sha

OLD = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916')


def index_npz(path, identity, start_step, kind):
    if not path.is_file():
        return {**identity, 'kind': kind, 'path': str(path), 'status': 'missing', 'missing_reason': 'not found'}
    actual_sha = sha(path)
    with np.load(path, allow_pickle=False) as data:
        flags = data['success_flags']
        n = len(data['actions'])
        if flags.shape != (n,) or len(data['rewards']) != n or len(data['physics_states']) != n + 1:
            raise ValueError('Trajectory action/state/time alignment failure: ' + str(path))
        indices = np.flatnonzero(flags)
        first = int(start_step + indices[0] + 1) if len(indices) else None
        keys = list(data.files)
        generated_steps = data['generated_steps'].tolist()
    seal = path.parent / 'complete.json'
    expected = None
    if seal.is_file():
        expected = json.loads(seal.read_text()).get('files', {}).get(path.name)
    if expected is not None and expected != actual_sha:
        raise ValueError('Historical trajectory changed: ' + str(path))
    return {**identity, 'kind': kind, 'status': 'indexed', 'path': str(path), 'sha256': actual_sha,
        'historical_seal_sha256': expected, 'bytes': path.stat().st_size,
        'start_step': start_step, 'end_step': start_step + n, 'actual_executed_steps': n,
        'first_success_step': first, 'first_success_definition': 'start_step + first true action-result index + 1',
        'generated_steps': generated_steps, 'fields': keys,
        'missing_fields': {'observation_ref': 'per-step image/observation not stored in historical trajectory',
            'next_observation_ref': 'no renderer or reconstruction run during inventory',
            'terminated': 'historical done combines causes; native terminated not separable',
            'truncated': 'historical done combines causes; native truncated not separable'},
        'privileged_physics_state_is_observation': False,
        'use': 'timing/action provenance only; insufficient for unfiltered image-based transition training'}


def main():
    heartbeat('indexing existing train600/development source trajectories and a0 repeat0 suffixes on CPU')
    bundle = OLD / 'input_bundles/final_train600_input_v1/manifest.json'
    manifest = json.loads(bundle.read_text())
    datasets = {}
    for name in ('round1_train_full_v1', 'round2_train_full_v1', 'round1_development_full_v1'):
        directory = OLD / 'datasets' / name
        with np.load(directory / 'arrays.npz', allow_pickle=False) as arrays:
            ids, cuts = arrays['episode_id'], arrays['cut_step']
        for key, cut in zip(ids, cuts):
            datasets[str(key)] = int(cut)
    entries = []
    parents = {}
    for index, row in enumerate(manifest['planned_provenance']):
        source = row['episode_id']
        split = row['split']
        if source in parents and parents[source] != split:
            raise ValueError('Original parent crossed splits')
        parents[source] = split
        identity = {'parent_episode_id': source, 'source_id': source, 'task': row['task'], 'split': split,
                    'data_origin': 'historical_train' if split == 'train' else 'historical_development',
                    'round': row['round'], 'bank_version': row['bank_version']}
        entries.append(index_npz(OLD / 'sources' / source / 'trajectory.npz',
                                 {**identity, 'branch_id': 'source_prefix', 'suffix_id': 'none'}, 0, 'source_prefix'))
        if split == 'train' and source in datasets:
            cut = datasets[source]
            # Chosen by source identity and fixed candidate/repeat, never selected by outcome.
            path = OLD / 'rollouts' / ('round' + str(row['round']) + '_labels') / row['bank_version'] / source / f'cut{cut:03d}' / 'a0/repeat_0/trajectory.npz'
            entries.append(index_npz(path, {**identity, 'branch_id': 'a0', 'suffix_id': 'repeat_0'}, cut, 'a0_repeat0_suffix'))
        if index and index % 100 == 0:
            heartbeat(f'indexed {index}/700 historical parents, fixed a0 repeat0 suffix selection')
    target = RESULTS / 'data_access_v1'
    target.mkdir(parents=True, exist_ok=False)
    records = target / 'existing_trajectory_index.jsonl'
    records.write_text(''.join(json.dumps(x, ensure_ascii=False, allow_nan=False) + '\n' for x in entries))
    registered = {r['episode_id']: r for r in manifest['registered_manifest']}
    split_rows = [{'parent_episode_id': source, 'source_id': source, 'split': split,
                   'task': registered[source]['task'], 'env_seed': registered[source]['env_seed']}
                  for source, split in sorted(parents.items())]
    atomic(target / 'parent_splits.json', {'rows': split_rows, 'historical_revealed_held_included': False})
    access = {'version': 'historical-access-v1', 'status': 'CPU_index_complete_with_explicit_field_gaps',
        'input_bundle': {'path': str(bundle), 'sha256': sha(bundle)},
        'index': {'path': str(records), 'sha256': sha(records)},
        'parent_splits': {'path': str(target / 'parent_splits.json'), 'sha256': sha(target / 'parent_splits.json')},
        'indexed_parent_count': len(parents), 'indexed_trajectory_count': len(entries),
        'kind_counts': dict(Counter(x['kind'] for x in entries)),
        'status_counts': dict(Counter(x['status'] for x in entries)),
        'coverage': '700 planned train/development source prefixes; exactly a0 repeat0 suffix for each of 600 train parents; other candidate/repeat trajectories are not claimed indexed',
        'first_success_observed_trajectories': sum(x.get('first_success_step') is not None for x in entries),
        'first_success_missing_reason': 'null means no true success in this indexed executed segment, not a fabricated whole-episode outcome',
        'common_data_root': str(OLD), 'raw_pool_status': 'new common raw pool not collected; requires later finite release',
        'new_training_from_test': False, 'resource_counts': {'simulator_attempts': 0, 'vla_sampling_calls': 0, 'optimizer_updates': 0},
        'views': [
            {'method': 'E1-core', 'target': 'BCE + a*gain + 0.5*b*pair', 'source_count': 600,
             'input': str(bundle), 'raw_image_requirement': False, 'recollection_required': False},
            {'method': 'VLA-Corrector-adapted', 'target': 'normal demonstration token latent transition',
             'source_count': None, 'missing_reason': 'token cache missing; use existing MT50 demonstrations and later one shared extraction release'},
            {'method': 'GAF-v1-adapted', 'target': 'discounted success-to-go / MSE',
             'source_count': None, 'missing_reason': 'B10 freezes view; action/success timing available but images/next flags incomplete; common raw pool pending'}]}
    atomic(target / 'DATA_ACCESS_READY.json', access)
    print(json.dumps({k: access[k] for k in ('indexed_parent_count', 'indexed_trajectory_count', 'kind_counts', 'status_counts', 'first_success_observed_trajectories')}))


if __name__ == '__main__':
    main()
