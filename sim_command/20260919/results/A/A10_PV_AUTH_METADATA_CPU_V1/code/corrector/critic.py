"""Frozen ten-step critic inference with parameterized, hash-checked assets.

Training, primitive selection policy and simulator state are deliberately absent.
Normalization and PCA preprocessing are contained in each checkpoint.
"""
# Extracted from ACT-RECAP/src/ac_tmil/ogg_research_v3/learning.py
# Source SHA256: e21a83fdbf6b052d2ed610c6adfeaaf186e64e9db122d6e02cb03ff372a21432
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

STATE_KEYS = ['history', 'history_mask', 'proprio', 'proprio_mask', 'past_actions', 'language', 'remaining']

def observed_features(arrays,norm_mean,norm_std):
    h=((arrays['history'].float()-norm_mean)/norm_std.clamp_min(1e-6)).clamp(-8,8)
    mask=arrays['history_mask'][...,None]
    visual=torch.cat([h[:,-1],(h*mask).sum(1)/mask.sum(1).clamp_min(1)],-1)
    language=F.layer_norm(arrays['language'].float(),(2048,))
    other=torch.cat([(arrays['proprio']*arrays['proprio_mask'][...,None]).flatten(1),
        arrays['past_actions'].flatten(1),arrays['remaining'].reshape(-1,1)],-1).float()
    return visual,language,other


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


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class FrozenSelector:
    """Load exactly four frozen v3 members without importing the training repo.

    ``assets_dir`` contains ``ranking.json``, optional ``config.json`` and
    ``models/refit/member_<id>/selected.pt``. Checkpoint hashes are mandatory.
    The default points to this checkout's ``assets/critic`` directory. All
    preprocessing buffers travel in the checkpoints, so no training data or
    separate visual normalization file is needed.

    This compatibility name supplies ``models``, ``ranking`` and ``verify`` to
    :class:`FrozenObjective`; it does not choose a correction arm or calibrate
    a deployment acceptance policy.
    """

    def __init__(self, assets_dir=None):
        self.assets_dir = (Path(assets_dir) if assets_dir is not None else
                           Path(__file__).resolve().parents[2] / 'assets' / 'critic')
        self.ranking_path = self.assets_dir / 'ranking.json'
        self.ranking = json.loads(self.ranking_path.read_text())
        self.ranking_hash = _sha256(self.ranking_path)
        cfg_path = self.assets_dir / 'config.json'
        self.cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
        self.models = []
        self.model_paths = []
        if len(self.ranking['model_hashes']) != 4 or self.ranking.get('horizon') != 10:
            raise ValueError('Expected the frozen four-member ten-step critic ranking')
        for member, expected in self.ranking['model_hashes'].items():
            if not str(member).isdigit():
                raise ValueError('Critic member identifiers must be numeric')
            path = self.assets_dir / 'models' / 'refit' / f'member_{member}' / 'selected.pt'
            if _sha256(path) != expected:
                raise ValueError(f'Critic checkpoint SHA changed: {path}')
            state = torch.load(path, map_location='cpu', weights_only=True)
            model = from_state(state).eval().requires_grad_(False)
            self.models.append(model)
            self.model_paths.append(path)
        self.versions = [(value, value._version) for model in self.models
                         for value in list(model.parameters()) + list(model.buffers())]

    def verify(self, check_files=False):
        if any(value._version != version for value, version in self.versions):
            raise ValueError('Frozen critic parameter or buffer changed')
        if any(model.training or any(p.requires_grad or p.grad is not None or p.device.type != 'cpu'
                                      for p in model.parameters()) for model in self.models):
            raise ValueError('Frozen critic gradient/eval/CPU invariant changed')
        if check_files:
            if _sha256(self.ranking_path) != self.ranking_hash:
                raise ValueError('Frozen ranking file SHA changed')
            for path, expected in zip(self.model_paths, self.ranking['model_hashes'].values()):
                if _sha256(path) != expected:
                    raise ValueError(f'Critic checkpoint SHA changed: {path}')
        return True
