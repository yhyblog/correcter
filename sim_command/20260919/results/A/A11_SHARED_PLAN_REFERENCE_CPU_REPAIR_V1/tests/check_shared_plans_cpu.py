"""Real BANK loader/publishers/controller, with explicitly synthetic boundaries."""
import ast,copy,hashlib,importlib.util,json,struct,sys,types
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
import inheritance
FORBIDDEN={'torch','numpy','mujoco','gymnasium','metaworld','pynvml','OpenGL'}
def audit(event,args):
    if event=='import' and args[0].split('.')[0] in FORBIDDEN:raise AssertionError('forbidden import '+args[0])
    if event in ('ctypes.dlopen','ctypes.dlsym','subprocess.Popen','os.system'):raise AssertionError('forbidden runtime '+event)
sys.addaudithook(audit)
from core.contracts import ContractError,sha
from core.event_recorder import EventRecorder
from pool_protocol import ARMS,command,unpack,digest,classify_outcome
from controller import run_attempt
from full_state import snapshot,compare,REQUIRED
from storage import Store
from shared_plans import make_bank_document,saved_bank_ref,prepare_bank_reference,load_bank,active_key,FORMAT
from public_records import make_transition,publish_transition
from sidecar_output import emit_sidecar
from intervention import initial_evidence,was_intervened
OUT=Path(sys.argv[1]).resolve();OUT.mkdir(parents=True,exist_ok=False)
checks=[];counts=dict(fake_controls=0,fake_observations=0,fake_native_plans=0,synthetic_bank_files=0)
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,sort_keys=True,allow_nan=False)+'\n')
def ref(path,format='json'):return dict(path=str(path),sha256=sha(path),format=format)
def check(name,value,detail=None):
    checks.append(dict(name=name,passed=bool(value),detail=detail));assert value,name
def reject(name,fn):
    try:fn()
    except (ContractError,ValueError) as e:check(name,True,dict(type=type(e).__name__,message=str(e)));return
    raise AssertionError(name+' accepted')
input_path=OUT/'synthetic_source.json'
source=dict(source_id='SYNTHETIC_SOURCE',parent_source_id='SYNTHETIC_PARENT',cut=5,absolute_target=300,
    env_seed=19,master_seed=17,task='shelf-place-v3',split='train',instruction='synthetic shelf input',status='SYNTHETIC_ONLY')
