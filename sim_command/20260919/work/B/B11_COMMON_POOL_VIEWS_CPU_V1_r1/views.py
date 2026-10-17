"""B11 metadata-only method qualification. No model or environment imports.

This is an internal consumer of A's immutable schemas, not a wire schema.
Caller validates the referenced bytes and canonical physical identity first.
"""
import hashlib
import math


def sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def ref(value):
    return isinstance(value, dict) and bool(value.get('path')) and sha(value.get('sha256'))


def verdict(reasons, **extra):
    return dict(eligible=not reasons, missing_reasons=sorted(set(reasons)), **extra)


def lvm(record):
    """Terminal completeness is intentionally not a dependency of LVM."""
    w, sig, ident = record['window'], record['input_signatures'], record['identity']
    errors = []
    if ident['split'] not in ('train', 'development'):
        errors.append('split_not_learning')
    if not w['normal_demonstration']:
        errors.append('not_normal_demonstration')
    steps = w['observed_steps']
    if len(steps) != 11 or steps != list(range(steps[0], steps[0] + 11)):
        errors.append('requires_contiguous_11_real_frames')
    if len(w['episode_ids']) != 11 or set(w['episode_ids']) != {ident['episode_id']}:
        errors.append('cross_episode_or_missing_frame_identity')
    if not ref(w['token_start_ref']) or not ref(w['token_end_ref']):
        errors.append('missing_endpoint_tokens')
    if w['token_shape'] != [256, 2048]:
        errors.append('token_shape_not_256x2048')
    if not steps or w['token_start_step'] != steps[0] or w['token_end_step'] != steps[-1]:
        errors.append('token_endpoint_step_mismatch')
    if (not sha(sig['encoder_sha256']) or w['token_start_encoder_sha256'] != sig['encoder_sha256']
            or w['token_end_encoder_sha256'] != sig['encoder_sha256']
            or not sha(sig['preprocessing_sha256']) or not w['feature_signature_verified']):
        errors.append('encoder_or_preprocessing_signature_mismatch')
    if (not ref(w['original_action_ref']) or w['original_action_shape'] != [4]
            or not sha(sig['normalizer_sha256'])
            or w['original_action_normalizer_sha256'] != sig['normalizer_sha256']
            or sig['action_representation'] != 'B_original_action_t'
            or not sha(sig['action_representation_sha256'])):
        errors.append('original_action_or_normalizer_mismatch')
    return verdict(errors, terminal_flags_preserved={k: record['outcome'][k] for k in ('terminated', 'truncated')},
                   action_clipped=False, endpoint_offset=10)


def outcome(out, protocol, *, absorbing_rule_verified=False):
    """s300 includes its final resulting state. Censoring is never a failure."""
    if protocol.get('parent_absolute_target_state') != 300:
        return None, 'target_not_absolute_s300'
    if not out.get('outcome_complete'):
        return None, out.get('reason') or 'incomplete_outcome'
    last, first = out.get('last_observed_parent_state'), out.get('first_success_step')
    if type(last) is not int or not 0 <= last <= 300:
        return None, 'invalid_observed_absolute_state'
    if out.get('success') == 1 and out.get('reason') == 'success':
        if type(first) is int and 1 <= first <= last:
            return 1, None
        return None, 'missing_first_success_state'
    if (out.get('success') == 0 and first is None
            and out.get('reason') == 'absolute_s300_complete' and last == 300):
        return 0, None
    if (out.get('success') == 0 and first is None and out.get('terminated') is True
            and out.get('reason') == 'frozen_absorbing_failure' and absorbing_rule_verified):
        return 0, None
    return None, 'unproven_or_censored_complete_outcome'


def full_state(record):
    state = record['restoration']
    if state['level'] != 'full_state_verified' or state['unknown_fields'] or not state['fields']:
        return False
    if not all(ref(state.get(k)) for k in ('reference_state_ref', 'observed_state_ref', 'verification_ref')):
        return False
    for f in state['fields']:
        if f['classification'] == 'unknown' or f['verdict'] not in ('equal', 'not_applicable'):
            return False
        if f['verdict'] == 'equal' and (not sha(f['reference_sha256']) or f['reference_sha256'] != f['observed_sha256']):
            return False
    return True


