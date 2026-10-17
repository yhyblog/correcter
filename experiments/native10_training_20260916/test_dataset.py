"""Synthetic episode/bank fixtures only; no future data, runtime or training."""
from copy import deepcopy
import json

import numpy as np
import pytest

from . import dataset, storage
from .candidates13 import CANDIDATE_ORDER, construct_candidates13
from .dataset import (DatasetError, audit_cut_selection, build_dataset, pack_group, raw_command_sha256,
                      save_new_dataset, load_saved_dataset)
from .protocol import suffix_seed


def fixture(*, seed=91001, split='train', round_id=1, dedup=False):
    episode = dict(episode_id=f'disassemble-v3__{seed}',case_id=f'disassemble-v3__{seed}',
                   task='disassemble-v3',env_seed=seed,split=split,round=round_id,
                   source_horizon=10,cut_rule={'kind':'first_alarm'})
    source = dict(status='complete',case=deepcopy(episode),
                  **{key:episode[key] for key in ('episode_id','task','env_seed','split')},
                  cuts=[5],full_episode_outcome_available=False,success=False,end_reason='selected_cut')
    source.update(requested_cut=None,actual_cut=5,selection_reason='first_legal_alarm',
                  available_legal_cuts=[5],first_legal_alarm_step=5,
                  selection_audit=dict(available_legal_cuts=[5],first_legal_alarm_step=5,
                      priority_order=[5],training_fallback_allowed=split=='train',selection_uses_outcome_labels=False))
    raw = np.full((50,4),.2,np.float32)
    raw[0,3] = 1.4
    raw[30,3] = -1.8
    post = raw.copy()
    post[:10,:3] += np.asarray([.015,-.02,.01],np.float32)
    plans, bank, _ = construct_candidates13(raw,{'velocity':raw.copy(),'direct':post.copy(),'post':post},
                                             np.ones((10,4),np.float32),422,1.)
    observed = {name:np.zeros(shape,dtype=np.bool_ if name.endswith('_mask') else np.float32)
                for name,shape in dataset.STATE_SHAPES.items()}
    observed['history_mask'][:] = True
    observed['proprio_mask'][:] = True
    observed['remaining'] = np.asarray(295/300,np.float32)
    provenance = dict(source_seal_sha256='a'*64,protocol_sha256='b'*64,candidate_bank_sha256='c'*64,
                      model_hashes={'vla':'d'*64,'critic':'e'*64,'D':'f'*64,'G0':'1'*64},
                      suffix_seed_namespace='cpu_dataset_fixture')
    branches = []
    for slot, method in enumerate((*CANDIDATE_ORDER, dataset.CONTROL)):
        if dedup and method != dataset.CONTROL and bank['aliases'][method] != method:
            continue
        canonical_slot = CANDIDATE_ORDER.index(bank['aliases'][method]) if method != dataset.CONTROL else 15
        for repeat in range(4):
            first = 10 if method == dataset.CONTROL else 15
            branches.append(dict(status='complete',method=method,repeat=repeat,
                **{key:episode[key] for key in ('episode_id','task','env_seed','split')},
                **deepcopy(provenance),cut_step=5,budget_attempt=seed*100+slot*4+repeat+1,
                success=bool((canonical_slot+repeat)%2==0),
                command_sha256=raw_command_sha256(plans[method]) if method != dataset.CONTROL else '2'*64,
                paired_suffix_id=f"{episode['episode_id']}:cut5:repeat{repeat}",
                suffix_seeds=[dict(step=first+10*i,decision_index=i,
                    seed=suffix_seed(episode,5,repeat,i,namespace=provenance['suffix_seed_namespace'])) for i in range(2)]))
    return dict(episode=episode,source_summary=source,observed=observed,candidate_plans=plans,
                candidate_metadata=bank,branch_summaries=branches,provenance=provenance)


