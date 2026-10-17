"""Isolated simulator process. Replays actual saved raw prefixes for each fork."""
import argparse,collections,json,os,pickle,random,time,traceback
from pathlib import Path
from multiprocessing.connection import Client
import paths
from paths import ROOT
from common import read,write,check,claim,seed,uid,identity,terminal_path

class Proxy:
    def __init__(self,slot,branch):
        self.conn=Client(str(Path(read(ROOT/'CONFIG.json')['local_dir'])/f'gpu{slot}.sock'),family='AF_UNIX');self.branch=branch;self.reset_metrics()
    def reset_metrics(self):self.metrics={}
    def rpc(self,kind,**kw):
        t=time.monotonic();self.conn.send(dict(kind=kind,branch=self.branch,**kw))
        if not self.conn.poll(1200):raise TimeoutError('model RPC 1200 seconds')
        r=self.conn.recv()
        if not r['ok']:raise RuntimeError(r['error']+'\n'+r.get('traceback',''))
        m=self.metrics.setdefault(kind,dict(count=0,service_seconds=0.,wait_seconds=0.,samples=[]));m['count']+=1;m['service_seconds']+=r.get('seconds',0);m['wait_seconds']+=time.monotonic()-t;m['samples'].append(r.get('seconds',0))
        return r.get('value')
    def close(self):
        try:self.rpc('close')
        finally:self.conn.close()

def arrays(path):
    import numpy as np
    with np.load(path,allow_pickle=False) as z:return {k:z[k].copy() for k in z.files}

class Simulation:
    def __init__(self,source):
        import numpy as np
        from lerobot.envs.metaworld import MetaworldEnv
        self.source=source;e=source['env_seed'];random.seed(e);np.random.seed(e)
        self.env=MetaworldEnv(task=source['task'],camera_name='corner2',obs_type='pixels_agent_pos',render_mode='rgb_array',observation_width=480,observation_height=480,max_path_length=300)
        n=self.env._env;random.seed(e);np.random.seed(e);n.seed(e);n.action_scale=.015;n.frame_skip=5
        self.obs,_=self.env.reset(seed=e);n.action_scale=.015;self.steps=0;self.seconds=0.
        if abs(float(n.model.opt.timestep)-1/400)>1e-10:raise ValueError('physics timestep is not 400 Hz')
        if self.obs['agent_pos'].shape!=(4,):raise ValueError('expected four physical action/proprio coordinates')
    def step(self,a):
        import numpy as np
        n=self.env._env;t=self.steps;n.frame_skip=((t+1)*400)//30-(t*400)//30
        begin=time.monotonic();raw,r,done,trunc,info=n.step(np.asarray(a,np.float32));self.obs=self.env._format_raw_obs(raw);self.steps+=1;self.seconds+=time.monotonic()-begin
        if n._did_see_sim_exception or not np.isfinite(self.obs['agent_pos']).all():raise RuntimeError('simulator exception/nonfinite observation')
        if self.obs['pixels'].shape!=(480,480,3):raise ValueError('image shape')
        return dict(success=bool(info.get('success',False)),done=bool(done or trunc),reward=float(r))
    def close(self):
        from render_context import close_environment
        close_environment(self.env)

def save_state(dest,sim,frames,props,actions,raw,age,H,observed,rng,source,score):
    import numpy as np,mujoco
    dest.mkdir(parents=True,exist_ok=False)
    n=sim.env._env;spec=mujoco.mjtState.mjSTATE_INTEGRATION
    state=np.empty(mujoco.mj_stateSize(n.model,spec));mujoco.mj_getState(n.model,n.data,state,spec)
    np.savez_compressed(dest/'state.npz',pixels=sim.obs['pixels'],agent_pos=sim.obs['agent_pos'],frames=np.asarray(frames),props=np.asarray(props),prefix=np.asarray(actions,np.float32),raw=raw,age=np.asarray(age),H=np.asarray(H),natural_rng=rng,simulator_integration_state=state,**{'observed__'+k:v for k,v in observed.items()})
    with (dest/'rng.pkl').open('wb') as f:pickle.dump(dict(python=random.getstate(),numpy=np.random.get_state(),environment=n.np_random.bit_generator.state),f)
    write(dest/'STATE.json',dict(source=source,cut=sim.steps,state_path=str(dest/'state.npz'),score=score,budget_remaining=300-sim.steps,restore='reset and replay saved raw prefix, then check current observation',rng_path=str(dest/'rng.pkl')))

