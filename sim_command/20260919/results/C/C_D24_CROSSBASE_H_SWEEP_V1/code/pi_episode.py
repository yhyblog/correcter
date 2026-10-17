"""One permanently resident policy; finite sequential task/H jobs on one UUID."""
import argparse
import copy
import json
import os
import signal
import sys
import time
import traceback
from collections import Counter
import paths
from paths import ROOT,ACCEPTED
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,before_cutoff,validate_job,admit_episode,admissions_allowed,AdmissionClosed


class Counts:
    def __init__(self):self.entered=Counter();self.returned=Counter();self.seconds=Counter();self.failed=[]
    def call(self,name,fn,units=None,detail=None):
        units=units or {};self.entered.update(units);t=time.monotonic()
        try:
            value=fn();self.returned.update(units);return value
        except BaseException as e:
            self.failed.append(dict(name=name,type=type(e).__name__,message=str(e)));raise
        finally:self.seconds[name]+=time.monotonic()-t
    def snapshot(self):return dict(entered=dict(self.entered),returned=dict(self.returned),seconds=dict(self.seconds),failed=list(self.failed))


class Runtime:
    def __init__(self,env,observation):self.env=env;self.observation=observation;self.steps=0;self.seconds=0.
    def frame(self):return self.observation['pixels']
    def proprio(self):
        import numpy as np
        return np.asarray(self.observation['agent_pos'],np.float32)
    def step(self,action,step):
        import numpy as np
        if step!=self.steps:raise ValueError('physical step clock')
        native=self.env._env;native.frame_skip=((step+1)*400)//30-(step*400)//30
        begin=time.monotonic();before=float(native.data.time)
        obs,reward,done,truncated,info=native.step(np.asarray(action,np.float32))
        if abs(float(native.data.time)-before-native.frame_skip/400)>1e-9:raise ValueError('physics cadence')
        if native._did_see_sim_exception:raise RuntimeError('native simulator exception')
        self.observation=self.env._format_raw_obs(obs);self.steps+=1;self.seconds+=time.monotonic()-begin
        return dict(reward=float(reward),done=bool(done or truncated),success=bool(info.get('success',False)))


def execute_episode(state,engine,env,source,H,method,out,stop,job):
    import random
    import numpy as np
    import torch
    from controller import run_episode
    mode=job['mode'];random_cut=None
    claim=admit_episode(source,job)
    native=env._env;start=time.monotonic();before=dict(engine.counts);meter_before=dict(state['meter'].entered);last=[0.];runtime=None;observed_cuts=[]
    result=dict(source_id=source['source_id'],task=source['task'],split=source['split'],ordinal=source['ordinal'],
        env_seed=source['env_seed'],policy_seed=source['policy_seed'],method=method,H=H,success=None,
        status='entered',steps=0,episode_started_utc=utc(),terminal=False,technical_failure=None,
        action_dim=4,control_hz=30,physics_hz=400,action_scale=.015,repeat=0,max_interventions=1 if mode=='G0-once' else None,
        mode=mode,branch=method,planned_random_cut=random_cut if mode=='Random-once' else None,attempt_ordinal=claim['stage_ordinal'],attempt_index=claim['attempt'],corrected_retry=claim['retry'],stage=job['stage'],cell_id=job['cell_id'],loss=engine.cfg['loss'],fit_seed=job['fit_seed'],unit_id=claim['unit_id'],renderer=job['renderer'])
    new_json(out/'ENTERED.json',result)
    def emit(kind,event):
        if kind!='step':
            if kind=='monitor' and event.get('intervention_executed'):observed_cuts.append(event['step'])
            from recorder import record
            record(out/'events.jsonl',{k:result[k] for k in ('source_id','task','cell_id','H','mode','branch')},kind,event)
        if time.monotonic()-last[0]>10:
            atomic_json(out.parent.parent/'EPISODE_PROGRESS.json',dict(source_id=source['source_id'],step=event['step'],H=H,method=method,mode=mode,utc=utc()));last[0]=time.monotonic()
    try:
        # Same reset order and explicit noise-generator seed as the accepted N runner.
        seed=source['env_seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
        native.seed(seed);native.action_scale=.015;native.frame_skip=5;state['policy'].reset()
        t=time.monotonic();obs,_=env.reset(seed=seed);result['reset_seconds']=time.monotonic()-t
        native.action_scale=.015;runtime=Runtime(env,obs);engine.set_episode(runtime,source['instruction'],out)
        if not state.get('first_observation_recorded'):
            pixels=np.asarray(runtime.frame())
            if pixels.ndim!=3 or pixels.shape[-1]!=3 or not np.isfinite(pixels).all() or pixels.min()==pixels.max():raise ValueError('first planned observation RGB invalid')
            new_json(out/'FIRST_PLANNED_OBSERVATION.json',dict(shape=list(pixels.shape),dtype=str(pixels.dtype),minimum=int(pixels.min()),maximum=int(pixels.max()),unique_RGB_values=int(np.unique(pixels).size),source_id=source['source_id'],step=0,extra_render_calls=0))
            state['first_observation_recorded']=True
        row=yield from run_episode(runtime,engine,source,method,H,emit,stop,mode=mode)
        np.savez_compressed(out/'trajectory.npz',**row.pop('arrays'));result.update(row)
        result.update(terminal=True,policy_calls=row['sampling_calls'],inference_seconds=sum(x['stats']['seconds'] for x in row['plans']),
            inference_seconds_scope='generation and correction only; context/DG0 included in episode wall time')
        engine.verify()
    except BaseException as e:
        result.update(status='technical_failure',success=None,intervention_cuts=observed_cuts,
            first_cut=observed_cuts[0] if observed_cuts else None,last_cut=observed_cuts[-1] if observed_cuts else None,
            technical_failure=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
    result.update(elapsed_seconds=time.monotonic()-start,episode_finished_utc=utc(),environment_seconds=runtime.seconds if runtime else 0,
        counters={k:v-before.get(k,0) for k,v in engine.counts.items()},numeric_counters={k:v-meter_before.get(k,0) for k,v in state['meter'].entered.items()},steps=runtime.steps if runtime else 0)
    from render_context import evidence
    result['render_context']=evidence(env)
    new_json(out/'RESULT.json',result)
    if result['status']=='technical_failure':
        from faults import pause
        pause(claim['unit_id'],out/'RESULT.json',result.get('technical_failure'))
    # Raw scientific result commits first. Optional compact export is independent.
    try:
        from publication_data import finite_values
        new_json(out/'SUMMARY_ROW.json',finite_values({k:v for k,v in result.items() if k not in ('events','plans')}))
    except (ValueError,TypeError) as error:
        new_json(out/'PUBLICATION_ERROR.json',dict(type=type(error).__name__,message=str(error),scientific_result_preserved=True))
    return result

