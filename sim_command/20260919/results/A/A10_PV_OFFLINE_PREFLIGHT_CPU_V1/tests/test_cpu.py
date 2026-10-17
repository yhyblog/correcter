"""Targeted stdlib-only tests; no numerical model or GPU library import."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import textwrap
import time

PKG=Path(__file__).resolve().parents[1]
WORK=PKG.parents[2]/'work/A/A10_PV_OFFLINE_PREFLIGHT_CPU_V1_r1'
OUT=WORK/('targeted_tests_'+str(time.time_ns()));OUT.mkdir(parents=True,exist_ok=False)
BLOCKED=[]
def audit(event,args):
    if event=='ctypes.dlopen' or event=='subprocess.Popen' or (event=='import' and args[0].split('.')[0] in {'torch','numpy','ctypes','mujoco','metaworld','OpenGL','pynvml'}):
        BLOCKED.append(dict(event=event,args=str(args)[:160]));raise RuntimeError('Forbidden during CPU test: '+event)
sys.addaudithook(audit)
sys.path.insert(0,str(PKG/'code'))
from core import contracts as c
from core.identity import normalize_pci,verify_device,check_policy_uuid
from launch import child_environment

rows=[]
def check(name,fn):
    try:value=fn();rows.append(dict(name=name,status='passed',evidence=value))
    except BaseException as e:rows.append(dict(name=name,status='failed',error=dict(type=type(e).__name__,message=str(e))))
def rejected(fn,typ=c.ContractError):
    try:fn()
    except typ:return True
    raise AssertionError('Expected fail-closed refusal')

proposal=c.read(PKG/'proposal/PROPOSAL.json');proposal['_sha256']=c.sha(PKG/'proposal/PROPOSAL.json')
release=c.read(PKG/'proposal/RELEASE_TEMPLATE.json');release.update(status='released',run_id='fake_run',wave_id='fake_wave',shard_id='fake_shard')
control=c.read(PKG/'proposal/CONTROL_REQUIRED.json')
control.update(campaign_id='corrector-sim-20260919',allowed_task_ids=[c.TASK])
board=dict(tasks=[control['board_task']]);release_path=c.CAMPAIGN/'releases'/ (c.RELEASE+'.json')
def valid():return c.validate_metadata(control,board,release,proposal,release_path,proposal['owner_host'])
check('synthetic_exact_future_authorization',valid)
for key,value in [('status','UNAUTHORIZED_TEMPLATE'),('task_id','A10_PREFLIGHT_NATIVE_V3'),('node_role','B'),('max_retries',1),('owner_host','wrong'),('proposal_sha256','0'*64),('resource_caps',{}),('cuda_environment',{})]:
    def test(key=key,value=value):
        r=deepcopy(release);r[key]=value
        return rejected(lambda:c.validate_metadata(control,board,r,proposal,release_path,proposal['owner_host']))
    check('reject_release_'+key,test)
for key,value in [('mode','prepare'),('formal_gpu_runs_enabled',False),('stop_requested',True),('active_compute_task_ids',[c.TASK,'B']),('active_compute_release_id','OLD'),('current_compute_limits',{})]:
    def test(key=key,value=value):
        x=deepcopy(control);x[key]=value
        return rejected(lambda:c.validate_metadata(x,board,release,proposal,release_path,proposal['owner_host']))
    check('reject_control_'+key,test)
check('current_CPU_release_cannot_launch',lambda:rejected(lambda:c.load_authorization(c.CAMPAIGN/'releases/P00_PV_OFFLINE_PREFLIGHT_CPU_V1.json')))
check('template_path_cannot_launch',lambda:rejected(lambda:c.load_authorization(PKG/'proposal/RELEASE_TEMPLATE.json')))

def exclusive_claim():
    old=c.CAMPAIGN;c.CAMPAIGN=OUT/'fake_campaign'
    try:
        r=dict(release,_sha256='f'*64);p=c.claim(r)
        rejected(lambda:c.claim(r),FileExistsError)
        return dict(path=str(p),claims=1,second_claim_denied=True,synthetic=True)
    finally:c.CAMPAIGN=old
check('exclusive_consumption_with_no_actual_claim',exclusive_claim)

def metering():
    p=OUT/'fake_events.jsonl';m=c.Meter(p,{'op':3,'forbidden':0})
    assert m.call('success',lambda:7,{'op':1})==7
    rejected(lambda:m.call('zero_cap',lambda:None,{'forbidden':1}))
    def fail():raise ValueError('synthetic partial failure')
    rejected(lambda:m.call('failure',fail,{'op':1}),ValueError)
    i=m.enter('synthetic_missing_terminal',{'op':1})
    rejected(lambda:m.enter('fourth_attempt',{'op':1}))
    x=c.reconcile(p,m.caps)
    assert x['entered']['op']==3 and x['returned']['op']==1 and len(x['failed'])==1 and x['unresolved']==[i]
    return x
check('entered_returned_failed_missing_terminal_no_refund',metering)

def torn_record():
    p=OUT/'fake_torn_events.jsonl';m=c.Meter(p,{'op':2});m.call('done',lambda:None,{'op':1})
    with p.open('a') as f:f.write('{"event_id":2,"phase":"entered"')
    x=c.reconcile(p,m.caps)
    assert x['counts_complete'] is False and x['entered']['op']==1 and len(x['corrupt_records'])==1
    return dict(known_entered_lower_bound=x['entered'],exact_count_unknown=True,no_zero_fabrication=True)
check('partial_JSON_entry_preserves_unknown_count_and_consumption',torn_record)

cfg=c.read(PKG/'config/CONFIG.json')
def visibility():
    env=child_environment(cfg,OUT/'retained_fake_cache',dict(NVIDIA_VISIBLE_DEVICES=cfg['cuda_environment']['NVIDIA_VISIBLE_DEVICES'],LD_PRELOAD='bad',PYTHONPATH='bad',MUJOCO_GL='egl'))
    assert all(env[k]==v for k,v in cfg['cuda_environment'].items())
    assert 'LD_PRELOAD' not in env and 'PYTHONPATH' not in env and 'MUJOCO_GL' not in env
    rejected(lambda:child_environment(cfg,OUT,{'NVIDIA_VISIBLE_DEVICES':'other'}))
    return {'frozen_visibility':True,'graphics_environment_not_required':True}
check('future_child_environment_no_hardware_calls',visibility)

def extract(path,name):
    s=path.read_text();t=ast.parse(s);nodes=[n for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name==name]
    assert len(nodes)==1
    return s,nodes[0]

class FakeArray(list):
    def __ge__(self,v):return FakeArray(x>=v for x in self)
    def __setitem__(self,key,value):
        if isinstance(key,slice):super().__setitem__(key,[list(x) if isinstance(x,(list,tuple)) else x for x in value])
        else:super().__setitem__(key,value)
class FakeTensor:
    def __init__(self,x):self.x=x
    def __getitem__(self,k):
        assert k is None;return [self.x]
class FakeNP:
    float32=float
    @staticmethod
    def zeros(shape,dtype):return FakeArray([0.]*shape[1] for _ in range(shape[0]))
    @staticmethod
    def arange(n):return FakeArray(range(n))
    @staticmethod
    def asarray(x):return FakeArray(x)
class FakeTorch:
    @staticmethod
    def as_tensor(x,device=None):return FakeTensor(x)

def one_frame():
    s,n=extract(PKG/'code/feature_path.py','cpu_batch')
    # Remove its local import; controlled fake is supplied without importing torch.
    fn=deepcopy(n);fn.body=[x for x in fn.body if not isinstance(x,ast.Import)]
    ns={'np':FakeNP,'torch':FakeTorch};exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<exact_cpu_batch_fake>','exec'),ns)
    spatial=[[2.]*4096];prop=[[.1,.2,.3,1.]];language=[3.]*2048
    x=ns['cpu_batch'](spatial,prop,[],language,0,device='cpu')
    assert x['history_mask']==[[False,False,False,False,True]] and x['proprio_mask']==x['history_mask']
    assert x['history'][0][4]==spatial[0] and all(v==0 for row in x['history'][0][:4] for v in row)
    assert x['proprio'][0][4]==prop[0] and all(v==0 for row in x['past_actions'][0] for v in row)
    assert x['remaining']==[1.]
    return dict(single_real_frame=True,zero_padding_masked=True,past_actions_zero=True,future_frame_not_input=True)
check('existing_cpu_batch_single_frame_fake',one_frame)

def noise_spec():
    p=PKG/'code/vendor_vla/src/lerobot/policies/pi05/modeling_pi05.py';s,n=extract(p,'sample_noise')
    class T:
        float32='float32'
        @staticmethod
        def normal(**kwargs):return kwargs
    ns={'torch':T};exec(compile(ast.fix_missing_locations(ast.Module(body=[n],type_ignores=[])),'<sample_noise_fake>','exec'),ns)
    x=ns['sample_noise'](None,(1,50,32),'cuda:0')
    assert x==dict(mean=0.,std=1.,size=(1,50,32),dtype='float32',device='cuda:0')
    return dict(actual_rng_calls=0,captured_frozen_call=x)
check('frozen_sample_noise_ABI_fake_no_draw',noise_spec)

def source_semantics():
    root=PKG.parents[5]
    # Compare actual function ASTs, not regenerated arithmetic implementations.
    pairs=[(root/'Corrector/experiments/standalone_ablation_20260918/candidates.py',PKG/'code/corrector/solo.py',['project_solo','audit_solo']),
           (root/'Corrector/src/corrector/guidance.py',PKG/'code/corrector/guidance.py',['flow_update','post_direction']),
           (root/'ACT-RECAP/src/ac_tmil/future_aware/features.py',PKG/'code/feature_path.py',['canonical_decode','spatial_tokens']),
           (root/'ACT-RECAP/src/ac_tmil/ogg/common.py',PKG/'code/feature_path.py',['cpu_batch'])]
    checked=[]
    for a,b,names in pairs:
        for name in names:
            _,na=extract(a,name);_,nb=extract(b,name)
            assert ast.dump(na,include_attributes=False)==ast.dump(nb,include_attributes=False),(a,name)
            checked.append(name)
    return {'unchanged_algorithm_bodies':checked,'numeric_tensor_execution':False}
check('frozen_independent_algorithm_and_feature_AST',source_semantics)

def syntax():
    files=[p for p in (PKG/'code').rglob('*.py') if 'vendor_vla' not in p.parts]
    for p in files:compile(p.read_text(),str(p),'exec')
    return dict(targeted_files=len(files),bytecode_written=False,imports_performed=False)
check('new_and_extracted_entry_static_syntax',syntax)

def quote():
    x=proposal['resource_caps'];q=proposal['call_quote']['Q']
    assert sum(q['objective_breakdown'].values())==x['objective_forward_calls']==10
    assert x['critic_forward_calls']==10*4==40 and x['action_gradient_calls']==1+3==4
    assert x['visual_encoder_forwards']==1+3==4 and x['language_embedding_forwards']==2 and x['encoder_forward_calls']==6
    assert x['own_projection_calls']==2+2==4 and x['raw_constraint_audits']==2
    assert x['vla_sampling_calls']==1 and x['baseline_sampling_calls']==0 and x['flow_forward_calls']==10
    assert all(x[k]==0 for k in ['vla_backward_calls','D_forward_calls','G0_forward_calls','environment_instances','environment_reset_calls','render_calls','training_updates','deletions','retries'])
    assert proposal['cost_semantics']['deployment_samples']=={'Post':1,'Velocity':2}
    return dict(quote_consistent=True,hardware_execution=False)
check('bounded_call_quote_and_deployment_cost_distinction',quote)

def fail_closed_budget():
    m=c.Meter(OUT/'fake_full_caps.jsonl',proposal['diagnostic_caps'])
    for key in ['baseline_sampling_calls','D_forward_calls','G0_forward_calls','render_calls','retries','deletions']:
        rejected(lambda key=key:m.call('must_not_enter',lambda:None,{key:1}))
    assert m.used==dict.fromkeys(m.caps,0)
    return dict(zero_caps_refused_before_execution=True)
check('forbidden_extra_work_caps',fail_closed_budget)

def loader_proof():
    s=(PKG/'code/diagnostic.py').read_text();tree=ast.parse(s)
    fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='run')
    start=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Import) and any(a.name=='safetensors.torch' for a in n.names))
    stop=next(i for i,n in enumerate(fn.body[start:],start) if isinstance(n,ast.Expr) and ast.get_source_segment(s,n).startswith('policy.eval()'))
    code=compile(ast.fix_missing_locations(ast.Module(body=fn.body[start+1:stop],type_ignores=[])),'<actual_loader_guard_fake>','exec')
    results=[]
    for mode in ['success','silent_random_return','swallowed_file_error','swallowed_state_error']:
        out=OUT/('loader_'+mode);out.mkdir()
        class StateResult:
            missing_keys=[];unexpected_keys=[]
        class ST:
            @staticmethod
            def load_file(filename):
                if mode=='swallowed_file_error':raise OSError('synthetic load failure')
                return {'a':'fake tensor metadata only'}
        class Policy:
            def load_state_dict(self,state,strict=True):
                if mode=='swallowed_state_error':raise ValueError('synthetic strict mismatch')
                return StateResult()
            @classmethod
            def from_pretrained(cls,path,**kw):
                model=cls()
                if mode!='silent_random_return':
                    try:model.load_state_dict(ST.load_file(path/'model.safetensors'),strict=True)
                    except Exception:pass  # exact failure risk in inherited loader
                return model
        m=c.Meter(out/'events.jsonl',dict(model_initializations=1,policy_model_loads=1,policy_state_file_loads=1,policy_state_dict_loads=1))
        ns=dict(st=ST,PI05Policy=Policy,ckpt=Path('/synthetic/checkpoint'),pc=object(),Path=Path,meter=m,ContractError=c.ContractError,write_new=c.write_new,out=out)
        if mode=='success':exec(code,ns)
        else:rejected(lambda:exec(code,ns))
        results.append(dict(mode=mode,accepted=mode=='success',real_weight_reads=0))
    return results
check('actual_loader_guard_fake_catches_silent_random_fallback',loader_proof)

result=dict(status='passed' if all(r['status']=='passed' for r in rows) else 'failed',tests=rows,
    torch_imports=0,numpy_imports=0,model_calls=0,hardware_calls=0,holder_queries=0,subprocesses=0,dlopen_calls=0,
    blocked_scope_events=BLOCKED,retained_test_root=str(OUT),all_fixtures_synthetic=True,
    actual_tensor_numerics='not executed; requires future compute release')
c.write_new(OUT/'TEST_RESULT.json',result)
print(json.dumps({'status':result['status'],'tests':len(rows),'failed':[r for r in rows if r['status']=='failed'],'result':str(OUT/'TEST_RESULT.json')},indent=2))
sys.exit(0 if result['status']=='passed' else 1)
