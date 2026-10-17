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
from admission import authority,before_cutoff,validate_job


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


def execute_episode(state,env,source,H,out,stop):
    import random
    import numpy as np
    import torch
    policy,model,features,post,device=(state[k] for k in ('policy','model','features','post','device'))
    native=env._env
    result=dict(source_id=source['source_id'],task=source['task'],split='test',ordinal=source['ordinal'],
        env_seed=source['env_seed'],policy_seed=source['policy_seed'],method='N',H=H,success=None,
        status='entered',steps=0,policy_calls=0,flow_calls=0,environment_seconds=0.,inference_seconds=0.,
        episode_started_utc=utc(),terminal=False,technical_failure=None,action_dim=4,
        control_hz=30,physics_hz=400,action_scale=.015)
    new_json(out/'ENTERED.json',result);start=time.monotonic();last_heartbeat=0
    try:
        seed=source['env_seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
        native.seed(seed);native.action_scale=.015;native.frame_skip=5;policy.reset()
        t=time.monotonic();obs,_=env.reset(seed=seed);result['environment_seconds']+=time.monotonic()-t
        native.action_scale=.015
        generator=torch.Generator(device=device);generator.manual_seed(source['policy_seed'])
        queue=[]
        for step in range(300):
            if stop() or time.monotonic()-start>1800:raise RuntimeError('episode interrupted or deadline exceeded')
            if not queue:
                t=time.monotonic()
                with torch.inference_mode():
                    batch=features._policy_batch(obs,source['instruction'])
                    images,masks=policy._preprocess_images(batch)
                    if len(images)!=3 or [bool(x[0]) for x in masks]!=[True,False,False]:raise ValueError('single-camera preprocessing mismatch')
                    noise=torch.randn((1,50,32),device=device,dtype=torch.float32,generator=generator)
                    result['policy_calls']+=1
                    raw=model.sample_actions(images,masks,batch['observation.language.tokens'],
                        batch['observation.language.attention_mask'],noise=noise,num_steps=10)
                    actions=post(raw[:,:,:4].reshape(-1,4)).reshape(50,4).float().cpu().numpy()
                    if actions.shape!=(50,4) or not np.isfinite(actions).all():raise ValueError('invalid decoded physical actions')
                    # Native MetaWorld clips each normalized control to its Box.
                    # Retain that original behavior instead of an extra projection.
                    queue=list(actions[:H])
                result['flow_calls']+=10;result['inference_seconds']+=time.monotonic()-t
            action=queue.pop(0);native.frame_skip=((step+1)*400)//30-(step*400)//30
            t=time.monotonic();raw,reward,terminated,truncated,info=native.step(np.asarray(action,dtype=np.float32))
            obs=env._format_raw_obs(raw);result['environment_seconds']+=time.monotonic()-t
            if obs['pixels'].shape!=(480,480,3) or obs['agent_pos'].shape!=(4,):raise ValueError('native observation shape')
            result['steps']=step+1
            if native._did_see_sim_exception:raise RuntimeError('MetaWorld simulator exception flag')
            success=bool(info.get('success',False))
            if success or terminated or truncated or step==299:
                result.update(success=success,status='complete',terminal=True,terminated=bool(terminated),
                    truncated=bool(truncated),terminal_reason='success' if success else 'terminated' if terminated else 'truncated' if truncated else 's300',last_reward=float(reward))
                break
            if time.monotonic()-last_heartbeat>10:
                atomic_json(out.parent.parent/'EPISODE_PROGRESS.json',dict(source_id=source['source_id'],step=step+1,H=H,utc=utc()))
                last_heartbeat=time.monotonic()
    except BaseException as e:
        result.update(status='technical_failure',success=None,technical_failure=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
    result.update(elapsed_seconds=time.monotonic()-start,episode_finished_utc=utc())
    new_json(out/'RESULT.json',result)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--slot',type=int,required=True);p.add_argument('--root',required=True);a=p.parse_args()
    root=__import__('pathlib').Path(a.root);authority();base=read(ROOT/'config/BASE.json');cfg=copy.deepcopy(base)
    cfg['device']=base['device_list'][a.slot];cfg['native']['device']=cfg['device']
    counts=Counts();egl=None;state=None;fatal=None;stopping=False
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
        import mujoco
        from gymnasium.envs.mujoco import mujoco_rendering
        from lerobot.envs.metaworld import MetaworldEnv
        egl.install_resident_rendering(mujoco_rendering)
        new_json(root/'MODEL_READY.json',dict(utc=utc(),process=process_identity(),device=device,
            GPU=cfg['device'],model_id='pi05_MT50_SFT030000',model_load_seconds=time.monotonic()-load_started,
            actual_strict_loader=str(root/'policy_loader.json'),model_resident=True))
        index=0
        while not stopping:
            index+=1;command=root/'inbox'/('%05d.json'%index)
            while not command.exists() and not stopping:
                if (root/'STOP.json').exists():stopping=True;break
                time.sleep(.5)
            if stopping:break
            payload=read(command);job=read(payload['job']);validate_job(job);authority()
            dest=__import__('pathlib').Path(payload['output']);dest.mkdir(parents=True,exist_ok=False)
            result=dict(job_id=job['job_id'],method=job['method'],H=job['H'],task=job['task'],episodes=[],exceptions=[],started_utc=utc())
            env=None;t0=time.monotonic();before=counts.snapshot()
            try:
                if not before_cutoff():result['status']='not_entered_deadline'
                else:
                    # Constructor work belongs to this job, not a separate preflight.
                    t=time.monotonic();env=MetaworldEnv(task=job['task'],camera_name='corner2',obs_type='pixels_agent_pos',
                        render_mode='rgb_array',observation_width=480,observation_height=480,max_path_length=300)
                    result['environment_initialization_seconds']=time.monotonic()-t
                    if float(env._env.model.opt.timestep)!=1/400:raise ValueError('unexpected physics timestep')
                    for source in job['sources']:
                        if stopping or not before_cutoff():break
                        ep=dest/'episodes'/source['source_id'];ep.mkdir(parents=True,exist_ok=False)
                        row=execute_episode(state,env,source,job['H'],ep,lambda:stopping)
                        result['episodes'].append(row)
                        # A known episode error is recorded once; no automatic retry.
                        if row['status']!='complete':break
                    result['status']='complete' if len(result['episodes'])==10 and all(r['status']=='complete' for r in result['episodes']) else 'partial_or_failed'
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
        if egl is not None:
            try:egl.finish_resident()
            except BaseException as e:cleanup.append(dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
        new_json(root/'WORKER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,numeric=counts.snapshot(),process=process_identity()))
    return 3 if fatal or cleanup else 0

if __name__=='__main__':sys.exit(main())
