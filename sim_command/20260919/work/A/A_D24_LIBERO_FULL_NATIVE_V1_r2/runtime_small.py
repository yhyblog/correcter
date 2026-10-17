"""Frozen CPU D2/G0; mature residual is diagnostic only."""
from pathlib import Path
import numpy as np
import torch
import d24_common as d
from native_models import WorldModel,BenefitModel

class Monitor:
    def __init__(self):
        torch.set_num_threads(2)
        ready=d.load(d.R/'MODEL_READY.json');normal=d.load(d.R/'models/normalization.json')
        self.worlds=[];self.gates=[]
        for ws,gs in zip([241,242],[341,342]):
            world=WorldModel(normal);gate=BenefitModel(normal)
            world.load_state_dict(torch.load(str(d.R/'models'/('D%d.pt'%ws)),map_location='cpu',weights_only=True))
            gate.load_state_dict(torch.load(str(d.R/'models'/('G0%d.pt'%gs)),map_location='cpu',weights_only=True))
            self.worlds.append(world.eval().requires_grad_(False));self.gates.append(gate.eval().requires_grad_(False))
        self.normal=normal;self.counts=dict(D_forward=0,G0_forward=0,matured_residuals=0)

    def tensor(self,context,actions):
        return dict({k:torch.from_numpy(np.asarray(v))[None] for k,v in context.items()},
                    actions=torch.as_tensor(np.asarray(actions),dtype=torch.float32)[None])

    @torch.no_grad()
    def predict(self,context,actions):
        batch=self.tensor(context,actions[:2]);pred=[]
        for world in self.worlds:
            f,p=world(batch);self.counts['D_forward']+=1;pred.append(f[0].numpy())
        return np.stack(pred)

    @torch.no_grad()
    def monitor(self,context,old3,mature_prediction,current_feature):
        old3=np.asarray(old3,np.float32)
        if old3.shape!=(3,7):raise ValueError('G0 must see exactly old three queued native commands')
        batch=self.tensor(context,old3);benefits=[]
        for world,gate in zip(self.worlds,self.gates):
            future,_=world(dict(batch,actions=batch['actions'][:,:2]));self.counts['D_forward']+=1
            benefits.append(float(gate(batch,future)));self.counts['G0_forward']+=1
        if not np.isfinite(benefits).all():raise ValueError('Nonfinite G0')
        residual=np.sqrt(np.mean(((mature_prediction[:,-1]-current_feature[:192])/np.asarray(self.normal['delta_scale']))**2))
        self.counts['matured_residuals']+=1
        return dict(gate=float(np.mean(benefits)),member_benefits=benefits,threshold=.05,
                    D2_mature_residual_diagnostic=float(residual),residual_in_G0_input=False)
