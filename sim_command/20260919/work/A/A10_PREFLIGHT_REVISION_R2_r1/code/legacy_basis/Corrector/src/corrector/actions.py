"""Actual command transformation used by all three correction methods."""
# Extracted from ACT-RECAP/src/ac_tmil/ogg/core.py
# Source SHA256: ddf23e1a4905cfce9276e6708dd26ad3560b43fdd3ad7ca44a74f4a23a64b985
import json
from pathlib import Path

import torch
from torch import nn

class ActionTransform(nn.Module):
    def __init__(self,q01,q99,eps=1e-8):
        super().__init__();self.register_buffer('q01',torch.as_tensor(q01).clone().float())
        self.register_buffer('q99',torch.as_tensor(q99).clone().float());self.eps=eps
    @classmethod
    def from_checkpoint(cls,path,device='cuda:0'):
        path=Path(path);meta=json.loads((path/'policy_postprocessor.json').read_text())['steps'][0]
        if meta['config']['norm_map']['ACTION']!='QUANTILES':raise ValueError('unsupported action normalization')
        from safetensors.torch import load_file
        state=load_file(path/meta['state_file'])
        get=lambda suffix:next(v for k,v in state.items() if 'action' in k and k.endswith(suffix))
        return cls(get('q01')[:4],get('q99')[:4],meta['config']['eps']).to(device)
    def forward(self,clean,clip=True):
        values=clean[...,:4];delta=self.q99-self.q01
        delta=torch.where(delta==0,torch.as_tensor(self.eps,device=values.device,dtype=values.dtype),delta)
        values=(values+1.0)*delta/2.0+self.q01
        return values.clamp(-1,1) if clip else values


class GuidanceError(RuntimeError):pass

