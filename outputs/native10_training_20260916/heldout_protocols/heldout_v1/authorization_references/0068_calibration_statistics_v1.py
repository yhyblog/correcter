"""Pure CPU calibration summaries and an unsealed global-selection proposal.

The caller must first verify all physical branch/source/resolution/scene seals,
the paired suffix identities, and the attempt ledger.  The records below carry
that audit's explicit completion declarations; this function is not a substitute
for the artifact audit.  It performs no I/O, model computation, or stage release.

Each record has planned_slot_id, resolved_episode_id, task, scene_fingerprint,
status='complete', artifact_audit_status=scene_isolation_status='passed', no_cut,
and the original resolved resolution (including ordered_rejections).  A cut
requires outcomes={method: [bool, bool]}; a no-cut source requires common_outcome
bool and may omit outcomes.  If supplied, its outcomes must all equal the common
outcome.  Missing/failed/exhausted records cannot become zero-difference sources.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json

import numpy as np

from .protocol import TASKS, canonical_hash, validate_manifest


DECISION_SHA256 = 'bb8e6c7f7eb145337b25ba6c859bf456754eead33062989aefff0d06c3314fd8'
METHODS = ('continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post')
COMPARISONS = ((1, 0), (2, 1), (3, 1), (4, 1), (2, 0), (3, 0), (4, 0))
REPLICATES = 2
BOOTSTRAP_DRAWS = 10000
BOOTSTRAP_SEED = 2026091622
REGISTERED_PRIMARY_IDS = tuple(f'{TASKS[i % 5]}__{start+i}'
                               for start in (2026111700, 2026111800) for i in range(50))
REGISTERED_PRIMARY_IDS_SHA256 = canonical_hash(list(REGISTERED_PRIMARY_IDS))
FIXED_CRITIC = dict(path='A', step=4000, members=4,
    selected_seal_sha256='f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a')
GLOBAL_SELECTION_RULE = dict(primary_method='post', fallback_method='alarm_replan10',
    rule='mean_paired_post_minus_replan_strictly_positive', source_denominator=100,
    replicates=2, no_cut_difference=0)
GLOBAL_SELECTION_RULE_JSON = json.dumps(GLOBAL_SELECTION_RULE, sort_keys=True, separators=(',', ':'))


class CalibrationStatisticsError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise CalibrationStatisticsError(message)


def _registration(manifest, primary_ids, expected_sha256, replacement_candidates):
    lookup = validate_manifest(manifest)
    ids = list(primary_ids)
    _require(ids == list(REGISTERED_PRIMARY_IDS) and len(set(ids)) == 100,
             'Exactly the original 100 ordered calibration primary IDs are required')
    _require(expected_sha256 == REGISTERED_PRIMARY_IDS_SHA256 == canonical_hash(ids),
             'Original primary-ID SHA binding differs')
    registered = [row['episode_id'] for row in manifest
                  if row['split'] == 'calibration' and not row.get('replacement_of')]
    _require(registered == ids, 'Calibration denominator differs from the original primary registration')
    _require(dict(Counter(lookup[key]['task'] for key in ids)) == {task: 20 for task in TASKS},
             'Every registered task requires exactly 20 calibration primaries')
    chains = {}
    for identity in ids:
        primary = lookup[identity]
        _require(primary.get('source_horizon') == 10 and primary.get('cut_rule') == {'kind': 'first_alarm'},
                 'Calibration requires native10 and the first eligible alarm')
        backups = sorted((row for row in manifest if row.get('replacement_of') == identity),
                         key=lambda row: row.get('replacement_ordinal', -1))
        _require([row.get('replacement_ordinal') for row in backups] == list(range(1, len(backups)+1)),
                 'Backup ordinals must be complete, unique and ordered')
        _require(all(row['split'] == 'calibration' and row['task'] == primary['task']
                     and row.get('source_horizon') == 10 and row.get('cut_rule') == {'kind': 'first_alarm'}
                     for row in backups), 'Backups must retain the primary task/split/cut protocol')
        backup_ids = [row['episode_id'] for row in backups]
        if replacement_candidates is not None:
            _require(replacement_candidates.get(identity, []) == backup_ids,
                     'Backup mapping differs from the approved manifest order')
        chains[identity] = [identity] + backup_ids
    return lookup, ids, chains


def _outcomes(record):
    no_cut = record.get('no_cut')
    _require(type(no_cut) is bool, 'Every source must explicitly declare its no-cut status')
    if no_cut:
        _require(type(record.get('common_outcome')) is bool,
                 'No-alarm sources require a known common full-episode outcome')
        broadcast = np.full((5, REPLICATES), record['common_outcome'], dtype=bool)
        if 'outcomes' not in record:
            return broadcast
    else:
        _require(record.get('common_outcome') is None,
                 'A cut source cannot substitute a common outcome for physical branches')
    values = record.get('outcomes')
    _require(isinstance(values, dict) and set(values) == set(METHODS),
             'Exactly five physical arms are required; no sixth selected-policy arm')
    rows = []
    for name in METHODS:
        value = np.asarray(values[name])
        _require(value.shape == (REPLICATES,) and value.dtype == np.dtype('bool'),
                 'Every arm must contain exactly two observed boolean paired outcomes')
        rows.append(value)
    labels = np.stack(rows)
    if no_cut:
        _require(np.array_equal(labels, broadcast), 'No-alarm outcomes must be shared by every arm/repeat')
    return labels


def _records(lookup, ids, chains, source_records):
    _require(isinstance(source_records, (list, tuple)) and len(source_records) == 100,
             'All 100 primary slots must be technically complete before proposing a selection')
    keyed = {}
    for row in source_records:
        identity = row.get('planned_slot_id')
        _require(identity in ids and identity not in keyed, 'Duplicate or unregistered logical primary slot')
        keyed[identity] = row
    _require(set(keyed) == set(ids), 'Missing calibration primaries cannot be filled with zero')
    labels, normalized, actual_ids, scenes = [], [], set(), set()
    for identity in ids:
        record = keyed[identity]
        _require(record.get('status') == 'complete'
                 and record.get('artifact_audit_status') == 'passed'
                 and record.get('scene_isolation_status') == 'passed',
                 'Technical incompleteness or unverified scene/source artifacts block selection')
        actual = record.get('resolved_episode_id')
        _require(actual in chains[identity] and actual not in actual_ids,
                 'Resolved source must be a distinct approved member of its primary backup chain')
        actual_ids.add(actual); case = lookup[actual]
        _require(record.get('task') == case['task'], 'Record task differs from its resolved source')
        scene = record.get('scene_fingerprint')
        _require(isinstance(scene, str) and len(scene) == 64 and all(c in '0123456789abcdef' for c in scene),
                 'An audited physical scene fingerprint is required')
        scene_key = (case['task'], scene)
        _require(scene_key not in scenes, 'Duplicate physical initial state within a task')
        scenes.add(scene_key)
        resolution = record.get('resolution', {})
        _require(resolution.get('status') == 'resolved'
                 and resolution.get('planned_slot_id') == identity
                 and resolution.get('resolved_episode_id') == actual
                 and resolution.get('substitution_after_outcome_forbidden') is True,
                 'Replacement resolution is incomplete or differs from logical/actual source IDs')
        rejected = resolution.get('ordered_rejections')
        predecessors = chains[identity][:chains[identity].index(actual)]
        _require(isinstance(rejected, list) and [row.get('episode_id') for row in rejected] == predecessors,
                 'Replacement chain was skipped, reordered or left incomplete')
        _require(all(row.get('reason') in ('initialization_failed', 'duplicate_initial_scene')
                     and row.get('before_first_action') is True for row in rejected),
                 'Replacement is allowed only for approved pre-action technical reasons')
        outcome = _outcomes(record)
        labels.append(outcome)
        normalized.append(dict(planned_slot_id=identity, resolved_episode_id=actual, task=case['task'],
            scene_fingerprint=scene, no_cut=record['no_cut'], resolution=deepcopy(resolution),
            outcomes={name: outcome[index].tolist() for index, name in enumerate(METHODS)}))
    return np.stack(labels), normalized


def _comparison(candidate, baseline, bootstrap=None):
    delta = (candidate.astype(np.int8)-baseline.astype(np.int8)).mean(axis=1)
    result = dict(gain=float(delta.mean()), rescues=int(np.count_nonzero(candidate & ~baseline)),
        harms=int(np.count_nonzero(~candidate & baseline)),
        positive_sources=int(np.count_nonzero(delta > 0)), negative_sources=int(np.count_nonzero(delta < 0)),
        zero_sources=int(np.count_nonzero(delta == 0)))
    if bootstrap is not None:
        result['source_95ci'] = np.quantile(delta[bootstrap].mean(axis=1), [.025, .975], method='linear').tolist()
    return result


def summarize_calibration(manifest, primary_ids, source_records, *, expected_primary_ids_sha256,
                          replacement_candidates=None):
    """Validate a completed cohort and return descriptive statistics plus proposal.

    The global option depends only on the integer post-minus-replan success sum;
    neither CI nor Q participates.  Actual selection sealing and heldout release
    remain separate analysis-authorized actions, with no writer in this module.
    """
    lookup, ids, chains = _registration(manifest, primary_ids, expected_primary_ids_sha256,
                                        replacement_candidates)
    y, rows = _records(lookup, ids, chains, source_records)
    tasks = np.asarray([row['task'] for row in rows]); no_cut = np.asarray([row['no_cut'] for row in rows])
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    bootstrap = np.concatenate([rng.choice(np.flatnonzero(tasks == task), size=(BOOTSTRAP_DRAWS, 20),
                                           replace=True) for task in TASKS], axis=1)
    def group(mask, *, intervals=False):
        data = y[mask]; count = len(data)
        if count == 0:
            return dict(sources=0, logical_outcomes_per_arm=0, success_counts=None,
                        success_rates=None, comparisons=None)
        counts = data.sum(axis=(0, 2), dtype=np.int64)
        return dict(sources=count, logical_outcomes_per_arm=count*REPLICATES,
            success_counts=dict(zip(METHODS, counts.tolist())),
            success_rates=dict(zip(METHODS, (counts/(count*REPLICATES)).tolist())),
            comparisons={METHODS[a]+'_minus_'+METHODS[b]:_comparison(data[:, a], data[:, b],
                bootstrap if intervals else None) for a, b in COMPARISONS})
    net = int(y[:, 4].sum(dtype=np.int64)-y[:, 1].sum(dtype=np.int64))
    selected = 'post' if net > 0 else 'alarm_replan10'
    proposal = dict(status='proposal_only', method=selected, post_enabled_on_alarm=net > 0,
        paired_success_difference=net, mean_source_post_minus_replan=net/(100*REPLICATES),
        rule=deepcopy(GLOBAL_SELECTION_RULE), ci_used=False, q_used=False,
        criterion='strictly positive mean; exact zero disables correction',
        selection_seal_created=False, selection_release_authorized=False,
        requires_subsequent_analysis_permission_to_seal=True)
    for index, row in enumerate(rows):
        row['post_minus_replan_mean'] = float((y[index, 4].astype(int)-y[index, 1].astype(int)).mean())
    return dict(schema='native10_calibration_statistics_v1', status='complete_statistics_proposal_only',
        decision_sha256=DECISION_SHA256, fixed_critic=deepcopy(FIXED_CRITIC), methods=list(METHODS),
        source_denominator=100, replicates=REPLICATES, logical_outcomes_per_arm=200,
        physical_arms=5, physical_branch_count=int((~no_cut).sum())*5*REPLICATES,
        primary_ids=ids, primary_ids_sha256=canonical_hash(ids),
        manifest_sha256=canonical_hash(manifest), normalized_input_sha256=canonical_hash(rows),
        resolved_source_ids=[row['resolved_episode_id'] for row in rows],
        replacement_source_count=sum(row['planned_slot_id'] != row['resolved_episode_id'] for row in rows),
        overall=group(np.ones(100, dtype=bool), intervals=True),
        per_task={task: group(tasks == task) for task in TASKS},
        alarm_conditioned=group(~no_cut), no_cut_common_outcomes=group(no_cut),
        per_source=rows, selection_proposal=proposal,
        bootstrap=dict(draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED, task_order=list(TASKS),
            source_order=ids, unit='whole logical primary source within task', quantile_method='linear',
            interval='percentile95', multiplicity_adjusted=False, suffixes_are_independent_sources=False,
            use='descriptive calibration only; not selection or reliable per-source uncertainty'),
        per_source_confidence_intervals=False, independent_validation_success=False,
        technical_missing=0, heldout_reads=0, heldout_mutations=0, selection_seals_written=0,
        model_calls=0, simulator_calls=0, optimizer_updates=0,
        limitations=['Caller must verify sealed physical artifacts, paired suffixes, scenes and ledger before this pure function.',
            'Two repeats per source are low-information measurements, not individual-source confidence intervals.',
            'These seven unadjusted source-bootstrap intervals are descriptive and never select a winner.',
            'Only the fixed global post-versus-replan option is proposed; no Q gate, per-task gate or sixth physical arm.',
            'Calibration proposal does not release selection sealing or heldout execution.'])
