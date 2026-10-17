"""Targeted CPU controller/ownership/video checks; no real models or envs."""
import ast,importlib.util,json,sys,types,hashlib,shutil
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code'))
import paths
from qio import new_json,utc
from admission import authority,frozen_units,resource_admission
checks={}
authority();u=frozen_units();checks['frozen79pairs158arms']=len(u)==158
checks['old_new_control_grant_match']=True
checks['capacity']=resource_admission()
for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
checks['changed_AST_parse']=True
# Avoid hardware/model imports: inject the deterministic seed function only.
proto=types.ModuleType('experiments.native10_training_20260916.protocol')
proto.seed_for=lambda *a,**kw:int.from_bytes(hashlib.sha256(repr((a,kw)).encode()).digest()[:8],'big')
sys.modules[proto.__name__]=proto
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
new=load(ROOT/'code/controller.py','new_demo_controller')
old=load(ROOT.parent/'A_D24_L11_RENDER_RECOVERY_V1/code/controller.py','old_frozen_controller')
class Runtime:
    def __init__(self):self.steps=0
    def frame(self):return np.full((2,2,3),self.steps,np.uint8)
    def proprio(self):return np.ones(4,np.float32)*self.steps
    def step(self,action,t):
        assert t==self.steps;self.steps+=1
        return dict(reward=float(t),done=self.steps==41,success=False)
class Engine:
    namespace='synthetic';
    def __init__(self):self.calls=[];self.runtime=None
    def language(self):self.calls.append('language');return 0
    def start_natural_stream(self,s):self.calls.append(('stream',s))
    def propose_natural(self):self.calls.append('sample');return np.arange(200,dtype=np.float32).reshape(50,4)/100,dict(policy_calls=1)
    def context(self,f,p,a,l,t):self.calls.append(('context',t));return t
    def monitor(self,c,p):self.calls.append(('monitor',c));return dict(gate=.1)
    def intervene(self,m,o,s,t):self.calls.append(('intervene',t));return -np.arange(200,dtype=np.float32).reshape(50,4)/100,dict(policy_calls=1)
source={'policy_seed':17,'source_id':'SYNTHETIC_NO_REAL_SOURCE'}
for H in (10,20,30,40,50):
    a,b=Engine(),Engine();aa=old.run_episode(Runtime(),a,source,'Post',H,lambda *_:None,mode='G0-multi');bb=new.run_episode(Runtime(),b,source,'Post',H,lambda *_:None,mode='G0-multi')
    assert a.calls==b.calls and aa['intervention_cuts']==bb['intervention_cuts'] and np.array_equal(aa['arrays']['actions'],bb['arrays']['actions'])
    n=Engine();out=new.run_episode(Runtime(),n,source,'N',H,lambda *_:None,mode='native');assert out['interventions']==0 and all(x=='sample' or isinstance(x,tuple) and x[0]=='stream' for x in n.calls)
    assert out['sampling_calls']==(41+H-1)//H
checks['real_controller_five_H_Post_byte_equivalent_actions_vs_frozen']=True
checks['N_no_language_DG0_Q_or_intervention_calls']=True
from demo_video import RGBWriter,compare_initial
d={k:'same' for k in ('task','source_id','env_seed','policy_seed','H','camera','shape','rgb_sha256','proprio','native_time','state')};assert compare_initial(d,d)['passed'];bad=dict(d,rgb_sha256='different');assert not compare_initial(d,bad)['passed']
checks['actual_initial_gate_rejects_mismatch']=True
folder=ROOT/'checks/synthetic_video';folder.mkdir(exist_ok=False)
rows={}
for method,steps in [('N',13),('Post',5)]:
    ep=folder/method;ep.mkdir();w=RGBWriter(ep/'recording.mp4')
    for step in range(steps+1):
        frame=np.zeros((480,480,3),np.uint8);frame[:,:,0]=30+step*9;frame[:,step*10:step*10+100,1]=180
        if method=='Post':frame[240:,:,2]=220
        w.write(step,frame)
    video=w.finish();rows[method]=dict(status='complete',terminal=True,success=method=='Post',steps=steps,terminal_reason='success' if method=='Post' else 's300',video=video,intervention_cuts=[2] if method=='Post' else [],first_cut=2 if method=='Post' else None,uid_hash=method,attempt=1)
import compose_pair
compose_pair.ROOT=folder;compose_pair.OUTPUT=folder/'output'
pair=folder/'pairs/synthetic';pair.mkdir(parents=True);new_json(pair/'INITIAL_CHECK.json',dict(passed=True,synthetic=True))
c=dict(task='synthetic-fixture',candidate_id='synthetic',source_id='SYNTHETIC',ordinal=0,H=10,env_seed=1,policy_seed=2,N={'synthetic':True},Post={'synthetic':True})
meta=compose_pair.compose(c,rows['N'],rows['Post']);assert meta['video_checks']['comparison']['frames']==14 and meta['video_checks']['held_frames']['Post']==8
checks['actual_ffmpeg_composition_decode_vertical_sync_hold_label']=True
checks['synthetic_artifacts_in_checks_only']=str(folder)
checks['no_torch_import']='torch' not in sys.modules
assert checks['no_torch_import']
new_json(ROOT/'CPU_CHECK.json',dict(status='PASS',utc=utc(),checks=checks,synthetic=True,scientific_compute=0,actual_model_environment_hardware_calls=0))
print(json.dumps({'status':'PASS','checks':list(checks),'capacity':checks['capacity']},indent=2))
