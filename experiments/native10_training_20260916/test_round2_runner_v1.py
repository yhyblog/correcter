"""New round2 entrypoint mocks; no CUDA, model, subprocess or simulation work."""
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from . import round2_runner_v1 as runner, storage


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path/'outputs'; root.mkdir()
    for module in (runner, storage, runner.legacy): monkeypatch.setattr(module, 'ROOT', root)
    cases = [dict(episode_id=f'e{i}', case_id=f'e{i}', split='train', round=2) for i in range(300)]
    config = dict(episode_manifest=cases, cpu={'worker_threads': 4}, analysis_approval={'protocol_sha256': 'a'*64},
        main_collection={'concurrency': {'workers_per_gpu': 4}, 'replacement_candidates': {row['episode_id']: [row['episode_id']+'b1', row['episode_id']+'b2'] for row in cases},
                         'banks': {runner.BANK: {'episode_ids': [row['episode_id'] for row in cases]}}},
        round2_collection={'original_collection': {'config_path': str(root/'old/config.json'), 'freeze_path': str(root/'old/freeze.json')},
                           'selected_training': {'path': str(root/'models/round1/B200')}})
    config_path, freeze_path = root/'config.json', root/'freeze.json'
    storage.dump(config_path, config); storage.dump(freeze_path, {'files': {}})
    args = SimpleNamespace(config=config_path, freeze=freeze_path, stage=runner.STAGE, bank_version=runner.BANK,
        workers=32, wave_id='synthetic', rank=0, gpu_rank=2)
    calls = []
    monkeypatch.setattr(runner.legacy, '_require_lifecycle', lambda: calls.append('lifecycle'))
    monkeypatch.setattr(runner.legacy, 'create_main_collector', lambda *args, **kwargs: pytest.fail('Must use new guarded collector'))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(set_num_threads=lambda n: calls.append(('threads', n)),
        cuda=SimpleNamespace(set_device=lambda n: calls.append(('cuda_stub', n)))))
    return config, args, calls, root


def stub_worker(monkeypatch, config, calls, *, fail=None, missing=None, backup=None):
    monkeypatch.setattr(runner, 'verify_frozen', lambda *args: config)
    collector = SimpleNamespace(engine=SimpleNamespace(close=lambda: calls.append('close')),
        loaded_identity={'status': 'passed', 'model_hashes': {'0': 'synthetic'}})
    def factory(cfg, stage, *, bank_version):
        calls.append(('factory', stage, bank_version)); return collector
    def slot(received, case):
        assert received is collector; identity = case['episode_id']; calls.append(('slot', identity))
        if identity == fail: raise RuntimeError('synthetic reset failure')
        if identity == missing:
            return dict(status='missing_unique_initial_scene', planned_slot_id=identity, resolved_episode_id=None,
                        ordered_rejections=[{'reason': 'duplicate_initial_scene'}]*3, outcome_unknown=True)
        return dict(status='complete', planned_slot_id=identity, resolved_episode_id=identity+'b1' if identity==backup else identity,
                    ordered_rejections=[{'reason': 'duplicate_initial_scene'}] if identity==backup else [], actual_branch_count=56, no_cut=False)
    monkeypatch.setattr(runner, 'create_round2_collector', factory)
    monkeypatch.setattr(runner, 'collect_round2_slot', slot)


def test_worker_calls_new_collector_and_accepts_only_registered_backup(setup, monkeypatch):
    cfg, args, calls, _ = setup; stub_worker(monkeypatch, cfg, calls, backup='e0')
    runner.worker(args)
    assert calls[0]=='lifecycle' and calls[-1]=='close'
    assert [x[1] for x in calls if isinstance(x,tuple) and x[0]=='slot'] == ['e'+str(i) for i in range(0,300,32)]
    folder=runner.execution_root(args.stage,args.bank_version,args.wave_id)/'workers/worker_00'
    result=json.loads((folder/'status.json').read_text())
    assert result['status']=='complete' and result['primary_capture_allowed']
    assert result['actual_branch_count']==560 and result['attempted_replacement_records']==1
    assert json.loads((folder/'loaded_model_identity.json').read_text())['status']=='passed'
    assert not result['next_stage_automatically_started']


def test_exhausted_duplicate_chain_remains_missing_in_plan(setup, monkeypatch):
    cfg,args,calls,_=setup;stub_worker(monkeypatch,cfg,calls,missing='e0')
    runner.worker(args)
    folder=runner.execution_root(args.stage,args.bank_version,args.wave_id)/'workers/worker_00'
    result=json.loads((folder/'status.json').read_text())
    assert result['status']=='complete_with_missing_slots' and result['missing_slot_ids']==['e0']
    assert result['completed_slot_records']==10 and result['actual_branch_count']==504


