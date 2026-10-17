"""CPU stubs test orchestration, not actual VLA/critic numerical equivalence."""
import ast
import json
from pathlib import Path
from types import MethodType,SimpleNamespace
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
    assert evidence['output_is_usable'] is False and evidence['entry_automatic_retry'] is False
    assert evidence['automatic_retry'] is (failure=='fallback')
    assert evidence['sampler_retry_performed'] is (failure=='fallback')
    if failure=='fallback':
        assert evidence['completed_proposal_policy_calls']==2 and len(engine.calls)==1
        assert evidence['actual_policy_calls']==2 and evidence['failed_proposal_policy_calls']==0
    assert engine.hook.settings['mode']=='velocity'


def test_new_stage_gate_precedes_any_proposal(setup,monkeypatch):
    from . import protocol
    engine,observed,case=setup
    def deny(*a,**k):raise ValueError('new stage denied')
    monkeypatch.setattr(protocol,'require_stage_budget',deny)
    with pytest.raises(ValueError,match='new stage denied'):subject.generate_solo(engine,observed,case,5,'solo_post')
    assert engine.calls==[]
    with pytest.raises(ValueError,match='new stage denied'):subject.create_engine({},'standalone_formal')


def _propose_ast(path):
    tree=ast.parse(path.read_text())
    cls=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='Native10Engine')
    return next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='propose')


def test_propose_ast_only_changes_known_journal_adapters_and_guidance_handler():
    base=Path(__file__).resolve().parents[1]
    old=_propose_ast(base/'native10_training_20260916/engine.py')
    new=_propose_ast(Path(subject.__file__))
    assert old.decorator_list==[]
    assert [ast.dump(node) for node in new.decorator_list]==[
        "Name(id='_journal_proposal', ctx=Load())"]
    new.decorator_list=[]
    expected=ast.parse('runtime = _JournalRuntime(self.runtime, self.proposal_activity, self.hook)').body[0]
    assert ast.dump(new.body[0])==ast.dump(expected)
    new.body[0]=ast.parse('runtime = self.runtime').body[0]
    for tree in (old,new):
        tries=[node for node in ast.walk(tree) if isinstance(node,ast.Try)]
        assert len(tries)==1 and len(tries[0].handlers)==1
        assert ast.dump(tries[0].handlers[0].type)=="Name(id='GuidanceError', ctx=Load())"
        tries[0].handlers=[]
    assert ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False)
    text=Path(subject.__file__).read_text()
    assert 'reference_generation' not in text and 'from corrector.candidates import construct' not in text


class SyntheticGuidanceError(RuntimeError):pass