def d5_score(pending,t,history,actions):
    import numpy as np
    if pending is None or pending['step']!=t-5:return None
    if not np.array_equal(np.asarray(actions[-5:],np.float32),pending['actions']):raise ValueError('D5 prediction action window changed')
    return float(np.mean(((pending['prediction']-history[None])/pending['scale'][:,None])**2))

def rollout(sim,proxy,source,out,*,H=10,trigger='none',threshold=None,method='R',capture=False,initial=None):
    import numpy as np
    frames=collections.deque(maxlen=5);props=collections.deque(maxlen=5);actions=[];events=[];states=[];raw=None;age=0;activeH=H;locked=0;pending=None;interventions=0;last_intervention=-1000
    language=proxy.rpc('begin',instruction=source['instruction'],observation=sim.obs,output=str(out))
    proxy.rpc('stream',seed=source['policy_seed'])
    first_pixels=sim.obs['pixels'].copy()
    if initial is not None:
        frames.extend(initial['frames'][:-1]);props.extend(initial['props'][:-1]);actions=list(initial['prefix']);raw=initial['queue'];activeH=len(raw);locked=sim.steps+(activeH if initial['commit'] else 0)
        proxy.rpc('stream',seed=initial['suffix_seed'],state=initial.get('natural_rng'))
    proxy.reset_metrics();begin=time.monotonic();lastbeat=0.;warm_remaining={'plan':1,'monitor':1,'intervene':1};timing_samples={};decision_seconds=0.
    def call(kind,**kw):
        v=proxy.rpc(kind,**kw)
        if warm_remaining.get(kind,0):warm_remaining[kind]-=1
        else:timing_samples.setdefault(kind,[]).append(proxy.metrics[kind]['samples'][-1])
        return v
    while sim.steps<300:
        check();t=sim.steps
        if time.monotonic()-begin>7200:raise TimeoutError('unit exceeded two hours')
        frames.append(sim.obs['pixels'].copy());props.append(sim.obs['agent_pos'].copy())
        if raw is None or age==activeH:raw=call('plan',observation=sim.obs);age=0;activeH=H
        legal=t>=locked and t%5==0 and len(frames)==5 and age>0 and min(activeH-age,300-t)>=5 and t+10<=300
        monitor_needed=capture or trigger in ['G0','D5','risk','nod']
        at_monitor=t>=locked and t%5==0 and min(activeH-age,300-t)>=5
        scores=None;chosen=False
        if monitor_needed and at_monitor:
            scores=call('monitor',frames=list(frames),props=list(props),past=actions[-4:],language=language,step=t,next_five=raw[age:age+5].copy(),heads=not capture,signal='all' if capture else trigger)
            decision_start=time.monotonic();d5=d5_score(pending,t,scores['actual'],actions);scores['D5']=d5
            if legal and trigger in ['G0','D5','risk','nod']:
                val=scores[trigger];chosen=val is not None and val>threshold
            decision_seconds+=time.monotonic()-decision_start
            scalar={k:scores.get(k) for k in ['G0','D5','risk','nod']}
            if capture and legal:
                observed=proxy.rpc('get_context');folder=ROOT/'pool'/source['source_id']/f'cut{t:03d}'
                folder.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(folder/'context.npz',next_five=raw[age:age+5],**observed)
                write(folder/'SCORE.json',dict(source=source,cut=t,score=scalar,context_path=str(folder/'context.npz')))
                if t in source['cuts']:
                    dest=folder/'snapshot';save_state(dest,sim,list(frames),list(props),actions,raw,age,activeH,observed,proxy.rpc('rng'),source,scalar);states.append(str(dest/'STATE.json'))
            if legal:events.append(dict(step=t,**scalar,selected=chosen))
        if legal and trigger=='random':chosen=seed('online_random',source['source_id'],t)/float(2**63-1)<threshold
        if legal and trigger=='periodic':chosen=(t-5)%threshold==0
        if initial is not None and t==initial['cut']:chosen=False
        if chosen:
            if method=='Post' and scores is None:raise ValueError('Post requires current causal context')
            raw=call('intervene',observation=sim.obs,method=method,seed=seed('online_a0',source['source_id'],t));age=0;activeH=10;locked=t+10;interventions+=1;last_intervention=t;pending=None
        elif scores is not None and scores['prediction'] is not None:
            pending=dict(step=t,prediction=scores['prediction'],scale=scores['scale'],actions=raw[age:age+5].copy())
        a=raw[age].copy();age+=1;step=sim.step(a);actions.append(a)
        if capture and sim.steps==6:
            if np.std(first_pixels)<1 or np.std(sim.obs['pixels'])<1:raise ValueError('empty/constant camera observation')
            write(out/'FIRST_PLANNED_OBSERVATION.json',dict(passed=True,source=source['source_id'],step=6,first_pixel_std=float(np.std(first_pixels)),current_pixel_std=float(np.std(sim.obs['pixels'])),mean_frame_difference=float(np.abs(first_pixels.astype(float)-sim.obs['pixels'].astype(float)).mean()),finite_proprio=bool(np.isfinite(sim.obs['agent_pos']).all()),renderer='own process/context/framebuffer'))
            from PIL import Image
            Image.fromarray(first_pixels).save(out/'frame0.png');Image.fromarray(sim.obs['pixels']).save(out/'frame6.png')
        if time.monotonic()-lastbeat>10:
            write(out/'PROGRESS.json',dict(time=time.time(),step=sim.steps,interventions=interventions,source=source['source_id']));lastbeat=time.monotonic()
        if step['success'] or step['done'] or sim.steps==300:
            if capture:np.savez_compressed(out/'raw_trajectory.npz',actions=np.asarray(actions,np.float32))
            metrics=proxy.metrics
            return dict(status='complete',success=step['success'],steps=sim.steps,terminal_reason='success' if step['success'] else 'done' if step['done'] else 's300',interventions=interventions,states=states,events=events,metrics=metrics,warm_timing_samples=timing_samples,policy_calls=sum(metrics.get(k,{}).get('count',0) for k in ['plan','intervene']),monitors=metrics.get('monitor',{}).get('count',0),action_gradients=interventions if method=='Post' else 0,inference_seconds=sum(m['service_seconds'] for m in metrics.values())+decision_seconds,trigger_compute_seconds=decision_seconds,rpc_seconds=sum(m['wait_seconds'] for m in metrics.values()),environment_seconds=sim.seconds,elapsed_seconds=time.monotonic()-begin,remaining_budget_reissued=False)