def test_complete_pack_retains_raw_and_clips_critic_anchor_with_separate_normal_control():
    group = fixture()
    packed = pack_group(**group)
    arrays = packed['arrays']
    assert arrays['actions'].shape == arrays['raw_actions'].shape == (13,10,4)
    assert arrays['outcomes'].shape == (13,4) and arrays['outcomes'].dtype == np.bool_
    assert arrays['raw_actions'][0,0,3] == np.float32(1.4)
    assert arrays['actions'][0,0,3] == 1
    np.testing.assert_array_equal(arrays['actions'],np.clip(arrays['raw_actions'],-1,1))
    assert arrays['outcomes'][0].tolist() == [True,False,True,False]
    assert arrays['control_outcomes'].tolist() == [False,True,False,True]
    assert arrays['control_valid'].all() and packed['metadata']['critic_eligible']
    assert packed['metadata']['candidate_order'][0] == 'a0'


def test_raw_alias_expansion_checks_identity_and_uses_inverse_multiplicity_weights():
    group = fixture(dedup=True)
    before = deepcopy(group)
    packed = pack_group(**group)
    values = packed['arrays']
    ids = values['group_ids']
    assert packed['metadata']['audited_alias_reuse']
    assert len(packed['metadata']['physical_attempt_ids']) == 4*(len(set(ids))+1)
    for identity in set(ids):
        mask = ids == identity
        assert values['candidate_weights'][mask].sum() == pytest.approx(1)
        assert values['gain_weights'][mask].sum() == pytest.approx(0 if identity == 0 else 1)
        assert np.unique(values['physical_attempt_ids'][mask,0]).size == 1
    # XYZ post has no gripper component: pair(xyz+,xyz-) and
    # pair(post,reverse_post) describe the same unordered raw group pair.
    assert values['pair_weights'][0] == values['pair_weights'][4] == .5
    np.testing.assert_array_equal(values['outcomes'][0],values['outcomes'][9])
    for name in CANDIDATE_ORDER:
        assert group['candidate_plans'][name].tobytes() == before['candidate_plans'][name].tobytes()
    assert group['branch_summaries'] == before['branch_summaries']


@pytest.mark.parametrize('field,value', [('model_hashes',{'vla':'0'*64}),('source_seal_sha256','0'*64),
    ('candidate_bank_sha256','0'*64),('protocol_sha256','0'*64),('suffix_seed_namespace','different'),
    ('paired_suffix_id','another_episode:cut5:repeat0'),('cut_step',15),('repeat',4)])
def test_alias_reuse_never_bypasses_state_model_repeat_suffix_provenance(field,value):
    group = fixture(dedup=True)
    group['branch_summaries'][0][field] = value
    with pytest.raises(DatasetError):
        pack_group(**group)


def test_matching_clipped_commands_do_not_authorize_raw_alias_reuse():
    group = fixture(dedup=True)
    group['candidate_plans']['velocity'][0,3] = 1.9
    # A clipped-only alias claim would treat both 1.4 and 1.9 as 1.0.
    group['candidate_metadata']['candidates']['velocity']['command_sha256'] = raw_command_sha256(group['candidate_plans']['velocity'])
    with pytest.raises(DatasetError,match='alias'):
        pack_group(**group)


def test_duplicate_logical_repeat_and_conflicting_identical_commands_are_errors():
    group = fixture()
    group['branch_summaries'].append(deepcopy(group['branch_summaries'][0]))
    with pytest.raises(DatasetError,match='Duplicate logical'):
        pack_group(**group)
    group = fixture()
    branch = next(row for row in group['branch_summaries'] if row['method']=='velocity' and row['repeat']==0)
    branch['success'] = not branch['success']
    with pytest.raises(DatasetError,match='conflicting outcome'):
        pack_group(**group)


def test_saved_suffix_stream_must_match_actual_registered_seed_and_decision_index():
    group = fixture()
    group['branch_summaries'][0]['suffix_seeds'][1]['seed'] += 1
    with pytest.raises(DatasetError,match='suffix stream'):
        pack_group(**group)