def _install_extracted_propose(engine,*,fail_base=False,fail_guided=True,nonfinite_logs=False,
                               fault=None,legacy_fallback=False):
    """Execute the production method AST using CPU fakes, never its model factory."""
    class Hook:
        def __init__(self):
            self.settings={'mode':'velocity'};self.last_noise_sha=None;self.begin_calls=[]
            self.begin(None)
        def begin(self,loss):
            self.begin_calls.append(loss);self.loss=loss
            self.logs=[];self.times=[];self.objective_calls=0;self.failed_backward_calls=0
    hook=Hook();calls=[];clears=[];events=[];control={'fault':fault}
    def native_action(seed):
        mode=None if hook.loss is None else hook.settings['mode']
        calls.append((seed,mode));events.append('native_action')
        hook.last_noise_sha='synthetic-initial-noise'
        if (mode is None and fail_base) or (mode is not None and fail_guided) or control['fault'] in ('generic_native','interrupt'):
            hook.times=[1.,.9,.8]
            hook.logs=[dict(tau=.9,backward_calls=1,gradient_norm=2.)]
            if nonfinite_logs:
                hook.logs[0].update(gradient_norm=float('nan'),
                    per_dimension=np.asarray([float('inf'),float('-inf')],np.float32))
            hook.objective_calls=2;hook.failed_backward_calls=1
            if control['fault']=='generic_native':raise RuntimeError('injected native runtime error')
            if control['fault']=='interrupt':raise KeyboardInterrupt('injected interruption')
            raise SyntheticGuidanceError('injected nonfinite guidance')
        hook.times=list(np.arange(10,0,-1)/10)
        plan=np.zeros((50,4),np.float32)
        first=plan[0].copy()
        if control['fault']=='shape':plan=plan[:49]
        if control['fault']=='schedule':hook.times=hook.times[:-1]
        if control['fault']=='first_action':first[0]=.5
        return first,plan,None
    def clear_policy(horizon):
        clears.append(horizon)
        if control['fault']=='prepare':raise RuntimeError('injected pre-sampling preparation error')
    runtime=SimpleNamespace(clear_policy=clear_policy,
        fingerprint=lambda:'unchanged-physics',native_action=native_action)
    cuda=SimpleNamespace(synchronize=lambda:events.append('synchronize'),
        reset_peak_memory_stats=lambda:events.append('reset_peak'),
        memory_allocated=lambda:2**20,max_memory_allocated=lambda:3*2**20,
        max_memory_reserved=lambda:4*2**20)
    ticks=iter(np.arange(100,dtype=float)/4)
    namespace=dict(np=np,torch=SimpleNamespace(cuda=cuda),
        time=SimpleNamespace(perf_counter=lambda:next(ticks)),
        GuidanceError=SyntheticGuidanceError,ProposalGuidanceError=subject.ProposalGuidanceError,
        _journal_proposal=subject._journal_proposal,_JournalRuntime=subject._JournalRuntime)
    function=_propose_ast(Path(subject.__file__))
    if legacy_fallback:
        function=_propose_ast(Path(__file__).resolve().parents[1]/'native10_training_20260916/engine.py')
        function.decorator_list=[ast.Name(id='_journal_proposal',ctx=ast.Load())]
        function.body[0]=ast.parse('runtime = _JournalRuntime(self.runtime, self.proposal_activity, self.hook)').body[0]
    tree=ast.Module(body=[function],type_ignores=[])
    exec(compile(ast.fix_missing_locations(tree),str(subject.__file__),'exec'),namespace)
    engine.runtime=runtime;engine.hook=hook;engine.calls=calls
    engine.propose=MethodType(namespace['propose'],engine)
    return dict(hook=hook,calls=calls,clears=clears,events=events,control=control,runtime=runtime)


@pytest.mark.parametrize('mode',[None,'direct','velocity'])
def test_actual_propose_guidance_failure_stops_after_one_native_action(setup,mode):
    engine,_,_=setup
    fake=_install_extracted_propose(engine,fail_base=mode is None)
    if mode is not None:engine.hook.settings['mode']=mode
    with pytest.raises(subject.ProposalGuidanceError) as found:
        engine.propose(123,None if mode is None else object())
    evidence=found.value.evidence
    assert fake['calls']==[(123,mode)] and fake['clears']==[10]
    assert fake['events'].count('native_action')==1
    assert isinstance(found.value.__cause__,SyntheticGuidanceError)
    assert evidence['policy_calls']==1 and evidence['policy_call_count_known']
    assert not evidence['output_is_usable'] and not evidence['successful_generation']
    assert not evidence['fallback_performed'] and evidence['fallback'] is None
    assert not evidence['automatic_retry'] and not evidence['sampler_retry_performed']
    assert evidence['times']==[1.,.9,.8] and evidence['noise_sha256']=='synthetic-initial-noise'
    assert evidence['updates']==[dict(tau=.9,backward_calls=1,gradient_norm=2.)]
    assert evidence['objective_forward_calls']==2 and evidence['backward_calls']==2
    assert evidence['failed_backward_calls']==1 and evidence['seconds']==.25
    assert evidence['peak_cuda_allocated_mib']==3 and evidence['peak_cuda_reserved_mib']==4
    assert evidence['incremental_peak_cuda_allocated_mib']==2 and evidence['environment_unchanged']
    assert fake['hook'].loss is None and fake['hook'].logs==[] and fake['hook'].times==[]
    assert engine.runtime is fake['runtime']
    journal=evidence['proposal_activity']['native_action_calls']
    assert len(journal)==1 and journal[0]['entered'] and journal[0]['raised'] and not journal[0]['returned']
    assert journal[0]['hook']['times']==[1.,.9,.8]
    json.dumps(evidence,allow_nan=False)