def execute(job,proxy,out):
    import numpy as np
    kind=job['kind'];s=job['source'];sim=None
    try:
        if kind in ['collect','closed']:
            sim=Simulation(s)
            return rollout(sim,proxy,s,out,H=job.get('H',10),trigger=job.get('trigger','none'),threshold=job.get('threshold'),method=job.get('method','R'),capture=kind=='collect')
        if kind in ['bank','score']:
            if kind=='score':
                scores=[]
                for folder in sorted((ROOT/'pool'/s['source_id']).glob('cut*')):
                    old=read(folder/'SCORE.json');z=arrays(folder/'context.npz');nf=z.pop('next_five')
                    proxy.rpc('begin',instruction=s['instruction'],observation={},output=str(out))
                    scored=proxy.rpc('saved_score',observed=z,next_five=nf)
                    vals={k:scored[k] for k in ['G0','risk','nod']};vals['D5']=old['score']['D5'];scores.append(dict(cut=old['cut'],**vals))
                    write(folder/'FINAL_SCORE.json',dict(source=s,cut=old['cut'],score=vals))
                return dict(status='complete',success=None,scores=scores,scientific_outcome='scores_only')
            st=read(job['state']);z=arrays(st['state_path']);observed={k[10:]:v for k,v in z.items() if k.startswith('observed__')}
            proxy.rpc('begin',instruction=s['instruction'],observation=dict(pixels=z['pixels'],agent_pos=z['agent_pos']),output=str(out))
            bank=proxy.rpc('bank',observed=observed,seed=seed('a0',s['source_id'],st['cut'],job['rep']))
            np.savez_compressed(out/'plans.npz',**bank.pop('plans'));write(out/'BANK.json',bank)
            return dict(status='complete',success=None,scientific_outcome='new_actions_generated',bank_path=str(out/'plans.npz'),metadata_path=str(out/'BANK.json'),**{k:bank[k] for k in ['metric_action_max_difference','metric_slopes']})
        if kind=='branch':
            st=read(job['state']);z=arrays(st['state_path']);sim=Simulation(s)
            for a in z['prefix']:
                step=sim.step(a)
                if step['done'] or step['success']:raise ValueError('restored prefix terminates before saved cut')
            if sim.steps!=st['cut']:raise ValueError('cut clock')
            np.testing.assert_allclose(sim.obs['agent_pos'],z['agent_pos'],atol=1e-6,rtol=0)
            difference=float(np.abs(sim.obs['pixels'].astype(float)-z['pixels'].astype(float)).mean())
            if difference>1e-3:raise ValueError(f'restored current image differs: {difference}')
            if job['arm']=='continue':queue=z['raw'][int(z['age']):int(z['H'])].copy();commit=False
            else:queue=arrays(job['bank_path'])[job['arm']][:job.get('C',10)].copy();commit=True
            initial=dict(frames=z['frames'],props=z['props'],prefix=z['prefix'],queue=queue,commit=commit,cut=st['cut'],suffix_seed=seed('suffix',s['source_id'],st['cut'],job['rep']))
            # First suffix draw preserves the captured policy RNG; other draws are paired resamplings.
            if job['rep']==0:initial['natural_rng']=z['natural_rng']
            suffix=job['suffix'];r=rollout(sim,proxy,s,out,H=10,trigger='G0' if suffix=='deploy10' else 'none',threshold=.05,method='Post' if suffix=='deploy10' else 'R',initial=initial)
            r.update(cut=st['cut'],restored_image_mean_abs_difference=difference,original_episode_budget=300,initial_prefix_length=len(queue),initial_correction_gradient_calls=job.get('gradient_calls',0),initial_replan_calls=0 if job['arm']=='continue' else 1)
            return r
        raise ValueError(kind)
    finally:
        if sim is not None:sim.close()

