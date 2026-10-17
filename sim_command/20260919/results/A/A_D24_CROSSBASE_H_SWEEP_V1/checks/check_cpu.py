"""Targeted actual queue/client fixture; fake model/environment, no hardware imports."""
import ast,contextlib,hashlib,json,sys,tempfile,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
import numpy as np
from queue_protocol import NativeQueue
from qio import read,new_json,utc
checks=[]
def ok(name):checks.append(name)
for H in (20,30):
    q=NativeQueue(H,'N');refills=[]
    for t in range(90):
        if q.needs_refill():refills.append(t);q.refill(np.zeros((50,4),np.float32))
        assert not q.monitor_due(t);q.action()
    assert refills==list(range(0,90,H))
    for method in ('R','Post','Velocity'):
        q=NativeQueue(H,method);q.refill(np.zeros((50,4),np.float32))
        for _ in range(5):q.action()
        assert q.legal_cut(5,5,5)
        candidate=np.arange(200,dtype=np.float32).reshape(50,4);q.commit(candidate,5)
        for t in range(5,15):
            assert not q.monitor_due(t)
            assert np.array_equal(q.action(),candidate[t-5])
        assert q.needs_refill()
        q.refill(np.ones((50,4),np.float32))
        assert q.limit==H and q.age==0 and q.tail_discards==q.restorations==1
        assert not q.legal_cut(15,5,15)
        for _ in range(5):q.action()
        assert q.legal_cut(20,5,20)
ok('actual NativeQueue: normal H20/30 refills, C10 lock, raw tail discard, restore H, next legal cut')
for value in (True,0,51):
    try:NativeQueue(value,'N');raise AssertionError('bad H accepted')
    except ValueError:pass
ok('normal H bounds and strict integer check')

# Exercise the actual native_client.main and real serialization with fake imports.
fake_torch=types.ModuleType('torch');fake_torch.set_num_threads=lambda n:None;sys.modules['torch']=fake_torch
mw=types.ModuleType('lerobot.envs.metaworld')
class Env:
    def __init__(self,task,obs_type):
        self.task_description='fixture '+task;self.t=0
        self._env=types.SimpleNamespace(seed=lambda seed:None,model=types.SimpleNamespace(opt=types.SimpleNamespace(timestep=.0025)),frame_skip=5,action_scale=.01,_last_rand_vec=np.zeros(3))
    def obs(self):return {'pixels':np.ones((480,480,3),np.uint8),'agent_pos':np.zeros(4,np.float32)}
    def reset(self,seed):self.t=0;return self.obs(),{}
    def step(self,action):self.t+=1;return self.obs(),0.,False,self.t==60,{'success':False}
    def close(self):pass
mw.MetaworldEnv=Env;sys.modules['lerobot.envs.metaworld']=mw
candidates=types.ModuleType('experiments.standalone_ablation_20260918.candidates')
candidates.project_solo=lambda a,d,m:(a.copy(),{'synthetic':True},{'actual_delta':np.zeros((10,4))})
sys.modules[candidates.__name__]=candidates
protocol=types.ModuleType('experiments.native10_training_20260916.protocol')
protocol.seed_for=lambda *args,**kw:12345
sys.modules[protocol.__name__]=protocol
import native_client
native_client.boundary=lambda *a,**kw:None
native_client.episode_deadline=contextlib.nullcontext
native_client.claim_unit=lambda u:dict(unit_id=u['unit_id'],synthetic=True)
class Connection:
    def __init__(self,gate):self.calls=[];self.gate=gate;self.counters={};self.pending={};self.request={}
    def send(self,req):
        self.calls.append(dict(req,observations=None,observation=None));self.request=req;k=req['kind']
        def count(name,n=1):self.counters[name]=self.counters.get(name,0)+n
        if k=='policy_info':reply={'native_action_slopes':np.ones((10,4))}
        elif k=='begin':self.counters={};reply={'counters':{}}
        elif k=='monitor':count('monitor_calls');reply={'gate':self.gate,'member_gates':[self.gate,self.gate]}
        elif k=='generate':reply={'raw':np.zeros((50,4),np.float32),'stats':{'flow_calls':10,'noise_sha256':'synthetic_same_noise'},'policy_seconds':0.}
        elif k=='gradient':count('Q_ensemble_forward_calls');count('action_gradient_calls');reply={'gradient':np.ones((10,4)), 'value':0.}
        elif k=='snapshot':reply={'counters':dict(self.counters)}
        else:reply={}
        self.pending=dict(ok=True,seconds=0.,**reply)
    def poll(self,*a):return True
    def recv(self):return self.pending
    def close(self):pass
