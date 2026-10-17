"""One fixed full-Q fit. Frozen tensors, paired initialization and minibatches."""
import argparse
import time
import traceback
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
import paths
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity
from admission import boundary
from corrector.critic import from_state

def parts(logits, data, ids):
    def average(values, weights):
        denominator=weights.sum(-1)
        return ((values*weights).sum(-1)/torch.where(denominator>0,denominator,torch.ones_like(denominator))).mean()
    y=data['labels'][ids];p=logits.sigmoid()
    bce=average(F.binary_cross_entropy_with_logits(logits,y,reduction='none'),data['candidate_weights'][ids])
    gain=average(((p-p[:,:1])-(y-y[:,:1])).square(),data['gain_weights'][ids])
    pair=(((p[:,1]-p[:,2])-(y[:,1]-y[:,2])).square()*data['pair_weight'][ids]).mean()
    return bce,gain,pair

def main(loss_name,member):
    boundary(admission=True);torch.set_num_threads(4)
    pipeline=Path(CONFIG['root_pipeline']);prepared=pipeline/'prepared'
    ident=loss_name+'_fit9101_member'+str(member);out=ROOT/'fits'/ident
    out.mkdir(parents=True,exist_ok=False)
    new_json(ROOT/'claims/fits'/(ident+'.json'),dict(task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],
        loss=loss_name,fit_seed=9101,member=member,process=process_identity(),reserved_updates=4000,at_utc=utc()))
    initial=torch.load(prepared/('initial_'+str(member)+'.pt'),map_location='cpu',weights_only=True)
    model=from_state(initial).cuda().train()
    assert sum(p.numel() for p in model.parameters())==7058 and all(p.requires_grad for p in model.parameters())
    data={k:v.cuda() for k,v in torch.load(prepared/'TRAIN_TENSORS.pt',map_location='cpu',weights_only=True).items()}
    batches=torch.as_tensor(np.load(prepared/('batches_'+str(member)+'.npy')),device='cuda')
    optimizer=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=.01)
    gain_on=loss_name in ['L10','L11'];pair_on=loss_name in ['L01','L11']
    updates=0;fatal=None;begin=time.monotonic();last=None
    new_json(out/'MODEL_READY.json',dict(at_utc=utc(),process=process_identity(),parameters=7058,
        trainable_parameters=7058,all_modules_trainable=['state','action','head','residual','advantage'],
        initialization='new untrained member shared across four losses; no old selected network',device='cuda:0'))
    try:
        for step,ids in enumerate(batches,1):
            boundary();optimizer.zero_grad(set_to_none=True)
            logits=model(data['features'][ids],data['actions'][ids]);bce,gain,pair=parts(logits,data,ids)
            loss=bce+int(gain_on)*gain+int(pair_on)*.5*pair
            if not torch.isfinite(loss):raise FloatingPointError('nonfinite full-Q loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step();updates=step
            if step%100==0:
                last=dict(at_utc=utc(),process=process_identity(),updates=updates,loss=float(loss.detach()),
                    BCE=float(bce.detach()),gain=float(gain.detach()),pair=float(pair.detach()),elapsed_seconds=time.monotonic()-begin)
                atomic_json(out/'PROGRESS.json',last)
        changes={}
        for name in ['state','action','head','residual','advantage']:
            values=[float((p.detach().cpu()-initial[k]).square().sum()) for k,p in model.named_parameters() if k.startswith(name+'.')]
            changes[name]=float(sum(values)**.5)
        assert all(v>0 for v in changes.values())
        checkpoint=out/'final.pt';torch.save({k:v.detach().cpu() for k,v in model.state_dict().items()},checkpoint)
    except BaseException as exc:
        fatal=dict(error=repr(exc),traceback=traceback.format_exc());raise
    finally:
        new_json(out/'RESULT.json',dict(status='complete' if updates==4000 and fatal is None else 'partial',at_utc=utc(),
            task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],loss=loss_name,fit_seed=9101,member=member,updates=updates,
            reserved_update_cap=4000,parameters=7058,trainable_parameters=7058,all_parameters_trained=True,
            initialization='shared untrained initialization',batch_size=32,optimizer='AdamW lr3e-4 wd0.01 clip1',
            coefficients=dict(BCE=1,gain=int(gain_on),pair=.5*int(pair_on)),
            module_parameter_change_L2=changes if fatal is None else None,fatal=fatal,last_progress=last,
            checkpoint=str(out/'final.pt') if (out/'final.pt').exists() else None,
            checkpoint_selection='fixed4000 last; no development/test seed selection',elapsed_seconds=time.monotonic()-begin,
            peak_GPU_allocated_bytes=int(torch.cuda.max_memory_allocated()),new_collection=0,D_G0_base_updates=0))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--loss',choices=['L00','L10','L01','L11'],required=True);p.add_argument('--member',type=int,required=True)
    a=p.parse_args();main(a.loss,a.member)
