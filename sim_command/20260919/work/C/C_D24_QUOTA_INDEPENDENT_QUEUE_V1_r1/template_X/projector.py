"""Preserve X raw H30 while reusing the frozen 10-command own-radius projector."""
import numpy as np
from experiments.standalone_ablation_20260918.candidates import project_solo as original
def project_solo(raw,direction,cfg):
    raw=np.asarray(raw)
    if raw.shape!=(30,4) or raw.dtype!=np.float32:raise ValueError('X native rawH30 required')
    padded=np.concatenate([raw,np.repeat(raw[-1:],20,axis=0)])
    full,stats,arrays=original(padded,direction,cfg)
    result=full[:30].copy()
    if not np.array_equal(result[10:],raw[10:]):raise ValueError('X unexecuted tail changed')
    return result,stats,arrays
