"""One frozen external encoder and Smol-specific heads for 24 branch contexts."""
import argparse
import time
from pathlib import Path
from collections import Counter
import paths
from paths import ROOT,ARTIFACTS,CONFIG
from qio import read,atomic_json,utc,process_identity
from admission import boundary
from counts import Counts

def main(path):
    cfg=read(path);out=Path(cfg['output']);boundary(True)
    import numpy as np
    import torch
    from numeric_setup import initialize
    from feature_path import canonical_decode,spatial_tokens,cpu_batch
    from ac_tmil.future_aware.models import WorldModel,BenefitModel
    from corrector.critic import FrozenSelector
    from corrector.guidance import FrozenObjective
    torch.set_num_threads(2);torch.backends.cuda.matmul.allow_tf32=True
    meter=Counts();started=time.monotonic();base=read(ROOT/'config/SMOL_BASE.json');state=initialize(read(base['base_config']),out,meter,'cuda:0');features=state['features']
    norm=read(ARTIFACTS/'dataset/NORMALIZATION.json');fit=read(ARTIFACTS/'FIT_SUMMARY.json');assert fit['G0_ready']
    worlds=[];gates=[]
    for ds,gs in ((1241,1341),(1242,1342)):
        world=WorldModel(norm).cuda();world.load_state_dict(torch.load(ARTIFACTS/'fits'/('D_'+str(ds))/'final.pt',map_location='cuda',weights_only=True))
        gate=BenefitModel(norm).cuda();gate.load_state_dict(torch.load(ARTIFACTS/'fits'/('G0_'+str(gs))/'final.pt',map_location='cuda',weights_only=True))
        worlds.append(world.eval().requires_grad_(False));gates.append(gate.eval().requires_grad_(False))
    selector=FrozenSelector(Path(CONFIG['selected_Q_assets']));contexts={};language_cache={}
    atomic_json(out/'Q_BINDING.json',dict(loss='L11',fit_seed=9101,member_seeds=[1041,1042,1043,1044],asset_root=CONFIG['selected_Q_assets'],ranking=read(Path(CONFIG['selected_Q_assets'])/'ranking.json'),utc=utc()))
    def encode(observations,counts):
        for obs in observations:
            f=obs['pixels'];p=obs['agent_pos']
            if f.shape!=(480,480,3) or f.dtype!=np.uint8 or not f.any() or np.asarray(p).shape!=(4,):raise ValueError('invalid actual observation')
        begin=time.monotonic()
        with torch.no_grad():
            raw=torch.as_tensor(features.encode_visual_batch(observations,batch_size=1),device='cuda').float()
            result=torch.cat([spatial_tokens(canonical_decode(row[None]),state['projection']).flatten(1) for row in raw],0).half().cpu().numpy()
        if result.shape!=(len(observations),4096) or not np.isfinite(result).all():raise ValueError('invalid features')
        counts['visual_observations']+=len(observations);counts['visual_encoder_calls']+=len(observations);counts['encoder_seconds']+=time.monotonic()-begin
        return result
    def handle(req):
        key=req['branch_id'];kind=req['kind']
        if kind=='begin':
            contexts[key]=dict(source=req['source_id'],instruction=req['instruction'],counts=Counter(),context=None,objective=None,step=None)
        ctx=contexts[key];counts=ctx['counts'];features._instruction=ctx['instruction']
        if 'source_id' in req and req['source_id']!=ctx['source']:raise ValueError('cross-source request')
        if kind=='begin':
            instruction=ctx['instruction']
            if instruction not in language_cache:
                t=time.monotonic();language_cache[instruction]=features.encode_instruction(instruction);counts['language_encoder_calls']+=1;counts['language_encoder_seconds']+=time.monotonic()-t
            ctx['language']=language_cache[instruction];return dict(language=ctx['language'].copy(),counters=dict(counts))
        if kind=='encode':return dict(spatial=encode(req['observations'],counts))
        if kind=='monitor':
            ctx['step']=int(req['step']);spatial=encode(req['observations'],counts)
            ctx['context']=cpu_batch(spatial.astype(np.float32),np.asarray(req['props'],np.float32),np.asarray(req['past_actions'],np.float32),ctx['language'],ctx['step'],device='cuda:0')
            commands=np.asarray(req['next_five'],np.float32)
            if commands.shape!=(5,4) or not np.isfinite(commands).all():raise ValueError('invalid old five commands')
            batch=dict(ctx['context'],actions=torch.as_tensor(np.clip(commands,-1,1),device='cuda')[None]);values=[]
            with torch.no_grad():
                for world,gate in zip(worlds,gates):future,_=world(batch);values.append(float(gate(batch,future)))
            counts['D_forward_calls']+=2;counts['G0_forward_calls']+=2;counts['monitor_calls']+=1
            if not np.isfinite(values).all():raise ValueError('nonfinite G0')
            return dict(gate=float(np.mean(values)),member_gates=values)
        if kind=='objective':
            if req['step']!=ctx['step'] or ctx['context'] is None:raise ValueError('objective context')
            raw=np.asarray(req['raw_plan'],np.float32)
            if raw.shape!=(50,4):raise ValueError('native raw50 required')
            observed={k:v[0].detach().cpu().numpy() for k,v in ctx['context'].items()}
            ctx['objective']=FrozenObjective(observed,np.clip(raw,-1,1).astype(np.float32),selector=selector);return dict(anchor_fixed=True)
        if kind=='gradient':
            if ctx['objective'] is None or req['step']!=ctx['step']:raise ValueError('unanchored gradient')
            commands=req.get('commands');commands=None if commands is None else np.asarray(commands,np.float32)
            gradient,stats=ctx['objective'].gradient(commands);ctx['objective'].verify(check_hashes=False)
            counts['Q_ensemble_forward_calls']+=1;counts['Q_member_forward_calls']+=4;counts['action_gradient_calls']+=1
            return dict(gradient=gradient.numpy(),value=stats['value'])
        if kind=='snapshot':
            selector.verify();return dict(counters=dict(counts),peak_allocated_bytes=int(torch.cuda.max_memory_allocated()))
        raise ValueError(kind)
    from mux import serve
    serve(cfg,handle,dict(status='ready',utc=utc(),process=process_identity(),slot=cfg['slot'],model='pi05_external_encoder_for_Smol',loss='L11',fit_seed=9101,loaded_D=2,loaded_G0=2,loaded_Q=4,model_replicas_per_GPU=1,logical_branch_capacity=24,inference_batch_size=1,load_seconds=time.monotonic()-started,GPU_allocated_bytes=int(torch.cuda.memory_allocated())))
    atomic_json(out/'SERVER_RESULT.json',dict(utc=utc(),status='complete',peak_allocated_bytes=int(torch.cuda.max_memory_allocated()),base_policy_sampling_calls=0))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);main(p.parse_args().config)
