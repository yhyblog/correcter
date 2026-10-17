"""CPU stubs test orchestration, not actual VLA/critic numerical equivalence."""
import ast
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from corrector.config import DEFAULT_MATCHING,DEFAULT_GUIDANCE
from . import engine as subject


class Array:
    def __init__(self,value):self.value=np.asarray(value,np.float32)
    def __sub__(self,other):return Array(self.value-other.value)
    def __truediv__(self,value):return Array(self.value/value)
    def __pow__(self,value):return Array(self.value**value)
    def detach(self):return self
    def cpu(self):return self
    def numpy(self):return self.value


class Objective:
    def __init__(self,observed,base,selector):self.base=base.copy();self.forward=0;self.backward=0
    def gradient(self):
        self.forward+=1;self.backward+=1
        return Array(np.ones((10,4),np.float32)),dict(value=0.)
    def evaluate(self,commands):
        self.forward+=1
        gain=float(np.asarray(commands).sum()-self.base[:10].sum())/100
        return dict(mean_gain=gain,candidate_mean_probability=.5+gain,a0_mean_probability=.5)
    def verify(self):return True
    def stats(self):return dict(objective_forward_calls=self.forward,objective_backward_calls=self.backward)


class Stub:
    def __init__(self):
        self.study=dict(seed_namespace='unchanged',matching=dict(DEFAULT_MATCHING),guidance=dict(DEFAULT_GUIDANCE))
        self.stage='standalone_preflight';self.state='same';self.calls=[];self.selector=object()
        self.runtime=SimpleNamespace(fingerprint=lambda:self.state)
        self.hook=SimpleNamespace(settings={'mode':'velocity'},begin=lambda _:None)
        self.transform=SimpleNamespace(q01=Array([-2,-2,-2,-2]),q99=Array([2,2,2,2]))
        self.fallback=False;self.noise_error=False;self.mutate=False
    def propose(self,seed,loss=None):
        mode=None if loss is None else self.hook.settings['mode'];self.calls.append((seed,mode))
        raw=np.zeros((50,4),np.float32)
        if loss is not None:raw[:10]=.03 if mode=='direct' else .02
        if self.mutate:self.state='changed'
        return raw,dict(policy_calls=2 if self.fallback else 1,fallback='synthetic_failure' if self.fallback else None,
            noise_sha256='different' if self.noise_error and loss is not None else 'same',seconds=.1,updates=[])
    def make_bank(self,*args,**kwargs):pytest.fail('Production called the joint bank')
    def verify(self):return True


@pytest.fixture
def setup(monkeypatch):
    from . import protocol
    monkeypatch.setattr(protocol,'require_stage_budget',lambda *a,**k:None)
    monkeypatch.setattr(subject,'_objective',Objective)
    return Stub(),{'state':np.zeros(3,np.float32)},dict(task='disassemble-v3',env_seed=2026111750,episode_id='disassemble-v3__2026111750')


@pytest.mark.parametrize('method,expected,own',[('solo_post',1,None),('solo_direct',2,'direct'),('solo_velocity',2,'velocity')])
def test_independent_entry_only_own_calls_and_complete_cost(setup,method,expected,own):
    engine,observed,case=setup
    plan,meta,arrays=subject.generate_solo(engine,observed,case,5,method)
    assert len(engine.calls)==meta['actual_policy_calls']==meta['expected_policy_calls']==expected
    assert [m for _,m in engine.calls]==([None] if own is None else [None,own])
    assert len({seed for seed,_ in engine.calls})==1
    assert meta['other_direction_calls']==meta['joint_bank_calls']==meta['random_calls']==0
    assert meta['includes_own_a0_generation'] and meta['full_entry_seconds']>=meta['component_seconds']['base_wall_seconds']
    assert meta['predictions']['replan']['mean_gain']==0 and meta['projection_audit']['status']=='passed'
    assert ('post_command_gradient' in arrays)==(method=='solo_post')
    assert ('own_native_raw' in arrays)==(method!='solo_post')
    assert meta['objective_stats']['objective_backward_calls']==(1 if method=='solo_post' else 0)
    assert plan.dtype==np.float32 and plan.shape==(50,4)


def test_every_entry_regenerates_a0_no_cross_method_cache(setup):
    engine,observed,case=setup;results=[]
    for method in ('solo_direct','solo_post','solo_velocity'):
        results.append(subject.generate_solo(engine,observed,case,5,method))
    assert [m for _,m in engine.calls]==[None,'direct',None,None,'velocity']
    assert len({seed for seed,_ in engine.calls})==1
    assert len({r[1]['raw_a0_sha256'] for r in results})==1
    assert engine.hook.settings['mode']=='velocity'


@pytest.mark.parametrize('failure',['fallback','noise_error','mutate'])
def test_fail_closed_keeps_actual_calls_without_usable_candidate(setup,failure):
    engine,observed,case=setup;setattr(engine,failure,True)
    with pytest.raises(subject.SoloGenerationError) as found:
        subject.generate_solo(engine,observed,case,5,'solo_direct')
    evidence=found.value.evidence
    assert evidence['output_is_usable'] is False and evidence['automatic_retry'] is False
    if failure=='fallback':assert evidence['completed_proposal_policy_calls']==2 and len(engine.calls)==1
    assert engine.hook.settings['mode']=='velocity'


def test_new_stage_gate_precedes_any_proposal(setup,monkeypatch):
    from . import protocol
    engine,observed,case=setup
    def deny(*a,**k):raise ValueError('new stage denied')
    monkeypatch.setattr(protocol,'require_stage_budget',deny)
    with pytest.raises(ValueError,match='new stage denied'):subject.generate_solo(engine,observed,case,5,'solo_post')
    assert engine.calls==[]
    with pytest.raises(ValueError,match='new stage denied'):subject.create_engine({},'standalone_formal')


def test_propose_ast_keeps_original_success_and_fallback_arithmetic():
    base=Path(__file__).resolve().parents[1]
    def find(path):
        tree=ast.parse(path.read_text())
        cls=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='Native10Engine')
        return next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='propose')
    old=find(base/'native10_training_20260916/engine.py');new=find(Path(subject.__file__))
    assert ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False)
    text=Path(subject.__file__).read_text()
    assert 'reference_generation' not in text and 'from corrector.candidates import construct' not in text
