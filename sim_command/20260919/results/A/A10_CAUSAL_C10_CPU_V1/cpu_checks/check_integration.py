"""Targeted stdlib-only synthetic controller / metering / process fixtures."""
import ast,copy,hashlib,importlib.abc,json,sys,types
from pathlib import Path
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'code'))
class BlockHeavy(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'torch','numpy','ctypes','mujoco','metaworld','gymnasium','pynvml','OpenGL','runtime_engine','numeric_setup','dg_models'}:
            raise AssertionError('CPU fixture attempted forbidden import: '+fullname)
sys.meta_path.insert(0,BlockHeavy())
from causal_contract import Flags,Queue,legal_cut,validate_reference,history_indices,run_branch
from core.contracts import ContractError,Meter,reconcile
from budget import BRANCHES,TOTAL,numeric_caps,validate_dynamic_counts
from native.initialization import EXPECTED_CAPS,InitializationAudit
from core.process_family import drain_group

WORK=Path(sys.argv[1]);WORK.mkdir(exist_ok=False)
checks=[]
def check(name,fn):
    fn();checks.append(dict(name=name,status='PASS'))
def refused(fn):
    try:fn()
    except (ValueError,AssertionError):return
    raise AssertionError('Expected refusal')

class Fake:
    """Scalar tokens only, no real observation/physics/tensor/model call."""
    def __init__(self,score=0,stop=None,prefix_match=True):
        self.seeds=dict(generation_seed=1,suffix_seed=2,restore_seed=3);self.threshold=.05
        self.score=score;self.stop=stop;self.prefix_match=prefix_match;self.trace=[];self.observations=[];self.forecasts=[]
    def emit(self,name,**data):self.trace.append((name,data))
    def reset(self):return {'t':0},Flags()
    def save_observation(self,obs,step):assert obs['t']==step;self.observations.append(step)
    def encode_context(self,obs,step,executed):
        assert self.observations==list(range(step+1));assert len(executed)==step
        frames,actions=history_indices(step)
        assert max(frames)<=step and all(i<step for i in actions)
        return {'t':step,'frames':frames,'actions':actions}
    def sample(self,obs,label,seed):self.trace.append(('sample',dict(label=label,step=obs['t'])));return [[i/100]*4 for i in range(50)]
    def forecast(self,context,actions,label):
        assert len(actions)==5 and context['t'] in [0,5]
        self.forecasts.append((context['t'],label));return ['future_tokens']
    def step(self,command,index,plan_id):
        self.trace.append(('control',dict(index=index,plan_id=plan_id,command=command)))
        flags=Flags(**self.stop[1]) if self.stop and index+1==self.stop[0] else Flags()
        return {'t':index+1},flags
    def check_prefix_at_cut(self):return self.prefix_match
    def residual(self,predictions,context):assert self.observations==list(range(6));return [123.]
    def gate_score(self,context,actions,predictions):assert context['t']==5;return self.score
    def intervene(self,obs,context,branch,seed):
        assert self.observations[-1]==5;self.trace.append(('intervene',dict(branch=branch)))
        return [[.4]*4]*50
    def clear_policy_queue(self):self.trace.append(('clear_hidden',{}))
    def finish(self,status,step,queue):return dict(status=status,step=step,remaining=len(queue.rows),horizon=queue.horizon,trace=self.trace)

def happy(branch,score):
    e=Fake(score);r=run_branch(e,branch)
    assert r['status']=='C10_and_H20_checked' and r['step']==16 and r['remaining']==19 and r['horizon']==20
    controls=[x for x in e.trace if x[0]=='control'];assert len(controls)==16
    assert [x[1]['plan_id'] for x in controls]==['native_prefix_H20']*5+[branch+'_C10']*10+['restored_native_H20']
    trigger=next(d for n,d in e.trace if n=='trigger_decision')
    assert trigger['real_G0_trigger']==(score>.05) and trigger['forced_engineering_intervention']==(score<=.05)
    tail=next(d for n,d in e.trace if n=='C10_tail_discarded');assert tail['raw_unexecuted']==40 and tail['committed_remaining']==0
    assert e.forecasts==[(0,'t0_targets_1_to_5'),(5,'t5_targets_6_to_10')]
    (WORK/(branch+('_alarm' if score>.05 else '_forced')+'.json')).write_text(json.dumps(r,indent=2))
for br in ['Post','Velocity']:
    for score in [0,.05,.2]:check(br+'_threshold_'+str(score),lambda b=br,s=score:happy(b,s))
