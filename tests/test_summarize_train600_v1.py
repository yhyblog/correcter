from copy import deepcopy
import numpy as np
import pytest
from experiments.native10_training_20260916 import summarize_train600_v1 as diag


def fixture():
    rows=[dict(episode_id=f'e{r}',task='task',round=r,cut_rule={'kind':'first_alarm'}) for r in (1,2)]
    names=['a0','xp','xn','gp','gn','hp','hn','fp','fn','velocity','direct','post','reverse_post']
    records=[dict(episode_id=f'e{r}',candidate_metadata=dict(clearance_mask=np.ones((10,4),bool).tolist(),
        channels={k:{'fallback':False} for k in ('xyz','gripper')}),cut_selection=dict(requested_cut=None,
        actual_cut=15,selection_kind='alarm',selection_reason='first_legal_alarm')) for r in (1,2)]
    aliases=np.stack([np.arange(13),np.zeros(13,dtype=int)])
    raw=np.zeros((2,13,10,4),np.float32)
    raw[0]=np.arange(13,dtype=np.float32)[:,None,None]/20
    outcomes=np.zeros((2,13,4),bool);outcomes[0,:,0]=True
    outcomes[0,1]=[False,True,False,False];outcomes[0,2]=True;outcomes[0,3]=False
    a=dict(raw_actions=raw,outcomes=outcomes,control_outcomes=np.zeros((2,4),bool),
        candidate_weights=np.stack([np.ones(13),np.full(13,1/13)]),
        gain_weights=np.stack([np.r_[0,np.ones(12)],np.zeros(13)]),
        pair_weights=np.stack([np.ones(5),np.zeros(5)]),alias_indices=aliases,task=np.array(['task','task']))
    return rows,dict(records=records,candidate_order=names),a


def test_whole_sources_alias_groups_and_paired_vs_mean_are_distinct():
    result=diag.build_analysis(*fixture());total=result['combined']['total'];info=total['information']
    assert total['sources']==2 and total['arms']['a0']['slots']==8
    assert info['unique_raw_groups']==14 and info['nonbase_unique_groups']==12
    assert (info['gain_mean_positive_groups'],info['gain_mean_negative_groups'],info['gain_mean_zero_groups'])==(1,1,10)
    assert info['both_candidate_mean_benefit_and_harm']==1
    assert total['correction_vs_a0']['xp']['rescues']==1
    assert total['correction_vs_a0']['xp']['harms']==1
    assert total['correction_vs_a0']['xp']['net_gain_pp']==0
    assert info['unique_direction_any_mean_difference']==1
    assert result['round1']['total']['correction_vs_a0']['xn']['source_ci95_pp']==[75,75]
    assert sum(x['sources'] for x in result['combined']['cut_cross_counts'])==2


def test_alias_outcome_mismatch_blocks():
    rows,metadata,arrays=fixture();arrays['outcomes'][1,3,0]=True
    with pytest.raises(AssertionError):diag.build_analysis(rows,metadata,arrays)


def test_full_regression_checks_every_nested_field():
    a={'arms':{'v':{'ci':[1,2],'sources':300}},'source':[{'id':'a'}]};b=deepcopy(a)
    b['new']=True;diag.subset_equal(a,b)
    b['arms']['v']['ci'][1]=3
    with pytest.raises(AssertionError,match='ci'):diag.subset_equal(a,b)


def test_both_zero_channels_and_directional_aliases_preserved():
    rows,metadata,arrays=fixture();metadata['records'][1]['candidate_metadata']['clearance_mask']=np.zeros((10,4),bool).tolist()
    result=diag.build_analysis(rows,metadata,arrays)
    s=result['round2']['per_source'][0]
    assert s['zero_xyz'] and s['zero_gripper'] and s['unique_direction_pairs']==0
    assert result['round2']['total']['direction_positive_vs_negative']['xp__minus__xn']['raw_distinct_sources']==0
