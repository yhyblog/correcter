"""Frozen external encoder; only newly fitted X heads are used in evaluation."""
import argparse
from collections import Counter
from multiprocessing.connection import Listener
from pathlib import Path
import time
import traceback
import paths
paths.external_encoder_paths()
from paths import ROOT,HEADS
from qio import read,atomic_json,utc,process_identity
from admission import boundary

def main(config_path):
    cfg=read(config_path);out=Path(cfg['output'])/'encoder';out.mkdir(parents=True,exist_ok=False)
    boundary(admission=True)
    import numpy as np
    import torch
    from numeric_setup import initialize
    from feature_path import canonical_decode,spatial_tokens,cpu_batch
    from episode_runtime import Counts
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=True
    meter=Counts();start=time.monotonic();state=initialize(read(cfg['base_config']),out,meter,'cuda:0')
    from corrector.actions import ActionTransform
    transform=ActionTransform.from_checkpoint(state['cfg']['checkpoint'],device='cuda:0')
    post_slopes=((transform.q99-transform.q01)/2).detach().cpu().numpy()
    features=state['features'];counts=Counter();language_cache={};source=None;language=None;context=None;step=None;objective=None
    worlds=[];gates=[];selector=None
    if cfg['phase']=='evaluate':
        from ac_tmil.future_aware.models import WorldModel,BenefitModel
        from corrector.critic import FrozenSelector
        from corrector.guidance import FrozenObjective
        norm=read(HEADS/'dataset/NORMALIZATION.json')
        fit=read(HEADS/'FIT_SUMMARY.json')
        if not fit['G0_ready']:raise RuntimeError('new G0 scientific gap; evaluation not permitted')
        for ds,gs in [(2241,2341),(2242,2342)]:
            world=WorldModel(norm).cuda();world.load_state_dict(torch.load(HEADS/'fits'/('D_'+str(ds))/'final.pt',map_location='cuda',weights_only=True))
            gate=BenefitModel(norm).cuda();gate.load_state_dict(torch.load(HEADS/'fits'/('G0_'+str(gs))/'final.pt',map_location='cuda',weights_only=True))
            worlds.append(world.eval().requires_grad_(False));gates.append(gate.eval().requires_grad_(False))
        if fit['Q_ready']:selector=FrozenSelector(HEADS/'models/Q_selected')
    identity=dict(at_utc=utc(),process=process_identity(),status='ready',phase=cfg['phase'],
        encoder_checkpoint=state['cfg']['checkpoint'],external_model_parameters=sum(p.numel() for p in state['policy'].parameters()),
        external_visual_encoder_parameters=sum(p.numel() for p in state['model'].paligemma_with_expert.paligemma.vision_tower.parameters()) if hasattr(state['model'].paligemma_with_expert.paligemma,'vision_tower') else None,
        external_encoder_allocated_bytes=int(torch.cuda.memory_allocated()),external_encoder_load_seconds=time.monotonic()-start,
        base_policy_sampling_calls=0,loaded_new_D=len(worlds),loaded_new_G0=len(gates),loaded_new_Q=4 if selector else 0)
    listener=Listener(cfg['socket_path'],family='AF_UNIX',authkey=bytes.fromhex(cfg['ipc_auth']))
    atomic_json(out/'READY.json',identity)
    def encode(observations):
        if not observations:raise ValueError('empty observation batch')
        for obs in observations:
            f=obs['pixels'];p=obs['agent_pos']
            if f.shape!=(480,480,3) or f.dtype!=np.uint8 or not f.any() or np.asarray(p).shape!=(4,):
                raise ValueError('invalid actual policy observation')
        begin=time.monotonic()
        with torch.no_grad():
            raw=features.encode_visual_batch(observations,batch_size=1)
            raw=torch.as_tensor(raw,device='cuda').float()
            spatial=torch.cat([spatial_tokens(canonical_decode(row[None]),state['projection']).flatten(1) for row in raw],0)
            result=spatial.half().cpu().numpy()
        if result.shape!=(len(observations),4096) or not np.isfinite(result).all():raise ValueError('invalid encoded observations')
        counts['visual_observations']+=len(observations);counts['visual_encoder_calls']+=len(observations)
        counts['encoder_seconds']+=time.monotonic()-begin
        return result
    def verify():
        if any(p._version!=v or p.requires_grad or p.grad is not None for p,v in state['versions']):raise ValueError('external model mutated')
        if meter.entered.get('denoise_step',0):raise ValueError('external encoder sampled policy actions')
        if selector:selector.verify()
    fatal=None
    try:
        with listener.accept() as connection:
            while True:
                req=connection.recv();boundary();begin=time.monotonic()
                try:
                    kind=req['kind']
                    if kind=='close':verify();connection.send(dict(ok=True));break
                    if kind=='begin':
                        counters_before=dict(counts)
                        source=req['source_id'];features._instruction=req['instruction'];context=objective=None;step=None
                        if req['instruction'] not in language_cache:
                            t=time.monotonic();language_cache[req['instruction']]=features.encode_instruction(req['instruction'])
                            counts['language_encoder_calls']+=1;counts['language_encoder_seconds']+=time.monotonic()-t
                        language=language_cache[req['instruction']]
                        result=dict(language=language.copy(),counters=dict(counts),counters_before=counters_before)
                    elif kind=='encode':
                        if req['source_id']!=source:raise ValueError('cross-source observation')
                        result=dict(spatial=encode(req['observations']))
                    elif kind=='monitor':
                        if cfg['phase']!='evaluate' or req['source_id']!=source:raise ValueError('invalid monitor phase')
                        step=int(req['step']);spatial=encode(req['observations'])
                        context=cpu_batch(spatial.astype(np.float32),np.asarray(req['props'],np.float32),
                            np.asarray(req['past_actions'],np.float32),language,step,device='cuda:0')
                        commands=np.asarray(req['next_five'],np.float32)
                        if commands.shape!=(5,4) or not np.isfinite(commands).all():raise ValueError('invalid old five commands')
                        batch=dict(context,actions=torch.as_tensor(np.clip(commands,-1,1),device='cuda')[None]);values=[]
                        with torch.no_grad():
                            for world,gate in zip(worlds,gates):
                                future,_=world(batch);values.append(float(gate(batch,future)))
                        counts['D_forward_calls']+=2;counts['G0_forward_calls']+=2;counts['monitor_calls']+=1
                        if not np.isfinite(values).all():raise ValueError('nonfinite new G0')
                        result=dict(gate=float(np.mean(values)),member_gates=values)
                    elif kind=='objective':
                        if selector is None or req['source_id']!=source or req['step']!=step or context is None:raise ValueError('objective without current trained context')
                        from corrector.guidance import FrozenObjective
                        raw=np.asarray(req['raw_plan'],np.float32)
                        if raw.shape!=(30,4):raise ValueError('native X rawH30 required')
                        raw=np.concatenate([raw,np.repeat(raw[-1:],20,axis=0)])
                        observed={k:v[0].detach().cpu().numpy() for k,v in context.items()}
                        objective=FrozenObjective(observed,np.clip(raw,-1,1).astype(np.float32),selector=selector)
                        result=dict(anchor_fixed=True)
                    elif kind=='gradient':
                        if objective is None or req['source_id']!=source or req['step']!=step:raise ValueError('gradient without anchored objective')
                        commands=req.get('commands');commands=None if commands is None else np.asarray(commands,np.float32)
                        gradient,stats=objective.gradient(commands)
                        counts['Q_ensemble_forward_calls']+=1;counts['Q_member_forward_calls']+=4;counts['action_gradient_calls']+=1
                        objective.verify(check_hashes=False)
                        result=dict(gradient=gradient.numpy(),value=stats['value'],post_direction=gradient.numpy()*post_slopes[None]**2,
                            Post_metric='inherited frozen pi05 clean-coordinate S squared, unchanged E8 Post bridge')
                    elif kind=='snapshot':
                        verify();result=dict(counters=dict(counts),meter=meter.snapshot(),peak_allocated_bytes=int(torch.cuda.max_memory_allocated()))
                    else:raise ValueError('unknown IPC operation '+str(kind))
                    connection.send(dict(ok=True,seconds=time.monotonic()-begin,**result))
                except BaseException as exc:
                    connection.send(dict(ok=False,error=repr(exc),traceback=traceback.format_exc()));raise
    except BaseException as exc:
        fatal=dict(error=repr(exc),traceback=traceback.format_exc());raise
    finally:
        listener.close()
        atomic_json(out/'RESULT.json',dict(status='failed' if fatal else 'complete',fatal=fatal,at_utc=utc(),
            counts=dict(counts),meter=meter.snapshot(),identity=identity,elapsed_seconds=time.monotonic()-start,
            peak_allocated_bytes=int(torch.cuda.max_memory_allocated()),external_encoder_sampling_calls=0))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);main(p.parse_args().config)
