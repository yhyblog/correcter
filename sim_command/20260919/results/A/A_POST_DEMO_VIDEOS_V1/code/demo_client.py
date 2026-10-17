"""One owned recording arm, isolated environment and EGL, resident model RPC."""
import argparse,copy,hashlib,os,random,signal,time,traceback
from pathlib import Path
from multiprocessing.connection import Client
import paths
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity
from admission import boundary,claim_unit,AdmissionClosed,before_cutoff
from demo_video import initial_record,RGBWriter,finite_values

def check_render_log(folder):
    p=Path(folder)/'stderr.log'
    if not p.exists():return
    with p.open('rb') as f:
        f.seek(0,2);end=f.tell();f.seek(max(0,end-65536));text=f.read().decode('utf8','replace')
    if any(s in text for s in ('0x506','0x0506','GL_INVALID_FRAMEBUFFER_OPERATION','OpenGL error')):raise RuntimeError('actual render error in own stderr')

class Runtime:
    def __init__(self,env,observation,writer,folder):
        self.env=env;self.observation=observation;self.steps=0;self.seconds=0.;self.writer=writer;self.folder=folder
        writer.write(0,observation['pixels'])
    def frame(self):return self.observation['pixels']
    def proprio(self):
        import numpy as np
        return np.asarray(self.observation['agent_pos'],np.float32)
    def step(self,action,step):
        import numpy as np
        boundary()
        if step!=self.steps:raise ValueError('physical step clock')
        n=self.env._env;n.frame_skip=((step+1)*400)//30-(step*400)//30
        start=time.monotonic();before=float(n.data.time)
        obs,reward,done,truncated,info=n.step(np.asarray(action,np.float32))
        if abs(float(n.data.time)-before-n.frame_skip/400)>1e-9:raise ValueError('physics cadence')
        if n._did_see_sim_exception:raise RuntimeError('native simulator exception')
        self.observation=self.env._format_raw_obs(obs);self.steps+=1;self.seconds+=time.monotonic()-start
        if self.steps%5==0:check_render_log(self.folder)
        self.writer.write(self.steps,self.observation['pixels'])
        return dict(reward=float(reward),done=bool(done or truncated),terminated=bool(done),truncated=bool(truncated),success=bool(info.get('success',False)))

class EngineProxy:
    def __init__(self,cfg):
        self.cfg=cfg;self.namespace=CONFIG['seed_namespace'];self.unit=None;self.runtime=None;self.audit_frames={}
        self.connection=Client(cfg['socket_path'],family='AF_UNIX',authkey=bytes.fromhex(cfg['ipc_auth']))
    def rpc(self,kind,**fields):
        u=self.unit or {};s=self.runtime.steps if self.runtime else 0
        self.connection.send(dict(kind=kind,branch_id=self.cfg['branch_id'],unit_id=u.get('unit_id'),source_id=u.get('source_id'),client_pid=os.getpid(),observation_step=s,rgb_sha256=self.audit_frames.get(s),**fields))
        if not self.connection.poll(900):raise TimeoutError('shared model RPC deadline')
        r=self.connection.recv()
        if not r.get('ok'):raise RuntimeError(r.get('error','model RPC failed')+' '+r.get('traceback',''))
        return r
    def begin(self,u,runtime,out,digest):
        self.unit=u;self.runtime=runtime;self.audit_frames={0:digest}
        self.rpc('begin',instruction=u['source']['instruction'],episode_out=str(out),observation=runtime.observation)
    def language(self):return self.rpc('language')['value']
    def start_natural_stream(self,seed):self.rpc('start_natural_stream',seed=seed)
    def propose_natural(self):
        r=self.rpc('propose_natural',observation=self.runtime.observation);return r['plan'],r['stats']
    def context(self,frames,props,past,language,step):return self.rpc('context',frames=frames,props=props,past=past,language=language,step=step)['context_id']
    def monitor(self,observed,next_five):return self.rpc('monitor',context_id=observed,next_five=next_five)['value']
    def intervene(self,method,observed,seed,step):
        r=self.rpc('intervene',method=method,context_id=observed,seed=seed,step=step,observation=self.runtime.observation);return r['plan'],r['stats']