write(input_path,source);small=ref(input_path)
signature=sha(input_path)
def payload(value):return struct.pack('<200f',*([value]*200))
PREFIX=payload(.05);SUFFIX=payload(.07)
class FakeBoundary:
    task='shelf-place-v3';H=10;cut=5;target=300;synthetic=True
    load_bank=load_bank
    def __init__(self,parent,job,success_at=None,mismatch=False):
        self.out=parent/job[0];self.out.mkdir(parents=True,exist_ok=False);self.store=Store(self.out,byte_limit=2*1024**2,record_limit=512*1024)
        self.job=job;self.success_at=success_at;self.mismatch=mismatch;self.steps=0;self.plan_refs={};self.plan_noise={};self.pending=None;self.trace=[]
        self.source_signature=signature
        self.cfg=dict(source=copy.deepcopy(source),source_signature=signature,source_manifest_ref=small,
            _normal_output=str(parent/'normal'),model_sha256='2'*64,feature_signature='3'*64,normalizer_ref=small,
            action_signature='4'*64,state_contract_sha256='5'*64,collection_policy=dict(name='synthetic_policy',version='fixture',checkpoint=small,training_lineage_ref=None))
        self.identity={k:'SYNTHETIC_'+k for k in ('campaign_id','task_id','run_id','node_role','hostname','wave_id','shard_id','release_id','driver','runtime','gpu_model')}
        self.identity.update({k:'a'*64 for k in ('code_sha256','config_sha256','data_manifest_sha256','model_sha256')})
    def reset(self):return 0
    def observe(self,obs,step):
        counts['fake_observations']+=1;assert obs==step
        r=self.store.json(f'observations/step{step}.json',dict(synthetic=True,step=step));n=ref(Path(r['path']))
        if self.pending is not None:
            publish_transition(self,self.pending,n,step);self.pending=None
        self.last_observation=n;self.last_proprio=[0.,0.,0.,0.]
    def sample(self,obs,namespace,repeat,step):
        counts['fake_native_plans']+=1;raw=PREFIX if namespace=='prefix' else SUFFIX
        path=Path(self.store.write(f'plans/{namespace}_{step}.f32',raw)['path']);self.plan_refs[digest(raw)]=ref(path,FORMAT)
        self.plan_noise[digest(raw)]=ref(path,'synthetic_no_model_noise');return raw
    def step(self,action,step,*,raw_plan,raw_index):
        assert self.steps==step and action==command(raw_plan,raw_index);self.steps+=1;counts['fake_controls']+=1
        success=self.steps==self.success_at
        self.trace.append(dict(step=step,index=raw_index,raw_sha=digest(raw_plan),active=getattr(self,'active_bank_plan_key',None)))
        self.pending=make_transition(self,raw_plan,raw_index,action,0.,success,success,False,step,digest(raw_plan))
        return self.steps,dict(success=success,terminated=success,truncated=False,technical_failure=False)
    def capture(self,step,raw,age):
        self.last_cut_raw=raw;groups={k:{} for k in REQUIRED}
        groups['identity']=dict(source_signature=self.source_signature);groups['queue_history']=dict(raw50=raw,age=age)
        groups['clocks']=dict(step=step,hidden=int(self.mismatch))
        state=snapshot(groups);self.store.json('CUT_STATE.json',state);return state
    def save_reference(self,state):
        self.reference=dict(source_signature=self.source_signature,state=state);self.store.json('CUT_REFERENCE.json',self.reference)
    def generate_bank(self,obs):
        plans={}
        # Explicit fixed synthetic arrays. a0 aliases fresh0; fresh1/fresh2 have
        # equal bytes intentionally, but their logical plan keys remain distinct.
        for key,value in [('fresh0',.1),('fresh1',.2),('fresh2',.2),('local_plus',.3),('local_minus',-.3)]:
            raw=payload(value);path=Path(self.store.write('bank/'+key+'.f32',raw)['path']);counts['synthetic_bank_files']+=1
            plans[key]=raw;self.plan_refs[digest(raw)]=ref(path,FORMAT);self.plan_noise[digest(raw)]=ref(path,'synthetic_no_model_noise')
        plans['a0']=plans['fresh0'];self.bank=plans
        self.store.json('bank/local_direction.json',dict(synthetic=True,no_projection_or_sampling=True))
        self.bank_manifest_ref=saved_bank_ref(self.store.json('BANK.json',make_bank_document(self,plans)))
        return plans
    def verify_prefix(self,reference):assert reference['source_signature']==self.source_signature
    def compare_state(self,a,b):return compare(a,b)
    def save_verification(self,v):self.verification=v;self.store.json('STATE_VERIFICATION.json',v)
    def clear_policy_queue(self):pass
    def finish(self,result):self.store.json('BRANCH_RESULT.json',result);emit_sidecar(self,result)
def drive(e,reference=None):
    r=EventRecorder(e.out/'events.jsonl',branch=e.job[0],source_id=source['source_id'],parent_source_id=source['parent_source_id'],synthetic=True,writer=e.store)
    return run_attempt(e,e.job,r,reference)
parent=OUT/'positive';normal=FakeBoundary(parent,ARMS[0],success_at=6);nr=drive(normal)
check('normal_complete_never_intervened',not json.loads((normal.out/'EPISODE_PUBLIC_V1.json').read_text())['intervened'])
check('real_BANK_producer_metadata_shape',json.loads((normal.out/'BANK.json').read_text())['plans']['a0']['logical_alias_of']=='fresh0')

# Extract precisely the previous deployed Engine.load_bank method (no runtime
# imports) and run it with its real stdlib dependencies, then old publisher.
oldtree=ast.parse((inheritance.PREVIOUS/'code/runtime_engine.py').read_text())
oldmethod=next(n for n in ast.walk(oldtree) if isinstance(n,ast.FunctionDef) and n.name=='load_bank')
ns=dict(Path=Path,ContractError=ContractError,sha=sha,unpack=unpack,digest=digest)
exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(oldmethod)],type_ignores=[])),'old_actual_Engine.load_bank','exec'),ns)
oldspec=importlib.util.spec_from_file_location('old_public_records',inheritance.PREVIOUS/'code/public_records.py');oldpub=importlib.util.module_from_spec(oldspec);oldspec.loader.exec_module(oldpub)
old=FakeBoundary(parent,next(j for j in ARMS if j[0]=='Q_a0_r1'))
prepare_bank_reference(old.cfg,parent,synthetic=True);ns['load_bank'](old,normal.reference)
old.observe(0,0);raw=old.bank['a0'];old.intervention_evidence=initial_evidence();old.active_bank_plan_key=None
t=oldpub.make_transition(old,raw,0,command(raw,0),0.,False,False,False,5,digest(raw));n=ref(Path(old.store.json('old_next.json',dict(synthetic=True))['path']))
reject('OLD_actual_loader_plus_publisher_rejects_legal_shared_BANK',lambda:oldpub.publish_transition(old,t,n,6))

