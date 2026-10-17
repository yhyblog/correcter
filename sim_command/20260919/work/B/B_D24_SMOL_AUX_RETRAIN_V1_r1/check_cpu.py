import ast
import json
import sys
import tempfile
from pathlib import Path
import numpy as np
import torch

C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R=C/'results/B/B_D24_SMOL_AUX_RETRAIN_V1'
sys.path.insert(0,str(R/'code'))
import paths,train_head
from qio import read,new_json,utc
from corrector.critic import TenStepCritic,STATE_KEYS
from ac_tmil.future_aware.models import WorldModel,BenefitModel

torch.set_num_threads(2);checks=[]
for p in (R/'code').glob('*.py'):ast.parse(p.read_text())
with tempfile.TemporaryDirectory(prefix='B_smol_aux_synthetic_') as temporary:
    fake=Path(temporary);d=fake/'dataset';d.mkdir()
    np.save(d/'states.npy',np.repeat(np.arange(8,dtype=np.float16)[:,None],4096,axis=1))
    np.save(d/'proprio.npy',np.repeat(np.arange(8,dtype=np.float32)[:,None],4,axis=1))
    np.save(d/'actions.npy',np.vstack([np.repeat(np.arange(7,dtype=np.float32)[:,None],4,axis=1),np.zeros((1,4),dtype=np.float32)]))
    np.save(d/'languages.npy',np.zeros((1,2048),np.float32));np.save(d/'train_windows.npy',np.asarray([[0,4],[0,6]],np.int64))
    (d/'TRAJECTORIES.json').write_text(json.dumps([dict(offset=0,length=8)]))
    original=train_head.ROOT;train_head.ROOT=fake
    try:batch=train_head.Windows('train').take([0,1],device='cpu')
    finally:train_head.ROOT=original
    assert batch['history'][0,:,0].tolist()==[0,1,2,3,4]
    assert batch['past_actions'][0,:,0].tolist()==[0,1,2,3]
    assert batch['targets'][0,:,0].tolist()==[5,6,7,7,7]
    assert batch['future_mask'].tolist()==[[True,True,True,False,False],[True,False,False,False,False]]
    assert batch['actions'][1,:,0].tolist()==[6,0,0,0,0]
    checks.append('mature causal windows, future5 temporal alignment and terminal masks')
    norm=dict(mean=np.zeros(4096).tolist(),std=np.ones(4096).tolist(),delta_scale=np.ones(4096).tolist())
    world=WorldModel(norm);gate=BenefitModel(norm)
    with torch.no_grad():
        future,prop=world(batch);gain=gate(batch,future)
    assert future.shape==(2,5,4096) and prop.shape==(2,5,4) and gain.shape==(2,) and torch.isfinite(gain).all()
    checks.append('existing D and G0 accept collected observation/proprio/action tensor contract')

logits=torch.zeros((1,3),requires_grad=True);labels=torch.tensor([[0.,1.,0.]])
loss=train_head.q_loss(logits,labels,torch.ones((1,3)),torch.tensor([[0.,1.,1.]]),torch.ones(1))
assert abs(float(loss.detach())-(np.log(2)+1.))<1e-6
masked=train_head.q_loss(logits,labels,torch.ones((1,3)),torch.tensor([[0.,.5,0.]]),torch.zeros(1))
assert abs(float(masked.detach())-(np.log(2)+1.))<1e-6
loss.backward();assert torch.isfinite(logits.grad).all()
checks.append('three-candidate L11 has unchanged source means/gain/pair units and exact alias weight normalization')
prep=dict(norm_mean=torch.zeros(4096),norm_std=torch.ones(4096),residual_scale=torch.tensor([.15,.15,.15,.4]),
    visual_center=torch.zeros(8192),visual_basis=torch.zeros(8192,16),visual_scale=torch.ones(16),
    language_center=torch.zeros(2048),language_basis=torch.zeros(2048,8),language_scale=torch.ones(8))
q=TenStepCritic(prep);assert sum(p.numel() for p in q.parameters())==7058 and all(p.requires_grad for p in q.parameters())
checks.append('all7058 Q parameters initialized trainable from scratch')
manifest=read(R/'SOURCE_MANIFEST.json');sources=manifest['parents']
assert len(sources)==250 and sum(s['split']=='train' for s in sources)==200 and manifest['task_environment_seed_overlap']==0
assert len({(s['task'],s['reset_seed']) for s in sources})==250
for s in sources:assert s['cut']%10==5 and len(s['suffix_policy_seeds'])==2
checks.append('frozen250 parent split and old queue midpoint cuts, unique real initialization inputs')
new_json(R/'evidence/CPU_CHECKS.json',dict(status='PASS',at_utc=utc(),checks=checks,synthetic_only=True,
    model_loading_from_checkpoints=0,optimizer_updates=0,GPU_calls=0,rollouts=0))
print(json.dumps(dict(status='PASS',checks=checks)))
