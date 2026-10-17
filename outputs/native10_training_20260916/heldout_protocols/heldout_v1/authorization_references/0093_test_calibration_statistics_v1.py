"""Synthetic CPU boundaries; no real calibration data, model or simulator."""
from copy import deepcopy

import pytest

from . import calibration_statistics_v1 as stats


@pytest.fixture
def cohort():
    manifest, records = [], []
    for index, identity in enumerate(stats.REGISTERED_PRIMARY_IDS):
        task, seed = identity.rsplit('__', 1)
        manifest.append(dict(episode_id=identity, case_id=identity, task=task, env_seed=int(seed),
            split='calibration', round=None, source_horizon=10, cut_rule={'kind': 'first_alarm'}))
        records.append(dict(planned_slot_id=identity, resolved_episode_id=identity, task=task,
            scene_fingerprint=f'{index:064x}', status='complete', artifact_audit_status='passed',
            scene_isolation_status='passed', no_cut=False,
            outcomes={name: [False, False] for name in stats.METHODS},
            resolution=dict(status='resolved', planned_slot_id=identity, resolved_episode_id=identity,
                substitution_after_outcome_forbidden=True, ordered_rejections=[])))
    return dict(manifest=manifest, primary_ids=list(stats.REGISTERED_PRIMARY_IDS), source_records=records,
                expected_primary_ids_sha256=stats.REGISTERED_PRIMARY_IDS_SHA256)


def test_strict_positive_selects_post_without_q_or_ci_threshold(cohort):
    cohort['source_records'][0]['outcomes']['post'][0] = True
    result = stats.summarize_calibration(**cohort)
    proposal = result['selection_proposal']
    assert proposal['method'] == 'post' and proposal['mean_source_post_minus_replan'] == .005
    assert proposal['status'] == 'proposal_only' and not proposal['ci_used'] and not proposal['q_used']
    assert not proposal['selection_release_authorized'] and not proposal['selection_seal_created']
    comparison = result['overall']['comparisons']['post_minus_alarm_replan10']
    assert comparison['source_95ci'][0] == 0
    assert comparison['rescues'] == 1 and comparison['harms'] == 0
    assert comparison['positive_sources'] == 1 and comparison['zero_sources'] == 99
    assert len(result['overall']['comparisons']) == 7
    assert result['physical_arms'] == 5 and result['logical_outcomes_per_arm'] == 200
    assert not result['per_source_confidence_intervals'] and not result['independent_validation_success']
    assert result['model_calls'] == result['simulator_calls'] == result['optimizer_updates'] == 0


@pytest.mark.parametrize('net', [-1, 0, 1])
def test_exact_zero_and_negative_disable_without_changing_fixed_method(cohort, net):
    records = cohort['source_records']
    records[0]['outcomes']['post'] = [True, False]
    records[1]['outcomes']['alarm_replan10'] = [True, False]
    if net != 0:
        records[2]['outcomes']['post' if net > 0 else 'alarm_replan10'][0] = True
    for row in records:
        row['q'] = {'post': -1000000 if net > 0 else 1000000}
    result = stats.summarize_calibration(**cohort)
    proposal = result['selection_proposal']
    assert proposal['paired_success_difference'] == net
    assert proposal['method'] == ('post' if net > 0 else 'alarm_replan10')
    assert proposal['mean_source_post_minus_replan'] == net/200
    assert result['fixed_critic']['path'] == 'A' and result['fixed_critic']['step'] == 4000


def test_all_no_alarm_keeps_complete_denominator_and_never_fills_missing(cohort):
    for index, row in enumerate(cohort['source_records']):
        row.update(no_cut=True, common_outcome=index < 60)
        row.pop('outcomes')
    result = stats.summarize_calibration(**cohort)
    assert result['selection_proposal']['method'] == 'alarm_replan10'
    assert result['source_denominator'] == result['no_cut_common_outcomes']['sources'] == 100
    assert result['physical_branch_count'] == 0 and result['alarm_conditioned']['sources'] == 0
    assert set(result['overall']['success_counts'].values()) == {120}
    assert all(row['post_minus_replan_mean'] == 0 for row in result['per_source'])


