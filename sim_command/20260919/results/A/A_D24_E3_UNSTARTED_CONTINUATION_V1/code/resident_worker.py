"""Pinned native VLA-Corrector evaluator with fixed-source/physical/recording adapters."""
import argparse
from collections import Counter
import os,sys,time,traceback,signal
from pathlib import Path
import paths
from paths import ROOT,WORKSPACE
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,before_cutoff
from source_plan import sources_for_slot,claim_source
from summary_json import native_summary_for_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--slot',type=int,required=True);p.add_argument('--root',required=True);a=p.parse_args()
    out=Path(a.root);cfg=read(ROOT/'config/CONFIG.json');base=read(ROOT/'config/BASE.json')
    base['native']['device']=base['device_list'][a.slot]
    selected,sources=sources_for_slot(a.slot)
    expected_episodes=sum(len(v) for v in sources.values())
    authority();new_json(out/'STARTED.json',dict(utc=utc(),process=process_identity(),tasks=selected,GPU=base['native']['device']))
    started=time.monotonic();egl=None;fatal=None;active=None;owned=[];stopping=False;completed=[]
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    try:
        from resident_egl import ResidentEGL
        egl=ResidentEGL(base['native'],out,lambda:None);egl.prepare()
        import torch,numpy as np,random,gymnasium as gym
        device=egl.bind_policy(torch);torch.set_num_threads(4)
        import mujoco
        from gymnasium.envs.mujoco import mujoco_rendering
        egl.install_resident_rendering(mujoco_rendering)
        import native_eval_unstarted as native
        native.UNSTARTED_EPISODE_COUNTS={i:len(sources[t]) for i,t in selected.items()}
        from lerobot.envs.metaworld import MetaworldEnv
        policy_ref={}

        class FixedSourceEnv(MetaworldEnv):
            def __init__(self,task):
                self.source_index=-1;self.current=None;self.ended=True
                super().__init__(task=task,camera_name='corner2',obs_type='pixels_agent_pos',render_mode='rgb_array',observation_width=480,observation_height=480,max_path_length=300)
                if float(self._env.model.opt.timestep)!=1/400:raise ValueError('physical timestep changed')
            def reset(self,seed=None,**kwargs):
                nonlocal active
                authority()
                if stopping or not before_cutoff():raise RuntimeError('new episode admission stopped')
                self.source_index+=1
                if self.source_index>=len(sources[self.task]):raise RuntimeError('unexpected extra reset; no extra source permitted')
                source=sources[self.task][self.source_index]
                claim_source(source,a.slot)
                self.current=source;active=self;self.t=0;self.ended=False
                self.begin=time.monotonic();self.environment_seconds=0.;self.counter=Counter();self.times=Counter()
                self.ep=ROOT/'runs'/source['source_id'];self.ep.mkdir(parents=True,exist_ok=False)
                new_json(self.ep/'ENTERED.json',dict(source,method='VLA-Corrector',H=10,repeat=0,utc=utc(),worker=a.slot))
                seed=source['env_seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
                self._env.seed(seed);self._env.action_scale=.015;self._env.frame_skip=5
                t=time.monotonic();observation,info=super().reset(seed=seed,**kwargs);self.reset_seconds=time.monotonic()-t
                self._env.action_scale=.015
                self.noise_generator=torch.Generator(device=device);self.noise_generator.manual_seed(source['policy_seed'])
                torch.manual_seed(source['policy_seed']);torch.cuda.manual_seed(source['policy_seed'])
                if observation['pixels'].shape!=(480,480,3) or not np.isfinite(observation['agent_pos']).all():raise ValueError('invalid planned-episode observation')
                return observation,info
            def step(self,action):
                if stopping or time.monotonic()-self.begin>1800:raise RuntimeError('episode stop/deadline')
                action=np.asarray(action,np.float32)
                if action.shape!=(4,) or not np.isfinite(action).all():raise ValueError('invalid physical action')
                self._env.frame_skip=((self.t+1)*400)//30-(self.t*400)//30
                before=float(self._env.data.time);begin=time.monotonic()
                raw,reward,done,truncated,info=self._env.step(action)
                if self._env._did_see_sim_exception:raise RuntimeError('MuJoCo simulation exception')
                if abs(float(self._env.data.time)-before-self._env.frame_skip/400)>1e-9:raise ValueError('control cadence changed')
                observation=self._format_raw_obs(raw);self.t+=1;self.environment_seconds+=time.monotonic()-begin
                success=bool(info.get('success',False));terminated=bool(done or success)
                info.update(task=self.task,done=bool(done),is_success=success)
                # Native wrapper would reset again here. Fixed-source adapter must not consume another source.
                self.ended=terminated or bool(truncated) or self.t>=300
                return observation,float(reward),terminated,bool(truncated or self.t>=300),info

        def make_env(*args,**kwargs):
            result={}
            for i,task in selected.items():
                env=gym.vector.SyncVectorEnv([lambda task=task:FixedSourceEnv(task)])
                owned.append(env);result[i]=env
            return {'metaworld':result}
        native.make_env=make_env

        cls=native.PI05ModifiedPolicy
        original_set=cls.set_safety_predictor
        def set_predictor(policy,*args,**kwargs):
            result=original_set(policy,*args,**kwargs);policy_ref['policy']=policy
            sampler=policy.model.sample_actions;denoiser=policy.model.denoise_step
            def sample_actions(*args,**kwargs):
                if active is not None:active.counter['sampling_calls']+=1
                return sampler(*args,**kwargs)
            def denoise_step(*args,**kwargs):
                if active is not None:active.counter['flow_calls']+=1
                return denoiser(*args,**kwargs)
            def sample_noise(shape,device):
                if active is None:raise RuntimeError('noise outside a planned episode')
                active.counter['noise_draws']+=1
                return torch.randn(shape,device=device,dtype=torch.float32,generator=active.noise_generator)
            policy.model.sample_actions=sample_actions;policy.model.denoise_step=denoise_step;policy.model.sample_noise=sample_noise
            new_json(out/'MODEL_READY.json',dict(utc=utc(),process=process_identity(),model_resident=True,
                model_id=cfg['model_id'],corrector=cfg['corrector_model'],epoch=30,device=device,GPU=base['native']['device'],
                model_load_seconds=time.monotonic()-started,repo_commit=cfg['repo_commit'],native_method=True))
            return result
        cls.set_safety_predictor=set_predictor
        original_predict=cls.predict_action_chunk_with_aux
        def predict(policy,*args,**kwargs):
            begin=time.monotonic();response=original_predict(policy,*args,**kwargs)
            if active is not None:
                active.counter['policy_requests']+=1;active.times['generation_and_correction_seconds']+=time.monotonic()-begin
                active.counter['interventions']+=int(bool(kwargs.get('guidance_replan')))
                active.counter['guidance_applied_steps']+=int(response.get('guidance_stats',{}).get('applied_steps',0))
            return response
        cls.predict_action_chunk_with_aux=predict
        original_encode=cls.encode_siglip_only
        def encode(policy,*args,**kwargs):
            begin=time.monotonic();result=original_encode(policy,*args,**kwargs)
            if active is not None:
                active.counter['safety_visual_encodes']+=1;active.times['safety_visual_seconds']+=time.monotonic()-begin
            return result
        cls.encode_siglip_only=encode
        original_delta=native.SiglipDynamicsPredictor.predict_delta_z
        def delta(predictor,*args,**kwargs):
            begin=time.monotonic();result=original_delta(predictor,*args,**kwargs)
            if active is not None:
                active.counter['safety_prediction_calls']+=1;active.times['safety_prediction_seconds']+=time.monotonic()-begin
            return result
        native.SiglipDynamicsPredictor.predict_delta_z=delta
        original_summary=native._make_episode_summary
        def episode_summary(**kwargs):
            row=original_summary(**kwargs)
            env=active
            if env is None or env.current is None:raise RuntimeError('missing actual fixed episode identity')
            source=env.current;error=kwargs.get('episode_error','')
            result=dict(source,method='VLA-Corrector',H=10,repeat=0,success=None if error else bool(kwargs['success']),
                status='technical_failure' if error else 'complete',technical_failure=error or None,
                steps=env.t,interventions=env.counter['interventions'],counters=dict(env.counter),times=dict(env.times),
                policy_calls=env.counter['sampling_calls'],elapsed_seconds=time.monotonic()-env.begin,
                reset_seconds=getattr(env,'reset_seconds',None),environment_seconds=env.environment_seconds,
                utc=utc(),max_interventions=None,threshold_config=cfg['threshold_parameters'],
                cooldown10_native_hard_retrigger_rule_preserved=True,raw50_execution_H10=True)
            # Durable core outcome precedes optional native diagnostic serialization.
            new_json(env.ep/'CORE_TERMINAL.json',result)
            clean_summary,null_reasons=native_summary_for_json(row)
            result.update(native_summary=clean_summary,native_summary_null_reasons=null_reasons,
                native_summary_original_nonfinite_types={key:'float:nan' for key in null_reasons})
            new_json(env.ep/'RESULT.json',result);completed.append(result)
            atomic_json(out/'PROGRESS.json',dict(utc=utc(),episodes=len(completed),successes=sum(r['success'] is True for r in completed),
                technical_failures=sum(r['technical_failure'] is not None for r in completed),last_source=source['source_id']))
            if error:raise RuntimeError('Recorded first technical episode failure; worker stops without further attempts: '+error)
            return row
        native._make_episode_summary=episode_summary

        sys.argv=[str(Path(native.__file__)), '--policy.path='+base['checkpoint'],'--policy.device='+device,
            '--policy.n_action_steps=10','--policy.chunk_size=50','--policy.compile_model=false',
            '--env.type=metaworld','--env.task=mt50','--env.episode_length=300','--eval.batch_size=1',
            '--eval.n_episodes=10','--eval.use_async_envs=false','--env.max_parallel_tasks=1','--seed=1000',
            '--rename_map={"observation.image":"observation.images.base_0_rgb"}',
            '--safety_model_path='+cfg['corrector_model'],'--safety_k=10','--guidance_eta=1',
            '--guidance_apply_every=1','--guidance_loss_objective=attract_delta_z_correction',
            '--guidance_compare_baseline=true','--meltdown_cooldown_steps=10',
            '--output_dir='+str(out/'native_output'),'--save_analysis=false','--save_raw_video=false',
            '--save_summary_csv=true','--save_summary_json=true']
        native.eval_modified_detection()
        if len(completed)!=expected_episodes:raise RuntimeError('worker native episode coverage incomplete')
    except BaseException as error:
        fatal=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    finally:
        if fatal and active is not None and hasattr(active,'ep') and not (active.ep/'RESULT.json').exists():
            new_json(active.ep/'FAILURE.json',dict(utc=utc(),source=active.current,failure=fatal,
                attempted=True,retry_allowed=False,success=None,steps=getattr(active,'t',None),
                core_terminal_available=(active.ep/'CORE_TERMINAL.json').exists()))
        cleanup=[]
        for env in owned:
            if getattr(env,'closed',False):continue
            try:env.close()
            except Exception as error:cleanup.append(str(error))
        if egl is not None:
            try:egl.finish_resident()
            except Exception as error:cleanup.append(str(error))
        new_json(out/'WORKER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,completed_episodes=len(completed),
            technical_failures=sum(r['technical_failure'] is not None for r in completed),elapsed_seconds=time.monotonic()-started,process=process_identity()))
    return 3 if fatal or cleanup or any(r['technical_failure'] for r in completed) else 0

if __name__=='__main__':sys.exit(main())
