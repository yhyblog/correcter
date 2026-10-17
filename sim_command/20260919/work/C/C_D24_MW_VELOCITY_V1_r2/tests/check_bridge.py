"""One bounded CPU check of native-coordinate gradients and solver signs."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import torch
from safetensors.torch import load_file
W=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(W))
from native_velocity import NativeVelocityBridge
from lerobot.processor import PolicyProcessorPipeline
from lerobot.processor.converters import policy_action_to_transition,transition_to_policy_action

reports=[]
for kind,stem,dim,H in [('smolvla','smol50k',32,50),('xvla','xvla30k',20,30)]:
    cfg=json.loads((W/'configs'/(stem+'_Velocity_shard0_r2.json')).read_text());ckpt=Path(cfg['checkpoint'])
    post=PolicyProcessorPipeline.from_pretrained(str(ckpt),config_filename='policy_postprocessor.json',
        to_transition=policy_action_to_transition,to_output=transition_to_policy_action)
    stats=load_file(str(ckpt/'policy_postprocessor_step_0_unnormalizer_processor.safetensors'))
    mean,std=stats['action.mean'],stats['action.std']
    policy=SimpleNamespace(config=SimpleNamespace(n_obs_steps=1,adapt_to_pi_aloha=False,action_mode='auto'),parameters=lambda:[])
    policy.model=SimpleNamespace(_rtc_enabled=lambda:False,denoise_step=lambda **kw:torch.zeros_like(kw['x_t']),
                                action_space=SimpleNamespace(real_dim=4),transformer=torch.nn.Identity())
    bridge=NativeVelocityBridge(policy,post,kind)
    clean=torch.zeros(1,H,dim);clean[0,0,0]=100
    ga=torch.arange(1,5).float().expand(10,4)
    bridge.begin(lambda commands:dict(gradient=ga.tolist(),value=float((torch.tensor(commands)*ga).sum())))
    got=bridge.gradient(clean,.3)
    expected=torch.zeros_like(clean);expected[0,:10,:4]=ga*std
    expected[0,0,0]=0
    torch.testing.assert_close(got,expected)
    leaf=clean[:,:10,:4].clone();mapped=post(leaf[0])
    torch.testing.assert_close(mapped,leaf[0]*std+mean)
    # Guidance placement, zero-strength identity, and negative-dt ascent.
    x=torch.zeros_like(clean);v=torch.zeros_like(clean)
    bridge.begin(lambda commands:dict(gradient=ga.tolist(),value=0.))
    for i in range(10):
        tau=1-i/10;t=torch.tensor([tau])
        if kind=='smolvla':out=bridge.smol(x,v,t)
        else:out=bridge.x_hook(None,(),{'action_with_noise':x,'t':t},v)
        expected_out=torch.zeros_like(v)
        if i>=7:expected_out[0,:10,:4]=((-10*tau) if kind=='smolvla' else (10*tau*tau))*ga*std
        torch.testing.assert_close(out,expected_out)
        if i>=7 and kind=='smolvla':assert ((-.1*out[0,:10,:4])*ga*std).sum()>0
    summary=bridge.finish();assert len(summary['updates'])==3
    bridge.begin()
    for i in range(10):
        t=torch.tensor([1-i/10])
        out=bridge.smol(x,v,t) if kind=='smolvla' else bridge.x_hook(None,(),{'action_with_noise':x,'t':t},v)
        assert out is v
    bridge.finish()
    reports.append(dict(base=kind,status='passed',saved_inverse_normalization=True,true_clamp_zero_outside=True,
        zero_padding_tail_gradient=True,three_late_updates=True,unguided_native_output_unchanged=True,
        model_loaded=False,GPU_initialized=torch.cuda.is_initialized(),action_std=std.tolist(),action_mean=mean.tolist()))
(W/'MINIMUM_CPU_CHECKS.json').write_text(json.dumps(reports,indent=2)+'\n')
print(json.dumps(reports,indent=2))
