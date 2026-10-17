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
from paths import ROOT,WORKSPACE
from qio import read,new_json,atomic_json,utc,process_identity
from common import claim_attempt,parent_path,boundary,AdmissionStop,episode_deadline,remaining_seconds

def main(config_path):
    cfg=read(config_path);out=Path(cfg['output']);boundary(admission=True)
    assert cfg['phase']=='evaluate', 'evaluation-only recovery; no collection or training'
    import numpy as np
    import torch
    from lerobot.envs.metaworld import MetaworldEnv
    from lerobot.policies.factory import get_policy_class,make_pre_post_processors
    from native_velocity import NativeVelocityBridge
    from experiments.standalone_ablation_20260918.candidates import project_solo
    from experiments.native10_training_20260916.protocol import seed_for
    checkpoint=Path(cfg['checkpoint']);assert hashlib.sha256((checkpoint/'config.json').read_bytes()).hexdigest()==cfg['checkpoint_config_sha256']
    assert (checkpoint/'model.safetensors').stat().st_size==cfg['checkpoint_weight_bytes']
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=True;started=time.monotonic()
    policy=get_policy_class('smolvla').from_pretrained(checkpoint,local_files_only=True,strict=True)
    policy.config.n_action_steps=10;policy.config.num_steps=10
    assert policy.config.chunk_size==50 and tuple(policy.config.output_features['action'].shape)==(4,)
    policy.to('cuda').eval().requires_grad_(False);pre,post=make_pre_post_processors(policy.config,pretrained_path=checkpoint)
    bridge=NativeVelocityBridge(policy,post,'smolvla')
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
        bridge.begin(gradient)
        with scope:
            if candidate_seed is not None:torch.manual_seed(candidate_seed);torch.cuda.manual_seed(candidate_seed)
            with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
                native=policy.predict_action_chunk(pre(sample))
                assert native.shape==(1,50,4)
                raw=np.stack([post(native[:,i]).reshape(-1).float().cpu().numpy() for i in range(50)]).astype(np.float32)
        stats=bridge.finish();counters['policy_queries']+=1;counters['policy_flow_calls']+=stats['flow_calls']
        counters['candidate_queries' if candidate_seed is not None else 'natural_queries']+=1
        counters['policy_seconds']+=time.monotonic()-t
        if raw.shape!=(50,4) or not np.isfinite(raw).all():raise ValueError('invalid raw50')
        return raw,stats
    def reset(env,source):
        check();seed=source['reset_seed'];random.seed(seed);np.random.seed(seed);env._env.seed(seed)
        obs,_=env.reset(seed=seed);policy.reset();torch.manual_seed(source['policy_seed']);torch.cuda.manual_seed(source['policy_seed'])
        physics=dict(timestep=float(env._env.model.opt.timestep),frame_skip=int(env._env.frame_skip),action_scale=float(env._env.action_scale))
        if abs(physics['timestep']-.0025)>1e-9 or physics['frame_skip']!=5 or abs(physics['action_scale']-.01)>1e-9:raise ValueError('frozen Smol native physics changed')
        counters['environment_resets']+=1;observation(obs)
        return obs,physics,np.asarray(env._env._last_rand_vec).copy()
    def step_env(env,raw):
        check();t=time.monotonic();result=env.step(raw);counters['environment_seconds']+=time.monotonic()-t;counters['environment_steps']+=1
        observation(result[0]);return result
    def terminal(value):return bool(value[2] or value[3] or value[4].get('success',value[4].get('is_success',False)))
    matching=read(cfg['engine_config'])['matching']
    with torch.inference_mode(False),torch.enable_grad():
        leaf=torch.zeros((10,4),device='cuda',requires_grad=True)
        physical=post(leaf);native_slopes=torch.autograd.grad(physical.sum(),leaf)[0].detach().cpu().numpy()
    if not np.isfinite(native_slopes).all() or np.any(native_slopes==0):raise ValueError('native inverse action transform invalid')
    atomic_json(out/'MODEL_READY.json',dict(status='ready',process=process_identity(),at_utc=utc(),
        base='SmolVLA050000',raw_H=50,native_K=10,NFE=10,model_resident=True,phase=cfg['phase'],
        base_parameters=sum(p.numel() for p in policy.parameters()),load_seconds=time.monotonic()-started,
        native_action_slopes=native_slopes[0].tolist(),base_allocated_bytes=int(torch.cuda.memory_allocated())))

    def collect_parent(source):
        check(True);folder=parent_path(source);folder.mkdir(parents=True,exist_ok=False)
        sid=source['source_id'];cut=source['cut'];begin=time.monotonic();bank=None;env=None;rows=[]
        first_claim=claim_attempt(sid+'/old/0',phase='collect',source_id=sid,candidate='old',repeat=0)
        try:
            random.seed(source['construction_seed']);np.random.seed(source['construction_seed'])
            env=MetaworldEnv(task=source['task'],obs_type='pixels_agent_pos')
            language=rpc('begin',source_id=sid,instruction=env.task_description)['language']
            for candidate in ['old','a0','local_plus','local_minus']:
                for repeat in [0,1]:
                    if rows and rows[0].get('normal_only'):break
                    claim=first_claim if candidate=='old' and repeat==0 else claim_attempt(sid+'/'+candidate+'/'+str(repeat),phase='collect',source_id=sid,candidate=candidate,repeat=repeat)
                    ep=folder/(candidate+'_r'+str(repeat));ep.mkdir();row=dict(source_id=sid,task=source['task'],split=source['split'],cut=cut,candidate=candidate,repeat=repeat,
                        claim=claim,status='entered',success=None,steps=0,normal_only=False,at_utc=utc())
                    new_json(ep/'ENTERED.json',row);before=dict(counters);encoder_before=rpc('snapshot')['counters'];t0=time.monotonic()
                    feats=[];props=[];actions=[];raw_actions=[];reward_values=[];success_flags=[]
                    try:
                        with episode_deadline():
                            obs,physics,randvec=reset(env,source);row['physics']=physics;raw=None;age=0;done=False
                            if bank is None:
                                feats.append(encode(obs,sid));props.append(observation(obs)['agent_pos'].copy())
                                for t in range(cut):
                                    if raw is None or age==10:raw,_=generate(obs,env.task_description);age=0
                                    action=raw[age].copy();age+=1;result=step_env(env,action);obs=result[0]
                                    raw_actions.append(action);actions.append(np.clip(action,-1,1));reward_values.append(float(result[1]));success_flags.append(bool(result[4].get('success',result[4].get('is_success',False))))
                                    feats.append(encode(obs,sid));props.append(observation(obs)['agent_pos'].copy());row['steps']=t+1
                                    if terminal(result):done=True;break
                                if done:
                                    row.update(status='complete',success=success_flags[-1],normal_only=True,terminal_reason='terminal_before_cut_decision')
                                else:
                                    if age!=5 or len(raw)-age<5:raise ValueError('fixed cut must preserve five old native commands')
                                    a0,_=generate(obs,env.task_description,source['a0_seed'])
                                    knots=np.random.default_rng(source['direction_seed']).normal(size=(3,4))
                                    direction=np.stack([np.interp(np.arange(10),[0,4.5,9],knots[:,j]) for j in range(4)],1)
                                    plus,pm,_=project_solo(a0,direction,matching);minus,mm,_=project_solo(a0,-direction,matching)
                                    bank=dict(features=np.asarray(feats,np.float16),props=np.asarray(props,np.float32),
                                        prefix_raw_actions=np.asarray(raw_actions,np.float32),prefix_actions=np.asarray(actions,np.float32),
                                        language=np.asarray(language,np.float32),old_raw=raw.copy(),old_age=np.int64(age),
                                        old_next_five=np.clip(raw[age:age+5],-1,1),a0=a0,local_plus=plus,local_minus=minus,
                                        randomization_vector=randvec,cut_rgb_mean=np.asarray(obs['pixels']).mean(axis=(0,1)),direction=direction)
                                    np.savez_compressed(folder/'BANK.npz',**bank)
                                    new_json(folder/'BANK.json',dict(source=source,real_observation=True,at_utc=utc(),
                                        random_direction=pm,negative_direction=mm,fresh_plan_count=1,old_queue_age=age,old_remaining_native_commands=10-age))
                            else:
                                if not np.allclose(randvec,bank['randomization_vector'],atol=1e-7,rtol=0):raise ValueError('paired reset randomization mismatch')
                                for t,action in enumerate(bank['prefix_raw_actions']):
                                    result=step_env(env,action);obs=result[0]
                                    if terminal(result):raise ValueError('prefix replay terminal mismatch')
                                    if not np.allclose(obs['agent_pos'],bank['props'][t+1],atol=1e-5,rtol=0):raise ValueError('prefix replay observed proprio mismatch')
                                    raw_actions.append(action.copy());actions.append(np.clip(action,-1,1));reward_values.append(float(result[1]));success_flags.append(False)
                                if not np.allclose(np.asarray(obs['pixels']).mean(axis=(0,1)),bank['cut_rgb_mean'],atol=.01,rtol=0):raise ValueError('prefix replay observed RGB statistic mismatch')
                                feats=list(bank['features']);props=list(bank['props']);row['steps']=cut
                            if not done:
                                torch.manual_seed(source['suffix_policy_seeds'][repeat]);torch.cuda.manual_seed(source['suffix_policy_seeds'][repeat])
                                if candidate=='old':raw=bank['old_raw'].copy();age=int(bank['old_age'])
                                else:raw=bank[candidate].copy();age=0
                                for t in range(cut,300):
                                    if age==10:raw,_=generate(obs,env.task_description);age=0
                                    action=raw[age].copy();age+=1;result=step_env(env,action);obs=result[0]
                                    raw_actions.append(action);actions.append(np.clip(action,-1,1));reward_values.append(float(result[1]));success_flags.append(bool(result[4].get('success',result[4].get('is_success',False))))
                                    feats.append(encode(obs,sid));props.append(observation(obs)['agent_pos'].copy());row['steps']=t+1
                                    if terminal(result) or t==299:
                                        row.update(status='complete',success=success_flags[-1],terminal_reason='success' if success_flags[-1] else 'environment_terminal' if terminal(result) else 'step_cap');break
                                    if t%25==0:atomic_json(out/'PROGRESS.json',dict(at_utc=utc(),phase='collect',source=sid,candidate=candidate,repeat=repeat,step=t+1))
                    except BaseException as exc:
                        row.update(status='budget_truncated' if isinstance(exc,AdmissionStop) else 'technical_failure',success=None,error=repr(exc),traceback=traceback.format_exc())
                    if feats:
                        np.savez_compressed(ep/'trajectory.npz',spatial=np.asarray(feats,np.float16),proprio=np.asarray(props,np.float32),
                            actions=np.asarray(actions,np.float32),raw_actions=np.asarray(raw_actions,np.float32),rewards=np.asarray(reward_values,np.float32),
                            success_flags=np.asarray(success_flags,bool),language=np.asarray(language,np.float32))
                    row.update(at_utc=utc(),elapsed_seconds=time.monotonic()-t0,counters={k:v-before.get(k,0) for k,v in counters.items()},
                        trajectory=str(ep/'trajectory.npz'),prefix_reused=not (candidate=='old' and repeat==0),suffix_seed=source['suffix_policy_seeds'][repeat])
                    try:row['encoder_counters']={k:v-encoder_before.get(k,0) for k,v in rpc('snapshot')['counters'].items()}
                    except Exception as exc:row['encoder_snapshot_error']=repr(exc)
                    new_json(ep/'RESULT.json',row);rows.append(row)
                    if row['status']!='complete':raise RuntimeError('recorded collection error; preserve attempts and stop owned worker')
                if rows and rows[0].get('normal_only'):break
            new_json(folder/'RESULT.json',dict(status='complete',source=source,normal_only=bool(rows[0]['normal_only']),
                real_rollouts=len(rows),outcomes=[{k:r[k] for k in ['candidate','repeat','status','success']} for r in rows],
                elapsed_seconds=time.monotonic()-begin,at_utc=utc()))
        except BaseException as exc:
            if not (folder/'old_r0/ENTERED.json').exists():
                new_json(folder/'INITIALIZATION_FAILURE.json',dict(status='technical_failure_before_rollout',claim=first_claim,
                    source_id=sid,error=repr(exc),success=None,at_utc=utc(),reserved_attempt_retained=True))
            raise
        finally:
            if env is not None:env.close()

    def evaluate_source(env,source,method):
        sid=source['source_id'];claim=claim_attempt(method+'/'+sid,phase='evaluate',method=method,source_id=sid)
        ep=ROOT/'evaluation'/method/sid;ep.mkdir(parents=True,exist_ok=False)
        row=dict(source,method=method,status='entered',success=None,steps=0,interventions=0,first_cut=None,events=[],claim=claim,
            adaptation='new Smol D/G0/Q; frozen external pi05 features',protocol='Mesa80Hz/.01/nativeK10/rawH50/NFE10')
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
                        trigger=bool(legal and monitor['gate']>.05 and row['interventions']==0)
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
                                np.savez_compressed(ep/'intervention.npz',raw_base=a0,corrected=raw,direction=direction,actual_delta=arrays['actual_delta'])
                            age=0;locked_until=t+10;row.update(interventions=1,first_cut=t)
                            event.update(candidate_seed=cs,commit_until=locked_until,restore_native_K=10,Q_acceptance_gate=False)
                        row['events'].append(event)
                    action=raw[age].copy();age+=1;result=step_env(env,action);obs=result[0]
                    actions.append(np.clip(action,-1,1));rewards.append(float(result[1]));successes.append(bool(result[4].get('success',result[4].get('is_success',False))));row['steps']=t+1
                    if terminal(result) or t==299:row.update(status='complete',success=successes[-1],terminal_reason='success' if successes[-1] else 'environment_terminal' if terminal(result) else 'step_cap');break
                row['encoder_counters']={k:v-encoder_before.get(k,0) for k,v in rpc('snapshot')['counters'].items()}
        except BaseException as exc:row.update(status='budget_truncated' if isinstance(exc,AdmissionStop) else 'technical_failure',success=None,error=repr(exc),traceback=traceback.format_exc())
        row.update(at_utc=utc(),elapsed_seconds=time.monotonic()-begin,counters={k:v-before.get(k,0) for k,v in counters.items()})
        np.savez_compressed(ep/'trajectory.npz',actions=np.asarray(actions,np.float32),rewards=np.asarray(rewards,np.float32),success_flags=np.asarray(successes,bool))
        new_json(ep/'RESULT.json',row)
        atomic_json(out/'PROGRESS.json',dict(at_utc=utc(),phase='evaluate',source_id=sid,method=method,status=row['status']))
        if row['status']!='complete':raise RuntimeError('recorded evaluation error; no implicit replay')
    fatal=None
    try:
        if cfg['phase']=='collect':
            parent_times=[]
            for source in cfg['parents']:
                # Save room for the already planned train/eval stages; stop at a
                # complete-parent boundary, without selecting parents by outcome.
                estimate=sum(parent_times)/len(parent_times) if parent_times else 900
                if remaining_seconds()<7200+estimate:
                    atomic_json(out/'COLLECTION_CUTOFF.json',dict(at_utc=utc(),reason='bounded downstream time reserve',remaining_seconds=remaining_seconds(),pending_parent=source['source_id']));break
                t=time.monotonic();collect_parent(source);parent_times.append(time.monotonic()-t)
        else:
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
            counters=dict(counters),at_utc=utc(),elapsed_seconds=time.monotonic()-started,peak_allocated_bytes=int(torch.cuda.max_memory_allocated())))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);main(p.parse_args().config)