def member(record, *, verification_checked=True, precut_evidence_checked=True):
    identity, p, plans, r = record['identity'], record['protocol'], record['plans'], record['repeats']
    value, why = outcome(record['outcome'], p)
    context = record['restoration']['reference_state_ref']
    return dict(parent=identity['parent_id'], source=identity['source_id'], split=identity['split'],
                source_signature=identity['source_signature'], context_signature=context['sha256'] if context else None,
                cut=p['cut_step'], target=p['target_namespace'], commitment=p['commitment_steps'],
                absolute_target=p['parent_absolute_target_state'], native_H=p['native_H'],
                arm=plans['candidate_family'], repeat=r['repeat_id'], planned_repeats=r['planned_repeat_ids'],
                physical_id=identity['physical_attempt_id'], raw_group=plans['raw_alias_group'],
                raw_C10_sha256=plans['raw_C10_sha256'], suffix_stream=plans['suffix_stream_id'],
                complete=value is not None, success=value, outcome_reason=why,
                full_state=full_state(record) and verification_checked and precut_evidence_checked)


COMPARISONS = {'gain_local_plus': ('Q_C10', ['local_plus', 'a0']),
               'gain_local_minus': ('Q_C10', ['local_minus', 'a0']),
               'pair': ('Q_C10', ['local_plus', 'local_minus']),
               'G0': ('G0_C5', ['old', 'fresh0', 'fresh1', 'fresh2'])}


def paired(rows, label):
    namespace, arms = COMPARISONS[label]
    rows = [r for r in rows if r['target'] == namespace and r['arm'] in arms]
    reasons = []
    by = {}
    for row in rows:
        key = row['arm'], row['repeat']
        if key in by:
            reasons.append('duplicate_logical_arm_repeat')
        by[key] = row
        if type(row['repeat']) is not int or row['repeat'] not in (0, 1) or row['planned_repeats'] != [0, 1]:
            reasons.append('unplanned_repeat')
        if row['cut'] not in (5, 55) or row['absolute_target'] != 300 or row['native_H'] != 10:
            reasons.append('temporal_protocol_mismatch')
        if row['commitment'] != (5 if namespace == 'G0_C5' else 10):
            reasons.append('C5_C10_namespace_mismatch')
    cross_keys = ('parent', 'source', 'split', 'source_signature', 'context_signature', 'cut', 'target')
    cross_ok = bool(rows) and all(len({r.get(k) for r in rows}) == 1 and rows[0].get(k) is not None for k in cross_keys)
    if not cross_ok:
        reasons.append('parent_cut_source_context_or_split_mismatch')
    if any(r['split'] not in ('train', 'development') for r in rows):
        reasons.append('split_not_learning')
    raw_stable = all(len({r['raw_group'] for r in rows if r['arm'] == a}) == 1
                     and all(sha(r['raw_group']) for r in rows if r['arm'] == a) for a in arms)
    if not raw_stable:
        reasons.append('raw_group_not_stable_across_repeats')
    valid = []
    for repeat in (0, 1):
        selected = [by.get((a, repeat)) for a in arms]
        if any(r is None or not r['complete'] or not r['full_state'] for r in selected):
            continue
        if cross_ok and raw_stable and len({r['suffix_stream'] for r in selected}) == 1 and selected[0]['suffix_stream']:
            valid.append(repeat)
    if valid != [0, 1]:
        reasons.append('missing_complete_aligned_full_state_double_repeat')
    if any(by.get((a, 0), {}).get('suffix_stream') == by.get((a, 1), {}).get('suffix_stream') for a in arms):
        reasons.append('repeat_streams_not_distinct')
    if any(by.get((a, 0), {}).get('physical_id') == by.get((a, 1), {}).get('physical_id') for a in arms):
        reasons.append('one_physical_attempt_reused_as_two_repeats')
    alias = label != 'G0' and all(by.get((arms[0], r), {}).get('raw_group') is not None
        and by.get((arms[0], r), {}).get('raw_group') == by.get((arms[1], r), {}).get('raw_group') for r in (0, 1))
    if alias:
        reasons.append('same_raw_C10_group')
    target = None
    if not reasons:
        mean = lambda a: sum(by[a, r]['success'] for r in (0, 1)) / 2
        target = sum(mean(a) for a in arms[1:]) / 3 - mean('old') if label == 'G0' else mean(arms[0]) - mean(arms[1])
    return dict(target=target, target_mask=not reasons, valid_pair_repeat_ids=valid,
                raw_alias_masked=alias, missing_reasons=sorted(set(reasons)),
                target_namespace=namespace, arms=arms)


