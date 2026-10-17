"""Targeted new batch combinations; all models/envs/processes explicitly synthetic.
The recorder, controller, BANK loader, transition/sidecar publisher, batch
scheduler and publication barrier are production functions, not fake copies.
"""
import ast,copy,hashlib,json,struct,sys,traceback,types
from contextlib import contextmanager
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
import inheritance
FORBIDDEN={'torch','numpy','mujoco','gymnasium','metaworld','pynvml','OpenGL'}
def audit(event,args):
    if event=='import' and args[0].split('.')[0] in FORBIDDEN:raise AssertionError('forbidden import '+args[0])
    if event in ('ctypes.dlopen','ctypes.dlsym','subprocess.Popen','os.system','os.kill','os.killpg'):
        raise AssertionError('forbidden real runtime '+event)
    if event=='open' and isinstance(args[0],str) and args[0].endswith('.safetensors'):
        raise AssertionError('large checkpoint read forbidden')
sys.addaudithook(audit)
from core.contracts import ContractError,sha,configure_store
from core.event_recorder import EventRecorder,EventIdentityConflict
from core.process_family import drain_group
from controller import run_attempt
from task_profiles import PROFILES,FIXED_SLOTS,profile,initialization_caps,validate_config
from pool_protocol import ARMS,command,digest,local_pair,stream_seed
from full_state import snapshot,compare,REQUIRED
from storage import Store,StorageDenied
from shared_plans import make_bank_document,saved_bank_ref,prepare_bank_reference,load_bank,FORMAT
from public_records import make_transition,publish_transition
from sidecar_output import emit_sidecar
from batch_publication import publish_parent
from batch_scheduler import run_schedule,validate_schedule,lifecycle_driver,OnceObservation,GlobalFault
from batch_storage import gate as storage_gate,BatchMonitor
from budget import numeric_caps,parent_caps,batch_caps,batch_timeouts,scheduler_caps,batch_storage
from authorization import check_documents,check_parent_documents,exclusive_record
from observation_phase import observation_phase,validate_observation_config
OUT=Path(sys.argv[1]).resolve();OUT.mkdir(parents=True,exist_ok=False)
checks=[];counts=dict(synthetic_controls=0,synthetic_observations=0,synthetic_plans=0,
    synthetic_local_pairs=0,synthetic_controller_attempts=0,synthetic_scheduler_starts=0,synthetic_claims=0)
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,allow_nan=False)+'\n')
def ref(path,format='json'):return dict(path=str(path),sha256=sha(path),format=format)
def check(name,value,detail=None):
    checks.append(dict(name=name,passed=bool(value),detail=detail))
    if not value:raise AssertionError(name)
def reject(name,fn,kind=(ContractError,ValueError,TypeError)):
    try:fn()
    except kind as e:check(name,True,dict(type=type(e).__name__,message=str(e)));return
    raise AssertionError(name+' accepted')
def payload(x):return struct.pack('<200f',*([x]*200))

