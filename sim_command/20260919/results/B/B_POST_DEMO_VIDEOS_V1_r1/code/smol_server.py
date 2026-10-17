"""One Smol policy serves independent branch RNG/queues, with native gradients."""
import argparse
import collections
import time
from pathlib import Path
from multiprocessing.connection import Client
import paths
from paths import ROOT
from qio import read,atomic_json,utc,process_identity
from admission import boundary

def main(path):
    cfg=read(path);out=Path(cfg['output']);base=read(ROOT/'config/SMOL_BASE.json');boundary(True)
    import numpy as np
    import torch
    from lerobot.policies.factory import get_policy_class,make_pre_post_processors
    from native_velocity import NativeVelocityBridge
    torch.set_num_threads(2);torch.backends.cuda.matmul.allow_tf32=True;started=time.monotonic()
    checkpoint=Path(base['checkpoint']);policy=get_policy_class('smolvla').from_pretrained(checkpoint,local_files_only=True,strict=True)
    policy.config.n_action_steps=10;policy.config.num_steps=10
    assert policy.config.chunk_size==50 and tuple(policy.config.output_features['action'].shape)==(4,)
    policy.to('cuda').eval().requires_grad_(False);pre,post=make_pre_post_processors(policy.config,pretrained_path=checkpoint);bridge=NativeVelocityBridge(policy,post,'smolvla')
    encoder=Client(cfg['encoder_socket'],family='AF_UNIX',authkey=bytes.fromhex(cfg['ipc_auth']));contexts={}
    with torch.inference_mode(False),torch.enable_grad():
        leaf=torch.zeros((10,4),device='cuda',requires_grad=True);native_slopes=torch.autograd.grad(post(leaf).sum(),leaf)[0].detach().cpu().numpy()
    if not np.isfinite(native_slopes).all() or np.any(native_slopes==0):raise ValueError('native inverse action transform')
    def forward(req):
        encoder.send(req)
        if not encoder.poll(900):raise TimeoutError('encoder RPC')
        reply=encoder.recv()
        if not reply.get('ok'):raise RuntimeError(reply.get('error')+' '+reply.get('traceback',''))
        reply.pop('ok',None);reply['encoder_service_seconds']=reply.pop('seconds',None);return reply
    def handle(req):
        key=req['branch_id'];kind=req['kind']
        if kind=='policy_reset':
            with torch.random.fork_rng(devices=[0]):
                torch.manual_seed(req['seed']);torch.cuda.manual_seed(req['seed']);policy.reset()
                contexts[key]=dict(cpu_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state(),queues=policy._queues,source=None,step=None)
            return {}
        ctx=contexts.get(key)
        if kind=='policy_info':return dict(native_action_slopes=native_slopes,model_resident=True)
        if kind=='begin':ctx['source']=req['source_id']
        if kind=='monitor':ctx['step']=req['step']
        if kind!='generate':return forward(req)
        obs=req['observation'];seed=req.get('candidate_seed');sample={'observation.image':torch.from_numpy(np.ascontiguousarray(obs['pixels'])).permute(2,0,1).float()/255,'observation.state':torch.as_tensor(obs['agent_pos'],dtype=torch.float32),'task':req['instruction']}
        begin=time.monotonic();policy._queues=ctx['queues']
        gradient=(lambda command:forward(dict(kind='gradient',branch_id=key,source_id=ctx['source'],step=ctx['step'],commands=command))) if req.get('gradient') else None
        bridge.begin(gradient)
        with torch.random.fork_rng(devices=[0]):
            torch.set_rng_state(ctx['cpu_rng']);torch.cuda.set_rng_state(ctx['cuda_rng'])
            if seed is not None:torch.manual_seed(seed);torch.cuda.manual_seed(seed)
            with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
                native=policy.predict_action_chunk(pre(sample));assert native.shape==(1,50,4)
                raw=np.stack([post(native[:,i]).reshape(-1).float().cpu().numpy() for i in range(50)]).astype(np.float32)
            if seed is None:ctx['cpu_rng']=torch.get_rng_state();ctx['cuda_rng']=torch.cuda.get_rng_state()
        ctx['queues']=policy._queues;stats=bridge.finish()
        if raw.shape!=(50,4) or not np.isfinite(raw).all():raise ValueError('raw50')
        return dict(raw=raw,stats=stats,policy_seconds=time.monotonic()-begin)
    from mux import serve
    try:serve(cfg,handle,dict(status='ready',utc=utc(),process=process_identity(),slot=cfg['slot'],model='SmolVLA',model_replicas_per_GPU=1,logical_branch_capacity=24,inference_batch_size=1,load_seconds=time.monotonic()-started,GPU_allocated_bytes=int(torch.cuda.memory_allocated()),native_action_slopes=native_slopes[0].tolist()))
    finally:
        encoder.send(dict(kind='close',branch_id='policy_service'));encoder.recv();encoder.close()
        atomic_json(out/'SERVER_RESULT.json',dict(status='complete',utc=utc(),peak_allocated_bytes=int(torch.cuda.max_memory_allocated())))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);main(p.parse_args().config)
