"""Small synthetic CPU suite; no actual heldout labels, models or environments."""
from copy import deepcopy

import numpy as np
import pytest

from . import heldout_statistics_v1 as stats


@pytest.fixture
def cohort():
    manifest, backups, records = [], [], []
    for index, identity in enumerate(stats.REGISTERED_PRIMARY_IDS):
        task, seed = identity.rsplit('__', 1)
        case = dict(episode_id=identity, case_id=identity, task=task, env_seed=int(seed),
            split='heldout', round=None, source_horizon=10, cut_rule={'kind': 'first_alarm'})
        manifest.append(case)
        for ordinal, backup in enumerate(stats.REGISTERED_REPLACEMENT_CANDIDATES[identity], 1):
            backups.append(dict(case, episode_id=backup, case_id=backup, env_seed=int(backup.rsplit('__', 1)[1]),
                replacement_of=identity, replacement_ordinal=ordinal))
        records.append(dict(planned_slot_id=identity, resolved_episode_id=identity, task=task,
            scene_fingerprint=f'{index:064x}', status='complete', artifact_audit_status='passed',
            scene_isolation_status='passed', no_cut=False, actual_cut=5,
            outcomes={name: [False]*4 for name in stats.METHODS},
            resolution=dict(status='resolved', planned_slot_id=identity, resolved_episode_id=identity,
                substitution_after_outcome_forbidden=True, ordered_rejections=[])))
    return dict(manifest=manifest+backups, primary_ids=list(stats.REGISTERED_PRIMARY_IDS), source_records=records,
        expected_primary_ids_sha256=stats.REGISTERED_PRIMARY_IDS_SHA256,
        replacement_candidates=deepcopy(stats.REGISTERED_REPLACEMENT_CANDIDATES))


def test_registration_constants_and_budget_semantics():
    assert stats.REGISTERED_PRIMARY_IDS_SHA256 == 'f05bbfeb92da78d8fb9242bd28b116cf6f5a4cff252b5ad0487506e0bd108afc'
    assert stats.REGISTERED_REPLACEMENT_CANDIDATES_SHA256 == '6fb70dde59cfa22b496608e4ba7cddf30f387a9b6a7d5e45b5fdb09d0d24e5da'
    assert stats.REPLICATES == 4 and stats.BOOTSTRAP_DRAWS == 10000 and stats.BOOTSTRAP_SEED == 2026091622
    assert stats.PRIMARY_COMPARISON == 'post_minus_alarm_replan10' and len(stats.COMPARISONS) == 7
    assert stats.SOURCE_DENOMINATOR*(1+1+5*stats.REPLICATES) == 2200


def test_five_pp_point_target_is_separate_from_interval_and_no_winner_selection(cohort):
    # Five independent +1 sources give exactly 20 net paired outcomes / 400.
    for row in cohort['source_records'][:5]: row['outcomes']['post'] = [True]*4
    for row in cohort['source_records']: row['outcomes']['direct'] = [True]*4
    result = stats.summarize_heldout(**cohort); main = result['primary_assessment']
    assert main['point_estimate'] == .05 and main['point_estimate_target_met']
    assert main['ci_supports_positive_gain'] == (main['source_95ci'][0] > 0)
    assert not main['true_gain_at_least_target_guaranteed']
    assert result['fixed_method'] == 'post' and 'selection_proposal' not in result
    assert result['primary_comparison'] == stats.PRIMARY_COMPARISON
    assert result['overall']['success_rates']['direct'] == 1
    assert result['model_calls'] == result['simulator_calls'] == result['optimizer_updates'] == 0
    assert result['selection_proposals_written'] == result['selection_seals_written'] == 0
    assert all(group['sources'] == 20 for group in result['per_task'].values())


def test_positive_interval_can_support_less_than_five_pp(cohort):
    # Small gains spread over sources produce positive CI but a <5pp point.
    for row in cohort['source_records'][:19]: row['outcomes']['post'][0] = True
    result = stats.summarize_heldout(**cohort); main = result['primary_assessment']
    assert main['point_estimate'] == .0475 and not main['point_estimate_target_met']
    assert main['ci_supports_positive_gain']