engines={}
for branch,end in [('Q_a0_r0',16),('Q_local_plus_r0',15),('Q_local_minus_r0',15),('G0_fresh0_r0',11),('G0_fresh1_r0',10),('G0_fresh2_r0',10),('G0_old_r0',11)]:
    job=next(j for j in ARMS if j[0]==branch);e=FakeBoundary(parent,job,success_at=end)
    prepare_bank_reference(e.cfg,parent,synthetic=True);result=drive(e,normal.reference);engines[branch]=e
    episode=json.loads((e.out/'EPISODE_PUBLIC_V1.json').read_text())
    expected=job[1]!='old'
    check(branch+'_actual_loader_controller_publisher',episode['intervened']==expected and result['intervention_evidence']['returned_commitment_steps']==(10 if branch.startswith('Q_') else 5))
    transition=json.loads((e.out/'transitions/step005.json').read_text())
    if job[1]!='old':check(branch+'_exact_shared_plan_ref',transition['generated_chunk_ref']==e.shared_bank.item(job[1])['raw50_ref'])
    else:check('G0_old_keeps_branch_prefix_ref',Path(transition['generated_chunk_ref']['path']).is_relative_to(e.out))
    if end in (16,11):
        suffix=json.loads((e.out/f'transitions/step{end-1:03d}.json').read_text())
        check(branch+'_native_suffix_stays_local',Path(suffix['generated_chunk_ref']['path']).is_relative_to(e.out))
    check(branch+'_never_claims_real_G0_trigger',result['intervention_evidence']['online_G0_triggered'] is False)
check('a0_fresh0_exact_logical_alias',engines['Q_a0_r0'].shared_bank.item('a0')['raw50_ref']==engines['G0_fresh0_r0'].shared_bank.item('fresh0')['raw50_ref'])

# Invoke actual publisher on new unsaved transition IDs; every rejection must
# precede its writer. The frozen document SHA and requested plan key both bind.
e=engines['G0_fresh1_r0'];e.active_bank_plan_key='fresh1'
base=json.loads((e.out/'transitions/step005.json').read_text());n=base['next_observation_ref']
def publish(value):return publish_transition(e,copy.deepcopy(value),n,6)
bad=copy.deepcopy(base);bad['candidate_family']='fresh2'
check('collision_fixture_identical_bytes_and_path',e.shared_bank.item('fresh1')['raw50_ref']==e.shared_bank.item('fresh2')['raw50_ref'])
reject('same_bytes_wrong_requested_plan_key_rejected',lambda:publish(bad))
saved=e.active_bank_plan_key;e.active_bank_plan_key='fresh2'
reject('wrong_controller_plan_key_rejected',lambda:publish(base));e.active_bank_plan_key=saved
unlisted=normal.out/'not_in_BANK.f32';unlisted.write_bytes(payload(.2));bad=copy.deepcopy(base);bad['generated_chunk_ref']=ref(unlisted,FORMAT)
reject('same_normal_same_SHA_unlisted_path_rejected',lambda:publish(bad))
external=OUT/'arbitrary_external.f32';external.write_bytes(payload(.2));bad=copy.deepcopy(base);bad['generated_chunk_ref']=ref(external,FORMAT)
reject('arbitrary_external_same_content_rejected',lambda:publish(bad))
for key in ('observation_ref','next_observation_ref'):
    bad=copy.deepcopy(base);foreign=ref(normal.out/'observations/step5.json');bad[key]=foreign
    reject('cross_branch_'+key+'_rejected',lambda bad=bad,key=key:publish_transition(e,bad,foreign if key=='next_observation_ref' else n,6))
bad=copy.deepcopy(base);bad['source']['source_id']='OTHER_SOURCE'
reject('publisher_cross_source_rejected',lambda:publish(bad))
bad=copy.deepcopy(base);bad['generated_chunk_ref']['format']='wrong_format'
reject('publisher_shared_format_rejected',lambda:publish(bad))
bad=copy.deepcopy(base);bad['step']=20
reject('shared_plan_outside_commitment_rejected',lambda:publish_transition(e,bad,n,21))

# Small independent malformed BANKs. Each uses genuine producer/binder/loader;
# only the intentionally corrupt fixture file is edited before it is consumed.
def bad_bank_case(name,change=None,anchor_change=None,file_change=None):
    par=OUT/'negative'/name;norm=FakeBoundary(par,ARMS[0],success_at=6);drive(norm)
    bank_path=norm.out/'BANK.json';doc=json.loads(bank_path.read_text())
    if change:
        change(doc);write(bank_path,doc)
        result=json.loads((norm.out/'BRANCH_RESULT.json').read_text());result['bank_manifest_ref']['sha256']=sha(bank_path);write(norm.out/'BRANCH_RESULT.json',result)
    branch=FakeBoundary(par,next(j for j in ARMS if j[0]=='Q_a0_r0'))
    prepare_bank_reference(branch.cfg,par,synthetic=True)
    if anchor_change:anchor_change(branch)
    if file_change:file_change(doc)
    reject(name,lambda:load_bank(branch,norm.reference))