def bce_groups(rows):
    """One input group per parent/cut/protocol/raw C10; aliases do not add weight."""
    groups = {}
    for row in rows:
        if row['target'] != 'Q_C10' or not sha(row['raw_C10_sha256']):
            continue
        key = (row['parent'], row['split'], row['source_signature'], row['context_signature'],
               row['cut'], row['target'], row['raw_C10_sha256'])
        groups.setdefault(key, []).append(row)
    result = []
    for key, items in sorted(groups.items()):
        by = {}; conflicts = []
        for r in items:
            if r['complete'] and type(r['repeat']) is int and r['repeat'] in (0, 1):
                if r['repeat'] in by and by[r['repeat']] != r['success']:
                    conflicts.append('conflicting_outcomes_in_same_raw_group_repeat')
                by[r['repeat']] = r['success']
        ids = sorted(by)
        result.append(dict(parent=key[0], split=key[1], source_signature=key[2], context_signature=key[3],
                           cut=key[4], target_namespace=key[5], raw_C10_sha256=key[6],
                           logical_arms=sorted({r['arm'] for r in items}),
                           physical_attempt_refs=sorted({r['physical_id'] for r in items}),
                           effective_repeat_ids=ids, effective_repeat_count=len(ids),
                           eligible=bool(ids) and not conflicts,
                           target=sum(by.values()) / len(ids) if ids and not conflicts else None,
                           missing_reasons=conflicts or ([] if ids else ['no_own_complete_outcome'])))
    return result


def window_indices(*, n, outcome_value, first_success_state, bad_actions=(), bad_features=(), bad_states=(),
                   language_ok=True, episode_contiguous=True):
    """Return real step indices only. No tensors, padding, or feature extraction."""
    bad_actions, bad_features, bad_states = map(set, (bad_actions, bad_features, bad_states))
    result = {'D5': [], 'GAF': [], 'D5_rejected': {}, 'GAF_rejected': {}, 'GAF_targets': []}
    for step in range(n):
        for method, length in [('D5', 5), ('GAF', 10)]:
            reasons = []
            if step + length > n:
                reasons.append('short_actual_window')
            if not episode_contiguous:
                reasons.append('cross_episode_or_gap')
            if any(t in bad_actions for t in range(step, min(step + length, n))):
                reasons.append('executed_action_mapping_unknown')
            if method == 'D5':
                if any(t in bad_features for t in range(max(0, step - 4), min(step + 5, n) + 1)):
                    reasons.append('feature_signature_or_reference_invalid')
            else:
                if step in bad_states or not language_ok:
                    reasons.append('state4_or_language2048_binding_invalid')
                if outcome_value is None:
                    reasons.append('incomplete_discounted_success_target')
                if outcome_value == 1 and (first_success_state is None or first_success_state <= step):
                    reasons.append('success_step_not_future_control_result')
            if reasons:
                for r in set(reasons):
                    result[method + '_rejected'][r] = result[method + '_rejected'].get(r, 0) + 1
            else:
                result[method].append(step)
                if method == 'GAF':
                    result['GAF_targets'].append(.99 ** (first_success_state - step - 1) if outcome_value else 0.)
    return result


def raw_c10_group(payload):
    if len(payload) != 800:
        raise ValueError('raw50 must be float32[50,4]')
    return hashlib.sha256(payload[:160]).hexdigest()
