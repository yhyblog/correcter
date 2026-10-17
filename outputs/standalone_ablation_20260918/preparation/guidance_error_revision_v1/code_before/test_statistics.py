from copy import deepcopy

import numpy as np
import pytest

from . import statistics as stats


@pytest.fixture
def records():
    return [dict(planned_slot_id=identity, resolved_episode_id=identity, task=identity.rsplit('__', 1)[0],
        scene_fingerprint=f'{i:064x}', status='complete', artifact_audit_status='passed', pairing_audit_status='passed',
        no_cut=identity in stats.NO_CUT_IDS, actual_cut=None if identity in stats.NO_CUT_IDS else 5,
        common_outcome=False if identity in stats.NO_CUT_IDS else None,
        outcomes={method: [False]*4 for method in stats.METHODS})
        for i, identity in enumerate(stats.REGISTERED_PRIMARY_IDS)]


def test_full_denominator_provenance_and_no_winner(records):
    for row in records:
        if not row['no_cut']: row['outcomes']['solo_direct'] = [True]*4
    result = stats.summarize(records)
    assert result['source_denominator'] == 100 and result['logical_outcomes_per_arm'] == 400
    assert result['new_physical_branches'] == 1176 and result['no_cut_common_outcomes']['sources'] == 2
    assert result['overall']['success_counts']['solo_direct'] == 392
    assert len(result['common_primary_comparisons']) == 3 and len(result['secondary_comparisons']) == 6
    assert len(result['overall']['comparisons']) == 10 and not result['winner_selected']
    assert not result['new_independent_heldout']
    assert set(result['per_task']) == set(stats.TASKS)
    assert all(row['sources'] == 20 for row in result['per_task'].values())
    assert result['method_provenance']['post'] == 'reused_sealed_control'


def test_common_source_draws_exact_quantiles_and_rescue_harm(records):
    for i, row in enumerate(records):
        if not row['no_cut']:
            row['outcomes']['solo_post'] = [i % 3 == 0, i % 4 == 0, False, True]
            row['outcomes']['alarm_replan10'] = [False, i % 2 == 0, i % 5 == 0, True]
    result = stats.summarize(records)
    y = np.asarray([[row['outcomes'][m] for m in stats.METHODS] for row in records], bool)
    delta = (y[:, 7].astype(int)-y[:, 1].astype(int)).mean(1)
    rng = np.random.default_rng(2026091801)
    draws = np.concatenate([rng.choice(np.arange(k, 100, 5), size=(10000, 20), replace=True) for k in range(5)], 1)
    means = delta[draws].mean(1)
    actual = result['overall']['comparisons']['solo_post_minus_alarm_replan10']
    assert actual['source_95ci'] == np.quantile(means, [.025, .975], method='linear').tolist()
    assert actual['source_bonferroni_98_333333ci'] == np.quantile(means, [.05/6, 1-.05/6], method='linear').tolist()
    assert actual['rescues'] == int((y[:, 7] & ~y[:, 1]).sum())
    assert actual['harms'] == int((~y[:, 7] & y[:, 1]).sum())
    assert actual['positive_sources']+actual['negative_sources']+actual['zero_sources'] == 100
    assert 'source_bonferroni_98_333333ci' not in result['overall']['comparisons']['solo_post_minus_post']
    assert result['bootstrap']['bonferroni_quantiles'] == [.05/6, 1-.05/6]


@pytest.mark.parametrize('change', ['missing', 'duplicate', 'task', 'repeat', 'missing_old', 'unaudited',
    'nonboolean', 'common_changed', 'unknown_common', 'wrong_cut_set', 'duplicate_scene', 'new_primary_order'])
def test_missing_or_changed_protocol_never_becomes_zero(records, change):
    args = {}
    if change == 'missing': records.pop()
    elif change == 'duplicate': records[-1] = deepcopy(records[0])
    elif change == 'task': records[0]['task'] = stats.TASKS[1]
    elif change == 'repeat': records[0]['outcomes']['solo_post'] = [False]*2
    elif change == 'missing_old': records[0]['outcomes'].pop('velocity')
    elif change == 'unaudited': records[0]['pairing_audit_status'] = 'pending'
    elif change == 'nonboolean': records[0]['outcomes']['solo_post'] = [0]*4
    elif change == 'common_changed':
        next(x for x in records if x['no_cut'])['outcomes']['solo_post'][0] = True
    elif change == 'unknown_common': next(x for x in records if x['no_cut'])['common_outcome'] = None
    elif change == 'wrong_cut_set': records[0].update(no_cut=True, actual_cut=None, common_outcome=False)
    elif change == 'duplicate_scene': records[5]['scene_fingerprint'] = records[0]['scene_fingerprint']
    else: args['primary_ids'] = list(reversed(stats.REGISTERED_PRIMARY_IDS))
    with pytest.raises(ValueError): stats.summarize(records, **args)


def test_exact_zero_does_not_select_or_create_a_gate(records):
    out = stats.summarize(records)
    for key in out['common_primary_comparisons']:
        row = out['overall']['comparisons'][key]
        assert row['gain'] == 0 and row['source_bonferroni_98_333333ci'] == [0., 0.]
        assert not row['adjusted_interval_supports_positive_gain']
    assert 'selection_proposal' not in out and out['selection_seals_written'] == 0
