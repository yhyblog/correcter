"""Read-only audit of a separately released five-arm development deployment.

No simulation, optimizer, candidate search or outcome-dependent source selection.
The original 100 primary slots are mandatory; no-cut known outcomes remain in
the denominator. Missing artifacts stop the audit rather than becoming failures.
This new module is separate from all sealed collection/training implementations.
"""
from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from . import artifact_loader as loader, storage
from .main_collection import POLICY_METHODS
from .protocol import canonical_hash, require_stage_budget, suffix_seed, validate_manifest


BOOTSTRAP_SEED = 2026091622
BOOTSTRAP_REPLICATES = 10000
COMPARISONS = ((1, 0), (2, 1), (3, 1), (4, 1), (2, 0), (3, 0), (4, 0))


def _read(path):
    return json.loads(Path(path).read_text())


def audit_suffix_identities(sequence, case, cut, repeat, namespace, shared_noise):
    for index, decision in enumerate(sequence):
        if type(decision.get('decision_index')) is not int or decision['decision_index'] != index:
            raise ValueError('Suffix decisions must be contiguous zero-based integer indices')
        key = (repeat, index); digest = decision.get('noise_sha256')
        expected_seed = suffix_seed(case, cut, repeat, index, namespace=namespace)
        if (decision.get('seed') != expected_seed or not isinstance(digest, str)
                or len(digest) != 64 or key in shared_noise and shared_noise[key] != digest):
            raise ValueError('Paired suffix seed/noise differs across arms')
        shared_noise[key] = digest


def summarize(outcomes, rows, *, bootstrap_replicates=BOOTSTRAP_REPLICATES):
    """Task-stratified source bootstrap; repeats are paired within each source."""
    values = np.asarray(outcomes)
    if (values.shape != (len(rows), 5, 4) or not len(rows)
            or not np.isin(values, [0, 1]).all()
            or len({row['episode_id'] for row in rows}) != len(rows)):
        raise ValueError('Require unique complete source x five-arm x four-repeat labels')
    if type(bootstrap_replicates) is not int or bootstrap_replicates < 1:
        raise ValueError('Bootstrap count must be positive')
    values = values.astype(np.float64)
    tasks = np.array([row['task'] for row in rows])
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    indices = np.concatenate([rng.choice(np.flatnonzero(tasks == task),
        (bootstrap_replicates, int((tasks == task).sum())), replace=True)
        for task in sorted(set(tasks))], axis=1)

    def group(mask):
        data = values[mask]
        if not len(data):
            return {'sources': 0}
        return dict(sources=len(data), logical_outcomes_per_arm=len(data)*4,
            success_counts=dict(zip(POLICY_METHODS, data.sum((0, 2)).astype(int).tolist())),
            success_rates=dict(zip(POLICY_METHODS, data.mean((0, 2)).tolist())))

    comparisons = {}
    for candidate, baseline in COMPARISONS:
        c, b = values[:, candidate], values[:, baseline]
        delta = (c-b).mean(1)
        comparisons[POLICY_METHODS[candidate]+'_minus_'+POLICY_METHODS[baseline]] = dict(
            gain=float(delta.mean()), source_95ci=np.quantile(delta[indices].mean(1), [.025, .975]).tolist(),
            rescues=int(((c == 1) & (b == 0)).sum()), harms=int(((c == 0) & (b == 1)).sum()),
            positive_sources=int((delta > 0).sum()), negative_sources=int((delta < 0).sum()),
            zero_sources=int((delta == 0).sum()))
    return dict(overall=group(np.ones(len(rows), bool)), comparisons=comparisons,
        per_task={task: group(tasks == task) for task in sorted(set(tasks))},
        alarm_conditioned=group(np.array([not row['no_cut'] for row in rows])),
        no_cut_common_outcomes=group(np.array([row['no_cut'] for row in rows])),
        bootstrap=dict(seed=BOOTSTRAP_SEED, replicates=bootstrap_replicates,
            unit='episode/source', stratification='task', suffix_repeats_independent=False,
            interval='percentile', multiplicity_adjusted=False),
        independent_validation_success=False,
        interpretation='Development policy comparison; seven descriptive paired comparisons, not heldout confirmation.')