def test_missing_repeat_is_unknown_and_never_a_failure_label():
    group = fixture(dedup=True)
    group['branch_summaries'] = [row for row in group['branch_summaries']
                                 if not(row['method']=='random_full_positive' and row['repeat']==3)]
    packet = pack_group(**group)
    assert packet['arrays'] is None and packet['metadata']['status'] == 'incomplete_labels'
    assert packet['metadata']['missing_labels'] == [dict(candidate='random_full_positive',repeat=3,reason='missing_paired_outcome')]
    packed = build_dataset([group['episode']],[group])
    assert packed['arrays']['outcomes'].shape == (0,13,4)
    assert packed['metadata']['planned_episode_count'] == 1
    assert not packed['metadata']['complete_planned_selection_evidence']


def test_explicit_failed_alias_attempt_is_preserved_and_not_silently_filled():
    group = fixture()
    branch = next(row for row in group['branch_summaries'] if row['method']=='velocity' and row['repeat']==0)
    branch.update(status='failed',error='synthetic execution fault')
    branch.pop('success')
    packet = pack_group(**group)
    assert packet['arrays'] is None
    assert dict(candidate='velocity',repeat=0,reason='explicit_failed_attempt') in packet['metadata']['missing_labels']


def test_no_alarm_early_success_failed_and_missing_sources_all_remain_planned():
    groups = [fixture(seed=91001+i) for i in range(4)]
    manifest = [group['episode'] for group in groups]
    no_cut = dict(episode=manifest[1],source_summary=deepcopy(groups[1]['source_summary']))
    no_cut['source_summary'].update(cuts=[],success=True,no_alarm=True,
                                  full_episode_outcome_available=True,end_reason='success',actual_cut=None,
                                  selection_reason='no_legal_cut',available_legal_cuts=[],first_legal_alarm_step=None,
                                  selection_audit=dict(available_legal_cuts=[],first_legal_alarm_step=None,
                                      priority_order=[15,5],training_fallback_allowed=True,selection_uses_outcome_labels=False))
    failed = dict(episode=manifest[2],source_summary=deepcopy(groups[2]['source_summary']))
    failed['source_summary'].update(status='failed',error='synthetic reset fault')
    packed = build_dataset(manifest,[groups[0],no_cut,failed])
    assert packed['metadata']['planned_episode_count'] == 4
    assert packed['metadata']['complete_critic_groups'] == 1
    assert packed['metadata']['status_counts'] == {'complete':1,'no_cut':1,'source_failed':1,'source_missing':1}
    records = packed['metadata']['records']
    assert records[1]['native10_outcome'] is True and not records[1]['critic_eligible']
    assert len(packed['rows']) == 1 and packed['rows'][0] == dict(manifest[0],planned_slot_id=manifest[0]['episode_id'])
    assert packed['arrays']['history'].shape == (1,5,4096)
    assert packed['arrays']['group_ids'].shape == (1,13)
    assert packed['arrays']['remaining'].shape == (1,)


@pytest.mark.parametrize('split',['calibration','heldout','p0'])
def test_protected_split_outcomes_cannot_enter_either_training_or_development(split):
    protected = fixture(split=split)
    with pytest.raises(DatasetError,match='forbidden'):
        pack_group(**protected)
    with pytest.raises(DatasetError,match='Cross-split'):
        build_dataset([protected['episode']],[protected])


def test_whole_episode_split_and_round_leakage_and_duplicate_groups_rejected():
    group = fixture()
    dev = deepcopy(group['episode']);dev['split'] = 'development'
    with pytest.raises(ValueError,match='Duplicate episode'):
        build_dataset([group['episode'],dev],[])
    with pytest.raises(DatasetError,match='Duplicate whole-episode'):
        build_dataset([group['episode']],[group,group])
    round2 = fixture(seed=91002,round_id=2)
    with pytest.raises(DatasetError,match='Cross-split/round'):
        build_dataset([group['episode'],round2['episode']],[round2],rounds=[1])
    changed = deepcopy(group);changed['source_summary']['case']['round'] = 2
    with pytest.raises(DatasetError,match='registration changed'):
        pack_group(**changed)


