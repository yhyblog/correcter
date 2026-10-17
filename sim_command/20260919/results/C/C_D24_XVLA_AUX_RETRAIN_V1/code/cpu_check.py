"""One bounded CPU integration check; no rollout, checkpoint load or optimizer step."""
import ast, tempfile,json,sys
from pathlib import Path
import numpy as np
import torch
import paths
from paths import ROOT,CAMPAIGN
from qio import read,atomic_json,utc,sha
from projector import project_solo
from corrector.critic import TenStepCritic,STATE_KEYS,FrozenSelector
from corrector.guidance import FrozenObjective
from ac_tmil.future_aware.models import WorldModel,BenefitModel
from ac_tmil.future_aware.training import objective
from train_head import q_loss

def main():
    torch.set_num_threads(2);torch.manual_seed(20260922);rng=np.random.default_rng(20260922)
    for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text())
    manifest=read(ROOT/'SOURCE_MANIFEST.json');parents=manifest['parents'];cfg=read(ROOT/'config/CONFIG.json');method=read(ROOT/'METHOD_FROZEN.json')
    assert len(parents)==250 and len({p['env_seed'] for p in parents})==250
    assert sum(p['split']=='train' for p in parents)==200 and sum(p['split']=='development' for p in parents)==50
    assert all(p['cut']==[5,15,35,55][p['ordinal'] if p['split']=='train' else p['task_ascii_index']%4] for p in parents)
    assert cfg['H']==30 and cfg['K']==cfg['NFE']==10 and cfg['planned_prior_attempts']==7013
    assert cfg['D_seeds']+cfg['G0_seeds']+cfg['Q_seeds']==[2241,2242,2341,2342,29301,29302,29303,29304]
    assert cfg['stage_attempt_cap']==4000 and cfg['small_network_update_cap']==32000
    assert all(sha(cfg[k]['path'])==cfg[k]['sha256'] for k in ['source_manifest','test_sources','method_frozen'])
    matching=read(ROOT/'config/ENGINE_CONFIG.json')['matching'];raw=rng.uniform(-.8,.8,(30,4)).astype(np.float32)
    raw[0,0]=1.2;raw[1,1]=-1.1
    knots=rng.normal(size=(3,4));direction=np.stack([np.interp(np.arange(10),[0,4.5,9],knots[:,j]) for j in range(4)],1)
    plus,pm,_=project_solo(raw,direction,matching);minus,mm,_=project_solo(raw,-direction,matching);zero,_,_=project_solo(raw,np.zeros((10,4)),matching)
    assert np.array_equal(plus[10:],raw[10:]) and np.array_equal(minus[10:],raw[10:]) and np.array_equal(zero,raw)
    assert plus[0,0]==raw[0,0] and minus[1,1]==raw[1,1]
    np.testing.assert_allclose(plus[:10]-raw[:10],raw[:10]-minus[:10],atol=6e-8,rtol=1e-5)
    norm=dict(mean=np.zeros(4096),std=np.ones(4096),delta_scale=np.ones(4096))
    batch=dict(history=torch.randn(4,5,4096),history_mask=torch.ones(4,5,dtype=torch.bool),proprio=torch.randn(4,5,4),
        proprio_mask=torch.ones(4,5,dtype=torch.bool),past_actions=torch.rand(4,4,4)*2-1,language=torch.randn(4,2048),
        remaining=torch.ones(4),actions=torch.rand(4,5,4)*2-1,targets=torch.randn(4,5,4096),future_mask=torch.ones(4,5,dtype=torch.bool),
        target_proprio=torch.randn(4,5,4),target_proprio_mask=torch.ones(4,5,dtype=torch.bool))
    world=WorldModel(norm).eval();gate=BenefitModel(norm).eval()
    with torch.no_grad():
        future,prop=world(batch);benefit=gate(batch,future)
        assert future.shape==(4,5,4096) and prop.shape==(4,5,4) and benefit.shape==(4,)
        assert torch.isfinite(objective(world,batch,pair=True))
    preprocessing=dict(norm_mean=torch.zeros(4096),norm_std=torch.ones(4096),residual_scale=torch.tensor([.15,.15,.15,.4]),
        visual_center=torch.zeros(8192),visual_basis=torch.randn(8192,16)*.01,visual_scale=torch.ones(16),
        language_center=torch.zeros(2048),language_basis=torch.randn(2048,8)*.01,language_scale=torch.ones(8))
    q=TenStepCritic(preprocessing);assert sum(p.numel() for p in q.parameters())==7058 and all(p.requires_grad for p in q.parameters())
    logits=torch.tensor([[0.,.7,-.8],[1.,1.,1.]],requires_grad=True);labels=torch.tensor([[.5,1.,0.],[0.,0.,0.]])
    cw=torch.tensor([[1.,1.,1.],[1/3,1/3,1/3]]);gw=torch.tensor([[0.,1.,1.],[0.,0.,0.]]);pw=torch.tensor([1.,0.])
    loss=q_loss(logits,labels,cw,gw,pw);prob=logits.sigmoid()
    bce=(torch.nn.functional.binary_cross_entropy_with_logits(logits,labels,reduction='none')*cw).sum(1)/cw.sum(1)
    gain=(((prob-prob[:,:1])-(labels-labels[:,:1])).square()*gw).sum(1)/gw.sum(1).clamp_min(1)
    pair=((prob[:,1]-prob[:,2])-(labels[:,1]-labels[:,2])).square()*pw
    torch.testing.assert_close(loss,(bce+gain+.5*pair).mean());assert torch.isfinite(torch.autograd.grad(loss,logits)[0]).all()
    with tempfile.TemporaryDirectory(prefix='C_aux_Q_CPU_',dir='/tmp') as tmp:
        root=Path(tmp);hashes={}
        for i in range(4):
            p=root/'models/refit'/f'member_{i}'/'selected.pt';p.parent.mkdir(parents=True);torch.save(q.state_dict(),p);hashes[str(i)]=sha(p)
        (root/'ranking.json').write_text(json.dumps(dict(horizon=10,model_hashes=hashes)))
        selector=FrozenSelector(root);context={k:batch[k][0].numpy() for k in STATE_KEYS}
        anchor=np.pad(raw,((0,20),(0,0)),mode='edge').clip(-1,1).astype(np.float32)
        f=FrozenObjective(context,anchor,selector=selector);g,stats=f.gradient();assert g.shape==(10,4) and torch.isfinite(g).all();f.verify(check_hashes=False)
    row=dict(status='passed',utc=utc(),CPU_only=True,GPU_calls=0,optimizer_updates=0,scientific_rollouts=0,
        checks=['250 independent split parents and fixed cuts','small input seals and budgets','H30 own radius/tail/mask/zero/opposite direction',
            'real model D/G0 causal input dimensions and D pair objective','Q all7058 parameters and L11 units/masks','fixed4-member export and command-only gradient'],
        source_manifest_sha256=sha(ROOT/'SOURCE_MANIFEST.json'),method_frozen_sha256=sha(ROOT/'METHOD_FROZEN.json'),
        D_parameters=sum(p.numel() for p in world.parameters()),G0_parameters=sum(p.numel() for p in gate.parameters()),Q_parameters=7058,
        native_model_loading_validation='first planned collection only',native_environment='mw-xvla-lr044, private writable XDG, same Mesa launcher')
    atomic_json(ROOT/'CPU_CHECK.json',row);print(json.dumps(row))

if __name__=='__main__':main()
