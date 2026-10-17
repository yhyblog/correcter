"""Mock-only launcher checks: subprocesses, CUDA and guarded slots are stubs."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from . import policy5_runner_v1 as runner, storage


def read(path):
    return json.loads(Path(path).read_text())


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path/'outputs'
    for module in (runner, storage, runner.legacy):
        monkeypatch.setattr(module, 'ROOT', root)
    cases = [dict(episode_id=f'e{i}', case_id=f'e{i}', split='development') for i in range(100)]
    config = dict(episode_manifest=cases, cpu={'worker_threads': 4},
        analysis_approval={'protocol_sha256': 'b'*64},
        main_collection={'concurrency': {'workers_per_gpu': 4},
                         'banks': {'new': {'episode_ids': [row['episode_id'] for row in cases]}}},
        policy_deployment={'old_collection': {'config_path': str(root/'old/config.json'),
                                             'freeze_path': str(root/'old/freeze.json')},
                           'selected_training': {'path': str(root/'models/round1/selected_training')}})
    root.mkdir()
    config_path, freeze_path = root/'config.json', root/'freeze.json'
    storage.dump(config_path, config); storage.dump(freeze_path, {'files': {}})
    args = SimpleNamespace(config=config_path, freeze=freeze_path, stage=runner.STAGE,
        bank_version='new', workers=32, wave_id='synthetic', rank=0, gpu_rank=2)
    calls = []
    monkeypatch.setattr(runner.legacy, '_require_lifecycle', lambda: calls.append('lifecycle'))
    monkeypatch.setattr(runner.legacy, 'resolve_slot', lambda *args: pytest.fail('Old replacement resolver is forbidden'))
    monkeypatch.setattr(runner.legacy, 'create_main_collector', lambda *args, **kwargs: pytest.fail('Old factory is forbidden'))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(
        set_num_threads=lambda n: calls.append(('threads', n)),
        cuda=SimpleNamespace(set_device=lambda n: calls.append(('cuda_stub', n)))))
    return config, args, calls, root


def use_guard_stubs(monkeypatch, config, calls, *, fail_episode=None, invalid_resolution=False):
    monkeypatch.setattr(runner, 'verify_frozen', lambda *args: config)
    collector = SimpleNamespace(engine=SimpleNamespace(close=lambda: calls.append('close')))
    def factory(cfg, stage, *, bank_version):
        calls.append(('guard_factory', stage, bank_version))
        return collector
    def slot(received, case):
        assert received is collector
        calls.append(('guard_slot', case['episode_id']))
        if case['episode_id'] == fail_episode:
            raise RuntimeError('mock branch error, prior attempt stays counted')
        no_cut = int(case['episode_id'][1:]) >= 95
        return dict(status='complete', planned_slot_id=case['episode_id'],
            resolved_episode_id='replacement' if invalid_resolution else case['episode_id'],
            ordered_rejections=[], actual_branch_count=0 if no_cut else 20, no_cut=no_cut)
    monkeypatch.setattr(runner, 'create_policy_collector', factory)
    monkeypatch.setattr(runner, 'collect_existing_slot', slot)


def test_worker_uses_only_guarded_factory_existing_slots_and_closes(setup, monkeypatch):
    config, args, calls, _ = setup
    use_guard_stubs(monkeypatch, config, calls)
    runner.worker(args)
    assert calls[0] == 'lifecycle'
    assert [value[1] for value in calls if isinstance(value, tuple) and value[0] == 'guard_slot'] == ['e0', 'e32', 'e64', 'e96']
    assert calls[-1] == 'close'
    root = runner.execution_root(args.stage, args.bank_version, args.wave_id)/'workers/worker_00'
    row = read(root/'status.json')
    assert row['status'] == 'complete' and row['no_cut_sources'] == 1
    assert row['actual_branch_count'] == 60 and row['source_captures'] == 0
    assert row['attempted_replacement_records'] == 0 and not row['next_stage_automatically_started']
    assert (root/'complete.json').is_file()


def test_worker_failure_stops_without_automatic_retry_and_closes(setup, monkeypatch):
    config, args, calls, _ = setup
    use_guard_stubs(monkeypatch, config, calls, fail_episode='e32')
    with pytest.raises(RuntimeError, match='mock branch error'):
        runner.worker(args)
    slots = [value[1] for value in calls if isinstance(value, tuple) and value[0] == 'guard_slot']
    assert slots == ['e0', 'e32'] and calls[-1] == 'close'
    root = runner.execution_root(args.stage, args.bank_version, args.wave_id)/'workers/worker_00'
    row = read(root/'failure.json')
    assert row['attempts_not_rolled_back'] and not row['automatic_retry']
    assert not row['source_capture_allowed'] and not row['replacement_allowed']
    assert not (root/'complete.json').exists()


def test_worker_rejects_any_replacement_result(setup, monkeypatch):
    config, args, calls, _ = setup
    use_guard_stubs(monkeypatch, config, calls, invalid_resolution=True)
    with pytest.raises(ValueError, match='replaced'):
        runner.worker(args)
    assert calls[-1] == 'close'


def test_lifecycle_guard_runs_before_any_cuda_or_factory(setup, monkeypatch):
    config, args, calls, _ = setup
    use_guard_stubs(monkeypatch, config, calls)
    def deny():
        raise RuntimeError('No formal lifecycle ancestor')
    monkeypatch.setattr(runner.legacy, '_require_lifecycle', deny)
    with pytest.raises(RuntimeError, match='lifecycle'):
        runner.worker(args)
    assert calls == []


def test_strided32workers_cover_original100_once(setup):
    config, _, _, _ = setup
    assigned = [case['episode_id'] for rank in range(32)
                for case in runner.legacy.assigned_slots(config, 'new', rank, 32)]
    assert len(assigned) == len(set(assigned)) == 100
    assert set(assigned) == {'e'+str(i) for i in range(100)}


def test_launch_spec_keeps_eight_gpu_wave_and_new_entrypoint(setup, monkeypatch):
    config, args, _, _ = setup
    monkeypatch.setattr(runner, 'verify_frozen', lambda *args: config)
    path = runner.launch_spec(args)
    row = read(path)
    assert row['hold_idle'] is False and row['workers'] == 32
    assert row['expected_branches'] == 1900 and row['expected_candidate_restores'] == 95
    assert row['hard_attempt_limit'] == 2100 and row['original_sources'] == 100
    assert [job['devices'] for job in row['jobs']] == [[i] for i in range(8)]
    for job in row['jobs']:
        assert job['command'][1].endswith('/run_policy5_gpu_v1.sh')
        assert job['command'][-2:] == ['--workers', '32']
    with pytest.raises(FileExistsError):
        runner.launch_spec(args)


@pytest.mark.parametrize('returncode', [0, 9])
def test_lifecycle_wraps_entire_launch_on_success_and_failure(setup, monkeypatch, returncode):
    config, args, calls, _ = setup
    monkeypatch.setattr(runner, 'verify_frozen', lambda *args: config)
    def run(command, *, cwd):
        calls.append(command)
        assert command[1].endswith('/gpu_occupancy_lifecycle.sh')
        assert command[2:4] == ['run', '--']
        return SimpleNamespace(returncode=returncode)
    monkeypatch.setattr(runner.subprocess, 'run', run)
    assert runner.launch(args) == returncode
    result = read(runner.execution_root(args.stage, args.bank_version, args.wave_id)/'launch_result.json')
    assert result['lifecycle_covers_entire_wave'] and not result['hold_idle']
    assert not result['next_stage_automatically_started']
    assert result['status'] == ('complete' if returncode == 0 else 'failed')


def test_supervisor_spawns_four_new_module_workers_on_fixed_ranks(setup, monkeypatch):
    config, args, calls, _ = setup
    monkeypatch.setattr(runner, 'verify_frozen', lambda *args: config)
    commands = []
    class Process:
        returncode = 0
        def poll(self): return self.returncode
        def wait(self, **kwargs): return self.returncode
    def popen(command, **kwargs):
        commands.append(command)
        return Process()
    monkeypatch.setattr(runner.subprocess, 'Popen', popen)
    runner.supervisor(args)
    assert calls == ['lifecycle']
    assert [cmd[cmd.index('--rank')+1] for cmd in commands] == ['2', '10', '18', '26']
    assert all(cmd[cmd.index('-m')+1] == runner.MODULE for cmd in commands)


def test_verify_requires_new_guard_training_and_source_seals(setup, monkeypatch):
    config, args, _, root = setup
    inputs = {'sources': {'e0': {'source_path': str(root/'sources/e0'),
        'resolution_path': str(root/'slot_resolution/e0'), 'old_bank_path': str(root/'banks/old/e0/cut005')}}}
    monkeypatch.setattr(runner.legacy, 'verify_frozen', lambda *args: config)
    monkeypatch.setattr(runner, 'validate_deployment_inputs', lambda *args: inputs)
    with pytest.raises(ValueError, match='omits'):
        runner.verify_frozen(args.config, args.freeze, args.stage, args.bank_version, 32)
    training = Path(config['policy_deployment']['selected_training']['path'])
    required = [runner.CODE/name for name in runner.REQUIRED_CODE]
    required += [root/'old/config.json', root/'old/freeze.json']
    required += [training/name for name in ['complete.json', 'result.json', 'selected_reload_audit.json',
                                           'selected/complete.json', 'selected/config.json']]
    required += [root/name for name in ['sources/e0/complete.json', 'slot_resolution/e0/complete.json', 'banks/old/e0/cut005/complete.json']]
    args.freeze.write_text(json.dumps({'files': {str(path): 'stub' for path in required}}))
    assert runner.verify_frozen(args.config, args.freeze, args.stage, args.bank_version, 32) is config
    config['main_collection']['concurrency']['workers_per_gpu'] = 2
    with pytest.raises(ValueError, match='workers|eight GPUs'):
        runner.verify_frozen(args.config, args.freeze, args.stage, args.bank_version, 32)


@pytest.mark.parametrize('stage,workers', [('round2_development_policy', 32), ('heldout', 32), (runner.STAGE, 16)])
def test_no_other_stage_or_worker_count_can_launch(stage, workers, monkeypatch):
    monkeypatch.setattr(runner.legacy, 'verify_frozen', lambda *args: pytest.fail('Must fail before reads'))
    with pytest.raises(ValueError, match='only round1_development_policy'):
        runner.verify_frozen('missing', 'missing', stage, 'new', workers)


def test_shell_points_to_guarded_runner_and_keeps_frozen_runtime_environment():
    shell = (runner.CODE/'run_policy5_gpu_v1.sh').read_text()
    assert '-m '+runner.MODULE+' "$@"' in shell
    assert 'vla-corrector-mesa.env' in shell and 'prepare_torch_runtime.sh' in shell
    assert 'PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1' in shell
    assert 'main_runner "$@"' not in shell
