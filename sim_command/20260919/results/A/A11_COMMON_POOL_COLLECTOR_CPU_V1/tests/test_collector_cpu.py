"""Targeted synthetic tests. Imports production controller, serializer and writer.
No Torch/NumPy/MuJoCo/native runtime import, live process, hardware or real claim.
"""
import ast,copy,hashlib,json,math,os,random,struct,sys,traceback
from pathlib import Path
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'code'))
from controller import run_attempt,sequential_jobs
from core.contracts import ContractError,Meter,reconcile,configure_store,sha
from core.event_recorder import EventRecorder,EventIdentityConflict
from core.failure_evidence import record_failure
from core.process_family import drain_group
from pool_protocol import ARMS,local_pair,project_direction,unpack,raw_group,command,stream_seed,paired_label,classify_outcome,digest
from full_state import snapshot,compare,REQUIRED
from storage import Store,StorageDenied
from authorization import check_documents,exclusive_record,verify_ref
from budget import TOTAL,numeric_caps
from sidecar_output import emit_sidecar,aggregate
OUT=Path(sys.argv[1]).resolve();OUT.mkdir(parents=True,exist_ok=False)
CHECKS=[];OPS={'synthetic_adapter_plans':0,'synthetic_adapter_controls':0,'synthetic_adapter_observations':0,
    'synthetic_candidate_gaussian_nodes':0,'synthetic_candidate_projections':0,'real_model_environment_hardware_calls':0}
def check(name,value):
    CHECKS.append(dict(name=name,passed=bool(value)))
    if not value:raise AssertionError(name)
def refuses(name,fn,cls=Exception):
    try:fn()
    except cls as e:check(name,True);return e
    raise AssertionError(name+' did not reject')
def rr(path,fmt='json'):return dict(path=str(path),sha256=sha(path),format=fmt)
def jsonwrite(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,sort_keys=True))
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
        self.bank={f'fresh{i}':self.sample(obs,'fresh',i,5) for i in range(3)};self.bank['a0']=self.bank['fresh0']
        pair=local_pair(self.bank['a0'],23);OPS['synthetic_candidate_gaussian_nodes']+=12;OPS['synthetic_candidate_projections']+=1
        self.store.json('bank/local_direction.json',pair['evidence'])
        for k,v in pair['plans'].items():
            self.bank[k]=v['raw'];f=self.out/'bank'/f'{k}.f32';self.store.write(f,v['raw']);self.plan_refs[digest(v['raw'])]=rr(f,'synthetic_float32');self.plan_noise[digest(v['raw'])]=self.plan_noise[digest(self.bank['a0'])]
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
def drive(engine):
    recorder=EventRecorder(engine.out/'events.jsonl',branch=engine.job[0],source_id='CPU_SYNTHETIC_SOURCE',parent_source_id='CPU_SYNTHETIC_PARENT',split='train',synthetic=True,writer=engine.store)
    return run_attempt(engine,engine.job,recorder,engine.shared.get('reference'))
