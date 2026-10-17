"""Pure CPU statistics for the fixed, previously revealed 100-source ablation.

Only the complete artifact audit supplies real records. This module opens no
files, chooses no method, and grants no execution or selection permission.
"""
from collections import Counter
from copy import deepcopy

import numpy as np

from experiments.native10_training_20260916.heldout_statistics_v1 import (
    REGISTERED_PRIMARY_IDS, REGISTERED_PRIMARY_IDS_SHA256)
from experiments.native10_training_20260916.protocol import TASKS, canonical_hash

OLD_METHODS = ('continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post')
SOLO_METHODS = ('solo_velocity', 'solo_direct', 'solo_post')
METHODS = OLD_METHODS+SOLO_METHODS
PRIMARY = ((7, 1), (6, 1), (5, 1))
SECONDARY = ((7, 4), (6, 3), (5, 2), (7, 0), (6, 0), (5, 0))
REFERENCE = ((1, 0),)
COMPARISONS = PRIMARY+SECONDARY+REFERENCE
NO_CUT_IDS = ('pick-place-wall-v3__2026111866', 'pick-place-wall-v3__2026111881')
REPLICATES, SOURCE_COUNT, BOOTSTRAP_DRAWS, BOOTSTRAP_SEED = 4, 100, 10000, 2026091801
BONFERRONI_QUANTILES = (.05/6, 1-.05/6)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _validated(records, primary_ids, expected_primary_ids_sha256):
    ids = list(primary_ids)
    require(ids == list(REGISTERED_PRIMARY_IDS)
        and expected_primary_ids_sha256 == REGISTERED_PRIMARY_IDS_SHA256 == canonical_hash(ids),
        'Keep the original ordered 100 primary identities')
    require(isinstance(records, (list, tuple)) and len(records) == SOURCE_COUNT,
        'All 100 audited sources are required; missingness is never a zero label')
    keyed = {}
    for row in records:
        identity = row.get('planned_slot_id')
        require(identity in ids and identity not in keyed, 'Duplicate or unregistered primary source')
        keyed[identity] = row
    rows, labels, actual_ids, scenes = [], [], set(), set()
    for identity in ids:
        row = deepcopy(keyed[identity]); task = identity.rsplit('__', 1)[0]
        require(row.get('status') == 'complete' and row.get('artifact_audit_status') == 'passed'
            and row.get('task') == task and row.get('pairing_audit_status') == 'passed',
            'Complete artifact and cross-implementation pairing audits are required')
        actual = row.get('resolved_episode_id')
        require(isinstance(actual, str) and actual.startswith(task+'__') and actual not in actual_ids,
            'Preserve distinct resolved-source identities separately from primary slots')
        actual_ids.add(actual)
        scene = row.get('scene_fingerprint')
        require(isinstance(scene, str) and len(scene) == 64 and set(scene) <= set('0123456789abcdef')
            and (task, scene) not in scenes, 'Distinct audited task-matched physical scenes required')
        scenes.add((task, scene))
        require(type(row.get('no_cut')) is bool and row['no_cut'] == (identity in NO_CUT_IDS),
            'Preserve the registered 98 cuts and exact two no-alarm sources')
        if row['no_cut']:
            require(row.get('actual_cut') is None and type(row.get('common_outcome')) is bool,
                'No-alarm sources retain their known common terminal outcome')
        else:
            cut = row.get('actual_cut')
            require(type(cut) is int and 5 <= cut <= 285 and cut % 10 == 5
                and row.get('common_outcome') is None, 'Original legal cut required')
        outcomes = row.get('outcomes')
        require(isinstance(outcomes, dict) and set(outcomes) == set(METHODS),
            'Exactly five reused and three newly measured arms are required')
        array = []
        for method in METHODS:
            values = np.asarray(outcomes[method])
            require(values.shape == (REPLICATES,) and values.dtype == np.dtype('bool'),
                'Each arm requires four observed binary paired outcomes')
            array.append(values)
        array = np.stack(array)
        if row['no_cut']:
            require(np.all(array == row['common_outcome']), 'No-alarm outcome must be common to all arms')
        rows.append(row); labels.append(array)
    require(Counter(row['task'] for row in rows) == Counter({task: 20 for task in TASKS}),
        'Keep 20 sources per task, not 80 independent suffixes')
    return rows, np.stack(labels)


