"""Pure, episode-grouped native10 label packaging; no collection or fitting.

Callers supply already-read, verified source/bank/branch records. This module
never discovers or opens future outcome files. ``save_new_dataset`` is its only
writer and exclusively creates a new version below this workflow's datasets/.
The provenance envelope binds every physical label to the same source, frozen
models, bank and suffix protocol; raw commands, never clipped proxies, define
aliases. Calibration, heldout and P0 labels cannot enter these training packs.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import numpy as np

from .candidates13 import CANDIDATE_ORDER, PAIRS
from .protocol import episode_key, suffix_seed, validate_manifest, canonical_hash


STATE_KEYS = ('history', 'history_mask', 'proprio', 'proprio_mask',
              'past_actions', 'language', 'remaining')
STATE_SHAPES = dict(history=(5, 4096), history_mask=(5,), proprio=(5, 4),
                    proprio_mask=(5,), past_actions=(4, 4), language=(2048,), remaining=())
PAIR_INDICES = np.asarray([(CANDIDATE_ORDER.index(a), CANDIDATE_ORDER.index(b))
                           for a, b in PAIRS], dtype=np.int64)
REPEATS = 4
CONTROL = 'continue_native10'
METHOD_ALIASES = {'alarm_replan10': 'a0', 'replan': 'a0',
                  'velocity_matched': 'velocity', 'direct_matched': 'direct', 'post_matched': 'post'}
PROVENANCE_HASH_KEYS = ('source_seal_sha256', 'protocol_sha256', 'candidate_bank_sha256')
ANALYSIS_SOURCE_NAMES = ('NATIVE10_ANALYSIS_LEAD.md', 'NATIVE10_TRAINING_READINESS_REVIEW.md',
                         'NATIVE10_RAW_BUDGET_AMENDMENT.md', 'NATIVE10_EVAL20_AMENDMENT.md')


class DatasetError(ValueError):
    """Malformed provenance, leakage or ambiguous labels, never a failed outcome."""


def raw_command_sha256(value):
    array = np.asarray(value)
    if array.dtype != np.float32 or array.shape not in ((10, 4), (50, 4)):
        raise DatasetError('Raw commands must be float32 10x4 or 50x4')
    if not np.isfinite(array).all():
        raise DatasetError('Nonfinite raw commands')
    return hashlib.sha256(array[:10].astype('<f4', copy=False).tobytes(order='C')).hexdigest()


def _sha(value, name):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise DatasetError(f'{name} must be a lowercase SHA256')
    return value


def _integer(value, name, lower=0, upper=None):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise DatasetError(f'{name} must be an integer')
    value = int(value)
    if value < lower or (upper is not None and value > upper):
        raise DatasetError(f'{name} outside allowed range')
    return value


def _binary(value, name):
    if not isinstance(value, (bool, np.bool_)):
        raise DatasetError(f'{name} must be a recorded binary boolean')
    return bool(value)


def _identity(row, episode, *, required=True):
    for field in ('episode_id', 'task', 'env_seed', 'split'):
        if field not in row and not required:
            continue
        if row.get(field) != episode[field]:
            raise DatasetError(f'{field} differs from whole-episode registration')
    if 'case_id' in row and row['case_id'] != episode['episode_id']:
        raise DatasetError('case_id differs from whole-episode registration')
    slot=episode.get('replacement_of',episode['episode_id'])
    if 'planned_slot_id' in row and row['planned_slot_id'] != slot:
        raise DatasetError('planned_slot_id differs from the registered primary episode')


def _observed(observed, cut):
    if not isinstance(observed, Mapping) or not set(STATE_KEYS) <= set(observed):
        raise DatasetError('All observed STATE_KEYS are required')
    result = {}
    for name in STATE_KEYS:
        value = np.asarray(observed[name])
        if value.shape != STATE_SHAPES[name] or not np.isfinite(value).all():
            raise DatasetError(f'Invalid singleton observed {name}: {value.shape}')
        if name.endswith('_mask'):
            if value.dtype != np.bool_:
                raise DatasetError(f'{name} must be boolean')
            result[name] = value.copy()
        else:
            if value.dtype.kind != 'f':
                raise DatasetError(f'{name} must be floating point')
            result[name] = value.astype(np.float32, copy=True)
    if not np.isclose(float(result['remaining']), (300-cut)/300, atol=1e-7, rtol=0):
        raise DatasetError('Observed remaining does not describe the registered cut')
    return result


def audit_cut_selection(episode, source_summary):
    """Audit approved training-only fallback without consulting any outcome/Q.

    The source supplies the saved legal anchor steps, first legal alarm (or
    None), and requested/actual/reason record. A recorded legal anchor is by
    contract nonterminal with at least ten original controls remaining. Actual
    state legality is established by the caller's sealed source audit.
    """
    rule = episode.get('cut_rule')
    if not isinstance(rule, Mapping) or rule.get('kind') not in ('scheduled', 'first_alarm'):
        raise DatasetError('Source requires its preregistered cut rule')
    available = source_summary.get('available_legal_cuts')
    if not isinstance(available, list):
        raise DatasetError('Cut selection requires available_legal_cuts')
    available = [_integer(step, 'available cut', 5, 285) for step in available]
    if len(set(available)) != len(available) or any(step % 10 != 5 for step in available):
        raise DatasetError('Recorded fallback anchors must be unique legal native10 midpoints')
    first_alarm = source_summary.get('first_legal_alarm_step')
    if first_alarm is not None:
        first_alarm = _integer(first_alarm, 'first legal alarm', 5, 285)
        if first_alarm not in available:
            raise DatasetError('First legal alarm must have a saved legal anchor')
    actual = source_summary.get('actual_cut')
    if actual is not None:
        actual = _integer(actual, 'actual cut', 5, 285)
    if source_summary.get('cuts') != ([] if actual is None else [actual]):
        raise DatasetError('Selected cut list and actual_cut disagree')
    reason = source_summary.get('selection_reason')
    if not isinstance(reason, str) or not reason:
        raise DatasetError('Explicit selection_reason is required')
    requested = source_summary.get('requested_cut')
    if rule['kind'] == 'scheduled':
        target = rule.get('step')
        if target not in (15, 45, 95) or requested != target or episode['split'] != 'train':
            raise DatasetError('Scheduled fallback is restricted to registered training targets 15/45/95')
        priority = {15:[15,5],45:[45,15,5],95:[95,45,15,5]}[target]
        expected = next((step for step in priority if step in available), None)
        kind = 'scheduled' if expected == target else 'fallback' if expected is not None else 'missing'
    else:
        if requested not in (None, 'first_legal_alarm'):
            raise DatasetError('First-alarm requested_cut must be null or first_legal_alarm')
        if first_alarm is not None:
            expected, priority, kind = first_alarm, [first_alarm], 'alarm'
        elif episode['split'] == 'train':
            priority = [15,5]
            expected = next((step for step in priority if step in available), None)
            kind = 'fallback' if expected is not None else 'missing'
        else:
            expected, priority, kind = None, [], 'missing'
    if actual != expected:
        raise DatasetError('Actual cut violates approved fixed fallback/alarm priority')
    expected_reason = ('scheduled_target_reached' if kind == 'scheduled' else
                       'scheduled_prior_anchor_fallback' if kind == 'fallback' and rule['kind'] == 'scheduled' else
                       'no_alarm_training_anchor_fallback' if kind == 'fallback' else
                       'first_legal_alarm' if kind == 'alarm' else
                       'no_legal_cut' if episode['split'] == 'train' else 'no_alarm_policy_common_outcome')
    if reason != expected_reason:
        raise DatasetError('Selection reason does not describe the approved cut/fallback rule')
    audit = source_summary.get('selection_audit')
    if not isinstance(audit, Mapping) or (audit.get('available_legal_cuts') != available
            or audit.get('first_legal_alarm_step') != first_alarm or audit.get('priority_order') != priority
            or audit.get('training_fallback_allowed') is not (episode['split'] == 'train')
            or audit.get('selection_uses_outcome_labels') is not False):
        raise DatasetError('Selection audit must bind legal anchors, fixed priority and no outcome selection')
    supplied_kind = source_summary.get('selection_kind',source_summary.get('selection_category'))
    if supplied_kind is not None and supplied_kind != kind:
        raise DatasetError('selection_kind disagrees with the audited fixed-priority rule')
    return dict(requested_cut=requested, actual_cut=actual, selection_reason=reason,
                selection_kind=kind, fixed_priority=priority, available_legal_cuts=available,
                first_legal_alarm_step=first_alarm, fallback_training_only=True,
                selection_uses_outcome_or_Q=False)


def _provenance(provenance):
    if not isinstance(provenance, Mapping):
        raise DatasetError('Source/model/protocol provenance is required')
    result = {name: _sha(provenance.get(name), name) for name in PROVENANCE_HASH_KEYS}
    models = provenance.get('model_hashes')
    if not isinstance(models, Mapping) or not models:
        raise DatasetError('Explicit frozen model_hashes are required')
    if any(not isinstance(name, str) or not name for name in models):
        raise DatasetError('Model identity names must be nonempty strings')
    result['model_hashes'] = {name: _sha(value, name) for name, value in sorted(models.items())}
    namespace = provenance.get('suffix_seed_namespace')
    if not isinstance(namespace, str) or not namespace:
        raise DatasetError('Explicit paired suffix seed namespace is required')
    result['suffix_seed_namespace'] = namespace
    return result


def _bank(plans, metadata):
    if not isinstance(plans, Mapping) or set(plans) != set(CANDIDATE_ORDER):
        raise DatasetError('Exactly the registered thirteen raw candidate plans are required')
    if metadata.get('candidate_order') != list(CANDIDATE_ORDER) or metadata.get('a0_slot') != 0:
        raise DatasetError('Candidate slot order/a0 anchor changed')
    raw = np.stack([np.asarray(plans[name])[:10].copy() for name in CANDIDATE_ORDER])
    hashes = [raw_command_sha256(plans[name]) for name in CANDIDATE_ORDER]
    canonical, aliases = {}, {}
    for name, digest in zip(CANDIDATE_ORDER, hashes):
        aliases[name] = canonical.setdefault(digest, name)
        supplied = metadata.get('candidates', {}).get(name, {})
        if supplied.get('command_sha256') != digest or metadata.get('aliases', {}).get(name) != aliases[name]:
            raise DatasetError(f'Raw candidate hash/alias mismatch: {name}')
    bounded = np.clip(raw[0].astype(np.float64), -1, 1)
    mask = 1-np.abs(bounded) >= .05
    if not np.array_equal(np.asarray(metadata.get('clearance_mask')), mask):
        raise DatasetError('Candidate bank clearance mask differs from its raw a0')
    for index, name in enumerate(CANDIDATE_ORDER):
        if raw[index][~mask].tobytes() != raw[0][~mask].tobytes():
            raise DatasetError('Candidate changed saturated/clearance-masked raw coordinates')
        supplied = np.asarray(plans[name])
        base_plan = np.asarray(plans['a0'])
        if supplied.shape != base_plan.shape or supplied[10:].tobytes() != base_plan[10:].tobytes():
            raise DatasetError('Candidate raw tail or horizon differs from a0')
        change = raw[index].astype(np.float64)-raw[0].astype(np.float64)
        represented = np.clip(raw[index].astype(np.float64), -1, 1)-bounded
        if np.max(np.abs(represented-change)) > 1e-6:
            raise DatasetError('Raw-to-critic action delta mapping changed')
        if np.any(np.abs(change) > 1-np.abs(bounded)+1e-6):
            raise DatasetError('Candidate lacks symmetric boundary feasibility')
        for sl, rms, maximum in ((slice(0,3),.05,.15),(slice(3,4),.1,.4)):
            if np.sqrt(np.mean(change[:,sl]**2)) > rms+1e-6 or np.abs(change[:,sl]).max() > maximum+1e-6:
                raise DatasetError('Candidate exceeds registered raw command radius/cap')
    multiplicities = Counter(aliases.values())
    candidate_weights = np.asarray([1/multiplicities[aliases[name]] for name in CANDIDATE_ORDER], np.float32)
    gain_weights = candidate_weights.copy()
    alias_indices = np.asarray([CANDIDATE_ORDER.index(aliases[name]) for name in CANDIDATE_ORDER], np.int64)
    gain_weights[alias_indices == 0] = 0
    pair_keys, pair_weights = [], np.zeros(len(PAIR_INDICES), np.float32)
    delta = raw.astype(np.float64)-raw[0].astype(np.float64)
    for index, (a, b) in enumerate(PAIR_INDICES):
        if np.max(np.abs(delta[a]+delta[b])) > 1e-6:
            raise DatasetError(f'Nonzero symmetry violation in pair {CANDIDATE_ORDER[a]}/{CANDIDATE_ORDER[b]}')
        key = tuple(sorted((int(alias_indices[a]), int(alias_indices[b]))))
        pair_keys.append(key if key[0] != key[1] else None)
    pair_multiplicity = Counter(key for key in pair_keys if key is not None)
    for index, key in enumerate(pair_keys):
        if key is not None:
            pair_weights[index] = 1/pair_multiplicity[key]
    return raw, hashes, aliases, alias_indices, candidate_weights, gain_weights, pair_weights


def _branch(row, episode, cut, provenance, hashes):
    _identity(row, episode)
    if row.get('cut_step') != cut:
        raise DatasetError('Branch cut differs from source state')
    method = METHOD_ALIASES.get(row.get('method'), row.get('method'))
    if method not in CANDIDATE_ORDER and method != CONTROL:
        raise DatasetError('Branch method is outside critic bank/normal control')
    repeat = _integer(row.get('repeat'), 'repeat', 0, REPEATS-1)
    for name in PROVENANCE_HASH_KEYS:
        if row.get(name) != provenance[name]:
            raise DatasetError(f'Branch {name} differs from bank provenance')
    if row.get('model_hashes') != provenance['model_hashes']:
        raise DatasetError('Branch model_hashes differ from bank provenance')
    if row.get('suffix_seed_namespace') != provenance['suffix_seed_namespace']:
        raise DatasetError('Branch suffix namespace differs from bank provenance')
    expected_pair = f"{episode['episode_id']}:cut{cut}:repeat{repeat}"
    if row.get('paired_suffix_id') != expected_pair:
        raise DatasetError('Paired suffix ID differs from episode/cut/repeat')
    attempt = _integer(row.get('budget_attempt'), 'budget_attempt', 1)
    status = row.get('status')
    if status not in ('complete', 'failed'):
        raise DatasetError('Branch status must explicitly be complete or failed')
    command_hash = _sha(row.get('command_sha256'), 'branch command_sha256')
    if method != CONTROL and command_hash != hashes[CANDIDATE_ORDER.index(method)]:
        raise DatasetError('Branch command SHA differs from the raw ten-command candidate')
    result = dict(method=method, repeat=repeat, budget_attempt=attempt, status=status,
                  command_sha256=command_hash, paired_suffix_id=expected_pair,
                  provenance=provenance, suffix_seeds=deepcopy(row.get('suffix_seeds', [])))
    if status == 'failed':
        result['error'] = deepcopy(row.get('error', 'technical_failure'))
        return result
    result['success'] = _binary(row.get('success'), 'success')
    suffixes = row.get('suffix_seeds')
    if not isinstance(suffixes, list):
        raise DatasetError('Complete branch must save its actual suffix seeds')
    first_step = cut + (10-cut % 10 if method == CONTROL else 10)
    for index, suffix in enumerate(suffixes):
        expected_seed = suffix_seed(episode, cut, repeat, index, namespace=provenance['suffix_seed_namespace'])
        if (_integer(suffix.get('decision_index'), 'suffix decision_index') != index
                or _integer(suffix.get('seed'), 'suffix seed') != expected_seed
                or _integer(suffix.get('step'), 'suffix step') != first_step+10*index):
            raise DatasetError('Actual suffix stream differs from preregistered paired stream')
    return result


def pack_group(episode, source_summary, observed=None, candidate_plans=None,
               candidate_metadata=None, branch_summaries=(), *, provenance=None):
    """Package one registered train/development episode; no disk reads.

    ``candidate_plans``/metadata may come from preview13 or the future training13
    bank. Labels are accepted only for all 13 slots x repeats 0..3, after audited
    raw-alias expansion. A complete normal control is returned separately when
    available. Missing/failed labels produce ``arrays=None`` and retained records,
    never zero-imputed critic targets. Branch records carry the provenance fields
    listed in PROVENANCE_HASH_KEYS plus model_hashes, command_sha256, suffix_seeds,
    paired_suffix_id and a counted physical budget_attempt.
    """
    validate_manifest([episode])
    if episode['split'] not in ('train', 'development'):
        raise DatasetError('Calibration/heldout/P0 labels are forbidden in training/development packs')
    if not isinstance(source_summary, Mapping):
        raise DatasetError('Explicit source summary required')
    _identity(source_summary, episode)
    if 'case' in source_summary and source_summary['case'] != episode:
        raise DatasetError('Source case/round/cut registration changed')
    record = dict(episode_id=episode['episode_id'], group_id=episode['episode_id'],
                  planned_slot_id=episode.get('replacement_of',episode['episode_id']),
                  task=episode['task'], env_seed=episode['env_seed'], split=episode['split'],
                  round=episode.get('round'), planned_episode_retained=True,
                  source_summary=deepcopy(dict(source_summary)), critic_eligible=False)
    status = source_summary.get('status')
    if status != 'complete':
        if status not in ('failed', 'missing'):
            raise DatasetError('Source status must explicitly be complete, failed or missing')
        if branch_summaries:
            raise DatasetError('Failed/missing source cannot supply candidate outcomes')
        record.update(status='source_'+status, missing_reason=status)
        return dict(metadata=record, arrays=None)
    record['cut_selection'] = audit_cut_selection(episode, source_summary)
    cuts = source_summary.get('cuts')
    if not isinstance(cuts, list) or len(cuts) > 1:
        raise DatasetError('Exactly one primary cut or explicit no-cut source is required')
    if not cuts:
        if branch_summaries or candidate_plans is not None:
            raise DatasetError('No-cut episode must not invent candidate/control labels')
        available = source_summary.get('full_episode_outcome_available') is True
        outcome = _binary(source_summary.get('success'), 'no-cut source success') if available else None
        record.update(status='no_cut', full_episode_outcome_available=available, native10_outcome=outcome,
                      missing_reason=source_summary.get('end_reason', 'no_legal_cut'))
        return dict(metadata=record, arrays=None)
    cut = _integer(cuts[0], 'cut_step', 5, 285)
    if cut % 10 != 5:
        raise DatasetError('Native10 active cut must be a midpoint with at least ten controls left')
    record['cut_step'] = cut
    if candidate_plans is None:
        if branch_summaries:
            raise DatasetError('Branch labels cannot be accepted without the raw candidate bank')
        record.update(status='missing_bank', missing_reason='candidate_bank_unavailable')
        return dict(metadata=record, arrays=None)
    if not isinstance(candidate_metadata, Mapping):
        raise DatasetError('Candidate metadata required')
    values = _observed(observed, cut)
    identity = _provenance(provenance)
    raw, hashes, aliases, alias_indices, weights, gain_weights, pair_weights = _bank(candidate_plans, candidate_metadata)
    records, physical_ids = {}, {}
    for supplied in branch_summaries:
        row = _branch(supplied, episode, cut, identity, hashes)
        key = (row['method'], row['repeat'])
        if key in records:
            raise DatasetError(f'Duplicate logical candidate/repeat ID: {key}')
        attempt = row['budget_attempt']
        physical_signature = {key: row[key] for key in ('repeat', 'command_sha256', 'paired_suffix_id',
                              'provenance', 'suffix_seeds', 'status')}
        if row['status'] == 'complete':
            physical_signature['success'] = row['success']
        # Normal continuation has a different prefix length and must never be
        # treated as an alias merely because a supplied hash happens to collide.
        physical_signature['control'] = row['method'] == CONTROL
        if attempt in physical_ids and physical_ids[attempt] != physical_signature:
            raise DatasetError('Physical attempt reused across incompatible raw/state/model/suffix identities')
        physical_ids[attempt] = physical_signature
        records[key] = row
    outcomes = np.empty((13, REPEATS), np.bool_)
    attempt_ids = np.empty((13, REPEATS), np.int64)
    reused, missing = [], []
    for index, name in enumerate(CANDIDATE_ORDER):
        for repeat in range(REPEATS):
            own = records.get((name, repeat))
            peers = [row for (method, rep), row in records.items()
                     if rep == repeat and method != CONTROL and row['status'] == 'complete'
                     and aliases[method] == aliases[name]]
            if own is not None and own['status'] == 'failed':
                missing.append(dict(candidate=name, repeat=repeat, reason='explicit_failed_attempt'))
                continue
            if not peers:
                missing.append(dict(candidate=name, repeat=repeat, reason='missing_paired_outcome'))
                continue
            # Multiple physically repeated identical branches must agree; their
            # repeats cannot be silently selected or averaged into a fake label.
            if len({row['success'] for row in peers}) != 1 or any(row['suffix_seeds'] != peers[0]['suffix_seeds'] for row in peers):
                raise DatasetError('Same raw/state/model/repeat alias has conflicting outcome/suffix realization')
            selected = own if own is not None else min(peers, key=lambda row: CANDIDATE_ORDER.index(row['method']))
            outcomes[index, repeat] = selected['success']
            attempt_ids[index, repeat] = selected['budget_attempt']
            if own is None:
                reused.append(dict(candidate=name, repeat=repeat, reused_from=selected['method'],
                                   budget_attempt=selected['budget_attempt'], raw_command_sha256=hashes[index]))
    controls = [records.get((CONTROL, repeat)) for repeat in range(REPEATS)]
    control_complete = all(row is not None and row['status'] == 'complete' for row in controls)
    record.update(provenance=identity, candidate_order=list(CANDIDATE_ORDER), aliases=aliases,
                  raw_command_sha256=dict(zip(CANDIDATE_ORDER, hashes)),
                  candidate_metadata=deepcopy(dict(candidate_metadata)),
                  branch_records=list(records.values()), physical_attempt_ids=sorted(physical_ids),
                  audited_alias_reuse=reused, missing_labels=missing,
                  control_complete=control_complete,
                  control_outcomes=[row['success'] for row in controls] if control_complete else None,
                  no_outcome_imputation=True, group_unit='whole episode; cuts/repeats/aliases remain together')
    if missing:
        record.update(status='incomplete_labels', missing_reason='four_paired_repeats_required')
        return dict(metadata=record, arrays=None)
    values.update(actions=np.clip(raw, -1, 1), raw_actions=raw, outcomes=outcomes,
                  candidate_weights=weights, gain_weights=gain_weights,
                  pair_indices=PAIR_INDICES.copy(), pair_weights=pair_weights,
                  alias_indices=alias_indices, group_ids=alias_indices.copy(), physical_attempt_ids=attempt_ids)
    # Controls are optional for critic fitting and never occupy slot zero. Their
    # independent mask distinguishes absent labels from observed binary failure.
    values['control_outcomes'] = np.asarray([row['success'] if row and row['status'] == 'complete' else False
                                            for row in controls], np.bool_)
    values['control_valid'] = np.asarray([row is not None and row['status'] == 'complete' for row in controls], np.bool_)
    record.update(status='complete', critic_eligible=True, missing_reason=None)
    return dict(metadata=record, arrays=values)


def build_dataset(manifest, group_inputs, *, purpose='train', rounds=None, analysis_sources=None):
    """Package supplied groups only; retain every eligible planned episode.

    Manifest includes all splits so episode leakage is caught before subsetting.
    ``group_inputs`` contains keyword dictionaries for pack_group (including the
    registered ``episode``). Supplying outcomes from other splits/rounds is an
    error, not something silently filtered. For development selection a complete
    claim also requires complete no-cut outcomes and all normal controls.
    """
    registry = validate_manifest(manifest)
    for key,row in registry.items():
        parent=row.get('replacement_of')
        if parent is not None:
            if parent not in registry or registry[parent].get('replacement_of') is not None:
                raise DatasetError('Backup must reference one registered primary episode')
            for field in ('task','split','round','cut_rule','source_horizon'):
                if row.get(field) != registry[parent].get(field):
                    raise DatasetError('Backup changed primary task/split/round/cut registration')
    source_bindings = _analysis_bindings(analysis_sources or {})
    if purpose not in ('train', 'development'):
        raise DatasetError('Only train/development packaging is permitted before final evaluation')
    selected_rounds = None if rounds is None else {_integer(value, 'round', 1, 2) for value in rounds}
    if selected_rounds is not None and (not selected_rounds or purpose != 'train'):
        raise DatasetError('Round filtering is only for an explicit nonempty train round set')
    eligible = {key: row for key, row in registry.items() if row['split'] == purpose and not row.get('replacement_of')
                and (selected_rounds is None or row.get('round') in selected_rounds)}
    supplied, packets = {}, {}
    for group in group_inputs:
        if not isinstance(group, Mapping) or not isinstance(group.get('episode'), Mapping):
            raise DatasetError('Group input requires its registered episode')
        episode = group['episode']
        key = episode_key(episode.get('task'), episode.get('env_seed'))
        slot=episode.get('replacement_of',key)
        if slot not in eligible or key not in registry or episode != registry[key]:
            raise DatasetError('Cross-split/round or unregistered episode input is forbidden')
        if slot in supplied:
            raise DatasetError('Duplicate whole-episode group; cuts cannot create independent examples')
        supplied[slot] = group
        packets[slot] = pack_group(**group)
    retained, complete = [], []
    all_attempts = {}
    for key, episode in eligible.items():
        packet = packets.get(key)
        if packet is None:
            summary = {name: episode[name] for name in ('episode_id', 'task', 'env_seed', 'split')}
            packet = pack_group(episode, dict(summary, status='missing'))
        row = packet['metadata']
        retained.append(row)
        for attempt in row.get('physical_attempt_ids', []):
            if attempt in all_attempts:
                raise DatasetError('Physical attempt ID appears in multiple episode groups')
            all_attempts[attempt] = key
        if packet['arrays'] is not None:
            complete.append(packet)
    if complete:
        names = tuple(complete[0]['arrays'])
        values = {name: np.stack([packet['arrays'][name] for packet in complete]) for name in names}
    else:
        values = {name: np.empty((0, *shape), dtype=np.bool_ if name.endswith('_mask') else np.float32)
                  for name, shape in STATE_SHAPES.items()}
        for name, shape, dtype in [('actions',(13,10,4),np.float32),('raw_actions',(13,10,4),np.float32),
                                  ('outcomes',(13,4),np.bool_),('candidate_weights',(13,),np.float32),
                                  ('gain_weights',(13,),np.float32),('pair_indices',(5,2),np.int64),
                                  ('pair_weights',(5,),np.float32),('alias_indices',(13,),np.int64),('group_ids',(13,),np.int64),
                                  ('physical_attempt_ids',(13,4),np.int64),('control_outcomes',(4,),np.bool_),
                                  ('control_valid',(4,),np.bool_)]:
            values[name] = np.empty((0,*shape),dtype=dtype)
    for name in ('episode_id', 'split', 'task'):
        values[name] = np.asarray([packet['metadata'][name] for packet in complete],dtype=np.str_)
    values['cut_step'] = np.asarray([packet['metadata']['cut_step'] for packet in complete],np.int64)
    values['round'] = np.asarray([packet['metadata'].get('round') or 0 for packet in complete],np.int64)
    values['planned_slot_id'] = np.asarray([packet['metadata']['planned_slot_id'] for packet in complete],dtype=np.str_)
    complete_selection = all(row['status'] == 'no_cut' and row.get('full_episode_outcome_available')
                             or row['critic_eligible'] and row['control_complete'] for row in retained)
    metadata = dict(schema='native10_dataset13_v1', purpose=purpose,
                    selected_rounds=None if selected_rounds is None else sorted(selected_rounds),
                    manifest_sha256=canonical_hash(manifest), registered_all_split_episode_count=len(registry),
                    registered_primary_episode_count=sum(not row.get('replacement_of') for row in registry.values()),
                    planned_episode_count=len(eligible), complete_critic_groups=len(complete),
                    records=retained, status_counts=dict(Counter(row['status'] for row in retained)),
                    candidate_order=list(CANDIDATE_ORDER), a0_slot=0, repeats=REPEATS,
                    group_unit='whole episode', normal_control_is_separate=True,
                    analysis_sources=source_bindings, real_input_artifact_audit_required_before_fit=True,
                    complete_planned_selection_evidence=bool(eligible) and bool(complete_selection),
                    incomplete_episodes_never_imputed=True, future_outcome_files_read=False,
                    simulator_calls=0, training_updates=0, physical_attempts_referenced=len(all_attempts),
                    logical_critic_labels=len(complete)*13*REPEATS)
    rows = [dict(deepcopy(registry[packet['metadata']['episode_id']]),planned_slot_id=packet['metadata']['planned_slot_id'])
            for packet in complete]
    return dict(metadata=metadata, arrays=values, rows=rows)


def _analysis_bindings(sources, *, require_latest=False):
    if not isinstance(sources, Mapping):
        raise DatasetError('Analysis source binding must be a path-to-SHA mapping')
    result = {str(name):_sha(value,'analysis document') for name,value in sources.items()}
    if require_latest and not set(ANALYSIS_SOURCE_NAMES) <= {Path(name).name for name in result}:
        raise DatasetError('Saved dataset must bind latest analysis lead/readiness/raw-budget sources')
    return result


def save_new_dataset(version, packed):
    """Exclusively create ROOT/datasets/<version>; never replace any dataset.

    Packaging is not a simulator/training release. The caller owns authorization
    to access input outcomes and later checks READY before any optimizer update.
    """
    if not isinstance(version, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',version) is None:
        raise DatasetError('Dataset version must be a single safe, explicit path component')
    _analysis_bindings(packed['metadata'].get('analysis_sources',{}),require_latest=True)
    from . import storage
    dest = storage.ROOT/'datasets'/version
    storage.destination(dest)
    dest.mkdir(exist_ok=False)
    storage.arrays(dest/'arrays.npz', **packed['arrays'])
    storage.dump(dest/'metadata.json', packed['metadata'])
    storage.dump(dest/'rows.json', packed['rows'])
    storage.seal(dest, schema='native10_dataset13_v1', dataset_version=version)
    return dest


def load_saved_dataset(path, purpose, expected_manifest_sha256):
    """Read and check this dataset's seal, without claiming upstream seal audit.

    This does not authorize access to calibration/heldout or training execution.
    A fit launcher must also verify its separately frozen source/bank/branch/
    ledger input-audit chain; our own valid seal alone cannot establish that.
    No caller in this module executes the loader or discovers dataset paths.
    """
    if purpose not in ('train','development'):
        raise DatasetError('Only train/development dataset loading is permitted')
    _sha(expected_manifest_sha256,'expected manifest SHA')
    from . import storage
    path = Path(path).resolve()
    if not path.is_relative_to((storage.ROOT/'datasets').resolve()):
        raise DatasetError('Saved dataset must belong to this new workflow datasets directory')
    seal_path = path/'complete.json'
    seal = json.loads(seal_path.read_text())
    if (seal.get('status') != 'complete' or seal.get('schema') != 'native10_dataset13_v1'
            or set(seal.get('files',{})) != {'arrays.npz','metadata.json','rows.json'}):
        raise DatasetError('Dataset seal has an unexpected schema/file set')
    for name,expected in seal['files'].items():
        _sha(expected,'sealed dataset file')
        target = (path/name).resolve()
        if not target.is_relative_to(path) or storage.sha256(target) != expected:
            raise DatasetError('Saved dataset file failed its seal: '+name)
    metadata = json.loads((path/'metadata.json').read_text())
    rows = json.loads((path/'rows.json').read_text())
    if (metadata.get('schema') != 'native10_dataset13_v1' or metadata.get('purpose') != purpose
            or metadata.get('manifest_sha256') != expected_manifest_sha256):
        raise DatasetError('Dataset purpose/schema/manifest differs from frozen fit inputs')
    _analysis_bindings(metadata.get('analysis_sources',{}),require_latest=True)
    validate_manifest(rows)
    if any(row['split'] != purpose for row in rows):
        raise DatasetError('Saved rows contain split leakage')
    with np.load(path/'arrays.npz',allow_pickle=False) as archive:
        values = {name:archive[name].copy() for name in archive.files}
    count = len(rows)
    required = set(STATE_KEYS)|{'actions','raw_actions','outcomes','candidate_weights','gain_weights',
        'pair_weights','pair_indices','group_ids','alias_indices','physical_attempt_ids','control_outcomes',
        'control_valid','episode_id','split','task','cut_step','round','planned_slot_id'}
    if set(values) != required or any(value.shape[0] != count for value in values.values()):
        raise DatasetError('Saved array fields/counts differ from complete source rows')
    if metadata.get('complete_critic_groups') != count:
        raise DatasetError('Saved group count differs from metadata')
    for name in ('episode_id','split','task','planned_slot_id'):
        if values[name].tolist() != [row[name] for row in rows]:
            raise DatasetError('Saved row identity ordering mismatch')
    if values['actions'].shape != (count,13,10,4) or values['raw_actions'].shape != (count,13,10,4):
        raise DatasetError('Saved command arrays have incorrect shape')
    if values['outcomes'].shape != (count,13,4) or values['outcomes'].dtype != np.bool_:
        raise DatasetError('Saved outcome array must contain complete binary labels')
    if (values['actions'].dtype != np.float32 or values['raw_actions'].dtype != np.float32
            or not np.isfinite(values['raw_actions']).all()
            or not np.array_equal(values['actions'],np.clip(values['raw_actions'],-1,1))):
        raise DatasetError('Saved raw-to-critic command representation changed')
    complete_records = [row for row in metadata['records'] if row.get('critic_eligible')]
    if [row['episode_id'] for row in complete_records] != values['episode_id'].tolist():
        raise DatasetError('Saved planned records do not align with complete arrays')
    verification = dict(dataset_path=str(path),seal_sha256=storage.sha256(seal_path),
                        files_verified=dict(seal['files']),dataset_seal_verified=True,
                        upstream_source_bank_branch_ledger_verified=False,
                        upstream_input_audit_required=True)
    return dict(metadata=metadata,arrays=values,rows=rows,verification=verification)
