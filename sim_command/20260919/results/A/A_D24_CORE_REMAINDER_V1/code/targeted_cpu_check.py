"""Only new causal/controller/metadata seams. No Torch or hardware imports."""
import ast,json,sys
from pathlib import Path
import numpy as np
import paths
from paths import ROOT
from controller import run_episode
from b10_adapters import CausalD5Monitor,ContractError,select_development_threshold
from admission import validate_job,authority,resource_admission
from qio import new_json,utc

class Runtime:
 def __init__(self):self.t=0
 def frame(self):return np.array([self.t],np.float32)
 def proprio(self):return np.zeros(4,np.float32)
 def step(self,action,t):
  assert t==self.t;self.t+=1
  return dict(reward=0.,success=False,done=self.t==26)
class Engine:
 namespace='corrector_native10_training_20260916_v1'
 cfg={'e6_threshold':.1}
 feature_scale=np.array([[1.]*4096,[2.]*4096])
 def __init__(self):self.calls=0
 def language(self):return np.zeros(2048,np.float32)
 def start_natural_stream(self,s):pass
 def propose_natural(self):return np.zeros((50,4),np.float32),dict(policy_calls=1,seconds=0.)
 def context(self,f,p,a,l,t):
  hist=np.zeros((5,4096),np.float32)
  for i,frame in enumerate(f):hist[-len(f)+i]=frame[0]
  return dict(history=hist,step=t)
 def actual_features(self,o):return o['history']
 def forecast(self,o,a):
  pred=np.stack([np.full((4096,),o['step']+i+1+.5) for i in range(5)])
  return dict(prediction=np.stack([pred,pred]),gate=.06,member_benefits={'241':.06,'242':.06})
 def intervene(self,m,o,seed,t):
  assert m=='R';self.calls+=1
  return self.propose_natural()
checks=[]
source={'source_id':'synthetic_e6_only','policy_seed':42}
for method in ['DEV','G0','D5']:
 engine=Engine();events=[]
 def emit(k,e):json.dumps(e,allow_nan=False);events.append((k,e))
 row=run_episode(Runtime(),engine,source,method,10,emit)
 assert row['steps']==26 and row['causal_D5_action_alignment_verified']
 assert row['interventions']==(0 if method=='DEV' else 1)
 assert row['g0_intervened']
 assert all(abs(s-.15625)<1e-10 for s in row['eligible_scores'])
 if method!='DEV':assert row['first_cut']==5 and engine.calls==1
 checks.append(method+'_real_controller_real_causal_monitor')
monitor=CausalD5Monitor(.1,np.ones((2,4096)),'one')
monitor.register(issued_step=0,predicted_features=np.zeros((2,5,4096)),conditioned_raw_actions=np.zeros((5,4)))
try:monitor.observe(issued_step=0,observed_step=5,actual_features=np.zeros((5,4096)),executed_raw_actions=np.ones((5,4)),episode_id='one',plan_age=5,remaining_queue=5)
except ContractError:checks.append('actual_action_mismatch_rejected')
else:raise AssertionError('action mismatch accepted')
tr=[dict(parent_episode_id=str(i),split='development',eligible_scores=[] if i==0 else [float(i)],g0_intervened=i>=3) for i in range(5)]
x=select_development_threshold(tr)
assert x['development_episodes']==5 and x['achieved_anomaly_interventions']==2 and not x['selection_uses_success']
checks.append('no_alarm_dev_retained_and_label_free_calibration')
for p in (ROOT/'jobs').glob('*.json'):validate_job(json.loads(p.read_text()))
for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
s=(ROOT/'code/manager.py').read_text();assert 'occupancy_adapter' not in s and '.fill_idle(' not in s
s=(ROOT/'code/service.py').read_text();assert 'stop_tree(' not in s and 'records=[],utc=utc(),auxiliary_holder_launches=0' in s
assert 'torch' not in sys.modules
checks.extend(['40_fixed_source_job_metadata','local_changed_AST','no_auxiliary_holder_entry','no_torch_import'])
authority();resource=resource_admission()
new_json(ROOT/'CPU_CHECK.json',dict(status='PASS',utc=utc(),checks=checks,resource_admission=resource,scientific_compute=0))
print(json.dumps({'status':'PASS','checks':len(checks),'available_GiB':resource['filesystem_available_bytes']/1024**3}))
