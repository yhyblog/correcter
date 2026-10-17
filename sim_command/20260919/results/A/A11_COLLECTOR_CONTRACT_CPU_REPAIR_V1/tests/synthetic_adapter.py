"""Only inherited fake adapter, explicit synthetic constant bank; no old suite."""
import random,struct
from pathlib import Path
from storage import Store
from pool_protocol import command,stream_seed,digest
from full_state import snapshot,compare,REQUIRED
from core.contracts import ContractError,sha
from sidecar_output import emit_sidecar
OUT=Path('SYNTHETIC_ONLY')
OPS={'synthetic_adapter_observations':0,'synthetic_adapter_plans':0,'synthetic_adapter_controls':0}
def rr(path,fmt='json'):return dict(path=str(path),sha256=sha(path),format=fmt)
class FakeEngine:
    task='shelf-place-v3';H=10;cut=5;target=300;synthetic=True
    def __init__(self,job,parent,shared,success_at=None,truncate_at=None,mismatch=False):
        self.job=job;self.out=parent/job[0];self.out.mkdir(parents=True,exist_ok=False);self.store=Store(self.out,byte_limit=2*1024**2,record_limit=512*1024)
        self.shared=shared;self.success_at=success_at;self.truncate_at=truncate_at;self.mismatch=mismatch
        self.steps=0;self.decisions={};self.counts={'sample':0,'observe':0,'control':0};self.trace=[];self.plan_refs={};self.plan_noise={};self.prefix=[]
        ref=dict(path=str(OUT/'synthetic_input.json'),sha256='a'*64,format='synthetic')
        self.cfg=dict(source=dict(parent_source_id='CPU_SYNTHETIC_PARENT',source_id='CPU_SYNTHETIC_SOURCE',master_seed=17,env_seed=19,instruction='synthetic only'),
            source_signature='1'*64,source_manifest_ref=ref,model_sha256='2'*64,feature_signature='3'*64,normalizer_ref=ref,action_signature='4'*64,
            state_contract_sha256='5'*64,_normal_output=str(parent/'normal'),collection_policy=dict(name='synthetic_policy',version='fixture',checkpoint=ref,training_lineage_ref=None))
        keys=['campaign_id','task_id','run_id','node_role','hostname','wave_id','shard_id','release_id','driver','runtime','gpu_model']
        self.identity={k:'CPU_SYNTHETIC_'+k for k in keys}
        self.identity.update({k:'b'*64 for k in ['code_sha256','config_sha256','data_manifest_sha256','model_sha256']})
    def reset(self):return 0
    def observe(self,obs,step):
        assert obs==step;self.counts['observe']+=1;OPS['synthetic_adapter_observations']+=1
    def clear_policy_queue(self):pass
    def sample(self,obs,namespace,repeat,step):
        if namespace=='prefix':repeat=None
        key=(namespace,repeat);idx=self.decisions.get(key,0);self.decisions[key]=idx+1
        seed=stream_seed(17,'CPU_SYNTHETIC_PARENT',namespace,repeat,idx)
        rng=random.Random(seed);raw=struct.pack('<200f',*[rng.uniform(-.5,.5) for _ in range(200)])
        self.counts['sample']+=1;OPS['synthetic_adapter_plans']+=1
        self.trace.append(dict(kind='sample',namespace=namespace,step=step,repeat=repeat,seed=seed,raw_sha=digest(raw)))
        path=self.out/f'plan_{self.counts["sample"]}.f32';self.store.write(path,raw);self.plan_refs[digest(raw)]=rr(path,'synthetic_float32');self.plan_noise[digest(raw)]=rr(path,'synthetic_not_model_noise')
        if step<5:self.prefix.append(digest(raw))
        return raw
    def step(self,action,step,*,raw_plan,raw_index):
        assert step==self.steps and action==command(raw_plan,raw_index)
        self.trace.append(dict(kind='control',step=step,index=raw_index,raw_sha=digest(raw_plan)))
        self.steps+=1;self.counts['control']+=1;OPS['synthetic_adapter_controls']+=1
        return self.steps,dict(success=self.steps==self.success_at,terminated=self.steps==self.success_at,
            truncated=self.steps==self.truncate_at,technical_failure=False)
    def capture(self,step,raw,age):
        self.last_cut_raw=raw
        groups={k:dict(value=k) for k in REQUIRED};groups['identity']=dict(source='CPU_SYNTHETIC_SOURCE',prefix=self.prefix)
        groups['queue_history']=dict(raw=raw,age=age);groups['clocks']=dict(step=step,phase=20,hidden=1 if self.mismatch else 0)
        state=snapshot(groups);self.store.json('CUT_STATE.json',state);return state
    def save_reference(self,state):
        self.shared['reference']=dict(state=state,prefix=self.prefix)
        self.store.json('CUT_REFERENCE.json',self.shared['reference'])
    def generate_bank(self,obs):
        self.bank={}
        for n,value in [('a0',.1),('local_plus',.2),('local_minus',-.2),('fresh0',.1),('fresh1',.3),('fresh2',-.3)]:
            raw=struct.pack('<200f',*([value]*200));self.bank[n]=raw
            path=self.out/'bank'/f'{n}.f32';self.store.write(path,raw)
            self.plan_refs[digest(raw)]=rr(path,'synthetic_float32');self.plan_noise[digest(raw)]=rr(path,'synthetic_no_noise_draw')
        self.store.json('bank/local_direction.json',{'synthetic':True,'not_numerically_recomputed':True})
        self.shared.update(bank=self.bank,plan_refs=self.plan_refs.copy(),plan_noise=self.plan_noise.copy())
        return self.bank
    def verify_prefix(self,reference):
        if self.prefix!=reference['prefix']:raise ContractError('wrong synthetic source/prefix')
    def compare_state(self,a,b):return compare(a,b)
    def save_verification(self,v):self.verification=v;self.store.json('STATE_VERIFICATION.json',v)
    def load_bank(self,reference):
        self.bank=self.shared['bank'];self.plan_refs.update(self.shared['plan_refs']);self.plan_noise.update(self.shared['plan_noise']);return self.bank
    def finish(self,result):
        self.result=result;self.store.json('BRANCH_RESULT.json',result);emit_sidecar(self,result)
