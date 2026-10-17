import time, json, traceback
from collections import Counter
from qio import utc, new_json, atomic_json

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


def execute_episode(state,engine,env,source,H,method,out,stop):
    import random
    import numpy as np
    import torch
    from controller import run_episode
    native=env._env;start=time.monotonic();before=dict(engine.counts);last=[0.];runtime=None
    result=dict(source_id=source['source_id'],task=source['task'],split='test',ordinal=source['ordinal'],
        env_seed=source['env_seed'],policy_seed=source['policy_seed'],method=method,H=H,success=None,
        status='entered',steps=0,episode_started_utc=utc(),terminal=False,technical_failure=None,
        action_dim=4,control_hz=30,physics_hz=400,action_scale=.015,repeat=0,max_interventions=1)
    new_json(out/'ENTERED.json',result)
    def emit(kind,event):
        if kind=='monitor':
            with (out/'events.jsonl').open('a') as f:f.write(json.dumps(event,allow_nan=False,sort_keys=True)+'\n')
        if time.monotonic()-last[0]>10:
            atomic_json(out.parent.parent/'EPISODE_PROGRESS.json',dict(source_id=source['source_id'],step=event['step'],H=H,method=method,utc=utc()));last[0]=time.monotonic()
    try:
        # Same reset order and explicit noise-generator seed as the accepted N runner.
        seed=source['env_seed'];random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
        native.seed(seed);native.action_scale=.015;native.frame_skip=5;state['policy'].reset()
        t=time.monotonic();obs,_=env.reset(seed=seed);result['reset_seconds']=time.monotonic()-t
        result['initial_randomization_vector']=np.asarray(native._last_rand_vec).tolist()
        native.action_scale=.015;runtime=Runtime(env,obs);engine.set_episode(runtime,source['instruction'],out)
        row=run_episode(runtime,engine,source,method,H,emit,stop)
        np.savez_compressed(out/'trajectory.npz',**row.pop('arrays'));result.update(row)
        result.update(terminal=True,policy_calls=row['sampling_calls'],inference_seconds=sum(x['stats']['seconds'] for x in row['plans']),
            inference_seconds_scope='generation and correction only; context/DG0 included in episode wall time')
        engine.verify()
    except BaseException as e:
        result.update(status='technical_failure',success=None,technical_failure=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc()))
    result.update(elapsed_seconds=time.monotonic()-start,episode_finished_utc=utc(),environment_seconds=runtime.seconds if runtime else 0,
        counters={k:v-before.get(k,0) for k,v in engine.counts.items()},steps=runtime.steps if runtime else 0)
    new_json(out/'RESULT.json',result);return result

