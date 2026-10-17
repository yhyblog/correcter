import numpy as np

def radii(delta):
    delta=np.asarray(delta,dtype=np.float64)
    return dict(xyz_rms=float(np.sqrt(np.mean(delta[:,:3]**2))),gripper_rms=float(np.sqrt(np.mean(delta[:,3:]**2))),
        xyz_linf=float(np.abs(delta[:,:3]).max()),gripper_linf=float(np.abs(delta[:,3:]).max()))
