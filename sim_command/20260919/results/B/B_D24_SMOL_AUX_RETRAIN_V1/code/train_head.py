"""Eight independent fresh heads, 4000 updates each; fixed final checkpoint."""
import argparse
import json
from pathlib import Path
import time
import numpy as np
import torch
import torch.nn.functional as F
import paths
from paths import ROOT
from qio import read,new_json,atomic_json,utc,process_identity,sha
from admission import boundary
from corrector.critic import STATE_KEYS,TenStepCritic
from ac_tmil.future_aware.models import WorldModel,BenefitModel
from ac_tmil.future_aware.training import objective

def q_loss(logits,labels,cw,gw,pw):
    def average(values,weights):
        denominator=weights.sum(-1)
        return ((values*weights).sum(-1)/torch.where(denominator>0,denominator,torch.ones_like(denominator))).mean()
    p=logits.sigmoid();bce=average(F.binary_cross_entropy_with_logits(logits,labels,reduction='none'),cw)
    gain=average(((p-p[:,:1])-(labels-labels[:,:1])).square(),gw)
    pair=(((p[:,1]-p[:,2])-(labels[:,1]-labels[:,2])).square()*pw).mean()
    return bce+gain+.5*pair

class Windows:
    def __init__(self,split):
        self.states=np.load(ROOT/'dataset/states.npy',mmap_mode='r');self.props=np.load(ROOT/'dataset/proprio.npy',mmap_mode='r')
        self.actions=np.load(ROOT/'dataset/actions.npy',mmap_mode='r');self.languages=np.load(ROOT/'dataset/languages.npy',mmap_mode='r')
        ts=read(ROOT/'dataset/TRAJECTORIES.json');self.offsets=np.asarray([x['offset'] for x in ts]);self.lengths=np.asarray([x['length'] for x in ts])
        self.indices=np.load(ROOT/'dataset'/(split+'_windows.npy'));self.size=len(self.indices)
    def take(self,indices,device='cuda'):
        traj,t=self.indices[indices].T;off=self.offsets[traj,None];last=self.lengths[traj,None]-1
        h=t[:,None]+np.arange(-4,1);f=t[:,None]+np.arange(1,6);a=t[:,None]+np.arange(5)
        hi=off+h;fi=off+np.minimum(f,last);ai=off+np.minimum(a,last)
        values=dict(history=self.states[hi].astype(np.float32),history_mask=np.ones(h.shape,bool),past_actions=self.actions[hi[:,:-1]].copy(),
            proprio=self.props[hi].copy(),proprio_mask=np.ones(h.shape,bool),language=self.languages[traj].copy(),
            actions=self.actions[ai].copy(),targets=self.states[fi].astype(np.float32),future_mask=f<=last,
            target_proprio=self.props[fi].copy(),target_proprio_mask=f<=last,remaining=((300-t)/300).astype(np.float32))
        return {k:torch.as_tensor(v,device=device) for k,v in values.items()}

