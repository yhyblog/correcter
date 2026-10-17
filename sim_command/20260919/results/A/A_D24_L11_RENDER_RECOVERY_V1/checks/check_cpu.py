"""Narrow real controller/proxy/dispatcher/runtime checks. Synthetic; no torch or GPU."""
import ast,copy,hashlib,json,sys,threading,concurrent.futures
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code'))
import paths
import pi_client
from pi_client import EngineProxy,Runtime
from rpc_state import EngineSessions
from controller import run_episode
from admission import frozen_units,authority

checks=[]
def ok(name):checks.append(name)

# Original controller equations/order are unchanged; only the old A yield is removed.
old=ROOT.parent/'A_D24_L11_RETEST_V1/code/controller.py'
tree=ast.parse(old.read_text());f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='iter_episode');f.name='run_episode'
loop=next(n for n in f.body if isinstance(n,ast.For));assert isinstance(loop.body[-1],ast.Expr) and isinstance(loop.body[-1].value,ast.Yield);loop.body.pop()
assert ast.dump(tree,include_attributes=False)==ast.dump(ast.parse((ROOT/'code/controller.py').read_text()),include_attributes=False)
ok('real_controller_AST_equal_old_A_without_cooperative_yield')
assert (ROOT/'code/numeric_engine.py').read_bytes()==(ROOT.parent/'A_D24_L11_RETEST_V1/code/numeric_engine.py').read_bytes()
ok('numerical_engine_byte_identical')
units=frozen_units();reuse=json.loads((ROOT/'REUSED_UNITS.json').read_text())
assert len(units)==1900 and not set(units)&{x['unit_id'] for x in reuse}
assert Counter((u['method'],u['mode'],u['H']) for u in units.values())==Counter({('Post','G0-multi',10):450,('Post','G0-once',10):500,('Velocity','G0-multi',10):450,('Velocity','G0-once',10):500})
ok('1900_exact_recovery_keys_H10_only_and100_valid_excluded')
authority();ok('current_small_authorization_identity')
for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text())
ok('all_changed_private_python_parses')

class FakeNative:
    def __init__(self,n):self.n=n;self.data=SimpleNamespace(time=0.);self.frame_skip=5;self._did_see_sim_exception=False;self.steps=0
    def step(self,action):
        self.data.time+=self.frame_skip/400;self.steps+=1
        return None,float(action.sum()),self.steps==23,False,{'success':False}
class FakeEnv:
    def __init__(self,n):self._env=FakeNative(n)
    def _format_raw_obs(self,obs):
        f=np.full((480,480,3),self._env.n+1,dtype=np.uint8);f[0,0,0]=self._env.steps%255
        return {'pixels':f,'agent_pos':np.array([self._env.n,self._env.steps,0,1],np.float32)}
class FakeEngine:
    def __init__(self,meter):self.counts=dict(sampling=0,contexts=0,interventions=0);self.features=SimpleNamespace(_instruction=None);self.meter=meter
    def language(self):return np.array([int(self.instruction)],np.float32)
    def start_natural_stream(self,seed):self.natural_seed=seed;self.natural_generator=np.random.default_rng(seed)
    def propose_natural(self):
        self.counts['sampling']+=1;self.meter.entered['sampling']+=1
        return self.natural_generator.uniform(-.1,.1,(50,4)).astype(np.float32),{'policy_calls':1,'seconds':0.}
    def context(self,frames,props,past,language,step):
        self.counts['contexts']+=1;self.meter.entered['contexts']+=1
        assert int(language[0])==int(self.instruction)==int(props[-1][0]);return {'owner':self.instruction,'step':step}
    def monitor(self,ctx,commands):
        assert ctx['owner']==self.instruction;return {'gate':.1}
    def intervene(self,method,ctx,seed,step):
        assert ctx['owner']==self.instruction and ctx['step']==step;self.counts['interventions']+=1
        return np.random.default_rng(seed).uniform(-.1,.1,(50,4)).astype(np.float32),{'policy_calls':1 if method=='Post' else 2,'seconds':0.}
    def verify(self):pass

test_units={}
for n in range(24):
    test_units[str(n)]={'unit_id':str(n),'uid_hash':'fake_'+str(n),'source_id':'synthetic_'+str(n),'source':{'instruction':str(n)},'policy_seed':100+n,'method':'Post' if n%2==0 else 'Velocity'}
meter=SimpleNamespace(entered=Counter());engine=FakeEngine(meter);audits=[];sessions=EngineSessions(engine,meter,test_units,ROOT/'checks/fake_no_science',audits.append);lock=threading.Lock()
class Connection:
    def send(self,req):
        with lock:
            try:self.reply=dict(ok=True,**sessions.handle(copy.deepcopy(req)))
            except Exception as e:self.reply=dict(ok=False,error=str(e))
    def poll(self,seconds):return True
    def recv(self):return self.reply
pi_client.Client=lambda *a,**k:Connection()
pi_client.check_render_log=lambda *a:None
pi_client.boundary=lambda *a:None
pi_client.before_cutoff=lambda:True

def run(n):
    u=test_units[str(n)];env=FakeEnv(n);seen=[];runtime=Runtime(env,env._format_raw_obs(None),lambda step,obs:seen.append(step),ROOT/'checks')
    proxy=EngineProxy({'branch_id':str(n),'socket_path':'synthetic','ipc_auth':'00'});proxy.begin(u,runtime,ROOT/'checks/fake_no_science/episodes'/u['uid_hash'],{})
    row=run_episode(runtime,proxy,u,u['method'],10,lambda *a:None,mode='G0-once' if n%3==0 else 'G0-multi')
    snap=proxy.rpc('snapshot');return row,snap,seen
with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:parallel=list(pool.map(run,range(24)))
assert all(row['steps']==23 and len(seen)==24 and snap['numeric']['contexts']>0 for row,snap,seen in parallel)
ok('24_real_controller_Runtime_proxy_dispatcher_fake_env_branches_interleaved')
serial=[run(n) for n in range(24)]
for (a,ma,sa),(b,mb,sb) in zip(parallel,serial):
    assert np.array_equal(a['arrays']['actions'],b['arrays']['actions']) and a['intervention_cuts']==b['intervention_cuts'] and ma['counts']==mb['counts']
ok('per_branch_stream_observation_context_counts_match_serial_synthetic')
req={'branch_id':'0','unit_id':'1','client_pid':0,'source_id':'synthetic_1','kind':'snapshot','observation_step':0}
try:sessions.handle(req);raise AssertionError('cross source accepted')
except ValueError:ok('cross_source_context_rejected')
req={'branch_id':'0','unit_id':'0','client_pid':__import__('os').getpid(),'source_id':'synthetic_0','kind':'monitor','observation_step':299,'context_id':299,'next_five':np.zeros((5,4),np.float32)}
try:sessions.handle(req);raise AssertionError('stale context accepted')
except ValueError:ok('stale_context_step_rejected')
assert 'multiple live environment renderers in one EGL process are forbidden' in (ROOT/'code/resident_egl.py').read_text()
assert 'torch' not in sys.modules and 'mujoco' not in sys.modules
ok('single_live_renderer_guard_and_no_model_hardware_imports')
print(json.dumps({'status':'PASS','synthetic':True,'scientific_compute':0,'checks':checks,'number':len(checks)},indent=2))
