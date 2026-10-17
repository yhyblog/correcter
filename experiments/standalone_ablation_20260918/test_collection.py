"""Synthetic fake-runtime tests; no real simulator, model or old artifact reads."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

from . import collection as subject, candidates, storage, protocol
from . import reference_generation
from experiments.native10_training_20260916.semantics import QueueSnapshot
from ac_tmil.idea3.local_collection import Trace


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def seal_old(path, protocol_sha):
    write_json(path/'complete.json', dict(status='complete', protocol_sha256=protocol_sha,
        files={str(p.relative_to(path)):storage.sha256(p) for p in path.rglob('*') if p.is_file()}))
    return storage.sha256(path/'complete.json')


class Ledger:
    def __init__(self): self.rows=[]
    def reserve(self, stage, kind, key):
        row=dict(number=len(self.rows)+1, stage=stage, kind=kind, key=key)
        self.rows.append(row)
        return row


class Runtime:
    """A counter-only substitute, never a physics engine."""
    def __init__(self, ledger): self.ledger=ledger;self.resets=[];self.t=0;self.terminal_at=27
    def reset(self, case, horizon):
        assert self.ledger.rows, 'Restore occurred before reserve'
        self.resets.append((case['episode_id'],horizon,len(self.ledger.rows)));self.t=0
    def physics_state(self): return np.asarray([self.t],np.float64)
    def frame(self): return np.full((2,2,3),self.t,np.uint8)
    def fingerprint(self): return {'clock':self.t,'synthetic':True}
    def step(self, command):
        self.t+=1
        return dict(reward=0.,success=False,done=self.t>=self.terminal_at)


class Engine:
    def __init__(self, runtime, raw, matching):
        self.runtime=runtime;self.raw=raw;self.matching=matching;self.calls=[];self.seeds=[]
        self.loaded_identity={'synthetic':True,'member_hashes':{'member0':'a'*64}}
        self.closed=False
    def verify(self): return True
    def close(self): self.closed=True
    def generate_solo(self, observed, case, cut, method):
        self.calls.append((method,tuple(observed),case['episode_id'],cut))
        scalar={'solo_post':1.,'solo_direct':2.,'solo_velocity':-1.}[method]
        direction=np.full((10,4),scalar,np.float32)
        plan,matching,arrays=candidates.project_solo(self.raw.copy(),direction,self.matching)
        arrays.update(post_command_gradient=np.ones((10,4),np.float32),
            post_internal_metric_direction=np.ones((10,4),np.float32))
        return plan,dict(method=method,base_seed=9,noise_sha256='n'*64,matching=matching),arrays
    def propose(self, seed):
        self.seeds.append(seed)
        return self.raw.copy(),dict(policy_calls=1,seconds=0.,noise_sha256=hashlib.sha256(str(seed).encode()).hexdigest())


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'isolated')
    monkeypatch.setattr(protocol,'validate_config',lambda *a,**k:None)
    monkeypatch.setattr(protocol,'require_stage_budget',lambda *a,**k:None)
    ledger=Ledger();runtime=Runtime(ledger)
    raw=np.zeros((50,4),np.float32);raw[:2,3]=np.float32(1.3);raw[10:,3]=np.float32(-1.4)
    case=dict(episode_id='disassemble-v3__101',case_id='disassemble-v3__101',
        task='disassemble-v3',env_seed=101,split='heldout',round=None,cut_rule={'kind':'first_alarm'})
    source=tmp_path/'archive/source';cut=source/'cut005';cut.mkdir(parents=True)
    # Produce the pre-existing toy prefix without invoking reset or any engine.
    trace=Trace(runtime)
    for i in range(5):trace.execute(runtime,raw[i])
    np.savez(source/'trajectory.npz',**trace.arrays())
    observed={k:np.zeros((2,),np.float32) for k in subject.STATE_KEYS}
    np.savez(cut/'context.npz',**observed,full_plan=raw)
    snapshot=QueueSnapshot(raw,0,5)
    write_json(cut/'anchor.json',dict(queue=snapshot.to_dict(False),image_sha256=subject.digest(runtime.frame()),
        world_fingerprint=runtime.fingerprint()))
    write_json(source/'summary.json',dict(case=case,actual_cut=5,no_cut=False,scene_fingerprint='scene',
        source_horizon=10,control_budget=300,full_episode_outcome_available=False,success=False))
    source_sha=seal_old(source,'b'*64)
    bank=tmp_path/'archive/bank';bank.mkdir()
    base=np.clip(raw,-1,1);mask=1-np.abs(base[:10])>=.05
    np.savez(bank/'formal_directions.npz',raw_a0=raw,critic_a0=base,mask=mask,
        post_command_gradient=np.ones((10,4),np.float32),post_internal_metric_direction=np.ones((10,4),np.float32))
    write_json(bank/'generation.json',dict(base_seed=9,base_generation=dict(noise_sha256='n'*64)))
    bank_sha=seal_old(bank,'b'*64)
    row=dict(case=case,planned_slot_id=case['episode_id'],resolved_episode_id=case['episode_id'],
        source_path=str(source),source_seal_sha256=source_sha,source_protocol_sha256='b'*64,
        collection_seal_sha256='c'*64,actual_cut=5,no_cut=False,scene_fingerprint='scene',
        common_outcome=None,old_bank_path=str(bank),old_bank_seal_sha256=bank_sha)
    config=dict(episode_manifest=[case],inputs={'sources':{case['episode_id']:row}},
        seed_namespace='synthetic_namespace',control_budget=300,source_horizon=10,matching=protocol.MATCHING,
        analysis_approval={'protocol_sha256':'d'*64},execution_plans={protocol.FORMAL:dict(
            episode_ids=[case['episode_id']],methods=list(subject.SOLO_METHODS),repeats=[0,1],
            bank_mode='solo',expected_attempts=7,workers=32)})
    engine=Engine(runtime,raw,config['matching']);collector=subject.Collector(engine,config,ledger,protocol.FORMAL)
    return SimpleNamespace(config=config,case=case,row=row,source=source,raw=raw,engine=engine,
        runtime=runtime,ledger=ledger,collector=collector,tmp=tmp_path)


def test_one_restore_three_independent_entries_and_identity_guards(fixture):
    f=fixture;bank=f.collector.prepare_bank(f.case)
    assert len(f.ledger.rows)==len(f.runtime.resets)==1
    assert f.ledger.rows[0]['kind']=='candidate_restore'
    assert [c[0] for c in f.engine.calls]==list(subject.SOLO_METHODS)
    assert all(call[1]==subject.STATE_KEYS for call in f.engine.calls)
    generation=subject.read(bank/'generation.json')
    assert generation['old_bank_used_as_generation_input'] is False
    assert generation['restore_count']==1 and generation['physical_state_unchanged'] is True
    for method in subject.SOLO_METHODS:
        item=subject.read(bank/'methods'/method/'generation.json')
        assert item['source_context_file_sha256']==storage.sha256(f.source/'cut005/context.npz')
        assert item['model_identity_sha256']==f.collector.model_identity_sha256
        assert generation['guards'][method]['archived']['comparison_after_independent_generation'] is True
    subject.checked_seal(bank,expected_protocol='d'*64)


def test_branch_precharged_raw_ten_and_paired_suffix(fixture):
    f=fixture;bank=f.collector.prepare_bank(f.case)
    paths=[f.collector.branch(f.case,method,0,bank) for method in subject.SOLO_METHODS]
    rows=[subject.read(p/'summary.json') for p in paths]
    assert len(f.runtime.resets)==len(f.ledger.rows)==4
    assert [r[2] for r in f.runtime.resets]==[1,2,3,4]
    assert all(r['actual_prefix_steps']==10 and r['first_actual_resample']==15 for r in rows)
    assert all(r['suffix_seeds']==rows[0]['suffix_seeds'] for r in rows)
    assert all(r['original_queue_remaining']==5 and not r['normalized_queue_injection'] for r in rows)
    for method,path in zip(subject.SOLO_METHODS,paths):
        trajectory=subject.load_arrays(path/'trajectory.npz')
        plan=subject.load_arrays(bank/'plans.npz')[method]
        assert subject.bit_equal(trajectory['actions'][5:15],plan[:10])
        assert trajectory['actions'][5,3]>1 # Original saturated raw command preserved.
        assert trajectory['actual_sampling_steps'].tolist()==[15,25]


def test_collect_complete_without_recapture_and_no_overwrite(fixture):
    f=fixture;result=f.collector.collect_episode(f.case)
    assert result['planned_slot_id']==result['resolved_episode_id']==f.case['episode_id']
    assert result['actual_branch_count']==6 and len(f.ledger.rows)==7
    summary=subject.read(__import__('pathlib').Path(result['completion_path'])/'summary.json')
    assert summary['new_source_capture'] is False and summary['initialization_replacement'] is False
    with pytest.raises(FileExistsError):f.collector.collect_episode(f.case)
    assert len(f.ledger.rows)==7


def test_unknown_method_or_repeat_and_reference_rejected_before_reserve(fixture):
    f=fixture
    with pytest.raises(ValueError,match='restricted'):f.collector.prepare_bank(f.case,kind='reference')
    for method,repeat in [('post',0),('solo_post',3),('solo_post',True)]:
        with pytest.raises(ValueError):f.collector.branch(f.case,method,repeat,f.tmp/'missing')
    with pytest.raises(ValueError,match='forbids'):f.collector.capture(f.case)
    assert f.ledger.rows==[] and f.runtime.resets==[]


def test_generation_failure_preserves_precharged_attempt(fixture,monkeypatch):
    f=fixture
    def fail(*args):raise RuntimeError('synthetic generation failure')
    monkeypatch.setattr(f.engine,'generate_solo',fail)
    with pytest.raises(RuntimeError,match='synthetic generation'):f.collector.prepare_bank(f.case)
    path=f.collector.bank_path(f.case,'solo')
    assert len(f.ledger.rows)==len(f.runtime.resets)==1
    assert (path/'attempt.json').exists() and not (path/'complete.json').exists()
    with pytest.raises(FileExistsError):f.collector.prepare_bank(f.case)
    assert len(f.ledger.rows)==1


def test_saved_source_binding_rejected_before_restore(fixture):
    f=fixture;(f.source/'summary.json').write_text('{}')
    with pytest.raises(ValueError,match='member changed'):f.collector.prepare_bank(f.case)
    assert f.ledger.rows==[] and f.runtime.resets==[]


def test_source_replacement_or_config_mutation_rejected(fixture):
    f=fixture;case=deepcopy(f.case);case['replacement_of']='other'
    with pytest.raises(ValueError,match='registered'):f.collector._case(case)
    f.config['seed_namespace']='changed'
    with pytest.raises(ValueError,match='registered'):f.collector._case(f.case)


def test_no_cut_retains_common_without_any_new_attempt(fixture,monkeypatch):
    f=fixture;row=dict(f.row,no_cut=True,actual_cut=None,common_outcome=True)
    monkeypatch.setattr(f.collector,'_source',lambda case:(row,f.source,{}))
    result=f.collector.collect_episode(f.case)
    summary=subject.read(__import__('pathlib').Path(result['completion_path'])/'summary.json')
    assert result['no_cut'] and summary['common_outcome'] is True
    assert summary['logical_branch_count']==6 and summary['actual_branch_count']==0
    assert summary['planned_episode_retained'] and not summary['outcome_filter_applied']
    assert not f.ledger.rows and not f.engine.calls and not f.runtime.resets


@pytest.mark.parametrize('attempts,repeats,refs,ref_repeats',[
    (30,[],['alarm_replan10','post'],[0,1]),
    (50,[0],list(subject.REFERENCE_METHODS),[0]),
])
def test_preflight_30_or_50_explicit_accounting(attempts,repeats,refs,ref_repeats):
    ids=[str(i) for i in range(5)]
    config={'inputs':{'sources':{k:{'no_cut':False} for k in ids}},'execution_plans':{
        protocol.PREFLIGHT:dict(episode_ids=ids,methods=list(subject.SOLO_METHODS),repeats=repeats,
            reference_methods=refs,ref_repeats=ref_repeats,bank_mode='paired_reference',expected_attempts=attempts)}}
    assert subject.stage_plan(config,protocol.PREFLIGHT)['expected_attempts']==attempts
    config['execution_plans'][protocol.PREFLIGHT]['expected_attempts']+=1
    with pytest.raises(ValueError,match='accounting'):subject.stage_plan(config,protocol.PREFLIGHT)


def test_formal_98_cut_two_common_accounting():
    ids=[str(i) for i in range(100)]
    config={'inputs':{'sources':{k:{'no_cut':int(k)>=98} for k in ids}},'execution_plans':{
        protocol.FORMAL:dict(episode_ids=ids,methods=list(subject.SOLO_METHODS),repeats=list(range(4)),
            bank_mode='solo',expected_attempts=1274)}}
    assert subject.stage_plan(config,protocol.FORMAL)['expected_attempts']==1274


def test_pending_scope_refused_before_engine_import(monkeypatch):
    def denied(*a,**k):raise ValueError('synthetic pending gate')
    monkeypatch.setattr(protocol,'validate_config',denied)
    monkeypatch.setattr(storage,'AttemptLedger',lambda _:pytest.fail('ledger reached'))
    with pytest.raises(ValueError,match='pending gate'):subject.create_collector({},protocol.FORMAL)


def test_reference_replay_normal_remaining_five_vs_intervention_ten(fixture,monkeypatch):
    f=fixture;cfg=deepcopy(f.config)
    cfg['execution_plans']={protocol.PREFLIGHT:dict(episode_ids=[f.case['episode_id']],
        methods=list(subject.SOLO_METHODS),repeats=[],reference_methods=['continue_native10','alarm_replan10'],
        ref_repeats=[0],bank_mode='paired_reference',expected_attempts=4,workers=5)}
    collector=subject.Collector(f.engine,cfg,f.ledger,protocol.PREFLIGHT)
    def reference(engine,observed,case,cut):
        assert engine is f.engine and case==f.case and cut==5
        return {'replan':f.raw.copy()},dict(synthetic_reference=True),{'raw_a0':f.raw.copy()}
    monkeypatch.setattr(reference_generation,'generate_reference',reference)
    result=collector.collect_episode(f.case)
    summary=subject.read(__import__('pathlib').Path(result['completion_path'])/'summary.json')
    rows=[subject.read(record['summary_path']) for record in summary['branch_records']]
    assert len(f.ledger.rows)==len(f.runtime.resets)==4
    assert len(f.engine.calls)==3 # Solo bank still generated with zero new solo rollouts.
    assert rows[0]['actual_prefix_steps']==5 and rows[0]['first_actual_resample']==10
    assert rows[1]['actual_prefix_steps']==10 and rows[1]['first_actual_resample']==15
    for left,right in zip(rows[0]['suffix_seeds'],rows[1]['suffix_seeds']):
        assert left['seed']==right['seed'] and left['noise_sha256']==right['noise_sha256']
        assert left['step']!=right['step']
    assert summary['reference_methods']==['continue_native10','alarm_replan10']
