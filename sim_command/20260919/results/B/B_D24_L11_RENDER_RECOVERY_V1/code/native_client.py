"""Resident Smol native K10 collector and deployment, with a separate encoder."""
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
from common import claim_attempt,parent_path,boundary,AdmissionStop,episode_deadline,remaining_seconds

def main(config_path):
    cfg=read(config_path);out=Path(cfg['output']);boundary(admission=True)
    assert cfg['phase']=='evaluate', 'evaluation-only recovery; no collection or training'
    import numpy as np
    import torch
    from lerobot.envs.metaworld import MetaworldEnv
    from experiments.standalone_ablation_20260918.candidates import project_solo
    from experiments.native10_training_20260916.protocol import seed_for
    torch.set_num_threads(1);started=time.monotonic()
    connection=Client(cfg['socket_path'],family='AF_UNIX',authkey=bytes.fromhex(cfg['ipc_auth']))
    counters=collections.Counter();stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,stop)
    def check(admit=False):
        boundary(admission=admit)
        if stopping:raise AdmissionStop('owned native worker stop')
    def rpc(kind,**fields):
        connection.send(dict(kind=kind,branch_id=cfg['branch_id'],**fields))
        if not connection.poll(900):raise TimeoutError('external encoder request timeout')
        reply=connection.recv()
        if not reply.get('ok'):raise RuntimeError('encoder: '+reply.get('error','unknown'))
        counters['model_service_RPC_seconds']+=reply.get('seconds',0)
        return reply
    def observation(obs):
        frame=np.asarray(obs['pixels']);prop=np.asarray(obs['agent_pos'],np.float32)
        if frame.shape!=(480,480,3) or frame.dtype!=np.uint8 or not frame.any() or prop.shape!=(4,) or not np.isfinite(prop).all():raise ValueError('invalid real observation')
        return dict(pixels=frame,agent_pos=prop)
    def encode(obs,source):return rpc('encode',source_id=source,observations=[observation(obs)])['spatial'][0]
    def generate(obs,instruction,candidate_seed=None,gradient=None):
        reply=rpc('generate',observation=observation(obs),instruction=instruction,candidate_seed=candidate_seed,gradient=gradient is not None)
        raw,stats=reply['raw'],reply['stats']
        counters['policy_queries']+=1;counters['policy_flow_calls']+=stats['flow_calls']
        counters['candidate_queries' if candidate_seed is not None else 'natural_queries']+=1
        counters['policy_seconds']+=reply['policy_seconds']
        return raw,stats
    def reset(env,source):
        check();seed=source['reset_seed'];random.seed(seed);np.random.seed(seed);env._env.seed(seed)
        obs,_=env.reset(seed=seed);rpc('policy_reset',seed=source['policy_seed'])
        physics=dict(timestep=float(env._env.model.opt.timestep),frame_skip=int(env._env.frame_skip),action_scale=float(env._env.action_scale))
        if abs(physics['timestep']-.0025)>1e-9 or physics['frame_skip']!=5 or abs(physics['action_scale']-.01)>1e-9:raise ValueError('frozen Smol native physics changed')
        counters['environment_resets']+=1;observation(obs)
        return obs,physics,np.asarray(env._env._last_rand_vec).copy()
    def step_env(env,raw):
        check();t=time.monotonic();result=env.step(raw);counters['environment_seconds']+=time.monotonic()-t;counters['environment_steps']+=1
        observation(result[0]);return result
    def terminal(value):return bool(value[2] or value[3] or value[4].get('success',value[4].get('is_success',False)))
    matching=read(cfg['engine_config'])['matching']
    native_slopes=np.asarray(rpc('policy_info')['native_action_slopes'])
    atomic_json(out/'MODEL_READY.json',dict(status='shared_model_connected',process=process_identity(),at_utc=utc(),
        base='SmolVLA050000',raw_H=50,native_K=10,NFE=10,model_replicas_in_this_process=0,branch_id=cfg['branch_id'],slot=cfg['slot'],native_action_slopes=native_slopes[0].tolist()))

    def evaluate_source(env,source,method):
        sid=source['source_id'];claim=claim_attempt(method+'/'+sid,phase='evaluate',method=method,source_id=sid)
        ep=ROOT/'episodes'/hashlib.sha256(claim['unit_id'].encode()).hexdigest();ep.mkdir(parents=True,exist_ok=False)
        row=dict(source,model='SmolVLA',H=10,mode='G0-multi',unit_id=claim['unit_id'],method=method,status='entered',success=None,steps=0,interventions=0,first_cut=None,events=[],claim=claim,
            trigger_mode='G0-multi',adaptation='Smol native bridge; frozen Smol D/G0; Q-free R or new selected full Q',Q_loss=CONFIG.get('selected_loss'),Q_fit_seed=CONFIG.get('selected_fit_seed'),Q_assets=CONFIG.get('selected_Q_assets'),protocol='Mesa80Hz/.01/nativeK10/rawH50/NFE10')
        new_json(ep/'ENTERED.json',row);before=dict(counters);begin=time.monotonic();actions=[];rewards=[];successes=[]
        try:
            with episode_deadline():
                obs,physics,_=reset(env,source);row['physics']=physics
                snapshot=rpc('begin',source_id=sid,instruction=env.task_description);encoder_before=snapshot['counters']
                frames=collections.deque(maxlen=5);props=collections.deque(maxlen=5);raw=None;age=0;locked_until=0
                for t in range(300):
                    check();observed=observation(obs);frames.append(observed['pixels'].copy());props.append(observed['agent_pos'].copy())
                    if raw is None or age==10:raw,_=generate(obs,env.task_description);age=0
                    if t>=locked_until and t%5==0 and min(10-age,300-t)>=5:
                        monitor=rpc('monitor',source_id=sid,step=t,observations=[dict(pixels=f,agent_pos=p) for f,p in zip(frames,props)],
                            props=list(props),past_actions=actions[-4:],next_five=raw[age:age+5])
                        legal=len(frames)==5 and len(actions)>=4 and age>0 and t+10<=300
                        trigger=bool(legal and monitor['gate']>.05)
                        event=dict(step=t,queue_age=age,gate=monitor['gate'],member_gates=monitor['member_gates'],legal_cut=legal,trigger=trigger)
                        if trigger:
                            cs=seed_for('D24_designated_a0',sid,source['policy_seed'],t,namespace=cfg['seed_namespace'])
                            a0,a0_stats=generate(obs,env.task_description,cs);raw=a0
                            if method in ['Post','Velocity']:
                                rpc('objective',source_id=sid,step=t,raw_plan=a0)
                                if method=='Post':
                                    reply=rpc('gradient',source_id=sid,step=t);direction=np.asarray(reply['gradient'])*native_slopes**2
                                else:
                                    guided,gstats=generate(obs,env.task_description,cs,lambda command:rpc('gradient',source_id=sid,step=t,commands=command))
                                    if gstats['noise_sha256']!=a0_stats['noise_sha256']:raise ValueError('a0/guided native noise mismatch')
                                    direction=np.clip(guided[:10],-1,1).astype(float)-np.clip(a0[:10],-1,1).astype(float)
                                    event['guidance']=gstats
                                raw,matched,arrays=project_solo(a0,direction,matching);event['matching']=matched
                                np.savez_compressed(ep/('intervention_'+str(t)+'.npz'),raw_base=a0,corrected=raw,direction=direction,actual_delta=arrays['actual_delta'])
                            age=0;locked_until=t+10;row['interventions']+=1
                            if row['first_cut'] is None:row['first_cut']=t
                            event.update(candidate_seed=cs,commit_until=locked_until,restore_native_K=10,Q_acceptance_gate=False)
                        row['events'].append(event)
                    action=raw[age].copy();age+=1;result=step_env(env,action);obs=result[0]
                    actions.append(np.clip(action,-1,1));rewards.append(float(result[1]));successes.append(bool(result[4].get('success',result[4].get('is_success',False))));row['steps']=t+1
                    if t%10==0:atomic_json(out/'PROGRESS.json',dict(at_utc=utc(),phase='active_rollout',source_id=sid,unit_id=claim['unit_id'],step=t+1,active_environment=True))
                    if terminal(result) or t==299:row.update(status='complete',success=successes[-1],terminal_reason='success' if successes[-1] else 'environment_terminal' if terminal(result) else 'step_cap');break
                row['encoder_counters']={k:v-encoder_before.get(k,0) for k,v in rpc('snapshot')['counters'].items()}
        except BaseException as exc:row.update(status='budget_truncated' if isinstance(exc,AdmissionStop) else 'technical_failure',success=None,error=repr(exc),traceback=traceback.format_exc())
        row.update(at_utc=utc(),elapsed_seconds=time.monotonic()-begin,counters={k:v-before.get(k,0) for k,v in counters.items()})
        np.savez_compressed(ep/'trajectory.npz',actions=np.asarray(actions,np.float32),rewards=np.asarray(rewards,np.float32),success_flags=np.asarray(successes,bool))
        from publication_data import finite_values
        new_json(ep/'RESULT.json',finite_values(row))
        new_json(ep/'SUMMARY_ROW.json',finite_values({k:v for k,v in row.items() if k!='events'}))
        atomic_json(out/'PROGRESS.json',dict(at_utc=utc(),phase='evaluate',source_id=sid,method=method,status=row['status']))
        if row['status']!='complete':raise RuntimeError('recorded evaluation error; no implicit replay')
    fatal=None
    try:
        for method in cfg['methods']:
            grouped=collections.OrderedDict()
            for source in cfg['sources_by_method'].get(method,[]):grouped.setdefault(source['task'],[]).append(source)
            for task,sources in grouped.items():
                check(True);construction_seed=cfg['construction_seed_by_task'][task];random.seed(construction_seed);np.random.seed(construction_seed);env=MetaworldEnv(task=task,obs_type='pixels_agent_pos')
                try:
                    for source in sources:evaluate_source(env,source,method)
                finally:env.close()
        new_json(out/'CLIENT_COMPUTE_DONE.json',dict(at_utc=utc()));rpc('close')
    except BaseException as exc:
        fatal=dict(error=repr(exc),traceback=traceback.format_exc());raise
    finally:
        connection.close();atomic_json(out/'CLIENT_RESULT.json',dict(status='failed' if fatal else 'complete',fatal=fatal,
            counters=dict(counters),at_utc=utc(),elapsed_seconds=time.monotonic()-started,peak_allocated_bytes=None,peak_memory_missing_reason='models reside in shared GPU services'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);main(p.parse_args().config)