def test_nonfinite_partial_diagnostics_are_explicit_strict_json(setup):
    engine,observed,case=setup
    fake=_install_extracted_propose(engine,nonfinite_logs=True)
    with pytest.raises(subject.SoloGenerationError) as found:
        subject.generate_solo(engine,observed,case,5,'solo_direct')
    evidence=found.value.evidence
    encoded=json.dumps(evidence,allow_nan=False)
    assert json.loads(encoded)==evidence and len(fake['calls'])==2
    update=evidence['proposal_records'][-1]['stats']['updates'][0]
    assert update['gradient_norm']=={'nonfinite':'nan'}
    assert update['per_dimension']==[
        {'nonfinite':'positive_infinity'},{'nonfinite':'negative_infinity'}]
    assert evidence['actual_policy_calls']==2 and evidence['output_is_usable'] is False


@pytest.mark.parametrize('method,fail_base,expected_calls',[
    ('solo_direct',False,2),('solo_velocity',False,2),
    ('solo_direct',True,1),('solo_velocity',True,1),('solo_post',True,1)])
def test_generator_merges_interrupted_propose_calls_and_cost(setup,method,fail_base,expected_calls):
    engine,observed,case=setup
    fake=_install_extracted_propose(engine,fail_base=fail_base)
    with pytest.raises(subject.SoloGenerationError) as found:
        subject.generate_solo(engine,observed,case,5,method)
    evidence=found.value.evidence
    assert len(fake['calls'])==evidence['actual_policy_calls']==expected_calls
    assert evidence['completed_proposal_policy_calls']==(0 if fail_base else 1)
    assert evidence['failed_proposal_policy_calls']==1 and evidence['policy_call_count_known']
    assert len(evidence['proposal_records'])==expected_calls
    failure=evidence['proposal_records'][-1]
    assert failure['returned_successfully'] is False and failure['stats']['seconds']==.25
    assert failure['stats']['objective_forward_calls']==2 and failure['stats']['backward_calls']==2
    assert evidence['component_seconds'][failure['purpose']+'_wall_seconds']>=0
    assert evidence['full_entry_seconds']>=sum(evidence['component_seconds'].values())
    assert evidence['output_is_usable'] is False and evidence['successful_generation'] is False
    assert evidence['automatic_retry'] is False and evidence['entry_automatic_retry'] is False
    assert fake['clears']==[10]*expected_calls and engine.hook.settings['mode']=='velocity'


def test_unknown_exception_call_count_is_not_silently_zero(setup):
    engine,observed,case=setup
    engine.proposal_activity=dict(native_action_calls=[{'status':'returned'}]*99)
    original=engine.propose
    def missing_failure_counters(seed,loss=None):
        if loss is not None:raise RuntimeError('sampler failed without invocation evidence')
        return original(seed,loss)
    engine.propose=missing_failure_counters
    with pytest.raises(subject.SoloGenerationError) as found:
        subject.generate_solo(engine,observed,case,5,'solo_direct')
    evidence=found.value.evidence
    assert evidence['actual_policy_calls'] is None and evidence['known_policy_calls']==1
    assert evidence['failed_proposal_policy_calls'] is None and not evidence['policy_call_count_known']
    assert evidence['sampler_retry_performed'] is None and evidence['automatic_retry'] is None
    assert evidence['entry_automatic_retry'] is False


def test_exception_report_of_internal_retry_is_preserved(setup):
    engine,observed,case=setup
    original=engine.propose
    def externally_retried_sampler(seed,loss=None):
        if loss is not None:
            raise subject.ProposalGuidanceError('external sampler retried',dict(policy_calls=2,
                seconds=.5,automatic_retry=True,sampler_retry_performed=True,output_is_usable=False))
        return original(seed,loss)
    engine.propose=externally_retried_sampler
    with pytest.raises(subject.SoloGenerationError) as found:
        subject.generate_solo(engine,observed,case,5,'solo_direct')
    evidence=found.value.evidence
    assert evidence['actual_policy_calls']==3 and evidence['failed_proposal_policy_calls']==2
    assert evidence['sampler_retry_performed'] is True and evidence['automatic_retry'] is True
    assert evidence['entry_automatic_retry'] is False and evidence['output_is_usable'] is False


@pytest.mark.parametrize('fault,expected,phase',[
    ('prepare',0,'before_native_action'),('generic_native',1,'native_action'),
    ('shape',1,'post_native_action_validation'),('schedule',1,'post_native_action_validation'),
    ('first_action',1,'post_native_action_validation')])