class SyntheticBoundary:
    """Only the model/environment/state reads are synthetic; real writers below."""
    H=10;target=300;synthetic=True;load_bank=load_bank
    def __init__(self,parent,job,success_at=None,mismatch=False):
        self.spec=parent;self.job=job;self.task=parent['source']['task'];self.cut=parent['source']['cut']
        self.out=Path(parent['paths']['output'])/job[0];self.out.mkdir(parents=True,exist_ok=False)
        self.store=Store(self.out,byte_limit=8*1024**2,record_limit=512*1024,file_limit=2048)
        self.steps=0;self.success_at=success_at;self.mismatch=mismatch;self.trace=[]
        self.plan_refs={};self.plan_noise={};self.pending=None;self.prefix=[]
        small=parent['source_ref'];self.source_signature=small['sha256']
        self.cfg=dict(source=copy.deepcopy(parent['source']),source_signature=self.source_signature,
            source_manifest_ref=small,_normal_output=str(self.out.parent/'normal'),model_sha256='2'*64,
            feature_signature='3'*64,normalizer_ref=small,action_signature='4'*64,state_contract_sha256='5'*64,
            collection_policy=dict(name='synthetic_policy',version='fixture',checkpoint=small,training_lineage_ref=None))
        self.identity={k:'SYNTHETIC_'+k for k in ('campaign_id','task_id','run_id','node_role','hostname','wave_id','shard_id','release_id','driver','runtime','gpu_model')}
        self.identity['run_id']='SYNTHETIC_'+parent['parent_key']
        self.identity.update({k:'a'*64 for k in ('code_sha256','config_sha256','data_manifest_sha256','model_sha256')})
    def reset(self):return 0
    def observe(self,obs,step):
        assert obs==step;counts['synthetic_observations']+=1
        n=ref(Path(self.store.json(f'observations/step{step}.json',dict(synthetic=True,step=step))['path']))
        if self.pending is not None:publish_transition(self,self.pending,n,step);self.pending=None
        self.last_observation=n;self.last_proprio=[0.]*4
    def sample(self,obs,namespace,repeat,step):
        counts['synthetic_plans']+=1
        raw=payload(.05+step*.00001 if namespace=='prefix' else .07)
        path=Path(self.store.write(f'plans/{namespace}_{repeat}_{step}.f32',raw)['path'])
        self.plan_refs[digest(raw)]=ref(path,FORMAT);self.plan_noise[digest(raw)]=ref(path,'synthetic_no_model_noise')
        self.trace.append(dict(kind='sample',step=step,namespace=namespace,raw_sha=digest(raw)))
        if namespace=='prefix':self.prefix.append(digest(raw))
        return raw
    def step(self,action,step,*,raw_plan,raw_index):
        assert self.steps==step and action==command(raw_plan,raw_index)
        self.steps+=1;counts['synthetic_controls']+=1;success=self.steps==self.success_at
        self.trace.append(dict(kind='control',step=step,index=raw_index,raw_sha=digest(raw_plan)))
        self.pending=make_transition(self,raw_plan,raw_index,action,0.,success,success,False,step,digest(raw_plan))
        return self.steps,dict(success=success,terminated=success,truncated=False,technical_failure=False)
    def capture(self,step,raw,age):
        self.last_cut_raw=raw;groups={k:{} for k in REQUIRED}
        groups['identity']=dict(source_signature=self.source_signature,task=self.task,prefix=self.prefix)
        groups['queue_history']=dict(raw50=raw,age=age)
        groups['clocks']=dict(step=step,hidden=int(self.mismatch))
        state=snapshot(groups);self.store.json('CUT_STATE.json',state);return state
    def save_reference(self,state):
        self.reference=dict(source_signature=self.source_signature,state=state,prefix=self.prefix)
        self.store.json('CUT_REFERENCE.json',self.reference)
    def generate_bank(self,obs):
        plans={}
        for i in range(3):
            raw=payload(.1+.05*i);key='fresh'+str(i)
            path=Path(self.store.write('bank/'+key+'.f32',raw)['path']);plans[key]=raw
            self.plan_refs[digest(raw)]=ref(path,FORMAT);self.plan_noise[digest(raw)]=ref(path,'synthetic_no_model_noise')
        plans['a0']=plans['fresh0'];pair=local_pair(plans['a0'],23);counts['synthetic_local_pairs']+=1
        self.store.json('bank/local_direction.json',dict(pair['evidence'],synthetic=True))
        for key,item in pair['plans'].items():
            raw=item['raw'];path=Path(self.store.write('bank/'+key+'.f32',raw)['path']);plans[key]=raw
            self.plan_refs[digest(raw)]=ref(path,FORMAT);self.plan_noise[digest(raw)]=self.plan_noise[digest(plans['a0'])]
        self.bank=plans;self.bank_manifest_ref=saved_bank_ref(self.store.json('BANK.json',make_bank_document(self,plans)))
        return plans
    def verify_prefix(self,reference):
        if reference['source_signature']!=self.source_signature or reference['prefix']!=self.prefix:
            raise ContractError('synthetic source/prefix mismatch')
    def compare_state(self,a,b):return compare(a,b)
    def save_verification(self,value):self.verification=value;self.store.json('STATE_VERIFICATION.json',value)
    def clear_policy_queue(self):pass
    def finish(self,result):self.store.json('BRANCH_RESULT.json',result);emit_sidecar(self,result)

