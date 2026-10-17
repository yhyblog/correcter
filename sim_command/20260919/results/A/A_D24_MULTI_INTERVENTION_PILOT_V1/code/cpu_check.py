"""Only new real-controller integration checks, with fake numerical/physics endpoints."""
import ast
import json
from pathlib import Path
import tempfile
import numpy as np
import paths
from paths import ROOT
from controller import run_episode
from admission import validate_job
from qio import new_json

class Runtime:
    def __init__(self,success_at=None):self.n=0;self.success_at=success_at
    def frame(self):return np.array([self.n],dtype=np.uint8)
    def proprio(self):return np.full(4,self.n,dtype=np.float32)
    def step(self,action,step):
        assert step==self.n;self.n+=1
        return dict(reward=0.,success=self.n==self.success_at,done=False)

class Engine:
    namespace='corrector_native10_training_20260916_v1'
    def __init__(self,gate=.1):self.gate=gate
    def language(self):return np.zeros(2)
    def propose(self,seed):return np.zeros((50,4),np.float32),dict(policy_calls=1,seed=seed)
    def context(self,frames,props,past,language,step):
        assert int(frames[-1][0])==step%256
        assert len(frames)==min(5,step+1) and len(past)==min(4,step)
        return dict(step=step)
    def monitor(self,observed,block):assert block.shape==(5,4);return dict(gate=self.gate)
    def intervene(self,method,observed,seed,step):
        raw,stats=self.propose(seed);return raw,dict(stats,method=method,policy_calls=2 if method=='Velocity' else 1)

def main():
    source=json.loads((ROOT/'config/SOURCES.json').read_text())['sources'][0];checks=[]
    with tempfile.TemporaryDirectory(prefix='corrector_pilot_cpu_',dir='/tmp') as td:
        def emit(kind,event):
            if kind=='monitor':new_json(Path(td)/('e'+str(len(list(Path(td).glob('*.json'))))+'.json'),event)
        once=run_episode(Runtime(),Engine(),source,'R_once',emit)
        multi=run_episode(Runtime(),Engine(),source,'R_multi',emit)
        assert once['interventions']==1 and multi['interventions']==20
        assert [x['step'] for x in multi['events'] if x['intervention_executed']]==list(range(5,291,15))
        checks.append('once=1 vs multi=20; legal age5; exact C10 lock and no added cooldown')
        assert all(not x['intervention_executed'] or (x['history_mature'] and x['true_G0_trigger'] and not x['forced_intervention']) for x in multi['events'])
        assert not once['events'][0]['history_mature'] and not once['events'][0]['legal_cut']
        checks.append('history maturity, true trigger, t0 exclusion, real JSON serialization')
        assert multi['plans'][0]['seed']==once['plans'][0]['seed']
        assert multi['plans'][1]['seed']==once['plans'][1]['seed']
        checks.append('arm-independent first natural and candidate repeat0 seed')
        for arm in ('R_multi','Post_multi','Velocity_multi'):
            early=run_episode(Runtime(8),Engine(),source,arm,lambda *_:None)
            assert early['steps']==8 and early['interventions']==1 and early['success']
        checks.append('success inside commitment stops immediately for R/Post/Velocity')
        quiet=run_episode(Runtime(),Engine(.05),source,'Post_multi',lambda *_:None)
        assert quiet['interventions']==0 and quiet['sampling_calls']==30 and quiet['steps']==300
        checks.append('strict threshold and no forced trigger; s300 finite natural H10')
        for path in (ROOT/'jobs').glob('*.json'):validate_job(json.loads(path.read_text()))
        checks.append('all120 fixed old20/repeat0 job identities')
        for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text())
        import sys
        assert not any(x in sys.modules for x in ('torch','mujoco','pynvml','OpenGL.EGL'))
        checks.append('isolated code AST parse; Torch/environment/hardware not imported')
    out=dict(status='PASS',checks=checks,count=len(checks),synthetic=True,model_hardware_environment_calls=0)
    new_json(ROOT/'evidence/CPU_CHECK.json',out);print(json.dumps(out))

if __name__=='__main__':main()
