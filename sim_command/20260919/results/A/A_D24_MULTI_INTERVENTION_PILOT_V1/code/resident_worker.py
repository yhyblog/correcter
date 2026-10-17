"""Resident D24 pilot worker; fresh native environment for each old initial state."""
import argparse
import copy
import os
import signal
import sys
import time
import traceback
from pathlib import Path
from collections import Counter
import paths
from paths import ROOT
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,before_cutoff,validate_job

class Counts:
    def __init__(self):self.entered=Counter();self.returned=Counter();self.seconds=Counter();self.failed=[]
    def call(self,name,fn,units=None,detail=None):
        units=units or {};self.entered.update(units);t=time.monotonic()
        try:
            value=fn();self.returned.update(units);return value
        except BaseException as e:self.failed.append(dict(name=name,type=type(e).__name__,message=str(e)));raise
        finally:self.seconds[name]+=time.monotonic()-t
    def snapshot(self):return dict(entered=dict(self.entered),returned=dict(self.returned),seconds=dict(self.seconds),failed=list(self.failed))

class Runtime:
    def __init__(self,env,observation):self.env=env;self.observation=observation;self.steps=0
    def frame(self):return self.observation['pixels']
    def proprio(self):
        import numpy as np
        return np.asarray(self.observation['agent_pos'],dtype=np.float32)
    def step(self,action,step):
        import numpy as np
        if step!=self.steps:raise ValueError('physical control clock mismatch')
        native=self.env._env;native.frame_skip=((step+1)*400)//30-(step*400)//30
        before=float(native.data.time)
        obs,reward,done,truncated,info=native.step(np.asarray(action,np.float32))
        if abs(float(native.data.time)-before-native.frame_skip/400)>1e-9:raise ValueError('physics cadence')
        if native._did_see_sim_exception:raise RuntimeError('native simulation exception')
        self.observation=self.env._format_raw_obs(obs);self.steps+=1
        return dict(reward=float(reward),done=bool(done or truncated),success=bool(info.get('success',False)))

def original_initial_state_check(env,source):
    """Small initial condition check, not full hidden-state equivalence certification."""
    import numpy as np
    native=env._env;p=Path(source['legacy_source_path'])/'initial_scene/state.npz'
    differences={}
    with np.load(p,allow_pickle=False) as old:
        for k in ('qpos','qvel','mocap_pos','mocap_quat','target_pos'):
            value=np.asarray(native._target_pos if k=='target_pos' else getattr(native.data,k))
            if value.shape!=old[k].shape:raise ValueError('old initial scene shape differs: '+k)
            difference=float(np.max(np.abs(value-old[k]),initial=0));differences[k]=difference
    result=dict(source=str(p),fields_max_absolute_difference=differences,tolerance=1e-6,
        old_initial_condition_matches=all(v<=1e-6 for v in differences.values()),full_hidden_state_equivalence_claimed=False)
    return result