def test_whole_source_bootstrap_exact_reproduction_and_pair_counts(cohort):
    for i, row in enumerate(cohort['source_records']):
        row['outcomes']['post'] = [i % 3 == 0, i % 4 == 0, False, True]
        row['outcomes']['alarm_replan10'] = [False, i % 2 == 0, i % 5 == 0, True]
    result = stats.summarize_heldout(**cohort)
    y = np.array([[r['outcomes'][m] for m in stats.METHODS] for r in cohort['source_records']], bool)
    rng = np.random.default_rng(2026091622)
    indices = np.concatenate([rng.choice(np.arange(k, 100, 5), size=(10000, 20), replace=True)
                              for k in range(5)], axis=1)
    delta = (y[:, 4].astype(int)-y[:, 1].astype(int)).mean(1)
    expected = np.quantile(delta[indices].mean(1), [.025, .975], method='linear').tolist()
    r = result['overall']['comparisons'][stats.PRIMARY_COMPARISON]
    assert r['source_95ci'] == expected
    assert r['rescues'] == int((y[:, 4] & ~y[:, 1]).sum())
    assert r['harms'] == int((~y[:, 4] & y[:, 1]).sum())
    assert r['positive_sources']+r['negative_sources']+r['zero_sources'] == 100
    assert result['bootstrap']['source_order'] == cohort['primary_ids']
    assert not result['bootstrap']['suffixes_are_independent_sources']


def test_no_alarm_keeps_every_source_and_common_known_outcome(cohort):
    for i, row in enumerate(cohort['source_records']):
        row.update(no_cut=True, actual_cut=None, common_outcome=i < 60); row.pop('outcomes')
    result = stats.summarize_heldout(**cohort)
    assert result['source_denominator'] == result['no_cut_common_outcomes']['sources'] == 100
    assert result['logical_outcomes_per_arm'] == 400 and result['physical_branch_count'] == 0
    assert set(result['overall']['success_counts'].values()) == {240}
    assert result['alarm_conditioned']['sources'] == 0
    assert result['primary_assessment']['source_95ci'] == [0., 0.]
    assert not result['primary_assessment']['point_estimate_target_met']
    assert not result['primary_assessment']['ci_supports_positive_gain']


@pytest.mark.parametrize('mutation', ['missing', 'failed', 'unknown_common', 'mixed_common', 'two_repeats',
    'sixth_arm', 'duplicate_scene', 'bad_cut', 'reordered_registration', 'changed_backup'])
def test_incomplete_or_protocol_changed_cohort_rejected(cohort, mutation):
    rows = cohort['source_records']; row = rows[0]
    if mutation == 'missing': rows.pop()
    elif mutation == 'failed': row['artifact_audit_status'] = 'failed'
    elif mutation == 'unknown_common': row.update(no_cut=True, actual_cut=None, common_outcome=None)
    elif mutation == 'mixed_common': row.update(no_cut=True, actual_cut=None, common_outcome=True)
    elif mutation == 'two_repeats': row['outcomes']['post'] = [False]*2
    elif mutation == 'sixth_arm': row['outcomes']['selected_policy'] = [False]*4
    elif mutation == 'duplicate_scene': rows[5]['scene_fingerprint'] = row['scene_fingerprint']
    elif mutation == 'bad_cut': row['actual_cut'] = 10
    elif mutation == 'reordered_registration': cohort['primary_ids'].reverse()
    else: cohort['replacement_candidates'][cohort['primary_ids'][0]].reverse()
    with pytest.raises(ValueError): stats.summarize_heldout(**cohort)


def use_second_backup(cohort):
    row = cohort['source_records'][0]; primary = row['planned_slot_id']
    backups = cohort['replacement_candidates'][primary]
    row['resolved_episode_id'] = row['resolution']['resolved_episode_id'] = backups[1]
    row['resolution']['ordered_rejections'] = [dict(episode_id=identity, reason='initialization_failed',
        before_first_action=True) for identity in [primary, backups[0]]]
    return row


def test_ordered_technical_replacement_preserves_primary_denominator(cohort):
    row = use_second_backup(cohort); row['outcomes']['post'][0] = True
    result = stats.summarize_heldout(**cohort)
    assert result['replacement_source_count'] == 1 and result['source_denominator'] == 100
    assert result['primary_ids'][0] != result['resolved_source_ids'][0]
    assert result['primary_assessment']['point_estimate'] == .0025
    assert result['primary_assessment']['nonpositive_or_crossing_ci_does_not_prove_ineffectiveness']


def test_outcome_based_or_skipped_replacement_rejected(cohort):
    row = use_second_backup(cohort)
    row['resolution']['ordered_rejections'][0]['reason'] = 'failed_episode'
    with pytest.raises(ValueError): stats.summarize_heldout(**cohort)
    row['resolution']['ordered_rejections'][0]['reason'] = 'initialization_failed'
    row['resolution']['ordered_rejections'].pop(0)
    with pytest.raises(ValueError): stats.summarize_heldout(**cohort)