def main(config):
    cfg=read(config);out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True);slot=cfg['slot']
    if cfg['kind'] in ['collect','closed','branch']:
        base=read(ROOT/'BASE.json');base['native']['device']=base['device_list'][slot]
        from resident_egl import ResidentEGL
        egl=ResidentEGL(base['native'],out,lambda:None);egl.prepare()
        from gymnasium.envs.mujoco import mujoco_rendering
        egl.install_resident_rendering(mujoco_rendering)
        from render_context import install
        install(mujoco_rendering,restore_buffer=True)
    else:egl=None
    proxy=Proxy(slot,cfg['branch']);write(out/'READY.json',identity());failures=0
    try:
        for job in cfg['jobs']:
            rp=terminal_path(job)
            if rp.exists():continue
            try:claim(job)
            except FileExistsError:continue
            dest=rp.parent;dest.mkdir(parents=True,exist_ok=True);write(dest/'ENTERED.json',dict(job=job,process=identity()))
            begin=time.time()
            try:r=execute(job,proxy,dest)
            except Exception as exc:
                failures+=1;r=dict(status='technical_failure',success=None,error=repr(exc),traceback=traceback.format_exc())
            write(rp,dict(job=job,**r,wall_seconds=time.time()-begin,finished=time.time()))
            write(out/'HEARTBEAT.json',dict(time=time.time(),last_job=job['id'],status=r['status'],failures=failures))
            if failures>=2:break
    finally:
        proxy.close()
        if egl is not None:egl.finish_resident()
        write(out/'RESULT.json',dict(time=time.time(),failures=failures))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('config');main(p.parse_args().config)
