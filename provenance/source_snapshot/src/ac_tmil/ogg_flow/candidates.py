"""Outcome-blind, symmetric matching on the commands actually executed."""
import numpy as np
from .common import MATCHED

def radii(delta):
    delta=np.asarray(delta,dtype=np.float64)
    return dict(xyz_rms=float(np.sqrt(np.mean(delta[:,:3]**2))),gripper_rms=float(np.sqrt(np.mean(delta[:,3:]**2))),
        xyz_linf=float(np.abs(delta[:,:3]).max()),gripper_linf=float(np.abs(delta[:,3:]).max()))

def construct(base,velocity,direct,post_gradient,random_seed,cfg):
    base=np.asarray(base,dtype=np.float32);a0=base[:10].astype(np.float64)
    assert base.shape==(50,4) and np.isfinite(base).all() and np.abs(base).max()<=1
    rng=np.random.default_rng(random_seed);knots=rng.normal(size=(3,4))
    random=np.stack([np.interp(np.arange(10),[0,4.5,9],knots[:,i]) for i in range(4)],axis=-1)
    directions=dict(velocity_matched=np.asarray(velocity[:10],float)-a0,direct_matched=np.asarray(direct[:10],float)-a0,
        post_matched=np.asarray(post_gradient,float),reverse_matched=-(np.asarray(direct[:10],float)-a0),random_matched=random)
    mask=1-np.abs(a0)>=cfg['boundary_clearance'];deltas={k:np.zeros((10,4)) for k in MATCHED};groups={}
    for name,indices in [('xyz',slice(0,3)),('gripper',slice(3,4))]:
        unit={};norms={};capacities={};bounds=np.minimum(1-np.abs(a0[:,indices]),cfg[name+'_linf'])
        for key in MATCHED:
            d=directions[key][:,indices]*mask[:,indices];norm=float(np.sqrt(np.mean(d*d)));norms[key]=norm
            unit[key]=d/max(norm,cfg['zero_threshold'])
            nz=np.abs(unit[key])>cfg['zero_threshold']
            capacities[key]=float(np.min(bounds[nz]/np.abs(unit[key][nz]))) if nz.any() else 0.
        radius=min(cfg[name+'_rms'],*capacities.values()) if min(norms.values())>cfg['zero_threshold'] else 0.
        radius=max(0.,radius*(1-1e-6))
        for key in MATCHED:deltas[key][:,indices]=radius*unit[key]
        groups[name]=dict(requested=cfg[name+'_rms'],achieved_target=radius,raw_masked_rms=norms,feasible_radii=capacities,
            zero_group=radius==0.,shrunk=radius<cfg[name+'_rms']*(1-2e-6))
    plans={'replan':base.copy(),'velocity_native':np.clip(velocity,-1,1).astype(np.float32),'direct_native':np.clip(direct,-1,1).astype(np.float32)}
    for key in MATCHED:
        plans[key]=base.copy();plans[key][:10]=(a0+deltas[key]).astype(np.float32)
        assert np.abs(plans[key]).max()<=1 and np.isfinite(plans[key]).all()
    achieved={k:radii(v[:10].astype(float)-a0) for k,v in plans.items()}
    for group in ['xyz','gripper']:
        values=[achieved[k][group+'_rms'] for k in MATCHED]
        assert max(values)-min(values)<cfg['tolerance']
    assert np.max(np.abs(plans['direct_matched'][:10].astype(float)+plans['reverse_matched'][:10]-2*a0))<cfg['tolerance']
    return plans,dict(groups=groups,actual=achieved,masked_fraction=float((~mask).mean()),
        mask=mask.tolist(),projection='group normalization and common symmetric feasible radius; may expand raw native output')