def test_worker_failure_is_preserved_without_retry_and_closes(setup,monkeypatch):
    cfg,args,calls,_=setup;stub_worker(monkeypatch,cfg,calls,fail='e32')
    with pytest.raises(RuntimeError,match='reset failure'): runner.worker(args)
    assert calls[-1]=='close'
    assert [x[1] for x in calls if isinstance(x,tuple) and x[0]=='slot']==['e0','e32']
    folder=runner.execution_root(args.stage,args.bank_version,args.wave_id)/'workers/worker_00'
    row=json.loads((folder/'failure.json').read_text())
    assert row['attempts_not_rolled_back'] and not row['automatic_retry']
    assert not (folder/'complete.json').exists()


def test_exact_300_assignment_once(setup):
    cfg,*_=setup
    ids=[row['episode_id'] for rank in range(32) for row in runner.legacy.assigned_slots(cfg,runner.BANK,rank,32)]
    assert len(ids)==len(set(ids))==300


def test_launch_spec_new_entrypoint_8x4_and17400_scope(setup,monkeypatch):
    cfg,args,_,_=setup;monkeypatch.setattr(runner,'verify_frozen',lambda *args:cfg)
    spec=json.loads(runner.launch_spec(args).read_text())
    assert spec['workers']==32 and len(spec['jobs'])==8 and spec['hold_idle'] is False
    assert spec['primary_capture_limit']==300 and spec['expected_branches']==16800 and spec['hard_attempt_limit']==17400
    assert spec['source_capture_allowed'] and spec['replacement_allowed']
    assert all(job['command'][1].endswith('/run_round2_gpu_v1.sh') for job in spec['jobs'])
    with pytest.raises(FileExistsError):runner.launch_spec(args)


@pytest.mark.parametrize('code',[0,9])
def test_lifecycle_covers_whole_wave_even_failure(setup,monkeypatch,code):
    cfg,args,calls,_=setup;monkeypatch.setattr(runner,'verify_frozen',lambda *args:cfg)
    def run(command,**kwargs):
        assert command[1].endswith('/gpu_occupancy_lifecycle.sh') and command[2:4]==['run','--']
        calls.append(command);return SimpleNamespace(returncode=code)
    monkeypatch.setattr(runner.subprocess,'run',run)
    assert runner.launch(args)==code
    row=json.loads((runner.execution_root(args.stage,args.bank_version,args.wave_id)/'launch_result.json').read_text())
    assert row['lifecycle_covers_entire_wave'] and not row['next_stage_automatically_started']


def test_supervisor_launches_only_new_module_workers(setup,monkeypatch):
    cfg,args,calls,_=setup;monkeypatch.setattr(runner,'verify_frozen',lambda *args:cfg);commands=[]
    class Process:
        returncode=0
        def poll(self):return 0
        def wait(self,**kwargs):return 0
    def popen(cmd,**kwargs):commands.append(cmd);return Process()
    monkeypatch.setattr(runner.subprocess,'Popen',popen);runner.supervisor(args)
    assert [cmd[cmd.index('--rank')+1] for cmd in commands]==['2','10','18','26']
    assert all(cmd[cmd.index('-m')+1]==runner.MODULE for cmd in commands)


@pytest.mark.parametrize('stage,workers',[('round1_development_policy',32),('heldout',32),(runner.STAGE,16)])
def test_other_stage_or_parallelism_fails_before_reads(stage,workers,monkeypatch):
    monkeypatch.setattr(runner.legacy,'verify_frozen',lambda *args:pytest.fail('No read before stage rejection'))
    with pytest.raises(ValueError,match='only round2_labels'):
        runner.verify_frozen('missing','missing',stage,runner.BANK,workers)


def test_release_is_checked_before_engine_and_guard_dependencies_required(setup,monkeypatch):
    cfg,args,calls,root=setup;monkeypatch.setattr(runner.legacy,'verify_frozen',lambda *args:cfg)
    def inputs(config,bank_version,*,require_release):
        assert require_release is True
        return {'scene_registry_before':{'snapshot_path':str(root/'scene_snapshot.jsonl')}}
    monkeypatch.setattr(runner,'validate_round2_inputs',inputs)
    with pytest.raises(ValueError,match='omits guard/runner'):
        runner.verify_frozen(args.config,args.freeze,args.stage,args.bank_version,32)


def test_new_shell_names_only_new_runner():
    script=(runner.CODE/'run_round2_gpu_v1.sh').read_text()
    assert '-m '+runner.MODULE+' "$@"' in script
    assert 'vla-corrector-mesa.env' in script and 'prepare_torch_runtime.sh' in script
    assert 'policy5_runner' not in script and 'main_runner "$@"' not in script
