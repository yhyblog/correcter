"""Bounded attributed RGB evidence from actual planned steps, without extra calls."""
from pathlib import Path
import os,hashlib
from qio import new_json,atomic_json,utc,process_identity
class ObservationEvidence:
    def __init__(self,unit,episode,worker,enabled):
        self.unit=unit;self.episode=Path(episode);self.worker=Path(worker);self.enabled=enabled;self.rows=[]
    def record(self,env,observation,step):
        if not self.enabled or step not in (0,5):return
        import numpy as np
        from PIL import Image
        from render_context import evidence
        rgb=np.asarray(observation['pixels']);prop=np.asarray(observation['agent_pos'])
        if rgb.shape!=(480,480,3) or rgb.dtype!=np.uint8 or not rgb.any() or not np.isfinite(prop).all():raise RuntimeError('invalid attributed actual observation')
        name=f'actual_rgb_step_{step:03d}.png';Image.fromarray(rgb).save(self.episode/name)
        row=dict(utc=utc(),unit_id=self.unit['unit_id'],source_id=self.unit['source_id'],normal_H=self.unit['H'],env_seed=self.unit['env_seed'],policy_seed=self.unit['policy_seed'],step=step,process=process_identity(),GPU_visibility=os.environ.get('CUDA_VISIBLE_DEVICES'),render_context=evidence(env),pixels_path=str(self.episode/name),pixels_sha256=hashlib.sha256(rgb.tobytes()).hexdigest(),proprioception=prop.tolist(),extra_render_calls=0,extra_model_calls=0,pre_intervention=step<=5,passed=True)
        self.rows.append(row);new_json(self.episode/f'OBSERVATION_{step:03d}.json',row)
        if step==5:atomic_json(self.worker/'FIRST_PLANNED_OBSERVATION.json',dict(utc=utc(),unit_id=self.unit['unit_id'],passed=len(self.rows)==2,checks=self.rows,planned_episode=True,structural_attribution_only=True,additional_scientific_units=0))