def execute_job(engine,state,MetaworldEnv,instruction,job,out,stop):
    import random
    import numpy as np
    import torch
    from controller import run_episode
    source=job['sources'][0];env=None;start=time.monotonic();tlast=[0.]
    row=dict(job_id=job['job_id'],method=job['method'],H=10,source_id=source['source_id'],
        task=source['task'],repeat=0,env_seed=source['env_seed'],cohort=source['cohort'],
        success=None,status='entered',started_utc=utc(),new_initial_state=False,synthetic=False)
    before=dict(engine.counts);new_json(out/'ENTERED.json',row)
    def emit(kind,event):
        if kind=='monitor':
            with (out/'events.jsonl').open('a') as f:
                f.write(__import__('json').dumps(event,allow_nan=False,sort_keys=True)+'\n')
        if time.monotonic()-tlast[0]>10:
            atomic_json(out/'PROGRESS.json',dict(kind=kind,step=event['step'],utc=utc()));tlast[0]=time.monotonic()
    try:
        # Identical old clean_reset order: seed before fresh construction, reseed
        # before the explicit reset, then native.seed AFTER that reset.
        seed=source['env_seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
        t=time.monotonic();env=MetaworldEnv(task=source['task'],camera_name='corner2',obs_type='pixels_agent_pos',
            render_mode='rgb_array',observation_width=480,observation_height=480,max_path_length=300)
        if abs(float(env._env.model.opt.timestep)-1/400)>1e-12:raise ValueError('native physics timestep')
        env._env.action_scale=.015
        random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);torch.cuda.manual_seed(seed);state['policy'].reset()
        obs,_=env.reset(seed=seed);env._env.action_scale=.015;env._env.seed(seed)
        row['initialization_seconds']=time.monotonic()-t
        check=original_initial_state_check(env,source);new_json(out/'INITIAL_STATE_CHECK.json',check)
        if not check['old_initial_condition_matches']:raise ValueError('existing old initial state not reproduced; no replacement')
        runtime=Runtime(env,obs);engine.set_episode(runtime,instruction,out)
        result=run_episode(runtime,engine,source,job['method'],emit,stop)
        np.savez_compressed(out/'trajectory.npz',**result.pop('arrays'))
        row.update(result);engine.verify()
    except BaseException as e:
        row.update(status='technical_failure',success=None,error=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
    finally:
        if env is not None:
            try:env.close()
            except BaseException as e:row.update(status='cleanup_failure',success=None,cleanup_error=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
        row.update(elapsed_seconds=time.monotonic()-start,finished_utc=utc(),
            counters={k:v-before.get(k,0) for k,v in engine.counts.items()},entered_episodes=1,
            terminal_episodes=int(row['status']=='complete'),successes=int(row['success'] is True),
            technical_failures=int(row['status']!='complete'))
        new_json(out/'RESULT.json',row)
    return row

def main():
    p=argparse.ArgumentParser();p.add_argument('--slot',type=int,required=True);p.add_argument('--root',required=True);a=p.parse_args()
    root=Path(a.root);authority();cfg=copy.deepcopy(read(ROOT/'config/BASE.json'));config=read(ROOT/'config/CONFIG.json')
    cfg['device']=cfg['device_list'][a.slot];cfg['native']['device']=cfg['device']
    counts=Counts();egl=None;engine=None;fatal=None;stopping=False;cleanup=[]
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    new_json(root/'STARTED.json',dict(process=process_identity(),GPU=cfg['device'],utc=utc()))
    t0=time.monotonic()
    try:
        from resident_egl import ResidentEGL
        egl=ResidentEGL(cfg['native'],root,lambda:None);egl.prepare()
        import torch
        device=egl.bind_policy(torch);torch.set_num_threads(4)
        from numeric_setup import initialize
        state=initialize(cfg,root,counts,device)
        from numeric_engine import Engine
        engine=Engine(state,config,root)
        import mujoco
        from gymnasium.envs.mujoco import mujoco_rendering
        from lerobot.envs.metaworld import MetaworldEnv,TASK_DESCRIPTIONS
        egl.install_resident_rendering(mujoco_rendering)
        instruction=TASK_DESCRIPTIONS['disassemble-v3']
        new_json(root/'MODEL_READY.json',dict(utc=utc(),process=process_identity(),GPU=cfg['device'],device=device,
            model_id='pi05_MT50_SFT030000',Q='A4000',DG0=[241,242],load_seconds=time.monotonic()-t0,
            actual_strict_loader=str(root/'policy_loader.json'),instruction=instruction,resident=True,Velocity_ready=True))
        index=0
        while not stopping:
            index+=1;command=root/'inbox'/('%05d.json'%index)
            while not command.exists() and not stopping:
                if (root/'STOP.json').exists():stopping=True;break
                time.sleep(.5)
            if stopping:break
            payload=read(command);job=read(payload['job']);validate_job(job);authority()
            if not before_cutoff():break
            out=Path(payload['output']);out.mkdir(parents=True,exist_ok=False)
            result=execute_job(engine,state,MetaworldEnv,instruction,job,out,lambda:stopping)
            new_json(root/'done'/('%05d.json'%index),dict(job_id=job['job_id'],result=str(out/'RESULT.json'),status=result['status'],utc=utc()))
            if result['status']!='complete':raise RuntimeError('owned worker stops after recorded technical failure')
    except BaseException as e:fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    finally:
        if engine is not None:
            try:engine.hook.close()
            except BaseException as e:cleanup.append(dict(type=type(e).__name__,message=str(e)))
        if egl is not None:
            try:egl.finish_resident()
            except BaseException as e:cleanup.append(dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
        new_json(root/'WORKER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,numeric=counts.snapshot(),
            pilot_counts=engine.counts if engine else None,process=process_identity()))
    return 3 if fatal or cleanup else 0

if __name__=='__main__':sys.exit(main())

