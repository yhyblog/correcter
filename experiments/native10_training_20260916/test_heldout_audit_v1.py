"""Synthetic adapter tests only: no true heldout labels or model loading."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from . import heldout_audit_v1 as audit
from .heldout_statistics_v1 import REGISTERED_REPLACEMENT_CANDIDATES


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def seal(path, protocol, role):
    files = {str(p.relative_to(path)): audit.storage.sha256(p) for p in path.rglob('*')
             if p.is_file() and p != path/'complete.json'}
    put(path/'complete.json', dict(status='complete', role=role, protocol_sha256=protocol, files=files))


def configuration(root):
    ids = list(audit.REGISTERED_PRIMARY_IDS); protocol = 'a'*64
    cases = [dict(episode_id=identity, case_id=identity, task=identity.rsplit('__', 1)[0],
        env_seed=int(identity.rsplit('__', 1)[1]), split='heldout', round=None,
        source_horizon=10, cut_rule={'kind': 'first_alarm'}) for identity in ids]
    primary_cases = list(cases)
    for case in primary_cases:
        for ordinal, identity in enumerate(REGISTERED_REPLACEMENT_CANDIDATES[case['episode_id']], 1):
            cases.append(dict(case, episode_id=identity, case_id=identity,
                env_seed=int(identity.rsplit('__', 1)[1]), replacement_of=case['episode_id'], replacement_ordinal=ordinal))
    hashes = {str(i): str(i)*64 for i in range(4)}
    return dict(analysis_approval=dict(protocol_sha256=protocol), episode_manifest=cases,
        critic_assets=str(root/'fake_selected'), heldout_collection=dict(selected_training=dict(
            selected_seal_sha256='b'*64, selected_reload_audit_sha256='c'*64),
            final_selection=dict(path=str(root/'final_selections/final_selection_v1'),
                seal_sha256='d'*64, result_sha256='e'*64)),
        budget=dict(stages={'training': dict(simulator_attempts=0, training_updates=51200),
            'heldout': dict(simulator_attempts=2200, training_updates=0),
            'technical_reserve': dict(simulator_attempts=1200, training_updates=0)}),
        main_collection=dict(banks={audit.BANK: dict(episode_ids=ids, critic_member_hashes=hashes)},
                             replacement_candidates=deepcopy(REGISTERED_REPLACEMENT_CANDIDATES)))


def ledger(config, *, cuts=2, backups=1):
    rows = [dict(number=1, stage='training', resource='training_updates', amount=51200,
                 protocol_sha256='old', kind='training', identity='previous')]
    def add(stage, kind, identity):
        rows.append(dict(number=len(rows)+1, stage=stage, resource='simulator_attempts', amount=1,
                         protocol_sha256=config['analysis_approval']['protocol_sha256'], kind=kind, identity=identity))
    for identity in audit.REGISTERED_PRIMARY_IDS:
        add('heldout', 'source_capture', identity)
    for i in range(backups): add('technical_reserve', 'source_capture', f'backup{i}')
    for i in range(cuts):
        add('heldout', 'candidate_restore', f'bank{i}')
        for j in range(20): add('heldout', 'branch_including_restore', f'bank{i}/branch{j}')
    return {row['number']: row for row in rows}


@pytest.fixture
def wave(tmp_path, monkeypatch):
    monkeypatch.setattr(audit.storage, 'ROOT', tmp_path)
    config = configuration(tmp_path); ids = list(audit.REGISTERED_PRIMARY_IDS)
    config_path, freeze_path = tmp_path/'config.json', tmp_path/'freeze.json'
    put(config_path, config); put(freeze_path, {'synthetic': True})
    path = tmp_path/'heldout_execution'/audit.STAGE/audit.BANK/'synthetic'
    spec_path = path/'wave_spec.json'
    put(spec_path, dict(config_sha256=audit.storage.sha256(config_path), freeze_sha256=audit.storage.sha256(freeze_path),
        stage=audit.STAGE, bank_version=audit.BANK, workers=32, hold_idle=False, original_primary_slots=100,
        paired_suffixes_per_state=4, primary_capture_limit=100, hard_attempt_limit=2200,
        global_choice_applied_during_collection=False, selection_automatically_started=False,
        fixed_main_injection='post', primary_policy_fixed_before_heldout=True,
        final_selection=config['heldout_collection']['final_selection'], selection_after_heldout_allowed=False,
        physical_arms=list(audit.METHODS), guard_factory='create_heldout_collector'))
    put(path/'launch_result.json', dict(status='complete', returncode=0, lifecycle_covers_entire_wave=True,
        hold_idle=False, next_stage_automatically_started=False, command=['lifecycle', '--spec', str(spec_path)]))
    selected = Path(config['critic_assets']); hashes = config['main_collection']['banks'][audit.BANK]['critic_member_hashes']
    loaded = dict(status='passed', stage='heldout', selected_assets=str(selected), selected_path=str(selected),
        selected_seal_sha256='b'*64, selected_reload_audit_sha256='c'*64,
        model_paths=[str(selected/f'models/refit/member_{i}/selected.pt') for i in range(4)],
        member_hashes=hashes, model_hashes=hashes, selection=dict(path='A', step=4000), optimizer_updates=0,
        actual_selector_paths=True, checkpoint_file_sha=True, frozen_parameter_buffer_versions=True,
        eval_cpu_no_parameter_grad=True,
        final_selection=dict(status='sealed', **config['heldout_collection']['final_selection'], method='post',
            post_enabled_on_alarm=True, primary_comparison='post_minus_alarm_replan10', selection_after_heldout_allowed=False))
    for rank in range(32):
        folder = path/'workers'/f'worker_{rank:02d}'; assigned = ids[rank::32]
        put(folder/'loaded_model_identity.json', loaded)
        put(folder/'status.json', dict(status='complete', stage=audit.STAGE, bank_version=audit.BANK,
            wave_id=path.name, rank=rank, workers=32, config_sha256=audit.storage.sha256(config_path),
            freeze_sha256=audit.storage.sha256(freeze_path), protocol_sha256='a'*64,
            assigned_slot_ids=assigned, completed_slot_records=len(assigned), missing_slot_ids=[],
            primary_capture_allowed=True, global_choice_applied_during_collection=False,
            fixed_main_injection='post', primary_policy_fixed_before_heldout=True,
            final_selection=config['heldout_collection']['final_selection'], selection_after_heldout_allowed=False,
            next_stage_automatically_started=False, guard_factory='create_heldout_collector',
            slot_entry='collect_heldout_slot'))
        for identity in assigned:
            collection = tmp_path/'collections'/audit.STAGE/audit.BANK/identity
            resolution = tmp_path/'slot_resolution'/identity
            put(collection/'complete.json', {'fake': 'no outcome file exists'})
            put(resolution/'complete.json', {'fake': 'metadata gate only'})
            put(folder/'slots'/f'{identity}.json', dict(status='complete', planned_slot_id=identity,
                resolved_episode_id=identity, ordered_rejections=[], completion_path=str(collection),
                completion_sha256=audit.storage.sha256(collection/'complete.json'), resolution_path=str(resolution)))
        seal(folder, 'a'*64, 'guarded_heldout_worker')
    return config, config_path, freeze_path, path


def test_complete_metadata_gate_does_not_need_outcomes(wave):
    result = audit._wave_gate(*wave, {})
    assert result['all_100_slots_complete'] and len(result['slots']) == 100
    assert result['loaded_workers'] == 32


@pytest.mark.parametrize('missing', ['launch', 'worker_seal', 'technical_slot'])
def test_incomplete_wave_blocks_before_outcomes(wave, missing):
    config, cp, fp, path = wave
    if missing == 'launch': (path/'launch_result.json').unlink()
    elif missing == 'worker_seal': (path/'workers/worker_31/complete.json').unlink()
    else:
        folder = path/'workers/worker_00'
        row = audit.read(folder/'status.json'); row['status'] = 'complete_with_missing_slots'
        row['missing_slot_ids'] = [audit.REGISTERED_PRIMARY_IDS[0]]
        put(folder/'status.json', row); seal(folder, 'a'*64, 'guarded_heldout_worker')
    with pytest.raises(ValueError): audit._wave_gate(config, cp, fp, path, {})


def test_wrong_actual_critic_attestation_rejected(wave):
    config, cp, fp, path = wave
    folder = path/'workers/worker_00'; row = audit.read(folder/'loaded_model_identity.json')
    row['selection'] = dict(path='B', step=200)
    put(folder/'loaded_model_identity.json', row); seal(folder, 'a'*64, 'guarded_heldout_worker')
    with pytest.raises(ValueError, match='A4000'): audit._wave_gate(config, cp, fp, path, {})


@pytest.mark.parametrize('cuts,backups', [(0, 0), (2, 1), (100, 200)])
def test_exact_primary_backup_bank_branch_closure(tmp_path, cuts, backups):
    config = configuration(tmp_path); values = ledger(config, cuts=cuts, backups=backups)
    result = audit._ledger_closure(config, values, list(values)[1:], cut_sources=cuts, replacement_captures=backups)
    assert result['new_attempts'] == 100+backups+21*cuts
    assert result['heldout_stage_attempts'] == 100+21*cuts
    assert result['backup_capture_attempts'] == backups and result['new_optimizer_updates'] == 0


@pytest.mark.parametrize('change', ['missing_used', 'duplicate_used', 'extra_identity', 'update', 'reserve_bank'])
def test_unaccounted_or_forbidden_computation_blocks_closure(tmp_path, change):
    config = configuration(tmp_path); values = ledger(config); used = list(values)[1:]
    if change == 'missing_used': used.pop()
    elif change == 'duplicate_used': used.append(used[0])
    elif change == 'extra_identity': values[len(values)]['identity'] = values[len(values)-1]['identity']
    elif change == 'update': values[used[-1]]['resource'] = 'training_updates'
    else: values[102]['kind'] = 'candidate_restore'
    with pytest.raises(ValueError):
        audit._ledger_closure(config, values, used, cut_sources=2, replacement_captures=1)


def test_resolution_preserves_primary_and_actual_backup_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(audit.storage, 'ROOT', tmp_path)
    primary = configuration(tmp_path)['episode_manifest'][0]
    case = dict(primary, episode_id=primary['task']+'__2026121500', env_seed=2026121500)
    rejected = [dict(episode_id=primary['episode_id'], reason='initialization_failed', budget_attempt=3,
                     source_seal_sha256='e'*64)]
    ordered = [{k: row[k] for k in ('episode_id', 'reason', 'budget_attempt')} | {'before_first_action': True}
               for row in rejected]
    resolution = dict(status='resolved', planned_slot_id=primary['episode_id'], resolved_episode_id=case['episode_id'],
        task=primary['task'], split='heldout', round=None, original_env_seed=primary['env_seed'],
        resolved_env_seed=case['env_seed'], source_protocol_sha256='a'*64, source_seal_sha256='b'*64,
        substitution_after_outcome_forbidden=True, ordered_rejections=ordered)
    folder = tmp_path/'slot_resolution'/primary['episode_id']; put(folder/'resolution.json', resolution)
    seal(folder, 'a'*64, 'resolution')
    assert audit._resolution(primary, case, {'ordered_rejections': ordered}, rejected, 'b'*64, 'a'*64, {}) == resolution
    changed = deepcopy(ordered); changed[0]['reason'] = 'failed_task'
    with pytest.raises(ValueError):
        audit._resolution(primary, case, {'ordered_rejections': changed}, rejected, 'b'*64, 'a'*64, {})


def test_full_adapter_keeps_fixed_post_assessment_without_reselection(wave, monkeypatch):
    config, cp, fp, path = wave
    from . import heldout_runner_v1 as runner
    monkeypatch.setattr(runner, 'verify_frozen', lambda *args: config)
    values = ledger(config, cuts=0, backups=0)
    raw = b''.join((json.dumps(row)+'\n').encode() for row in values.values())
    monkeypatch.setattr(audit.loader, '_ledger_snapshot', lambda: (raw, values))
    records = []
    for index, case in enumerate(config['episode_manifest'][:100]):
        identity = case['episode_id']
        records.append(dict(planned_slot_id=identity, resolved_episode_id=identity, task=case['task'],
            scene_fingerprint=f'{index:064x}', status='complete', artifact_audit_status='passed',
            scene_isolation_status='passed', no_cut=True, actual_cut=None, common_outcome=index < 60,
            resolution=dict(status='resolved', planned_slot_id=identity, resolved_episode_id=identity,
                substitution_after_outcome_forbidden=True, ordered_rejections=[])))
    monkeypatch.setattr(audit, '_labels', lambda *args: (records, list(values)[1:], 0, 0, 0))
    raw_scenes, scenes = scene_fixture(config, tmp_root=cp.parent, records=records)
    monkeypatch.setattr(audit.loader, '_scene_registry_snapshot', lambda: (raw_scenes, scenes))
    result = audit.run_audit(cp, fp, path, version='synthetic')
    output = Path(result['path']); full = audit.read(output/'result.json')
    assert full['role'] == audit.ROLE and full['status'] == 'passed'
    assert full['planned_slots'] == 100 and full['new_attempts'] == 100
    assert full['primary_assessment']['method_fixed_before_heldout'] == 'post'
    assert full['primary_assessment']['point_estimate'] == 0
    assert not full['primary_assessment']['posthoc_method_selection']
    assert 'selection_proposal' not in full
    assert not full['selection_seal_created'] and not full['selection_release_authorized']
    assert set(full['statistics']['overall']['success_counts'].values()) == {240}
    assert not (output/'selected_policy.json').exists()
    assert full['model_calls'] == full['simulator_calls'] == full['optimizer_updates'] == 0
    assert audit.read(output/'complete.json')['role'] == 'native10_heldout_readonly_audit'


def scene_fixture(config, tmp_root, records):
    old = []
    for index in range(800):
        split = 'train' if index < 600 else 'development' if index < 700 else 'calibration'
        old.append(dict(episode_id=f'previous{index}', task=config['episode_manifest'][index % 100]['task'],
            split=split, status='accepted', scene_fingerprint=f'{index+1000:064x}'))
    prefix = b''.join((json.dumps(row)+'\n').encode() for row in old)
    path = tmp_root/'before_scenes.jsonl'; path.write_bytes(prefix)
    config['heldout_preparation'] = dict(scene_registry_before=dict(snapshot_path=str(path),
        sha256=audit.storage.sha256(path), bytes=len(prefix), records=800))
    current = [dict(episode_id=row['resolved_episode_id'], task=row['task'], split='heldout',
                    status='accepted', scene_fingerprint=row['scene_fingerprint']) for row in records]
    raw = prefix+b''.join((json.dumps(row)+'\n').encode() for row in current)
    return raw, {row['episode_id']: row for row in old+current}


@pytest.mark.parametrize('mutation', ['prefix_changed', 'same_task_collision', 'old_identity'])
def test_cross_split_scene_isolation_cannot_be_bypassed(tmp_path, monkeypatch, mutation):
    monkeypatch.setattr(audit.storage, 'ROOT', tmp_path)
    config = configuration(tmp_path)
    records = [dict(resolved_episode_id=case['episode_id'], task=case['task'], scene_fingerprint=f'{i:064x}')
               for i, case in enumerate(config['episode_manifest'][:100])]
    raw, scenes = scene_fixture(config, tmp_path, records)
    assert audit._scene_coverage(config, raw, scenes, records, {})['previous_accepted_sources'] == 800
    if mutation == 'prefix_changed': raw = b'x'+raw[1:]
    elif mutation == 'same_task_collision': records[0]['scene_fingerprint'] = f'{1000:064x}'
    else: records[0]['resolved_episode_id'] = 'previous0'
    with pytest.raises(ValueError): audit._scene_coverage(config, raw, scenes, records, {})


def test_heldout_gate_rejects_changed_fixed_policy(wave):
    config, cp, fp, path = wave
    folder = path/'workers/worker_00'; row = audit.read(folder/'status.json')
    row['fixed_main_injection'] = 'direct'
    put(folder/'status.json', row); seal(folder, 'a'*64, 'guarded_heldout_worker')
    with pytest.raises(ValueError): audit._wave_gate(config, cp, fp, path, {})