def test_all_real_propose_failure_locations_have_exact_activity(setup,fault,expected,phase):
    engine,_,_=setup
    fake=_install_extracted_propose(engine,fail_guided=False,fault=fault)
    with pytest.raises(subject.ProposalExecutionError) as found:engine.propose(123)
    evidence=found.value.evidence
    assert evidence['policy_calls']==evidence['actual_policy_calls']==len(fake['calls'])==expected
    assert evidence['policy_call_count_known'] and evidence['failure_phase']==phase
    assert evidence['output_is_usable'] is False and evidence['automatic_retry'] is False
    assert engine.runtime is fake['runtime']
    records=evidence['proposal_activity']['native_action_calls']
    assert len(records)==expected
    if expected:
        assert records[0]['entered']
        assert records[0]['returned'] is (phase=='post_native_action_validation')
        assert records[0]['raised'] is (phase=='native_action')
        assert records[0]['hook']['noise_sha256']=='synthetic-initial-noise'
        assert records[0]['seconds']>=0
    json.dumps(evidence,allow_nan=False)


def test_new_proposal_clears_previous_activity_even_before_sampling(setup):
    engine,_,_=setup
    fake=_install_extracted_propose(engine,fail_guided=False)
    _,stats=engine.propose(123)
    previous=engine.proposal_activity
    assert len(previous['native_action_calls'])==1 and previous['status']=='returned'
    assert stats['proposal_activity']==previous
    fake['control']['fault']='prepare'
    with pytest.raises(subject.ProposalExecutionError) as found:engine.propose(456)
    assert engine.proposal_activity is not previous
    assert found.value.evidence['policy_calls']==0
    assert found.value.evidence['proposal_activity']['native_action_calls']==[]
    assert found.value.evidence['proposal_activity']['seed']==456
    assert previous['native_action_calls'][0]['seed']==123 and len(fake['calls'])==1


def test_generator_counts_post_sample_validation_failure_instead_of_unknown(setup):
    engine,observed,case=setup
    fake=_install_extracted_propose(engine,fail_guided=False,fault='first_action')
    with pytest.raises(subject.SoloGenerationError) as found:
        subject.generate_solo(engine,observed,case,5,'solo_direct')
    evidence=found.value.evidence
    assert evidence['actual_policy_calls']==1 and evidence['policy_call_count_known']
    assert evidence['failed_proposal_policy_calls']==1 and evidence['completed_proposal_policy_calls']==0
    failure=evidence['proposal_records'][0]['stats']
    assert failure['native_action_returned_calls']==1 and failure['failure_phase']=='post_native_action_validation'
    assert len(fake['calls'])==1 and not evidence['output_is_usable']


def test_old_fallback_ast_two_native_failures_are_both_counted_only_in_test(setup):
    engine,_,_=setup
    fake=_install_extracted_propose(engine,fail_base=True,fail_guided=True,legacy_fallback=True)
    with pytest.raises(subject.ProposalExecutionError) as found:engine.propose(123,object())
    evidence=found.value.evidence
    assert len(fake['calls'])==evidence['policy_calls']==2
    assert fake['calls']==[(123,'velocity'),(123,None)]
    assert fake['clears']==[10,10] and evidence['sampler_retry_performed'] is True
    records=evidence['proposal_activity']['native_action_calls']
    assert [row['index'] for row in records]==[0,1]
    assert all(row['entered'] and row['raised'] and not row['returned'] for row in records)
    assert all(row['hook']['times']==[1.,.9,.8] for row in records)
    assert evidence['output_is_usable'] is False and engine.runtime is fake['runtime']


def test_keyboard_interrupt_keeps_original_type_and_started_activity(setup):
    engine,observed,case=setup
    fake=_install_extracted_propose(engine,fail_guided=False,fault='interrupt')
    with pytest.raises(KeyboardInterrupt) as found:
        subject.generate_solo(engine,observed,case,5,'solo_post')
    evidence=found.value.evidence
    assert evidence['actual_policy_calls']==1 and not evidence['output_is_usable']
    failure=evidence['proposal_records'][0]['stats']
    assert failure['error_type']=='KeyboardInterrupt'
    assert failure['proposal_activity']['native_action_calls'][0]['raised']
    assert len(fake['calls'])==1 and fake['hook'].loss is None
