"""CPU invariants on final raw commands and the critic's bounded representation."""
import numpy as np
from corrector.candidates import radii


def audit_raw_bank(raw_a0, plans, config):
    raw=np.asarray(raw_a0,dtype=np.float32)
    base=np.clip(raw,-1,1)
    mask=1-np.abs(base.astype(np.float64))>=config['boundary_clearance']
    rows={}
    for name,value in plans.items():
        value=np.asarray(value,dtype=np.float32)
        if value.shape!=raw.shape or not np.isfinite(value).all():raise ValueError('Invalid raw candidate')
        delta=value.astype(np.float64)-raw.astype(np.float64)
        np.testing.assert_array_equal(value[10:],raw[10:])
        np.testing.assert_array_equal(value[~mask],raw[~mask])
        proxy=np.clip(value,-1,1)
        np.testing.assert_allclose(proxy.astype(float)-base.astype(float),delta,atol=1e-6,rtol=0)
        stats=radii(delta[:10])
        for group in ('xyz','gripper'):
            for norm in ('rms','linf'):
                if stats[group+'_'+norm]>config[group+'_'+norm]+1e-6:
                    raise ValueError('Final executed perturbation exceeds cap')
        rows[name]=dict(actual_delta=stats,raw_outside_unit_fraction=float((np.abs(value[:10])>1).mean()),
                        raw_max_abs=float(np.abs(value[:10]).max()),critic_mapping_passed=True,mask_passed=True)
    name='replan' if 'replan' in plans else 'a0'
    if np.asarray(plans[name]).tobytes()!=raw.tobytes():raise ValueError('Raw anchor not bit-identical')
    if 'reverse_matched' in plans:
        np.testing.assert_allclose(plans['direct_matched'][:10].astype(float)+plans['reverse_matched'][:10]-2*raw[:10],0,atol=1e-6,rtol=0)
    return dict(status='passed',tolerance=1e-6,anchor_bit_identical=True,actual=rows,
                bounded_proxy_is_scored=True,raw_identity_not_inferred_from_proxy=True)
