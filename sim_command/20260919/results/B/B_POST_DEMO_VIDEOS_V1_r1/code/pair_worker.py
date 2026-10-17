"""One frozen candidate, two fresh matched resets, actual outcomes and bounded RGB streams."""
import argparse,copy,random,signal,time,traceback,shutil
from pathlib import Path
import paths
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity,ref
from admission import boundary,claim_arm,AdmissionStop
from pi_client import EngineProxy
from video_io import Writer,compose

def main(config_path):
 cfg=read(config_path);unit=cfg['unit'];out=Path(cfg['output']);prepared=next(p for p in read(ROOT/'PREPARED_PAIRS.json')['pairs'] if p['candidate']['unit_id']==unit['unit_id'])
 base=copy.deepcopy(read(ROOT/'config/BASE.json'));base['native']['device']=base['device_list'][cfg['slot']]
 def stop(*_):raise AdmissionStop('owned formal family stopping')
 for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
 start=time.monotonic();egl=None;engine=None;arms={};initial={};initial_frames={};state_check=None;technical=[];result=None
 def progress(arm,step,status='recording',active=True):atomic_json(out/'PROGRESS.json',dict(utc=utc(),candidate_id=unit['candidate_id'],arm=arm,step=step,status=status,active_environment=active,slot=cfg['slot']))
 try:
  boundary(True)
  from resident_egl import ResidentEGL
  egl=ResidentEGL(base['native'],out,lambda:None);egl.prepare()
  import numpy as np
  from PIL import Image
  from gymnasium.envs.mujoco import mujoco_rendering
  from lerobot.envs.metaworld import MetaworldEnv
  egl.install_resident_rendering(mujoco_rendering);engine=EngineProxy(cfg)
  new_json(out/'MODEL_READY.json',dict(utc=utc(),status='shared_pi05_connected',slot=cfg['slot'],process=process_identity(),no_extra_preflight=True))
  trajectory=np.load(prepared['post_trajectory']);post_actions=trajectory['actions'].copy();saved_success=trajectory['success_flags'].copy();trajectory.close()
  if post_actions.ndim!=2 or post_actions.shape[1]!=4 or not np.isfinite(post_actions).all():raise ValueError('invalid saved Post action units')
  class Runtime:
   def __init__(self,env,obs):self.env=env;self.observation=obs;self.steps=0
  for arm in ['N','Post']:
   boundary(True);ep=out/arm;ep.mkdir(exist_ok=False);claim=claim_arm(unit,arm);env=None;writer=None;runtime=None;actions=[];rewards=[];successes=[];last_progress=0.;arm_start=time.monotonic()
   row=dict(method=arm,status='entered',success=None,terminal=False,steps=0,frame_count=0,mode=prepared[arm+'_mode'],claim=claim,H=unit['H'],env_seed=unit['env_seed'],policy_seed=unit['policy_seed'],control_hz=30,physics_hz=400,action_scale=.015,policy_calls=0)
   new_json(ep/'ENTERED.json',row)
   try:
    # Match the original execution entry: fresh environment, then original reset seed.
    env=MetaworldEnv(task=unit['task'],camera_name='corner2',obs_type='pixels_agent_pos',render_mode='rgb_array',observation_width=480,observation_height=480,max_path_length=300)
    native=env._env;seed=unit['env_seed'];random.seed(seed);np.random.seed(seed);native.seed(seed);native.action_scale=.015;native.frame_skip=5
    obs,reset_info=env.reset(seed=seed);native.action_scale=.015;runtime=Runtime(env,obs)
    initial[arm]=dict(task=unit['task'],source_id=unit['source_id'],env_seed=seed,policy_seed=unit['policy_seed'],camera='corner2',proprio=np.asarray(obs['agent_pos'],np.float32).tolist(),qpos=native.data.qpos.tolist(),reset_random_vector=np.asarray(native._last_rand_vec).tolist(),physics_time_at_reset=float(native.data.time),reset_info={k:str(v) for k,v in reset_info.items()})
    initial_frames[arm]=np.asarray(obs['pixels']).copy();Image.fromarray(initial_frames[arm]).save(ep/'initial.png');new_json(ep/'INITIAL_STATE.json',initial[arm])
    if arm=='Post':
     diffs={k:float(np.max(np.abs(np.array(initial['N'][k])-np.array(initial['Post'][k])))) for k in ('proprio','qpos','reset_random_vector')}
     rgb=np.abs(initial_frames['N'].astype(np.int16)-initial_frames['Post'].astype(np.int16));diffs.update(first_RGB_max=int(rgb.max()),first_RGB_mean=float(rgb.mean()))
     state_check=dict(passed=all(diffs[k]<=1e-7 for k in ('proprio','qpos','reset_random_vector')) and diffs['first_RGB_max']<=1,measurements=diffs,full_hidden_state_proof=False,checks='actual first observation, robot/object reset coordinates and native reset random vector')
     new_json(out/'INITIAL_STATE_CHECK.json',state_check)
     if not state_check['passed']:raise RuntimeError('actual two-arm initial state mismatch')
    writer=Writer(ep/'recording.mp4');writer.write(obs['pixels']);progress(arm,0)
    if arm=='N':engine.begin(runtime,env.task_description,ep);engine.start_natural_stream(unit['policy_seed'])
    cap=300 if arm=='N' else len(post_actions);plan=None
    for step in range(cap):
     boundary()
     if arm=='N':
      if step%unit['H']==0:
       plan,stats=engine.propose_natural();row['policy_calls']+=1
       if np.asarray(plan).shape!=(50,4):raise ValueError('baseline raw action horizon/units')
      action=np.asarray(plan[step%unit['H']],np.float32)
     else:action=np.asarray(post_actions[step],np.float32)
     if not np.isfinite(action).all():raise ValueError('nonfinite action')
     native.frame_skip=((step+1)*400)//30-(step*400)//30;before=float(native.data.time)
     native_obs,reward,terminated,truncated,info=native.step(action)
     if abs(float(native.data.time)-before-native.frame_skip/400)>1e-9:raise ValueError('physics cadence changed')
     if native._did_see_sim_exception:raise RuntimeError('native simulator exception')
     runtime.observation=env._format_raw_obs(native_obs);runtime.steps=step+1;writer.write(runtime.observation['pixels'])
     success=bool(info.get('success',False));actions.append(action.copy());rewards.append(float(reward));successes.append(success)
     if time.monotonic()-last_progress>3 or step in (4,9):progress(arm,step+1);last_progress=time.monotonic()
     if success or terminated or truncated:
      row.update(status='complete',terminal=True,success=success,terminal_reason='success' if success else 'terminated' if terminated else 'truncated',terminated=bool(terminated),truncated=bool(truncated));break
    else:
     if cap==300:row.update(status='complete',terminal=True,success=False,terminal_reason='configured_episode_horizon',terminated=False,truncated=True)
     else:row.update(status='replay_ended_before_terminal',terminal=False,success=None,terminal_reason='saved_action_stream_exhausted_without_original_success')
    if arm=='N':
     row['model_snapshot']=engine.rpc('snapshot')
     if any(row['model_snapshot']['counts'][k] for k in ('D_forward','G0_forward','interventions','action_gradients','Q_ensemble_forward')):raise ValueError('baseline auxiliary intervention detected')
    if arm=='Post':row['saved_trajectory_step_count']=len(post_actions);row['replayed_success_flags_match_prefix']=bool(np.array_equal(np.asarray(successes),saved_success[:len(successes)]))
   except BaseException as exc:
    row.update(status='technical_failure',success=None,terminal=False,error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()));technical.append(row['error'])
   finally:
    if writer:
     try:writer.close()
     except BaseException as exc:row.update(status='technical_failure',success=None,terminal=False,encoding_error=repr(exc));technical.append(dict(type='EncodingError',message=str(exc)))
    if env:
     try:env.close()
     except BaseException as exc:technical.append(dict(type='EnvironmentCleanupError',message=str(exc)))
    row.update(steps=len(actions),frame_count=writer.frames if writer else 0,elapsed_seconds=time.monotonic()-arm_start,utc=utc())
    np.savez_compressed(ep/'trajectory.npz',actions=np.asarray(actions,dtype=np.float32),rewards=np.asarray(rewards),success_flags=np.asarray(successes,dtype=bool))
    new_json(ep/'RESULT.json',row);arms[arm]=row
   if row['status']=='technical_failure':break
  qualified=bool(state_check and state_check['passed'] and all(a in arms and arms[a]['terminal'] and arms[a]['status']=='complete' for a in ['N','Post']) and arms['N']['success'] is False and arms['Post']['success'] is True)
  target=Path(CONFIG['output_root'])
  if not qualified:target=target/'unqualified'
  target=target/unit['task']/unit['candidate_id'];target.mkdir(parents=True,exist_ok=False)
  for arm,name in [('N','baseline.mp4'),('Post','post.mp4')]:
   source=out/arm/'recording.mp4'
   if source.exists():shutil.copyfile(source,target/name)
  progress('encoding',sum(x['steps'] for x in arms.values()),'encoding',False)
  verification=compose(target,unit,arms,prepared['post_intervention_cuts'],boundary) if qualified else None
  metadata=dict(candidate=unit,recording_modes=dict(N='policy_rerun',Post='saved_action_replay'),historical=prepared['historical'],saved_Post_actions=prepared['post_trajectory'],Post_intervention_steps=prepared['post_intervention_cuts'],initial_state=initial,initial_state_check=state_check,arms=arms,qualified=qualified,verification=verification,model=CONFIG['model_id'],loss='L11',fit_seed=9101,assets=str(ROOT/'ASSETS.json'),sampling='fixed outcome-selected qualitative candidates; not a new random evaluation',scientific_success_rate_update=False,fps=30,speed=1,physics_hz=400,control_hz=30,action_scale=.015,utc=utc())
  new_json(target/'metadata.json',metadata)
  result=dict(candidate_id=unit['candidate_id'],task=unit['task'],H=unit['H'],source_id=unit['source_id'],status='qualified' if qualified else 'technical_failure' if technical else 'unqualified',qualified=qualified,output=str(target),metadata=str(target/'metadata.json'),technical=technical,arms={k:{f:v.get(f) for f in ('status','success','terminal','steps','terminal_reason')} for k,v in arms.items()})
 except BaseException as exc:
  result=dict(candidate_id=unit['candidate_id'],task=unit['task'],H=unit['H'],source_id=unit['source_id'],status='technical_failure',qualified=False,error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()),arms=arms)
 finally:
  if engine:
   try:engine.rpc('close')
   except BaseException:pass
   finally:engine.connection.close()
  if egl:
   try:egl.finish_resident()
   except BaseException as exc:result['cleanup_error']=repr(exc);result['status']='technical_failure';result['qualified']=False
  result.update(utc=utc(),elapsed_seconds=time.monotonic()-start)
  new_json(out/'PAIR_RESULT.json',result);progress('finished',sum(x.get('steps',0) for x in arms.values()),'complete',False)
 return 0 if result['status'] in ('qualified','unqualified') else 3
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);raise SystemExit(main(p.parse_args().config))
