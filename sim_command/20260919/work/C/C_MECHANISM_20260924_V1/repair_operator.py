"""Fixed-anchor variants; all writes preserve untouched raw coordinates."""
import numpy as np

def describe(raw,plan):
    d=plan[:10].astype(float)-raw[:10].astype(float)
    b=np.clip(raw[:10],-1,1);mask=1-np.abs(b)>=.05
    bounds=np.minimum(1-np.abs(b),np.array([.15,.15,.15,.4]))
    assert np.array_equal(plan[10:],raw[10:]) and np.array_equal(plan[:10][~mask],raw[:10][~mask])
    assert np.isfinite(plan).all() and np.all(np.abs(d)<=bounds+1e-6)
    return dict(xyz_rms=float(np.sqrt(np.mean(d[:,:3]**2))),gripper_rms=float(np.sqrt(np.mean(d[:,3:]**2))),zero=bool(not np.any(d)),mask_fraction=float(mask.mean()),boundary_fraction=float(np.mean((np.abs(d)>=bounds-1e-6)&mask)))

def write_delta(raw,delta):
    p=raw.copy();nonzero=delta!=0
    p[:10][nonzero]=(raw[:10].astype(float)+delta)[nonzero].astype(np.float32)
    describe(raw,p);return p

def project(raw,direction,multiplier=1.,unified=False,expand=True):
    anchor=np.clip(raw[:10],-1,1).astype(float)
    mask=1-np.abs(anchor)>=.05
    d=np.asarray(direction,float)*mask
    bound=np.minimum(1-np.abs(anchor),np.array([.15,.15,.15,.4]))
    delta=np.zeros_like(d);factors=[]
    for ids,rho in [(slice(0,3),.05*multiplier),(slice(3,4),.1*multiplier)]:
        x=d[:,ids];n=np.sqrt(np.mean(x*x));nz=np.abs(x)>1e-10
        factor=min(rho/max(n,1e-10),float(np.min(bound[:,ids][nz]/np.abs(x[nz])))) if n>1e-10 else 0.
        if not expand:factor=min(1.,factor)
        factors.append(factor)
        delta[:,ids]=x*factor*(1-1e-6)
    if unified:
        positive=[f for f,x in zip(factors,[d[:,:3],d[:,3:]]) if np.any(x)]
        delta=d*(min(positive) if positive else 0.)*(1-1e-6)
    return write_delta(raw,delta)

def sign_variant(raw,post,sign):return write_delta(raw,(post[:10].astype(float)-raw[:10].astype(float))*sign)