@pytest.mark.parametrize('mutation', ['missing', 'duplicate', 'failed', 'unresolved', 'unaudited',
    'wrong_task', 'wrong_repeat', 'sixth_arm', 'unknown_no_alarm', 'inconsistent_common', 'duplicate_scene'])
def test_incomplete_or_invalid_cohort_blocks_proposal(cohort, mutation):
    records = cohort['source_records']; row = records[0]
    if mutation == 'missing': records.pop()
    elif mutation == 'duplicate': records[-1] = deepcopy(row)
    elif mutation == 'failed': row['status'] = 'failed'
    elif mutation == 'unresolved': row['resolution']['status'] = 'missing_unique_initial_scene'
    elif mutation == 'unaudited': row['artifact_audit_status'] = 'pending'
    elif mutation == 'wrong_task': row['task'] = stats.TASKS[1]
    elif mutation == 'wrong_repeat': row['outcomes']['post'].append(False)
    elif mutation == 'sixth_arm': row['outcomes']['selected_policy'] = [False, False]
    elif mutation == 'unknown_no_alarm': row.update(no_cut=True, common_outcome=None)
    elif mutation == 'inconsistent_common': row.update(no_cut=True, common_outcome=True)
    elif mutation == 'duplicate_scene': records[5]['scene_fingerprint'] = row['scene_fingerprint']
    with pytest.raises(ValueError):
        stats.summarize_calibration(**cohort)


def test_unregistered_primary_order_or_split_cannot_change_denominator(cohort):
    for mutation in ('order', 'hash', 'split'):
        changed = deepcopy(cohort)
        if mutation == 'order': changed['primary_ids'].reverse()
        elif mutation == 'hash': changed['expected_primary_ids_sha256'] = '0'*64
        else: changed['manifest'][0]['split'] = 'heldout'
        with pytest.raises(ValueError):
            stats.summarize_calibration(**changed)


def replacement(cohort):
    primary = cohort['manifest'][0]; row = cohort['source_records'][0]
    backups = []
    for ordinal in (1, 2):
        seed = 2026121400+ordinal-1
        identity = f"{primary['task']}__{seed}"
        cohort['manifest'].append(dict(primary, episode_id=identity, case_id=identity, env_seed=seed,
            replacement_of=primary['episode_id'], replacement_ordinal=ordinal))
        backups.append(identity)
    row['resolved_episode_id'] = backups[1]
    row['resolution']['resolved_episode_id'] = backups[1]
    row['resolution']['ordered_rejections'] = [dict(episode_id=identity,
        reason='duplicate_initial_scene', before_first_action=True) for identity in [primary['episode_id'], backups[0]]]
    cohort['replacement_candidates'] = {primary['episode_id']: backups}
    return row


def test_approved_replacement_retains_logical_primary_denominator(cohort):
    row = replacement(cohort)
    row['outcomes']['post'] = [True, False]
    result = stats.summarize_calibration(**cohort)
    assert result['replacement_source_count'] == 1 and result['source_denominator'] == 100
    assert result['primary_ids'][0] != result['resolved_source_ids'][0]
    assert result['selection_proposal']['mean_source_post_minus_replan'] == .005
    assert result['bootstrap']['source_order'] == cohort['primary_ids']


@pytest.mark.parametrize('invalid', ['skipped', 'after_action', 'outcome_reason', 'mapping'])
def test_invalid_replacement_chain_blocks_selection(cohort, invalid):
    row = replacement(cohort)
    if invalid == 'skipped': row['resolution']['ordered_rejections'].pop(0)
    elif invalid == 'after_action': row['resolution']['ordered_rejections'][0]['before_first_action'] = False
    elif invalid == 'outcome_reason': row['resolution']['ordered_rejections'][0]['reason'] = 'failed_episode'
    else: cohort['replacement_candidates'][cohort['primary_ids'][0]].reverse()
    with pytest.raises(ValueError):
        stats.summarize_calibration(**cohort)


def test_preparation_contract_has_only_the_registered_global_choice():
    assert stats.GLOBAL_SELECTION_RULE == dict(primary_method='post', fallback_method='alarm_replan10',
        rule='mean_paired_post_minus_replan_strictly_positive', source_denominator=100,
        replicates=2, no_cut_difference=0)
    assert stats.BOOTSTRAP_SEED == 2026091622 and stats.BOOTSTRAP_DRAWS == 10000
