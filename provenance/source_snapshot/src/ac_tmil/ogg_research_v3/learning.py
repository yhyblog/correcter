"""Observable ten-step relative critic with train-only fixed state projections."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from ac_tmil.ogg_research.critic_data import STATE_KEYS
from ac_tmil.ogg_research_v2.training import loss_parts
from ac_tmil.ogg_research_v2.evaluation import sealed
from ac_tmil.idea3.local_collection import seal
from .common import ROOT,REPO,BASE,METHODS,read,freeze,dump,save_arrays,file_sha256,seed_for
from .capacity import fit_pca
from .learning_protocol import LEARN


def observed_features(arrays,norm_mean,norm_std):
    h=((arrays['history'].float()-norm_mean)/norm_std.clamp_min(1e-6)).clamp(-8,8)
    mask=arrays['history_mask'][...,None]
    visual=torch.cat([h[:,-1],(h*mask).sum(1)/mask.sum(1).clamp_min(1)],-1)
    language=F.layer_norm(arrays['language'].float(),(2048,))
    other=torch.cat([(arrays['proprio']*arrays['proprio_mask'][...,None]).flatten(1),
        arrays['past_actions'].flatten(1),arrays['remaining'].reshape(-1,1)],-1).float()
    return visual,language,other


class TrainData:
    def __init__(self):
        sources=[(ROOT/'data/pilot/h10',ROOT/'config.json'),(ROOT/'data/train_extra/h10',LEARN/'config.json')]
        self.rows=[];self.planned=[];parts={k:[] for k in STATE_KEYS+['actions','outcomes']};self.input_hashes={}
        for path,protocol in sources:
            sealed(path,protocol);meta=json.loads((path/'rows.json').read_text())
            self.rows.extend(meta['rows']);self.planned.extend(meta['all_planned_sources'])
            with np.load(path/'arrays.npz') as z:
                for k in parts:parts[k].append(z[k].copy())
            self.input_hashes[str(path/'complete.json')]=file_sha256(path/'complete.json')
        assert len(self.planned)==len({r['case_id'] for r in self.planned})==100
        self.arrays={k:torch.as_tensor(np.concatenate(v)) for k,v in parts.items()}
        assert self.arrays['actions'].shape[1:]==(9,10,4)
        assert self.arrays['outcomes'].shape[1:]==(9,8)
        self.lookup={r['case_id']:i for i,r in enumerate(self.rows)}
        norm=json.loads((BASE/'models/spatial_pair_241/normalization.json').read_text())
        self.norm_mean=torch.tensor(norm['mean']);self.norm_std=torch.tensor(norm['std']).clamp_min(1e-6)
        self.visual,self.language,self.other=observed_features(self.arrays,self.norm_mean,self.norm_std)
    def indices(self,ids):return np.asarray([self.lookup[x] for x in ids if x in self.lookup],dtype=int)


def fit_preprocessing(data,indices,cfg):
    assert len(indices)==len(np.unique(indices)) and len(indices)>16
    result=dict(norm_mean=data.norm_mean,norm_std=data.norm_std,residual_scale=torch.tensor(cfg['residual_scale']))
    for name,values,width in [('visual',data.visual,cfg['visual_pca_dimension']),('language',data.language,cfg['language_pca_dimension'])]:
        for suffix,value in zip(['center','basis','scale'],fit_pca(values,indices,width)):
            result[name+'_'+suffix]=value
    return result


class TenStepCritic(nn.Module):
    def __init__(self,preprocessing):
        super().__init__()
        for key,value in preprocessing.items():self.register_buffer(key,value.detach().clone())
        width=self.visual_basis.shape[1]+self.language_basis.shape[1]+37
        self.state=nn.Sequential(nn.Linear(width,32),nn.SiLU(),nn.Linear(32,16),nn.SiLU())
        self.action=nn.Sequential(nn.Linear(40,16),nn.SiLU(),nn.Linear(16,16),nn.SiLU())
        self.residual=nn.Sequential(nn.Linear(40,16),nn.SiLU(),nn.Linear(16,16),nn.SiLU())
        self.head=nn.Sequential(nn.Linear(32,32),nn.SiLU(),nn.Linear(32,1))
        self.advantage=nn.Sequential(nn.Linear(48,32),nn.SiLU(),nn.Linear(32,1))

    def features(self,arrays):
        visual,language,other=observed_features(arrays,self.norm_mean,self.norm_std)
        return self.project(visual,language,other)

    def project(self,visual,language,other):
        parts=[]
        for name,values in [('visual',visual),('language',language)]:
            parts.append((((values-getattr(self,name+'_center'))@getattr(self,name+'_basis'))/getattr(self,name+'_scale')).clamp(-8,8))
        return torch.cat([*parts,other],-1)

    def forward(self,features,actions):
        n,k,h,d=actions.shape
        if (h,d)!=(10,4):raise ValueError('This critic requires exactly ten four-dimensional commands')
        base=actions[:,0].repeat_interleave(k,0)
        shared=torch.cat([self.state(features).repeat_interleave(k,0),self.action(base.flatten(1))],-1)
        delta=((actions.flatten(0,1)-base)/self.residual_scale).flatten(1)
        actual=self.advantage(torch.cat([shared,self.residual(delta)],-1))
        zero=self.advantage(torch.cat([shared,self.residual(torch.zeros_like(delta))],-1))
        return (self.head(shared)+actual-zero).reshape(n,k)


def from_state(state):
    keys=['norm_mean','norm_std','residual_scale']+[f'{name}_{suffix}' for name in ['visual','language'] for suffix in ['center','basis','scale']]
    model=TenStepCritic({k:state[k] for k in keys});model.load_state_dict(state)
    return model


@torch.no_grad()
def canonical_features(model,arrays):
    return torch.cat([model.features({k:arrays[k][i:i+1] for k in STATE_KEYS})
        for i in range(len(arrays['history']))])


def verify_implementation():
    original=read(LEARN/'training_registration.json');expected=dict(original['code_hashes'])
    amendment=LEARN/'training_implementation_amendment.json'
    if amendment.exists():
        change=read(amendment)
        assert change['original_registration_sha256']==file_sha256(LEARN/'training_registration.json')
        for name,sha in change['original_code_hashes'].items():assert expected[name]==sha
        expected.update(change['replacement_code_hashes'])
    inference=LEARN/'inference_implementation_amendment.json'
    if inference.exists():
        change=read(inference)
        assert change['ranking_sha256']==file_sha256(LEARN/'ranking.json')
        for name,sha in change['original_code_hashes'].items():assert expected[name]==sha
        expected.update(change['replacement_code_hashes'])
    for name,sha in expected.items():assert file_sha256(REPO/name)==sha,name
    return expected


@torch.no_grad()
def predict(model,data,indices):
    # Batch only a single source in inference, exactly as in deployment.
    result=[]
    for i in indices:
        obs={k:data.arrays[k][i:i+1] for k in STATE_KEYS}
        result.append(model(model.features(obs),data.arrays['actions'][i:i+1]).sigmoid())
    return torch.cat(result).numpy()


def fit_job(phase,member):
    cfg=read(LEARN/'config.json');tc=cfg['training'];data=TrainData()
    folder=LEARN/'models'/phase/f'member_{member}'
    if (folder/'complete.json').exists():sealed(folder,LEARN/'config.json');return
    torch.set_num_threads(tc['threads_per_worker']);begin=time.perf_counter()
    train_ids=cfg['inner_train'] if phase=='inner' else [c['case_id'] for c in data.planned]
    train=data.indices(train_ids);held=data.indices(cfg['inner_validation']) if phase=='inner' else np.arange(len(data.rows))
    if phase=='inner':assert not set(train_ids)&set(cfg['inner_validation'])
    steps=tc['steps'] if phase=='inner' else read(LEARN/'stopping.json')['selected_step']
    checkpoints=tc['checkpoints'] if phase=='inner' else [steps]
    torch.manual_seed(seed_for('v3_h10_parameters',member))
    model=TenStepCritic(fit_preprocessing(data,train,tc))
    parameters=sum(p.numel() for p in model.parameters());assert parameters==7058
    cached=canonical_features(model,data.arrays)
    # Same single-source floating-point path as deployment, using only fitted
    # training statistics. A batched projection can differ in near-null PCs.
    with torch.no_grad():
        for i in held[:3]:
            direct=model.features({k:data.arrays[k][i:i+1] for k in STATE_KEYS})
            np.testing.assert_array_equal(cached[i:i+1].numpy(),direct.numpy())
    informative=(data.arrays['outcomes'].float().mean(-1)-data.arrays['outcomes'][:,:1].float().mean(-1)).ne(0).any(1).numpy()
    weights=np.where(informative[train],tc['informative_source_weight'],1)
    pool=np.repeat(train,weights);rng=np.random.default_rng(seed_for('v3_h10_batches',phase,member))
    opt=torch.optim.AdamW(model.parameters(),lr=tc['lr'],weight_decay=tc['weight_decay'])
    history=[];batches=[];predictions=[]
    for step in range(1,steps+1):
        chosen=pool[rng.integers(0,len(pool),tc['batch_groups'])];batches.append(chosen)
        opt.zero_grad(set_to_none=True)
        logits=model(cached[chosen],data.arrays['actions'][chosen])
        absolute,relative,_,_=loss_parts(logits,data.arrays['outcomes'][chosen])
        loss=absolute+tc['relative_weight']*relative
        if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
        loss.backward();gradient=torch.nn.utils.clip_grad_norm_(model.parameters(),tc['clip'])
        if not torch.isfinite(gradient):raise ValueError('Nonfinite training gradient')
        opt.step()
        if step in checkpoints:
            model.eval();predictions.append(predict(model,data,held));model.train()
            history.append(dict(step=step,nll=float(absolute.detach()),relative_mse=float(relative.detach())))
    opt.zero_grad(set_to_none=True);model.eval().requires_grad_(False)
    with torch.no_grad():
        actions=data.arrays['actions'][held[:2]];identical=actions[:,:1].expand_as(actions).clone()
        anchored=model(cached[held[:2]],identical)
        assert float((anchored-anchored[:,:1]).abs().max())<2e-6
    folder.mkdir(parents=True,exist_ok=True)
    torch.save({k:v.detach().clone() for k,v in model.state_dict().items()},folder/'selected.pt')
    save_arrays(folder/'predictions.npz',probabilities=np.stack(predictions),indices=held,
        minibatches=np.asarray(batches),train_indices=train,source_weights=weights)
    dump(folder/'details.json',dict(phase=phase,member=member,steps=steps,checkpoints=checkpoints,
        parameters=parameters,train_sources=[data.rows[i]['case_id'] for i in train],
        held_sources=[data.rows[i]['case_id'] for i in held],preprocessing_fit_sources=[data.rows[i]['case_id'] for i in train],
        informative_train_sources=int(informative[train].sum()),history=history,
        identical_action_anchor_passed=True,seconds=time.perf_counter()-begin,input_hashes=data.input_hashes))
    seal(folder,['selected.pt','predictions.npz','details.json'],config_sha256=file_sha256(LEARN/'config.json'))
    print(json.dumps(dict(event='h10_fit_complete',phase=phase,member=member,steps=steps,seconds=time.perf_counter()-begin)),flush=True)


def run_phase(phase):
    cfg=read(LEARN/'config.json');logs=LEARN/'training_logs'/phase;logs.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    python='/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python'
    children=[];streams=[]
    try:
        for member in cfg['training']['members']:
            stream=(logs/f'member_{member}_{time.time_ns()}.log').open('x');streams.append(stream)
            children.append(subprocess.Popen([python,'-u','-m',__spec__.name,'--phase',phase,'--member',str(member)],
                cwd=REPO,env=env,stdout=stream,stderr=subprocess.STDOUT))
        while any(p.poll() is None for p in children):
            if any(p.poll() not in (None,0) for p in children):raise RuntimeError(f'{phase} training job failed')
            time.sleep(.5)
        assert all(p.returncode==0 for p in children)
    finally:
        for p in children:
            if p.poll() is None:p.terminate()
        for p in children:p.wait()
        for f in streams:f.close()


def run_all():
    cfg=read(LEARN/'config.json');data=TrainData()
    for split in ['calibration','validation']:
        assert not any((ROOT/'sources/single'/c['case_id']).exists() for c in read(ROOT/'config.json')['cases'] if c['split']==split)
    source_files=[Path(__file__),Path(__file__).with_name('learning_data.py'),Path(__file__).with_name('learning_protocol.py'),Path(__file__).with_name('learning_collection.py'),Path(__file__).with_name('learning_evaluation.py')]
    if not (LEARN/'training_registration.json').exists():
        freeze(LEARN/'training_registration.json',dict(unix=time.time(),input_hashes=data.input_hashes,
            code_hashes={str(p.relative_to(REPO)):file_sha256(p) for p in source_files},
            calibration_validation_absent=True,planned_sources=100,reached_sources=len(data.rows)))
    verify_implementation()
    run_phase('inner')
    if not (LEARN/'stopping.json').exists():
        probabilities=[];indices=None
        for member in cfg['training']['members']:
            folder=LEARN/'models/inner'/f'member_{member}';sealed(folder,LEARN/'config.json')
            with np.load(folder/'predictions.npz') as z:
                if indices is not None:np.testing.assert_array_equal(indices,z['indices'])
                indices=z['indices'].copy();probabilities.append(z['probabilities'].copy())
        mean=np.mean(probabilities,axis=0).astype(float)
        true=data.arrays['outcomes'][indices].double().mean(-1).numpy()
        actual=true[:,1:]-true[:,:1]
        error=((mean[:,:,1:]-mean[:,:,:1]-actual[None])**2).mean((1,2))
        selected=int(error.argmin())
        freeze(LEARN/'stopping.json',dict(selected_step=cfg['training']['checkpoints'][selected],
            inner_ensemble_gain_mse=error.tolist(),zero_gain_mse=float((actual**2).mean()),
            inner_held_sources=[data.rows[i]['case_id'] for i in indices],
            learned_on_inner_train_only=True,selection='relative gain MSE, earliest tie'))
    run_phase('refit')
    hashes={str(m):file_sha256(LEARN/'models/refit'/f'member_{m}/selected.pt') for m in cfg['training']['members']}
    if not (LEARN/'ranking.json').exists():
        freeze(LEARN/'ranking.json',dict(status='frozen',created_unix=time.time(),config_sha256=file_sha256(LEARN/'config.json'),
            model_hashes=hashes,stopping_sha256=file_sha256(LEARN/'stopping.json'),
            training_registration_sha256=file_sha256(LEARN/'training_registration.json'),horizon=10,
            implementation_amendment_sha256=file_sha256(LEARN/'training_implementation_amendment.json') if (LEARN/'training_implementation_amendment.json').exists() else None,
            planned_train_sources=100,reached_train_sources=len(data.rows),parameters_per_member=7058,
            calibration_outcomes_used=False,validation_outcomes_used=False,ranking=cfg['ranking']))
    print(json.dumps(dict(status='ranking_frozen',models=hashes,selected_step=read(LEARN/'stopping.json')['selected_step'])),flush=True)


class FrozenSelector:
    def __init__(self):
        self.cfg=read(LEARN/'config.json');self.ranking=read(LEARN/'ranking.json');self.models=[]
        self.policy=read(LEARN/'frozen_policy.json') if (LEARN/'frozen_policy.json').exists() else None
        if self.policy is not None:assert self.policy['ranking_sha256']==file_sha256(LEARN/'ranking.json')
        for member,sha in self.ranking['model_hashes'].items():
            folder=LEARN/'models/refit'/f'member_{member}';sealed(folder,LEARN/'config.json')
            path=folder/'selected.pt';assert file_sha256(path)==sha
            state=torch.load(path,map_location='cpu',weights_only=True)
            self.models.append(from_state(state).eval().requires_grad_(False))
        self.versions=[(p,p._version) for m in self.models for p in m.parameters()]

    @torch.no_grad()
    def score(self,observed,plans):
        # Near-null language PCs amplify differences in BLAS reductions.
        # Preserve the training's CPU execution path and restore the caller's
        # thread setting before any VLA or simulator work resumes.
        previous=torch.get_num_threads()
        try:
            torch.set_num_threads(self.cfg['training']['threads_per_worker'])
            return self._score(observed,plans)
        finally:torch.set_num_threads(previous)

    def _score(self,observed,plans):
        obs={k:torch.as_tensor(observed[k])[None] for k in STATE_KEYS}
        actions=torch.as_tensor(np.stack([plans[k][:10] for k in METHODS]))[None]
        if not torch.isfinite(actions).all() or float(actions.abs().max())>1.:raise ValueError('Invalid final commands')
        probabilities=np.stack([m(m.features(obs),actions).sigmoid().numpy()[0] for m in self.models]).astype(float)
        gain=probabilities-probabilities[:,:1];mean=gain.mean(0);std=gain.std(0)
        winner=int(mean.argmax())
        result=dict(winner=METHODS[winner],winner_index=winner,member_probabilities=probabilities.tolist(),
            mean_gain=mean.tolist(),std_gain=std.tolist(),predicted_winner_gain=float(mean[winner]),
            winner_gain_std=float(std[winner]),ranking_sha256=file_sha256(LEARN/'ranking.json'),
            uses_hidden_simulator_state=False,horizon=10)
        if self.policy is not None:
            from .learning_evaluation import accept
            accepted=accept(result,self.policy['rule'])
            result.update(calibrated_accepted=accepted,calibrated_selected=result['winner'] if accepted else 'replan',
                frozen_policy_sha256=file_sha256(LEARN/'frozen_policy.json'))
        return result

    def verify(self):
        assert all(not p.requires_grad and p.grad is None and p._version==v for p,v in self.versions)


class FrozenController:
    """One correction at the first frozen G0 alarm; execute h10 then fixed10."""
    def __init__(self):
        self.selector=FrozenSelector()
        if self.selector.policy is None:raise ValueError('Calibration must be frozen before deployment')
        self.candidates=read(ROOT/'config.json')['candidates']

    def select(self,observed,specified_replan,direction_seed):
        from .candidates import construct
        base=np.asarray(specified_replan,dtype=np.float32)
        if base.shape!=(50,4) or not np.isfinite(base).all() or np.abs(base).max()>1:
            raise ValueError('Expected an already postprocessed 50x4 replan in [-1,1]')
        plans,_=construct(base,observed,direction_seed,10,self.candidates)
        details=self.selector.score(observed,plans)
        chosen=details['calibrated_selected']
        details.update(prefix_steps=10,continuation='clear_queue_then_fixed10_to_300',
            extra_VLA_calls=0,critic_forward_calls=4,extra_interventions_after_this=False)
        return plans[chosen],details


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-all',action='store_true');p.add_argument('--phase',choices=['inner','refit']);p.add_argument('--member',type=int);a=p.parse_args()
    run_all() if a.run_all else fit_job(a.phase,a.member)
