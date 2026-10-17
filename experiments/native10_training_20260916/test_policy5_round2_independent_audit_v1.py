"""Synthetic only: completion gates, source aggregation and raw-command checks."""
from copy import deepcopy
import json

import numpy as np
import pytest

from . import policy5_round2_independent_audit_v1 as audit


def test_independent_pair_counts_and_bootstrap():
    assert audit.self_test()['status']=='passed'
    y=np.zeros((100,5,4),bool)
    y[:5,:,:]=True
    y[5,2,:]=True
    y[6,1,:2]=True
    rows=[dict(episode_id=str(i),task=str(i%5),no_cut=i<5) for i in range(100)]
    result=audit.aggregate(y,rows,[str(i) for i in range(5)],draws=10000)
    value=result['comparisons']['velocity_minus_alarm_replan10']
    assert value['rescues']==4 and value['harms']==2 and value['gain']==.005
    assert (value['positive_sources'],value['negative_sources'],value['zero_sources'])==(1,1,98)
    assert result['overall']['logical_outcomes_per_arm']==400
    assert result['no_cut_common_outcomes']['sources']==5
    assert len(result['comparisons'])==7
    assert result['bootstrap']['suffix_repeats_independent'] is False
    assert result['bootstrap']['quantile_method']=='linear'


def test_missing_collection_cannot_read_any_outcome(tmp_path,monkeypatch):
    monkeypatch.setattr(audit,'ROOT',tmp_path)
    config=tmp_path/'config.json'
    config.write_text(json.dumps(dict(main_collection=dict(banks={'wave':dict(
        episode_ids=[str(i) for i in range(100)],stage=audit.STAGE,kind='policy5',generation_round=2)}))))
    monkeypatch.setattr(audit.Checks,'seal',lambda *args,**kwargs:pytest.fail('seals/outcomes before completion'))
    with pytest.raises(ValueError,match='100 incomplete'):
        audit.audit(config,'wave','future',tmp_path/'primary/result.json')
    assert not (tmp_path/'policy5_independent_audits/future').exists()


def test_all_collections_still_require_primary_complete(tmp_path,monkeypatch):
    monkeypatch.setattr(audit,'ROOT',tmp_path)
    ids=[str(i) for i in range(100)]
    config=tmp_path/'config.json'
    config.write_text(json.dumps(dict(main_collection=dict(banks={'wave':dict(
        episode_ids=ids,stage=audit.STAGE,kind='policy5',generation_round=2)}))))
    for identity in ids:
        path=tmp_path/'collections'/audit.STAGE/'wave'/identity
        path.mkdir(parents=True);(path/'complete.json').write_text('{}')
    monkeypatch.setattr(audit.Checks,'seal',lambda *args,**kwargs:pytest.fail('outcomes before primary completion'))
    with pytest.raises(ValueError,match='primary audit seal'):
        audit.audit(config,'wave','future',tmp_path/'primary/result.json')
    with pytest.raises(ValueError,match='mandatory'):
        audit.audit(config,'wave','future')


def commands():
    raw=np.zeros((50,4),np.float32);raw[0,0]=1.2
    mask=1-np.abs(np.clip(raw[:10],-1,1).astype(float))>=.05
    plans={name:raw.copy() for name in audit.METHODS[1:]}
    for name,sign in [('velocity',1),('direct',-1),('post',1)]:
        plans[name][:10][mask]=.01*sign
    directions=dict(raw_a0=raw.copy(),critic_a0=np.clip(raw,-1,1),
        critic_candidates=np.stack([np.clip(plans[n],-1,1) for n in audit.METHODS[1:]]))
    formal=dict(raw_a0=raw.copy(),mask=mask)
    matching=dict(tolerance=1e-6,boundary_clearance=.05,xyz_rms=.05,gripper_rms=.1,xyz_linf=.15,gripper_linf=.4)
    return plans,directions,formal,matching


def test_final_raw_rms_and_alias_groups():
    result=audit.command_diagnostics(*commands())
    assert result['status']=='passed' and result['raw_distinct_groups']==3
    assert result['modifiable_coordinates']==39
    assert result['methods']['post']['raw_alias_of']=='velocity'
    assert result['methods']['velocity']['xyz_rms']==result['methods']['direct']['xyz_rms']
    assert result['methods']['alarm_replan10']['xyz_rms']==0


@pytest.mark.parametrize('change,match',[('tail','tail'),('mask','masked'),('critic','mapping'),('rms','not matched')])
def test_raw_mismatches_rejected(change,match):
    plans,directions,formal,matching=commands()
    if change=='tail':plans['velocity'][20,0]=.1
    elif change=='mask':plans['velocity'][0,0]=1.1
    elif change=='critic':directions['critic_a0'][2,0]=.2
    else:plans['velocity'][1,0]=.02
    if change!='critic':
        directions['critic_candidates']=np.stack([np.clip(plans[n],-1,1) for n in audit.METHODS[1:]])
    with pytest.raises(ValueError,match=match):
        audit.command_diagnostics(plans,directions,formal,matching)


def test_stage_and_statistics_remain_fixed():
    assert audit.STAGE=='round2_development_policy'
    assert audit.BOOTSTRAP_SEED==2026091622 and audit.BOOTSTRAP_DRAWS==10000
    assert audit.PAIRS==((1,0),(2,1),(3,1),(4,1),(2,0),(3,0),(4,0))
