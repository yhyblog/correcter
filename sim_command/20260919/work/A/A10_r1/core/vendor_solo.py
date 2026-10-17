"""One-direction matching; no other candidate or random generator is an input."""
from __future__ import annotations

import hashlib
import numpy as np

from .vendor_dependencies import preserve_raw_anchor, radii

METHODS=('solo_post','solo_direct','solo_velocity')
MARGIN=1-1e-6


def bit_equal(first,second):
    a,b=np.asarray(first),np.asarray(second)
    return a.shape==b.shape and a.dtype==b.dtype and a.tobytes()==b.tobytes()


def array_sha(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def _inputs(raw_a0,direction,cfg):
    raw=np.asarray(raw_a0)
    vector=np.asarray(direction)
    if raw.shape!=(50,4) or raw.dtype!=np.dtype('float32') or not np.isfinite(raw).all():
        raise ValueError('Raw anchor must be finite float32 [50,4]')
    if vector.shape!=(10,4) or not np.issubdtype(vector.dtype,np.floating) or not np.isfinite(vector).all():
        raise ValueError('Only one finite ten-command direction is accepted')
    expected=dict(xyz_rms=.05,gripper_rms=.10,xyz_linf=.15,gripper_linf=.4,
                  boundary_clearance=.05,tolerance=1e-6,zero_threshold=1e-10)
    if any(cfg.get(k)!=v for k,v in expected.items()):
        raise ValueError('Standalone matching must retain the frozen scientific settings')
    return raw,vector


def project_solo(raw_a0,direction,cfg):
    """Return (raw50, matching metadata, arrays) using only this direction.

    The original group RMS includes masked coordinates. Symmetric capacities,
    float64 matching, float32 command write and the original inward margin are
    retained. A small nonzero native direction may be expanded.
    """
    raw,vector=_inputs(raw_a0,direction,cfg)
    base=np.clip(raw,-1,1).astype(np.float32);anchor=base[:10].astype(np.float64)
    mask=1-np.abs(anchor)>=cfg['boundary_clearance']
    masked=np.asarray(vector,np.float64)*mask
    unit=np.zeros((10,4),np.float64);delta=np.zeros_like(unit);groups={}
    for name,indices in (('xyz',slice(0,3)),('gripper',slice(3,4))):
        d=masked[:,indices];norm=float(np.sqrt(np.mean(d*d)))
        bounds=np.minimum(1-np.abs(anchor[:,indices]),cfg[name+'_linf'])
        # Keep the original max(n, threshold) arithmetic; only own n is tested.
        e=d/max(norm,cfg['zero_threshold']);unit[:,indices]=e
        nz=np.abs(e)>cfg['zero_threshold']
        capacity=float(np.min(bounds[nz]/np.abs(e[nz]))) if nz.any() else 0.
        radius=min(cfg[name+'_rms'],capacity) if norm>cfg['zero_threshold'] else 0.
        radius=max(0.,radius*MARGIN);delta[:,indices]=radius*e
        groups[name]=dict(requested=cfg[name+'_rms'],raw_masked_rms=norm,feasible_radius=capacity,
            achieved_target=radius,zero_group=radius==0.,own_direction_zero=norm<=cfg['zero_threshold'],
            shrunk=radius<cfg[name+'_rms']*(1-2e-6),expanded=radius>norm,
            other_direction_capacities_used=False)
    bounded=base.copy();bounded[:10]=(anchor+delta).astype(np.float32)
    raw_plan=preserve_raw_anchor(raw,base,bounded)
    actual=raw_plan[:10].astype(np.float64)-raw[:10].astype(np.float64)
    if not np.isfinite(raw_plan).all() or any(radii(actual)[k]>cfg[k]+cfg['tolerance'] for k in radii(actual)):
        raise ValueError('Standalone projection exceeds the original finite command caps')
    if not bit_equal(raw_plan[10:],raw[10:]) or not bit_equal(raw_plan[:10][~mask],raw[:10][~mask]):
        raise ValueError('Standalone projection changed raw tail or masked coordinates')
    np.testing.assert_allclose(np.clip(raw_plan[:10],-1,1).astype(float)-anchor,actual,atol=cfg['tolerance'],rtol=0)
    result=dict(schema='standalone_own_radius_v1',groups=groups,actual=radii(actual),
        masked_fraction=float((~mask).mean()),mask=mask.tolist(),radius_margin=MARGIN,
        projection='own direction normalization and own symmetric feasible radius; may expand native direction',
        other_directions_used=False,random_calls=0)
    arrays=dict(raw_a0=raw.copy(),critic_a0=base,raw_plan=raw_plan.copy(),raw_direction=vector.copy(),
        mask=mask,masked_direction=masked,unit_direction=unit,requested_delta=delta,actual_delta=actual,
        critic_commands=np.clip(raw_plan[:10],-1,1))
    return raw_plan,result,arrays


def audit_solo(raw_a0,raw_plan,raw_direction,matching_cfg):
    """CPU replay of the one-direction projection; no model or other arm access."""
    expected,matching,arrays=project_solo(raw_a0,raw_direction,matching_cfg)
    if not bit_equal(raw_plan,expected):raise ValueError('Saved solo plan differs from its own-direction projection')
    raw=np.asarray(raw_a0);actual=arrays['actual_delta'];zero=actual==0
    if not bit_equal(np.asarray(raw_plan)[:10][zero],raw[:10][zero]):
        raise ValueError('Zero actual delta changed the raw bit pattern')
    return dict(status='passed',raw_a0_sha256=array_sha(raw),raw_plan_sha256=array_sha(raw_plan),
        direction_sha256=array_sha(raw_direction),actual=matching['actual'],groups=matching['groups'],
        tail_bit_exact=True,mask_bit_exact=True,zero_delta_bit_exact=True,critic_raw_delta_consistent=True,
        own_only_projection=True,other_directions_used=False)