def main(kind,seed):
    boundary(admission=True);torch.set_num_threads(4);torch.manual_seed(seed);np.random.seed(seed)
    out=ROOT/'fits'/(kind+'_'+str(seed));out.mkdir(parents=True,exist_ok=False)
    new_json(ROOT/'claims/fits'/(kind+'_'+str(seed)+'.json'),dict(kind=kind,seed=seed,reserved_update_cap=4000,
        run='D24_B_SMOL_AUX_r1',initialization='from scratch',at_utc=utc(),process=process_identity()))
    data=ROOT/'dataset';norm=read(data/'NORMALIZATION.json');rng=np.random.default_rng(seed);begin=time.monotonic()
    parents=torch.load(data/'train_parents.pt',map_location='cpu',weights_only=True)
    dev=torch.load(data/'development_parents.pt',map_location='cpu',weights_only=True) if (data/'development_parents.pt').exists() else None
    ready=read(ROOT/'DATA_SUMMARY.json');train_windows=dev_windows=local=None;world=None;bootstrap=None
    if kind=='D':
        model=WorldModel(norm).cuda();train_windows=Windows('train');dev_windows=Windows('dev')
        if (data/'train_local.pt').exists():local={k:v.cuda() for k,v in torch.load(data/'train_local.pt',map_location='cpu',weights_only=True).items()}
        optimizer=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=1e-4)
    elif kind=='G0':
        if not ready['G0_ready']:raise ValueError('G0 supervision gap')
        model=BenefitModel(norm).cuda();ds=1241 if seed==1341 else 1242
        world=WorldModel(norm).cuda();world.load_state_dict(torch.load(ROOT/'fits'/('D_'+str(ds))/'final.pt',map_location='cuda',weights_only=True));world.eval().requires_grad_(False)
        eligible=torch.where(parents['G0_valid'])[0].numpy()
        optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,weight_decay=1e-3)
    elif kind=='Q':
        if not ready['Q_ready']:raise ValueError('Q supervision gap')
        model=TenStepCritic(torch.load(data/'Q_PREPROCESSING.pt',map_location='cpu',weights_only=True)).cuda()
        assert sum(p.numel() for p in model.parameters())==7058 and all(p.requires_grad for p in model.parameters())
        eligible=torch.where(parents['candidate_weights'][:,0]>0)[0].numpy();bootstrap=[]
        for task in sorted(set(parents['tasks'])):
            ids=[int(i) for i in eligible if parents['tasks'][i]==task]
            if ids:bootstrap.extend(rng.choice(ids,len(ids),replace=True).tolist())
        new_json(out/'BOOTSTRAP.json',dict(train_parent_indices=bootstrap,train_only=True,seed=seed))
        optimizer=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=.01)
    else:raise ValueError(kind)
    model.train();updates=0;history=[]
    def state(values,ids):return {k:values[k][ids].to('cuda') for k in STATE_KEYS}
    def dev_metric():
        model.eval()
        with torch.no_grad():
            if kind=='D':
                if not dev_windows.size:return None
                ids=np.linspace(0,dev_windows.size-1,min(128,dev_windows.size),dtype=int)
                scores=[float(objective(model,dev_windows.take(ids[i:i+32]))) for i in range(0,len(ids),32)]
                value=dict(future5_loss=float(np.mean(scores)),descriptive_windows=len(ids))
            elif kind=='G0':
                ids=torch.where(dev['G0_valid'])[0] if dev is not None else []
                if not len(ids):return None
                batch=state(dev,ids);batch['actions']=dev['old_five'][ids].cuda();future,_=world(batch);pred=model(batch,future)
                target=dev['G0_target'][ids].cuda();value=dict(MAE=float((pred-target).abs().mean()),MSE=float((pred-target).square().mean()),parents=len(ids))
            else:
                ids=torch.where(dev['candidate_weights'][:,0]>0)[0] if dev is not None else []
                if not len(ids):return None
                logits=model(model.features(state(dev,ids)),dev['actions'][ids].cuda())
                value=dict(L11=float(q_loss(logits,dev['labels'][ids].cuda(),dev['candidate_weights'][ids].cuda(),dev['gain_weights'][ids].cuda(),dev['pair_weight'][ids].cuda())),parents=len(ids))
        model.train();return value
    fatal=None
    try:
        for step in range(1,4001):
            boundary();optimizer.zero_grad(set_to_none=True)
            if kind=='D':
                batch=train_windows.take(rng.integers(train_windows.size,size=64));loss=objective(model,batch)
                if local:
                    ids=torch.as_tensor(rng.integers(len(local['history']),size=16),device='cuda')
                    paired={k:v[ids].flatten(0,1) for k,v in local.items()}
                    loss=.5*loss+.5*objective(model,paired,pair=True)
            elif kind=='G0':
                ids=rng.choice(eligible,16,replace=True);batch=state(parents,ids);batch['actions']=parents['old_five'][ids].cuda()
                with torch.no_grad():future,_=world(batch)
                prediction=model(batch,future);loss=F.smooth_l1_loss(prediction,parents['G0_target'][ids].cuda(),beta=.1)
            else:
                ids=rng.choice(bootstrap,16,replace=True);features=model.features(state(parents,ids));logits=model(features,parents['actions'][ids].cuda())
                loss=q_loss(logits,parents['labels'][ids].cuda(),parents['candidate_weights'][ids].cuda(),parents['gain_weights'][ids].cuda(),parents['pair_weight'][ids].cuda())
            if not torch.isfinite(loss):raise FloatingPointError('nonfinite head loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step();updates+=1
            if step%100==0:
                progress=dict(kind=kind,seed=seed,updates=updates,loss=float(loss.detach()),at_utc=utc(),elapsed_seconds=time.monotonic()-begin)
                if step%1000==0:progress['development']=dev_metric();history.append(progress)
                atomic_json(out/'PROGRESS.json',progress)
        torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},out/'final.pt')
    except BaseException as exc:fatal=repr(exc);raise
    finally:
        atomic_json(out/'RESULT.json',dict(status='complete' if updates==4000 and fatal is None else 'partial',kind=kind,seed=seed,
            updates=updates,reserved_update_cap=4000,fatal=fatal,history=history,at_utc=utc(),elapsed_seconds=time.monotonic()-begin,
            parameters=sum(p.numel() for p in model.parameters()),all_parameters_trained=True,initialization='from scratch',
            checkpoint_selection='fixed4000 final, no test or dev selection',normalization_PCA_train_only=True,
            checkpoint=str(out/'final.pt') if (out/'final.pt').exists() else None))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--kind',choices=['D','G0','Q'],required=True);p.add_argument('--seed',type=int,required=True);a=p.parse_args();main(a.kind,a.seed)
