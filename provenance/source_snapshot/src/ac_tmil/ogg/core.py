from __future__ import annotations
from dataclasses import dataclass
import json,math
from pathlib import Path
import numpy as np
import torch
from torch import nn
from safetensors.torch import load_file
from .common import digest


class ActionTransform(nn.Module):
    def __init__(self,q01,q99,eps=1e-8):
        super().__init__();self.register_buffer('q01',torch.as_tensor(q01).clone().float())
        self.register_buffer('q99',torch.as_tensor(q99).clone().float());self.eps=eps
    @classmethod
    def from_checkpoint(cls,path,device='cuda:0'):
        path=Path(path);meta=json.loads((path/'policy_postprocessor.json').read_text())['steps'][0]
        if meta['config']['norm_map']['ACTION']!='QUANTILES':raise ValueError('unsupported action normalization')
        state=load_file(path/meta['state_file'])
        get=lambda suffix:next(v for k,v in state.items() if 'action' in k and k.endswith(suffix))
        return cls(get('q01')[:4],get('q99')[:4],meta['config']['eps']).to(device)
    def forward(self,clean,clip=True):
        values=clean[...,:4];delta=self.q99-self.q01
        delta=torch.where(delta==0,torch.as_tensor(self.eps,device=values.device,dtype=values.dtype),delta)
        values=(values+1.0)*delta/2.0+self.q01
        return values.clamp(-1,1) if clip else values


@dataclass
class Reference:
    source_id:str
    start:int
    target_step:int
    plan_id:int
    commands:np.ndarray
    predicted:np.ndarray
    start_visual:np.ndarray
    feature_id:str
    d_id:str
    def validate(self,step,plan_id,executed,feature_id,d_id,terminal=False):
        if terminal or step+5>300:return 'terminal_or_budget'
        if self.target_step!=step or step-self.start!=5:return 'wrong_time'
        if self.plan_id!=plan_id:return 'wrong_plan'
        if feature_id!=self.feature_id or d_id!=self.d_id:return 'wrong_version'
        if np.shape(executed)!=(5,4) or not np.array_equal(np.clip(executed,-1,1),self.commands):return 'wrong_commands'
        if self.predicted.shape!=(5,4096) or not np.isfinite(self.predicted).all():return 'invalid_prediction'
        return None
    def metadata(self):
        return dict(source_id=self.source_id,reference_start_step=self.start,target_step=self.target_step,plan_id=self.plan_id,
                    planned_commands_5x4=self.commands.tolist(),planned_commands_hash=digest(self.commands),
                    feature_version=self.feature_id,projection_seed=19431,normalization_version=self.d_id,d_checkpoint_id=self.d_id,
                    provenance='saved_before_executing_reference_prefix')


class GuidanceError(RuntimeError):pass


def velocity_update(x,v,tau,transform,loss_fn,settings):
    """Frozen velocity as a leaf: preserve gradients only through the action objective."""
    if x.shape!=v.shape or x.ndim!=3 or x.shape[1:]!=(50,32):raise GuidanceError('invalid_velocity_shape')
    with torch.inference_mode(False),torch.enable_grad():
        x=x.detach().clone().float();leaf=v.detach().clone().float().requires_grad_(True)
        clean=x-float(tau)*leaf;before=transform(clean[:,:5])
        loss=loss_fn(before)
        if loss.ndim or not torch.isfinite(loss):raise GuidanceError('nonfinite_or_nonscalar_loss')
        gradient=torch.autograd.grad(loss,leaf,allow_unused=False)[0]
        if not torch.isfinite(gradient).all():raise GuidanceError('nonfinite_gradient')
        mask=torch.zeros_like(gradient);mask[:,:5,:4]=1;gradient=gradient*mask
        log=dict(tau=float(tau),loss_before=float(loss.detach()),gradient_norm=float(gradient.norm()),
                 direct_gradient_outside_mask=float((gradient*(1-mask)).abs().max()),
                 clipping_fraction=float((before.abs()>=1).float().mean()),accepted=False,halvings=0,
                 objective_forward_calls=1,backward_calls=1)
        accepted=v.detach();last=before.detach()
        for halving in range(settings['max_halvings']+1):
            alpha=settings['alpha']/(2**halving);candidate=leaf.detach()-alpha*gradient.detach()
            after=transform(x-float(tau)*candidate)[:,:5]
            delta=(after-before.detach()).abs()
            if not torch.isfinite(after).all():raise GuidanceError('nonfinite_commands')
            if float(delta.max())<=settings['command_cap']:
                accepted=candidate;last=after;log.update(accepted=True,halvings=halving,alpha=alpha,
                    command_delta_linf=float(delta.max()),command_delta_per_dimension=delta.amax((0,1)).tolist())
                break
        with torch.no_grad():loss_after=loss_fn(last)
        log['objective_forward_calls']+=1
        if not torch.isfinite(loss_after):raise GuidanceError('nonfinite_updated_loss')
        log['loss_after']=float(loss_after)
        return accepted.to(dtype=v.dtype),log


class DenoiseHook:
    """Patch only velocity outputs; retain the existing PI0.5 sampler and timing grid."""
    def __init__(self,model,transform,settings):
        self.model=model;self.original=model.denoise_step;self.transform=transform;self.settings=settings
        self.loss_fn=None;self.logs=[];self.times=[];self.objective_calls=0;self.failed_backward_calls=0
        def wrapped(*args,**kwargs):
            value=self.original(*args,**kwargs)
            tau=float(kwargs['timestep'][0]);self.times.append(tau)
            if self.loss_fn is None or self.settings['alpha']==0:return value
            if not any(math.isclose(tau,t,abs_tol=1e-6) for t in self.settings['times']):return value
            try:result,row=velocity_update(kwargs['x_t'],value,tau,self.transform,self.loss_fn,self.settings)
            except GuidanceError as error:
                self.failed_backward_calls+=int(str(error) in ['nonfinite_gradient','nonfinite_commands','nonfinite_updated_loss'])
                raise
            self.logs.append(row);return result
        model.denoise_step=wrapped
    def begin(self,loss_fn=None):
        self.logs=[];self.times=[];self.objective_calls=0;self.failed_backward_calls=0
        def counted(commands):
            self.objective_calls+=1
            try:return loss_fn(commands)
            except ValueError as error:raise GuidanceError('invalid_objective_input: '+str(error)) from error
        self.loss_fn=counted if loss_fn is not None else None
    def close(self):self.model.denoise_step=self.original


def visual_objective(world,batch,target):
    target=target.detach().clone()
    if target.requires_grad:raise ValueError('reference target must be frozen')
    def loss(commands):
        predicted,_=world(dict(batch,actions=commands))
        return ((predicted[:,4]-target)/world.delta_scale).square().mean()
    return loss
