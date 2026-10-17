"""Reused synthetic boundaries only; no previous suites or assertions executed."""
import copy,json,struct
from pathlib import Path
from core.contracts import ContractError,sha
from core.event_recorder import EventRecorder
from controller import run_attempt
from task_profiles import PROFILES
from pool_protocol import ARMS,command,digest,local_pair,stream_seed
from full_state import snapshot,compare,REQUIRED
from storage import Store
from shared_plans import make_bank_document,saved_bank_ref,prepare_bank_reference,load_bank,FORMAT
from public_records import make_transition,publish_transition
from sidecar_output import emit_sidecar
from batch_publication import publish_parent
OUT=None
counts=dict(synthetic_controls=0,synthetic_observations=0,synthetic_plans=0,synthetic_local_pairs=0,synthetic_controller_attempts=0,synthetic_scheduler_starts=0,synthetic_claims=0)
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,allow_nan=False)+'\n')

def ref(path,format='json'):return dict(path=str(path),sha256=sha(path),format=format)

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
        parent_source_id=engine.spec['source']['parent_source_id'],split=engine.spec['source']['split'],synthetic=True,writer=engine.store)
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