def main(config_path):
    cfg=read(config_path);out=Path(cfg['output']);unit=cfg['unit'];attempt=cfg['attempt'];boundary(True)
    claim=claim_unit(unit,attempt);ep=ROOT/'episodes'/unit['uid_hash']/('attempt_%d'%attempt);ep.mkdir(parents=True,exist_ok=False)
    row=dict(unit,status='entered',success=None,terminal=False,claim=claim,attempt=attempt,steps=0,episode_started_utc=utc(),technical_failure=None,action_dim=4,control_hz=30,physics_hz=400,action_scale=.015,renderer='NVIDIA_EGL',environment_process=process_identity(),recording_mode='policy_rerun',new_scientific_evaluation_units=0)
    new_json(ep/'ENTERED.json',row);base=copy.deepcopy(read(ROOT/'config/BASE.json'));base['native']['device']=base['device_list'][cfg['slot']]
    egl=env=engine=runtime=writer=None;cleanup=[];start=time.monotonic();last=[0.]
    def interrupted(*_):raise AdmissionClosed('owned recording arm interrupted')
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,interrupted)
    try:
        from resident_egl import ResidentEGL
        egl=ResidentEGL(base['native'],out,lambda:None);egl.prepare()
        import numpy as np
        from gymnasium.envs.mujoco import mujoco_rendering
        from lerobot.envs.metaworld import MetaworldEnv
        from controller import run_episode
        from rpc_state import validate_observation
        egl.install_resident_rendering(mujoco_rendering);engine=EngineProxy(cfg)
        new_json(out/'MODEL_READY.json',dict(status='shared_model_connected',utc=utc(),process=process_identity(),slot=cfg['slot'],branch_id=cfg['branch_id'],model_replicas_in_this_process=0))
        init=time.monotonic();env=MetaworldEnv(task=unit['task'],camera_name='corner2',obs_type='pixels_agent_pos',render_mode='rgb_array',observation_width=480,observation_height=480,max_path_length=300);row['environment_initialization_seconds']=time.monotonic()-init
        native=env._env
        if float(native.model.opt.timestep)!=1/400:raise ValueError('physics timestep changed')
        seed=unit['env_seed'];random.seed(seed);np.random.seed(seed);native.seed(seed);native.action_scale=.015;native.frame_skip=5
        reset=time.monotonic();obs,_=env.reset(seed=seed);row['reset_seconds']=time.monotonic()-reset;native.action_scale=.015;check_render_log(out)
        validate_observation(obs)
        if obs['pixels'].min()==obs['pixels'].max():raise ValueError('constant actual RGB')
        initial=initial_record(unit,native,obs,ep);gate=ROOT/'pairs'/unit['candidate_id']/'INITIAL_CHECK.json'
        atomic_json(out/'PROGRESS.json',dict(utc=utc(),phase='waiting_pair_initial_check',unit_id=unit['unit_id'],step=0,active_environment=True))
        wait_until=time.monotonic()+600
        while not gate.exists():
            boundary()
            if time.monotonic()>wait_until:raise TimeoutError('peer initial state not available')
            time.sleep(.2)
        verdict=read(gate)
        if not verdict['passed']:
            row.update(status='initial_state_rejected',terminal=False,success=None,initial_check=verdict,retry_allowed=False)
        else:
            # Every arm must match the initially approved pair, including a
            # technical correction; no policy call can precede this gate.
            if initial['rgb_sha256']!=verdict['N_initial_rgb_sha256']:raise ValueError('retry initial frame differs from approved pair')
            writer=RGBWriter(ep/'recording.mp4');runtime=Runtime(env,obs,writer,out)
            engine.begin(unit,runtime,ep,initial['rgb_sha256']);row['first_policy_request_utc']=utc()
            def emit(kind,event):
                if kind!='step':
                    from recorder import record
                    record(ep/'events.jsonl',dict(unit_id=unit['unit_id'],source_id=unit['source_id'],method=unit['method'],H=unit['H']),kind,event)
                if time.monotonic()-last[0]>3:
                    atomic_json(out/'PROGRESS.json',dict(utc=utc(),unit_id=unit['unit_id'],source_id=unit['source_id'],step=event['step'],interventions=event.get('interventions'),phase='actual_recording',active_environment=True));last[0]=time.monotonic()
            result=run_episode(runtime,engine,unit,unit['method'],unit['H'],emit,stop=lambda:not before_cutoff(),mode=unit['mode'])
            np.savez_compressed(ep/'trajectory.npz',**result.pop('arrays'));row.update(result);row['terminal']=True
            check_render_log(out);metrics=engine.rpc('snapshot');row.update(counters=metrics['counts'],numeric_counters=metrics['numeric'],initial_check=verdict)
            if unit['method']=='N' and any(row['counters'][k] for k in ('contexts','D_forward','G0_forward','interventions','action_gradients','Q_ensemble_forward')):raise ValueError('N arm performed correction work')
    except BaseException as exc:
        row.update(status='technical_failure',success=None,technical_failure=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()),retry_allowed=isinstance(exc,(ConnectionResetError,BrokenPipeError,EOFError)))
    finally:
        if writer is not None:
            try:row['video']=writer.finish()
            except BaseException as exc:
                row['video_error']=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());row['recording_incomplete']=True
        if env is not None:
            try:env.close()
            except BaseException as exc:cleanup.append(dict(stage='env_close',type=type(exc).__name__,message=str(exc)))
        if engine is not None:
            try:engine.rpc('close')
            except BaseException as exc:cleanup.append(dict(stage='RPC_close',type=type(exc).__name__,message=str(exc)))
            engine.connection.close()
        if egl is not None:
            try:egl.finish_resident()
            except BaseException as exc:cleanup.append(dict(stage='EGL_cleanup',type=type(exc).__name__,message=str(exc)))
    row.update(episode_finished_utc=utc(),elapsed_seconds=time.monotonic()-start,environment_seconds=runtime.seconds if runtime else None,steps=runtime.steps if runtime else 0,cleanup=cleanup,extra_render_calls=0,recorded_policy_observation_only=True)
    new_json(ep/'RESULT.json',finite_values(row));new_json(out/'CLIENT_RESULT.json',dict(utc=utc(),status=row['status'],result=str(ep/'RESULT.json'),cleanup=cleanup))
    atomic_json(out/'PROGRESS.json',dict(utc=utc(),phase='exited',active_environment=False,status=row['status'],step=row['steps']))
    return 3 if row['status']=='technical_failure' or cleanup or row.get('recording_incomplete') else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);raise SystemExit(main(p.parse_args().config))
