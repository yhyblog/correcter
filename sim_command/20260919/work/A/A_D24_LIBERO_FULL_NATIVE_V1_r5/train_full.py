"""True native development labels -> fixed D2/G0/L11 fits -> frozen test gate."""
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import d24_common as d
from context import context,stack

def main():
    d.authorize(admission=True);batch=d.load(d.W/'BATCH.json');cfg=d.load(batch['jobs'][0]['config']);spec=cfg['adaptation']
    d.exclusive(d.R/'FIT_CLAIM.json',dict(utc=d.utc(),process=d.identity(),max_updates=32000,test_rows=0))
    samples=[];pairs={};all_rows=[];invalid=[]
    for job in batch['jobs']:
        output=Path(job['output']);done=d.load(output/'DEV_DONE.json')
        if done['planned']!=done['recorded']:raise ValueError('Development attempts not accounted')
        for line in (output/'development.jsonl').read_text().splitlines():
            row=json.loads(line);all_rows.append(row)
            if row['split'] not in ('adapt_train','adapt_validation'):raise ValueError('No test fitting')
            if row['status']!='complete' or type(row['success']) is not bool or not row.get('valid_D_feature_clock'):
                invalid.append(dict(source=row['source_id'],reason='technical outcome or missing real feature clock'));continue
            with np.load(row['trajectory'],allow_pickle=False) as z:
                f=z['features'].copy();a=z['actions'].copy();starts=z['chunk_starts'].copy()
            if len(f)!=len(a)+1 or f.shape[1:]!=(329,) or a.shape[1:]!=(7,):raise ValueError('Native D data shape')
            for step in starts:
                step=int(step)
                if step+2>=len(f):continue
                value=context(list(f[:step+1]),list(a[:step]),step);value['actions']=a[step:step+2]
                samples.append(dict(parent=row['parent_id'],split=row['split'],input=value,
                    visual_target=f[step+1:step+3,:192],proprio_target=f[step+1:step+3,320:328]))
            if row.get('cut_data'):
                with np.load(row['cut_data'],allow_pickle=False) as z:cut={k:z[k].copy() for k in z.files}
                pairs.setdefault(row['parent_id'],{})[row['branch']]=(row,cut)
    if len(all_rows)!=40:raise ValueError('Exactly the40 frozen additional development attempts required')
    benefits=[];label_rows=[]
    for parent,branches in sorted(pairs.items()):
        if set(branches)!={'old','fresh'}:
            invalid.append(dict(parent=parent,reason='missing real old/fresh terminal pair'));continue
        (old,oc),(fresh,fc)=branches['old'],branches['fresh']
        aligned=(old['cut_step']==fresh['cut_step']==2 and old['policy_seed']==fresh['policy_seed'] and
            old['reset_seed']==fresh['reset_seed'] and oc['old3'].shape==(3,7) and
            np.allclose(oc['prefix_actions'],fc['prefix_actions'],rtol=1e-5,atol=1e-6))
        if not aligned:
            invalid.append(dict(parent=parent,reason='native firstage2/prefix action stream not aligned'));continue
        target=float(fresh['success'])-float(old['success'])
        inp={k:oc[k] for k in ['history','history_mask','past_actions','proprio','proprio_mask','language','remaining']}
        inp['actions']=oc['old3']
        benefits.append(dict(parent=parent,split=old['split'],input=inp,target=target))
        label_rows.append(dict(parent_id=parent,split=old['split'],old_success=old['success'],fresh_success=fresh['success'],
            benefit=target,old_source=old['source_id'],fresh_source=fresh['source_id'],cut=2,repeats_per_branch=1,
            definition='execute3_then_native5; old continues queued3, fresh newly samples3',physical_state_equivalence_proven=None))
    train=[x for x in samples if x['split']=='adapt_train'];val=[x for x in samples if x['split']=='adapt_validation']
    gt=[x for x in benefits if x['split']=='adapt_train'];gv=[x for x in benefits if x['split']=='adapt_validation']
    qstatus=d.load(d.R/'Q_DATA_STATUS.json')
    status=dict(utc=d.utc(),development_prior_attempts=160,development_new_attempts=len(all_rows),development_cumulative=200,
        new_parent_identities=0,complete_new_attempts=sum(r['status']=='complete' for r in all_rows),
        technical_failures=sum(r['status']!='complete' for r in all_rows),D_train_rows=len(train),D_validation_rows=len(val),
        G0_train_pairs=len(gt),G0_validation_pairs=len(gv),G0_train_targets=[r['target'] for r in gt],
        G0_validation_targets=[r['target'] for r in gv],G0_labels=label_rows,Q=qstatus,invalid=invalid,
        actual_future_observations=True,observed_one_pair_labels_not_success_probabilities=True,test_labels_used=0)
    d.atomic(d.R/'DATA_STATUS.json',status)
    reasons=[]
    if not train:reasons.append('no genuine D2 feature/action/target window')
    if len({r['target'] for r in gt})<2:reasons.append('G0 train old3/fresh3 terminal benefit has no variation (not perturbation labels)')
    if not qstatus['Q_L11_supervision_ready']:reasons.append('Q lacks actual common-parent/cut gain or pair contrast')
    if reasons:
        gap=dict(utc=d.utc(),status='SCIENTIFIC_GAP',reasons=reasons,data_status=str(d.R/'DATA_STATUS.json'),
                 optimizer_updates=0,test_attempts=0,threshold_changed=False,extra_development_allowed=False)
        d.atomic(d.R/'SCIENTIFIC_GAP.json',gap);d.atomic(d.R/'FIT_SUMMARY.json',gap);return

    import torch
    from native_models import WorldModel,BenefitModel,masked_mse
    from native_head import action_norm
    torch.set_num_threads(4)
    out=d.R/'models';out.mkdir(exist_ok=False);updates=0;reports=[];start=time.monotonic()
    history=np.concatenate([x['input']['history'][x['input']['history_mask']] for x in train])
    delta=np.stack([x['visual_target'][-1]-x['input']['history'][-1] for x in train])
    pd=np.stack([x['proprio_target'][-1]-x['input']['proprio'][-1] for x in train])
    normalization=dict(mean=history.mean(0).tolist(),std=np.maximum(history.std(0),.05).tolist(),
        delta_scale=np.maximum(delta.std(0),.05).tolist(),proprio_delta_scale=np.maximum(pd.std(0),.05).tolist(),
        fitted_split='adapt_train',train_parents=sorted({x['parent'] for x in train}),feature_partition='192visual/128language/8native_norm_state/1remaining')
    d.atomic(out/'normalization.json',normalization)
    def tensors(rows):return {k:torch.from_numpy(v) for k,v in stack([r['input'] for r in rows]).items()}
    tx=tensors(train);ty=torch.from_numpy(np.stack([x['visual_target'] for x in train]));tp=torch.from_numpy(np.stack([x['proprio_target'] for x in train]))
    vx=tensors(val) if val else None;vy=torch.from_numpy(np.stack([x['visual_target'] for x in val])) if val else None
    gx=tensors(gt);gy=torch.tensor([x['target'] for x in gt],dtype=torch.float32)
    vgx=tensors(gv) if gv else None;vgy=torch.tensor([x['target'] for x in gv],dtype=torch.float32) if gv else None
    ps=torch.as_tensor(normalization['proprio_delta_scale'],dtype=torch.float32)
    parent_indices={p:np.array([i for i,x in enumerate(train) if x['parent']==p]) for p in sorted({x['parent'] for x in train})}
    def step_boundary(component,step,loss):
        nonlocal updates
        d.authorize();updates+=1
        if updates>32000:raise RuntimeError('Small update cap')
        if (step+1)%250==0:d.atomic(d.R/'FIT_PROGRESS.json',dict(component=component,step=step+1,updates=updates,loss=float(loss.detach()),utc=d.utc()))
    def slice_batch(batch,idx):return {k:v[idx] for k,v in batch.items()}
    def validation_world(model):
        if vx is None:return None
        total=0.;n=0
        with torch.no_grad():
            for start_i in range(0,len(val),64):
                idx=slice(start_i,start_i+64);pred,_=model(slice_batch(vx,idx));target=vy[idx]
                total+=float((((pred-target)/model.delta_scale)**2).sum());n+=target.numel()
        return total/n
    for world_seed,gate_seed in zip([241,242],[341,342]):
        torch.manual_seed(world_seed);world=WorldModel(normalization)
        optimizer=torch.optim.AdamW(world.parameters(),lr=spec['fit_lr'],weight_decay=spec['fit_weight_decay'])
        rng=np.random.default_rng(world_seed);parent_names=list(parent_indices)
        for step in range(4000):
            idx=np.array([rng.choice(parent_indices[parent_names[int(p)]]) for p in rng.integers(0,len(parent_names),size=16)])
            prediction,proprio=world(slice_batch(tx,idx));loss=(((prediction-ty[idx])/world.delta_scale)**2).mean()+(((proprio-tp[idx])/ps)**2).mean()
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite D2 loss')
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(world.parameters(),1.);optimizer.step();step_boundary('D%d'%world_seed,step,loss)
        world.eval().requires_grad_(False);torch.save(world.state_dict(),out/('D%d.pt'%world_seed))
        reports.append(dict(component='D',seed=world_seed,updates=4000,parameters=sum(p.numel() for p in world.parameters()),validation_MSE=validation_world(world)))
        with torch.no_grad():
            future,_=world(dict(gx,actions=gx['actions'][:,:2]))
            vfuture=world(dict(vgx,actions=vgx['actions'][:,:2]))[0] if vgx is not None else None
        torch.manual_seed(gate_seed);gate=BenefitModel(normalization)
        optimizer=torch.optim.AdamW(gate.parameters(),lr=spec['fit_lr'],weight_decay=spec['fit_weight_decay']);rng=np.random.default_rng(gate_seed)
        for step in range(4000):
            idx=rng.integers(0,len(gt),size=16);prediction=gate(slice_batch(gx,idx),future[idx]);loss=((prediction-gy[idx])**2).mean()
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite G0 loss')
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(gate.parameters(),1.);optimizer.step();step_boundary('G0%d'%gate_seed,step,loss)
        gate.eval().requires_grad_(False);torch.save(gate.state_dict(),out/('G0%d.pt'%gate_seed))
        with torch.no_grad():vmse=float(((gate(vgx,vfuture)-vgy)**2).mean()) if vgx is not None else None
        reports.append(dict(component='G0',seed=gate_seed,updates=4000,parameters=sum(p.numel() for p in gate.parameters()),validation_MSE=vmse))

    with np.load(d.R/'Q_DEVELOPMENT.npz',allow_pickle=False) as z:q={k:z[k].copy() for k in z.files}
    mask=q['train'];feature=q['feature'][mask].astype(np.float64)
    mean=feature.mean(0);std=np.maximum(feature.std(0),.05)
    mid,scale=action_norm(d.load(cfg['norm_stats'])['norm_stats'])
    def design(m):
        f=(q['feature'][m]-mean)/std;a=(q['actions'][m]-mid)/scale;ref=(q['reference'][m]-mid)/scale
        return torch.from_numpy(np.concatenate((np.repeat(f[:,None,:],5,axis=1),a.reshape(-1,5,35),np.repeat(ref[:,None,:].reshape(-1,1,35),5,axis=1)),axis=-1).astype(np.float32))
    x=design(mask);y=torch.from_numpy(q['outcomes'][mask]);cw=torch.from_numpy(q['cw'][mask].astype(np.float32));gw=torch.from_numpy(q['gw'][mask].astype(np.float32));pw=torch.from_numpy(q['pw'][mask])
    vqx=design(~mask);vqy=torch.from_numpy(q['outcomes'][~mask])
    saved=dict(feature_mean=mean,feature_std=std,action_mid=mid,action_scale=scale,members=np.asarray(4))
    def average(value,weight):return ((value*weight).sum(-1)/weight.sum(-1).clamp_min(1)).mean()
    def loss_parts(logits,target,cw,gw,pw):
        probability=logits.sigmoid();bce=average(torch.nn.functional.binary_cross_entropy_with_logits(logits,target,reduction='none'),cw)
        gain=average(((probability-probability[:,:1])-(target-target[:,:1]))**2,gw)
        pair=average(torch.stack([(probability[:,a]-probability[:,b])-(target[:,a]-target[:,b]) for a,b in [(1,2),(3,4)]],-1)**2,pw)
        return bce+gain+.5*pair
    for member,seed in enumerate([9301,9302,9303,9304]):
        torch.manual_seed(seed);model=torch.nn.Sequential(torch.nn.Linear(399,128),torch.nn.ReLU(),torch.nn.Linear(128,64),torch.nn.ReLU(),torch.nn.Linear(64,1))
        optimizer=torch.optim.AdamW(model.parameters(),lr=spec['fit_lr'],weight_decay=spec['fit_weight_decay']);rng=np.random.default_rng(seed+1)
        for step in range(4000):
            idx=rng.integers(0,len(x),size=16);logits=model(x[idx]).squeeze(-1);loss=loss_parts(logits,y[idx],cw[idx],gw[idx],pw[idx])
            if not torch.isfinite(loss):raise RuntimeError('Nonfinite native L11 loss')
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step();step_boundary('Q%d'%seed,step,loss)
        model.eval().requires_grad_(False)
        for layer,index in enumerate([0,2,4]):
            saved['m%d_w%d'%(member,layer)]=model[index].weight.detach().numpy();saved['m%d_b%d'%(member,layer)]=model[index].bias.detach().numpy()
        with torch.no_grad():vmse=float(((model(vqx).squeeze(-1).sigmoid()-vqy)**2).mean())
        reports.append(dict(component='Q_L11',seed=seed,updates=4000,parameters=sum(p.numel() for p in model.parameters()),validation_Brier_MSE=vmse))
    if updates!=32000:raise RuntimeError('Fixed fit updates incomplete')
    np.savez_compressed(str(out/'native_head.npz'),**saved)
    refs=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(out.iterdir()) if p.is_file()]
    ready=dict(utc=d.utc(),status='complete',optimizer_updates=updates,model_path=str(out/'native_head.npz'),
        model_sha256=hashlib.sha256((out/'native_head.npz').read_bytes()).hexdigest(),members=reports,
        selection='fixed final4000/member; validation descriptive only',test_used=False,seconds=time.monotonic()-start,models=refs)
    d.atomic(d.R/'FIT_SUMMARY.json',ready)
    d.exclusive(d.R/'METHOD_FROZEN.json',dict(utc=d.utc(),method='Full-Post/Full-Velocity native-LIBERO',
        science=spec,Q_loss=batch['Q_loss'],models=refs,data_status=str(d.R/'DATA_STATUS.json'),
        code={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in d.W.glob('*.py')},
        source_plan_sha256=hashlib.sha256((d.R/'SOURCE_PLAN.json').read_bytes()).hexdigest(),
        test_started=False,D_horizon_adaptation_disclosed=True,G0_single_pair_label_noise_disclosed=True,
        Q_training_cut=20,deployment_legal_cut='native age2',test_model_selection=False))
    d.exclusive(d.R/'MODEL_READY.json',ready);d.event('fit_complete',result=str(d.R/'FIT_SUMMARY.json'))

if __name__=='__main__':
    try:main()
    except BaseException as e:
        import traceback
        d.atomic(d.R/'PIPELINE_FAILED.json',dict(phase='fit',error=repr(e),traceback=traceback.format_exc(),utc=d.utc()));raise
