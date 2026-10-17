"""Synthetic CPU matching tests; no source files, model or simulator calls."""
import numpy as np
import pytest
from corrector.config import DEFAULT_MATCHING
from corrector.candidates import construct
from . import candidates as c


def test_tiny_nonzero_direction_is_expanded_not_shrink_only():
    raw=np.zeros((50,4),np.float32);direction=np.full((10,4),1e-7,np.float32)
    plan,meta,arrays=c.project_solo(raw,direction,DEFAULT_MATCHING)
    assert meta['groups']['xyz']['expanded'] and meta['groups']['gripper']['expanded']
    assert meta['groups']['xyz']['achieved_target']==.05*(1-1e-6)
    assert meta['groups']['gripper']['achieved_target']==.1*(1-1e-6)
    assert c.audit_solo(raw,plan,direction,DEFAULT_MATCHING)['status']=='passed'
    assert np.any(arrays['actual_delta'])


@pytest.mark.parametrize('channel',['xyz','gripper'])
def test_own_zero_only_disables_own_group(channel):
    raw=np.zeros((50,4),np.float32);d=np.ones((10,4),np.float32)
    if channel=='xyz':d[:,:3]=0
    else:d[:,3:]=0
    _,m,_=c.project_solo(raw,d,DEFAULT_MATCHING)
    assert m['groups'][channel]['zero_group']
    assert not m['groups']['gripper' if channel=='xyz' else 'xyz']['zero_group']


def test_other_joint_zero_no_longer_disables_post():
    base=np.zeros((50,4),np.float32);direction=np.ones((10,4),np.float32)
    old,oldmeta=construct(base,base,base,direction,7,DEFAULT_MATCHING)
    plan,new,_=c.project_solo(base,direction,DEFAULT_MATCHING)
    assert np.array_equal(old['post_matched'],base)
    assert oldmeta['groups']['xyz']['zero_group'] and np.any(plan[:10])
    assert new['groups']['xyz']['achieved_target']>0


def test_solo_radius_not_less_than_joint_for_same_direction():
    base=np.zeros((50,4),np.float32)
    velocity=base.copy();velocity[:10]=.02
    direct=base.copy();direct[:10]=.03
    post=np.full((10,4),.04,np.float32)
    _,old=construct(base,velocity,direct,post,11,DEFAULT_MATCHING)
    for direction in (velocity[:10].astype(float),direct[:10].astype(float),post):
        _,new,_=c.project_solo(base,direction,DEFAULT_MATCHING)
        for channel in ('xyz','gripper'):
            assert new['groups'][channel]['achieved_target']>=old['groups'][channel]['achieved_target']-1e-6


def test_sparse_group_uses_full_rms_denominator_and_coordinate_cap():
    raw=np.zeros((50,4),np.float32);d=np.zeros((10,4),np.float32);d[0,0]=1
    plan,meta,arrays=c.project_solo(raw,d,DEFAULT_MATCHING)
    assert meta['groups']['xyz']['raw_masked_rms']==float(np.sqrt(1/30))
    assert np.isclose(meta['groups']['xyz']['feasible_radius'],.15/np.sqrt(30))
    assert np.isclose(plan[0,0],.15*(1-1e-6))
    assert not np.any(arrays['actual_delta'][:,3])


def test_mask_raw_outside_tail_and_signed_zero_are_preserved():
    raw=np.zeros((50,4),np.float32);raw[0,0]=-0.;raw[:,3]=1.5
    raw[1,1]=np.nextafter(np.float32(.95),np.float32(1));raw[10:,:3]=.123
    d=np.ones((10,4),np.float32);d[0,0]=0
    plan,meta,arrays=c.project_solo(raw,d,DEFAULT_MATCHING)
    assert plan[0,0].tobytes()==raw[0,0].tobytes()
    assert c.bit_equal(plan[10:],raw[10:]) and c.bit_equal(plan[:,3],raw[:,3])
    assert not arrays['mask'][1,1] and c.bit_equal(plan[1:2,1],raw[1:2,1])
    assert meta['groups']['gripper']['zero_group']
    assert c.audit_solo(raw,plan,d,DEFAULT_MATCHING)['zero_delta_bit_exact']


@pytest.mark.parametrize('value',[0.,1e-12,1e-10])
def test_zero_threshold_does_not_invent_random_fallback(value):
    raw=np.zeros((50,4),np.float32);d=np.full((10,4),value,np.float64)
    plan,meta,_=c.project_solo(raw,d,DEFAULT_MATCHING)
    assert c.bit_equal(plan,raw)
    assert meta['random_calls']==0 and meta['other_directions_used'] is False


@pytest.mark.parametrize('change',['raw_dtype','direction_shape','nonfinite','changed_cap','changed_plan'])
def test_invalid_input_or_changed_projection_rejected(change):
    raw=np.zeros((50,4),np.float32);d=np.ones((10,4),np.float32);cfg=dict(DEFAULT_MATCHING)
    if change=='raw_dtype':raw=raw.astype(np.float64)
    elif change=='direction_shape':d=d[None]
    elif change=='nonfinite':d[0,0]=np.nan
    elif change=='changed_cap':cfg['xyz_linf']=.2
    with pytest.raises(ValueError):
        plan,_,_=c.project_solo(raw,d,cfg)
        if change=='changed_plan':plan[10,0]=.1;c.audit_solo(raw,plan,d,cfg)