def _comparison(candidate, baseline, draws=None, *, primary=False):
    delta = (candidate.astype(np.int8)-baseline.astype(np.int8)).mean(axis=1)
    rescue = int(np.count_nonzero(candidate & ~baseline))
    harm = int(np.count_nonzero(~candidate & baseline))
    out = dict(gain=(rescue-harm)/(len(delta)*REPLICATES), paired_success_difference=rescue-harm,
        rescues=rescue, harms=harm, positive_sources=int(np.count_nonzero(delta > 0)),
        negative_sources=int(np.count_nonzero(delta < 0)), zero_sources=int(np.count_nonzero(delta == 0)))
    if draws is not None:
        means = delta[draws].mean(axis=1)
        out['source_95ci'] = np.quantile(means, [.025, .975], method='linear').tolist()
        if primary:
            out['source_bonferroni_98_333333ci'] = np.quantile(means, BONFERRONI_QUANTILES, method='linear').tolist()
            out['bonferroni_quantiles'] = list(BONFERRONI_QUANTILES)
            out['adjusted_interval_supports_positive_gain'] = out['source_bonferroni_98_333333ci'][0] > 0
    return out


def summarize(records, *, primary_ids=REGISTERED_PRIMARY_IDS,
              expected_primary_ids_sha256=REGISTERED_PRIMARY_IDS_SHA256, task_sha256=None):
    require(task_sha256 is None or isinstance(task_sha256, str) and len(task_sha256) == 64
        and set(task_sha256) <= set('0123456789abcdef'), 'Frozen TASK SHA must be a valid digest')
    rows, y = _validated(records, primary_ids, expected_primary_ids_sha256)
    tasks = np.asarray([r['task'] for r in rows]); no_cut = np.asarray([r['no_cut'] for r in rows])
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.concatenate([rng.choice(np.flatnonzero(tasks == task), size=(BOOTSTRAP_DRAWS, 20), replace=True)
                            for task in TASKS], axis=1)
    names = lambda pairs: [METHODS[a]+'_minus_'+METHODS[b] for a, b in pairs]
    def group(mask, intervals=False):
        data = y[mask]; n = len(data)
        if not n:
            return dict(sources=0, logical_outcomes_per_arm=0, success_counts=None, success_rates=None, comparisons=None)
        counts = data.sum(axis=(0, 2), dtype=np.int64)
        return dict(sources=n, logical_outcomes_per_arm=n*REPLICATES,
            success_counts=dict(zip(METHODS, counts.tolist())),
            success_rates=dict(zip(METHODS, (counts/(n*REPLICATES)).tolist())),
            comparisons={METHODS[a]+'_minus_'+METHODS[b]: _comparison(data[:, a], data[:, b],
                draws if intervals else None, primary=(a, b) in PRIMARY) for a, b in COMPARISONS})
    overall = group(np.ones(SOURCE_COUNT, dtype=bool), True)
    for index, row in enumerate(rows):
        row['paired_source_gains'] = {METHODS[a]+'_minus_'+METHODS[b]:
            float((y[index, a].astype(int)-y[index, b].astype(int)).mean()) for a, b in COMPARISONS}
    return dict(schema='standalone_ablation_statistics_v1', status='complete_fixed_ablation_statistics',
        task_sha256=task_sha256, source_denominator=100, replicates=4, logical_outcomes_per_arm=400,
        reached_sources=98, no_cut_sources=2, new_physical_branches=1176,
        methods=list(METHODS), reused_methods=list(OLD_METHODS), new_methods=list(SOLO_METHODS),
        method_provenance={m: 'reused_sealed_control' if m in OLD_METHODS else 'new_solo_measurement' for m in METHODS},
        common_primary_comparisons=names(PRIMARY), secondary_comparisons=names(SECONDARY), reference_comparisons=names(REFERENCE),
        overall=overall, per_task={task: group(tasks == task) for task in TASKS},
        alarm_conditioned=group(~no_cut), no_cut_common_outcomes=group(no_cut), per_source=rows,
        primary_ids=list(primary_ids), primary_ids_sha256=canonical_hash(list(primary_ids)),
        bootstrap=dict(draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED, task_order=list(TASKS), source_order=list(primary_ids),
            unit='whole source within task; all eight methods and all four repeats share each draw',
            quantile_method='linear', ordinary_quantiles=[.025, .975],
            primary_family_size=3, bonferroni_quantiles=list(BONFERRONI_QUANTILES),
            adjusted_confidence=1-.05/3, approximate_bootstrap_family_control=True,
            secondary_intervals_confirmatory=False),
        winner_selected=False, new_independent_heldout=False, per_source_confidence_intervals=False,
        selection_seals_written=0, model_calls=0, simulator_calls=0, optimizer_updates=0,
        limitations=['Previously revealed test cohort; this is a fixed structural ablation, not a new independent heldout.',
            'All three solo-minus-replan comparisons form one primary family; do not retain only the winner.',
            'Bonferroni percentile bootstrap intervals provide approximate family control, not an exact finite-sample guarantee.',
            'Secondary intervals are descriptive; crossing zero does not establish equivalence or noninferiority.',
            'Deployment branches are independent; the fixed critic still used mixed-candidate training data.'])
