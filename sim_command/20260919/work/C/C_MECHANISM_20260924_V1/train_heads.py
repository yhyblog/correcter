"""Matched-input risk target and properly retrained no-D benefit control."""
import argparse,time
import paths
from paths import ROOT,TRAIN_ROOT
from common import read,write,check

def main(mode,member):
    import torch,numpy as np
    import torch.nn.functional as F
    from ac_tmil.future_aware.data import LocalData
    from ac_tmil.future_aware.models import BenefitModel
    from ac_tmil.future_aware.critic import load_world,crossfit_predictions,predict_all
    torch.set_num_threads(2);torch.manual_seed(member);torch.cuda.set_device(0)
    out=ROOT/'heads'/f'{mode}_{member}';out.mkdir(parents=True,exist_ok=False)
    train=LocalData(TRAIN_ROOT,'train','spatial');val=LocalData(TRAIN_ROOT,'validation','spatial')
    assert not ({r['source'] for r in train.groups}&{r['source'] for r in val.groups})
    world,norm=load_world(TRAIN_ROOT,241+(member%2==0));world.requires_grad_(False)
    if mode=='risk':
        # Identical source-level D cross-fitting procedure used for original G0.
        tf,folds=crossfit_predictions(TRAIN_ROOT,train,241+(member%2==0));vf=predict_all(world,val)
    else:tf=vf=None;folds=[]
    torch.manual_seed(member)
    # Keep capacity exactly matched; no-D effect input is zero in BOTH fit and deployment.
    model=BenefitModel(norm).cuda();optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,weight_decay=1e-3)
    weights=torch.tensor([1/sum(r['source']==g['source'] for r in train.groups) for g in train.groups],device='cuda:0');weights/=weights.sum()
    def batch(data,idx,future):
        b={k:v[idx,0] for k,v in data.values.items()}
        f=future[idx,0] if future is not None else b['history'][:,-1,None].expand(-1,5,-1)
        means=data.values['successes'][idx]/data.values['repeats'][idx]
        y=1-means[:,0] if mode=='risk' else means[:,1:].mean(-1)-means[:,0]
        return b,f,y
    best=float('inf');history=[];begin=time.time()
    for step in range(1,1601):
        check();idx=torch.multinomial(weights,16,replacement=True);b,f,y=batch(train,idx,tf)
        model.train();optimizer.zero_grad(set_to_none=True);p=model(b,f)
        loss=F.binary_cross_entropy_with_logits(p,y) if mode=='risk' else F.smooth_l1_loss(p,y,beta=.1)
        loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1);optimizer.step()
        if step%200==0:
            model.eval();errs=[]
            with torch.no_grad():
                for i in range(len(val)):
                    b,f,y=batch(val,slice(i,i+1),vf);p=model(b,f)
                    errs.append(float(F.binary_cross_entropy_with_logits(p,y) if mode=='risk' else (p-y).abs().mean()))
            groups={}
            for g,e in zip(val.groups,errs):groups.setdefault(g['source'],[]).append(e)
            metric=float(np.mean([np.mean(x) for x in groups.values()]));history.append(dict(step=step,validation_metric=metric,loss=float(loss)))
            if metric<best:best=metric;selected=step;torch.save(model.state_dict(),out/'selected.pt')
            write(out/'PROGRESS.json',dict(step=step,history=history))
    write(out/'RESULT.json',dict(status='complete',mode=mode,member=member,selected_step=selected,validation_metric=best,history=history,train_parents=sorted({r['source'] for r in train.groups}),validation_parents=sorted({r['source'] for r in val.groups}),target='failure_old_execute5_native10' if mode=='risk' else 'fresh_minus_old_execute5_native10',parameters=sum(p.numel() for p in model.parameters()),crossfit=folds,new_test_used=False,source_weighting='uniform parent, uniform cuts within parent',capacity_matched=True,noD_training_and_inference_matched=mode=='nod',seconds=time.time()-begin))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['risk','nod']);p.add_argument('member',type=int);a=p.parse_args();main(a.mode,a.member)
