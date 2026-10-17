"""24 independent live rollout contexts, one resident model, one GPU thread.

Every iterator advances one original control step. All model/gradient operations
remain batch1 and finish before switching contexts; no gradient is averaged.
"""
import argparse,copy,random,signal,time,traceback,sys
from collections import Counter
from pathlib import Path
import paths
from paths import ROOT
from qio import read,new_json,atomic_json,utc,process_identity
from admission import authority,admit_unit,admissions_allowed,before_cutoff,AdmissionClosed
from runtime import Counts,Runtime

def main():
 a=argparse.ArgumentParser();a.add_argument('--slot',type=int,required=True);a.add_argument('--root',required=True);args=a.parse_args()
 wr=Path(args.root);base=read(ROOT/'config/BASE.json');cfg=copy.deepcopy(base);cfg['device']=base['device_list'][args.slot];cfg['native']['device']=cfg['device']
 authority();stopping=False;fatal=None;egl=None;state=None;engine=None;active=[];counts=Counts();peak=0;completed=technical=0;iterations=0;numeric_delta=Counter()
 def stop(*_):
  nonlocal stopping
  stopping=True
 for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,stop)
 new_json(wr/'STARTED.json',dict(utc=utc(),process=process_identity(),GPU=cfg['device']))
 load_start=time.monotonic()
 try:
  from resident_egl import ResidentEGL
  egl=ResidentEGL(cfg['native'],wr,lambda:None);egl.prepare()
  import numpy as np
  import torch
  device=egl.bind_policy(torch);torch.set_num_threads(4)
  from numeric_setup import initialize
  state=initialize(cfg,wr,counts,device)
  from numeric_engine import Engine
  engine=Engine(state,read(ROOT/'config/CONFIG.json'),wr)
  from gymnasium.envs.mujoco import mujoco_rendering
  from lerobot.envs.metaworld import MetaworldEnv
  from controller import iter_episode
  from recorder import record
  egl.install_resident_rendering(mujoco_rendering)
  new_json(wr/'MODEL_READY.json',dict(utc=utc(),process=process_identity(),GPU=cfg['device'],model_replicas=1,logical_context_target=24,batch_size=1,gradient_batch_size=1,load_seconds=time.monotonic()-load_start,policy_loader=str(wr/'policy_loader.json'),loss='L11',fit_seed=9101,GPU_reserved_bytes=torch.cuda.max_memory_reserved(device),GPU_allocated_bytes=torch.cuda.max_memory_allocated(device)))

  def rng_save():return (random.getstate(),np.random.get_state(),torch.get_rng_state(),torch.cuda.get_rng_state(device))
  def rng_restore(saved):
   random.setstate(saved[0]);np.random.set_state(saved[1]);torch.set_rng_state(saved[2]);torch.cuda.set_rng_state(saved[3],device)

  def activate(branch):
   rng_restore(branch['rng']);engine.set_episode(branch['runtime'],branch['unit']['source']['instruction'],branch['out']);engine.counts=branch['counts']
   if branch.get('natural_generator') is not None:engine.natural_generator=branch['natural_generator'];engine.natural_seed=branch['natural_seed']

  def snapshot(branch):
   branch['rng']=rng_save();branch['natural_generator']=getattr(engine,'natural_generator',None);branch['natural_seed']=getattr(engine,'natural_seed',None)

  def emit_for(branch,kind,event):
   if kind!='step':record(branch['out']/'events.jsonl',dict(source_id=branch['unit']['source_id'],cell_id=branch['unit']['cell_id'],H=branch['unit']['H'],mode=branch['unit']['mode'],branch=branch['unit']['method']),kind,event)
   if kind=='step':branch['last_step']=event['step']

  def finish(branch,row,error=None):
   nonlocal completed,technical
   unit=branch['unit'];result=dict(unit_id=unit['unit_id'],source_id=unit['source_id'],task=unit['task'],env_seed=unit['env_seed'],policy_seed=unit['policy_seed'],ordinal=unit['ordinal'],split=unit['split'],repeat=0,model='pi05',method=unit['method'],mode=unit['mode'],H=unit['H'],loss='L11',fit_seed=9101,cell_id=unit['cell_id'],stage='MAIN' if unit['mode']=='G0-multi' else 'ONCE',success=None,status='technical_failure',terminal=False,steps=branch.get('last_step',0),started_utc=branch['started_utc'],attempt_ordinal=branch['claim']['stage_ordinal'],attempt_index=0,renderer='NVIDIA_EGL')
   if row is not None:
    arrays=row.pop('arrays');np.savez_compressed(branch['out']/'trajectory.npz',**arrays);result.update(row);result['terminal']=True
   if error:result['technical_failure']=error
   try:branch['env'].close()
   except BaseException as e:
    result.update(status='technical_failure',success=None,terminal=False,cleanup_failure=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
   result.update(finished_utc=utc(),elapsed_seconds=time.monotonic()-branch['started'],environment_initialization_seconds=branch['initialization_seconds'],reset_seconds=branch['reset_seconds'],environment_seconds=branch['runtime'].seconds,counters=branch['counts'],numeric_counters=dict(branch['numeric']),cooperative_active_seconds=branch['active_seconds'],elapsed_scope='end-to-end shared-model rollout including scheduling interleave',batch_size=1,model_replicas_per_GPU=1,logical_contexts_per_GPU_target=24,costs_unknown_reason=None)
   new_json(branch['out']/'RESULT.json',result)
   if result['status']=='complete':completed+=1
   else:technical+=1
   return result

  def create(unit):
   claim=admit_unit(unit,args.slot);dest=ROOT/'episodes'/unit['uid_hash'];dest.mkdir(exist_ok=False);started=time.monotonic();started_utc=utc()
   new_json(dest/'ENTERED.json',dict(utc=started_utc,unit=unit,claim=claim,GPU=cfg['device'],scientific_attempt=True))
   env=None
   try:
    # Fixed MT1(seed42)/task0 constructor; the planned reset is source-specific.
    t=time.monotonic();env=MetaworldEnv(task=unit['task'],camera_name='corner2',obs_type='pixels_agent_pos',render_mode='rgb_array',observation_width=480,observation_height=480,max_path_length=300);init=time.monotonic()-t
    native=env._env
    if float(native.model.opt.timestep)!=1/400:raise ValueError('physics timestep changed')
    seed=unit['env_seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed);native.seed(seed);native.action_scale=.015;native.frame_skip=5;state['policy'].reset()
    t=time.monotonic();obs,_=env.reset(seed=seed);reset=time.monotonic()-t;native.action_scale=.015;runtime=Runtime(env,obs)
    pixels=np.asarray(runtime.frame())
    if not (wr/'FIRST_PLANNED_OBSERVATION.json').exists():
     if pixels.ndim!=3 or pixels.shape[-1]!=3 or pixels.min()==pixels.max():raise ValueError('invalid planned RGB observation')
     new_json(wr/'FIRST_PLANNED_OBSERVATION.json',dict(utc=utc(),unit_id=unit['unit_id'],shape=list(pixels.shape),minimum=int(pixels.min()),maximum=int(pixels.max()),extra_render_calls=0))
    branch=dict(unit=unit,claim=claim,out=dest,env=env,runtime=runtime,counts={k:0 for k in engine.counts},numeric=Counter(),active_seconds=0.,rng=rng_save(),started=started,started_utc=started_utc,initialization_seconds=init,reset_seconds=reset,last_step=0)
    branch['iterator']=iter_episode(runtime,engine,unit['source'],unit['method'],unit['H'],lambda kind,event:emit_for(branch,kind,event),lambda:stopping or not before_cutoff(),mode=unit['mode'])
    return branch
   except BaseException as e:
    error=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    if env is not None:env.close()
    new_json(dest/'RESULT.json',dict(unit_id=unit['unit_id'],cell_id=unit['cell_id'],source_id=unit['source_id'],method=unit['method'],mode=unit['mode'],H=unit['H'],loss='L11',fit_seed=9101,status='technical_failure',success=None,terminal=False,technical_failure=error,elapsed_seconds=time.monotonic()-started,calls=None,calls_missing_reason='failed before controller entry',utc=utc()))
    raise

  for method in ['Post','Velocity']:
   command=wr/(method+'_GO.json')
   while not command.exists() and not stopping:
    if (wr/'STOP.json').exists():stopping=True;break
    time.sleep(.5)
   if stopping:break
   units=read(ROOT/'worker_units'/f'{method}_{args.slot}.json');pending=iter(units);exhausted=False;lastbeat=0
   while active or not exhausted:
    if (wr/'STOP.json').exists():exhausted=True
    while len(active)<24 and not exhausted and not stopping:
     if not admissions_allowed():exhausted=True;break
     try:unit=next(pending)
     except StopIteration:exhausted=True;break
     try:active.append(create(unit));peak=max(peak,len(active))
     except AdmissionClosed:exhausted=True;break
    for branch in list(active):
     activate(branch);before=dict(counts.entered);t=time.monotonic();done=False;row=None;error=None
     try:next(branch['iterator'])
     except StopIteration as e:done=True;row=e.value
     except BaseException as e:done=True;error=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
     finally:
      branch['active_seconds']+=time.monotonic()-t
      for k,v in counts.entered.items():branch['numeric'][k]+=v-before.get(k,0)
      snapshot(branch)
     iterations+=1
     if done:
      engine.verify();finish(branch,row,error);active.remove(branch)
      if error:raise RuntimeError('technical rollout failure requires private diagnosis: '+error['message'])
    now=time.monotonic()
    if now-lastbeat>=5:
     atomic_json(wr/'PROGRESS.json',dict(utc=utc(),process=process_identity(),method=method,model_replicas=1,batch_size=1,logical_target=24,active_environments=len(active),peak_active_environments=peak,completed=completed,technical=technical,control_iterations=iterations,branches=[dict(unit_id=x['unit']['unit_id'],step=x['last_step']) for x in active],GPU_reserved_bytes=torch.cuda.max_memory_reserved(device),GPU_allocated_bytes=torch.cuda.max_memory_allocated(device)));lastbeat=now
    if stopping and not active:break
    if not active and (exhausted or stopping):break
   new_json(wr/(method+'_DONE.json'),dict(utc=utc(),method=method,completed_total=completed,technical_total=technical,all_assigned_entered=exhausted and all((ROOT/'episodes'/u['uid_hash']/'RESULT.json').exists() for u in units)))
  engine.verify()
 except BaseException as e:fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
 finally:
  cleanup=[]
  for branch in active:
   try:finish(branch,None,dict(type='OwnedWorkerDrain',message='own worker exiting after technical fault or bounded stop; not scientific failure'))
   except BaseException as e:cleanup.append(dict(type=type(e).__name__,message=str(e)))
  if engine is not None:
   try:engine.hook.close()
   except BaseException as e:cleanup.append(dict(type=type(e).__name__,message=str(e)))
  if egl is not None:
   try:egl.finish_resident()
   except BaseException as e:cleanup.append(dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
  new_json(wr/'WORKER_EXIT.json',dict(utc=utc(),process=process_identity(),fatal=fatal,cleanup=cleanup,model_replicas=1,peak_active_environments=peak,completed=completed,technical=technical,numeric=counts.snapshot()))
 return 3 if fatal or cleanup else 0

if __name__=='__main__':sys.exit(main())
