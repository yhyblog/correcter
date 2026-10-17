from pathlib import Path
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');P=B/'results/A/A10_CAUSAL_C10_CPU_V1';O=B/'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1'
s=(O/'code/diagnostic.py').read_text()
chunk=s[s.index('    from lerobot.configs.policies'):s.index('    with np.load')]
chunk=chunk.replace('pc.n_action_steps=10','pc.n_action_steps=20')
q=s[s.index('    original_load=torch.load'):s.index("    stage='objective_setup'")]
header='''"""Real numeric setup extracted from accepted PV V3; imported only below gate.
Private integration changes: H20 policy config, native EGL binding, live cut.
Strict loader and corrector math are inherited verbatim except call-site scope.
"""
import hashlib,json,os
from pathlib import Path
from importlib.metadata import version
import numpy as np
import torch
from core.contracts import ContractError,write_new
class CountedCallable:
    def __init__(self,fn,meter,name,units):self.fn,self.meter,self.name,self.units=fn,meter,name,units
    def __call__(self,*a,**kw):return self.meter.call(self.name,lambda:self.fn(*a,**kw),self.units)
    def __getattr__(self,k):return getattr(self.fn,k)
def initialize(cfg,out,meter,device):
    for name,expected in cfg['runtime_packages'].items():
        if version(name)!=expected:raise ContractError('Runtime package changed: '+name)
    if torch.version.git_version!='e2d141dbde55c2a4370fac5165b0561b6af4798b':raise ContractError('Torch commit changed')
'''
end='''    transform=meter.call('load_same_action_transform',lambda:ActionTransform.from_checkpoint(ckpt,device=device),{'normalizer_transform_loads':1})
    projection=meter.call('load_frozen_spatial_projection',lambda:torch.from_numpy(np.load(cfg['projection'],allow_pickle=False)).to(device),{'projection_loads':1})
    return locals()
'''
(P/'code/numeric_setup.py').write_text(header+chunk+q+end)
print('Extracted strict loader, instrumentation and frozen Q setup; CPU source operations only')