def audit(config, bank_version):
    from .policy_deployment_v1 import validate_deployment_inputs, verify_bank_anchor
    registration = config['main_collection']['banks'][bank_version]
    stage = registration['stage']
    require_stage_budget(config, stage)  # Explicit later deployment release, before outcomes.
    inputs = validate_deployment_inputs(config, bank_version)
    old = _read(config['policy_deployment']['old_collection']['config_path'])
    old_bank = config['policy_deployment']['old_collection']['bank_version']
    old_registration = old['main_collection']['banks'][old_bank]
    protocol = config['analysis_approval']['protocol_sha256']
    raw_ledger, ledger = loader._ledger_snapshot()
    raw_scenes, scenes = loader._scene_registry_snapshot()
    registry = validate_manifest(config['episode_manifest'])
    artifacts, attempts, old_source_attempts, rows, labels = {}, [], [], [], []
    for episode_id in inputs['episode_ids']:
        bound = inputs['sources'][episode_id]
        case = registry[episode_id]
        source = Path(bound['source_path'])
        summary, source_data, contexts, queues, source_attempt = loader._source(
            case, source, old_registration, old, ledger, artifacts, scenes)
        old_source_attempts.append(source_attempt)
        folder = storage.ROOT/'collections'/stage/bank_version/case['case_id']
        loader._sealed(folder, [protocol], 'collection', artifacts)
        collection = _read(folder/'summary.json')
        provenance = dict(episode_id=episode_id, case_id=case['case_id'], task=case['task'],
            env_seed=case['env_seed'], split=case['split'], round=case.get('round'),
            generation_round=registration['generation_round'], planned_slot_id=episode_id,
            bank_version=bank_version, bank_kind='policy5', stage=stage,
            source_protocol_sha256=inputs['old_protocol_sha256'],
            source_seal_sha256=bound['source_seal_sha256'], model_hashes=registration['model_hashes'],
            protocol_sha256=protocol, critic_member_hashes=registration['critic_member_hashes'],
            generation_critic_sha256=canonical_hash(registration['critic_member_hashes']),
            suffix_seed_namespace=config['seed_namespace'], suffix_protocol='native10_first_ten_raw_commands_v1')
        if (any(collection.get(key) != value for key, value in provenance.items())
                or collection.get('status') != 'complete' or collection.get('no_cut') != (not summary['cuts'])
                or collection.get('logical_branch_count') != 20
                or collection.get('case') != case or collection.get('methods') != list(POLICY_METHODS)
                or collection.get('replicates') != 4 or collection.get('cuts') != summary['cuts']
                or collection.get('source_seal_sha256') != bound['source_seal_sha256']
                or collection.get('model_hashes') != registration['model_hashes']
                or collection.get('planned_episode_retained') is not True
                or collection.get('outcome_filter_applied') is not False):
            raise ValueError('Deployment collection/source identity differs')
        outcome = np.empty((5, 4), bool)
        if summary['cuts']:
            cut = summary['cuts'][0]
            bank = storage.ROOT/'banks'/bank_version/case['case_id']/f'cut{cut:03d}'
            loader._sealed(bank, [protocol], 'bank', artifacts)
            verify_bank_anchor(bank, bound)
            generation = _read(bank/'generation.json')
            plans = loader._npz(bank/'plans.npz')
            expected_identity = dict(provenance,
                candidate_bank_sha256=storage.sha256(bank/'complete.json'))
            if (set(plans) != set(POLICY_METHODS[1:])
                    or collection.get('candidate_bank_sha256') != expected_identity['candidate_bank_sha256']
                    or any(generation.get(key) != value for key, value in expected_identity.items()
                           if key != 'candidate_bank_sha256')):
                raise ValueError('Deployment bank provenance differs')
            attempts.append(loader._attempt(bank, generation, ledger, kind='candidate_restore', stage=stage,
                protocol=protocol, identity=str(bank.relative_to(storage.ROOT.resolve()))))
            records = collection.get('branch_records', [])
            saved = {(row['method'], row['repeat']): row for row in records}
            expected = {(name, repeat) for name in POLICY_METHODS for repeat in range(4)}
            if len(records) != 20 or set(saved) != expected or collection.get('actual_branch_count') != 20:
                raise ValueError('Five-arm source has incomplete paired branch labels')
            noise = {}
            for arm, name in enumerate(POLICY_METHODS):
                for repeat in range(4):
                    branch = storage.ROOT/'rollouts'/stage/bank_version/case['case_id']/f'cut{cut:03d}'/name/f'repeat_{repeat}'
                    loader._sealed(branch, [protocol], 'branch', artifacts)
                    row = _read(branch/'summary.json'); record = saved[(name, repeat)]
                    if (any(row.get(key) != value for key, value in expected_identity.items())
                            or row.get('method') != name or row.get('candidate_name') != name
                            or row.get('repeat') != repeat or row.get('cut_step') != cut
                            or row.get('status') != 'complete'
                            or row.get('paired_suffix_id') != f'{episode_id}:cut{cut}:repeat{repeat}'
                            or type(row.get('success')) is not bool
                            or record.get('seal_sha256') != storage.sha256(branch/'complete.json')
                            or Path(record.get('summary_path', '')).resolve() != (branch/'summary.json').resolve()
                            or any(record.get(key) != row.get(key) for key in ('success', 'budget_attempt', 'command_sha256'))):
                        raise ValueError('Deployment branch/source/model reference differs')
                    attempts.append(loader._attempt(branch, row, ledger, kind='branch_including_restore',
                        stage=stage, protocol=protocol, identity=str(branch.relative_to(storage.ROOT.resolve()))))
                    loader._branch_trajectory(row, branch, source_data, queues[cut],
                        None if name == POLICY_METHODS[0] else plans[name])
                    audit_suffix_identities(row['suffix_seeds'], case, cut, repeat, config['seed_namespace'], noise)
                    outcome[arm, repeat] = row['success']
        else:
            if (not summary['full_episode_outcome_available'] or type(summary.get('success')) is not bool
                    or collection.get('actual_branch_count') != 0 or collection.get('branch_records')
                    or collection.get('common_outcome_available') is not True
                    or collection.get('common_outcome') != summary['success']):
                raise ValueError('No-cut source requires its original known full-episode outcome')
            outcome[:] = summary['success']
        rows.append(dict(episode_id=episode_id, task=case['task'], no_cut=not summary['cuts'],
            actual_cut=summary['actual_cut'], scene_fingerprint=summary['scene_fingerprint'],
            paired_outcomes={name: outcome[i].tolist() for i, name in enumerate(POLICY_METHODS)},
            success_counts=dict(zip(POLICY_METHODS, outcome.sum(1).tolist()))))
        labels.append(outcome)
    charged = [row for row in ledger.values() if row['stage'] == stage and row['resource'] == 'simulator_attempts']
    if (len(attempts) != len(set(attempts)) or set(attempts) != {row['number'] for row in charged}
            or len(attempts) != inputs['expected_attempts']
            or any(row['kind'] not in ('candidate_restore', 'branch_including_restore') for row in charged)):
        raise ValueError('Deployment attempt closure differs; unsealed/failed attempts must be resolved explicitly')
    return dict(status='passed', stage=stage, bank_version=bank_version,
        config_content_sha256=canonical_hash(config), selected_training=config['policy_deployment']['selected_training'],
        planned_slots=len(rows), technical_missing=0, source_capture_attempts_added=0,
        new_attempts=len(attempts), attempts_by_kind=dict(Counter(row['kind'] for row in charged)),
        attempt_numbers=attempts, original_source_attempt_numbers=old_source_attempts,
        ledger_snapshot_sha256=hashlib.sha256(raw_ledger).hexdigest(),
        scene_registry_snapshot_sha256=hashlib.sha256(raw_scenes).hexdigest(),
        artifacts=list(artifacts.values()), per_source=rows, statistics=summarize(labels, rows))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--bank', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Audit output must be an independent new directory')
    result = audit(_read(args.config), args.bank)
    storage.dump(args.output/'result.json', result)
    storage.seal(args.output, role='native10_policy5_readonly_audit', simulator_attempts=0, optimizer_updates=0)
    print(json.dumps({key: result[key] for key in ('status', 'planned_slots', 'new_attempts', 'statistics')}))
