"""Real CPU Torch regression for cached inference normalization tensors."""
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np
import torch

C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
N=C/'results/B/B_D24_CROSSBASE_H_SWEEP_V1';R=N/'recovery/velocity_r2'
sys.path.insert(0,str(C/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code/vendor_vla/src'))
from lerobot.processor.normalize_processor import UnnormalizerProcessorStep
from lerobot.configs.types import FeatureType,NormalizationMode,PolicyFeature

def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class ActualInverseTransform:
    def __init__(self):
        self.step=UnnormalizerProcessorStep(features={'action':PolicyFeature(type=FeatureType.ACTION,shape=(4,))},
            norm_map={FeatureType.ACTION:NormalizationMode.MEAN_STD},dtype=torch.float64,
            stats={'action':{'mean':[0.1,-0.1,0.2,0.0],'std':[0.2,0.4,0.6,0.8]}})
        self.steps=[self.step]
    def __call__(self,x):return self.step._normalize_action(x,inverse=True)

def bridge(cls,post):
    b=cls.__new__(cls);b.post=post;b.updates=[]
    b.gradient_rpc=lambda x:dict(gradient=np.ones_like(x),value=0.)
    return b

old=module(N/'code/native_velocity.py','old_bridge').NativeVelocityBridge
fixed=module(R/'code/native_velocity.py','fixed_bridge').NativeVelocityBridge
post=ActualInverseTransform()
with torch.inference_mode():
    post(torch.zeros(10,4));clean=torch.zeros(1,50,4)
assert torch.is_inference(post.step._tensor_stats['action']['std'])
try:
    with torch.inference_mode():bridge(old,post).gradient(clean,.2)
except RuntimeError as e:
    assert 'Inference tensors cannot be saved for backward' in str(e)
    reproduced=str(e)
else:raise AssertionError('original defect was not reproduced')
before={k:v.clone() for k,v in post.step._tensor_stats['action'].items()}
b=bridge(fixed,post)
with torch.inference_mode():g=b.gradient(clean,.2)
expected=torch.tensor([.2,.4,.6,.8]).expand(10,4)
torch.testing.assert_close(g[0,:10],expected)
assert torch.count_nonzero(g[:,10:])==0 and len(b.updates)==1
for k,v in post.step._tensor_stats['action'].items():
    assert not torch.is_inference(v)
    torch.testing.assert_close(v,before[k],rtol=0,atol=0)
with torch.inference_mode():g2=b.gradient(clean,.2)
torch.testing.assert_close(g,g2,rtol=0,atol=0)
out=dict(status='passed',device='cpu',GPU_probe=False,original_failure_reproduced=reproduced,
    actual_normalizer_implementation_used=True,synthetic_CPU_statistics=True,normalization_values_bitwise_preserved=True,
    finite_expected_action_gradient=True,tail_gradient_zero=True,repeated_guidance_passed=True,
    model_weights_or_scientific_configuration_changed=False)
(R/'CPU_REPAIR_CHECK.json').write_text(json.dumps(out,sort_keys=True)+'\n');print(json.dumps(out))
