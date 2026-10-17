"""Resident X raw30, natural H20/H30 and corrective C10 evaluation."""
import argparse
import collections
import contextlib
import hashlib
from multiprocessing.connection import Client
from pathlib import Path
import random
import signal
import time
import traceback
import paths
from paths import ROOT,WORKSPACE,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity
from common import boundary,AdmissionStop
from admission import claim_unit
from horizon_queue import HorizonQueue

def main(config_path):
    cfg=read(config_path);out=Path(cfg['output']);boundary(admission=True)
    import numpy as np
    import torch
    from lerobot.envs.metaworld import MetaworldEnv
    from render_context import install, evidence, close_environment
    install(native_lifetime=True)
    from lerobot.policies.factory import get_policy_class,make_pre_post_processors
    from native_velocity import NativeVelocityBridge
    from projector import project_solo
    from experiments.native10_training_20260916.protocol import seed_for
    checkpoint=Path(cfg['checkpoint']);assert hashlib.sha256((checkpoint/'config.json').read_bytes()).hexdigest()==cfg['checkpoint_config_sha256']
    assert (checkpoint/'model.safetensors').stat().st_size==cfg['checkpoint_weight_bytes']
    torch.set_num_threads(2);torch.backends.cuda.matmul.allow_tf32=True;started=time.monotonic()
    policy=get_policy_class('xvla').from_pretrained(checkpoint,local_files_only=True,strict=True)
    policy.config.n_action_steps=10;policy.config.num_denoising_steps=10
    assert policy.config.chunk_size==30 and tuple(policy.config.output_features['action'].shape)==(4,)
    assert tuple(policy.config.input_features['observation.state'].shape)==(4,)
    policy.to('cuda').eval().requires_grad_(False);pre,post=make_pre_post_processors(policy.config,pretrained_path=checkpoint)
    bridge=NativeVelocityBridge(policy,post,'xvla')
    connection=Client(cfg['socket_path'],family='AF_UNIX',authkey=bytes.fromhex(cfg['ipc_auth'])) if cfg['encoder_required'] else None
    counters=collections.Counter();stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,stop)
    def check(admit=False):
        boundary(admission=admit)
        if stopping or time.time()>=CONFIG['absolute_wall_deadline_unix']-90:raise AdmissionStop('owned native worker stop or finite deadline')
    def rpc(kind,**fields):
        if connection is None:raise RuntimeError('N must never use auxiliary RPC')
        counters['encoder_RPC_entered']+=1
        connection.send(dict(kind=kind,**fields))
        if not connection.poll(600):raise TimeoutError('external encoder request timeout')
        reply=connection.recv()
        if not reply.get('ok'):raise RuntimeError('encoder: '+reply.get('error','unknown'))
        counters['encoder_RPC_seconds']+=reply.get('seconds',0)
        return reply
    def observation(obs):
        frame=np.asarray(obs['pixels']);prop=np.asarray(obs['agent_pos'],np.float32)
        if frame.shape!=(480,480,3) or frame.dtype!=np.uint8 or not frame.any() or prop.shape!=(4,) or not np.isfinite(prop).all():raise ValueError('invalid real observation')
        return dict(pixels=frame,agent_pos=prop)
    def encode(obs,source):return rpc('encode',source_id=source,observations=[observation(obs)])['spatial'][0]
    def generate(obs,instruction,candidate_seed=None,gradient=None):
        t=time.monotonic();sample={'observation.image':torch.from_numpy(np.ascontiguousarray(obs['pixels'])).permute(2,0,1).float()/255,
            'observation.state':torch.as_tensor(obs['agent_pos'],dtype=torch.float32),'task':instruction}
        scope=torch.random.fork_rng(devices=[0]) if candidate_seed is not None else contextlib.nullcontext()
        counters['policy_queries_entered']+=1
        bridge.begin(gradient)
        with scope:
            if candidate_seed is not None:torch.manual_seed(candidate_seed);torch.cuda.manual_seed(candidate_seed)
            with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
                native=policy.predict_action_chunk(pre(sample))
                assert native.shape==(1,30,4)
                raw=np.stack([post(native[:,i]).reshape(-1).float().cpu().numpy() for i in range(30)]).astype(np.float32)
        stats=bridge.finish();counters['policy_queries']+=1;counters['policy_flow_calls']+=stats['flow_calls']
        counters['candidate_queries' if candidate_seed is not None else 'natural_queries']+=1
        counters['policy_seconds']+=time.monotonic()-t
        if raw.shape!=(30,4) or not np.isfinite(raw).all():raise ValueError('invalid raw30')
        return raw,stats
    def reset(env,source):
        check();seed=source['reset_seed'];random.seed(seed);np.random.seed(seed);env._env.seed(seed)
        obs,_=env.reset(seed=seed);policy.reset();torch.manual_seed(source['policy_seed']);torch.cuda.manual_seed(source['policy_seed'])
        physics=dict(timestep=float(env._env.model.opt.timestep),frame_skip=int(env._env.frame_skip),action_scale=float(env._env.action_scale))
        if abs(physics['timestep']-.0025)>1e-9 or physics['frame_skip']!=5 or abs(physics['action_scale']-.01)>1e-9:raise ValueError('frozen X native physics changed')
        counters['environment_resets']+=1;observation(obs)
        return obs,physics,np.asarray(env._env._last_rand_vec).copy()
    def step_env(env,raw):
        check();t=time.monotonic();result=env.step(raw);counters['environment_seconds']+=time.monotonic()-t;counters['environment_steps']+=1
        observation(result[0])
        if not np.isfinite(float(result[1])) or getattr(env._env,'_did_see_sim_exception',False):raise RuntimeError('nonfinite reward or actual simulator exception')
        return result
    def terminal(value):return bool(value[2] or value[3] or value[4].get('success',value[4].get('is_success',False)))
    matching=read(cfg['engine_config'])['matching']
    native_slopes=None
    if cfg['methods'][0] in ('Post','Velocity'):
        with torch.inference_mode(False),torch.enable_grad():
            leaf=torch.zeros((10,4),device='cuda',requires_grad=True)
            physical=post(leaf);native_slopes=torch.autograd.grad(physical.sum(),leaf)[0].detach().cpu().numpy()
        if not np.isfinite(native_slopes).all() or np.any(native_slopes==0):raise ValueError('native inverse action transform invalid')
    atomic_json(out/'MODEL_READY.json',dict(status='ready',process=process_identity(),at_utc=utc(),
        base='X-VLA030000',raw_plan_length=30,normal_H=[20,30],commitment_C=10,base_n_action_steps_metadata=10,NFE=10,model_resident=True,phase=cfg['phase'],
        base_parameters=sum(p.numel() for p in policy.parameters()),load_seconds=time.monotonic()-started,
        native_action_slopes=native_slopes[0].tolist() if native_slopes is not None else None,encoder_required=cfg['encoder_required'],base_allocated_bytes=int(torch.cuda.memory_allocated())))

    ZERO_ENCODER=('visual_observations','visual_encoder_calls','language_encoder_calls','D_forward_calls','G0_forward_calls','monitor_calls','Q_ensemble_forward_calls','Q_member_forward_calls','action_gradient_calls')
    def evaluate_unit(unit):
        source=unit['runtime_source'];sid=source['source_id'];uid=unit['unit_id'];method=unit['method'];H=unit['H']
        claim=claim_unit(unit);ep=ROOT/'evaluation'/unit['cell_id']/sid;ep.mkdir(parents=True,exist_ok=False)
        row=dict(source,unit_id=uid,cell_id=unit['cell_id'],model='X-VLA',H=H,normal_H=H,C=unit['C'],raw_plan_length=30,loss=unit['Q_loss'],fit_seed=unit['Q_fit_seed'],Q_members=unit['Q_members'],method=method,status='entered',success=None,steps=0,interventions=0,first_cut=None,events=[],plans=[],claim=claim,mode=unit['mode'],current_paper=unit['current_paper'],context_key=uid,repeat=None,repeat_reason='fixed source manifest has no independent repeat field',adaptation='frozen X base/D/G0/L11; normal_H separated from C10',protocol='Mesa80Hz/.01/corner2_480/NFE10',max_interventions=unit['max_interventions'])
        new_json(ep/'ENTERED.json',row);begin=time.monotonic();actions=[];rewards=[];successes=[];env=None;encoder_begun=False
        row['encoder_counters']={k:0 for k in ZERO_ENCODER}
        from observation_evidence import ObservationEvidence
        proof=ObservationEvidence(unit,ep,out,cfg['slot']<8 and uid==cfg['units'][0]['unit_id'])
        try:
            seed=cfg['constructor_seeds'][source['task']];random.seed(seed);np.random.seed(seed)
            counters['environment_constructors_entered']+=1
            env=MetaworldEnv(task=source['task'],obs_type='pixels_agent_pos')
            obs,physics,randvec=reset(env,source);row['physics']=physics;row['initial_randomization_vector']=randvec.tolist()
            if connection is not None:
                snap=rpc('begin',source_id=uid,scientific_source_id=sid,instruction=env.task_description);encoder_before=snap['counters_before'];encoder_begun=True
            frames=collections.deque(maxlen=5);props=collections.deque(maxlen=5);queue=HorizonQueue(H,method)
            for t in range(300):
                check()
                if time.monotonic()-begin>1800:raise AdmissionStop('episode wall deadline')
                observed=observation(obs);frames.append(observed['pixels'].copy());props.append(observed['agent_pos'].copy())
                proof.record(env,observed,t)
                if queue.needs_plan():
                    raw,stats=generate(obs,env.task_description);queue.natural(raw,t)
                    row['plans'].append(dict(step=t,kind='natural',execution_limit=H,raw_length=30,stats=stats))
                if queue.can_monitor(t,len(frames),len(actions)):
                    monitor=rpc('monitor',source_id=uid,step=t,observations=[dict(pixels=f,agent_pos=p) for f,p in zip(frames,props)],props=list(props),past_actions=actions[-4:],next_five=queue.raw[queue.age:queue.age+5])
                    trigger=bool(monitor['gate']>.05)
                    event=dict(step=t,normal_H=H,queue_limit=queue.limit,queue_age=queue.age,old_queue_remaining=queue.limit-queue.age,history_frames=len(frames),history_actions=len(actions),gate=monitor['gate'],member_gates=monitor['member_gates'],legal_cut=True,trigger=trigger,locked_until_before=queue.locked_until)
                    if trigger:
                        cs=seed_for('D24_designated_a0',sid,source['policy_seed'],t,namespace=cfg['seed_namespace'])
                        a0,a0_stats=generate(obs,env.task_description,cs);raw=a0
                        row['plans'].append(dict(step=t,kind='candidate_a0',candidate_seed=cs,execution_limit=10,raw_length=30,stats=a0_stats))
                        if method in ('Post','Velocity'):
                            rpc('objective',source_id=uid,step=t,raw_plan=a0)
                            if method=='Post':
                                reply=rpc('gradient',source_id=uid,step=t);direction=np.asarray(reply['post_direction']);event['Post_metric']=reply['Post_metric']
                            else:
                                guided,gstats=generate(obs,env.task_description,cs,lambda command:rpc('gradient',source_id=uid,step=t,commands=command))
                                if gstats['noise_sha256']!=a0_stats['noise_sha256']:raise ValueError('a0/guided native noise mismatch')
                                direction=np.clip(guided[:10],-1,1).astype(float)-np.clip(a0[:10],-1,1).astype(float)
                                event['guidance']=gstats
                                row['plans'].append(dict(step=t,kind='guided',candidate_seed=cs,execution_limit=10,raw_length=30,stats=gstats))
                            raw,matched,arrays=project_solo(a0,direction,matching);event['matching']=matched
                            np.savez_compressed(ep/f'intervention_cut_{t:03d}.npz',raw_base=a0,corrected=raw,direction=direction,actual_delta=arrays['actual_delta'])
                        queue.intervene(raw,t,event);row['interventions']+=1
                        if row['first_cut'] is None:row['first_cut']=t
                        event.update(intervention_index=row['interventions'],candidate_seed=cs,Q_acceptance_gate=False)
                    row['events'].append(event)
                action=queue.action().copy();result=step_env(env,action);queue.advanced(t);obs=result[0]
                actions.append(np.clip(action,-1,1));rewards.append(float(result[1]));successes.append(bool(result[4].get('success',result[4].get('is_success',False))));row['steps']=t+1
                done=terminal(result) or t==299
                if done:row.update(status='complete',success=successes[-1],terminal_reason='success' if successes[-1] else 'environment_terminal' if terminal(result) else 'step_cap')
                yield dict(step=t+1,source_id=sid,unit_id=uid)
                if done:break
        except BaseException as exc:
            if row['status']=='complete':row['post_terminal_error']=repr(exc)
            else:row.update(status='budget_truncated' if isinstance(exc,(AdmissionStop,GeneratorExit)) else 'technical_failure',success=None,error=repr(exc),traceback=traceback.format_exc())
        if encoder_begun:
            try:
                snap=rpc('snapshot',source_id=uid)
                row['encoder_counters'].update({k:v-encoder_before.get(k,0) for k,v in snap['counters'].items()})
                row['encoder_meter']=snap.get('meter');row['encoder_cost_complete']=True
            except BaseException as exc:
                row['encoder_cost_complete']=False;row['encoder_cost_error']=repr(exc)
                row['encoder_counters']=None
        else:row['encoder_cost_complete']=connection is None
        row.update(at_utc=utc(),elapsed_seconds=time.monotonic()-begin,counters=dict(counters))
        np.savez_compressed(ep/'trajectory.npz',actions=np.asarray(actions,np.float32),rewards=np.asarray(rewards,np.float32),success_flags=np.asarray(successes,bool))
        if env is not None:row['render_context']=evidence(env)
        new_json(ep/'RESULT.json',row)
        if env is not None:close_environment(env)
        if row['status']=='technical_failure':
            from faults import pause
            pause(uid,ep/'RESULT.json',row.get('error'))
        atomic_json(out/'PROGRESS.json',dict(at_utc=utc(),phase='evaluate',unit_id=uid,source_id=sid,method=method,H=H,status=row['status']))
        return row
    fatal=None;active=[]
    try:
        assert cfg['phase']=='evaluate'
        from cooperative import capture_rng,restore_rng
        queue=list(cfg['units']);completed=[];peak=0;last=0.;ticks=0;all_counters=collections.Counter()
        while active or queue:
            while queue and len(active)<cfg['branches'] and not stopping:
                try:check(True)
                except AdmissionStop:break
                unit=queue.pop(0)
                active.append(dict(unit=unit,generator=evaluate_unit(unit),rng=capture_rng(),counters=collections.Counter(),step=0))
            peak=max(peak,len(active))
            if not active:break
            for branch in list(active):
                restore_rng(branch['rng']);counters=branch['counters']
                try:
                    progress=next(branch['generator']);branch['step']=progress['step'];ticks+=1
                except AdmissionStop:
                    queue.insert(0,branch['unit']);branch['generator'].close();active.remove(branch)
                except StopIteration as done:
                    completed.append(dict(unit_id=branch['unit']['unit_id'],status=done.value['status']))
                    active.remove(branch);all_counters.update(counters)
                finally:branch['rng']=capture_rng()
            if time.monotonic()-last>=5:
                atomic_json(out/'CONCURRENCY.json',dict(at_utc=utc(),slot=cfg['slot'],active_contexts=len(active),peak_contexts=peak,advancing_contexts=[dict(unit_id=b['unit']['unit_id'],source_id=b['unit']['source_id'],H=b['unit']['H'],step=b['step']) for b in active],completed=len(completed),pending=len(queue),physical_step_advances=ticks,model_replicas=1,external_encoder_replicas=int(cfg['encoder_required']),batch_size=1,peak_GPU_bytes=int(torch.cuda.max_memory_allocated()),RSS_high_water_KiB=__import__('resource').getrusage(__import__('resource').RUSAGE_SELF).ru_maxrss));last=time.monotonic()
        counters=all_counters
        new_json(out/'CONTEXTS_COMPLETE.json',dict(at_utc=utc(),completed=completed,pending_units=[u['unit_id'] for u in queue],peak_active_contexts=peak,physical_step_advances=ticks))
        new_json(out/'CLIENT_COMPUTE_DONE.json',dict(at_utc=utc()))
        if connection is not None:rpc('close')
    except BaseException as exc:
        fatal=dict(error=repr(exc),traceback=traceback.format_exc());raise
    finally:
        for branch in active:
            try:
                restore_rng(branch['rng']);counters=branch['counters'];branch['generator'].close()
            except BaseException:pass
        if connection is not None:connection.close()
        atomic_json(out/'CLIENT_RESULT.json',dict(status='failed' if fatal else 'complete',fatal=fatal,counters=dict(counters),at_utc=utc(),elapsed_seconds=time.monotonic()-started,peak_allocated_bytes=int(torch.cuda.max_memory_allocated()),encoder_required=cfg['encoder_required']))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);main(p.parse_args().config)
