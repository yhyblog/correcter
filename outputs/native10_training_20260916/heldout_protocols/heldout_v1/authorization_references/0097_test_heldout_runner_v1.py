"""Synthetic heldout entry wiring; never load a model or simulator."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from . import heldout_runner_v1 as runner
from . import storage


def fixture_inputs(tmp_path, monkeypatch):
    root = tmp_path/'outputs'
    root.mkdir()
    for module in (runner, runner.legacy, storage):
        monkeypatch.setattr(module, 'ROOT', root)
    cases = [dict(episode_id=f'cal{i}', case_id=f'cal{i}', split='heldout')
             for i in range(100)]
    config = dict(heldout_collection={'final_selection':{'path':'syntheticselection','seal_sha256':'s','result_sha256':'r'}},cpu={'worker_threads': 4}, episode_manifest=cases,
        analysis_approval={'protocol_sha256': 'a'*64},
        main_collection=dict(concurrency={'workers_per_gpu': 4},
            banks={runner.BANK: {'episode_ids': [c['episode_id'] for c in cases]}},
            replacement_candidates={c['episode_id']: [c['episode_id']+'_backup1',
                c['episode_id']+'_backup2'] for c in cases}))
    cp, fp = root/'config.json', root/'freeze.json'
    cp.write_text(json.dumps(config)); fp.write_text('{}')
    args = SimpleNamespace(config=cp, freeze=fp, stage=runner.STAGE,
        bank_version=runner.BANK, workers=32, wave_id='synthetic', rank=0)
    monkeypatch.setattr(runner, 'verify_frozen', lambda *a: config)
    return root, config, args


@pytest.mark.parametrize('mode', ['complete', 'replacement', 'missing', 'failure'])
def test_worker_new_capture_guard_and_ordered_slot_entry(tmp_path, monkeypatch, mode):
    _, config, args = fixture_inputs(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(runner.legacy, '_require_lifecycle', lambda: calls.append('lifecycle'))
    monkeypatch.setattr(runner.legacy, 'create_main_collector',
                        lambda *a, **k: pytest.fail('unguarded collector'))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(
        set_num_threads=lambda n: None,
        cuda=SimpleNamespace(set_device=lambda n: calls.append('cuda_stub'))))
    collector = SimpleNamespace(loaded_identity={'status': 'synthetic'},
        engine=SimpleNamespace(close=lambda: calls.append('closed')))
    def factory(received, stage, *, bank_version):
        assert received is config and stage == 'heldout'
        assert bank_version == 'heldout_policy_v1'
        calls.append('heldout_factory')
        return collector
    def slot(received, case):
        assert received is collector and case['split'] == 'heldout'
        calls.append(case['episode_id'])
        identity = case['episode_id']
        if identity == 'cal32' and mode == 'failure':
            raise RuntimeError('synthetic technical error')
        missing = identity == 'cal32' and mode == 'missing'
        replacement = identity == 'cal32' and mode == 'replacement'
        common = identity == 'cal96'
        return dict(status='missing_unique_initial_scene' if missing else 'complete',
            planned_slot_id=identity, resolved_episode_id=None if missing else
            identity+'_backup1' if replacement else identity,
            ordered_rejections=[{'before_first_action': True}] if replacement else [],
            actual_branch_count=0 if common or missing else 20, no_cut=common)
    monkeypatch.setattr(runner, 'create_heldout_collector', factory)
    monkeypatch.setattr(runner, 'collect_heldout_slot', slot)
    if mode == 'failure':
        with pytest.raises(RuntimeError, match='technical error'):
            runner.worker(args)
    else:
        runner.worker(args)
    assert calls[:3] == ['lifecycle', 'cuda_stub', 'heldout_factory']
    assert calls[-1] == 'closed'
    folder = runner.execution_root(args.stage, args.bank_version, args.wave_id)/'workers/worker_00'
    result = json.loads((folder/('failure.json' if mode == 'failure' else 'status.json')).read_text())
    assert result['next_stage_automatically_started'] is False
    if mode == 'failure':
        assert calls[3:-1] == ['cal0', 'cal32']
        assert result['attempts_not_rolled_back'] and not result['automatic_retry']
        assert result['source_capture_allowed'] and result['replacement_allowed']
    else:
        assert calls[3:-1] == ['cal0', 'cal32', 'cal64', 'cal96']
        assert result['completed_slot_records'] == 4
        assert result['primary_capture_allowed'] is True
        assert result['global_choice_applied_during_collection'] is False
        assert result['actual_branch_count'] == (40 if mode == 'missing' else 60)
        assert result['missing_slot_ids'] == (['cal32'] if mode == 'missing' else [])
        assert result['attempted_replacement_records'] == (1 if mode == 'replacement' else 0)


def test_unreleased_or_wrong_stage_denied_before_cuda_or_artifact_creation(tmp_path, monkeypatch):
    args = SimpleNamespace(config='unused', freeze='unused', stage='heldout',
        bank_version='heldout_policy_v1', workers=32, wave_id='unused', rank=0)
    def denied(*a):
        raise ValueError('heldout scope not released')
    monkeypatch.setattr(runner, 'verify_frozen', denied)
    monkeypatch.setattr(runner.legacy, '_require_lifecycle', lambda: pytest.fail('unreleased lifecycle'))
    monkeypatch.setattr(runner, 'create_heldout_collector', lambda *a, **k: pytest.fail('model access'))
    with pytest.raises(ValueError, match='not released'):
        runner.worker(args)


def test_other_stages_and_concurrency_denied_before_read(monkeypatch):
    monkeypatch.setattr(runner.legacy, 'verify_frozen', lambda *a: pytest.fail('read before stage guard'))
    for stage in ['round2_development_policy', 'calibration', 'training_final', 'round2_labels']:
        with pytest.raises(ValueError, match='only heldout'):
            runner.verify_frozen('unused', 'unused', stage, runner.BANK, 32)
    with pytest.raises(ValueError, match='32 workers'):
        runner.verify_frozen('unused', 'unused', runner.STAGE, runner.BANK, 8)


def test_actual_verify_entry_requires_full_authorization_inventory(monkeypatch, tmp_path):
    base, training, scene = tmp_path/'old', tmp_path/'training', tmp_path/'scene.jsonl'
    config = dict(heldout_collection=dict(
        original_collection={'config_path': str(base/'config.json'), 'freeze_path': str(base/'freeze.json')},
        selected_training={'path': str(training)},final_selection={'path':str(tmp_path/'selection')}))
    required = [runner.CODE/name for name in runner.REQUIRED_CODE]
    required += [base/'config.json', base/'freeze.json', training/'complete.json',
        training/'result.json', training/'selected_reload_audit.json', training/'selected/complete.json',
        training/'selected/config.json', scene,tmp_path/'selection/complete.json',tmp_path/'selection/result.json']
    frozen = {'files': {str(path.resolve()): 'a'*64 for path in required}}
    calls = []
    monkeypatch.setattr(runner.legacy, 'verify_frozen', lambda *a: config)
    monkeypatch.setattr(runner.legacy, 'worker_layout', lambda *a: (4, 32))
    monkeypatch.setattr(runner.legacy, '_json', lambda *a: frozen)
    def validate(received, bank, *, require_release):
        assert received is config and bank == runner.BANK and require_release
        calls.append('heldout_release_and_inputs')
        return {'scene_registry_before': {'snapshot_path': str(scene)}}
    monkeypatch.setattr(runner, 'validate_heldout_inputs', validate)
    def inventory(received, seal):
        assert received is config and seal is frozen
        calls.append('complete_authorization_inventory')
    monkeypatch.setattr(runner, 'verify_authorization_inventory', inventory)
    assert runner.verify_frozen('unused', 'unused', runner.STAGE, runner.BANK, 32) is config
    assert calls == ['heldout_release_and_inputs', 'complete_authorization_inventory']
    def refuse(*a):
        raise ValueError('missing absolute authorization reference')
    monkeypatch.setattr(runner, 'verify_authorization_inventory', refuse)
    with pytest.raises(ValueError, match='absolute authorization'):
        runner.verify_frozen('unused', 'unused', runner.STAGE, runner.BANK, 32)


def test_wave_spec_has_new_capture_five_ungated_arms_two_suffixes(tmp_path, monkeypatch):
    _, _, args = fixture_inputs(tmp_path, monkeypatch)
    spec = json.loads(runner.launch_spec(args).read_text())
    assert len(spec['jobs']) == 8 and spec['workers'] == 32 and not spec['hold_idle']
    assert spec['primary_capture_limit'] == spec['expected_candidate_restores'] == 100
    assert spec['expected_branches'] == 100*5*4 and spec['hard_attempt_limit'] == 2200
    assert spec['paired_suffixes_per_state'] == 4
    assert spec['source_capture_allowed'] and spec['replacement_allowed']
    assert spec['physical_arms'] == ['continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post']
    assert not spec['global_choice_applied_during_collection']
    assert not spec['selection_automatically_started']
    assert all('run_heldout_gpu_v1.sh' in job['command'][1] for job in spec['jobs'])
    shell = (runner.CODE/'run_heldout_gpu_v1.sh').read_text()
    assert 'native10_training_20260916.heldout_runner_v1' in shell


def test_launch_wraps_whole_wave_and_preserves_failure(tmp_path, monkeypatch):
    _, _, args = fixture_inputs(tmp_path, monkeypatch)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=7)
    monkeypatch.setattr(runner.subprocess, 'run', run)
    assert runner.launch(args) == 7
    assert len(calls) == 1
    assert calls[0][1].endswith('/gpu_occupancy_lifecycle.sh') and calls[0][2:4] == ['run', '--']
    result = json.loads((runner.execution_root(args.stage, args.bank_version, args.wave_id)/'launch_result.json').read_text())
    assert result['status'] == 'failed' and result['lifecycle_covers_entire_wave']
    assert not result['next_stage_automatically_started']
