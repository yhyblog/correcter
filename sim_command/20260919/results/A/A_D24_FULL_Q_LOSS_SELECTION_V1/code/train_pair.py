"""One fit/member pair, four fresh models sharing initialization and batch stream."""
import argparse,copy,hashlib,json,os,signal,time,traceback
from pathlib import Path
import paths
from paths import ROOT,TASK
from qio import read,new_json,atomic_json,utc,sha,process_identity
from admission import authority,admissions_allowed,before_cutoff

def paired_seed(fit,member,kind):
 return int.from_bytes(hashlib.sha256(f'corrector_fullQ_paired_v1|{fit}|{member}|{kind}'.encode()).digest()[:8],'big')%(2**63)

def fit_pair(fit,member):
 authority()
 cfg=read(ROOT/'config/TRAIN.json');out=ROOT/'training'/f's{fit}_m{member}';out.mkdir(parents=True,exist_ok=False)
 new_json(out/'CLAIM.json',dict(task_id=TASK,fit_seed=fit,member=member,max_updates=16000,utc=utc(),process=process_identity()))
 start=time.monotonic();completed={};current=None;step=0;fatal=None;stopping=False
 def stop(*_):
  nonlocal stopping
  stopping=True
 for s in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(s,stop)
 def boundary():
  if stopping or not admissions_allowed() or not before_cutoff() or time.monotonic()-start>7200:raise RuntimeError('training admission stop/time limit')
 try:
  import numpy as np
  import torch
  from corrector.critic import STATE_KEYS,TenStepCritic
  from loss_formula import e1_loss
  torch.set_num_threads(2)
  rows=read(cfg['train_rows'])
  if len(rows)!=600 or any(r['split']!='train' for r in rows):raise ValueError('train600 identity')
  with np.load(cfg['train_arrays'],allow_pickle=False) as archive:
   arrays={k:torch.from_numpy(archive[k].copy()) for k in STATE_KEYS+['actions','outcomes','candidate_weights','gain_weights','pair_weights']}
  if arrays['actions'].shape!=(600,13,10,4) or arrays['outcomes'].shape!=(600,13,4):raise ValueError('training shape')
  if not bool(torch.isfinite(arrays['actions']).all()) or bool((arrays['actions'].abs()>1).any()):raise ValueError('action units')
  old_path=Path(cfg['preprocessing_only_assets'])/'models/refit'/f'member_{member}'/'selected.pt'
  old=torch.load(old_path,map_location='cpu',weights_only=True)
  preprocessing={k:old[k].detach().clone() for k in cfg['preprocessing_fields']};del old
  torch.manual_seed(paired_seed(fit,member,'initialization'))
  initial=TenStepCritic(preprocessing).requires_grad_(True)
  if sum(p.numel() for p in initial.parameters())!=7058:raise ValueError('full Q architecture')
  with (out/'initial.pt').open('xb') as f:torch.save(initial.state_dict(),f)
  names={name:p.numel() for name,p in initial.named_parameters() if p.requires_grad}
  init_params={name:p.detach().clone() for name,p in initial.named_parameters()}
  boot_rng=np.random.default_rng(paired_seed(fit,member,'bootstrap'));pool=[]
  for task in sorted({r['task'] for r in rows}):
   ids=[i for i,r in enumerate(rows) if r['task']==task];pool.extend(boot_rng.choice(ids,len(ids),replace=True).tolist())
  pool=np.asarray(pool,dtype=np.int64);batch_rng=np.random.default_rng(paired_seed(fit,member,'minibatches'))
  batches=pool[batch_rng.integers(0,len(pool),(4000,32))]
  with (out/'minibatches.npy').open('xb') as f:np.save(f,batches,allow_pickle=False)
  with torch.no_grad():features=torch.cat([initial.features({k:arrays[k][i:i+1] for k in STATE_KEYS}) for i in range(600)])
  new_json(out/'INPUT_READY.json',dict(utc=utc(),fit_seed=fit,member=member,trainable_parameters=sum(names.values()),trainable_names=names,
   train_rows=cfg['train_rows'],train_arrays=cfg['train_arrays'],preprocessing_only_from=str(old_path),preprocessing_keys=cfg['preprocessing_fields'],old_network_loaded=False,
   initialization_seed=paired_seed(fit,member,'initialization'),bootstrap_seed=paired_seed(fit,member,'bootstrap'),batch_seed=paired_seed(fit,member,'minibatches'),
   initialization=str(out/'initial.pt'),initialization_sha256=sha(out/'initial.pt'),minibatches=str(out/'minibatches.npy'),minibatches_sha256=sha(out/'minibatches.npy'),bootstrap=pool.tolist(),CPU=True))
  for loss in cfg['losses']:
   boundary();current=loss;step=0;dest=out/loss;dest.mkdir(exist_ok=False)
   model=copy.deepcopy(initial).train().requires_grad_(True)
   assert all(torch.equal(p,init_params[n]) for n,p in model.named_parameters())
   optimizer=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=.01)
   new_json(dest/'ENTERED.json',dict(utc=utc(),updates_cap=4000,trainable_parameters=7058,initialization=str(out/'initial.pt'),minibatches=str(out/'minibatches.npy')))
   begin=time.monotonic();metrics={}
   for index in range(4000):
    if index%50==0:boundary()
    chosen=batches[index];optimizer.zero_grad(set_to_none=True)
    logits=model(features[chosen],arrays['actions'][chosen])
    parts=e1_loss(logits,arrays['outcomes'][chosen],candidate_weights=arrays['candidate_weights'][chosen],gain_weights=arrays['gain_weights'][chosen],pair_weights=arrays['pair_weights'][chosen],gain_enabled=loss in ['L10','L11'],pair_enabled=loss in ['L01','L11'])
    if not bool(torch.isfinite(parts['loss'])):raise ValueError('nonfinite training loss')
    parts['loss'].backward();grad=torch.nn.utils.clip_grad_norm_(model.parameters(),1.)
    if not bool(torch.isfinite(grad)):raise ValueError('nonfinite training gradient')
    optimizer.step();step=index+1
    if step%100==0:
     metrics={k:float(v.detach()) for k,v in parts.items()}
     atomic_json(out/'PROGRESS.json',dict(utc=utc(),status='training',fit_seed=fit,member=member,loss=loss,step=step,completed_losses=list(completed),actual_completed_updates=4000*len(completed)+step,elapsed_seconds=time.monotonic()-start,metrics_last_minibatch=metrics))
   optimizer.zero_grad(set_to_none=True);model.eval().requires_grad_(False)
   changes={}
   for module in cfg['modules']:
    params=[(n,p) for n,p in model.named_parameters() if n.startswith(module+'.')]
    changes[module]={'parameters':sum(p.numel() for _,p in params),'changed_tensors':sum(not torch.equal(p,init_params[n]) for n,p in params),'delta_l2':float(sum((p-init_params[n]).square().sum() for n,p in params).sqrt())}
   checkpoint=dest/'final.pt'
   with checkpoint.open('xb') as f:torch.save({k:v.detach().cpu().clone() for k,v in model.state_dict().items()},f)
   row=dict(status='complete',loss=loss,fit_seed=fit,member=member,updates=4000,trainable_parameters=7058,modules=changes,checkpoint=str(checkpoint),checkpoint_sha256=sha(checkpoint),elapsed_seconds=time.monotonic()-begin,metrics_last_minibatch=metrics,initialization=str(out/'initial.pt'),minibatches=str(out/'minibatches.npy'),selected_at_fixed_update=4000,utc=utc())
   new_json(dest/'RESULT.json',row);completed[loss]=row
 except BaseException as error:fatal=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
 final=dict(task_id=TASK,status='complete' if len(completed)==4 and fatal is None else 'partial_or_failed',fit_seed=fit,member=member,completed=completed,current_loss=current,current_loss_steps=step,actual_updates=4000*len(completed)+(step if current not in completed else 0),elapsed_seconds=time.monotonic()-start,fatal=fatal,utc=utc())
 new_json(out/'RESULT.json',final)
 return 0 if final['status']=='complete' else 3

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--fit',type=int,required=True);p.add_argument('--member',type=int,required=True);a=p.parse_args();raise SystemExit(fit_pair(a.fit,a.member))
