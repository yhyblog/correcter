"""Entrypoint-only synthetic tests: subprocess, GPU and collector are mocked."""
from copy import deepcopy
import json
from types import SimpleNamespace
import sys

import pytest
from . import runner as subject, protocol, storage
from .collection import SOLO_METHODS


def config(count=32):
    size=100 if count==32 else 5;ids=[f'case{i}' for i in range(size)]
    cases=[{'episode_id':key} for key in ids]
    return dict(episode_manifest=cases,cpu={'worker_threads':4},analysis_approval={'protocol_sha256':'p'*64},
        inputs={'sources':{key:{'no_cut':count==32 and i>=98} for i,key in enumerate(ids)}},
        execution_plans={protocol.FORMAL:dict(episode_ids=ids,methods=list(SOLO_METHODS),
            repeats=[0,1,2,3] if count==32 else [0],bank_mode='solo',workers=count,
            expected_attempts=1274 if count==32 else 20)})


def arguments(tmp_path,workers=32):
    cfg=tmp_path/'config.json';cfg.write_text('{}')
    freeze=tmp_path/'freeze.json';freeze.write_text('{}')
    return SimpleNamespace(config=cfg,freeze=freeze,stage=protocol.FORMAL,workers=workers,
        wave_id='synthetic_v1',rank=0,gpu_rank=0)


@pytest.mark.parametrize('workers,copies,gpus',[(5,1,5),(32,4,8)])
def test_worker_layout_and_exact_source_partition(workers,copies,gpus):
    cfg=config(workers)
    assert subject.worker_layout(cfg,protocol.FORMAL,workers)==(copies,gpus)
    groups=[subject.assigned_slots(cfg,protocol.FORMAL,r,workers) for r in range(workers)]
    flat=[row['episode_id'] for group in groups for row in group]
    expected=cfg['execution_plans'][protocol.FORMAL]['episode_ids']
    assert len(flat)==len(set(flat))==len(expected) and set(flat)==set(expected)
    assert all(groups)
    with pytest.raises(ValueError):subject.worker_layout(cfg,protocol.FORMAL,workers+1)


def test_new_freeze_entry_delegated_with_explicit_stage(tmp_path,monkeypatch):
    from . import prepare
    args=arguments(tmp_path);calls=[]
    def verify(*values):calls.append(values);return config()
    monkeypatch.setattr(prepare,'verify_frozen',verify)
    assert subject.verify_frozen(args.config,args.freeze,args.stage,32)==config()
    assert calls==[(args.config,args.freeze,args.stage)]


def test_release_failure_precedes_lifecycle_or_gpu(tmp_path,monkeypatch):
    args=arguments(tmp_path)
    def denied(*a,**k):raise ValueError('new stage locked')
    monkeypatch.setattr(subject,'verify_frozen',denied)
    monkeypatch.setattr(subject,'require_lifecycle',lambda:pytest.fail('lifecycle reached'))
    monkeypatch.setattr(subject,'create_collector',lambda *a:pytest.fail('model reached'))
    with pytest.raises(ValueError,match='stage locked'):subject.worker(args)


def test_missing_lifecycle_precedes_gpu_and_engine(tmp_path,monkeypatch):
    args=arguments(tmp_path)
    monkeypatch.setattr(subject,'verify_frozen',lambda *a:config())
    def denied():raise RuntimeError('missing lifecycle ancestor')
    monkeypatch.setattr(subject,'require_lifecycle',denied)
    monkeypatch.setattr(subject,'create_collector',lambda *a:pytest.fail('model reached'))
    with pytest.raises(RuntimeError,match='lifecycle ancestor'):subject.worker(args)


@pytest.mark.parametrize('workers,jobs',[(5,5),(32,8)])
def test_stage_wave_specs_never_start_idle_holders(tmp_path,monkeypatch,workers,jobs):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'new')
    monkeypatch.setattr(subject,'verify_frozen',lambda *a:config(workers))
    args=arguments(tmp_path,workers);path=subject.launch_spec(args)
    spec=json.loads(path.read_text())
    assert spec['workers']==workers and len(spec['jobs'])==jobs
    assert spec['hold_idle'] is False and spec['whole_wave_reserves_all_eight_gpus'] is True
    assert not spec['source_capture_allowed'] and not spec['replacement_allowed']
    assert spec['episode_ids']==config(workers)['execution_plans'][args.stage]['episode_ids']
    assert [job['devices'] for job in spec['jobs']]==[[i] for i in range(jobs)]
    assert all('supervisor' in job['command'] for job in spec['jobs'])
    with pytest.raises(FileExistsError):subject.launch_spec(args)


@pytest.mark.parametrize('returncode',[0,3])
def test_launch_uses_one_entire_wave_lifecycle_and_no_retry(tmp_path,monkeypatch,returncode):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'new')
    monkeypatch.setattr(subject,'verify_frozen',lambda *a:config())
    calls=[]
    def run(command,**kwargs):calls.append((command,kwargs));return SimpleNamespace(returncode=returncode)
    monkeypatch.setattr(subject.subprocess,'run',run)
    args=arguments(tmp_path)
    assert subject.launch(args)==returncode and len(calls)==1
    command=calls[0][0]
    assert command[0]=='bash' and command[1].endswith('gpu_occupancy_lifecycle.sh')
    assert command[2:4]==['run','--']
    result=json.loads((subject.execution_root(args.stage,args.wave_id)/'launch_result.json').read_text())
    assert result['status']==('complete' if returncode==0 else 'failed')
    assert result['lifecycle_covers_entire_wave'] and not result['hold_idle']
    assert not result['automatic_retry'] and not result['next_stage_automatically_started']


def test_generation_failure_evidence_preserved_no_retry(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'new')
    args=arguments(tmp_path);cfg=config()
    monkeypatch.setattr(subject,'verify_frozen',lambda *a:cfg)
    monkeypatch.setattr(subject,'require_lifecycle',lambda:None)
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(set_num_threads=lambda n:None,
        cuda=SimpleNamespace(set_device=lambda n:None)))
    class Error(RuntimeError):
        evidence={'completed_proposal_policy_calls':1,'synthetic_only':True}
    class Collector:
        loaded_identity={'synthetic_only':True}
        def __init__(self):self.closed=False;self.engine=self
        def collect_episode(self,case):raise Error('generation failed')
        def close(self):self.closed=True
    fake=Collector();monkeypatch.setattr(subject,'create_collector',lambda *a:fake)
    with pytest.raises(Error):subject.worker(args)
    folder=subject.execution_root(args.stage,args.wave_id)/'workers/worker_00'
    error=json.loads((folder/'failure.json').read_text())
    assert error['generation_failure_evidence']==Error.evidence
    assert error['attempts_preserved'] and not error['automatic_retry']
    assert fake.closed and not (folder/'complete.json').exists()


def test_unsafe_wave_component_rejected():
    for value in ('../old','/tmp/escape','',None,'two/waves'):
        with pytest.raises(ValueError):subject.component(value)