def parent_spec(name,task,cut,index=0):
    root=OUT/name;root.mkdir(parents=True,exist_ok=False)
    source=dict(source_id='SYNTHETIC_SOURCE_'+name,parent_source_id='SYNTHETIC_PARENT_'+name,
        cut=cut,absolute_target=300,env_seed=19+index,master_seed=17+index,task=task,split='train',
        instruction=PROFILES[task]['instruction'],status='SYNTHETIC_ONLY')
    path=root/'SOURCE.json';write(path,source)
    return dict(parent_key=name,source=source,source_ref=ref(path),device=dict(gpu_uuid='SYNTHETIC_UUID_'+str(index)),
        paths=dict(output=str(root/'output'),cache=str(root/'cache')))

def drive(engine,reference=None):
    counts['synthetic_controller_attempts']+=1
    if engine.job[0]!='normal':prepare_bank_reference(engine.cfg,engine.out.parent,synthetic=True)
    recorder=EventRecorder(engine.out/'events.jsonl',branch=engine.job[0],source_id=engine.spec['source']['source_id'],
        parent_source_id=engine.spec['source']['parent_source_id'],split='train',synthetic=True,writer=engine.store)
    return run_attempt(engine,engine.job,recorder,reference)

class VirtualBackend:
    """Only process scheduling and model/environment boundaries are replaced."""
    synthetic=True
    def __init__(self,*,components=False,fail=None,system_fail=None):
        self.components=components;self.fail=fail;self.system_fail=system_fail
        self.started={};self.active={};self.trace=[];self.refs={};self.engines={};self.max_active=0
        self.exited=False;self.cleanup=None
    def refresh(self):pass
    def start(self,parent,job):
        key=parent['parent_key'];assert key not in self.active
        self.started.setdefault(key,[]).append(job[0]);self.active[key]=job[0]
        self.trace.append(('start',key,job[0],parent['device']['gpu_uuid']))
        self.max_active=max(self.max_active,len(self.active));counts['synthetic_scheduler_starts']+=1
        return dict(parent=parent,job=job,polls=0)
    def poll(self,h):
        h['polls']+=1
        if h['polls']==1:return None
        parent,job=h['parent'],h['job'];key=parent['parent_key']
        row=dict(branch=job[0],returncode=0,remaining_group=[],cleanup_complete=True,failure_scope='parent')
        if (key,job[0]) in (self.fail,self.system_fail):
            row.update(returncode=3,result=None,failure_scope='wave' if (key,job[0])==self.system_fail else 'parent')
        elif self.components:
            e=SyntheticBoundary(parent,job,success_at=parent['source']['cut']+12)
            result=drive(e,self.refs.get(key));self.engines[key,job[0]]=e
            if job[0]=='normal':self.refs[key]=e.reference
            row['result']=result
        else:row['result']=dict(status='complete',legal_cut_reached=True,restore_level='reference_capture' if job[0]=='normal' else 'full_state_verified',synthetic=True)
        self.trace.append(('exit',key,job[0]));del self.active[key];return row
    def record_exit(self,parent,job,row):self.trace.append(('record_exit',parent['parent_key'],job[0]))
    def drain(self):
        self.trace.append(('drain',tuple(self.active)));self.active.clear();self.exited=True
        self.cleanup=dict(status='all_formal_group_members_exited',synthetic=True,process_group='SYNTHETIC_ONLY',actions=[])
        return self.cleanup
    def was_started(self,parent):return parent['parent_key'] in self.started
    def publish(self,parent):
        assert self.exited and not self.active;self.trace.append(('publish',parent['parent_key']))
        if not self.components:return dict(parent_key=parent['parent_key'],synthetic=True)
        store=Store(Path(parent['paths']['output'])/'reserved',byte_limit=8*1024**2,record_limit=1024**2)
        return publish_parent(parent,store,self.cleanup,synthetic=True)

def schedule(name,parents,c,backend,gate=lambda:None):
    ticks=[0.];log=OUT/(name+'_scheduler.jsonl')
    recorder=EventRecorder(log,branch='synthetic_batch_manager',source_id='SYNTHETIC_BATCH_'+name,
        parent_source_id='not_applicable:synthetic_batch',split='train',synthetic=True)
    result=run_schedule(parents,c,backend,gate=gate,emit=recorder.emit,limits=scheduler_caps(c),timeouts=batch_timeouts(c),
        clock=lambda:ticks[0],pause=lambda t:ticks.__setitem__(0,ticks[0]+t))
    write(OUT/(name+'_result.json'),dict(result=result,trace=backend.trace,synthetic=True))
    events=[json.loads(line) for line in log.read_text().splitlines()]
    check(name+'_real_recorder',all(x['synthetic'] and x['branch']=='synthetic_batch_manager' for x in events))
    return result

