"""One authorized fixed4000 full-Q fit, with a paired scratch state and batches."""
import argparse,signal,time,traceback
import numpy as np
import torch
import torch.nn.functional as F
import paths
from paths import ROOT,TASK
from qio import read,new_json,atomic_json,utc,sha,process_identity
from admission import boundary
from corrector.critic import from_state

def loss_parts(logits,batch,loss):
    def avg(v,w):return ((v*w).sum(-1)/w.sum(-1).clamp_min(1)).mean()
    p=logits.sigmoid();y=batch['labels']
    bce=avg(F.binary_cross_entropy_with_logits(logits,y,reduction='none'),batch['candidate_weights'])
    gain=avg(((p-p[:,:1])-(y-y[:,:1])).square(),batch['gain_weights'])
    pair=(((p[:,1]-p[:,2])-(y[:,1]-y[:,2])).square()*batch['pair_weight']).mean()
    return dict(loss=bce+int(loss in ['L10','L11'])*gain+.5*int(loss in ['L01','L11'])*pair,bce=bce,gain=gain,pair=pair)

def main(loss,member):
    boundary(True);cfg=read(ROOT/'config/TRAIN.json');assert loss in cfg['losses'] and member in cfg['members']
    torch.set_num_threads(2);out=ROOT/'training'/f'{loss}_s9101_m{member}';out.mkdir(parents=True,exist_ok=False)
    source=ROOT/'inputs'/f's9101_m{member}';initial=torch.load(source/'initial.pt',map_location='cpu',weights_only=True)
    new_json(out/'CLAIM.json',dict(task_id=TASK,utc=utc(),process=process_identity(),loss=loss,member=member,updates_cap=4000,initialization=str(source/'initial.pt'),minibatches=str(source/'minibatches.npy')))
    updates=0;fatal=None;begin=time.monotonic();model=None;metrics={};changes={};stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,stop)
    try:
        model=from_state(initial).cuda().train().requires_grad_(True)
        assert sum(p.numel() for p in model.parameters())==7058 and all(p.requires_grad for p in model.parameters())
        arrays={k:v.cuda() for k,v in torch.load(ROOT/'inputs/TRAIN.pt',map_location='cpu',weights_only=True).items()}
        batches=torch.as_tensor(np.load(source/'minibatches.npy'),device='cuda')
        optimizer=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.01)
        for step in range(4000):
            if step%50==0:
                boundary()
                if stopping:raise RuntimeError('owned fit stopped')
            batch={k:v[batches[step]] for k,v in arrays.items()};optimizer.zero_grad(set_to_none=True)
            parts=loss_parts(model(batch['features'],batch['actions']),batch,loss)
            if not bool(torch.isfinite(parts['loss'])):raise ValueError('nonfinite Q loss')
            parts['loss'].backward();grad=torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
            if not bool(torch.isfinite(grad)):raise ValueError('nonfinite Q gradient')
            optimizer.step();updates=step+1
            if updates%100==0:
                metrics={k:float(v.detach()) for k,v in parts.items()}
                atomic_json(out/'PROGRESS.json',dict(utc=utc(),loss=loss,member=member,updates=updates,metrics=metrics,elapsed_seconds=time.monotonic()-begin))
        for name,module in model.named_children():
            entries=[(n,p.detach().cpu()) for n,p in module.named_parameters()]
            changes[name]=dict(parameters=sum(p.numel() for _,p in entries),
                changed_tensors=sum(not torch.equal(p,initial[name+'.'+n]) for n,p in entries),
                delta_l2=float(sum((p-initial[name+'.'+n]).square().sum() for n,p in entries).sqrt()))
        assert all(v['delta_l2']>0 for v in changes.values())
        assert all(torch.equal(v.detach().cpu(),initial[k]) for k,v in model.named_buffers())
        with (out/'final.pt').open('xb') as f:torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},f)
    except BaseException as exc:fatal=dict(error=repr(exc),traceback=traceback.format_exc())
    result=dict(status='complete' if updates==4000 and fatal is None else 'partial_or_failed',task_id=TASK,utc=utc(),loss=loss,member=member,fit_seed=9101,
        updates=updates,trainable_parameters=7058,modules=changes,preprocessing_unchanged=fatal is None,
        initialization=str(source/'initial.pt'),minibatches=str(source/'minibatches.npy'),old_network_loaded=False,
        checkpoint=str(out/'final.pt') if (out/'final.pt').exists() else None,
        checkpoint_sha256=sha(out/'final.pt') if (out/'final.pt').exists() else None,
        metrics_last_minibatch=metrics,fatal=fatal,elapsed_seconds=time.monotonic()-begin,selected_at_fixed_update=4000)
    new_json(out/'RESULT.json',result);return 0 if result['status']=='complete' else 3

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--loss',required=True);p.add_argument('--member',type=int,required=True);a=p.parse_args();raise SystemExit(main(a.loss,a.member))
