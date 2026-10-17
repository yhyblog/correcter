"""Pure statistics for the fixed, complete native10 heldout cohort.

The caller must audit the physical source/branch/resolution/scene seals, loaded
A4000 identity, paired suffixes and attempt ledger before supplying records.
This module performs no I/O, model computation, selection or stage release.
Only synthetic inputs are used during preparation; a future complete heldout
artifact audit owns permission to read and supply the actual outcomes.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

import numpy as np

from .protocol import TASKS, canonical_hash, validate_manifest


DECISION_SHA256 = '7b50be9baff4a7eca49607bda0a91f7b24e597fb95d65add765803daf70cbf24'
STAGE = 'heldout'
BANK = 'heldout_policy_v1'
METHODS = ('continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post')
COMPARISONS = ((1, 0), (2, 1), (3, 1), (4, 1), (2, 0), (3, 0), (4, 0))
PRIMARY_COMPARISON = 'post_minus_alarm_replan10'
REPLICATES = 4
SOURCE_DENOMINATOR = 100
PRACTICAL_TARGET = .05
BOOTSTRAP_DRAWS = 10000
BOOTSTRAP_SEED = 2026091622
REGISTERED_PRIMARY_IDS = tuple(f'{TASKS[i % 5]}__{start+i}'
    for start in (2026111750, 2026111850) for i in range(50))
REGISTERED_PRIMARY_IDS_SHA256 = canonical_hash(list(REGISTERED_PRIMARY_IDS))
REGISTERED_REPLACEMENT_CANDIDATES = {
    REGISTERED_PRIMARY_IDS[block*50+i]: [f'{TASKS[i % 5]}__{start+2*i+j}' for j in range(2)]
    for block, start in enumerate((2026121500, 2026121700)) for i in range(50)}
REGISTERED_REPLACEMENT_CANDIDATES_SHA256 = canonical_hash(REGISTERED_REPLACEMENT_CANDIDATES)
FIXED_CRITIC = dict(path='A', step=4000, members=4,
    selected_seal_sha256='f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a')


class HeldoutStatisticsError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise HeldoutStatisticsError(message)


def _registration(manifest, primary_ids, expected_sha256, replacement_candidates):
    lookup = validate_manifest(manifest)
    ids = list(primary_ids)
    _require(ids == list(REGISTERED_PRIMARY_IDS), 'Exactly the original 100 ordered heldout IDs are required')
    _require(expected_sha256 == REGISTERED_PRIMARY_IDS_SHA256 == canonical_hash(ids),
             'Original heldout primary-ID SHA binding differs')
    registered = [row['episode_id'] for row in manifest
                  if row['split'] == STAGE and not row.get('replacement_of')]
    _require(registered == ids, 'Heldout cannot pool calibration or change the primary denominator')
    _require(dict(Counter(lookup[key]['task'] for key in ids)) == {task: 20 for task in TASKS},
             'Each heldout task requires its original 20 primary slots')
    all_backups = [row for row in manifest if row['split'] == STAGE and row.get('replacement_of')]
    _require(len(all_backups) == 200, 'Retain the original 200 ordered heldout backups')
    chains = {}
    for identity in ids:
        primary = lookup[identity]
        _require(primary.get('round') is None and primary.get('source_horizon') == 10
                 and primary.get('cut_rule') == {'kind': 'first_alarm'},
                 'Heldout must retain native10, round=None and the first legal alarm')
        backups = sorted((row for row in all_backups if row.get('replacement_of') == identity),
                         key=lambda row: row.get('replacement_ordinal', -1))
        backup_ids = [row['episode_id'] for row in backups]
        _require([row.get('replacement_ordinal') for row in backups] == [1, 2]
                 and backup_ids == REGISTERED_REPLACEMENT_CANDIDATES[identity],
                 'Backup IDs or original ordinal order changed')
        _require(all(all(row.get(name) == primary.get(name)
                         for name in ('split', 'round', 'task', 'source_horizon', 'cut_rule'))
                     for row in backups), 'Backup changed its primary task/split/cut protocol')
        if replacement_candidates is not None:
            _require(replacement_candidates.get(identity) == backup_ids,
                     'Replacement mapping differs from the original manifest order')
        chains[identity] = [identity]+backup_ids
    return lookup, ids, chains


def _outcomes(record):
    no_cut = record.get('no_cut')
    _require(type(no_cut) is bool, 'Every source must explicitly declare no_cut')
    if no_cut:
        _require(record.get('actual_cut') is None and type(record.get('common_outcome')) is bool,
                 'No-cut sources require their known common full-episode outcome')
        broadcast = np.full((len(METHODS), REPLICATES), record['common_outcome'], dtype=bool)
        if 'outcomes' not in record:
            return broadcast
    else:
        cut = record.get('actual_cut')
        _require(type(cut) is int and cut % 10 == 5 and 5 <= cut <= 285,
                 'Cut sources require an audited legal native10 first-alarm midpoint')
        _require(record.get('common_outcome') is None, 'Physical branches cannot be replaced by a common outcome')
    values = record.get('outcomes')
    _require(isinstance(values, dict) and set(values) == set(METHODS),
             'Exactly the five physical arms are required, with no sixth selected-policy arm')
    rows = []
    for name in METHODS:
        value = np.asarray(values[name])
        _require(value.shape == (REPLICATES,) and value.dtype == np.dtype('bool'),
                 'Each arm needs four observed boolean paired outcomes')
        rows.append(value)
    labels = np.stack(rows)
    if no_cut:
        _require(np.array_equal(labels, broadcast), 'No-cut outcome must be common to every arm and repeat')
    return labels


def _records(lookup, ids, chains, source_records):
    _require(isinstance(source_records, (list, tuple)) and len(source_records) == SOURCE_DENOMINATOR,
             'All 100 primary slots must be technically complete before heldout statistics')
    keyed = {}
    for row in source_records:
        identity = row.get('planned_slot_id')
        _require(identity in ids and identity not in keyed, 'Duplicate or unregistered logical primary slot')
        keyed[identity] = row
    _require(set(keyed) == set(ids), 'Missing technical slots cannot be filled with zero outcomes')
    labels, normalized, actual_ids, scenes = [], [], set(), set()
    for identity in ids:
        record = keyed[identity]
        _require(record.get('status') == 'complete'
                 and record.get('artifact_audit_status') == 'passed'
                 and record.get('scene_isolation_status') == 'passed',
                 'Unverified or incomplete artifacts/scenes block heldout statistics')
        actual = record.get('resolved_episode_id')
        _require(actual in chains[identity] and actual not in actual_ids,
                 'Resolved source must be a distinct approved member of its original backup chain')
        actual_ids.add(actual); case = lookup[actual]
        _require(record.get('task') == case['task'], 'Record task differs from its actual registered source')
        scene = record.get('scene_fingerprint')
        _require(isinstance(scene, str) and len(scene) == 64 and all(c in '0123456789abcdef' for c in scene),
                 'Audited initial physical scene fingerprint required')
        scene_key = (case['task'], scene)
        _require(scene_key not in scenes, 'Duplicate accepted physical initial scene within a task')
        scenes.add(scene_key)
        resolution = record.get('resolution', {})
        _require(resolution.get('status') == 'resolved'
                 and resolution.get('planned_slot_id') == identity
                 and resolution.get('resolved_episode_id') == actual
                 and resolution.get('substitution_after_outcome_forbidden') is True,
                 'Resolution is incomplete or differs from planned/actual source IDs')
        rejected = resolution.get('ordered_rejections')
        predecessors = chains[identity][:chains[identity].index(actual)]
        _require(isinstance(rejected, list) and [row.get('episode_id') for row in rejected] == predecessors,
                 'Pre-action replacement predecessors were skipped, reordered or left incomplete')
        _require(all(row.get('reason') in ('initialization_failed', 'duplicate_initial_scene')
                     and row.get('before_first_action') is True for row in rejected),
                 'Outcome-dependent source replacement is forbidden')
        outcome = _outcomes(record)
        labels.append(outcome)
        normalized.append(dict(planned_slot_id=identity, resolved_episode_id=actual, task=case['task'],
            scene_fingerprint=scene, no_cut=record['no_cut'], actual_cut=record.get('actual_cut'),
            common_outcome=record.get('common_outcome'), resolution=deepcopy(resolution),
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


def summarize_heldout(manifest, primary_ids, source_records, *, expected_primary_ids_sha256,
                      replacement_candidates=None):
    """Summarize all 100 audited heldout sources without selecting a policy.

    The fixed main comparison remains post-minus-replan even when another arm
    scores higher.  Point target attainment and a strictly positive CI lower
    endpoint are separate descriptions, neither a guarantee of true >=5pp gain.
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
            comparisons={METHODS[a]+'_minus_'+METHODS[b]: _comparison(data[:, a], data[:, b],
                bootstrap if intervals else None) for a, b in COMPARISONS})
    overall = group(np.ones(SOURCE_DENOMINATOR, dtype=bool), intervals=True)
    main = overall['comparisons'][PRIMARY_COMPARISON]
    net = int(y[:, 4].sum(dtype=np.int64)-y[:, 1].sum(dtype=np.int64))
    point = net/(SOURCE_DENOMINATOR*REPLICATES)
    _require(main['gain'] == point, 'Source-mean and paired-count main effect disagree')
    # Integer net >=20 gives the exact registered 5pp boundary on 400 outcomes.
    assessment = dict(comparison=PRIMARY_COMPARISON, method_fixed_before_heldout='post',
        paired_success_difference=net, point_estimate=point, practical_target=PRACTICAL_TARGET,
        point_estimate_target_met=net >= 20, source_95ci=deepcopy(main['source_95ci']),
        ci_supports_positive_gain=main['source_95ci'][0] > 0,
        true_gain_at_least_target_guaranteed=False,
        nonpositive_or_crossing_ci_does_not_prove_ineffectiveness=True,
        posthoc_method_selection=False, selection_rule_changed=False,
        interpretation='Report point target attainment and interval evidence separately; neither guarantees a true gain of at least five percentage points.')
    for index, row in enumerate(rows):
        row['post_minus_replan_mean'] = float((y[index, 4].astype(int)-y[index, 1].astype(int)).mean())
    return dict(schema='native10_heldout_statistics_v1', status='complete_statistics_fixed_policy',
        decision_sha256=DECISION_SHA256, stage=STAGE, bank_version=BANK,
        fixed_critic=deepcopy(FIXED_CRITIC), fixed_method='post', methods=list(METHODS),
        primary_comparison=PRIMARY_COMPARISON,
        secondary_comparisons=[METHODS[a]+'_minus_'+METHODS[b] for a, b in COMPARISONS
                               if METHODS[a]+'_minus_'+METHODS[b] != PRIMARY_COMPARISON],
        source_denominator=SOURCE_DENOMINATOR, replicates=REPLICATES, logical_outcomes_per_arm=400,
        physical_arms=5, physical_branch_count=int((~no_cut).sum())*len(METHODS)*REPLICATES,
        primary_ids=ids, primary_ids_sha256=canonical_hash(ids),
        registered_replacement_candidates_sha256=REGISTERED_REPLACEMENT_CANDIDATES_SHA256,
        manifest_sha256=canonical_hash(manifest), normalized_input_sha256=canonical_hash(rows),
        resolved_source_ids=[row['resolved_episode_id'] for row in rows],
        replacement_source_count=sum(row['planned_slot_id'] != row['resolved_episode_id'] for row in rows),
        overall=overall, per_task={task: group(tasks == task) for task in TASKS},
        alarm_conditioned=group(~no_cut), no_cut_common_outcomes=group(no_cut),
        per_source=rows, primary_assessment=assessment,
        bootstrap=dict(draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED, task_order=list(TASKS),
            source_order=ids, unit='whole logical primary source within task', quantile_method='linear',
            interval='percentile95', multiplicity_adjusted=False, suffixes_are_independent_sources=False,
            use='Fixed heldout primary comparison plus six preregistered secondary descriptions'),
        per_source_confidence_intervals=False, calibration_outcomes_pooled=False,
        technical_missing=0, selection_proposals_written=0, selection_seals_written=0,
        next_stage_automatically_started=False, model_calls=0, simulator_calls=0, optimizer_updates=0,
        limitations=['Caller must verify physical artifacts, paired suffixes, loaded A4000, cross-split scenes and ledger.',
            'All 100 primary slots are retained; technical missingness is never encoded as a failed or zero-difference source.',
            'Four suffixes remain paired measurements within each source, not 400 independent initial states.',
            'Seven intervals are unadjusted; post-minus-replan was fixed before opening heldout.',
            'A point estimate at least five percentage points does not establish true gain of at least that size.',
            'An interval containing zero is not proof of strict ineffectiveness.',
            'Results concern the fixed five tasks, native10 and one intervention at the first legal alarm.'])