def suite_components():
    # Two complete parent layouts combine real scheduler/controller/BANK/publication.
    parents=[parent_spec('combo_cut5','disassemble-v3',5,0),parent_spec('combo_cut55','shelf-place-v3',55,1)]
    backend=VirtualBackend(components=True);result=schedule('combined',parents,2,backend)
    check('combined_30_real_controller_branches',result['status']=='complete' and result['branch_starts']==30)
    check('concurrent_parent_limit_and_fixed_UUID',backend.max_active==2 and all(
        [x[2] for x in backend.trace if x[0]=='start' and x[1]==p['parent_key']]==[j[0] for j in ARMS] and
        {x[3] for x in backend.trace if x[0]=='start' and x[1]==p['parent_key']}=={p['device']['gpu_uuid']} for p in parents))
    for p in parents:
        root=Path(p['paths']['output']);cut=p['source']['cut']
        labels=json.loads((root/'reserved/PAIRED_LABELS.json').read_text())['labels']
        check(p['parent_key']+'_double_repeat_public_labels',all(v['target_mask'] and v['valid_pair_repeat_ids']==[0,1] for v in labels.values()))
        check(p['parent_key']+'_separate_private_cost_index',(root/'reserved/PRIVATE_COST_INDEX.json').exists())
        for job in ARMS[1:]:
            e=backend.engines[p['parent_key'],job[0]];r=json.loads((e.out/'BRANCH_RESULT.json').read_text())
            commitment=10 if job[0].startswith('Q_') else 5
            suffix=[x for x in e.trace if x['kind']=='sample' and x['namespace'] in ('Q_C10','G0_C5')]
            check(p['parent_key']+'_'+job[0]+'_cut_commitment_H10',r['restore_level']=='full_state_verified' and
                r['intervention_evidence']['returned_commitment_steps']==commitment and suffix[0]['step']==cut+commitment)
            t=json.loads((e.out/f'transitions/step{cut:03d}.json').read_text())
            check(p['parent_key']+'_'+job[0]+'_public_cut_and_local_observation',t['anchor_id'].endswith(':cut'+str(cut)) and Path(t['observation_ref']['path']).is_relative_to(e.out))
        check(p['parent_key']+'_public_private_cost_separation',json.loads((root/'Q_a0_r0/EPISODE_PUBLIC_V1.json').read_text())['cost_event_refs']==[])
    # Remaining task/cut combinations: normal plus Q and G0 actual caller paths.
    tested={(p['source']['task'],p['source']['cut']) for p in parents}
    for task in PROFILES:
        for cut in (5,55):
            if (task,cut) in tested:continue
            p=parent_spec('metadata_'+task+'_cut'+str(cut),task,cut,2)
            n=SyntheticBoundary(p,ARMS[0],success_at=cut+12);drive(n)
            for name in ('Q_a0_r0','G0_fresh2_r0'):
                e=SyntheticBoundary(p,next(j for j in ARMS if j[0]==name),success_at=cut+12)
                r=drive(e,n.reference);check(task+'_cut'+str(cut)+'_'+name,r['legal_cut_reached'] and r['restore_level']=='full_state_verified')
    # One full absolute target path, not a rerun of the old full15-branch suite.
    full=parent_spec('absolute300','stick-push-v3',55,3);e=SyntheticBoundary(full,ARMS[0]);r=drive(e)
    check('cut55_actual_controller_absolute_s300',r['controls']==300 and r['outcome']['success']==0 and r['outcome']['outcome_complete'])
    # New whole-wave failure and isolation state machine cases use process-only fake rows.
    ps=[parent_spec('slots'+str(i),FIXED_SLOTS[i][0],FIXED_SLOTS[i][2],i) for i in range(8)]
    for c in (1,2,4,8):
        be=VirtualBackend();rr=schedule('slots_c'+str(c),ps,c,be)
        check('concurrency_'+str(c)+'_eight_parents',rr['status']=='complete' and rr['branch_starts']==120 and be.max_active==c)
    be=VirtualBackend(fail=(ps[0]['parent_key'],'Q_a0_r0'));rr=schedule('one_parent_failure',ps[:2],2,be)
    check('ordinary_failure_stops_only_one_parent',len(be.started[ps[0]['parent_key']])==2 and len(be.started[ps[1]['parent_key']])==15 and rr['status']=='partial_or_failed')
    be=VirtualBackend(system_fail=(ps[0]['parent_key'],'normal'));rr=schedule('system_failure',ps[:2],2,be)
    check('system_fault_stops_owned_wave',rr['primary']['scope']=='wave' and all(len(v)==1 for v in be.started.values()) and rr['cleanup']['status']=='all_formal_group_members_exited')
    calls=[0]
    def stopped():
        calls[0]+=1
        if calls[0]==2:raise GlobalFault('synthetic CONTROL stop')
    be=VirtualBackend();rr=schedule('global_stop',ps[:2],2,be,stopped)
    check('CONTROL_stop_no_new_branches_after_stop',rr['branch_starts']==2 and rr['primary']['scope']=='wave')
    for field in ('source_id','parent_source_id'):
        bad=copy.deepcopy(ps[:2]);bad[1]['source'][field]=bad[0]['source'][field]
        reject('duplicate_'+field,lambda bad=bad:validate_schedule(bad,2))
    bad=copy.deepcopy(ps[:2]);bad[1]['device']=bad[0]['device'];reject('duplicate_physical_UUID',lambda:validate_schedule(bad,2))
    reject('oversized_parallelism',lambda:validate_schedule(ps,16))
    reject('other45_task_default_deny',lambda:profile('reach-v3',5))
    reject('cut_bool_default_deny',lambda:profile('shelf-place-v3',True))
    reject('cut_unquoted_default_deny',lambda:profile('shelf-place-v3',15))
    # Exact exit->restore ordering and inherited group draining with fake PID table.
    events=[];ticks=[0.];member=[dict(pid=999991,start_ticks=17)]
    def reader(group,owner):return member if ticks[0]<31 else []
    drained=drain_group(999990,999990,reader=reader,send=lambda p,s:events.append(('signal',p,int(s))),
        clock=lambda:ticks[0],pause=lambda t:ticks.__setitem__(0,ticks[0]+t))
    check('owned_group_drain_TERM_KILL_until_exit',[x[2] for x in events]==[15,9] and drained['status']=='all_formal_group_members_exited')
    events=[];observe=OnceObservation(lambda:events.append('restore') or dict(status='occupancy_resolved',synthetic=True))
    rr=lifecycle_driver(lambda:events.append('one_reservation_command') or 3,
        lambda:events.append('whole_group_exit') or drained,observe)
    observe();check('one_reservation_one_restore_after_whole_exit',events==['one_reservation_command','whole_group_exit','restore'] and rr['returncode']==3)
    reject('missing_exit_never_claimed_restored',lambda:lifecycle_driver(lambda:0,lambda:None,lambda:(_ for _ in ()).throw(AssertionError('must not restore'))))
    n=[0]
    def fail_observer():n[0]+=1;raise RuntimeError('synthetic observation failure')
    once=OnceObservation(fail_observer);once();once();check('restore_observation_exception_not_retried',n[0]==1)
    reject('wrong_group_owner_never_signaled',lambda:drain_group(2,1,reader=lambda a,b:[],send=lambda a,b:None),RuntimeError)
    reject('publish_before_whole_exit_rejected',lambda:publish_parent(ps[0],Store(OUT/'bad_publish'),dict(status='live'),synthetic=True))
