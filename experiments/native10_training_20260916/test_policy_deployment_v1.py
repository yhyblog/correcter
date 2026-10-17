"""Synthetic sealed CPU fixtures only; no model, optimizer or simulator calls."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from . import policy_deployment_v1 as policy, storage, main_collection, engine
from .main_collection import POLICY_METHODS, SPLIT_REPLICATES, select_cut
from .protocol import candidate_seed, canonical_hash


def read(path):
    return json.loads(Path(path).read_text())


def rewrite(path, value):
    Path(path).write_text(json.dumps(value))


def reseal(path, **metadata):
    (path/'complete.json').unlink()
    storage.seal(path, **metadata)
    return storage.sha256(path/'complete.json')


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path/'outputs'
    for module in (policy, storage, main_collection):
        monkeypatch.setattr(module, 'ROOT', root)
    cases = [dict(episode_id=f'disassemble-v3__{i}', case_id=f'disassemble-v3__{i}',
        task='disassemble-v3', env_seed=i, split='development', round=None,
        source_horizon=10, cut_rule={'kind': 'first_alarm'}) for i in range(100)]
    old_protocol, new_protocol = 'a'*64, 'b'*64
    old_models = dict(vla='c'*64, d='d'*64, g0='e'*64, implementation='f'*64,
                      **{'critic_'+str(i): str(i)*64 for i in range(4)})
    registration = dict(kind='labels13', stage='round1_labels', generation_round=1,
        episode_ids=[row['episode_id'] for row in cases], model_hashes=old_models,
        critic_member_hashes={str(i): str(i)*64 for i in range(4)},
        cut_selection_policy='analysis_lead_v1', random_seed_domain='original')
    old = dict(episode_manifest=cases, seed_namespace='synthetic_cpu_only',
        source_horizon=10, prefix_horizon=10, suffix_horizon=10, control_budget=300,
        gate_threshold=.05, guidance={'alpha': 10, 'times': [.3, .2, .1]},
        matching=dict(xyz_rms=.05, gripper_rms=.1, xyz_linf=.15, gripper_linf=.4,
            boundary_clearance=.05, tolerance=1e-6, zero_threshold=1e-10),
        cpu={'worker_threads': 2}, scene_identity={'schema': 'test'},
        split_replicates=dict(SPLIT_REPLICATES), methods=list(POLICY_METHODS),
        main_collection={'banks': {'original': registration}, 'concurrency': {'workers_per_gpu': 4}},
        analysis_approval={'protocol_sha256': old_protocol})
    old_path = root/'original/config.json'
    storage.dump(old_path, old)
    freeze = root/'original/freeze.json'
    storage.dump(freeze, {'files': {str(old_path): storage.sha256(old_path)}})
    bound = {}
    raw = np.zeros((50, 4), np.float32)
    raw[:, 3] = 1.5  # Raw action preservation must catch accidental clamping.
    mask = np.ones((10, 4), bool); mask[:, 3] = False
    for i, case in enumerate(cases):
        identity = case['episode_id']; cut = 5 if i < 95 else None
        source = root/'sources'/identity
        selection = select_cut(case, [5] if cut else [], cut)
        storage.dump(source/'summary.json', dict(case=case, planned_episode_retained=True,
            outcome_filter_applied=False, cuts=[5] if cut else [], **selection,
            seed_namespace=old['seed_namespace'], no_alarm=cut is None, success=i % 2 == 0,
            full_episode_outcome_available=cut is None, model_hashes=old_models,
            cut_selection_policy='analysis_lead_v1'))
        storage.arrays(source/'trajectory.npz', actions=np.zeros((5, 4), np.float32))
        if cut:
            storage.dump(source/'cut005/anchor.json', {'step': 5})
            storage.arrays(source/'cut005/context.npz', full_plan=raw)
        storage.seal(source, protocol_sha256=old_protocol)
        source_sha = storage.sha256(source/'complete.json')
        resolution = root/'slot_resolution'/identity
        storage.dump(resolution/'resolution.json', dict(status='resolved', planned_slot_id=identity,
            resolved_episode_id=identity, ordered_rejections=[], source_protocol_sha256=old_protocol,
            source_seal_sha256=source_sha))
        storage.seal(resolution, protocol_sha256=old_protocol)
        bank_sha = None
        if cut:
            bank = root/'banks/original'/identity/'cut005'
            noise = '9'*64
            storage.arrays(bank/'plans.npz', a0=raw)
            storage.arrays(bank/'formal_directions.npz', raw_a0=raw, mask=mask)
            storage.dump(bank/'generation.json', dict(episode_id=identity, cut_step=5,
                source_seal_sha256=source_sha, model_hashes=old_models,
                base_seed=candidate_seed(case, 5, namespace=old['seed_namespace']),
                base_generation={'noise_sha256': noise},
                noise_hashes=dict(replan=noise, velocity=noise, direct=noise),
                suffix_seed_namespace=old['seed_namespace'], suffix_protocol='native10_first_ten_raw_commands_v1'))
            storage.seal(bank, protocol_sha256=old_protocol)
            bank_sha = storage.sha256(bank/'complete.json')
        bound[identity] = dict(source_seal_sha256=source_sha,
            resolution_seal_sha256=storage.sha256(resolution/'complete.json'), old_bank_seal_sha256=bank_sha)
    trained = root/'models/round1/synthetic'
    selected = trained/'selected'
    hashes = {}
    for member in range(4):
        path = selected/f'models/refit/member_{member}/selected.pt'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f'CPU synthetic artifact {member}; never torch.load'.encode())
        hashes[str(member)] = storage.sha256(path)
    storage.dump(selected/'ranking.json', dict(horizon=10, a0_slot=0, model_hashes=hashes))
    storage.seal(selected, role='four_member_critic_export', model_hashes=hashes)
    storage.dump(trained/'result.json', dict(status='complete', phase='round1',
        selected_assets=str(selected), model_hashes=hashes))
    storage.dump(trained/'selected_reload_audit.json', dict(status='passed', source_count=95,
        episode_ids=[row['episode_id'] for row in cases[:95]], members_checked=4, gradient_slots=[0, 11],
        feature_cache_bit_exact=True, thirteen_candidate_member_probability_bit_exact=True,
        member_and_ensemble_gradient_bit_exact=True, a0_anchor_exactly_zero=True, state_and_anchor_immutable=True))
    storage.seal(trained, role='native10_two_path_training', phase='round1', model_hashes=hashes)
    config = deepcopy(old)
    config['critic_assets'] = str(selected)
    config['analysis_approval']['protocol_sha256'] = new_protocol
    config['budget'] = {'stages': {policy.STAGE: dict(simulator_attempts=2100, training_updates=0)}}
    config['stage_release_scopes'] = {policy.STAGE: policy.STAGE}
    newreg = deepcopy(registration)
    newreg.update(kind='policy5', stage=policy.STAGE, critic_member_hashes=hashes,
        allowed_source_protocol_sha256=[old_protocol],
        model_hashes={**{k: old_models[k] for k in ('vla', 'd', 'g0', 'implementation')},
                      **{'critic_'+k: v for k, v in hashes.items()}})
    config['main_collection']['banks'] = {'new': newreg}
    config['policy_deployment'] = dict(schema=policy.SCHEMA,
        old_collection=dict(config_path=str(old_path), config_sha256=storage.sha256(old_path),
            freeze_path=str(freeze), freeze_sha256=storage.sha256(freeze), bank_version='original'),
        selected_training=dict(path=str(trained), seal_sha256=storage.sha256(trained/'complete.json'),
            selected_seal_sha256=storage.sha256(selected/'complete.json')), source_bindings=bound)
    return config, cases, root


def new_bank(inputs, case):
    bound = inputs['sources'][case['episode_id']]
    old = Path(bound['old_bank_path'])
    new = policy.ROOT/'banks/new'/case['case_id']/'cut005'
    with np.load(old/'plans.npz') as data:
        raw = data['a0'].copy()
        plans = {name: raw.copy() for name in POLICY_METHODS[1:]}
        storage.arrays(new/'plans.npz', **plans)
        storage.arrays(new/'directions.npz', raw_a0=raw, critic_a0=np.clip(raw, -1, 1),
            critic_candidates=np.stack([np.clip(plan, -1, 1) for plan in plans.values()]))
    with np.load(old/'formal_directions.npz') as data:
        storage.arrays(new/'formal_directions.npz', **{key: data[key] for key in data.files})
    storage.dump(new/'generation.json', read(old/'generation.json'))
    storage.seal(new, protocol_sha256=bound['new_protocol_sha256'])
    return new


def test_complete100_preserves_five_common_outcomes_and_real_attempt_count(prepared):
    config, cases, _ = prepared
    inputs = policy.validate_deployment_inputs(config, 'new')
    assert inputs['expected_attempts'] == 1995 and inputs['hard_attempt_limit'] == 2100
    assert inputs['planned_denominator_per_arm'] == 400
    assert inputs['episode_ids'] == [row['episode_id'] for row in cases]
    common = [row for row in inputs['sources'].values() if row['cut'] is None]
    assert len(common) == 5 and {row['common_outcome'] for row in common} == {True, False}
    assert all(row['old_bank_path'] is None for row in common)
    assert inputs['simulator_calls'] == inputs['model_calls'] == 0


@pytest.mark.parametrize('field,value', [('seed_namespace', 'newseed'), ('guidance', {'alpha': 20}),
    ('matching', {'xyz_rms': .1}), ('source_horizon', 50), ('cpu', {'worker_threads': 8})])
def test_changed_execution_semantics_are_rejected(prepared, field, value):
    config, _, _ = prepared
    config[field] = value
    with pytest.raises(ValueError, match='semantics'):
        policy.validate_deployment_inputs(config, 'new')


def test_source_missing_fails_before_any_model_construction(prepared, monkeypatch):
    config, cases, root = prepared
    (root/'sources'/cases[0]['case_id']/'complete.json').unlink()
    monkeypatch.setattr(policy, '_require_main', lambda *args: None)
    monkeypatch.setattr(engine, 'create_engine', lambda *args: pytest.fail('Model factory must never run'))
    with pytest.raises(FileNotFoundError):
        policy.create_policy_collector(config, policy.STAGE, bank_version='new')


def test_stage_release_denial_precedes_all_input_reads(monkeypatch):
    def deny(*args):
        raise ValueError('unreleased deployment')
    monkeypatch.setattr(policy, '_require_main', deny)
    monkeypatch.setattr(policy, 'validate_deployment_inputs', lambda *args: pytest.fail('No reads before gate'))
    with pytest.raises(ValueError, match='unreleased'):
        policy.create_policy_collector({}, policy.STAGE, bank_version='new')


def test_labels_release_scope_cannot_be_reused_for_deployment(prepared):
    config, _, _ = prepared
    config['stage_release_scopes'][policy.STAGE] = 'round1_native10_local_labels'
    with pytest.raises(ValueError, match='own round1_development_policy'):
        policy.validate_deployment_inputs(config, 'new')


def test_resealed_replacement_resolution_is_rejected(prepared):
    config, cases, root = prepared
    identity = cases[0]['episode_id']; folder = root/'slot_resolution'/identity
    row = read(folder/'resolution.json'); row['resolved_episode_id'] = 'replacement'
    rewrite(folder/'resolution.json', row)
    config['policy_deployment']['source_bindings'][identity]['resolution_seal_sha256'] = reseal(folder, protocol_sha256='a'*64)
    with pytest.raises(ValueError, match='replaced'):
        policy.validate_deployment_inputs(config, 'new')


def test_unknown_noalarm_is_not_zero_imputed(prepared):
    config, cases, root = prepared
    identity = cases[-1]['episode_id']; folder = root/'sources'/identity
    row = read(folder/'summary.json'); row['full_episode_outcome_available'] = False
    rewrite(folder/'summary.json', row)
    digest = reseal(folder, protocol_sha256='a'*64)
    binding = config['policy_deployment']['source_bindings'][identity]
    binding['source_seal_sha256'] = digest
    resolution = root/'slot_resolution'/identity
    row = read(resolution/'resolution.json'); row['source_seal_sha256'] = digest
    rewrite(resolution/'resolution.json', row)
    binding['resolution_seal_sha256'] = reseal(resolution, protocol_sha256='a'*64)
    with pytest.raises(ValueError, match='known common outcome'):
        policy.validate_deployment_inputs(config, 'new')


def test_incomplete_training_cannot_supply_selected_critic(prepared):
    config, _, _ = prepared
    path = Path(config['policy_deployment']['selected_training']['path'])
    (path/'complete.json').unlink()
    with pytest.raises(FileNotFoundError):
        policy.validate_deployment_inputs(config, 'new')


def test_critic_hashes_must_match_selected_export(prepared):
    config, _, _ = prepared
    config['main_collection']['banks']['new']['critic_member_hashes']['0'] = '0'*64
    with pytest.raises(ValueError, match='hashes'):
        policy.validate_deployment_inputs(config, 'new')


@pytest.mark.parametrize('change', ['raw', 'seed', 'noise', 'mask', 'source', 'tail', 'masked', 'critic'])
def test_bank_mismatch_blocks_before_branch(prepared, change):
    config, cases, _ = prepared
    inputs = policy.validate_deployment_inputs(config, 'new')
    bank = new_bank(inputs, cases[0])
    assert policy.verify_bank_anchor(bank, inputs['sources'][cases[0]['episode_id']])['raw50_a0_bit_exact']
    if change in ('raw', 'mask', 'tail', 'masked', 'critic'):
        path = bank/('formal_directions.npz' if change == 'mask' else 'directions.npz' if change == 'critic' else 'plans.npz')
        with np.load(path) as archive:
            values = {key: archive[key].copy() for key in archive.files}
        if change == 'raw':
            values['alarm_replan10'][49, 3] = 1.  # Tail must also be bit-exact.
        elif change == 'tail':
            values['post'][10, 0] = .2
        elif change == 'masked':
            values['velocity'][0, 3] = 1.4
        elif change == 'critic':
            values['critic_candidates'][0, 0, 0] = .1
        else:
            values['mask'][0, 0] = False
        path.unlink(); storage.arrays(path, **values)
    else:
        path = bank/'generation.json'; values = read(path)
        if change == 'seed': values['base_seed'] += 1
        if change == 'noise':
            values['base_generation']['noise_sha256'] = '8'*64
            values['noise_hashes'] = dict(replan='8'*64, velocity='8'*64, direct='8'*64)
        if change == 'source': values['source_seal_sha256'] = '8'*64
        rewrite(path, values)
    reseal(bank, protocol_sha256='b'*64)
    with pytest.raises(ValueError):
        policy.verify_bank_anchor(bank, inputs['sources'][cases[0]['episode_id']])


def test_ledger_blocks_capture_replacement_and_noalarm_attempts(prepared):
    config, cases, _ = prepared
    inputs = policy.validate_deployment_inputs(config, 'new')
    calls = []
    delegate = SimpleNamespace(reserve=lambda *args, **kwargs: calls.append((args, kwargs)))
    ledger = policy._PolicyLedger(delegate, inputs)
    ledger.reserve(policy.STAGE, 'candidate_restore', 'banks/new/'+cases[0]['case_id']+'/cut005')
    assert len(calls) == 1
    for stage, kind, identity in [
        (policy.STAGE, 'source_capture', cases[0]['case_id']),
        ('technical_reserve', 'source_capture', 'replacement'),
        (policy.STAGE, 'candidate_restore', 'banks/new/'+cases[-1]['case_id']+'/cut005'),
        (policy.STAGE, 'branch_including_restore', 'rollouts/'+policy.STAGE+'/new/'+cases[0]['case_id']+'/cut005/post/repeat_4')]:
        with pytest.raises(ValueError, match='prohibits'):
            ledger.reserve(stage, kind, identity)
    assert len(calls) == 1


def test_collector_checks_old_source_before_base_capture_fallback(prepared, monkeypatch):
    config, cases, root = prepared
    inputs = policy.validate_deployment_inputs(config, 'new')
    collector = object.__new__(policy.GuardedPolicyCollector)
    collector.deployment_inputs, collector.config = inputs, config
    monkeypatch.setattr(main_collection.MainCollector, 'collect_episode', lambda *args: pytest.fail('Base must not run'))
    (root/'sources'/cases[0]['case_id']/'complete.json').unlink()
    with pytest.raises(FileNotFoundError):
        collector.collect_episode(cases[0])
    with pytest.raises(ValueError, match='forbids'):
        collector.capture(cases[0])


def test_guard_bank_report_is_sealed_and_precedes_base_branch_reserve(prepared, monkeypatch):
    config, cases, _ = prepared
    inputs = policy.validate_deployment_inputs(config, 'new')
    bank = new_bank(inputs, cases[0])
    collector = object.__new__(policy.GuardedPolicyCollector)
    collector.deployment_inputs = inputs
    collector.stage, collector.bank_version, collector.protocol_sha256 = policy.STAGE, 'new', 'b'*64
    monkeypatch.setattr(main_collection.MainCollector, '_bank', lambda *args: (bank, {}, {}))
    collector._bank(cases[0], Path(inputs['sources'][cases[0]['episode_id']]['source_path']), 5)
    report = policy.ROOT/'policy_guard'/policy.STAGE/'new'/cases[0]['episode_id']
    policy._sealed(report, ['b'*64])
    assert read(report/'bank_check.json')['checked_before_branch']
    before = storage.sha256(report/'complete.json')
    collector._bank(cases[0], None, 5)
    assert storage.sha256(report/'complete.json') == before


def test_budget_and_original_slot_order_are_fixed(prepared):
    config, _, _ = prepared
    config['budget']['stages'][policy.STAGE]['simulator_attempts'] = 2101
    with pytest.raises(ValueError, match='2100'):
        policy.validate_deployment_inputs(config, 'new')
    config['budget']['stages'][policy.STAGE]['simulator_attempts'] = 2100
    config['main_collection']['banks']['new']['episode_ids'].reverse()
    with pytest.raises(ValueError, match='ordered 100'):
        policy.validate_deployment_inputs(config, 'new')


def test_auditor_import_contract_without_reading_actual_outputs():
    from . import policy5_audit_v1 as auditor
    from .policy_deployment_v1 import validate_deployment_inputs, verify_bank_anchor
    assert callable(auditor.audit) and callable(validate_deployment_inputs) and callable(verify_bank_anchor)


@pytest.mark.parametrize('channel', ['xyz', 'gripper'])
def test_actual_within_bank_rms_must_match_existing_tolerance(channel):
    audit = {'actual': {name: {'actual_delta': {'xyz_rms': .02, 'gripper_rms': .04}}
                       for name in ('velocity_matched', 'direct_matched', 'post_matched')}}
    assert policy._matched_rms(audit, {'tolerance': 1e-6})['status'] == 'passed'
    audit['actual']['direct_matched']['actual_delta'][channel+'_rms'] += 2e-6
    with pytest.raises(ValueError, match='RMS is not matched'):
        policy._matched_rms(audit, {'tolerance': 1e-6})


def test_actual_bank_unequal_small_corrections_fail_even_below_caps(prepared):
    config, cases, _ = prepared
    inputs = policy.validate_deployment_inputs(config, 'new')
    bank = new_bank(inputs, cases[0])
    path = bank/'plans.npz'
    with np.load(path) as archive:
        plans = {key: archive[key].copy() for key in archive.files}
    for name, delta in [('velocity', .01), ('direct', .02), ('post', .01)]:
        plans[name][:10, :3] += delta
    path.unlink(); storage.arrays(path, **plans)
    path = bank/'directions.npz'; path.unlink()
    storage.arrays(path, raw_a0=plans['alarm_replan10'], critic_a0=np.clip(plans['alarm_replan10'], -1, 1),
        critic_candidates=np.stack([np.clip(plans[name], -1, 1) for name in POLICY_METHODS[1:]]))
    reseal(bank, protocol_sha256='b'*64)
    with pytest.raises(ValueError, match='RMS is not matched'):
        policy.verify_bank_anchor(bank, inputs['sources'][cases[0]['episode_id']])