def suite():
    # Full virtual timing, actual production recorder/controller + fake boundary.
    parent=OUT/'controller';shared={};engines=[]
    for job in ARMS:
        e=FakeEngine(job,parent,shared);result=drive(e);engines.append(e)
        check(job[0]+'_s300_complete',result['controls']==300 and result['outcome']['success']==0 and result['legal_cut_reached'])
        check(job[0]+'_native_samples',e.counts['sample']==(33 if job[0]=='normal' else 30))
        events=[json.loads(x) for x in (e.out/'events.jsonl').read_text().splitlines()]
        check(job[0]+'_real_recorder_scope',all(x['synthetic'] and x['branch']==job[0] for x in events))
        if job[0]!='normal':
            c=next(x for x in events if x['event']=='commitment_finished');expected=10 if job[0].startswith('Q_') else 5
            check(job[0]+'_commitment_and_tail',c['actual_steps']==expected and c['discarded_raw_tail']==(40 if expected==10 or job[1]=='old' else 45))
            suffix=[x for x in e.trace if x['kind']=='sample' and x['namespace'] in ('Q_C10','G0_C5')]
            check(job[0]+'_H10_resume',suffix[0]['step']==5+expected and result['restore_level']=='full_state_verified')
    check('totals_15_4500_453_4515',len(engines)==15 and sum(e.counts['control'] for e in engines)==4500 and sum(e.counts['sample'] for e in engines)==453 and sum(e.counts['observe'] for e in engines)==4515)
    check('prefix_noise_same_across_repeats',len({e.prefix[0] for e in engines})==1)
    check('nominal_budget_arithmetic',TOTAL['env_steps']==4500 and TOTAL['vla_sampling_calls']==453 and TOTAL['flow_forward_calls']==4530 and TOTAL['environment_reset_calls']==780 and TOTAL['reset_model_calls']==1560 and TOTAL['initialization_physics_substeps']==390000)
    dest=parent/'aggregate';dest.mkdir();labels=aggregate(parent,Store(dest))
    check('actual_aggregate_sidecars_validate',len(list(dest.glob('SIDECAR_AGGREGATE*.json')))==4 and all(v['valid_pair_repeat_ids']==[0,1] for v in labels.values()))
    old=json.loads((parent/'G0_old_r0/SIDECAR_V1.json').read_text());check('old_C5_is_queue_rows5_through9',old['plans']['raw_C5_sha256']==digest(engines[0].last_cut_raw[80:160]))
    for name,at,trunc in [('early_success',7,None),('success_s300',300,None),('unknown_truncation',None,17)]:
        e=FakeEngine(ARMS[0],OUT/name,{},success_at=at,truncate_at=trunc);r=drive(e)
        check(name+'_outcome',r['outcome']['success']==(None if trunc else 1) and r['outcome']['outcome_complete']==(not bool(trunc)))
    e=FakeEngine(ARMS[0],OUT/'before_cut',{},success_at=3);r=drive(e);check('normal_no_cut_no_bank',not r['legal_cut_reached'] and 'bank' not in e.shared)
    e=FakeEngine(ARMS[1],OUT/'mismatch',shared,mismatch=True);refuses('hidden_state_mismatch_before_intervention',lambda:drive(e),ContractError)
    check('mismatch_does_not_enter_suffix',e.steps==5 and not any(x['kind']=='sample' and x['namespace']=='Q_C10' for x in e.trace))
    e=FakeEngine(ARMS[0],OUT/'other49',{});e.task='reach-v3';refuses('other49_default_reject',lambda:drive(e),ContractError)
    # Local direction, byte preservation and no RNG effects outside local stream.
    raw=struct.pack('<200f',*([0.,-.0,.2,.99,1.2,-1.2]+[.1]*194));before=random.getstate()
    pair=local_pair(raw,41);OPS['synthetic_candidate_gaussian_nodes']+=12;OPS['synthetic_candidate_projections']+=1
    check('candidate_RNG_isolated',random.getstate()==before)
    check('twelve_nodes_and_smooth_interpolation',len(pair['evidence']['nodes'])==4 and all(len(x)==3 for x in pair['evidence']['nodes']))
    for name,row in pair['plans'].items():
        check(name+'_tail_and_boundary_bits',row['raw'][160:]==raw[160:] and row['raw'][12:24]==raw[12:24])
        check(name+'_float32_execution_delta',all(abs(a-b)<=1e-6 for a,b in zip(row['actual_raw_delta'],row['actual_execution_delta'])))
    zero=project_direction(raw,[0.]*40);OPS['synthetic_candidate_projections']+=1
    check('zero_direction_no_resample_bits',all(x['raw']==raw for x in zero['plans'].values()))
    tail=bytearray(raw);struct.pack_into('<f',tail,160,.333);check('different_tail_same_C10_alias',raw_group(raw)==raw_group(bytes(tail)))
    bounded=bytearray(raw);struct.pack_into('<f',bounded,16,1.4)
    check('clamp_equal_is_not_raw_alias',command(raw,1)==command(bytes(bounded),1) and raw_group(raw)!=raw_group(bytes(bounded)))
    check('prefix_stream_does_not_include_repeat',stream_seed(1,'synthetic','prefix',0,0)==stream_seed(1,'synthetic','prefix',1,0))
    check('Q_G0_and_repeats_separate',len({stream_seed(1,'synthetic',ns,r,0) for ns in ('Q_C10','G0_C5') for r in (0,1)})==4)
    # Pair repeat intersection and cross-repeat source consistency.
    saved=json.loads((dest/'PAIRED_LABELS.json').read_text())['records'];q=[r for r in saved if r['target']=='Q_C10'];g=[r for r in saved if r['target']=='G0_C5']
    check('missing_Q_repeat_masks_pair',not paired_label([r for r in q if not(r['arm']=='local_plus' and r['repeat']==1)],['local_plus','local_minus'],'pair')['target_mask'])
    check('missing_fresh2_masks_G0',not paired_label([r for r in g if not(r['arm']=='fresh2' and r['repeat']==1)],['old','fresh0','fresh1','fresh2'],'G0')['target_mask'])
    cross=copy.deepcopy(q)
    for x in cross:
        if x['repeat']==1:x['parent']='different'
    check('cross_repeat_parent_rejected',not paired_label(cross,['local_plus','local_minus'],'pair')['target_mask'])
    alias=copy.deepcopy(q)
    for x in alias:
        if x['arm'] in ('local_plus','local_minus'):x['raw_group']='same'
    check('raw_alias_pair_mask',not paired_label(alias,['local_plus','local_minus'],'pair')['target_mask'])
    low=copy.deepcopy(g);low[0]['restore_level']='independent_replay_observable_match'
    check('observable_only_not_counterfactual',not paired_label(low,['old','fresh0','fresh1','fresh2'],'G0')['target_mask'])
    check('technical_censor_not_negative',classify_outcome(299,False,False,False,'technical_failure')['success'] is None)
    check('s300_inclusive_negative',classify_outcome(300,False,False,True)['success']==0)
    s=shared['reference']['state'];bad=copy.deepcopy(s);bad['unknown_fields']=['unclassified'];refuses('unknown_field_refuses',lambda:compare(s,bad),ContractError)
    bad=copy.deepcopy(s);bad['schema']='wrong';refuses('wrong_state_schema_refuses',lambda:compare(s,bad),ContractError)
    bad=copy.deepcopy(s);bad['fields'].append(bad['fields'][0]);refuses('duplicate_state_field_refuses',lambda:compare(s,bad),ContractError)
    from full_state import typed
    refuses('unknown_python_object_refuses',lambda:typed(object()),ContractError)
    check('signed_zero_distinguishable',typed(-0.)!=typed(0.))
    # Writer short writes, durable charge on ENOSPC, no ended-event refund.
    w=OUT/'writer';w.mkdir();short=Store(w/'short',byte_limit=100,record_limit=50,reserve_bytes=0,write_fn=lambda fd,v:os.write(fd,v[:2]))
    short.write('x',b'1234567');check('short_write_completed_exactly',(w/'short/x').read_bytes()==b'1234567' and short.used==7)
    calls=[0]
    def diskfull(fd,v):
        calls[0]+=1
        if calls[0]>1:raise OSError(28,'synthetic disk full')
        return os.write(fd,v[:2])
    fail=Store(w/'disk',byte_limit=100,record_limit=50,reserve_bytes=0,write_fn=diskfull)
    refuses('disk_failure_retained',lambda:fail.write('x',b'1234567'),OSError)
    check('failed_bytes_not_refunded',fail.used==7 and not(w/'disk/x').exists() and list((w/'disk').glob('*.partial_*'))[0].read_bytes()==b'12')
    refuses('writer_byte_limit',lambda:short.write('too_big',b'a'*51),StorageDenied)
    refuses('writer_path_escape',lambda:short.write('../outside',b'a'),StorageDenied)
    log=OUT/'missing_terminal.jsonl';meter=Meter(log,{'ops':2});meter.enter('partial',{'ops':1});ledger=reconcile(log,{'ops':2})
    check('missing_terminal_charged_once',ledger['entered']['ops']==1 and ledger['returned']['ops']==0 and ledger['unresolved']==[1])
    recorder=EventRecorder(OUT/'conflict.jsonl',branch='synthetic',source_id='synthetic',parent_source_id='synthetic',synthetic=True)
    refuses('production_recorder_reserved_branch',lambda:recorder.emit('bad',branch='duplicate'),EventIdentityConflict)
    check('recorder_conflict_no_partial_event',not(OUT/'conflict.jsonl').exists() and recorder.events==0)
    try:raise RuntimeError('synthetic primary traceback')
    except RuntimeError as e:
        evidence=record_failure(e,branch='synthetic',stage='fixture',category='primary',synthetic=True)
        jsonwrite(OUT/'SYNTHETIC_TRACEBACK.json',evidence)
    check('live_traceback_saved','raise RuntimeError' in evidence['traceback'] and evidence['synthetic'])
    calls=[]
    def fails(job):calls.append(job);return dict(returncode=3,remaining_group=[],cleanup_complete=True,result={})
    sequential_jobs(ARMS,fails);check('first_failure_stops_wave',len(calls)==1)
    calls=[]
    def uncleared(job):calls.append(job);return dict(returncode=0,remaining_group=[{'pid':99999}],cleanup_complete=False,result={})
    sequential_jobs(ARMS,uncleared);check('exit_barrier_blocks_next',len(calls)==1)
    ticks=[0.];sent=[];member=[dict(pid=999991,start_ticks=17)]
    def reader(group,owner):return member if ticks[0]<31 else []
    drain=drain_group(999990,999990,reader=reader,send=lambda p,s:sent.append((p,int(s))),clock=lambda:ticks[0],pause=lambda x:ticks.__setitem__(0,ticks[0]+x))
    check('fake_group_TERM_KILL_exit_barrier',drain['status']=='all_formal_group_members_exited' and [x[1] for x in sent]==[15,9])
    refuses('wrong_group_ownership',lambda:drain_group(2,1,reader=lambda a,b:[],send=lambda a,b:None),RuntimeError)
    claim=OUT/'SYNTHETIC_CLAIM.json';exclusive_record(claim,{'synthetic':True});refuses('duplicate_synthetic_claim_refuses',lambda:exclusive_record(claim,{}),FileExistsError)
    blob=OUT/'input';blob.write_bytes(b'synthetic');refuses('wrong_input_SHA_refuses',lambda:verify_ref(dict(path=str(blob),sha256='0'*64)),ContractError)
    # JSON metadata from the actual prepared proposal, never a runtime entry.
    prop=json.loads((P/'proposal/PROPOSAL.json').read_text());prop['_sha256']=sha(P/'proposal/PROPOSAL.json')
    release=json.loads((P/'proposal/RELEASE_TEMPLATE.json').read_text());board=json.loads((P/'proposal/BOARD_TEMPLATE.json').read_text());control=json.loads((P/'proposal/CONTROL_TEMPLATE.json').read_text())
    refuses('unauthorized_template_refuses',lambda:check_documents(control,board,release,prop,prop['owner_host']),ContractError)
    release['status']='released'
    for state in ('ready','running'):
        b=copy.deepcopy(board);b['tasks'][0]['status']=state;check('board_'+state+'_passes',check_documents(control,b,release,prop,prop['owner_host'])['status']=='PASS')
    b=copy.deepcopy(board);b['tasks'][0]['status']='released';refuses('board_released_refuses',lambda:check_documents(control,b,release,prop,prop['owner_host']),ContractError)
    for key,value in [('release_id','OLD'),('status','closed'),('proposal_sha256','0'*64),('owner_host','wrong')]:
        r=copy.deepcopy(release);r[key]=value;refuses('wrong_'+key+'_refuses',lambda:check_documents(control,board,r,prop,prop['owner_host']),ContractError)
    r=copy.deepcopy(release);r['device']['gpu_uuid']='wrong';refuses('wrong_UUID_refuses',lambda:check_documents(control,board,r,prop,prop['owner_host']),ContractError)
    check('forbidden_modules_not_imported',not any(m.split('.')[0] in ('torch','mujoco','OpenGL','pynvml','ctypes','numpy','runtime_engine','runtime_state','execution') for m in sys.modules))
    jsonwrite(OUT/'CONTROLLER_TOTALS.json',dict(synthetic=True,engines=[dict(job=e.job,counts=e.counts,result=e.result) for e in engines],operations=OPS))
try:
    suite();status='PASS';failure=None
except BaseException as e:status='FAIL';failure=traceback.format_exc()
result=dict(status=status,synthetic=True,checks=CHECKS,passed=sum(x['passed'] for x in CHECKS),failure=failure,operations=OPS,
    real_operations=0,real_launcher_invocations=0,real_claims=0,hardware_queries=0)
jsonwrite(OUT/'CHECK_RESULT.json',result);print(json.dumps(result,ensure_ascii=False))
sys.exit(0 if status=='PASS' else 1)
