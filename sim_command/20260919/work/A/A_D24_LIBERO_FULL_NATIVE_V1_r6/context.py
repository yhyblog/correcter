"""Causal native329 decomposition; no model/hardware import."""
import numpy as np

def context(features,actions,step):
    if len(features)!=step+1 or len(actions)!=step:raise ValueError('causal feature/action clock')
    history=np.zeros((5,192),np.float32);mask=np.zeros(5,bool)
    proprio=np.zeros((5,8),np.float32);past=np.zeros((4,7),np.float32)
    start=max(0,step-4);block=np.asarray(features[start:step+1],np.float32)
    if block.shape!=(step-start+1,329) or not np.isfinite(block).all():raise ValueError('native329 finite features')
    history[-len(block):]=block[:,:192];proprio[-len(block):]=block[:,320:328];mask[-len(block):]=True
    if step>start:past[-(step-start):]=np.asarray(actions[start:step],np.float32)
    return dict(history=history,history_mask=mask,past_actions=past,proprio=proprio,
        proprio_mask=mask.copy(),language=block[-1,192:320].copy(),remaining=np.asarray(block[-1,328],np.float32))

def legal_age2(step,chunk_start,pending,max_steps,used):
    return not used and step-chunk_start==2 and len(pending)==3 and step+5<=max_steps

def stack(rows):
    return {k:np.stack([r[k] for r in rows]) for k in rows[0]}