for H in (20,30):
    for method in ('N','R','Post','Velocity'):
        for gate in (0.,1.):
            name=f'{method}_{H}_{int(gate)}';out=ROOT/'checks'/'synthetic'/name;out.mkdir(parents=True,exist_ok=False)
            native_client.ROOT=out;conn=Connection(gate);native_client.Client=lambda *a,**kw:conn
            u=dict(unit_id=name,source_id='synthetic_source',method=method,H=H,mode='native' if method=='N' else 'G0-multi',C=None if method=='N' else 10,Q_loss='L11' if method in ('Post','Velocity') else None,Q_fit_seed=9101 if method in ('Post','Velocity') else None,current_paper=method!='Velocity',missing_reasons={'repeat':'fixture has no repeat'},native_source_record=dict(source_id='synthetic_source',task='synthetic-task',reset_seed=1,policy_seed=2))
            cfg=dict(output=str(out),phase='evaluate',socket_path='fake',ipc_auth='aa',branch_id=name,slot=0,normal_H=H,methods=[method],engine_config=str(ROOT/'config/ENGINE_CONFIG.json'),construction_seed_by_task={'synthetic-task':1},units=[u],seed_namespace='corrector_native10_training_20260916_v1')
            p=out/'CONFIG.json';new_json(p,cfg);native_client.main(p)
            row=read(out/'episodes'/hashlib.sha256(name.encode()).hexdigest()/'RESULT.json')
            assert row['status']=='complete' and row['success'] is False and row['H']==H
            kinds=[q['kind'] for q in conn.calls]
            if method=='N':
                assert not set(kinds)&{'begin','monitor','objective','gradient','snapshot','policy_info'}
                assert row['interventions']==0 and row['counters']['policy_queries']==(60+H-1)//H
            elif method=='R':assert 'objective' not in kinds and 'gradient' not in kinds
            if gate==1 and method!='N':
                assert row['interventions']==4 and row['first_cut']==5
                cuts=[e['step'] for e in row['events'] if e['trigger']];assert cuts==[5,20,35,50]
                assert all(e['restore_normal_H']==H and e['commit_until']==e['step']+10 for e in row['events'] if e['trigger'])
            if gate==0:assert row['interventions']==0
ok('actual native_client with fake RPC/environment: 16 combinations, N no auxiliary calls, R no Q, immutable results and multi first_cut')
for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
source=(ROOT/'code/native_client.py').read_text()
assert 'age==10' not in source and 'min(10-age' not in source
assert 'queue.monitor_due(t)' in source and 'queue.commit(raw,t)' in source and 'queue.action()' in source
ok('real caller wired to actual H/C state; no hardcoded normal age10')
old=ROOT.parents[2]/'results/B/B_D24_L11_RETEST_V1/code/native_velocity.py'
assert old.read_bytes()==(ROOT/'code/native_velocity.py').read_bytes()
ok('native Velocity integration unchanged byte-for-byte')
import admission
units=admission.frozen_units();assert len({u['unit_id'] for u in units.values()})==4000
assert len({(u['source_id'],u['H'],u['method']) for u in units.values()})==4000
assert all(u['H'] in (20,30) for u in units.values())
ok('4000 exact identities include H/method; no H10 or non-owned source')
new_json(ROOT/'CPU_CHECK.json',dict(status='PASS',utc=utc(),checks=checks,synthetic=True,actual_scientific_compute=0,hardware_imports=0,formal_claims=0,note='Fake numerical responses test only unchanged caller wiring and queue semantics; they are not a numerical/model validation.'))
print(json.dumps({'status':'PASS','checks':checks}))
