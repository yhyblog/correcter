import argparse
import copy
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import paths
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity
from admission import boundary
from counts import Counts

def main(path):
    cfg=read(path);out=Path(cfg['output']);boundary(True)
    base=copy.deepcopy(read(ROOT/'config/BASE.json'));base['device']=base['device_list'][cfg['slot']];base['native']['device']=base['device']
    from resident_egl import ResidentEGL
    egl=ResidentEGL(base['native'],out,lambda:None);egl.prepare()
    import torch
    torch.set_num_threads(2);device=egl.bind_policy(torch);counts=Counts();started=time.monotonic()
    from numeric_setup import initialize
    from numeric_engine import Engine
    state=initialize(base,out,counts,device)
    asset=read(ROOT/'ASSETS.json')['assets']['pi05'];engine_cfg=dict(CONFIG,critic_assets=asset['assets'],selected_model=dict(member_hashes=asset['member_hashes'],ensemble=asset),loss='L11',fit_seed=9101)
    engine=Engine(state,engine_cfg,out);contexts={}
    fields=('runtime','instruction','episode_out','natural_seed','natural_generator','counts')
    def handle(req):
        key=req['branch_id'];kind=req['kind']
        if kind=='begin':
            contexts[key]=dict(counts={k:0 for k in engine.counts},numeric=Counter(),instruction=req['instruction'],episode_out=Path(req['episode_out']),runtime=SimpleNamespace(observation=req['observation']),observed=None)
        ctx=contexts[key]
        for name in fields:
            if name in ctx:setattr(engine,name,ctx[name])
        engine.features._instruction=ctx['instruction']
        if 'observation' in req:engine.runtime.observation=req['observation']
        before=dict(counts.entered)
        if kind=='begin':reply={}
        elif kind=='language':reply=dict(value=engine.language())
        elif kind=='start_natural_stream':engine.start_natural_stream(req['seed']);reply={}
        elif kind=='propose_natural':
            plan,stats=engine.propose_natural();reply=dict(plan=plan,stats=stats)
        elif kind=='context':
            ctx['observed']=engine.context(req['frames'],req['props'],req['past'],req['language'],req['step']);reply=dict(context_id=req['step'])
        elif kind=='monitor':reply=dict(value=engine.monitor(ctx['observed'],req['next_five']))
        elif kind=='intervene':
            plan,stats=engine.intervene(req['method'],ctx['observed'],req['seed'],req['step']);reply=dict(plan=plan,stats=stats)
        elif kind=='snapshot':engine.verify();reply={}
        else:raise ValueError(kind)
        for name in fields:
            if hasattr(engine,name):ctx[name]=getattr(engine,name)
        ctx['numeric'].update({k:v-before.get(k,0) for k,v in counts.entered.items()})
        if kind=='snapshot':reply.update(counts=dict(ctx['counts']),numeric=dict(ctx['numeric']),peak_allocated_bytes=int(torch.cuda.max_memory_allocated(device)))
        return reply
    from mux import serve
    try:serve(cfg,handle,dict(status='ready',utc=utc(),process=process_identity(),slot=cfg['slot'],model='pi05',loss='L11',fit_seed=9101,model_replicas_per_GPU=1,logical_branch_capacity=24,inference_batch_size=1,load_seconds=time.monotonic()-started,GPU_allocated_bytes=int(torch.cuda.memory_allocated(device))))
    finally:
        engine.hook.close();egl.finish_resident();atomic_json(out/'SERVER_RESULT.json',dict(utc=utc(),numeric=counts.snapshot(),peak_allocated_bytes=int(torch.cuda.max_memory_allocated(device))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);main(p.parse_args().config)
