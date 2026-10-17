"""Independent physical environment and controller; shared model RPC only."""
import argparse
import copy
import random
import time
import traceback
import hashlib
from pathlib import Path
from multiprocessing.connection import Client
import paths
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity
from admission import boundary,claim_unit,AdmissionStop

class Runtime:
    def __init__(self,env,observation):self.env=env;self.observation=observation;self.steps=0;self.seconds=0.
    def frame(self):return self.observation['pixels']
    def proprio(self):
        import numpy as np
        return np.asarray(self.observation['agent_pos'],np.float32)
    def step(self,action,step):
        import numpy as np
        boundary()
        if step!=self.steps:raise ValueError('physical step clock')
        native=self.env._env;native.frame_skip=((step+1)*400)//30-(step*400)//30
        begin=time.monotonic();before=float(native.data.time)
        obs,reward,done,truncated,info=native.step(np.asarray(action,np.float32))
        if abs(float(native.data.time)-before-native.frame_skip/400)>1e-9:raise ValueError('physics cadence')
        if native._did_see_sim_exception:raise RuntimeError('native simulator exception')
        self.observation=self.env._format_raw_obs(obs);self.steps+=1;self.seconds+=time.monotonic()-begin
        return dict(reward=float(reward),done=bool(done or truncated),success=bool(info.get('success',False)))

class EngineProxy:
    def __init__(self,cfg):
        self.cfg=cfg;self.namespace=CONFIG['seed_namespace'];self.connection=Client(cfg['socket_path'],family='AF_UNIX',authkey=bytes.fromhex(cfg['ipc_auth']))
    def rpc(self,kind,**fields):
        self.connection.send(dict(kind=kind,branch_id=self.cfg['branch_id'],**fields))
        if not self.connection.poll(900):raise TimeoutError('shared model RPC deadline')
        reply=self.connection.recv()
        if not reply.get('ok'):raise RuntimeError(reply.get('error','model service failed')+' '+reply.get('traceback',''))
        return reply
    def begin(self,runtime,instruction,out):self.runtime=runtime;self.rpc('begin',instruction=instruction,episode_out=str(out),observation=runtime.observation)
    def language(self):return self.rpc('language')['value']
    def start_natural_stream(self,seed):self.rpc('start_natural_stream',seed=seed)
    def propose_natural(self):
        r=self.rpc('propose_natural',observation=self.runtime.observation);return r['plan'],r['stats']
    def context(self,frames,props,past,language,step):return self.rpc('context',frames=frames,props=props,past=past,language=language,step=step)['context_id']
    def monitor(self,observed,next_five):return self.rpc('monitor',next_five=next_five)['value']
    def intervene(self,method,observed,seed,step):
        r=self.rpc('intervene',method=method,seed=seed,step=step,observation=self.runtime.observation);return r['plan'],r['stats']

def main(config_path):
    cfg=read(config_path);out=Path(cfg['output']);boundary(True);base=copy.deepcopy(read(ROOT/'config/BASE.json'))
    base['native']['device']=base['device_list'][cfg['slot']]
    from resident_egl import ResidentEGL
    egl=ResidentEGL(base['native'],out,lambda:None);egl.prepare()
    import numpy as np
    from gymnasium.envs.mujoco import mujoco_rendering
    from lerobot.envs.metaworld import MetaworldEnv
    from controller import run_episode
    from publication_data import finite_values
    egl.install_resident_rendering(mujoco_rendering);engine=EngineProxy(cfg)
    new_json(out/'MODEL_READY.json',dict(status='shared_model_connected',utc=utc(),process=process_identity(),slot=cfg['slot'],branch_id=cfg['branch_id'],model_replicas_in_this_process=0))
    failed=0
    try:
        for unit in cfg['units']:
            boundary(True);claim=claim_unit(unit);ep=ROOT/'episodes'/hashlib.sha256(unit['unit_id'].encode()).hexdigest();ep.mkdir(exist_ok=False)
            row=dict(unit,status='entered',success=None,terminal=False,claim=claim,steps=0,episode_started_utc=utc(),technical_failure=None,action_dim=4,control_hz=30,physics_hz=400,action_scale=.015)
            new_json(ep/'ENTERED.json',row);env=None;runtime=None;start=time.monotonic();last=[0.]
            def emit(kind,event):
                if kind!='step':
                    from recorder import record
                    record(ep/'events.jsonl',dict(unit_id=unit['unit_id'],source_id=unit['source_id'],method=unit['method'],H=unit['H']),kind,event)
                if time.monotonic()-last[0]>5:
                    atomic_json(out/'PROGRESS.json',dict(utc=utc(),unit_id=unit['unit_id'],source_id=unit['source_id'],step=event['step'],phase='active_rollout',active_environment=True));last[0]=time.monotonic()
            try:
                env=MetaworldEnv(task=unit['task'],camera_name='corner2',obs_type='pixels_agent_pos',render_mode='rgb_array',observation_width=480,observation_height=480,max_path_length=300)
                native=env._env;seed=unit['env_seed'];random.seed(seed);np.random.seed(seed);native.seed(seed);native.action_scale=.015;native.frame_skip=5
                reset_begin=time.monotonic();obs,_=env.reset(seed=seed);row['reset_seconds']=time.monotonic()-reset_begin;native.action_scale=.015
                runtime=Runtime(env,obs);engine.begin(runtime,env.task_description,ep)
                result=run_episode(runtime,engine,unit,unit['method'],unit['H'],emit,stop=lambda:time.time()>=CONFIG['absolute_wall_deadline_unix'],mode=unit['mode'])
                np.savez_compressed(ep/'trajectory.npz',**result.pop('arrays'));row.update(result);row['terminal']=True
                metrics=engine.rpc('snapshot');row.update(counters=metrics['counts'],numeric_counters=metrics['numeric'],inference_seconds=sum(v['stats']['seconds'] for v in row['plans']),inference_seconds_scope='sampling/correction service time; context service and RPC wait separately included in wall time')
            except BaseException as exc:
                failed+=1;row.update(status='technical_failure',success=None,technical_failure=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
            finally:
                if env is not None:env.close()
            row.update(episode_finished_utc=utc(),elapsed_seconds=time.monotonic()-start,environment_seconds=runtime.seconds if runtime else None,steps=runtime.steps if runtime else 0)
            new_json(ep/'RESULT.json',finite_values(row));new_json(ep/'SUMMARY_ROW.json',finite_values({k:v for k,v in row.items() if k not in ('events','plans')}))
            atomic_json(out/'PROGRESS.json',dict(utc=utc(),unit_id=unit['unit_id'],status=row['status'],phase='between_units',active_environment=False))
            if failed>=2:break
    finally:
        try:engine.rpc('close')
        finally:engine.connection.close();egl.finish_resident()
        atomic_json(out/'CLIENT_RESULT.json',dict(utc=utc(),status='partial' if failed else 'complete',technical_failures=failed))
    return 3 if failed else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);raise SystemExit(main(p.parse_args().config))
