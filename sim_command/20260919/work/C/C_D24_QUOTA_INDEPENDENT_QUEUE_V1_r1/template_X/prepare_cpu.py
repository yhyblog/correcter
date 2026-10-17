"""Paired scratch initializations and frozen train-only input projection."""
import hashlib
import numpy as np
import torch
import paths
from paths import ROOT,HEADS
from qio import read,new_json,utc,ref,sha
from corrector.critic import TenStepCritic,STATE_KEYS

def paired_seed(fit,member,kind):
    return int.from_bytes(hashlib.sha256(f'corrector_fullQ_paired_v1|{fit}|{member}|{kind}'.encode()).digest()[:8],'big')%(2**63)

def main():
    torch.set_num_threads(2)
    cfg=read(ROOT/'config/TRAIN.json');out=ROOT/'inputs';out.mkdir(exist_ok=False)
    parents=torch.load(cfg['train_parents'],map_location='cpu',weights_only=True)
    prep=torch.load(cfg['preprocessing'],map_location='cpu',weights_only=True)
    fields=['norm_mean','norm_std','residual_scale']+[f'{n}_{s}' for n in ['visual','language'] for s in ['center','basis','scale']]
    assert set(prep)==set(fields)
    assert parents['actions'].shape==(191,3,10,4) and parents['labels'].shape==(191,3)
    assert torch.isfinite(parents['actions']).all() and parents['actions'].abs().max()<=1
    assert torch.equal(parents['labels'],parents['outcomes'].double().mean(-1))
    eligible=torch.where(parents['candidate_weights'][:,0]>0)[0].numpy();assert len(eligible)==191
    model=TenStepCritic(prep)
    with torch.no_grad():
        features=torch.cat([model.features({k:parents[k][i:i+1] for k in STATE_KEYS}) for i in range(191)])
    assert features.shape==(191,61) and torch.isfinite(features).all()
    arrays={k:parents[k] for k in ['actions','labels','candidate_weights','gain_weights','pair_weight']}
    arrays['features']=features
    with (out/'TRAIN.pt').open('xb') as f:torch.save(arrays,f)
    streams=[]
    for member in cfg['members']:
        seed=cfg['fit_seed'];torch.manual_seed(paired_seed(seed,member,'initialization'))
        fresh=TenStepCritic(prep).requires_grad_(True)
        assert sum(p.numel() for p in fresh.parameters())==7058 and all(p.requires_grad for p in fresh.parameters())
        directory=out/f's{seed}_m{member}';directory.mkdir()
        with (directory/'initial.pt').open('xb') as f:torch.save(fresh.state_dict(),f)
        rng=np.random.default_rng(paired_seed(seed,member,'bootstrap'));pool=[]
        for task in sorted(set(parents['tasks'])):
            ids=[int(i) for i in eligible if parents['tasks'][i]==task]
            if ids:pool.extend(rng.choice(ids,len(ids),replace=True).tolist())
        rng=np.random.default_rng(paired_seed(seed,member,'minibatches'))
        batches=np.asarray(pool,dtype=np.int64)[rng.integers(0,len(pool),(4000,32))]
        with (directory/'minibatches.npy').open('xb') as f:np.save(f,batches,allow_pickle=False)
        row=dict(fit_seed=seed,member=member,bootstrap=pool,initialization=ref(directory/'initial.pt'),
            minibatches=ref(directory/'minibatches.npy'),paired_key_excludes_loss=True,
            seeds={kind:paired_seed(seed,member,kind) for kind in ['initialization','bootstrap','minibatches']})
        new_json(directory/'INPUT_READY.json',row);streams.append(row)
    # Exercise all authorized objectives and their action/model gradients without optimizer updates.
    from train_fit import loss_parts
    sample={k:v[:32] for k,v in arrays.items()};logits=fresh(sample['features'],sample['actions'])
    checks={}
    for loss in cfg['losses']:
        fresh.zero_grad(set_to_none=True);parts=loss_parts(logits,sample,loss)
        parts['loss'].backward(retain_graph=True)
        assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in fresh.parameters())
        checks[loss]={k:float(v.detach()) for k,v in parts.items()}
    new_json(ROOT/'CPU_CHECK.json',dict(status='passed',utc=utc(),trainable_parameters=7058,
        fixed_features=[191,61],frozen_preprocessing_only=True,old_network_loaded=False,
        train_only_data=ref(HEADS/'DATA_SUMMARY.json'),preprocessing=ref(cfg['preprocessing']),
        source_masks_retained=True,paired_streams=streams,objectives_checked=checks,
        preparation_optimizer_updates=0,collection=0,test_model_selection=0))
    print('CPU_CHECK passed:191 parents,16 fresh complete-Q fits,paired streams,no optimizer updates')

if __name__=='__main__':main()
