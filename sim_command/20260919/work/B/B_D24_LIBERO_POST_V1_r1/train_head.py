"""Fixed-step CPU fitting from new LIBERO development rollouts only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import d24_common as d


def main(batch_path):
    import numpy as np
    import torch
    from native_head import Head, FEATURE_DIM, action_norm
    cfg=d.load(batch_path);out=d.R/cfg['batch_id'];spec=cfg['adaptation']
    d.authorize(admission=True)
    if torch.cuda.is_initialized():
        raise RuntimeError('Small-head fitting must stay on CPU')
    torch.set_num_threads(4)
    d.exclusive(out/'FIT_CLAIM.json',dict(at_utc=d.utc(),process=d.identity(),steps_per_member=spec['fit_steps'],
        seeds=spec['fit_seeds'],test_rows_used=0,base_model_updates=0))
    examples=[]
    for job in cfg['jobs']:
        p=Path(job['output']);done=d.load(p/'DEV_DONE.json')
        if done['planned'] != done['recorded']:
            raise RuntimeError('Development collection incomplete')
        for line in (p/'development.jsonl').read_text().splitlines():
            row=json.loads(line)
            if row['split'] not in ('adapt_train','adapt_validation'):
                raise ValueError('Forbidden fitting source split')
            if row['status'] != 'complete' or not row.get('cut_data'):
                continue
            with np.load(row['cut_data'],allow_pickle=False) as z:
                f=z['feature'].copy();a=z['candidate'][:5].copy();a0=z['reference'][:5].copy()
            if f.shape != (FEATURE_DIM,) or type(row['success']) is not bool:
                raise ValueError('Malformed native development observation/outcome')
            examples.append((row,f,a,a0))
    train=[e for e in examples if e[0]['split']=='adapt_train']
    validation=[e for e in examples if e[0]['split']=='adapt_validation']
    train_parents={e[0]['parent_id'] for e in train};val_parents={e[0]['parent_id'] for e in validation}
    if train_parents & val_parents:
        raise ValueError('Parent leakage across adaptation split')
    if len(train)<40 or len(train_parents)<8 or len({e[0]['success'] for e in train})<2:
        diagnosis=dict(status='blocked',reason='insufficient real development success/failure contrast',
            train_rows=len(train),train_parents=len(train_parents),
            train_successes=sum(e[0]['success'] for e in train),validation_rows=len(validation),
            fabricated_labels=0,test_started=False,optimizer_updates=0,at_utc=d.utc())
        d.atomic(out/'FIT_DIAGNOSIS.json',diagnosis)
        raise RuntimeError(diagnosis['reason'])
    stats=d.load(cfg['norm_stats'])['norm_stats'];mid,scale=action_norm(stats)
    feature=np.stack([e[1] for e in train]).astype(np.float64)
    mean=feature.mean(0);std=np.maximum(feature.std(0),.05)
    def matrix(rows):
        return np.stack([np.concatenate(((f-mean)/std,((a-mid)/scale).reshape(-1),
                                          ((a0-mid)/scale).reshape(-1))) for _,f,a,a0 in rows]).astype(np.float32)
    x=torch.from_numpy(matrix(train));y=torch.tensor([float(e[0]['success']) for e in train])[:,None]
    vx=torch.from_numpy(matrix(validation)) if validation else None
    vy=torch.tensor([float(e[0]['success']) for e in validation])[:,None] if validation else None
    state=dict(feature_mean=mean,feature_std=std,action_mid=mid,action_scale=scale,members=np.asarray(len(spec['fit_seeds'])))
    reports=[];models=[];updates=0;started=time.monotonic()
    pos_weight=(1-y).sum()/y.sum()
    for m,seed in enumerate(spec['fit_seeds']):
        d.authorize(admission=True)
        torch.manual_seed(seed)
        model=torch.nn.Sequential(torch.nn.Linear(FEATURE_DIM+70,128),torch.nn.ReLU(),
            torch.nn.Linear(128,64),torch.nn.ReLU(),torch.nn.Linear(64,1))
        optimizer=torch.optim.AdamW(model.parameters(),lr=spec['fit_lr'],weight_decay=spec['fit_weight_decay'])
        generator=torch.Generator().manual_seed(seed+1)
        for step in range(spec['fit_steps']):
            d.authorize()
            indices=torch.randint(len(train),(spec['fit_batch_size'],),generator=generator)
            loss=torch.nn.functional.binary_cross_entropy_with_logits(model(x[indices]),y[indices],pos_weight=pos_weight)
            optimizer.zero_grad();loss.backward();optimizer.step();updates+=1
            if (step+1)%250==0:
                progress=dict(member=m,seed=seed,step=step+1,optimizer_updates=updates,
                              training_loss=float(loss.detach()),at_utc=d.utc())
                d.atomic(out/'FIT_PROGRESS.json',progress);print(json.dumps(progress),flush=True)
        model.eval();models.append(model)
        with torch.no_grad():
            report=dict(seed=seed,steps=spec['fit_steps'],
                train_bce=float(torch.nn.functional.binary_cross_entropy_with_logits(model(x),y)),
                train_accuracy=float(((model(x)>0)==y.bool()).float().mean()),
                validation_bce=float(torch.nn.functional.binary_cross_entropy_with_logits(model(vx),vy)) if validation else None,
                validation_accuracy=float(((model(vx)>0)==vy.bool()).float().mean()) if validation else None)
        reports.append(report)
        for layer,index in enumerate((0,2,4)):
            state['m%d_w%d'%(m,layer)]=model[index].weight.detach().numpy().copy()
            state['m%d_b%d'%(m,layer)]=model[index].bias.detach().numpy().copy()
    temp=out/'native_head.tmp.npz';np.savez_compressed(str(temp),**state)
    model_path=out/'native_head.npz';os.replace(str(temp),str(model_path))
    # Check the exported inference and its action derivative on actual training rows.
    head=Head(model_path);errors=[]
    for i,e in enumerate(train[:4]):
        inp=x[i].detach().clone().requires_grad_(True)
        q=torch.stack([torch.sigmoid(model(inp)) for model in models]).mean()
        grad=torch.autograd.grad(q,inp)[0][FEATURE_DIM:FEATURE_DIM+35].detach().numpy().reshape(5,7)/scale
        nq,ng=head.q_grad(e[1],e[2],e[3])
        errors.append(dict(q_abs=abs(float(q)-nq),grad_max_abs=float(np.max(np.abs(grad-ng)))))
    if max(e['q_abs'] for e in errors)>1e-5 or max(e['grad_max_abs'] for e in errors)>1e-4:
        raise RuntimeError('Native head export/gradient mismatch')
    report=dict(status='complete',at_utc=d.utc(),model_path=str(model_path),
        model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
        optimizer_updates=updates,base_model_updates=0,train_rows=len(train),validation_rows=len(validation),
        train_parent_ids=sorted(train_parents),validation_parent_ids=sorted(val_parents),
        train_successes=int(y.sum()),validation_successes=int(vy.sum()) if validation else 0,
        feature_version=spec['feature_version'],feature_dim=FEATURE_DIM,
        checkpoint_choice='all fixed final-step members; validation is descriptive only; no test input',
        export_validation=errors,members=reports,elapsed_seconds=time.monotonic()-started)
    d.atomic(out/'FIT_RESULT.json',report)
    d.atomic(out/'MODEL_READY.json',report)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True)
    main(p.parse_args().batch)
