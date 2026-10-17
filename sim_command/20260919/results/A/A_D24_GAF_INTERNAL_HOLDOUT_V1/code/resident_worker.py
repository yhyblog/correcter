"""One frozen N policy per GPU; native GAF guides every H10 sampling call."""
import argparse,copy,time,traceback,signal
from pathlib import Path
import paths
from paths import ROOT
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,before_cutoff
from gaf_runtime import Counts,Ledger,load_critics,make_adapter,pi05_denoiser_hook


def episode(state,critics,language,env,source,out,stop):
    import random,numpy as np,torch
    policy,model,features,post,device=(state[k] for k in ('policy','model','features','post','device'))
    native=env._env;start=time.monotonic();ledger=Ledger();meter=state['meter'];before=meter.snapshot()
    result=dict(source,method='GAF-v1 adapted',H=10,C=10,success=None,status='entered',steps=0,
        policy_calls=0,flow_calls=0,interventions=None,intervention_count_reason='native continuous per-sampling guidance; no G0 event or once cap',
        environment_seconds=0.,inference_seconds=0.,elapsed_seconds=None,episode_started_utc=utc(),
        terminal=False,technical_failure=None,action_dim=4,control_hz=30,physics_hz=400,action_scale=.015)
    # Exclusive method/source admission. A notification can never repeat a source.
    new_json(ROOT/'claims'/(source['source_id']+'.json'),dict(source,utc=utc(),method='GAF-v1 adapted',repeat=0))
    new_json(out/'ENTERED.json',result)
    try:
        seed=source['env_seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
        native.seed(seed);native.action_scale=.015;native.frame_skip=5;policy.reset()
        t=time.monotonic();obs,_=env.reset(seed=seed);result['environment_seconds']+=time.monotonic()-t;native.action_scale=.015
        generator=torch.Generator(device=device);generator.manual_seed(source['policy_seed']);queue=[]
        for step in range(300):
            if stop() or time.monotonic()-start>1800:raise RuntimeError('episode stopped/deadline')
            if not queue:
                t=time.monotonic()
                adapter=make_adapter(critics,obs['agent_pos'],language,device,ledger)
                with torch.inference_mode(),pi05_denoiser_hook(model,adapter):
                    batch=features._policy_batch(obs,source['instruction']);images,masks=policy._preprocess_images(batch)
                    if len(images)!=3 or [bool(x[0]) for x in masks]!=[True,False,False]:raise ValueError('N single-camera preprocessing mismatch')
                    noise=torch.randn((1,50,32),device=device,dtype=torch.float32,generator=generator)
                    result['policy_calls']+=1
                    raw=model.sample_actions(images,masks,batch['observation.language.tokens'],batch['observation.language.attention_mask'],noise=noise,num_steps=10)
                    actions=post(raw[:,:,:4].reshape(-1,4)).reshape(50,4).float().cpu().numpy()
                    if actions.shape!=(50,4) or not np.isfinite(actions).all():raise ValueError('invalid physical action')
                    queue=list(actions[:10])
                result['inference_seconds']+=time.monotonic()-t
            action=queue.pop(0);native.frame_skip=((step+1)*400)//30-(step*400)//30
            t=time.monotonic();raw,reward,terminated,truncated,info=native.step(np.asarray(action,dtype=np.float32))
            obs=env._format_raw_obs(raw);result['environment_seconds']+=time.monotonic()-t;result['steps']=step+1
            if obs['pixels'].shape!=(480,480,3) or obs['agent_pos'].shape!=(4,):raise ValueError('invalid actual observation')
            if native._did_see_sim_exception:raise RuntimeError('MetaWorld simulator exception')
            success=bool(info.get('success',False))
            if success or terminated or truncated or step==299:
                result.update(success=success,status='complete',terminal=True,terminated=bool(terminated),truncated=bool(truncated),
                    terminal_reason='success' if success else 'terminated' if terminated else 'truncated' if truncated else 's300',last_reward=float(reward));break
    except BaseException as e:
        result.update(status='technical_failure',success=None,technical_failure=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
    after=meter.snapshot();gs=ledger.snapshot()
    result.update(elapsed_seconds=time.monotonic()-start,episode_finished_utc=utc(),gaf_counts=gs,
        flow_calls=gs['entered'].get('flow_forward',0),numeric_delta={k:after['entered'].get(k,0)-before['entered'].get(k,0) for k in after['entered']})
    new_json(out/'RESULT.json',result);return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--slot',type=int,required=True);p.add_argument('--root',required=True);a=p.parse_args()
    out=Path(a.root);authority();base=read(ROOT/'config/BASE.json');cfg=copy.deepcopy(base)
    cfg['device']=base['device_list'][a.slot];cfg['native']['device']=cfg['device']
    sources=read(ROOT/'config/EVAL_SOURCES_V1.json')['rows'];tasks=sorted({s['task'] for s in sources})
    selected=[t for i,t in enumerate(tasks) if i%8==a.slot]
    expected=sum(s['task'] in selected for s in sources);counts=Counts();egl=None;fatal=None;stopping=False;completed=[];env=None;cleanup=[]
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    new_json(out/'STARTED.json',dict(utc=utc(),process=process_identity(),GPU=cfg['device'],tasks=selected));start=time.monotonic()
    try:
        from resident_egl import ResidentEGL
        egl=ResidentEGL(cfg['native'],out,lambda:None);egl.prepare()
        import torch,numpy as np
        torch.set_num_threads(4);device=egl.bind_policy(torch)
        from numeric_setup import initialize
        state=initialize(cfg,out,counts,device);state['meter']=counts
        critics=load_critics(device)
        import mujoco
        from gymnasium.envs.mujoco import mujoco_rendering
        from lerobot.envs.metaworld import MetaworldEnv
        egl.install_resident_rendering(mujoco_rendering)
        new_json(out/'MODEL_READY.json',dict(utc=utc(),process=process_identity(),GPU=cfg['device'],device=device,
            base_model='pi05_MT50_SFT030000',critic_seeds=[9201,9202,9203],critic_checkpoint_loads=3,
            model_resident=True,model_load_seconds=time.monotonic()-start,strict_policy_loader=str(out/'policy_loader.json')))
        for task in selected:
            authority()
            if stopping or not before_cutoff():break
            rows=[s for s in sources if s['task']==task]
            t0=time.monotonic()
            with torch.no_grad():language=state['features'].encode_instruction(rows[0]['instruction'])
            if language.shape!=(2048,) or not np.isfinite(language).all():raise ValueError('invalid real task language feature')
            new_json(out/'tasks'/(task+'.json'),dict(utc=utc(),task=task,language_embedding_calls=1,language_seconds=time.monotonic()-t0,
                source='same frozen feature_path.encode_instruction as saved B11 language',image_feature_extraction_for_GAF=0))
            t0=time.monotonic()
            env=MetaworldEnv(task=task,camera_name='corner2',obs_type='pixels_agent_pos',render_mode='rgb_array',observation_width=480,observation_height=480,max_path_length=300)
            if float(env._env.model.opt.timestep)!=1/400:raise ValueError('physics timestep mismatch')
            init_seconds=time.monotonic()-t0
            for source in rows:
                if stopping or not before_cutoff():break
                dest=ROOT/'runs'/source['source_id'];dest.mkdir(parents=True,exist_ok=False)
                result=episode(state,critics,language,env,source,dest,lambda:stopping)
                completed.append(result)
                atomic_json(out/'PROGRESS.json',dict(utc=utc(),episodes=len(completed),successes=sum(r['success'] is True for r in completed),
                    last_source=source['source_id'],last_task_init_seconds=init_seconds))
                if result['status']!='complete':raise RuntimeError('first technical failure stops worker; no automatic retry')
            env.close();env=None
        if len(completed)!=expected:raise RuntimeError('worker source coverage incomplete')
    except BaseException as e:
        fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    finally:
        if env is not None:
            try:env.close()
            except BaseException as e:cleanup.append(dict(stage='environment',type=type(e).__name__,message=str(e)))
        if egl is not None:
            try:egl.finish_resident()
            except BaseException as e:cleanup.append(dict(stage='graphics',type=type(e).__name__,message=str(e)))
        new_json(out/'WORKER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,completed_episodes=len(completed),expected_episodes=expected,
            technical_failures=sum(r['status']!='complete' for r in completed),numeric=counts.snapshot(),process=process_identity(),elapsed_seconds=time.monotonic()-start))
    return 0 if fatal is None and not cleanup else 3

if __name__=='__main__':raise SystemExit(main())
