"""Read-only old-bank seed reconstruction for later policy5 preparation.

Checks existing source/bank/branch records against the unchanged keyed seed
functions. Does not generate a new candidate, run any model, or claim that an
unexecuted new bank has already reproduced old noise or physical outcomes.
"""
from collections import Counter
import argparse
import json
from pathlib import Path

import numpy as np

from . import storage
from .protocol import candidate_seed, canonical_hash, seed_for, suffix_seed


def read(path):
    return json.loads(Path(path).read_text())


def check(config_path):
    config = read(config_path)
    registration = config['main_collection']['banks']['round1_labels_v1']
    lookup = {row['episode_id']: row for row in config['episode_manifest']}
    cases = [lookup[key] for key in registration['episode_ids'] if lookup[key]['split'] == 'development']
    assert len(cases) == 100 and set(Counter(row['task'] for row in cases).values()) == {20}
    namespace = config['seed_namespace']
    pairs = [('continue_native10', 'continue_native10'), ('alarm_replan10', 'a0'),
             ('velocity', 'velocity'), ('direct', 'direct'), ('post', 'post')]
    rows, artifacts, suffix_records, branch_count = [], {}, 0, 0
    for case in cases:
        source = storage.ROOT/'sources'/case['case_id']
        summary = read(source/'summary.json')
        artifacts[str(source/'summary.json')] = storage.sha256(source/'summary.json')
        row = dict(episode_id=case['episode_id'], task=case['task'], cuts=summary['cuts'])
        if not summary['cuts']:
            assert summary['no_alarm'] and summary['full_episode_outcome_available']
            assert type(summary['success']) is bool
            row['common_outcome'] = summary['success'];rows.append(row);continue
        cut, = summary['cuts']
        bank = storage.ROOT/'banks/round1_labels_v1'/case['case_id']/f'cut{cut:03d}'
        generation = read(bank/'generation.json')
        artifacts[str(bank/'generation.json')] = storage.sha256(bank/'generation.json')
        assert generation['base_seed'] == candidate_seed(case, cut, namespace=namespace)
        noise = generation['noise_hashes']
        assert set(noise) == {'replan', 'velocity', 'direct'} and len(set(noise.values())) == 1
        assert generation['base_generation']['noise_sha256'] == noise['replan']
        # labels13 preserves formal V/D/P plans unchanged; local-only probes
        # have separate random streams and do not enter the five-arm evaluator.
        with np.load(bank/'plans.npz', allow_pickle=False) as plans, np.load(bank/'formal_directions.npz', allow_pickle=False) as formal:
            base = formal['raw_a0']
            assert plans['a0'].tobytes() == base.tobytes()
            for name in ('velocity', 'direct', 'post'):
                expected = base.copy()
                expected[:10] = (base[:10].astype(float)+formal[name+'_matched_actual_delta']).astype(np.float32)
                assert plans[name].dtype == expected.dtype and plans[name].tobytes() == expected.tobytes()
        schedules, shared_noise = {}, {}
        for policy_name, old_name in pairs:
            for repeat in range(4):
                branch = storage.ROOT/'rollouts/round1_labels/round1_labels_v1'/case['case_id']/f'cut{cut:03d}'/old_name/f'repeat_{repeat}'
                path = branch/'summary.json';saved = read(path)
                assert saved['method'] == old_name and saved['repeat'] == repeat and saved['cut_step'] == cut
                assert saved['paired_suffix_id'] == f"{case['episode_id']}:cut{cut}:repeat{repeat}"
                records = []
                for index, item in enumerate(saved['suffix_seeds']):
                    assert type(item['decision_index']) is int and item['decision_index'] == index
                    assert item['seed'] == suffix_seed(case, cut, repeat, index, namespace=namespace)
                    key = (repeat, index);digest = item['noise_sha256']
                    assert isinstance(digest, str) and len(digest) == 64
                    if key in shared_noise:
                        assert shared_noise[key] == digest
                    shared_noise[key] = digest
                    records.append(dict(index=index, seed=item['seed'], noise_sha256=digest))
                    suffix_records += 1
                schedules[f'{policy_name}:{repeat}'] = records
                artifacts[str(path)] = storage.sha256(path);branch_count += 1
        row.update(base_seed=generation['base_seed'], base_noise_sha256=noise['replan'],
            formal_plans_preserved_bit_exact=True,
            matching_random_seed=seed_for('matching_random', case['task'], case['env_seed'], cut, namespace=namespace),
            old_suffix_records=schedules)
        rows.append(row)
    no_cut = [row for row in rows if not row['cuts']]
    assert len(no_cut) == 5 and sum(row['common_outcome'] for row in no_cut) == 4 and branch_count == 1900
    code = Path(__file__).resolve()
    return dict(status='passed_existing_seed_reconstruction', config_path=str(Path(config_path).resolve()),
        config_sha256=storage.sha256(config_path), code_sha256=storage.sha256(code),
        seed_namespace=namespace, development_sources=100, per_task=dict(Counter(row['task'] for row in cases)),
        reached_sources=95, no_alarm_common_sources=5, common_successes=4, common_failures=1,
        old_branch_summaries_checked=branch_count, actual_old_suffix_records_checked=suffix_records,
        candidate_seed_domain='designated_a0: episode(task,env_seed), cut, candidate_index=0',
        suffix_seed_domain='branch_suffix_decision: episode(task,env_seed), cut, repeat, decision_index',
        arm_critic_bank_worker_abs_time_in_seed=False,
        main_branch_order_domain='main_branch_order: episode_id, cut, bank_version; ordering only',
        old_local13_random_domain='main_local_labels_v1: episode_id, cut; not used by policy5',
        fixed_config_content_sha256=canonical_hash(config), per_source=rows, artifacts=artifacts,
        new_candidates_generated=0, new_branch_outcomes_observed=0, model_calls=0,
        simulator_attempts=0, optimizer_updates=0,
        actual_new_vs_old_noise_verified=False,
        conclusion='Same namespace and keyed functions imply the same intended streams. New raw a0/noise still require runtime checks. Primary policy5 inference remains within the five new arms; no sixth arm.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Use a new independent seed review output directory')
    result = check(args.config)
    storage.dump(args.output/'result.json', result)
    storage.seal(args.output, role='read_only_policy5_seed_preparation', simulator_attempts=0, optimizer_updates=0)
    print(json.dumps({key: result[key] for key in ('status', 'development_sources',
        'old_branch_summaries_checked', 'actual_old_suffix_records_checked', 'actual_new_vs_old_noise_verified')}))
