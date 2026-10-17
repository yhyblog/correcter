"""Only the new resident episode/controller/metadata boundary, no real Torch."""
import ast
import contextlib
import copy
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import paths
from paths import ROOT
from qio import read,new_json,utc
from admission import validate_job

checks={}
jobs=[read(p) for p in (ROOT/'jobs').glob('*.json')]
for j in jobs:validate_job(j)
assert len(jobs)==250 and sum(len(j['sources']) for j in jobs)==2500
checks['frozen_250_jobs_2500_episodes']=True
for method in ('P','V','R'):
    j=copy.deepcopy(jobs[0]);j['method']=method
    try:validate_job(j)
    except ValueError:pass
    else:raise AssertionError('unimplemented method silently accepted')
checks['unimplemented_method_refused']=True
assert 'torch' not in sys.modules
class Tensor:
    def __init__(self,a):self.a=a
    def __getitem__(self,k):return Tensor(self.a[k])
    def reshape(self,*a):return Tensor(self.a.reshape(*a))
    def float(self):return self
    def cpu(self):return self
    def numpy(self):return self.a
class Generator:
    def __init__(self,**kw):pass
    def manual_seed(self,seed):self.seed=seed
fake=SimpleNamespace(manual_seed=lambda seed:None,Generator=Generator,float32=None,
    inference_mode=contextlib.nullcontext,randn=lambda shape,**kw:Tensor(np.zeros(shape,np.float32)))
sys.modules['torch']=fake
from resident_worker import execute_episode
source=jobs[0]['sources'][0]
root=Path(tempfile.mkdtemp(prefix='corrector_d24_episode_cpu_'))
class Native:
    _did_see_sim_exception=False
    def __init__(self,terminal=None,error=None):self.steps=0;self.frames=[];self.terminal=terminal;self.error=error
    def seed(self,x):self.seed_value=x
    def step(self,action):
        assert action.shape==(4,)
        self.steps+=1;self.frames.append(self.frame_skip)
        if self.steps==self.error:raise ValueError('synthetic physics failure')
        return np.zeros(4),0.,False,False,dict(success=self.steps==self.terminal)
class Env:
    def __init__(self,**kw):self._env=Native(**kw)
    def reset(self,**kw):return self._format_raw_obs(None),{}
    def _format_raw_obs(self,raw):return dict(pixels=np.zeros((480,480,3),np.uint8),agent_pos=np.zeros(4))
state=dict(policy=SimpleNamespace(reset=lambda:None,_preprocess_images=lambda batch:([1,2,3],[[True],[False],[False]])),
    model=SimpleNamespace(sample_actions=lambda *a,**kw:Tensor(np.zeros((1,50,32),np.float32))),
    features=SimpleNamespace(_policy_batch=lambda *a:{'observation.language.tokens':None,'observation.language.attention_mask':None}),
    post=lambda x:x,device='synthetic_CPU')
for name,kw,H in [('success',dict(terminal=3),10),('s300',{},50),('exception',dict(error=2),10)]:
    out=root/name/'episodes'/'source';out.mkdir(parents=True);env=Env(**kw)
    r=execute_episode(state,env,source,H,out,lambda:False)
    if name=='success':assert r['success'] is True and r['steps']==3 and env._env.frames==[13,13,14]
    elif name=='s300':assert r['success'] is False and r['steps']==300 and r['policy_calls']==6 and sum(env._env.frames)==4000
    else:assert r['success'] is None and r['status']=='technical_failure' and 'synthetic physics failure' in r['technical_failure']['traceback']
    checks[name+'_actual_episode_controller_fake_boundary']=True
sys.modules.pop('torch')
from resident_egl import ResidentEGL
from native.native_egl import NativeEGL
obj=object.__new__(ResidentEGL);obj.opened=True;obj.closed=False;obj.context=123
obj.open_context(480,480)
try:obj.open_context(64,64)
except ValueError:pass
else:raise AssertionError('renderer size changed')
checks['resident_context_reuse_size_guard']=True
calls=[]
class Viewer:
    def __init__(self):self.con=SimpleNamespace(free=lambda:calls.append('free'))
rendering=SimpleNamespace(OffScreenViewer=Viewer);obj.viewers=[];obj.journal=SimpleNamespace(call=lambda key,fn,**kw:fn())
obj.install_resident_rendering(rendering);viewer=Viewer();viewer.free();viewer.close()
assert calls==['free']
checks['per_environment_renderer_free_idempotent']=True
for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
checks['all_new_code_AST']=True
assert 'torch' not in sys.modules and 'mujoco' not in sys.modules
checks['no_real_model_or_hardware_import']=True
new_json(ROOT/'evidence/CPU_CHECKS.json',dict(status='PASS',checks=checks,utc=utc(),synthetic_root=str(root),real_models=0,real_environments=0,real_GPU_calls=0,scope='new resident controller and metadata only; prior reservation tests reused'))
print('PASS',len(checks),'targeted CPU checks')
