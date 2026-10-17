"""CPU synthetic statistics and arithmetic artifact fixtures only; no real env."""
from copy import deepcopy

import numpy as np
import pytest

from . import main_progress_audit as audit, main_runner, storage
from .protocol import pending_protocol, ProtocolError
from .test_main_collection import setup, approve
from .test_artifact_loader import collected


def _snapshot(ids, completed):
    return dict(primary_ids=ids, resolved={key:{} for key in completed},operational={},artifacts={})


def test_pending_gate_before_artifacts_or_snapshot_access(monkeypatch):
    cfg=pending_protocol();cfg['main_collection']={'banks':{'test':dict(kind='labels13',stage='collect',episode_ids=[])}}
    monkeypatch.setattr(audit.loader,'_ledger_snapshot',lambda:pytest.fail('Pending stage touched ledger'))
    with pytest.raises(ProtocolError):audit.progress(cfg,'test')


def test_minimum_threshold_cannot_be_lowered_and_fast_finish_set_is_not_selected(monkeypatch):
    ids=[str(i) for i in range(70)]
    monkeypatch.setattr(audit,'progress',lambda *args:_snapshot(ids,ids[1:51]))
    monkeypatch.setattr(audit,'audit_one',lambda *args:pytest.fail('Read scientific outcomes before prefix50'))
    config={'analysis_approval':{'protocol_sha256':'0'*64}}
    result=audit.run(config)
    assert not result['threshold_ready'] and result['scientific_summary'] is None
    assert not result['scientific_summary_emitted']
    with pytest.raises(ValueError,match='at least50'):audit.run(config,min_train=49)


def test_fixed_prefix_and_progress_only_never_choose_completion_order(monkeypatch):
    ids=[str(i) for i in range(70)]
    monkeypatch.setattr(audit,'progress',lambda *args:_snapshot(ids,list(reversed(ids))))
    called=[]
    def one(key,*args):called.append(key);return {'attempts':[int(key)+1]}
    monkeypatch.setattr(audit,'audit_one',one)
    monkeypatch.setattr(audit,'summarize',lambda groups:{'n':len(groups),'ranking_or_winner_selected':False})
    config={'analysis_approval':{'protocol_sha256':'0'*64}}
    result=audit.run(config,progress_only=True)
    assert result['threshold_ready'] and not called and not result['scientific_summary_emitted']
    result=audit.run(config)
    assert called==ids[:50] and result['scientific_summary']['n']==50


def test_mixed_registered_bank_filters_development_before_opening_its_artifacts(collected,monkeypatch):
    config,case,collector,document,ready=collected
    main_runner.resolve_slot(collector,case)
    dev=deepcopy(case);dev.update(episode_id='disassemble-v3__9999',case_id='disassemble-v3__9999',env_seed=9999,split='development',round=None)
    config['episode_manifest'].append(dev)
    config['main_collection']['banks']['labels_round1']['episode_ids'].insert(0,dev['episode_id'])
    approve(config,document,ready)
    # Existing synthetic seals bind the earlier capture protocol explicitly.
    import json
    original=json.loads((storage.ROOT/'sources'/case['case_id']/'complete.json').read_text())['protocol_sha256']
    config['main_collection']['banks']['labels_round1']['bank_protocol_sha256']=original
    approve(config,document,ready)
    real= audit.loader._sealed
    def checked(path,*args):
        assert dev['episode_id'] not in str(path)
        return real(path,*args)
    monkeypatch.setattr(audit.loader,'_sealed',checked)
    snapshot=audit.progress(config,'labels_round1')
    assert snapshot['primary_ids']==[case['episode_id']]
    assert snapshot['operational']['sealed_completed_slots']==1
    assert snapshot['operational']['branch_seals']==56
    assert audit.run(config,'labels_round1')['scientific_summary'] is None


def test_complete_artifact_chain_pairing_and_raw_stats_use_cpu_stub_only(collected):
    config,case,collector,_,_=collected
    main_runner.resolve_slot(collector,case)
    snapshot=audit.progress(config,'labels_round1')
    group=audit.audit_one(case['episode_id'],config,'labels_round1',snapshot)
    result=audit.summarize([group])
    assert len(set(group['attempts']))==58
    assert result['cohort_primary_slots']==1 and result['reached_legal_cuts']==1
    assert result['cost']['actual_branches']==56
    assert result['unique_task_scene_fingerprints']==1
    assert result['per_source'][0]['raw_critic_delta_max_error']<=1e-6
    assert result['ranking_or_winner_selected'] is False