bad_bank_case('wrong_parent',lambda d:d.update(parent_source_id='OTHER_PARENT'))
bad_bank_case('wrong_source',lambda d:d.update(source_id='OTHER_SOURCE'))
bad_bank_case('wrong_source_signature',lambda d:d.update(source_signature='0'*64))
bad_bank_case('wrong_cut',lambda d:d.update(cut=4))
bad_bank_case('wrong_source_manifest',lambda d:d['source_manifest_ref'].update(sha256='0'*64))
bad_bank_case('wrong_BANK_SHA',anchor_change=lambda e:e.cfg['_reference_bank_ref'].update(sha256='0'*64))
bad_bank_case('wrong_BANK_supplied_content',anchor_change=lambda e:e.cfg['_reference_bank'].update(extra='unbound'))
bad_bank_case('wrong_plan_key_mapping',lambda d:d['plans']['a0'].update(plan_key='fresh0'))
bad_bank_case('wrong_plan_alias',lambda d:d['plans']['a0'].update(logical_alias_of='fresh1'))
bad_bank_case('wrong_shape',lambda d:d['plans']['a0'].update(shape=[40,5]))
bad_bank_case('wrong_dtype',lambda d:d['plans']['a0'].update(dtype='>f4'))
bad_bank_case('wrong_plan_format',lambda d:d['plans']['a0']['raw50_ref'].update(format='bytes'))
bad_bank_case('wrong_realpath',lambda d:d['plans']['a0'].update(raw50_realpath='/OTHER_PATH'))
bad_bank_case('wrong_plan_raw_content',file_change=lambda d:Path(d['plans']['a0']['raw50_ref']['path']).write_bytes(payload(.9)))
bad_bank_case('wrong_BANK_path',anchor_change=lambda e:e.cfg['_reference_bank_ref'].update(path=str(external)))

# Actual precut controller -> actual episode publisher, and failed full-state
# gate leaves the private intervention evidence unentered (no invented episode).
early=FakeBoundary(OUT/'precut',next(j for j in ARMS if j[0]=='Q_a0_r0'),success_at=2);er=drive(early)
check('actual_precut_episode_intervened_false',json.loads((early.out/'EPISODE_PUBLIC_V1.json').read_text())['intervened'] is False and not er['intervention_evidence']['commitment_entered'])
check('precut_missing_sidecar_still_explicit',(early.out/'SIDECAR_MISSING.json').exists() and not (early.out/'SIDECAR_V1.json').exists())
failure=FakeBoundary(OUT/'before_intervention_failure',next(j for j in ARMS if j[0]=='Q_a0_r0'),mismatch=True)
reject('full_state_failure_before_intervention',lambda:drive(failure,normal.reference))
check('failed_state_never_entered_or_replaced',failure.intervention_evidence==initial_evidence())
check('failure_flag_false',was_intervened(dict(intervention_evidence=failure.intervention_evidence,legal_cut_reached=True,restore_level='failed')) is False)
write(failure.out/'INTERVENTION_FAILURE_EVIDENCE.json',dict(synthetic=True,evidence=failure.intervention_evidence,public_episode_saved=False))
check('G0_old_is_control_not_candidate_replacement',engines['G0_old_r0'].intervention_evidence['kind']=='old_queue_control' and not engines['G0_old_r0'].intervention_evidence['plan_replaced'])
tree=ast.parse((P/'code/runtime_engine.py').read_text());engine_class=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Engine')
check('runtime_Engine_binds_exact_tested_loader',any(isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='load_bank' and isinstance(n.value,ast.Name) and n.value.id=='verified_load_bank' for n in engine_class.body))
for path in (P/'code').rglob('*.py'):ast.parse(path.read_text())
check('forbidden_runtime_never_imported',not any(n.split('.')[0] in FORBIDDEN for n in sys.modules))
write(OUT/'CHECKS.json',dict(status='PASS',checks=checks,count=len(checks),synthetic=True,synthetic_counts=counts,
    real_model_environment_hardware_holder_launcher_claim_calls=0,old104_or133_suite_executed=False,deletions=0))
print(json.dumps(dict(status='PASS',checks=len(checks),synthetic_counts=counts,output=str(OUT))))
