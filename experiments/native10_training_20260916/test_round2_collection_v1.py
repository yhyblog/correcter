"""Synthetic registration/assets/runtime stubs; no real models or simulators."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from . import round2_collection_v1 as round2, storage, main_collection, adapter, engine, main_runner
from .protocol import TASKS, canonical_hash, candidate_seed
from .main_collection import SPLIT_REPLICATES, LABEL_METHODS, select_cut
from .candidates13 import CANDIDATE_ORDER, DEFAULT_CONFIG, PAIRS
from .test_main_collection import MainEngineStub


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path/'outputs'
    for module in (storage, round2, main_collection, adapter, main_runner):
        monkeypatch.setattr(module, 'ROOT', root)
    primaries, backups, replacements = [], [], {}
    for i in range(300):
        task, index = TASKS[i % 5], i//5
        rule = {'kind': 'first_alarm'} if index % 2 == 0 else dict(kind='scheduled', step=(15, 45, 95)[(index//2) % 3], fallback='none_pending_analysis_review')
        seed = 2026111300+i; identity = f'{task}__{seed}'
        case = dict(task=task, env_seed=seed, case_id=identity, episode_id=identity,
                    split='train', round=2, source_horizon=10, cut_rule=rule)
        primaries.append(case); replacements[identity] = []
        for order in range(2):
            backup_seed = 3026111300+i*2+order; backup = f'{task}__{backup_seed}'
            backups.append(dict(deepcopy(case), case_id=backup, episode_id=backup,
                                env_seed=backup_seed, replacement_of=identity))
            replacements[identity].append(backup)
    models = dict(vla='a'*64, d='b'*64, g0='c'*64, implementation='d'*64)
    old = dict(status='pending', episode_manifest=primaries+backups, seed_namespace='synthetic_round2',
        source_horizon=10, prefix_horizon=10, suffix_horizon=10, control_budget=300, gate_threshold=.05,
        guidance={'alpha': 10, 'times': [.3, .2, .1]}, matching=dict(DEFAULT_CONFIG),
        cpu={'worker_threads': 4, 'critic_threads': 2}, scene_identity={'schema': 'synthetic'},
        split_replicates=dict(SPLIT_REPLICATES), methods=list(main_collection.POLICY_METHODS),
        main_collection=dict(concurrency={'workers_per_gpu': 4}, replacement_capture_stage='technical_reserve',
            replacement_candidates=replacements, banks={'round1_labels_v1': dict(model_hashes=models,
                random_seed_domain='main_local_labels_v1')}), analysis_approval={'protocol_sha256': 'e'*64})
    oldpath = root/'original/config.json'; freeze = root/'original/freeze.json'
    storage.dump(oldpath, old); storage.dump(freeze, {'files': {str(oldpath): storage.sha256(oldpath)}})
    trained = root/'models/round1/B200'; selected = trained/'selected'; hashes = {}
    for member in range(4):
        path = selected/f'models/refit/member_{member}/selected.pt'; path.parent.mkdir(parents=True)
        path.write_bytes(f'fake opaque CPU checkpoint {member}'.encode()); hashes[str(member)] = storage.sha256(path)
    storage.dump(selected/'ranking.json', dict(horizon=10, a0_slot=0, model_hashes=hashes))
    storage.seal(selected, role='four_member_critic_export', model_hashes=hashes)
    selectedsha = storage.sha256(selected/'complete.json'); monkeypatch.setattr(round2, 'SELECTED_SEAL', selectedsha)
    storage.dump(trained/'result.json', dict(status='complete', phase='round1', selection={'path': 'B', 'step': 200},
        optimizer_updates=19200, selected_assets=str(selected), model_hashes=hashes))
    storage.dump(trained/'selected_reload_audit.json', {'status': 'passed'})
    storage.seal(trained, role='native10_two_path_training', phase='round1', model_hashes=hashes)
    cfg = deepcopy(old); cfg['critic_assets'] = str(selected)
    cfg['budget'] = dict(hard_total=50000, training_update_total=51200, count_failures=True, count_retries=True,
        stages={round2.STAGE: dict(simulator_attempts=17400, training_updates=0),
                round2.REPLACEMENT_STAGE: dict(simulator_attempts=1200, training_updates=0)})
    cfg['stage_release_scopes'] = {round2.STAGE: round2.SCOPE, round2.REPLACEMENT_STAGE: round2.REPLACEMENT_SCOPE}
    radii = {row['episode_id']: .5 if ((i//5)//2) % 2 == 0 else 1. for i, row in enumerate(primaries)}
    cfg['main_collection']['banks'] = {round2.BANK: dict(stage=round2.STAGE, kind='labels13', generation_round=2,
        episode_ids=[row['episode_id'] for row in primaries], cut_selection_policy='analysis_lead_v1',
        random_seed_domain='main_local_labels_v1', channel_radius_by_episode=radii,
        model_hashes={**models, **{'critic_'+key: value for key, value in hashes.items()}}, critic_member_hashes=hashes)}
    cfg['round2_collection'] = dict(schema='native10_round2_collection_v1',
        original_collection=dict(config_path=str(oldpath), config_sha256=storage.sha256(oldpath),
            freeze_path=str(freeze), freeze_sha256=storage.sha256(freeze), bank_version='round1_labels_v1'),
        selected_training=dict(path=str(trained), seal_sha256=storage.sha256(trained/'complete.json'), selected_seal_sha256=selectedsha),
        effective_cut_policy=deepcopy(round2.EFFECTIVE_CUT_POLICY),
        requested_cut_rules_sha256=canonical_hash({row['episode_id']: row['cut_rule'] for row in primaries}))
    live = root/'scene_registry/entries.jsonl'; snapshot = root/'preparation/scenes.jsonl'
    for path in (live, snapshot):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'{"existing":true}\n')
    cfg['round2_preparation'] = {'scene_registry_before': dict(live_path=str(live), snapshot_path=str(snapshot),
        sha256=storage.sha256(snapshot), bytes=snapshot.stat().st_size, records=1)}
    return cfg, primaries, root


def test_pending_exact300_and_original_placeholder_resolve_to_lead(prepared):
    cfg, cases, root = prepared
    checked = round2.validate_round2_inputs(cfg)
    assert checked['planned_primary_sources'] == 300 and len(checked['cases']) == 900
    assert checked['primary_capture_limit'] == 300 and checked['expected_max_attempts'] == 17400
    assert not checked['cross_bank_a0_identity_required'] and not checked['old_guided_action_reuse_allowed']
    assert not (root/'sources').exists()
    case = next(row for row in cases if row['cut_rule'].get('step') == 95)
    assert case['cut_rule']['fallback'] == 'none_pending_analysis_review'
    assert select_cut(case, [5, 15], None)['actual_cut'] == 15
    assert select_cut(cases[0], [5, 15], None)['actual_cut'] == 15
    assert select_cut(cases[0], [], None)['actual_cut'] is None


@pytest.mark.parametrize('key,value', [('guidance', {'alpha': 20}), ('gate_threshold', .1),
    ('source_horizon', 50), ('seed_namespace', 'newstream'), ('matching', {'xyz_rms': .1})])
def test_scientific_parameters_cannot_change(prepared, key, value):
    cfg, _, _ = prepared; cfg[key] = value
    with pytest.raises(ValueError, match='semantics'):
        round2.validate_round2_inputs(cfg)


def test_unreleased_factory_fails_before_model_or_new_sources(prepared, monkeypatch):
    cfg, _, root = prepared
    monkeypatch.setattr(engine, 'create_engine', lambda *args: pytest.fail('No model load in pending stage'))
    with pytest.raises(ValueError):
        round2.create_round2_collector(cfg)
    assert not (root/'sources').exists()


def test_exact_scope_and_resource_isolation(prepared):
    cfg, _, _ = prepared
    cfg['stage_release_scopes'][round2.STAGE] = 'round1_native10_local_labels'
    with pytest.raises(ValueError, match='separate exact'):
        round2.validate_round2_inputs(cfg)
    cfg['stage_release_scopes'][round2.STAGE] = round2.SCOPE
    cfg['budget']['stages'][round2.STAGE]['training_updates'] = 1
    with pytest.raises(ValueError, match='budgets'):
        round2.validate_round2_inputs(cfg)


def test_radius_uses_per_task_adjacent_pairs_not_global_case_parity(prepared):
    cfg, _, _ = prepared
    radii = cfg['main_collection']['banks'][round2.BANK]['channel_radius_by_episode']
    cfg['main_collection']['banks'][round2.BANK]['channel_radius_by_episode'] = {
        key: .5 if i % 2 == 0 else 1. for i, key in enumerate(radii)}
    with pytest.raises(ValueError, match='adjacent-pair'):
        round2.validate_round2_inputs(cfg)


def test_future_split_or_reordered_primary_list_is_rejected(prepared):
    cfg, cases, _ = prepared
    registration = cfg['main_collection']['banks'][round2.BANK]
    registration['episode_ids'].reverse()
    with pytest.raises(ValueError, match='ordered 300'):
        round2.validate_round2_inputs(cfg)


def test_scene_prefix_allows_append_but_not_rewrite(prepared):
    cfg, _, _ = prepared
    path = Path(cfg['round2_preparation']['scene_registry_before']['live_path'])
    with path.open('ab') as f: f.write(b'{"new_round2":true}\n')
    assert round2.validate_round2_inputs(cfg)['status'] == 'passed'
    path.write_bytes(b'{"changed":true}\n')
    with pytest.raises(ValueError, match='prefix changed'):
        round2.validate_round2_inputs(cfg)


def test_selected_seal_and_actual_loaded_identity_are_not_config_only(prepared):
    cfg, _, _ = prepared
    checked = round2.validate_round2_inputs(cfg)
    obj = object.__new__(round2.Round2Collector)
    obj.round2_inputs = checked; obj.critic_hashes = checked['selected_training']['model_hashes']
    obj._verify_models = lambda: None
    selector = SimpleNamespace(assets_dir='/wrong', model_paths=[], verify=lambda **kwargs: None)
    obj.engine = SimpleNamespace(selector=selector)
    with pytest.raises(ValueError, match='Actual loaded critic directory'):
        obj.actual_loaded_identity()
    cfg['round2_collection']['selected_training']['selected_seal_sha256'] = '0'*64
    with pytest.raises(ValueError, match='fixed B200'):
        round2.validate_round2_inputs(cfg)


def test_ledger_separates_primary_backup_and_56_branch_interface(prepared):
    cfg, cases, _ = prepared; checked = round2.validate_round2_inputs(cfg); calls = []
    ledger = round2._Round2Ledger(SimpleNamespace(reserve=lambda *a, **kw: calls.append((a, kw))), checked)
    primary = cases[0]['episode_id']; backup = cfg['main_collection']['replacement_candidates'][primary][0]
    ledger.reserve(round2.STAGE, 'source_capture', primary)
    ledger.reserve('technical_reserve', 'source_capture', backup)
    ledger.reserve(round2.STAGE, 'candidate_restore', f'banks/{round2.BANK}/{backup}/cut015')
    for method in LABEL_METHODS:
        for repeat in range(4):
            ledger.reserve(round2.STAGE, 'branch_including_restore', f'rollouts/{round2.STAGE}/{round2.BANK}/{primary}/cut015/{method}/repeat_{repeat}')
    assert len(calls) == 59
    for stage, kind, identity in [(round2.STAGE, 'source_capture', backup),
        ('technical_reserve', 'source_capture', primary), ('heldout', 'source_capture', primary),
        (round2.STAGE, 'candidate_restore', f'banks/{round2.BANK}/{primary}/cut010'),
        (round2.STAGE, 'branch_including_restore', f'rollouts/{round2.STAGE}/{round2.BANK}/{primary}/cut015/a0/repeat_4')]:
        with pytest.raises(ValueError, match='outside'):
            ledger.reserve(stage, kind, identity)
    with pytest.raises(ValueError, match='optimizer'):
        ledger.reserve(round2.STAGE, 'source_capture', primary, resource='training_updates')


def test_new_capture_labels13_raw_symmetry_and_paired_suffix_interface(prepared, monkeypatch):
    cfg, cases, root = prepared
    monkeypatch.setattr(round2, 'require_stage_budget', lambda *args, **kwargs: None)
    monkeypatch.setattr(main_collection, '_require_main', lambda *args: None)
    monkeypatch.setattr(main_collection, '_score_bank', lambda eng, obs, raw, plans: {name: {'mean_gain': 0.} for name in plans})
    def scene(runtime, case, attempt, config, destination):
        record = dict(status='accepted', scene_fingerprint='a'*64, exact_state_sha256='b'*64)
        storage.dump(destination/'identity.json', record); storage.seal(destination)
        return record
    monkeypatch.setattr(main_collection, '_capture_scene', scene)
    models = cfg['main_collection']['banks'][round2.BANK]['critic_member_hashes']
    stub = MainEngineStub(cfg, models, gate=.1, success_at=28)
    selected = Path(cfg['critic_assets']); stub.selector.assets_dir = selected
    stub.selector.model_paths = [selected/f'models/refit/member_{member}/selected.pt' for member in models]
    stub.selector.verify = lambda **kwargs: True
    calls = []
    def reserve(stage, kind, identity, **kwargs):
        row = dict(number=len(calls)+1, stage=stage, kind=kind, identity=identity)
        calls.append(row); return row
    collector = round2.Round2Collector(stub, cfg, SimpleNamespace(reserve=reserve))
    assert collector.loaded_identity['status'] == 'passed'
    case = cases[0]
    backup_id = cfg['main_collection']['replacement_candidates'][case['episode_id']][0]
    backup = next(row for row in cfg['episode_manifest'] if row['episode_id'] == backup_id)
    with pytest.raises(FileNotFoundError):
        collector.capture(backup)
    assert calls == []
    completed = collector.collect_episode(case)
    result = json.loads((completed/'summary.json').read_text())
    assert len(calls) == 58 and calls[0]['kind'] == 'source_capture'
    assert all(row['stage'] == round2.STAGE for row in calls)
    assert result['actual_branch_count'] == 56 and result['methods'] == list(LABEL_METHODS)
    bank = collector.bank_path(case, 5)
    with np.load(bank/'plans.npz') as archive:
        assert list(archive.files) == list(CANDIDATE_ORDER)
        raw = archive['a0']
        assert np.all(raw[:, 3] == np.r_[np.full(10, np.float32(1.4)), np.full(40, np.float32(9.))])
        for name in archive.files: np.testing.assert_array_equal(archive[name][10:], raw[10:])
        for positive, negative in PAIRS:
            np.testing.assert_allclose(archive[positive].astype(float)+archive[negative]-2*raw.astype(float), 0, atol=1e-6, rtol=0)
    metadata = json.loads((bank/'metadata.json').read_text())
    assert metadata['a0_slot'] == 0 and metadata['candidate_count'] == 13
    assert metadata['aliases']['gripper_positive'] == metadata['aliases']['gripper_negative'] == 'a0'
    normal = json.loads((collector.branch_path(case, 5, 'continue_native10', 0)/'summary.json').read_text())
    a0 = json.loads((collector.branch_path(case, 5, 'a0', 0)/'summary.json').read_text())
    assert normal['first_actual_resample'] == 10 and a0['first_actual_resample'] == 15
    assert normal['suffix_seeds'][0]['decision_index'] == a0['suffix_seeds'][0]['decision_index'] == 0
    assert normal['suffix_seeds'][0]['seed'] == a0['suffix_seeds'][0]['seed']
    assert normal['suffix_seeds'][0]['noise_sha256'] == a0['suffix_seeds'][0]['noise_sha256']
    with pytest.raises(FileNotFoundError):
        collector.capture(backup)  # An ordinary completed source cannot activate a replacement.
    assert len(calls) == 58