def early():
    for t in [1,5,6,15,16]:
        for flag in ['success','terminated','truncated']:
            e=Fake(stop=(t,{flag:True}));r=run_branch(e,'Post');assert r['step']==t
            assert len([x for x in e.trace if x[0]=='control'])==t
            if t<=5:assert not any(x[0]=='intervene' for x in e.trace)
            if 6<=t<=15:assert not any(x[0]=='clear_hidden' for x in e.trace)
check('early_success_termination_truncation_15_cases',early)
def cut_cases():
    q=Queue();assert legal_cut(5,q,Flags())[1]=='natural_refresh_boundary'
    q.replace([[0]*4]*50,20,'x');assert not legal_cut(5,q,Flags())[0]
    for _ in range(5):q.pop()
    assert legal_cut(5,q,Flags())[0];assert not legal_cut(0,q,Flags())[0]
    assert not legal_cut(5,q,Flags(success=True))[0];assert not legal_cut(5,q,Flags(),1)[0]
    q.rows=q.rows[:4];assert not legal_cut(5,q,Flags())[0]
    refused(lambda:Queue().replace([[float('nan')]*4]*50,20,'bad'))
check('legal_cut_order_and_no_natural_boundary_intervention',cut_cases)
def causal_cases():
    assert history_indices(0)==([0],[])
    assert history_indices(5)==([1,2,3,4,5],[1,2,3,4])
    ref=dict(created_at=0,targets=[1,2,3,4,5],plan_id='x',actions=[[0]*4]*5)
    assert validate_reference(ref,5,'x',[[0]*4]*5)
    for key,value in [('created_at',1),('targets',[2,3,4,5,6]),('plan_id','wrong'),('actions',[[1]*4]*5)]:
        bad={**ref,key:value};refused(lambda:validate_reference(bad,5,'x',[[0]*4]*5))
    e=Fake(prefix_match=False);r=run_branch(e,'Velocity');assert r['step']==5 and r['status']=='independent_prefix_mismatch'
    assert not any(n=='intervene' for n,d in e.trace)
    e=Fake();r=run_branch(e,'Post',scheduled=False);assert r['status']=='G0_not_triggered' and r['step']==5
check('reference_future_action_plan_mismatch_and_independent_replay_stop',causal_cases)
def queue_cases():
    source=[[i/100]*4 for i in range(50)];q=Queue();q.replace(source,10,'c10');source[0][0]=99
    assert q.pop()[0]==0
    for _ in range(9):q.pop()
    assert q.discard()['raw_unexecuted']==40 and q.raw is None
    refused(q.pop);q.replace([[.2]*4]*50,20,'restored');q.pop();assert len(q.rows)==19
check('C10_tail_discard_copy_isolation_and_restore_H20',queue_cases)
def budget_cases():
    assert TOTAL['vla_sampling_calls']==7 and TOTAL['flow_forward_calls']==70
    assert TOTAL['env_steps']==32 and TOTAL['policy_physics_substeps']==426
    assert TOTAL['initialization_physics_substeps']==52000 and TOTAL['environment_reset_calls']==104 and TOTAL['reset_model_calls']==208
    assert TOTAL['D_forward_calls']==8 and TOTAL['G0_forward_calls']==4
    assert TOTAL['objective_forward_calls']==11 and TOTAL['critic_forward_calls']==44 and TOTAL['action_gradient_calls']==4
    assert TOTAL['render_calls']==34 and TOTAL['native_mj_forward_calls']==452
    assert TOTAL['encoder_forward_calls']==42 and TOTAL['native_nvml_identity_queries']==3
    for br in BRANCHES:validate_dynamic_counts(BRANCHES[br],br,16,True)
check('new_source_derived_budget_arithmetic',budget_cases)
def billing():
    f=WORK/'fake_meter.jsonl';m=Meter(f,{'x':2});m.call('ok',lambda:1,{'x':1})
    m.enter('missing_terminal',{'x':1});refused(lambda:m.enter('over',{'x':1}))
    r=reconcile(f,{'x':2});assert r['entered']['x']==2 and r['returned']['x']==1 and r['unresolved']==[2]
