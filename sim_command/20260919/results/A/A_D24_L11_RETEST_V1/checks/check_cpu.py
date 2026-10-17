"""Narrow real-controller transformation and context-isolation checks, CPU only."""
import ast,copy,hashlib,json,sys,time,collections
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'A_D24_FULL_Q_AUTORUN_POST_LED_V1'
sys.path.insert(0,str(ROOT/'code'))
from qio import new_json,ref,utc
checks=[]
old=ast.parse((OLD/'code/controller.py').read_text())
new=ast.parse((ROOT/'code/controller.py').read_text())
f=next(x for x in old.body if isinstance(x,ast.FunctionDef) and x.name=='run_episode')
g=next(x for x in new.body if isinstance(x,ast.FunctionDef) and x.name=='iter_episode')
restored=copy.deepcopy(g);restored.name=f.name
loop=next(x for x in restored.body if isinstance(x,ast.For))
assert isinstance(loop.body[-1],ast.Expr) and isinstance(loop.body[-1].value,ast.Yield)
loop.body.pop()
assert ast.dump(f,include_attributes=False)==ast.dump(restored,include_attributes=False)
checks.append('generator science AST equals prior controller after removing sole step yield')

def namespace(node):
 ns={'deque':collections.deque,'time':time,'np':np,'seed_for':lambda *a,**k:int(hashlib.sha256(repr(a).encode()).hexdigest()[:12],16)}
 exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(node)],type_ignores=[])),'controller_fixture','exec'),ns)
 return ns[node.name]

run=namespace(f);iterate=namespace(g)
class Env:
 def __init__(self,n):self.n=n;self.t=0;self.actions=[]
 def frame(self):return np.full((2,2,3),self.t,np.uint8)
 def proprio(self):return np.ones(4,dtype=np.float32)*self.t
 def step(self,a,t):
  assert t==self.t;self.actions.append(a.copy());self.t+=1
  return {'reward':float(t),'success':self.t==self.n,'done':False}
class Engine:
 namespace='frozen'
 def language(self):return np.zeros(2,np.float32)
 def start_natural_stream(self,seed):self.rng=np.random.default_rng(seed)
 def propose_natural(self):return self.rng.normal(0,.01,(50,4)).astype(np.float32),{'policy_calls':1,'seconds':0.}
 def context(self,frames,props,past,lang,t):return {'step':t}
 def monitor(self,o,raw):return {'gate':.1}
 def intervene(self,method,o,seed,t):return np.random.default_rng(seed).normal(0,.01,(50,4)).astype(np.float32),{'policy_calls':1 if method=='Post' else 2,'seconds':0.}

for method in ['Post','Velocity']:
 for mode in ['G0-once','G0-multi']:
  for h in [10,30]:
   source={'source_id':'synthetic','policy_seed':32};a=Env(45);b=Env(45)
   expected=run(a,Engine(),source,method,h,lambda *x:None,mode=mode)
   it=iterate(b,Engine(),source,method,h,lambda *x:None,mode=mode)
   try:
    while True:next(it)
   except StopIteration as terminal:actual=terminal.value
   for key in ['success','steps','intervention_cuts','first_cut','last_cut','sampling_calls','flow_calls']:
    assert expected[key]==actual[key],(method,mode,h,key)
   assert np.array_equal(expected['arrays']['actions'],actual['arrays']['actions'])
   checks.append(f'{method}/{mode}/H{h} yields preserve frozen actions and trigger/commit outcomes')
# 24 live generators all advance before any branch completes, with independent
# random streams and environments (the actual worker restores per-context RNG).
contexts=[]
for i in range(24):
 env=Env(45);eng=Engine();src={'source_id':'synthetic'+str(i),'policy_seed':i+1}
 contexts.append((env,iterate(env,eng,src,'Post',10,lambda *x:None,mode='G0-multi')))
for _ in range(6):
 for env,it in contexts:next(it)
assert all(env.t==6 for env,_ in contexts)
assert len({env.actions[0].tobytes() for env,_ in contexts})==24
checks.append('24 actual independent controller contexts advance round-robin; no queued-only concurrency')
units=[json.loads(x) for x in (ROOT/'UNITS.jsonl').read_text().splitlines()]
reused=json.loads((ROOT/'REUSED_UNITS.json').read_text())
assert len(units)==len({u['unit_id'] for u in units})==2900
assert len(reused)==100 and not ({u['unit_id'] for u in units}&{u['unit_id'] for u in reused})
assigned=[]
for method in ['Post','Velocity']:
 for slot in range(8):assigned.extend(json.loads((ROOT/'worker_units'/f'{method}_{slot}.json').read_text()))
assert collections.Counter(u['unit_id'] for u in assigned)==collections.Counter(u['unit_id'] for u in units)
checks.append('2900 exclusive new A units split once;100 exact reused units excluded')
for file in (ROOT/'code').glob('*.py'):ast.parse(file.read_text())
checks.append('private Python entry ASTs parse')
assert not any(k in sys.modules for k in ['torch','mujoco','metaworld'])
new_json(ROOT/'CPU_CHECK.json',dict(utc=utc(),status='PASS',checks=checks,scientific_compute=0,models_imported=False,source=ref(OLD/'code/controller.py'),private=ref(ROOT/'code/controller.py')))
print(json.dumps({'status':'PASS','checks':len(checks),'scientific_compute':0}))
