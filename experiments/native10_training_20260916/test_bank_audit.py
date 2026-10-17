import numpy as np
import pytest
from corrector.candidates import construct
from .commands import preserve_raw_anchor
from .bank_audit import audit_raw_bank

CFG=dict(xyz_rms=.05,gripper_rms=.1,xyz_linf=.15,gripper_linf=.4,boundary_clearance=.05,tolerance=1e-6,zero_threshold=1e-10)


def test_full_bank_preserves_raw_anchor_mask_actual_deltas_and_reverse():
    rng=np.random.default_rng(211)
    raw=rng.uniform(-.6,.6,(50,4)).astype(np.float32)
    raw[0]=[1.4,-1.3,.97,-.97]
    raw[1,2]=-0.
    base=np.clip(raw,-1,1)
    velocity=np.clip(base+rng.normal(0,.1,(50,4)),-1,1).astype(np.float32)
    direct=np.clip(base+rng.normal(0,.1,(50,4)),-1,1).astype(np.float32)
    bounded,_=construct(base,velocity,direct,rng.normal(size=(10,4)),31,CFG)
    actual={name:preserve_raw_anchor(raw,base,plan) for name,plan in bounded.items() if not name.endswith('_native')}
    audit=audit_raw_bank(raw,actual,CFG)
    assert audit['status']=='passed'
    for plan in actual.values():
        np.testing.assert_array_equal(plan[0],raw[0])
        assert plan[10:].tobytes()==raw[10:].tobytes()


def test_mapping_audit_rejects_unreported_near_boundary_change():
    raw=np.zeros((50,4),np.float32);raw[0,0]=.97
    corrupted=raw.copy();corrupted[0,0]=.98
    with pytest.raises(AssertionError):audit_raw_bank(raw,{'replan':raw,'post':corrupted},CFG)
