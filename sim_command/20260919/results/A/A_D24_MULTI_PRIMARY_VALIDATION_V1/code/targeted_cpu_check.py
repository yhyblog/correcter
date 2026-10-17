"""Changed controller/real recorder/serializer composition; no real model/env."""
import ast
import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path
import numpy as np
import paths
from paths import ROOT
from qio import read,new_json,utc
from controller import run_episode,random_coin
from e6_controller import run_episode as run_e6
from recorder import record
from admission import frozen_jobs,validate_job
from publication_data import finite_values,merge_event,EvidenceConflict

class Runtime:
    def frame(self):return np.zeros((3,3,3),np.uint8)
    def proprio(self):return np.zeros(4,np.float32)
    def step(self,action,t):return dict(reward=0.,success=False,done=t==74)

class Engine:
    namespace='corrector_native10_training_20260916_v1'
    cfg={'e6_threshold':.2521600950570383}
    feature_scale=np.ones((2,4),np.float32)
    def __init__(self):self.seeds=[];self.monitors=[]
    def language(self):return None
    def start_natural_stream(self,seed):self.natural_seed=seed
    def propose_natural(self):return np.zeros((50,4),np.float32),dict(policy_calls=1,seconds=0.)
    def context(self,frames,props,actions,language,t):self.monitors.append(t);return {'step':t}
    def monitor(self,obs,next_five):return dict(gate=.2,member_benefits={})
    def actual_features(self,obs):return np.ones((5,4),np.float32)
    def forecast(self,obs,next_five):return dict(prediction=np.zeros((2,5,4),np.float32),gate=.2,member_benefits={})
    def intervene(self,method,obs,seed,t):self.seeds.append((method,seed,t));return np.ones((50,4),np.float32)*.1,dict(policy_calls=2 if method=='Velocity' else 1,seconds=0.)

def main():
    checked=[];source={'source_id':'CPU_synthetic_only','policy_seed':20260922}
    with tempfile.TemporaryDirectory(prefix='corrector_multi_cpu_') as temp:
        folder=Path(temp)
        def run(name,fn,method,mode=None):
            engine=Engine();path=folder/(name+'.jsonl');owned=dict(source_id=source['source_id'],task='synthetic',cell_id=name,H=10,branch=method)
            if mode:owned['mode']=mode
            kwargs={'mode':mode} if mode else {}
            row=fn(Runtime(),engine,source,method,10,lambda kind,event:record(path,owned,kind,event),**kwargs)
            row.pop('arrays');new_json(folder/(name+'.json'),row);saved=read(folder/(name+'.json'))
            lines=[json.loads(x) for x in path.read_text().splitlines()]
            assert all(x['source_id']==source['source_id'] for x in lines)
            cuts=saved['intervention_cuts'];assert saved['first_cut']==cuts[0] and saved['last_cut']==cuts[-1] and len(cuts)>=2
            assert all(b-a>=10 for a,b in zip(cuts,cuts[1:]));assert len(cuts)==len(set(cuts))
            for event in saved['events']:
                if event['intervention_executed'] and event['step']+10<75:assert event['C10_complete'] and event['C10_steps_executed']==10 and event['native_H_restored']
                if mode=='Random-multi':assert (event['random_coin'] is not None)==event['legal_cut']
            checked.append(dict(case=name,cuts=cuts,serialized_events=len(lines),real_controller=True,real_recorder=True));return engine,saved
        outputs=[run('Random_'+m,run_episode,m,'Random-multi') for m in ['R','Post','Velocity']]
        assert all([t[1:] for t in outputs[0][0].seeds]==[t[1:] for t in engine.seeds] for engine,_ in outputs)
        run('G0',run_episode,'Velocity','G0-multi')
        run('E6_G0',run_e6,'G0');run('E6_D5',run_e6,'D5')
        try:record(folder/'conflict.jsonl',{'source_id':'A'},'monitor',{'source_id':'B'})
        except ValueError:checked.append({'case':'identity_conflict_rejected'})
        else:raise AssertionError('reserved identity accepted')
        assert finite_values({'x':math.inf})['x'] is None
    cfg=read(ROOT/'config/CONFIG.json');jobs=frozen_jobs();n=0
    # Only new identity/path combinations, no old 133/185 fixtures.
    for meta in jobs.values():
        job=read(meta['path']);validate_job(job);n+=len(job['sources'])
    assert n==8800 and len(cfg['cells'])==41 and cfg['max_interventions'] is None
    e1=[c for c in cfg['cells'] if c['stage']=='E1'];weights=set()
    for cell in e1:
        c=read(cell['numeric_config']);assert len(c['sources'])==50 and {s['ordinal'] for s in c['sources']}==set(range(10))
        weights.update(m['checkpoint'] for m in c['selected_model']['ensemble']['members'])
    assert len(weights)==48
    for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    assert 'torch' not in sys.modules and 'mujoco' not in sys.modules
    new_json(ROOT/'cpu_checks/TARGETED_RESULT.json',dict(status='passed',utc=utc(),checks=checked,planned_first_evaluations=n,E1_unique_checkpoints=len(weights),real_models=0,real_environments=0,hardware_calls=0,large_model_hashes=0,scientific_compute=0))
    print('PASS',len(checked),'controller/recorder cases;8800 source identities;48 existing weights')

if __name__=='__main__':main()
