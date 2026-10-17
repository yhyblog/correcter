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
from admission import authority,before_cutoff,validate_job,admit_episode


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


def execute_episode(state,engine,env,source,H,method,out,stop,mode,random_cut):
    import random
    import numpy as np
    import torch
    from controller import run_episode
    claim=admit_episode(source,H,mode)
    native=env._env;start=time.monotonic();before=dict(engine.counts);last=[0.];runtime=None;observed_cuts=[]
    result=dict(source_id=source['source_id'],task=source['task'],split='test',ordinal=source['ordinal'],
        env_seed=source['env_seed'],policy_seed=source['policy_seed'],method=method,H=H,success=None,
        status='entered',steps=0,episode_started_utc=utc(),terminal=False,technical_failure=None,
        action_dim=4,control_hz=30,physics_hz=400,action_scale=.015,repeat=0,max_interventions=1 if mode=='Random-once' else None,
        mode=mode,branch=method,planned_random_cut=random_cut if mode=='Random-once' else None,attempt_ordinal=claim['stage_ordinal'],attempt_index=claim['attempt'],corrected_retry=claim['retry'],recovery='r3')
    new_json(out/'ENTERED.json',result)
    def emit(kind,event):
        if kind!='step':
            if kind=='monitor' and event.get('intervention_executed'):observed_cuts.append(event['step'])
            with (out/'events.jsonl').open('a') as f:f.write(json.dumps(dict(event,event_kind=kind),allow_nan=False,sort_keys=True)+'\n')
        if time.monotonic()-last[0]>10:
            atomic_json(out.parent.parent/'EPISODE_PROGRESS.json',dict(source_id=source['source_id'],step=event['step'],H=H,method=method,mode=mode,utc=utc()));last[0]=time.monotonic()
    try:
        # Same reset order and explicit noise-generator seed as the accepted N runner.
        seed=source['env_seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
        native.seed(seed);native.action_scale=.015;native.frame_skip=5;state['policy'].reset()
        t=time.monotonic();obs,_=env.reset(seed=seed);result['reset_seconds']=time.monotonic()-t
        native.action_scale=.015;runtime=Runtime(env,obs);engine.set_episode(runtime,source['instruction'],out)
        row=run_episode(runtime,engine,source,method,H,emit,stop,mode=mode,random_cut=random_cut)
        np.savez_compressed(out/'trajectory.npz',**row.pop('arrays'));result.update(row)
        result.update(terminal=True,policy_calls=row['sampling_calls'],inference_seconds=sum(x['stats']['seconds'] for x in row['plans']),
            inference_seconds_scope='generation and correction only; context/DG0 included in episode wall time')
        engine.verify()
    except BaseException as e:
        result.update(status='technical_failure',success=None,intervention_cuts=observed_cuts,
            first_cut=observed_cuts[0] if observed_cuts else None,last_cut=observed_cuts[-1] if observed_cuts else None,
            technical_failure=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
    result.update(elapsed_seconds=time.monotonic()-start,episode_finished_utc=utc(),environment_seconds=runtime.seconds if runtime else 0,
        counters={k:v-before.get(k,0) for k,v in engine.counts.items()},steps=runtime.steps if runtime else 0)
    new_json(out/'RESULT.json',result);return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--slot',type=int,required=True);p.add_argument('--root',required=True);a=p.parse_args()
    root=__import__('pathlib').Path(a.root);authority();base=read(ROOT/'config/BASE.json');cfg=copy.deepcopy(base)
    cfg['device']=base['device_list'][a.slot];cfg['native']['device']=cfg['device']
    counts=Counts();egl=None;state=None;engine=None;fatal=None;stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    new_json(root/'STARTED.json',dict(process=process_identity(),GPU=cfg['device'],utc=utc()))
    load_started=time.monotonic()
    try:
        # Physical mapping must precede all Torch/MuJoCo imports.
        from resident_egl import ResidentEGL
        egl=ResidentEGL(cfg['native'],root,lambda:None);egl.prepare()
        import torch
        device=egl.bind_policy(torch)
        from numeric_setup import initialize
        state=initialize(cfg,root,counts,device)
        from numeric_engine import Engine
        engine=Engine(state,read(ROOT/'config/CONFIG.json'),root)
        import mujoco
        from gymnasium.envs.mujoco import mujoco_rendering
        from lerobot.envs.metaworld import MetaworldEnv
        egl.install_resident_rendering(mujoco_rendering)
        new_json(root/'MODEL_READY.json',dict(utc=utc(),process=process_identity(),device=device,
            GPU=cfg['device'],model_id='pi05_MT50_SFT030000',model_load_seconds=time.monotonic()-load_started,
            actual_strict_loader=str(root/'policy_loader.json'),model_resident=True,Q='A4000',DG0=[241,242],training_coverage='historical5tasks'))
        index=0
        while not stopping:
            index+=1;command=root/'inbox'/('%05d.json'%index)
            while not command.exists() and not stopping:
                if (root/'STOP.json').exists():stopping=True;break
                time.sleep(.5)
            if stopping:break
            payload=read(command);job=read(payload['job']);validate_job(job);authority()
            dest=__import__('pathlib').Path(payload['output']);dest.mkdir(parents=True,exist_ok=False)
            result=dict(job_id=job['job_id'],method=job['method'],mode=job['mode'],H=job['H'],task=job['task'],episodes=[],exceptions=[],started_utc=utc())
            env=None;t0=time.monotonic();before=counts.snapshot()
            try:
                if not before_cutoff():result['status']='not_entered_deadline'
                else:
                    # Constructor work belongs to this job, not a separate preflight.
                    t=time.monotonic();env=MetaworldEnv(task=job['task'],camera_name='corner2',obs_type='pixels_agent_pos',
                        render_mode='rgb_array',observation_width=480,observation_height=480,max_path_length=300)
                    result['environment_initialization_seconds']=time.monotonic()-t
                    if float(env._env.model.opt.timestep)!=1/400:raise ValueError('unexpected physics timestep')
                    selected={x['source_id']:x['selected_cut'] for x in job['random_schedule']}
                    for source in job['sources']:
                        if stopping or not before_cutoff():break
                        ep=dest/'episodes'/source['source_id'];ep.mkdir(parents=True,exist_ok=False)
                        row=execute_episode(state,engine,env,source,job['H'],job['method'],ep,lambda:stopping or not before_cutoff(),job['mode'],selected[source['source_id']])
                        result['episodes'].append(row)
                        # A known episode error is recorded once; no automatic retry.
                        if row['status']!='complete':break
                    result['status']='complete' if len(result['episodes'])==len(job['sources']) and all(r['status']=='complete' for r in result['episodes']) else 'partial_or_failed'
            except BaseException as e:
                result.update(status='technical_failure');result['exceptions'].append(dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
            finally:
                if env is not None:
                    try:env.close()
                    except BaseException as e:
                        result['exceptions'].append(dict(stage='environment_cleanup',type=type(e).__name__,message=str(e),traceback=traceback.format_exc()));result['status']='cleanup_failure'
                after=counts.snapshot()
                result.update(elapsed_seconds=time.monotonic()-t0,finished_utc=utc(),
                    numeric_delta={k:after['entered'].get(k,0)-before['entered'].get(k,0) for k in after['entered']},
                    entered_episodes=len(result['episodes']),terminal_episodes=sum(r['status']=='complete' for r in result['episodes']),
                    successes=sum(r['success'] is True for r in result['episodes']),technical_failures=sum(r['status']=='technical_failure' for r in result['episodes']))
                new_json(dest/'RESULT.json',result);new_json(root/'done'/('%05d.json'%index),dict(job_id=job['job_id'],result=str(dest/'RESULT.json'),status=result['status'],utc=utc()))
            if result['status'] in ('cleanup_failure','technical_failure') or result['technical_failures']:
                # Unknown native state does not continue on this worker. Other workers are independent.
                raise RuntimeError('worker stops after job/episode technical failure: '+job['job_id'])
    except BaseException as e:
        fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    finally:
        cleanup=[]
        if engine is not None:
            try:engine.hook.close()
            except BaseException as e:cleanup.append(dict(type=type(e).__name__,message=str(e)))
        if egl is not None:
            try:egl.finish_resident()
            except BaseException as e:cleanup.append(dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
        new_json(root/'WORKER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,numeric=counts.snapshot(),method_counts=engine.counts if engine else None,process=process_identity()))
    return 3 if fatal or cleanup else 0

if __name__=='__main__':sys.exit(main())