def test_normal_controls_are_optional_for_fitting_but_missing_blocks_complete_selection_claim():
    group = fixture(split='development',round_id=None)
    group['branch_summaries'] = [row for row in group['branch_summaries'] if row['method'] != dataset.CONTROL]
    packed = build_dataset([group['episode']],[group],purpose='development')
    assert packed['metadata']['complete_critic_groups'] == 1
    assert not packed['arrays']['control_valid'].any()
    assert not packed['metadata']['complete_planned_selection_evidence']


def test_physical_attempt_ids_cannot_be_reassigned_to_other_candidate_or_episode():
    group = fixture()
    group['branch_summaries'][4]['budget_attempt'] = group['branch_summaries'][0]['budget_attempt']
    with pytest.raises(DatasetError,match='Physical attempt reused'):
        pack_group(**group)
    first,second = fixture(),fixture(seed=91002)
    second['branch_summaries'][0]['budget_attempt'] = first['branch_summaries'][0]['budget_attempt']
    with pytest.raises(DatasetError,match='multiple episode'):
        build_dataset([first['episode'],second['episode']],[first,second])


def test_save_exclusively_creates_new_version_under_new_root_and_seals(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'new_workflow')
    group = fixture()
    sources = {'coordination/'+name:'3'*64 for name in dataset.ANALYSIS_SOURCE_NAMES}
    packed = build_dataset([group['episode']],[group],analysis_sources=sources)
    path = save_new_dataset('synthetic_v1',packed)
    assert path == storage.ROOT/'datasets/synthetic_v1'
    assert json.loads((path/'rows.json').read_text()) == packed['rows']
    seal = json.loads((path/'complete.json').read_text())
    assert set(seal['files']) == {'arrays.npz','metadata.json','rows.json'}
    with np.load(path/'arrays.npz',allow_pickle=False) as values:
        assert values['outcomes'].dtype == np.bool_ and values['raw_actions'].shape == (1,13,10,4)
    before = {file.name:file.read_bytes() for file in path.iterdir()}
    with pytest.raises(FileExistsError):
        save_new_dataset('synthetic_v1',packed)
    assert before == {file.name:file.read_bytes() for file in path.iterdir()}
    loaded = load_saved_dataset(path,'train',packed['metadata']['manifest_sha256'])
    assert loaded['verification']['dataset_seal_verified']
    assert not loaded['verification']['upstream_source_bank_branch_ledger_verified']
    np.testing.assert_array_equal(loaded['arrays']['outcomes'],packed['arrays']['outcomes'])
    with pytest.raises(DatasetError,match='purpose/schema/manifest'):
        load_saved_dataset(path,'development',packed['metadata']['manifest_sha256'])
    (path/'rows.json').write_text('[]')
    with pytest.raises(DatasetError,match='failed its seal'):
        load_saved_dataset(path,'train',packed['metadata']['manifest_sha256'])
    with pytest.raises(DatasetError):
        save_new_dataset('../old_archive',packed)


