"""Only event integration: real controllers/recorder, inherited scalar callbacks.

All outputs are SYNTHETIC. No runtime_engine import, model, hardware or launcher.
"""
import ast,copy,hashlib,importlib.abc,importlib.util,json,os,sys,traceback,types
from pathlib import Path
P=Path(__file__).resolve().parents[1]
O=P.parent/'A10_CAUSAL_C10_CPU_V1'
sys.path.insert(0,str(P/'code'))
FORBIDDEN={'torch','numpy','ctypes','mujoco','metaworld','gymnasium','pynvml','OpenGL','runtime_engine','numeric_setup','dg_models'}
class BlockHeavy(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in FORBIDDEN:raise AssertionError('Forbidden CPU import: '+fullname)
sys.meta_path.insert(0,BlockHeavy())
from causal_contract import Flags,history_indices,run_branch
from core.event_recorder import EventRecorder,EventIdentityConflict,RESERVED_FIELDS,PROTECTED_FIELDS
from core.failure_evidence import save_failure,record_failure,branch_stage
from core.contracts import write_new

WORK=Path(sys.argv[1]);WORK.mkdir(exist_ok=False)
checks=[];provenance=[];cases=[]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def check(name,fn):
    try:detail=fn()
    except BaseException as error:
        save_failure(WORK/('unexpected_failure_'+name+'.json'),error,branch=None,stage=name,category='CPU_fixture',synthetic=True)
        raise
    checks.append(dict(name=name,status='PASS',synthetic=True,detail=detail))
def extracted_method(path,cls,name,namespace):
    tree=ast.parse(path.read_text(),filename=str(path))
    node=next(n for c in tree.body if isinstance(c,ast.ClassDef) and c.name==cls for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)
    module=ast.Module(body=[copy.deepcopy(node)],type_ignores=[])
    exec(compile(ast.fix_missing_locations(module),str(path),'exec'),namespace)
    provenance.append(dict(path=str(path),sha256=sha(path),class_name=cls,method=name,
        ast_sha256=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest(),extraction='unchanged method AST; module not imported'))
    return namespace[name]

# Execute the OLD controller with the OLD actual Engine.emit before any new case.
def old_regression():
    path=O/'code/causal_contract.py';spec=importlib.util.spec_from_file_location('synthetic_old_controller',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    emit=extracted_method(O/'code/runtime_engine.py','Engine','emit',dict(json=json,os=os))
    out=WORK/'synthetic_old_regression';out.mkdir()
    e=types.SimpleNamespace(out=out,events=0,branch='Post',reset_calls=0,
        cfg={'source':dict(source_id='synthetic-old-source',parent_source_id='synthetic-parent')})
    e.emit=types.MethodType(emit,e)
    def reset():e.reset_calls+=1;raise AssertionError('Old regression must fail before reset')
    e.reset=reset
    try:module.run_branch(e,'Post')
    except TypeError as error:
        assert "multiple values for keyword argument 'branch'" in str(error)
        ev=save_failure(out/'EXPECTED_SYNTHETIC_FAILURE.json',error,branch='Post',stage='branch_start',category='expected_old_regression',synthetic=True)
    else:raise AssertionError('Old real combination did not reproduce')
    assert e.events==1 and e.reset_calls==0 and not (out/'causal_events.jsonl').exists()
    write_new(out/'PROOF.json',dict(synthetic=True,old_controller=dict(path=str(path),sha256=sha(path)),
        outcome='expected duplicate-key TypeError reproduced using old actual controller and Engine.emit',
        reset_callbacks=0,event_file_exists=False,old_prewrite_counter=1,old_runtime_stack_backfilled=False,failure=ev))
    return dict(expected_error='TypeError',event_file_exists=False,reset_callbacks=0)
check('old_real_combination_before_new_cases',old_regression)

# Reuse the previously published scalar callback fixture, REMOVE its Fake.emit.
old_fake=O/'cpu_checks/check_integration.py'
node=next(n for n in ast.parse(old_fake.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Fake')
node=copy.deepcopy(node);node.name='InheritedCallbacks'
node.body=[n for n in node.body if not (isinstance(n,ast.FunctionDef) and n.name=='emit')]
assert not any(isinstance(n,ast.FunctionDef) and n.name=='emit' for n in node.body)
ns=dict(Flags=Flags,history_indices=history_indices)
exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(old_fake),'exec'),ns)
InheritedCallbacks=ns['InheritedCallbacks']
provenance.append(dict(path=str(old_fake),sha256=sha(old_fake),extraction='existing Fake callback class; Fake.emit removed; subclass only adds real recorder integration and saved evidence'))
new_emit=extracted_method(P/'code/runtime_engine.py','Engine','emit',{})

class Callbacks(InheritedCallbacks):
    emit=new_emit  # exact production delegate, not another Fake.emit
    def __init__(self,out,branch,source='synthetic-source',**kwargs):
        super().__init__(**kwargs);self.out=out;out.mkdir();self.branch=branch;self.steps=0
        self.recorder=EventRecorder(out/'causal_events.jsonl',branch=branch,source_id=source,
            parent_source_id='synthetic-parent',split='synthetic',synthetic=True)
    def reset(self):
        obs,flags=super().reset()
        return obs,Flags(**self.stop[1]) if self.stop and self.stop[0]==0 else flags
    def save_observation(self,obs,step):
        super().save_observation(obs,step)
        self.emit('observation_saved',step=step,pixel_sha256='synthetic-pixels-'+str(step),proprio_sha256='synthetic-proprio-'+str(step))
    def encode_context(self,obs,step,executed):
        context=super().encode_context(obs,step,executed)
        self.emit('causal_features',step=step,observations=context['frames'],past_action_indices=context['actions'],
            future_observations_used=False,context_shas={'synthetic':'step-'+str(step)})
        return context
    def step(self,command,index,plan_id):
        obs,flags=super().step(command,index,plan_id);self.steps=index+1
        self.emit('native_transition_returned',step=index,next_step=index+1,plan_id=plan_id,action=command,
            success=flags.success,terminated=flags.terminated,truncated=flags.truncated)
        return obs,flags
    def check_prefix_at_cut(self):
        matched=super().check_prefix_at_cut()
        if self.branch=='Velocity':self.emit('independent_prefix_comparison',observed_matches=matched,hidden_state_equivalence_proven=False)
        return matched
    def finish(self,status,step,queue):
        result=super().finish(status,step,queue)
        result.update(synthetic=True,branch=self.branch,source_id=self.recorder.identity['source_id'],
            episode_id=self.recorder.identity['episode_id'],restoration_coverage=status=='C10_and_H20_checked')
        write_new(self.out/'SYNTHETIC_BRANCH_RESULT.json',result)
        return result

def load_events(e):
    raw=e.recorder.path.read_bytes();assert raw.endswith(b'\n')
    rows=[json.loads(x) for x in raw.decode().splitlines()]
    assert len(rows)==e.recorder.events
    assert [r['event_id'] for r in rows]==list(range(1,len(rows)+1))
    for row in rows:
        assert {k:row[k] for k in e.recorder.identity}==dict(e.recorder.identity)
        assert row['synthetic'] is True and row['split']=='synthetic'
    assert rows[0]['event']=='branch_start'
    return rows

def exercise(name,branch,score=0,scheduled=True,stop=None,prefix_match=True,source='synthetic-source'):
    e=Callbacks(WORK/name,branch,source=source,score=score,stop=stop,prefix_match=prefix_match)
    result=run_branch(e,branch,scheduled=scheduled);rows=load_events(e);names=[r['event'] for r in rows]
    assert json.loads(json.dumps(result))==json.loads((e.out/'SYNTHETIC_BRANCH_RESULT.json').read_text())
    controls=[r for r in rows if r['event']=='native_transition_returned']
    obs=[r for r in rows if r['event']=='observation_saved']
    assert len(controls)==result['step'] and [r['step'] for r in controls]==list(range(result['step']))
    assert [r['step'] for r in obs]==list(range(result['step']+1))
    for r in controls:
        i=rows.index(r);assert rows[i+1]['event']=='observation_saved' and rows[i+1]['step']==r['next_step']
    features=[r for r in rows if r['event']=='causal_features']
    for r in features:
        assert (r['observations'],r['past_action_indices'])==history_indices(r['step']) and not r['future_observations_used']
    if result['status']=='C10_and_H20_checked':
        assert result['step']==16 and result['remaining']==19 and result['horizon']==20
        assert [r['plan_id'] for r in controls]==['native_prefix_H20']*5+[branch+'_C10']*10+['restored_native_H20']
        cut=next(r for r in rows if r['event']=='cut_legality')
        assert cut['legal'] and cut['step']==5 and cut['age']==5 and cut['remaining']==15
        trigger=next(r for r in rows if r['event']=='trigger_decision')
        assert trigger['real_G0_trigger']==(score>.05)
        assert trigger['forced_engineering_intervention']==bool(scheduled and score<=.05)
        assert not trigger['residual_used_by_G0'] and not trigger['Q_acceptance_gate']
        tail=next(r for r in rows if r['event']=='C10_tail_discarded')
        assert tail['raw_unexecuted']==40 and tail['committed_remaining']==0 and tail['age']==10 and tail['hidden_policy_queue_empty']
        restored=rows[-1];assert restored['event']=='native_H20_restored' and restored['remaining']==19
        ordered=['branch_start','forecast_created','cut_legality','trigger_decision','old_H20_queue_discarded','C10_tail_discarded','native_H20_restored']
        assert [n for n in names if n in ordered]==ordered
        assert e.forecasts==[(0,'t0_targets_1_to_5'),(5,'t5_targets_6_to_10')]
    if stop and stop[0]<=15:
        assert result['step']==stop[0] and 'native_H20_restored' not in names and 'C10_tail_discarded' not in names
        if stop[0]<=5:
            assert 'cut_legality' not in names and not any(n=='intervene' for n,_ in e.trace)
            assert not any(r['step']==stop[0] for r in features)
        else:assert result['status']=='early_C10_stop'
    if not prefix_match:
        assert result['status']=='independent_prefix_mismatch' and result['step']==5
        assert 'trigger_decision' not in names and not any(n=='intervene' for n,_ in e.trace)
    if not scheduled and score<=.05 and not stop and prefix_match:
        assert result['status']=='G0_not_triggered' and result['step']==5
        assert not any(n=='intervene' for n,_ in e.trace)
        trigger=rows[-1];assert not trigger['real_G0_trigger'] and not trigger['forced_engineering_intervention'] and not trigger['execute_intervention']
    item=dict(name=name,branch=branch,synthetic=True,status=result['status'],events=len(rows),controls=len(controls),
        legal_cut=any(r['event']=='cut_legality' and r['legal'] for r in rows),
        C10_steps=sum(r['plan_id']==branch+'_C10' for r in controls),tail_discarded='C10_tail_discarded' in names,
        restored=result['restoration_coverage'],remaining=result['remaining'],episode_id=e.recorder.identity['episode_id'])
    cases.append(item);return item

for branch in ['Post','Velocity']:
    for label,score in [('below',0),('equal',.05),('above',.2)]:
        name=branch+'_threshold_'+label
        check(name,lambda n=name,b=branch,s=score:exercise(n,b,score=s))
        name=branch+'_force_off_'+label
        check(name,lambda n=name,b=branch,s=score:exercise(n,b,score=s,scheduled=False))
    for step in [0,1,5,6,15,16]:
        for flag in ['success','terminated','truncated']:
            name=branch+'_stop_'+str(step)+'_'+flag
            check(name,lambda n=name,b=branch,t=step,f=flag:exercise(n,b,stop=(t,{f:True})))
check('Velocity_prefix_mismatch',lambda:exercise('Velocity_prefix_mismatch','Velocity',prefix_match=False))
check('source_isolation',lambda:exercise('source_isolation','Post',source='synthetic-another-source'))
assert len({c['episode_id'] for c in cases})==3

def collision_checks():
    folder=WORK/'synthetic_conflicts';folder.mkdir();proof=[]
    for committed in [False,True]:
        for field in sorted(PROTECTED_FIELDS):
            path=folder/(str(committed)+'_'+field+'.jsonl')
            r=EventRecorder(path,branch='Post',source_id='synthetic-conflict',parent_source_id='synthetic-parent',split='synthetic',synthetic=True)
            if committed:r.emit('accepted_before')
            before=path.read_bytes() if path.exists() else None;count=r.events
            try:r.emit('refused',**{field:r.identity.get(field,'same-or-conflicting')})
            except EventIdentityConflict as error:message=str(error)
            else:raise AssertionError('Collision accepted: '+field)
            assert r.events==count and (path.read_bytes() if path.exists() else None)==before
            r.emit('accepted_after')
            assert [json.loads(x)['event_id'] for x in path.read_text().splitlines()]==list(range(1,count+2))
            proof.append(dict(field=field,prior_committed=committed,bytes_unchanged_on_refusal=True,committed_counter_unchanged=True,message=message))
    path=folder/'nonfinite.jsonl';r=EventRecorder(path,branch='Post',source_id='synthetic',parent_source_id='synthetic',split='synthetic',synthetic=True)
    try:r.emit('nonfinite',value=float('nan'))
    except ValueError:pass
    else:raise AssertionError('Nonfinite JSON accepted')
    assert not path.exists() and r.events==0
    write_new(folder/'PROOF.json',dict(synthetic=True,required_reserved=sorted(RESERVED_FIELDS),additional_scope_field='synthetic',checks=proof,serialization_before_open=True))
    return dict(conflicts=len(proof),all_rejected_before_write_and_ID_commit=True)
check('reserved_identity_conflicts_and_no_partial_events',collision_checks)

def traceback_checks():
    out=WORK/'synthetic_tracebacks';out.mkdir();rec=EventRecorder(out/'causal_events.jsonl',branch='Velocity',source_id='synthetic-traceback',parent_source_id='synthetic-parent',split='synthetic',synthetic=True)
    rec.emit('branch_start');engine=types.SimpleNamespace(recorder=rec,steps=0)
    def primary_raise():raise ValueError('synthetic primary')
    def cleanup_raise():raise RuntimeError('synthetic cleanup')
    try:primary_raise()
    except BaseException as error:
        primary=save_failure(out/'failure.json',error,branch='Velocity',stage=branch_stage('controller',engine),category='primary',synthetic=True)
    original=(out/'failure.json').read_bytes()
    try:cleanup_raise()
    except BaseException as error:
        cleanup=save_failure(out/'cleanup_failure__environment_close.json',error,branch='Velocity',stage=branch_stage('cleanup',engine),category='cleanup',operation='environment_close',synthetic=True)
    assert (out/'failure.json').read_bytes()==original
    assert primary['type']=='ValueError' and cleanup['type']=='RuntimeError'
    assert primary['traceback_present'] and cleanup['traceback_present']
    assert 'primary_raise' in primary['traceback'] and 'cleanup_raise' in cleanup['traceback']
    assert primary['stage']['last_committed_event']=='branch_start' and primary['stage']['returned_control_steps']==0
    # Same production graphics cleanup catch, extracted without importing any EGL code.
    close=extracted_method(P/'code/native/native_egl.py','NativeEGL','close',
        dict(record_failure=lambda error,**context:record_failure(error,**context,synthetic=True)))
    class Journal:
        def call(self,key,fn,**kwargs):return fn()
    fake=types.SimpleNamespace(closed=False,render_contexts=[types.SimpleNamespace(free=cleanup_raise)],
        context=None,initialized=False,calls=None,api=None,journal=Journal(),cleanup_errors=[],destination=out/'Velocity')
    close(fake)
    assert len(fake.cleanup_errors)==1 and 'cleanup_raise' in fake.cleanup_errors[0]['traceback']
    # The production close is shared; synthetic scope is injected only into saved fixture envelope.
    write_new(out/'EXTRACTED_GRAPHICS_CLEANUP_PROOF.json',dict(synthetic=True,production_handler=fake.cleanup_errors,
        real_graphics_calls=0,primary_file_unchanged=(out/'failure.json').read_bytes()==original))
    return dict(primary_preserved=True,separate_cleanup=True,live_tracebacks=True,extracted_graphics_handler=True)
check('live_traceback_primary_cleanup_separation',traceback_checks)

def payload_static():
    calls=[]
    for rel in ['causal_contract.py','runtime_engine.py']:
        tree=ast.parse((P/'code'/rel).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='emit':
                keys={k.arg for k in node.keywords if k.arg is not None}
                assert not keys.intersection(PROTECTED_FIELDS)
                calls.append(dict(file=rel,line=node.lineno,event=ast.unparse(node.args[0]),keys=sorted(keys),
                    expanded_payloads=[ast.unparse(k.value) for k in node.keywords if k.arg is None]))
    write_new(WORK/'EMIT_PAYLOAD_AUDIT.json',dict(synthetic=True,calls=calls,
        dynamic_payloads='controller old/tail exercised by real run_branch; runtime transition row statically checked',reserved_fields=sorted(RESERVED_FIELDS)))
    engine=ast.parse((P/'code/runtime_engine.py').read_text())
    step=next(n for c in engine.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='step')
    row=next(n.value for n in ast.walk(step) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='row' for t in n.targets))
    assert not {k.arg for k in row.keywords}.intersection(PROTECTED_FIELDS)
    return dict(calls=len(calls),reserved_collisions=0)
check('targeted_real_emit_payload_audit',payload_static)
assert not any(k.split('.')[0] in FORBIDDEN for k in sys.modules)
write_new(WORK/'SOURCE_PROVENANCE.json',dict(synthetic=True,sources=provenance,recorder=dict(path=str(P/'code/core/event_recorder.py'),sha256=sha(P/'code/core/event_recorder.py')),
    controller=dict(path=str(P/'code/causal_contract.py'),sha256=sha(P/'code/causal_contract.py'))))
write_new(WORK/'RESULT.json',dict(status='PASS',synthetic=True,checks=checks,case_count=len(cases),cases=cases,
    forbidden_imports=[],real_models=0,real_environments=0,real_launchers=0,real_hardware_calls=0,old_runtime_stack_backfilled=False))
print(json.dumps(dict(status='PASS',checks=len(checks),branch_cases=len(cases),result=str(WORK/'RESULT.json'))))
