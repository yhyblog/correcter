"""Native Smol/X K10 execution with true G0, once-only C10 Post transfer."""
import argparse
import collections
import contextlib
import hashlib
import json
from multiprocessing.connection import Client
from pathlib import Path
import random
import signal
import sys
import time
import traceback
import d24_common as d


def main(config_path):
    cfg = d.load(config_path)
    d.authorize(admission=True)
    out = Path(cfg['output'])
    status = dict(status='loading_base', job_id=cfg['job_id'], method='Full-Post-transfer',
        checkpoint=cfg['checkpoint'], H=cfg['H'], K=cfg['K'], planned_episodes=len(cfg['episodes']),
        completed_episodes=0, technical_failures=0)
    d.atomic(out/'status.json',status)
    started, connection, stopping = time.monotonic(), None, False
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):
        signal.signal(sig,stop)
    try:
        import numpy as np
        import torch
        from lerobot.envs.metaworld import MetaworldEnv
        from lerobot.policies.factory import get_policy_class, make_pre_post_processors
        sys.path.insert(0,str(d.ROOT/'Corrector'))
        from experiments.native10_training_20260916.protocol import seed_for
        checkpoint=Path(cfg['checkpoint'])
        if hashlib.sha256((checkpoint/'config.json').read_bytes()).hexdigest()!=cfg['checkpoint_config_sha256']:
            raise ValueError('Frozen base configuration changed')
        if (checkpoint/'model.safetensors').stat().st_size!=cfg['checkpoint_weight_bytes']:
            raise ValueError('Frozen base checkpoint size changed')
        torch.set_num_threads(4)
        torch.backends.cuda.matmul.allow_tf32=True
        policy=get_policy_class(cfg['kind']).from_pretrained(checkpoint,local_files_only=True,strict=True)
        policy.config.n_action_steps=cfg['K']
        if cfg['kind']=='smolvla':
            policy.config.num_steps=cfg['NFE']
        else:
            policy.config.num_denoising_steps=cfg['NFE']
        if (policy.config.chunk_size!=cfg['H'] or cfg['K']!=10 or
            tuple(policy.config.output_features['action'].shape)!=(4,) or
            tuple(policy.config.input_features['observation.state'].shape)!=(4,)):
            raise ValueError('Frozen native action/state/queue interface changed')
        policy.to('cuda').eval().requires_grad_(False)
        pre,post=make_pre_post_processors(policy.config,pretrained_path=checkpoint)
        torch.cuda.synchronize()
        connection=Client(cfg['socket_path'],family='AF_UNIX',authkey=bytes.fromhex(cfg['ipc_auth']))
        def rpc(value):
            connection.send(value)
            if not connection.poll(300):
                raise TimeoutError('Frozen corrector request timed out')
            result=connection.recv()
            if result.get('ok') is not True:
                raise RuntimeError('Frozen corrector failed: '+result.get('error','unknown'))
            return result
        status.update(status='running',load_seconds=time.monotonic()-started,model_resident=True)
        d.atomic(out/'status.json',status)
        grouped=collections.OrderedDict()
        for source in cfg['episodes']:
            grouped.setdefault(source['task'],[]).append(source)
        for task,sources in grouped.items():
            d.authorize(admission=True)
            random.seed(sources[0]['reset_seed'])
            np.random.seed(sources[0]['reset_seed'])
            env=MetaworldEnv(task=task,obs_type='pixels_agent_pos')
            try:
                for source in sources:
                    d.authorize(admission=True)
                    if stopping:
                        raise RuntimeError('Worker stop before source admission')
                    d.episode_claim(out,source)
                    ep=out/'episodes'/source['source_id']
                    ep.mkdir(parents=True,exist_ok=False)
                    begin=time.monotonic()
                    row=dict(source,method='Full-Post-transfer',checkpoint=cfg['checkpoint'],H=cfg['H'],K=10,
                        NFE=10,status='entered',success=None,steps=0,queries=0,natural_queries=0,candidate_queries=0,
                        interventions=0,first_cut=None,inference_seconds=0.,environment_seconds=0.,
                        preprocessing_seconds=0.,corrector_seconds=0.,monitor_calls=0,
                        action_dim=4,state_dim=4,max_interventions=1,commitment=10,
                        scope='frozen pi05 visual/language/D/G0/Q transfer; native base and native MW physics',
                        feature_embedding='pi05 canonical feature path; no base embedding substitution')
                    d.exclusive(ep/'ENTERED.json',row)
                    actions,rewards,successes,events=[],[],[],[]
                    try:
                        with d.episode_deadline():
                            seed=source['reset_seed']
                            random.seed(seed);np.random.seed(seed);env._env.seed(seed)
                            obs,_=env.reset(seed=seed)
                            row['initial_randomization_vector']=np.asarray(env._env._last_rand_vec).tolist()
                            row['physics']=dict(timestep=float(env._env.model.opt.timestep),frame_skip=int(env._env.frame_skip),
                                action_scale=float(env._env.action_scale),wrapper='same native env.step as frozen N')
                            policy.reset();torch.manual_seed(source['policy_seed'])
                            rpc(dict(kind='episode',source_id=source['source_id'],instruction=env.task_description,
                                     episode_output=str(ep)))
                            frames,props=collections.deque(maxlen=5),collections.deque(maxlen=5)
                            raw,age,locked_until=None,0,0
                            last_progress=0.
                            def generate(candidate_seed=None):
                                t=time.monotonic()
                                sample={'observation.image':torch.from_numpy(np.ascontiguousarray(obs['pixels'])).permute(2,0,1).float()/255,
                                    'observation.state':torch.as_tensor(obs['agent_pos'],dtype=torch.float32),'task':env.task_description}
                                row['preprocessing_seconds']+=time.monotonic()-t
                                t=time.monotonic()
                                scope=torch.random.fork_rng(devices=[0]) if candidate_seed is not None else contextlib.nullcontext()
                                with scope:
                                    if candidate_seed is not None:
                                        torch.manual_seed(candidate_seed)
                                        torch.cuda.manual_seed(candidate_seed)
                                    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
                                        normalized=policy.predict_action_chunk(pre(sample))
                                        if tuple(normalized.shape)!=(1,cfg['H'],4):
                                            raise ValueError('Unexpected native normalized chunk shape')
                                        # Same per-action postprocessor as N; natural chunks use the
                                        # same global RNG stream. Candidate draws are forked separately.
                                        result=np.stack([post(normalized[:,i]).reshape(-1).cpu().float().numpy()
                                                         for i in range(cfg['H'])])
                                row['inference_seconds']+=time.monotonic()-t
                                row['queries']+=1
                                row['candidate_queries' if candidate_seed is not None else 'natural_queries']+=1
                                if result.shape!=(cfg['H'],4) or not np.isfinite(result).all():
                                    raise ValueError('Invalid native physical action chunk')
                                return np.asarray(result,np.float32)
                            for step in range(cfg['max_steps']):
                                d.authorize()
                                if stopping:
                                    raise RuntimeError('Worker stopped during episode')
                                frame=np.asarray(obs['pixels'])
                                if frame.ndim!=3 or frame.shape[-1]!=3 or frame.dtype!=np.uint8 or not frame.any():
                                    raise RuntimeError('Invalid actual RGB observation')
                                frames.append(frame.copy());props.append(np.asarray(obs['agent_pos'],np.float32).copy())
                                if raw is None or age==10:
                                    raw=generate();age=0
                                if step>=locked_until and step%5==0 and min(10-age,300-step)>=5:
                                    monitor=rpc(dict(kind='monitor',source_id=source['source_id'],step=step,
                                        frames=[dict(shape=f.shape,data=f.tobytes()) for f in frames],
                                        props=[p.tolist() for p in props],past_actions=[a.tolist() for a in actions[-4:]],
                                        next_five=raw[age:age+5].tolist()))
                                    row['corrector_seconds']+=monitor.pop('seconds')
                                    monitor.pop('ok')
                                    row['monitor_calls']+=1
                                    legal=len(frames)==5 and len(actions)>=4 and age>0 and step+10<=300
                                    trigger=bool(legal and monitor['gate']>.05 and row['interventions']==0)
                                    event=dict(step=step,queue_age=age,legal_cut=legal,trigger=trigger,
                                        gate_threshold=.05,intervention_executed=False,synthetic=False,**monitor)
                                    if trigger:
                                        candidate_seed=seed_for('D24_designated_a0',source['source_id'],source['policy_seed'],step,
                                            namespace=cfg['seed_namespace'])
                                        raw=generate(candidate_seed)
                                        corrected=rpc(dict(kind='post',source_id=source['source_id'],step=step,raw_plan=raw.tolist()))
                                        row['corrector_seconds']+=corrected.pop('seconds')
                                        corrected.pop('ok')
                                        raw=np.asarray(corrected.pop('raw_plan'),np.float32)
                                        if raw.shape!=(cfg['H'],4) or not np.isfinite(raw).all():
                                            raise ValueError('Invalid Post output')
                                        age=0;locked_until=step+10
                                        row['interventions']=1;row['first_cut']=step
                                        event.update(intervention_executed=True,candidate_seed=candidate_seed,commit_until=locked_until,
                                            old_tail_discarded=True,restore_native_K=10,post=corrected)
                                    events.append(event);d.append(ep/'events.jsonl',event)
                                action=raw[age].copy();age+=1
                                t=time.monotonic()
                                obs,reward,terminated,truncated,info=env.step(action)
                                row['environment_seconds']+=time.monotonic()-t
                                actions.append(action);rewards.append(float(reward))
                                success=bool(info.get('success',info.get('is_success',False)))
                                successes.append(success);row['steps']=step+1
                                if not np.asarray(obs['pixels']).any():
                                    raise RuntimeError('Invalid resulting RGB observation')
                                if time.monotonic()-last_progress>10:
                                    d.atomic(out/'EPISODE_PROGRESS.json',dict(source_id=source['source_id'],step=step+1,
                                        method='Full-Post-transfer',interventions=row['interventions'],at_utc=d.utc()))
                                    last_progress=time.monotonic()
                                if success or terminated or truncated or step==cfg['max_steps']-1:
                                    row.update(status='complete',success=success,terminated=bool(terminated),truncated=bool(truncated),
                                        terminal_reason='success' if success else 'environment_terminal' if terminated or truncated else 'step_cap')
                                    break
                            row['corrector_counts']=rpc(dict(kind='verify'))['counters']
                    except BaseException as exc:
                        row.update(status='technical_failure',success=None,error=repr(exc),traceback=traceback.format_exc())
                    row.update(at_utc=d.utc(),elapsed_seconds=time.monotonic()-begin,result_path=str(ep/'RESULT.json'))
                    np.savez_compressed(ep/'trajectory.npz',actions=np.asarray(actions,np.float32),
                                        rewards=np.asarray(rewards),success_flags=np.asarray(successes))
                    d.exclusive(ep/'RESULT.json',row);d.append(out/'episodes.jsonl',row)
                    status['completed_episodes']+=int(row['status']=='complete')
                    status['technical_failures']+=int(row['status']!='complete')
                    status.update(latest_source=source['source_id'],at_utc=d.utc())
                    d.atomic(out/'status.json',status)
                    if row['status']!='complete':
                        raise RuntimeError('Recorded technical episode failure; no automatic retry')
            finally:
                env.close()
        d.exclusive(out/'CLIENT_COMPUTE_DONE.json',dict(at_utc=d.utc(),completed_episodes=status['completed_episodes']))
        rpc(dict(kind='close'))
        status['status']='complete'
    except BaseException as exc:
        status.update(status='failed',error=repr(exc),traceback=traceback.format_exc())
        raise
    finally:
        if connection is not None:
            connection.close()
        status.update(at_utc=d.utc(),elapsed_seconds=time.monotonic()-started)
        d.atomic(out/'status.json',status)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--config',required=True)
    main(p.parse_args().config)