def selection_fixture(*,split='train',kind='scheduled',target=95,available=(5,15,45),alarm=None,actual=45):
    episode=fixture(split=split)['episode']
    episode['cut_rule']={'kind':kind,**({'step':target} if kind=='scheduled' else {})}
    priority=({15:[15,5],45:[45,15,5],95:[95,45,15,5]}[target] if kind=='scheduled'
              else [alarm] if alarm is not None else [15,5] if split=='train' else [])
    reason=('scheduled_target_reached' if kind=='scheduled' and actual==target else
            'scheduled_prior_anchor_fallback' if kind=='scheduled' and actual is not None else
            'first_legal_alarm' if alarm is not None else
            'no_alarm_training_anchor_fallback' if actual is not None else
            'no_legal_cut' if split=='train' else 'no_alarm_policy_common_outcome')
    source=dict(requested_cut=target if kind=='scheduled' else None,actual_cut=actual,
                selection_reason=reason,cuts=[] if actual is None else [actual],
                available_legal_cuts=list(available),first_legal_alarm_step=alarm,
                selection_audit=dict(available_legal_cuts=list(available),first_legal_alarm_step=alarm,
                    priority_order=priority,training_fallback_allowed=split=='train',selection_uses_outcome_labels=False))
    return episode,source


@pytest.mark.parametrize('target,available,actual',[(15,[5],5),(45,[5,15],15),(95,[5,15,45],45),(95,[5],5),(45,[5,15,45],45)])
def test_approved_scheduled_fallback_uses_fixed_priority_not_requested_actual_equality(target,available,actual):
    episode,source=selection_fixture(target=target,available=available,actual=actual)
    result=audit_cut_selection(episode,source)
    assert result['actual_cut']==actual and not result['selection_uses_outcome_or_Q']
    source['success']=True
    source['candidate_Q']=99.
    assert audit_cut_selection(episode,source)==result


def test_no_alarm_fallback_is_training_only_and_priority_cannot_be_changed_by_reason():
    episode,source=selection_fixture(kind='first_alarm',available=[5,15],actual=15)
    assert audit_cut_selection(episode,source)['selection_kind']=='fallback'
    source.update(actual_cut=5,cuts=[5])
    with pytest.raises(DatasetError,match='priority'):
        audit_cut_selection(episode,source)
    episode,source=selection_fixture(split='development',kind='first_alarm',available=[5,15],actual=None)
    assert audit_cut_selection(episode,source)['actual_cut'] is None
    source.update(actual_cut=15,cuts=[15],selection_reason='no_alarm_training_anchor_fallback')
    with pytest.raises(DatasetError,match='priority'):
        audit_cut_selection(episode,source)


def test_cut_reason_and_priority_evidence_are_required_not_just_plausible_actual_step():
    episode,source=selection_fixture()
    source['selection_reason']='chosen_by_success'
    with pytest.raises(DatasetError,match='Selection reason'):
        audit_cut_selection(episode,source)
    episode,source=selection_fixture()
    source['selection_audit']['selection_uses_outcome_labels']=True
    with pytest.raises(DatasetError,match='Selection audit'):
        audit_cut_selection(episode,source)


def test_dataset_cannot_be_saved_without_latest_analysis_source_binding(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'new_workflow')
    group=fixture()
    with pytest.raises(DatasetError,match='latest analysis'):
        save_new_dataset('unbound',build_dataset([group['episode']],[group]))
    assert not storage.ROOT.exists()


def test_registered_backup_resolves_one_primary_slot_without_extra_denominator():
    primary,backup=fixture(),fixture(seed=91009)
    backup['episode']['replacement_of']=primary['episode']['episode_id']
    backup['source_summary']['case']=deepcopy(backup['episode'])
    packed=build_dataset([primary['episode'],backup['episode']],[backup])
    assert packed['metadata']['planned_episode_count']==1
    assert packed['rows'][0]['episode_id']==backup['episode']['episode_id']
    assert packed['rows'][0]['planned_slot_id']==primary['episode']['episode_id']
    assert packed['metadata']['records'][0]['planned_slot_id']==primary['episode']['episode_id']
    with pytest.raises(DatasetError,match='Duplicate whole-episode'):
        build_dataset([primary['episode'],backup['episode']],[primary,backup])
    backup['episode']['split']='development'
    with pytest.raises(DatasetError,match='Backup changed'):
        build_dataset([primary['episode'],backup['episode']],[])
