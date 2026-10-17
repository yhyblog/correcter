"""Causal world dynamics, success values, and pre-proposal benefit prediction."""
from __future__ import annotations

import torch
from torch import nn
import torch.nn.functional as F


class ContextEncoder(nn.Module):
    def __init__(self, dimension, width=256, no_action=False):
        super().__init__();self.no_action=no_action
        self.visual=nn.Linear(dimension,width)
        self.proprio=nn.Linear(5,width)
        self.action=nn.Linear(4,width,bias=False)
        self.language=nn.Sequential(nn.LayerNorm(2048),nn.Linear(2048,width))
        self.cell=nn.GRUCell(width,width)
        self.norm=nn.LayerNorm(width)

    def forward(self, history, history_mask, past_actions, proprio, proprio_mask, language):
        batch,steps,_=history.shape
        if steps!=5 or past_actions.shape!=(batch,4,4):raise ValueError('invalid causal history')
        if not history_mask[:,-1].all():raise ValueError('current observation must be valid')
        actions=F.pad(past_actions,(0,0,1,0))
        if self.no_action:actions=torch.zeros_like(actions)
        p=torch.cat([proprio*proprio_mask[...,None],proprio_mask[...,None].to(proprio.dtype)],-1)
        context=self.language(language)
        tokens=self.visual(history)+self.action(actions)+self.proprio(p)+context[:,None]
        hidden=torch.zeros_like(context)
        for index in range(steps):
            updated=self.cell(self.norm(tokens[:,index]),hidden)
            hidden=torch.where(history_mask[:,index,None],updated,hidden)
        return hidden


class WorldModel(nn.Module):
    def __init__(self, normalization, width=256, no_action=False, no_proprio=False):
        super().__init__();self.no_action=no_action;self.no_proprio=no_proprio;self.horizon=5
        for key in ['mean','std','delta_scale']:
            self.register_buffer(key,torch.as_tensor(normalization[key],dtype=torch.float32))
        dimension=len(self.mean)
        self.encoder=ContextEncoder(dimension,width,no_action)
        self.action=nn.Linear(4,width,bias=False)
        self.feedback=nn.Linear(dimension,width)
        self.cell=nn.GRUCell(width,width)
        self.norm=nn.LayerNorm(width)
        self.visual_out=nn.Linear(width,dimension)
        self.proprio_out=nn.Linear(width,4)
        nn.init.zeros_(self.visual_out.weight);nn.init.zeros_(self.visual_out.bias)
        nn.init.zeros_(self.proprio_out.weight);nn.init.zeros_(self.proprio_out.bias)

    def forward(self,batch):
        a=batch['actions']
        if a.shape[1:]!=(5,4):raise ValueError('world model accepts exactly the committed five commands')
        history=(batch['history']-self.mean)/self.std
        proprio=torch.zeros_like(batch['proprio']) if self.no_proprio else batch['proprio']
        pmask=torch.zeros_like(batch['proprio_mask']) if self.no_proprio else batch['proprio_mask']
        hidden=self.encoder(history,batch['history_mask'],batch['past_actions'],
            proprio,pmask,batch['language'])
        predicted=history[:,-1];p=proprio[:,-1]
        states=[];proprios=[]
        for j in range(5):
            action=torch.zeros_like(a[:,j]) if self.no_action else a[:,j].clamp(-1,1)
            hidden=self.cell(self.norm(self.feedback(predicted)+self.action(action)),hidden)
            predicted=predicted+self.visual_out(hidden)*(self.delta_scale/self.std)/5
            p=p+self.proprio_out(hidden)/5
            states.append(predicted*self.std+self.mean);proprios.append(p)
        return torch.stack(states,1),torch.stack(proprios,1)


def masked_mse(predicted,target,mask,scale):
    error=((predicted-target)/scale).float().square().mean(-1)
    return (error*mask).sum()/mask.sum().clamp_min(1)


def intervention_loss(predicted,target,mask,scale):
    """Candidates in the same source state; no cross-state contrast pairs."""
    if predicted.ndim!=4 or predicted.shape[1]!=4:raise ValueError('expected [group,4,time,feature]')
    left,right=torch.triu_indices(4,4,1,device=predicted.device)
    pm=mask[:,left]&mask[:,right]
    error=(((predicted[:,left]-predicted[:,right])-(target[:,left]-target[:,right]))/scale).square().mean(-1)
    return (error*pm).sum()/pm.sum().clamp_min(1)


class OutcomeModel(nn.Module):
    """Q_5^fixed10; only the five executed commands and their predicted effects."""
    def __init__(self,normalization,future=True,width=128):
        super().__init__();self.future=future
        for key in ['mean','std','delta_scale']:
            self.register_buffer(key,torch.as_tensor(normalization[key],dtype=torch.float32))
        dimension=len(self.mean)
        self.encoder=ContextEncoder(dimension,width)
        self.actions=nn.Linear(20,width)
        self.effects=nn.Linear(dimension,width) if future else None
        self.head=nn.Sequential(nn.Linear(width*3+1 if future else width*2+1,width),nn.SiLU(),
                                nn.Dropout(.1),nn.Linear(width,1))

    def forward(self,batch,predicted=None):
        if batch['actions'].shape[1:]!=(5,4):raise ValueError('outcome score cannot read unexecuted tail')
        h=self.encoder((batch['history']-self.mean)/self.std,batch['history_mask'],
            batch['past_actions'],batch['proprio'],batch['proprio_mask'],batch['language'])
        values=[h,self.actions(batch['actions'].clamp(-1,1).flatten(1))]
        if self.future:
            if predicted is None:raise ValueError('predicted future is required')
            if predicted.shape!=(len(h),5,len(self.mean)):
                raise ValueError('outcome future must match the five committed action times')
            # All five action-conditioned effects contribute; no real future in inference.
            effect=(predicted-batch['history'][:,-1,None])/self.delta_scale
            values.append(self.effects(effect.mean(1)))
        values.append(batch['remaining'][:,None])
        return self.head(torch.cat(values,-1)).squeeze(-1)


class BenefitModel(OutcomeModel):
    """Regression of a specified continue/replan protocol, not a safety probability."""
    pass


class ControllerBenefitModel(BenefitModel):
    """Long-term intervention benefit also depends on the preserved queued tail."""
    def __init__(self,normalization,width=128):
        super().__init__(normalization,future=True,width=width)
        self.queue_head=nn.Sequential(nn.Linear(50*4+50+1,64),nn.SiLU(),nn.Linear(64,1))
        nn.init.zeros_(self.queue_head[-1].weight);nn.init.zeros_(self.queue_head[-1].bias)

    def forward(self,batch,predicted=None):
        queue=batch['queue'];mask=batch['queue_mask']
        if queue.shape[1:]!=(50,4) or mask.shape!=queue.shape[:2]:raise ValueError('invalid remaining queue')
        context=torch.cat([(queue.clamp(-1,1)*mask[...,None]).flatten(1),mask.to(queue.dtype),
                           batch['plan_age'][:,None].to(queue.dtype)/50],-1)
        return super().forward(batch,predicted)+self.queue_head(context).squeeze(-1)


def binomial_loss(logits,successes,repeats):
    if (repeats<=0).any() or (successes<0).any() or (successes>repeats).any():
        raise ValueError('invalid Bernoulli outcome counts')
    # Candidate groups receive equal weight; repeats express precision, not new states.
    return F.binary_cross_entropy_with_logits(logits,successes/repeats)