def suite_metadata():
    # Real JSON authority + all eight real proposed config documents, no launcher.
    proposal=json.loads((P/'proposal/PROPOSAL.json').read_text());proposal['_sha256']=sha(P/'proposal/PROPOSAL.json')
    docs=json.loads((P/'proposal/CANDIDATE_PUBLICATION_DOCUMENTS.json').read_text())
    control,board,release=docs['CONTROL'],docs['TASK_BOARD'],docs['RELEASE'];host=proposal['owner_host']
    configs=[json.loads(Path(p['config']['path']).read_text()) for p in proposal['parents']]
    accepted=json.loads(Path(proposal['accepted_parent_index']['path']).read_text())
    check('all8_source_config_dedup_and_301_contract',check_parent_documents(proposal,configs,accepted)['status']=='PASS')
    def current_row(bb):return next(t for t in bb['tasks'] if t['id']=='A11_COMMON_POOL_BATCH1_V1')
    for status in ('ready','running'):
        bb=copy.deepcopy(board);current_row(bb)['status']=status
        check('publication_board_'+status,check_documents(control,bb,release,proposal,host)['status']=='PASS')
    for label,obj,change in [
        ('board_released',board,lambda d:current_row(d).update(status='released')),
        ('release_old',release,lambda d:d.update(release_id='OLD')),
        ('release_closed',release,lambda d:d.update(closed=True)),
        ('wrong_host',release,lambda d:d.update(owner_host='wrong')),
        ('wrong_caps',release,lambda d:d['resource_caps'].update(env_steps=0)),
        ('wrong_uuid',release,lambda d:d['parents'][0]['device'].update(gpu_uuid='wrong'))]:
        bad=copy.deepcopy(obj);change(bad)
        reject(label,lambda bad=bad,obj=obj:check_documents(control,bad if obj is board else board,bad if obj is release else release,proposal,host))
    unauthorized=json.loads((P/'proposal/RELEASE_TEMPLATE.json').read_text())
    reject('unauthorized_template',lambda:check_documents(control,board,unauthorized,proposal,host))
    active=json.loads((P.parents[2]/'CONTROL.json').read_text())
    reject('actual_CPU_CONTROL_rejects_compute',lambda:check_documents(active,board,release,proposal,host))
    for key in ('source_signature','source_manifest_ref'):
        bad=copy.deepcopy(configs)
        if key=='source_signature':bad[0][key]='0'*64
        else:bad[0][key]['sha256']='0'*64
        reject('config_'+key+'_binding',lambda bad=bad:check_parent_documents(proposal,bad,accepted))
    claim=OUT/'SYNTHETIC_CLAIM.json'
    claim_value=dict(time=0,release_sha256='a'*64,run_id='SYNTHETIC_BATCH_FIXTURE',consumed=True,remaining_caps_reusable=False)
    exclusive_record(claim,claim_value,'claim');counts['synthetic_claims']+=1
    reject('duplicate_synthetic_exclusive_claim',lambda:exclusive_record(claim,claim_value,'claim'),FileExistsError)
    # Concurrency resources and controlled storage boundaries use fake capacities.
    for c in (1,2,4,8):
        caps=scheduler_caps(c);s=batch_storage(c)
        check('planning_RAM_'+str(c),s['RAM_planning_bytes']==c*64*1024**3)
        check('finite_timeout_and_scheduler_'+str(c),caps['poll_iterations']>0 and batch_timeouts(c)['reserved_wave_seconds']==((8+c-1)//c)*27900+300)
    cap=dict(device=1,available_bytes=2**50,available_inodes=2**30)
    check('batch_capacity_admitted_not_quota',storage_gate(release,proposal,lambda p:cap)['project_quota_known'] is False)
    reject('batch_capacity_bytes',lambda:storage_gate(release,proposal,lambda p:dict(cap,available_bytes=1)))
    reject('batch_capacity_inodes',lambda:storage_gate(release,proposal,lambda p:dict(cap,available_inodes=1)))
    reject('two_filesystems_unquoted',lambda:storage_gate(release,proposal,lambda p:dict(cap,device=1 if p==proposal['paths']['output'] else 2)))
    old=copy.deepcopy(release);old['storage_admission']['mode']='bounded_first_parent'
    reject('old_single_parent_risk_not_batch_permission',lambda:storage_gate(old,proposal,lambda p:cap))
    monitor=BatchMonitor(proposal,Store(OUT/'monitor'),scan_fn=lambda p,n:dict(logical_file_bytes=0,entries=0),capacity_fn=lambda p:cap)
    check('eight_private_caches_one_monitor',len(monitor.check()['parents'])==8)
    monitor.scan=lambda p,n:dict(logical_file_bytes=3*1024**3,entries=1)
    reject('private_cache_threshold',monitor.check)
    tiny=Store(OUT/'hard_writer',byte_limit=100,record_limit=50,reserve_bytes=0)
    reject('controlled_record_hard_bytes',lambda:tiny.write('too_big',b'x'*51),StorageDenied)
    # Real CONFIG and exact native scope function; no NativeEGL construction/import.
    native=inheritance.BASE_CODE/'native/native_egl.py';tree=ast.parse(native.read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeEGL')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='observation_scope')
    ns=dict(contextmanager=contextmanager,Refused=ContractError)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(method)],type_ignores=[])),str(native),'exec'),ns)
    scope=types.SimpleNamespace(config=configs[0]['native'],phase=None,journal=types.SimpleNamespace(observation_phase=None))
    for step in range(301):
        with ns['observation_scope'](scope,observation_phase(step)):
            assert scope.phase=='step_'+str(step) and scope.journal.observation_phase==scope.phase
        assert scope.phase is None and scope.journal.observation_phase is None
    check('actual_native_scope_all301_config_phases',True,dict(source=str(native),source_sha256=sha(native)))
    for value in (-1,301,True,1.,'55'):reject('strict_observation_clock_'+repr(value),lambda value=value:observation_phase(value))
    try:
        with ns['observation_scope'](scope,'step_55'):
            with ns['observation_scope'](scope,'step_56'):pass
    except ContractError:pass
    else:raise AssertionError('nested scope accepted')
    check('scope_exception_and_nested_exit_clears_phase',scope.phase is None and scope.journal.observation_phase is None)
    bad=copy.deepcopy(configs[0]);bad['native']['observation_phases']=bad['native']['observation_phases'][:16]
    reject('old16phase_config_rejected',lambda:validate_observation_config(bad))
    tree=ast.parse((P/'code/runtime_engine.py').read_text());engine=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Engine')
    methodcalls={n.name:[ast.unparse(x.args[0]) for x in ast.walk(n) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='observation_scope'] for n in engine.body if isinstance(n,ast.FunctionDef)}
    check('actual_reset_and_step_use_same_phase_function',methodcalls['reset']==['observation_phase(0)'] and methodcalls['step']==['observation_phase(step + 1)'])
    state=ast.parse((P/'code/runtime_state.py').read_text())
    check('actual_state_captures_parent_GPU_rng',any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='get_rng_state' and n.args and ast.unparse(n.args[0])=='engine.device' for n in ast.walk(state)))
    for task in PROFILES:
        i=initialization_caps(task);check(task+'_derived_init_counts',i['environment_reset_calls']==52 and i['initialization_physics_substeps']==26000 and i['initialization_mj_forward_calls']==(106 if task=='pick-place-wall-v3' else 210))
    check('batch116caps_derived_upper_not_actual_example',len(proposal['resource_caps'])==116 and proposal['resource_caps']['vla_sampling_calls']==3624 and proposal['resource_caps']['flow_forward_calls']==36240 and proposal['resource_caps']['env_steps']==36000 and proposal['resource_caps']['observation_calls']==36120)
    check('cut55_sampling_preserves453',sum(numeric_caps(j[0],55)['vla_sampling_calls'] for j in ARMS)==453)
    check('cut_seed_namespace_preserves5_distinguishes55',stream_seed(17,'synthetic','prefix',0,0)==stream_seed(17,'synthetic','prefix',1,0,cut=5) and stream_seed(17,'synthetic','prefix',0,0,cut=5)!=stream_seed(17,'synthetic','prefix',0,0,cut=55))
    state=snapshot({k:{} for k in REQUIRED});bad=copy.deepcopy(state);bad['unknown_fields']=['unsupported']
    reject('unknown_full_state_field_remains_rejected',lambda:compare(state,bad))
    check('no_forbidden_runtime_modules',not any(x.split('.')[0] in FORBIDDEN for x in sys.modules))

try:
    if len(sys.argv)<3 or sys.argv[2]!='metadata':suite_components()
    suite_metadata();status='PASS';failure=None
except BaseException:status='FAIL';failure=traceback.format_exc()
configure_store(None)
result=dict(status=status,synthetic=True,checks=checks,checks_count=len(checks),passed=sum(x['passed'] for x in checks),
    failure=failure,synthetic_counts=counts,real_model_environment_hardware_holder_launcher_claim_operations=0,
    large_weight_hashes=0,old_whole_suites_executed=False,deletions=0)
write(OUT/'CHECK_RESULT.json',result)
print(json.dumps(dict(status=status,checks=len(checks),passed=result['passed'],failure=failure,synthetic_counts=counts,output=str(OUT))))
sys.exit(0 if status=='PASS' else 1)
