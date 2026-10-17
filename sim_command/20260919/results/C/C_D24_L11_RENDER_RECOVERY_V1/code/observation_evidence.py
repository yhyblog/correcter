"""Bounded evidence from planned rollouts only; no new renders/model calls."""
from pathlib import Path
import os
from qio import read,new_json,atomic_json,utc,process_identity

class ObservationEvidence:
    def __init__(self,unit,episode,worker,enabled):
        self.unit=unit;self.episode=Path(episode);self.worker=Path(worker);self.enabled=enabled;self.rows=[]
        self.previous=read(unit['original_source']['result_path']) if enabled else None
    def record(self,env,observation,step,monitor):
        if not self.enabled or step not in (0,5):return
        import numpy as np
        from PIL import Image
        rgb=np.asarray(observation['pixels']);prop=np.asarray(observation['agent_pos'])
        if rgb.shape!=(480,480,3) or rgb.dtype!=np.uint8 or not rgb.any() or not np.isfinite(prop).all():raise RuntimeError('invalid attributed observation')
        name=f'actual_rgb_step_{step:03d}.png';Image.fromarray(rgb).save(self.episode/name)
        renderer=getattr(env._env,'mujoco_renderer',None)
        viewers=getattr(renderer,'_viewers',{})
        old=next((x for x in self.previous.get('events',[]) if x['step']==step),None)
        difference=abs(float(monitor['gate'])-float(old['gate'])) if old else None
        # Small numerical variation across GPU replicas is permitted. This
        # two-frame check targets the known pre-Q corruption, not full-state
        # reproducibility or a new scientific acceptance criterion.
        passed=difference is not None and difference<=.001
        value=dict(utc=utc(),unit_id=self.unit['unit_id'],source_id=self.unit['source_id'],env_seed=self.unit['env_seed'],policy_seed=self.unit['policy_seed'],step=step,process=process_identity(),GPU_visibility=os.environ.get('CUDA_VISIBLE_DEVICES'),renderer_id=id(renderer),viewer_ids={str(k):id(v) for k,v in viewers.items()},pixels_path=str(self.episode/name),actual_frame=True,extra_render_calls=0,extra_model_calls=0,pre_Q=True,current_gate=monitor['gate'],historical_L01_gate=old['gate'] if old else None,gate_absolute_difference=difference,engineering_comparison_tolerance=.001,passed=passed)
        self.rows.append(value);new_json(self.episode/f'OBSERVATION_{step:03d}.json',value)
        if step==5:
            proof=dict(utc=utc(),unit_id=self.unit['unit_id'],passed=all(r['passed'] for r in self.rows) and len(self.rows)==2,checks=self.rows,planned_recovery_episode=True,additional_scientific_units=0)
            new_json(self.episode/'PRE_Q_VALIDATION.json',proof)
            atomic_json(self.worker/'FIRST_PLANNED_OBSERVATION.json',proof)
            if not proof['passed']:raise RuntimeError('first planned observation differs before Q; hold model admissions')
