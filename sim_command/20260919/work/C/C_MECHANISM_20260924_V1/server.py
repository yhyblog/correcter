"""One serialized model server per GPU; no environment state is shared."""
import argparse,copy,os,time,traceback
from pathlib import Path
from types import SimpleNamespace
from multiprocessing.connection import Listener,wait
import paths
from paths import ROOT,QROOT,TRAIN_ROOT
from common import read,write,check,identity,seed

def main(slot):
    import numpy as np
    cfg=read(ROOT/'CONFIG.json');base=read(ROOT/'BASE.json');out=ROOT/'servers'/str(slot);out.mkdir(parents=True,exist_ok=True)
    base['device']=base['device_list'][slot];base['native']['device']=base['device']
    from resident_egl import ResidentEGL
    egl=ResidentEGL(base['native'],out,lambda:None);egl.prepare()
    import torch
    torch.set_num_threads(2);device=egl.bind_policy(torch)
    from counts import Counts
    from numeric_setup import initialize
    from numeric_engine import Engine
    from corrector.critic import FrozenSelector
    from corrector.guidance import FrozenObjective
    from ac_tmil.future_aware.models import BenefitModel
    from repair_operator import project,sign_variant,describe
    counts=Counts();started=time.monotonic();state=initialize(base,out,counts,device);engine=Engine(state,read(ROOT/'ENGINE.json'),out)
    selectors={loss:(engine.selector if loss=='L11' else FrozenSelector(QROOT/(loss+'_s9101'))) for loss in ['L00','L10','L01','L11']}
    heads={};contexts={};calls=0
    def load_heads():
        if heads:return
        for member in [341,342]:
            w=241+(member%2==0);norm=read(TRAIN_ROOT/'models'/f'spatial_pair_{w}'/'normalization.json')
            for mode in ['risk','nod']:
                if not (ROOT/'heads'/f'{mode}_{member}'/'RESULT.json').exists():raise RuntimeError('heads not ready')
                m=BenefitModel(norm).to(device);m.load_state_dict(torch.load(ROOT/'heads'/f'{mode}_{member}'/'selected.pt',map_location=device,weights_only=True));heads[mode,member]=m.eval().requires_grad_(False)
    def objective(obs,raw,loss):
        return FrozenObjective({k:v[0].detach().cpu().numpy() for k,v in obs.items()},np.clip(raw,-1,1),selector=selectors[loss])
    slopes=((engine.transform.q99-engine.transform.q01)/2).detach().cpu().numpy()
    def correct(obs,raw,loss='L11'):
        obj=objective(obs,raw,loss);g,_=obj.gradient();p=project(raw,g.numpy()*slopes[None]**2);return p,obj
    @torch.no_grad()
    def score(ctx,next_five,with_heads,signal='all'):
        obs=ctx['observed'];b=dict(obs,actions=torch.as_tensor(next_five,device=device)[None]);g=[];pred=[];risk=[];nod=[]
        if with_heads and signal in ['all','risk','nod']:load_heads()
        for w,world in engine.worlds.items():
            if signal!='nod':
                future,_=world(b);pred.append(future[0].float().cpu().numpy())
                if signal in ['all','G0']:g.append(float(engine.gates[w](b,future)))
                if with_heads and signal in ['all','risk']:risk.append(float(heads['risk',w+100](b,future).sigmoid()))
            if with_heads and signal in ['all','nod']:nod.append(float(heads['nod',w+100](b,b['history'][:,-1,None].expand(-1,5,-1))))
        ans=dict(G0=float(np.mean(g)) if g else None,prediction=np.stack(pred) if pred else None,actual=obs['history'][0].float().cpu().numpy(),scale=np.stack([w.delta_scale.cpu().numpy() for w in engine.worlds.values()]))
        if risk:ans['risk']=float(np.mean(risk))
        if nod:ans['nod']=float(np.mean(nod))
        return ans
    def handle(r):
        key=r['branch'];kind=r['kind']
        if kind=='begin':
            contexts[key]=dict(runtime=SimpleNamespace(observation=r['observation']),instruction=r['instruction'],episode_out=Path(r['output']),counts={k:0 for k in engine.counts})
        ctx=contexts[key]
        for k in ['runtime','instruction','episode_out','counts','natural_seed','natural_generator']:
            if k in ctx:setattr(engine,k,ctx[k])
        engine.features._instruction=ctx['instruction']
        if 'observation' in r:engine.runtime.observation=r['observation']
        if kind=='begin':value=engine.language()
        elif kind=='stream':
            engine.start_natural_stream(r['seed'])
            if r.get('state') is not None:engine.natural_generator.set_state(torch.as_tensor(r['state'],dtype=torch.uint8,device='cpu'))
            value=None
        elif kind=='rng':value=engine.natural_generator.get_state().cpu().numpy()
        elif kind=='plan':value=engine.propose_natural()[0]
        elif kind=='monitor':
            ctx['observed']=engine.context(r['frames'],r['props'],r['past'],r['language'],r['step']);value=score(ctx,r['next_five'],r.get('heads',False),r.get('signal','all'))
        elif kind=='saved_score':
            ctx['observed']={k:torch.as_tensor(v,device=device) for k,v in r['observed'].items()};value=score(ctx,r['next_five'],True)
        elif kind=='get_context':value={k:v.detach().cpu().numpy() for k,v in ctx['observed'].items()}
        elif kind=='intervene':
            raw,_=engine.propose(r['seed']);value=raw
            if r['method']=='Post':value,_=correct(ctx['observed'],raw)
        elif kind=='bank':
            obs={k:torch.as_tensor(v,device=device) for k,v in r['observed'].items()};raw,_=engine.propose(r['seed']);plans={'R':raw};predictions={};repair_times={}
            for loss in ['L00','L10','L01','L11']:
                t=time.monotonic();p,obj=correct(obs,raw,loss);repair_times[loss]=time.monotonic()-t;plans[loss]=p
                predictions[loss]=dict(base=obj.evaluate(np.clip(raw[:10],-1,1)),corrected=obj.evaluate(np.clip(p[:10],-1,1)))
            final=plans['L11'];plans['reverse']=sign_variant(raw,final,-1)
            for j in range(3):plans[f'sign{j}']=sign_variant(raw,final,np.random.default_rng(seed(r['seed'],'sign',j)).choice([-1,1],(10,4)))
            obj=objective(obs,raw,'L11');g,_=obj.gradient();d=g.numpy()*slopes[None]**2
            plans['no_metric']=project(raw,g.numpy());plans['unified']=project(raw,d,unified=True)
            plans['radius05']=project(raw,d,.5);plans['radius2']=project(raw,d,2.)
            for n in [2,4]:
                t=time.monotonic();p=raw.copy()
                for _ in range(n):
                    gg,_=obj.gradient(np.clip(p[:10],-1,1));proposal=project(raw,gg.numpy()*slopes[None]**2)
                    delta=p[:10].astype(float)-raw[:10].astype(float)+(proposal[:10].astype(float)-raw[:10].astype(float))/n
                    p=project(raw,delta,expand=False)
                plans[f'grad{n}']=p;repair_times[f'grad{n}']=time.monotonic()-t
            # New independent directions, unrelated to thirteen training templates.
            v=np.random.default_rng(seed(r['seed'],'novel_direction')).normal(size=(10,4))
            plans['probe_plus']=project(raw,v);plans['probe_minus']=sign_variant(raw,plans['probe_plus'],-1)
            for loss in predictions:
                o=objective(obs,raw,loss)
                predictions[loss]['probe_plus']=o.evaluate(np.clip(plans['probe_plus'][:10],-1,1))
                predictions[loss]['probe_minus']=o.evaluate(np.clip(plans['probe_minus'][:10],-1,1))
            value=dict(plans=plans,predictions=predictions,diagnostics={k:describe(raw,p) for k,p in plans.items()},repair_seconds=repair_times,metric_action_max_difference=float(np.max(np.abs(plans['no_metric']-final))),metric_slopes=slopes.tolist())
        else:raise ValueError(kind)
        for k in ['natural_seed','natural_generator']:
            if hasattr(engine,k):ctx[k]=getattr(engine,k)
        return value
    local=Path(cfg['local_dir']);local.mkdir(exist_ok=True);sock=local/f'gpu{slot}.sock'
    listener=Listener(str(sock),family='AF_UNIX');socket0=listener._listener._socket;connections=[]
    write(out/'MODEL_READY.json',dict(**identity(),slot=slot,load_seconds=time.monotonic()-started,gpu_allocated_bytes=torch.cuda.memory_allocated(device),Q_losses=list(selectors),batch_size=1))
    try:
        while not (out/'STOP').exists() or connections:
            check()
            for c in wait([socket0,*connections],timeout=1):
                if c is socket0:connections.append(listener.accept());continue
                try:
                    r=c.recv()
                    if r['kind']=='close':contexts.pop(r['branch'],None);c.send(dict(ok=True));connections.remove(c);c.close();continue
                    torch.cuda.synchronize(device);t=time.monotonic();v=handle(r);torch.cuda.synchronize(device);elapsed=time.monotonic()-t;calls+=1
                    c.send(dict(ok=True,value=v,seconds=elapsed))
                    if calls%25==0:write(out/'HEARTBEAT.json',dict(time=time.time(),calls=calls,connections=len(connections),gpu_allocated_bytes=torch.cuda.memory_allocated(device)))
                except (EOFError,ConnectionResetError,BrokenPipeError):
                    if c in connections:connections.remove(c)
                    c.close()
                except Exception as exc:
                    err=dict(error=repr(exc),traceback=traceback.format_exc());write(out/'LAST_ERROR.json',err)
                    try:c.send(dict(ok=False,**err))
                    except (EOFError,ConnectionResetError,BrokenPipeError):pass
    finally:
        for c in connections:c.close()
        listener.close();engine.hook.close();egl.finish_resident()
        write(out/'RESULT.json',dict(status='exited',calls=calls,time=time.time()))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('slot',type=int);main(p.parse_args().slot)