check('missing_terminal_charged_no_refund',billing)
def physics_fake():
    class Task:
        def _make_tasks(self):pass
    class Mujoco:
        def do_simulation(self,ctrl,n_frames):return n_frames
    class Base: 
        def reset(self):pass
    class Native(Mujoco,Base):
        def __init__(self):pass
        def reset_model(self):pass
    class Wrapper:
        def __init__(self):pass
        def _make_envs_task(self):pass
    audit=InitializationAudit(WORK/'fake_init.jsonl',EXPECTED_CAPS)
    audit.install(Task,Native,Base,Mujoco,Wrapper)
    try:
        obj=object.__new__(Native)
        with audit.scope('policy_control'):
            assert obj.do_simulation(None,13)==13;assert obj.do_simulation(None,13)==13
            refused(lambda:obj.do_simulation(None,13))
            for i in range(2,16):obj.do_simulation(None,((i+1)*400)//30-(i*400)//30)
            refused(lambda:obj.do_simulation(None,13))
        assert audit.used['policy_physics_substeps']==213 and audit.used['policy_do_simulation_calls']==16
    finally:audit.uninstall()
check('initialization_hook_new_13_13_14_schedule_and_preentry_caps',physics_fake)
def drain_fake():
    state={'time':0.,'live':True};signals=[]
    def reader(pgid,owner):return [dict(pid=101,start_ticks=42)] if state['live'] else []
    def send(pid,sig):signals.append((pid,int(sig)));state['live']=False
    def pause(dt):state['time']+=dt
    result=drain_group(100,100,reader=reader,send=send,clock=lambda:state['time'],pause=pause)
    assert result['status']=='all_formal_group_members_exited' and signals==[(101,15)]
check('fake_only_same_group_exit_barrier',drain_fake)
def reserved_fake():
    import reserved
    original_argv=list(sys.argv)
    original={k:getattr(reserved,k) for k in ['held_reservation_fds','read','mark','run_forwarded','group_members','drain_group','write_new','os','sys']}
    try:
        for case in ['complete','first_failed','leftover','signal','natural_stop']:
            calls=[];drains=[];writes=[]
            reserved.held_reservation_fds=lambda:[901]
            reserved.os=types.SimpleNamespace(getpgrp=lambda:100,getpid=lambda:100)
            sys.argv=['reserved.py','--release','fake-release','--launch-directory',str(WORK)]
            reserved.mark=lambda *a,**k:None
            reserved.read=lambda path:dict(control=dict(branch_order=['Post','Velocity']),python='fake-python') if str(path).endswith('CONFIG.json') else dict(status='early_prefix_stop' if case=='natural_stop' else 'C10_and_H20_checked')
            def run(cmd,**kw):
                calls.append(cmd);assert kw['pass_fds']==[901]
                assert cmd[:5]==['timeout','--foreground','--signal=TERM','--kill-after=30s','1800s']
                if case=='signal':raise KeyboardInterrupt('synthetic signal')
                return 3 if case=='first_failed' else 0
            reserved.run_forwarded=run
            reserved.group_members=lambda *a:[dict(pid=101,start_ticks=1)] if case=='leftover' else []
            reserved.drain_group=lambda *a:drains.append(a) or dict(status='all_formal_group_members_exited')
            reserved.write_new=lambda path,value:writes.append(str(path))
            try:reserved.main()
            except KeyboardInterrupt:assert case=='signal'
            assert len(calls)==(2 if case=='complete' else 1) and drains==[(100,100)]
            assert any(x.endswith('process_family_cleanup.json') for x in writes)
    finally:
        sys.argv=original_argv
        for k,v in original.items():setattr(reserved,k,v)
check('two_children_one_inherited_lock_failure_signal_exit_barriers_fake',reserved_fake)
# Narrow changed-file parse only; inherited vendor/corrector math not re-tested.
changed=['causal_contract.py','budget.py','numeric_setup.py','runtime_engine.py','diagnostic.py','reserved.py','launch.py','publication_check.py','core/contracts.py','native/initialization.py','native/native_egl.py','native/graphics_contract.py']
for f in changed:ast.parse((P/'code'/f).read_text(),filename=f)
checks.append(dict(name='AST_changed_12_files',status='PASS'))
assert not any(k.split('.')[0] in {'torch','numpy','ctypes','mujoco','metaworld','gymnasium','pynvml','OpenGL'} for k in sys.modules)
(WORK/'RESULT.json').write_text(json.dumps(dict(status='PASS',checks=checks,forbidden_imports=[],models=0,environments=0,real_locks=0,real_signals=0,hardware_calls=0,scope='new causal/queue/timing/accounting integration only; no old numeric rerun'),indent=2)+'\n')
print(json.dumps(dict(status='PASS',checks=len(checks),result=str(WORK/'RESULT.json'))))
