"""New H restoration, seed routing and worker handoff only; synthetic CPU."""
import ast
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import paths
from paths import ROOT,CAMPAIGN
from controller import run_episode
from admission import authority,validate_job
from qio import new_json,sha,read

class Runtime:
    def __init__(self,end=None):self.n=0;self.end=end
    def frame(self):return np.asarray([self.n],dtype=np.int64)
    def proprio(self):return np.full(4,self.n,dtype=np.float32)
    def step(self,action,step):
        assert self.n==step;self.n+=1
        return dict(reward=0.,success=self.n==self.end,done=False)
class Engine:
    namespace='corrector_native10_training_20260916_v1'
    def __init__(self,gate=.1):self.gate=gate;self.sample=0
    def language(self):return np.zeros(2)
    def start_natural_stream(self,seed):self.seed=seed;self.sample=0
    def propose_natural(self):
        self.sample+=1;return np.full((50,4),self.sample/100,np.float32),dict(policy_calls=1,seconds=0)
    def context(self,frames,props,past,language,step):
        assert frames[-1][0]==step and len(frames)==min(5,step+1) and len(past)==min(4,step)
        return {'step':step}
    def monitor(self,observed,block):assert block.shape==(5,4);return {'gate':self.gate}
    def intervene(self,method,observed,seed,step):
        return np.full((50,4),-.2,np.float32),dict(policy_calls=2 if method=='Velocity' else 1,seconds=0,seed=seed)

def main():
    checks=[];authority()
    source=read(ROOT/'config/TEST_SOURCES_V1.json')['rows'][0]
    plans={}
    for H in (10,20,30,40,50):
        quiet=run_episode(Runtime(),Engine(.05),source,'Post',H,lambda *_:None)
        assert quiet['interventions']==0 and quiet['sampling_calls']==(300+H-1)//H
        assert [p['step'] for p in quiet['plans']]==list(range(0,300,H))
        for method in ('R','Post','Velocity'):
            row=run_episode(Runtime(),Engine(),source,method,H,lambda *_:None)
            assert row['interventions']==1 and row['first_cut']==5
            natural=[p['step'] for p in row['plans'] if p['kind']=='natural']
            assert natural==[0]+list(range(15,300,H))
            assert all(p['H']==H for p in row['plans'] if p['kind']=='natural')
            assert not any(5<e['step']<15 for e in row['events'])
            assert row['sampling_calls']==len(natural)+(2 if method=='Velocity' else 1)
            assert np.all(row['arrays']['actions'][5:15]==np.float32(-.2))
            assert row['events'][0]['legal_cut'] is False
            early=run_episode(Runtime(8),Engine(),source,method,H,lambda *_:None)
            assert early['success'] and early['steps']==8 and len(early['plans'])==2
            plans[(H,method)]=row['plans'][1]['seed']
    assert len(set(plans.values()))==1
    checks+=['all5 H quiet queues match natural N cadence with strict >.05 gate',
        'all3 methods one true cut5; exactly10 commitment then H restored at15; no monitor during lock',
        'early success in C10 stops immediately; Post1 and Velocity2 generation accounting',
        'candidate seed independent of method/H; one mature past-only frame context']
    jobs=list((ROOT/'jobs').glob('*.json'));assert len(jobs)==550
    for p in jobs:validate_job(read(p))
    assert sha(ROOT/'config/TEST_SOURCES_V1.json')==sha(CAMPAIGN/'deadline_20260924/A/config/TEST_SOURCES_V1.json')
    assert sum(len(read(p)['sources']) for p in jobs)==5500
    checks.append('550 task/H jobs=5500 once episodes use original test-table bytes first10 ordinals only')
    from manager import available_jobs,remaining_unclaimed
    pending=available_jobs();assert len(pending)==150 and all(x[4]['H']==10 for x in pending) and remaining_unclaimed()
    checks.append('first priority group150 task jobs allH10; H30/50 waits for H10 processed')
    from occupancy_adapter import WorkerOccupancy
    import occupancy_adapter as oa
    holder=[]
    fake=SimpleNamespace(formal_exited=lambda *a:holder.append(a),monitor_cached=lambda _:None,devices=[],fill_idle=lambda *a:None)
    w=WorkerOccupancy.__new__(WorkerOccupancy);w.owner={'pid':1,'pgid':1};w.identities={(2,20):(0,{'pid':2,'start_ticks':20})};w.retired=set();w.adapter=fake;w.devices=[{'gpu_uuid':'fake0'}]
    fixture=ROOT/'evidence/holder_family_check_final';fixture.mkdir()
    workers={0:dict(proc=SimpleNamespace(poll=lambda:0,returncode=0),root=fixture)}
    with patch.object(oa,'group_members',return_value=[{'pid':99}]),patch.object(oa,'process_identity',return_value={'pid':99,'ppid':98,'start_ticks':990}),patch.object(oa,'same_process',return_value=False),patch.object(oa,'read',return_value={}):
        w.refresh(workers)
    assert not holder
    with patch.object(oa,'group_members',return_value=[]),patch.object(oa,'same_process',return_value=False),patch.object(oa,'read',return_value={}):w.refresh(workers)
    assert len(holder)==1 and holder[0][2]['cleanup_complete']
    checks.append('real worker-family adapter never marks an orphan/unknown family idle; proven exit only')
    engine=(ROOT/'code/numeric_engine.py').read_text();base=CAMPAIGN/'results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/code/numeric_engine.py'
    old=ast.parse(base.read_text());new=ast.parse(engine)
    oldc=next(n for n in old.body if isinstance(n,ast.ClassDef));newc=next(n for n in new.body if isinstance(n,ast.ClassDef))
    for method in ('intervene','context','monitor','verify'):
        oldf=next(n for n in oldc.body if isinstance(n,ast.FunctionDef) and n.name==method)
        newf=next(n for n in newc.body if isinstance(n,ast.FunctionDef) and n.name==method)
        assert ast.dump(oldf)==ast.dump(newf)
    checks.append('Post/Velocity numeric/solo projection, DG0, history features and frozen checks unchanged AST')
    assert 'torch.Generator(device=self.device)' in engine and 'generator=self.natural_generator' in engine and 'noise=noise' in engine
    manager=(ROOT/'code/manager.py').read_text();assert manager.index('occupancy.before(slot)')<manager.index('proc=subprocess.Popen')
    service=(ROOT/'code/service.py').read_text();assert service.index('auxiliary=stop_tree')<service.index('os.close(fd)')
    for f in (ROOT/'code').glob('*.py'):ast.parse(f.read_text())
    assert not any(x in sys.modules for x in ('torch','mujoco','pynvml','OpenGL.EGL'))
    checks.append('per-worker ACK before Popen; auxiliary drain before sameFD release; valid AST no model/hardware imports')
    new_json(ROOT/'evidence/CPU_CHECK.json',dict(status='PASS',checks=checks,count=len(checks),synthetic=True,real_model_environment_hardware_calls=0))
    print(json.dumps(dict(status='PASS',checks=len(checks))))
if __name__=='__main__':main()
