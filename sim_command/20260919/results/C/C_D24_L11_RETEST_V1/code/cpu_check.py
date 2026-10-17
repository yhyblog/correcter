"""Focused CPU fixtures for cooperative controller state isolation, no GPU."""
import importlib.util,json
import numpy as np
import paths
from paths import ROOT,CAMPAIGN
from qio import read,atomic_json,utc

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Runtime:
    def __init__(self,end):self.t=0;self.end=end
    def frame(self):return np.full((2,2,3),self.t,np.uint8)
    def proprio(self):return np.array([self.t,0,0,1],np.float32)
    def step(self,a,t):
        assert self.t==t;self.t+=1
        return dict(reward=float(a[0]),success=self.t==self.end,done=False)
class Engine:
    namespace='corrector_native10_training_20260916_v1'
    def language(self):return np.zeros(3)
    def start_natural_stream(self,seed):self.rng=np.random.default_rng(seed)
    def propose_natural(self):return self.rng.normal(size=(50,4)).astype(np.float32),dict(policy_calls=1,seconds=0)
    def context(self,f,p,a,l,t):return t
    def monitor(self,o,n):return dict(gate=.1,member_benefits=[.1,.1])
    def intervene(self,m,o,seed,t):return np.random.default_rng(seed).normal(size=(50,4)).astype(np.float32),dict(policy_calls=1 if m=='Post' else 2,seconds=0)
def normalized(value):
    value=dict(value);value.pop('elapsed_control_seconds');a=value.pop('arrays');return value,a
def main():
    old=load(CAMPAIGN/'results/C/C_D24_PI05_SELECTED_H40_H50_V1/code/controller.py','old_controller_fixture')
    new=load(ROOT/'code/controller.py','new_controller_fixture');checks=[]
    for h in [40,50]:
        for method in ['Post','Velocity']:
            expected=[];active=[];actual=[]
            for n,end in enumerate([67,83]):
                source=dict(source_id='CPU_fixture_'+str(n),policy_seed=817+n)
                expected.append(old.run_episode(Runtime(end),Engine(),source,method,h,lambda *_:None,mode='G0-multi'))
                active.append((n,new.run_episode(Runtime(end),Engine(),source,method,h,lambda *_:None,mode='G0-multi')))
                actual.append(None)
            while active:
                for n,g in list(active):
                    try:next(g)
                    except StopIteration as done:actual[n]=done.value;active.remove((n,g))
            for a,b in zip(expected,actual):
                x,ax=normalized(a);y,ay=normalized(b);assert x==y
                assert all(np.array_equal(ax[k],ay[k]) for k in ax)
                cuts=b['intervention_cuts'];assert all(v-u>=10 for u,v in zip(cuts,cuts[1:]));assert b['first_cut']==cuts[0]
            checks.append(f'{method} H{h}: two interleaved independent contexts preserve cuts,C10,plans,actions and call counts')
    units=read(ROOT/'UNIT_INDEX.json');assert len(units)==len({u['unit_id'] for u in units})==2500
    assert all(u['owner']=='C' and u['Q_loss']=='L11' and u['Q_fit_seed']==9101 for u in units)
    cfg=read(ROOT/'config/CONFIG.json');assert [x['method'] for x in cfg['stages']]==['Post','Post','Velocity','Velocity','Velocity']
    assert all(sum(slot%8==gpu for slot in range(24))*8==24 for gpu in range(8))
    for d in ['code','xcode']:
        for p in (ROOT/d).glob('*.py'):compile(p.read_text(),str(p),'exec')
    result=dict(status='passed',utc=utc(),checks=checks+['2500 unique authorized units, no old-result output paths','Post precedes all Velocity','24 workers x8 isolated contexts on8 GPUs','private code syntax'],scope='bounded CPU synthetic controller fixtures; no model, simulator or GPU calls',extra_scientific_units=0,GPU_calls=0,real_GPU_concurrency_verified=False)
    atomic_json(ROOT/'CPU_CHECK.json',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
