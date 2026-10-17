"""Old standalone numerical rules on a resident policy; no old release/ledger entry."""
from pathlib import Path
import hashlib
import json
import time
import numpy as np
import torch
from paths import WORKSPACE
from qio import new_json,sha
from corrector.actions import ActionTransform
from corrector.critic import FrozenSelector
from corrector.guidance import FrozenObjective,FlowHook
from experiments.standalone_ablation_20260918.candidates import project_solo
from feature_path import canonical_decode,spatial_tokens,cpu_batch

class Engine:
    def __init__(self,state,config,out):
        self.state=state;self.cfg=config;self.out=out;self.namespace=config['seed_namespace']
        self.device=state['device'];self.model=state['model'];self.policy=state['policy'];self.features=state['features']
        self.transform=ActionTransform.from_checkpoint(state['cfg']['checkpoint'],device=self.device)
        self.selector=FrozenSelector(config['critic_assets'])
        if self.selector.ranking['model_hashes']!=config['selected_model']['member_hashes']:raise ValueError('not A4000')
        self.hook=FlowHook(self.model,self.transform,dict(config['guidance'],mode='velocity'))
        self.worlds={};self.gates={};identities={}
        from ac_tmil.future_aware.models import WorldModel,BenefitModel
        base=WORKSPACE/'ACT-RECAP/outputs/act_recap_future_aware_20260914'
        for w,g in ((241,341),(242,342)):
            folder=base/'models'/('spatial_pair_'+str(w));norm=json.loads((folder/'normalization.json').read_text())
            meta=json.loads((folder/'complete.json').read_text());p=Path(meta['selected']['path'])
            if sha(p)!=meta['checkpoint_sha256']:raise ValueError('D5 checkpoint identity')
            model=WorldModel(norm).to(self.device);model.load_state_dict(torch.load(p,map_location=self.device,weights_only=True),strict=True)
            self.worlds[w]=model.eval().requires_grad_(False)
            p=base/'critics'/('gate_'+str(g))/'selected.pt'
            model=BenefitModel(norm).to(self.device);model.load_state_dict(torch.load(p,map_location=self.device,weights_only=True),strict=True)
            self.gates[w]=model.eval().requires_grad_(False)
            identities[str(w)]=dict(world=meta['checkpoint_sha256'],gate=sha(p))
        self.versions=[(p,p._version) for m in [self.policy,*self.worlds.values(),*self.gates.values()]
            for p in list(m.parameters())+list(m.buffers())]
        self.counts=dict(sampling=0,flow=0,contexts=0,D_forward=0,G0_forward=0,interventions=0,action_gradients=0,Q_ensemble_forward=0)
        new_json(out/'AUXILIARY_IDENTITY.json',dict(A4000=config['selected_model'],DG0=identities,
            guidance=config['guidance'],matching=config['matching'],solo_rule=config['solo_rule'],optimizer_updates=0))

    def set_episode(self,runtime,instruction,out):
        self.runtime=runtime;self.instruction=instruction;self.features._instruction=instruction;self.episode_out=out

    def language(self):return self.features.encode_instruction(self.instruction)

    def propose(self,seed,objective=None):
        begin=time.monotonic();self.hook.begin(objective)
        self.counts['sampling']+=1
        try:
            with torch.random.fork_rng(devices=[torch.device(self.device).index or 0]),torch.no_grad():
                torch.manual_seed(seed);torch.cuda.manual_seed(seed)
                self.policy.reset()
                batch=self.features._policy_batch(self.runtime.observation,self.instruction)
                images,masks=self.policy._preprocess_images(batch)
                raw=self.model.sample_actions(images,masks,batch['observation.language.tokens'],
                    batch['observation.language.attention_mask'],num_steps=10)
                actions=self.state['post'](raw[:,:,:4].reshape(-1,4)).reshape(50,4).float().cpu().numpy()
            times=list(self.hook.times);updates=list(self.hook.logs);noise=self.hook.last_noise_sha
            self.counts['flow']+=len(times)
            if len(times)!=10 or not np.allclose(times,np.arange(10,0,-1)/10,atol=1e-6):raise ValueError('flow schedule changed')
            if actions.dtype!=np.float32 or actions.shape!=(50,4) or not np.isfinite(actions).all():raise ValueError('invalid raw50')
            return actions,dict(policy_calls=1,seconds=time.monotonic()-begin,noise_sha256=noise,times=times,updates=updates)
        finally:self.hook.begin(None)

    @torch.no_grad()
    def context(self,frames,props,past,language,step):
        self.counts['contexts']+=1
        raw=self.features.encode_visual_batch([dict(pixels=f,agent_pos=p) for f,p in zip(frames,props)],batch_size=1)
        raw=torch.as_tensor(raw,device=self.device).float()
        spatial=torch.cat([spatial_tokens(canonical_decode(row[None]),self.state['projection']).flatten(1) for row in raw],dim=0)
        spatial=spatial.half().float().cpu().numpy()
        return cpu_batch(spatial,props,past,language,step,device=self.device)

    @torch.no_grad()
    def monitor(self,observed,next_five):
        batch=dict(observed,actions=torch.as_tensor(next_five,device=self.device)[None]);benefits={}
        for w,world in self.worlds.items():
            self.counts['D_forward']+=1;future,_=world(batch)
            self.counts['G0_forward']+=1;benefits[str(w)]=float(self.gates[w](batch,future))
        if not np.isfinite(list(benefits.values())).all():raise ValueError('nonfinite G0')
        return dict(gate=float(np.mean(list(benefits.values()))),member_benefits=benefits,trigger_metric='frozen G0 mean benefit; no D-error trigger')

    def intervene(self,method,observed,seed,step):
        begin=time.monotonic();raw,base_stats=self.propose(seed);self.counts['interventions']+=1
        if method=='R':return raw,dict(base_stats,method='R',Q_acceptance_gate=False)
        base=np.clip(raw,-1,1).astype(np.float32)
        unbatched={k:v[0].detach().cpu().numpy() for k,v in observed.items()}
        objective=FrozenObjective(unbatched,base,selector=self.selector);guided_stats=None
        if method=='Post':
            gradient,grad_stats=objective.gradient();slopes=((self.transform.q99-self.transform.q01)/2).detach().cpu().numpy()
            direction=gradient.numpy()*slopes[None]**2
            extras=dict(post_command_gradient=gradient.numpy(),transform_slopes=slopes)
        elif method=='Velocity':
            native,guided_stats=self.propose(seed,objective)
            if base_stats['noise_sha256']!=guided_stats['noise_sha256']:raise ValueError('a0/guided noise mismatch')
            direction=np.clip(native,-1,1).astype(np.float32)[:10].astype(float)-base[:10].astype(float)
            grad_stats=None;extras=dict(own_native_raw=native)
        else:raise ValueError('unknown guidance method')
        plan,matching,arrays=project_solo(raw,direction,self.cfg['matching'])
        predictions=dict(replan=objective.evaluate(base[:10]),corrected=objective.evaluate(np.clip(plan[:10],-1,1)))
        objective.verify(check_hashes=False);stats=objective.stats()
        self.counts['action_gradients']+=stats['objective_backward_calls'];self.counts['Q_ensemble_forward']+=stats['objective_forward_calls']
        arrays.update(extras);np.savez_compressed(self.episode_out/('intervention_%03d.npz'%step),**arrays)
        return plan,dict(method=method,policy_calls=1 if method=='Post' else 2,seconds=time.monotonic()-begin,
            base=base_stats,guided=guided_stats,gradient=grad_stats,matching=matching,predictions=predictions,
            objective=stats,noise_sha256=base_stats['noise_sha256'],Q_acceptance_gate=False,other_direction_calls=0)

    def verify(self):
        if any(p._version!=v or p.requires_grad or p.grad is not None for p,v in self.versions):raise ValueError('frozen model changed')
        self.selector.verify()

