"""Synthetic arithmetic and complete-cohort gates; no real source reads."""
from copy import deepcopy
import json

import numpy as np
import pytest

from . import diagnostics as d, protocol


def inputs(method='solo_post'):
    raw = np.zeros((50, 4), np.float32)
    plan = raw.copy(); plan[:10, :3] = .04; plan[:10, 3] = .08
    delta = plan[:10].astype(float)
    saved = dict(raw_a0=raw, raw_plan=plan, mask=np.ones((10, 4), bool))
    groups = {g: dict(achieved_target=r, zero_group=False) for g, r in [('xyz', .04), ('gripper', .08)]}
    meta = dict(matching=dict(groups=groups), predictions={method:dict(mean_gain=.1)},
        actual_policy_calls=1 if method == 'solo_post' else 2,
        includes_own_a0_generation=True, cached_a0_used=False, restore_included=False,
        model_loading_included=False, full_entry_seconds=3., diagnostic_scoring_included=True,
        component_seconds=dict(base_wall_seconds=1., matching_seconds=.1))
    full = d.FULL[method]
    old = {full+'_matched_actual_delta': delta/2}
    oldgen = dict(matching=dict(groups={g:dict(achieved_target=v['achieved_target']/2, zero_group=False)
        for g,v in groups.items()}), bank_predictions={full:dict(mean_gain=.05)})
    outcomes = {method:[True,True,False,False], full:[True,False,False,False],
        'alarm_replan10':[False,False,False,False]}
    return method, saved, meta, old, oldgen, outcomes, protocol.MATCHING


@pytest.mark.parametrize('method', ['solo_post', 'solo_direct', 'solo_velocity'])
def test_actual_command_math_q_and_independent_entry_cost(method):
    result = d.method_diagnostic(*inputs(method))
    assert result['groups']['xyz']['new_over_old_rms'] == 2
    assert result['groups']['gripper']['new_over_old_rms'] == 2
    assert result['groups']['xyz']['actual_delta_angle_degrees'] == pytest.approx(0, abs=1e-5)
    assert result['groups']['xyz']['shared_capacity_constraint_released']
    assert result['actual_solo_minus_replan'] == .5 and result['actual_solo_minus_old_matched'] == .25
    assert result['predicted_solo_minus_old_matched'] == .05
    assert result['cost']['actual_policy_calls'] == (1 if method == 'solo_post' else 2)
    assert result['cost']['full_entry_seconds'] == 3 and result['cost']['own_a0_seconds'] == 1
    assert result['cost']['includes_own_a0_generation'] and not result['cost']['cached_a0_used']
    args = list(inputs(method)); args[2]['cached_a0_used'] = True
    with pytest.raises(ValueError, match='own a0'): d.method_diagnostic(*args)


def test_old_zero_recovery_and_new_zero_keep_undefined_values():
    args = list(inputs()); args[3]['post_matched_actual_delta'][:] = 0
    for group in args[4]['matching']['groups'].values(): group.update(achieved_target=0., zero_group=True)
    result = d.method_diagnostic(*args)
    assert result['groups']['xyz']['old_zero_recovered']
    assert result['groups']['xyz']['new_over_old_rms'] is None
    assert result['groups']['xyz']['actual_delta_angle_degrees'] is None
    args[1]['raw_plan'][:] = 0
    result = d.method_diagnostic(*args)
    assert result['groups']['xyz']['new_actual_zero'] and not result['groups']['xyz']['old_zero_recovered']
    assert result['whole_actual_delta_angle_degrees'] is None


def test_correlations_are_finite_descriptions_with_ties_and_constant_guard():
    got = d.association([0,0,1,np.nan], [0,0,2,1])
    assert got['pairs'] == 3 and got['excluded_nonfinite'] == 1
    assert got['spearman_average_ties'] == pytest.approx(1)
    assert got['descriptive_only'] and not got['q_acceptance_rule_added']
    constant = d.association([1,1], [0,1])
    assert constant['pearson'] is None and constant['spearman_average_ties'] is None


def test_aggregate_preserves_method_cost_and_null_ratio_counts():
    row = dict(methods={m:d.method_diagnostic(*inputs(m)) for m in d.SOLO_METHODS})
    got = d.aggregate_sources([row])
    assert got['solo_post']['actual_policy_calls']['mean'] == 1
    assert got['solo_direct']['actual_policy_calls']['mean'] == 2
    assert got['solo_velocity']['full_entry_seconds_including_own_a0']['mean'] == 3
    assert not got['solo_post']['amortized_shared_a0_cost_used']
    assert got['solo_post']['groups']['xyz']['ratio_undefined_old_zero'] == 0


def test_read_requires_prior_audit_sha_and_stale_files_fail(tmp_path):
    p = tmp_path/'meta.json'; p.write_text(json.dumps(dict(cost=1)))
    reader = d.Reader([dict(path=str(p), sha256=d.storage.sha256(p))])
    assert reader.json(p) == dict(cost=1)
    with pytest.raises(ValueError, match='not covered'): reader.json(tmp_path/'unregistered.json')
    p.write_text(json.dumps(dict(cost=2)))
    with pytest.raises(ValueError): reader.json(p)


def test_preflight_and_partial_formal_block_before_reading(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Incomplete audit must not read metadata or outcomes')
    monkeypatch.setattr(d, 'Reader', forbidden)
    for stage in (protocol.PREFLIGHT, protocol.FORMAL):
        with pytest.raises(ValueError, match='full formal audit'):
            d.summarize({}, dict(status='passed', stage=stage, completed_sources=99))