def synthetic_group(index,no_cut=False):
    outcome=np.zeros((13,4),np.bool_)
    outcome[0]=[False,False,True,True]
    outcome[1]=[True,True,False,True] # 2rescue/1harm versus a0
    values=dict(outcomes=outcome,control_outcomes=np.zeros(4,np.bool_),control_valid=np.ones(4,np.bool_),
        raw_actions=np.zeros((13,10,4),np.float32),actions=np.zeros((13,10,4),np.float32),group_ids=np.arange(13))
    return dict(primary_id=f'primary{index}',case=dict(episode_id=f'actual{index}',task='test',cut_rule={'kind':'scheduled','step':15}),
        source=dict(requested_cut=15,actual_cut=None if no_cut else 15,selection_category='no_cut' if no_cut else 'scheduled',
                    selection_reason='synthetic',scene_fingerprint=str(index)),
        packed=dict(arrays=None if no_cut else values,metadata=dict(native10_outcome=True)),
        candidate_metadata=dict(clearance_mask=np.ones((10,4),bool),channels={'xyz':{'fallback':False},'gripper':{'fallback':True}}),
        bank_generation={'generation_wall_seconds':1.},branch_rows=[],attempts=[],rejections=[])


def test_known_no_cut_remains_in_full_denominator_and_information_is_conditional():
    groups=[synthetic_group(i,no_cut=i>0) for i in range(50)]
    result=audit.summarize(groups)
    full=result['full_planned_denominator']['candidates_vs_a0']['xyz_positive']
    conditional=result['conditional_legal_cut_denominator']['candidates_vs_a0']['xyz_positive']
    assert full['logical_pairs']==200 and full['rescues']==2 and full['harms']==1
    assert full['net_gain']==pytest.approx(1/200) and conditional['net_gain']==pytest.approx(1/4)
    assert full['positive_sources']==1 and full['zero_sources']==49
    assert result['known_no_cut']==49 and result['candidate_information']['sources']==1
    assert result['candidate_information']['channel_fallback_sources']=={'xyz':0,'gripper':1}
    assert result['candidate_information']['informative_mean_labels']==1
    assert result['ranking_or_winner_selected'] is False
    comparisons=result['full_planned_denominator']
    total=comparisons['candidates_vs_continue_native10']['xyz_positive']
    interruption=comparisons['replan_vs_continue_native10']
    assert interruption['rescues']==2 and interruption['harms']==0
    assert total['rescues']==3 and total['harms']==0
    assert total['rescues']!=interruption['rescues']+full['rescues']
    assert total['harms']!=interruption['harms']+full['harms']
    assert total['net_gain']==pytest.approx(interruption['net_gain']+full['net_gain'])
    assert all(abs(value)<1e-12 for value in comparisons['i_a_t_decomposition']['mean_identity_error'].values())
    reached=result['per_source'][0]
    assert reached['paired_outcomes']['xyz_positive']==[True,True,False,True]
    assert reached['paired_outcomes']['continue_native10']==[False]*4
    assert reached['success_means']['xyz_positive']==.75
    assert reached['outcome_origin']=='physical_paired_branches'
    assert result['per_source'][1]['outcome_origin']=='shared_known_no_cut_episode_outcome'
    assert result['per_source'][1]['paired_outcomes']['continue_native10']==[True]*4


def test_unknown_outcomes_cannot_be_cast_to_success_or_failure():
    group=synthetic_group(0);group['packed']['arrays']['outcomes']=np.full((13,4),-1)
    with pytest.raises(ValueError,match='Unknown labels'):audit.summarize([group])
    group=synthetic_group(0,no_cut=True);group['packed']['metadata']['native10_outcome']=None
    with pytest.raises(ValueError,match='Unknown no-cut'):audit.summarize([group])
    with pytest.raises(ValueError,match='Unknown labels'):
        audit.paired(np.full((1,4),-1),np.zeros((1,4)))
