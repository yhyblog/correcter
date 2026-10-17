"""Preparation-only guards for one later, separately released round1 policy wave.

Importing or validating this module never loads a model or opens an environment.
The existing main runner does NOT select this factory automatically. A separately
frozen launcher must call create_policy_collector and collect_existing_slot.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re

import numpy as np

from .main_collection import (MainCollector, POLICY_METHODS, SPLIT_REPLICATES,
                              _bit_equal, _load_arrays, _read, _require_main,
                              _sealed, select_cut)
from .protocol import candidate_seed, canonical_hash
from .storage import ROOT, AttemptLedger, dump, seal, sha256


SCHEMA = 'native10_policy_deployment_v1'
STAGE = 'round1_development_policy'
UNCHANGED = ('episode_manifest', 'seed_namespace', 'source_horizon', 'prefix_horizon',
             'suffix_horizon', 'control_budget', 'gate_threshold', 'guidance',
             'matching', 'cpu', 'split_replicates', 'scene_identity')


def _inside(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()) or path.is_relative_to((ROOT/'p0').resolve()):
        raise ValueError('Deployment references must be inside the new workflow, outside P0')
    return path


def _file(path, expected):
    path = _inside(path)
    if not isinstance(expected, str) or len(expected) != 64 or sha256(path) != expected:
        raise ValueError('Deployment bound file SHA changed: '+str(path))
    return path


def _completed(path, expected, *, protocol=None):
    path = _inside(path)
    _file(path/'complete.json', expected)
    record = _read(path/'complete.json')
    # Training exports intentionally have no simulator protocol field. The exact
    # complete seal is still bound, and its entire file inventory is verified.
    _sealed(path, [protocol] if protocol is not None else [record.get('protocol_sha256')])
    return record


def _raw(value):
    value = np.asarray(value)
    if value.shape != (50, 4) or value.dtype != np.dtype('float32') or not np.isfinite(value).all():
        raise ValueError('Designated a0 must retain its finite raw float32 50x4 plan')
    return value


def _noise(record):
    hashes = record.get('noise_hashes', {})
    noise = record.get('base_generation', {}).get('noise_sha256')
    if (not isinstance(noise, str) or len(noise) != 64
            or set(hashes) != {'replan', 'velocity', 'direct'}
            or any(value != noise for value in hashes.values())):
        raise ValueError('Bank does not prove common replan/velocity/direct initial noise')
    return noise


def _training(config, binding, registration, reached_ids):
    path = _inside(binding['path'])
    complete = _completed(path, binding['seal_sha256'])
    if complete.get('role') != 'native10_two_path_training' or complete.get('phase') != 'round1':
        raise ValueError('Deployment requires a completed round1 two-path training export')
    result = _read(path/'result.json')
    selected = path/'selected'
    if (result.get('status') != 'complete' or result.get('phase') != 'round1'
            or _inside(result['selected_assets']) != selected
            or _inside(config['critic_assets']) != selected):
        raise ValueError('Selected critic must be the completed training result selection')
    export = _completed(selected, binding['selected_seal_sha256'])
    ranking = _read(selected/'ranking.json')
    hashes = ranking.get('model_hashes', {})
    if (export.get('role') != 'four_member_critic_export' or set(hashes) != {'0', '1', '2', '3'}
            or ranking.get('horizon') != 10 or ranking.get('a0_slot') != 0
            or hashes != result.get('model_hashes') or hashes != complete.get('model_hashes')
            or hashes != export.get('model_hashes') or hashes != registration['critic_member_hashes']):
        raise ValueError('Selected critic member hashes/role/horizon disagree')
    for member, digest in hashes.items():
        _file(selected/f'models/refit/member_{member}/selected.pt', digest)
        if registration['model_hashes'].get('critic_'+member) != digest:
            raise ValueError('Registered critic model identity differs from selected export')
    audit = _read(path/'selected_reload_audit.json')
    checks = ('feature_cache_bit_exact', 'thirteen_candidate_member_probability_bit_exact',
              'member_and_ensemble_gradient_bit_exact', 'a0_anchor_exactly_zero', 'state_and_anchor_immutable')
    if (audit.get('status') != 'passed' or audit.get('source_count') != len(reached_ids)
            or audit.get('episode_ids') != reached_ids or audit.get('members_checked') != 4
            or audit.get('gradient_slots') != [0, 11] or any(audit.get(key) is not True for key in checks)):
        raise ValueError('Selected export lacks complete real development reload audit')
    return dict(path=str(path), seal_sha256=binding['seal_sha256'],
                selected_seal_sha256=binding['selected_seal_sha256'], model_hashes=hashes)


def validate_deployment_inputs(config, bank_version):
    """Read-only complete binding check; this function grants no execution scope.

    The round1 deployment contract is intentionally narrow: exactly the original
    100 primary development episodes, 95 saved alarm cuts and five known common
    outcomes. Any change requires a new reviewed preparation implementation.
    """
    binding = config['policy_deployment']
    if binding.get('schema') != SCHEMA:
        raise ValueError('Missing versioned policy deployment binding')
    if not isinstance(bank_version, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', bank_version):
        raise ValueError('Deployment bank version must be a safe component')
    if config.get('stage_release_scopes', {}).get(STAGE) != STAGE:
        raise ValueError('Deployment requires its own round1_development_policy release scope')
    registration = config['main_collection']['banks'][bank_version]
    if (registration.get('kind') != 'policy5' or registration.get('stage') != STAGE
            or registration.get('generation_round') != 1
            or registration.get('cut_selection_policy') != 'analysis_lead_v1'):
        raise ValueError('Only the separately registered round1 development policy5 bank is supported')
    if config['budget']['stages'][STAGE] != dict(simulator_attempts=2100, training_updates=0):
        raise ValueError('Deployment stage must retain the 2100 simulator / zero update ceiling')
    if config.get('methods') != list(POLICY_METHODS) or config.get('split_replicates') != SPLIT_REPLICATES:
        raise ValueError('Deployment must retain the five registered arms and four development repeats')
    original = binding['old_collection']
    old_path = _file(original['config_path'], original['config_sha256'])
    freeze_path = _file(original['freeze_path'], original['freeze_sha256'])
    old, frozen = _read(old_path), _read(freeze_path)
    if frozen.get('files', {}).get(str(old_path)) != original['config_sha256']:
        raise ValueError('Original collection freeze does not bind its configuration')
    old_version = original['bank_version']
    old_registration = old['main_collection']['banks'][old_version]
    if old_version == bank_version or old_registration.get('kind') != 'labels13':
        raise ValueError('Deployment needs an independent bank and an original labels13 reference')
    for key in UNCHANGED:
        if key not in old or config.get(key) != old[key]:
            raise ValueError('Deployment changed frozen collection semantics: '+key)
    if config['main_collection']['concurrency'] != old['main_collection']['concurrency']:
        raise ValueError('Deployment changed frozen worker concurrency')
    if any(registration['model_hashes'].get(key) != old_registration['model_hashes'][key]
           for key in ('vla', 'd', 'g0', 'implementation')):
        raise ValueError('Deployment must preserve frozen VLA/D/G0/collection implementation')
    old_protocol = old['analysis_approval']['protocol_sha256']
    if old_protocol not in registration.get('allowed_source_protocol_sha256', []):
        raise ValueError('Original source protocol must be explicitly allowlisted')
    lookup = {row['episode_id']: row for row in old['episode_manifest']}
    ids = [identity for identity in old_registration['episode_ids']
           if lookup[identity]['split'] == 'development' and not lookup[identity].get('replacement_of')]
    if len(ids) != 100 or len(set(ids)) != 100 or registration['episode_ids'] != ids:
        raise ValueError('Deployment must retain the original ordered 100 development slots')
    if set(binding['source_bindings']) != set(ids):
        raise ValueError('Every original development source/resolution must have an explicit frozen binding')
    sources, reached = {}, []
    for identity in ids:
        case, bound = lookup[identity], binding['source_bindings'][identity]
        if case['case_id'] != identity or case.get('cut_rule') != {'kind': 'first_alarm'}:
            raise ValueError('Deployment cannot alter original first-alarm source registration')
        source, resolution_path = ROOT/'sources'/identity, ROOT/'slot_resolution'/identity
        _completed(source, bound['source_seal_sha256'], protocol=old_protocol)
        _completed(resolution_path, bound['resolution_seal_sha256'], protocol=old_protocol)
        resolution, summary = _read(resolution_path/'resolution.json'), _read(source/'summary.json')
        if (resolution.get('status') != 'resolved' or resolution.get('planned_slot_id') != identity
                or resolution.get('resolved_episode_id') != identity or resolution.get('ordered_rejections') != []
                or resolution.get('source_protocol_sha256') != old_protocol
                or resolution.get('source_seal_sha256') != bound['source_seal_sha256']
                or summary.get('case') != case or summary.get('planned_episode_retained') is not True
                or summary.get('outcome_filter_applied') is not False or (source/'rejection.json').exists()):
            raise ValueError('Deployment source/resolution is missing, replaced or inconsistent')
        if any(summary.get('model_hashes', {}).get(key) != registration['model_hashes'][key] for key in ('vla', 'd', 'g0')):
            raise ValueError('Original source VLA/D/G0 identity changed')
        if summary.get('seed_namespace') != config['seed_namespace']:
            raise ValueError('Original source random namespace changed')
        expected = select_cut(case, summary['available_legal_cuts'], summary['first_legal_alarm_step'])
        if (summary.get('cut_selection_policy') != 'analysis_lead_v1'
                or any(summary.get(key) != value for key, value in expected.items())):
            raise ValueError('Original development cut changed or fallback was introduced')
        cut = expected['actual_cut']
        if summary['cuts'] != ([] if cut is None else [cut]):
            raise ValueError('Original source saved cut disagrees with first alarm')
        saved_cuts = sorted(int(path.name[3:]) for path in source.glob('cut[0-9][0-9][0-9]') if path.is_dir())
        if saved_cuts != summary['available_legal_cuts']:
            raise ValueError('Original source no longer contains all saved legal anchors')
        if not (source/'trajectory.npz').is_file():
            raise ValueError('Original source replay trajectory is missing')
        for saved_cut in saved_cuts:
            folder = source/f'cut{saved_cut:03d}'
            if not (folder/'anchor.json').is_file() or not (folder/'context.npz').is_file():
                raise ValueError('Original source anchor/context is incomplete')
        common, old_bank = None, None
        if cut is None:
            if (summary.get('full_episode_outcome_available') is not True
                    or summary.get('no_alarm') is not True or type(summary.get('success')) is not bool
                    or bound.get('old_bank_seal_sha256') is not None):
                raise ValueError('No-alarm source must retain its known common outcome without a bank')
            common = summary['success']
        else:
            reached.append(identity)
            old_bank = ROOT/'banks'/old_version/identity/f'cut{cut:03d}'
            _completed(old_bank, bound['old_bank_seal_sha256'], protocol=old_protocol)
            generation = _read(old_bank/'generation.json')
            if (generation.get('episode_id') != identity or generation.get('cut_step') != cut
                    or generation.get('source_seal_sha256') != bound['source_seal_sha256']
                    or generation.get('model_hashes') != old_registration['model_hashes']
                    or generation.get('base_seed') != candidate_seed(case, cut, namespace=config['seed_namespace'])):
                raise ValueError('Original a0 bank does not match the source and registered random stream')
            _noise(generation)
            old_plan = _raw(_load_arrays(old_bank/'plans.npz')['a0'])
            if not _bit_equal(old_plan, _load_arrays(old_bank/'formal_directions.npz')['raw_a0']):
                raise ValueError('Original labels13 a0 differs from its raw generated anchor')
        sources[identity] = dict(case=deepcopy(case), source_path=str(source),
            source_seal_sha256=bound['source_seal_sha256'], resolution_path=str(resolution_path),
            resolution_seal_sha256=bound['resolution_seal_sha256'],
            old_bank_path=str(old_bank) if old_bank else None,
            old_bank_seal_sha256=bound.get('old_bank_seal_sha256'), cut=cut, common_outcome=common)
        sources[identity].update(old_protocol_sha256=old_protocol,
                                new_protocol_sha256=config['analysis_approval']['protocol_sha256'],
                                matching=deepcopy(config['matching']))
    if len(reached) != 95:
        raise ValueError('Original development coverage must remain 95 alarm cuts plus five no-alarm episodes')
    training = _training(config, binding['selected_training'], registration, reached)
    return dict(schema=SCHEMA, status='passed', episode_ids=ids, sources=sources,
        old_protocol_sha256=old_protocol, bank_version=bank_version, stage=STAGE,
        training=training, config_binding_sha256=canonical_hash(config), expected_attempts=95*21,
        hard_attempt_limit=2100, planned_denominator_per_arm=400,
        expected_cut_sources=95, common_outcome_sources=5, simulator_calls=0, model_calls=0)


def compare_bank_identity(inputs, case, new_bank, new_protocol):
    """Verify raw50 anchor, initial noise and mask before any new physical branch."""
    source = inputs['sources'][case['episode_id']]
    if case != source['case'] or source['cut'] is None:
        raise ValueError('Bank identity requires the original registered alarm cut')
    old_bank, new_bank = Path(source['old_bank_path']), _inside(new_bank)
    _completed(old_bank, source['old_bank_seal_sha256'], protocol=inputs['old_protocol_sha256'])
    _sealed(new_bank, [new_protocol])
    old, new = _read(old_bank/'generation.json'), _read(new_bank/'generation.json')
    before = _raw(_load_arrays(old_bank/'plans.npz')['a0'])
    plans = _load_arrays(new_bank/'plans.npz')
    if set(plans) != set(POLICY_METHODS[1:]):
        raise ValueError('Policy bank must contain exactly replan/velocity/direct/post')
    after = _raw(plans['alarm_replan10'])
    previous = _load_arrays(old_bank/'formal_directions.npz')
    current = _load_arrays(new_bank/'formal_directions.npz')
    if (not _bit_equal(before, after) or not _bit_equal(before, previous['raw_a0'])
            or not _bit_equal(after, current['raw_a0'])):
        raise ValueError('Regenerated designated raw50 a0 differs from the original development bank')
    if old['base_seed'] != new.get('base_seed') or _noise(old) != _noise(new):
        raise ValueError('Regenerated a0 seed/initial noise differs from the original bank')
    if not _bit_equal(previous['mask'], current['mask']):
        raise ValueError('Regenerated common feasible-coordinate mask changed')
    mask = current['mask']
    if mask.shape != (10, 4) or mask.dtype != np.dtype('bool'):
        raise ValueError('Common feasible-coordinate mask must be boolean 10x4')
    for name in POLICY_METHODS[1:]:
        plan = _raw(plans[name])
        if not _bit_equal(plan[10:], after[10:]) or not _bit_equal(plan[:10][~mask], after[:10][~mask]):
            raise ValueError('Policy correction changed raw tail or masked coordinates')
    directions = _load_arrays(new_bank/'directions.npz')
    expected_critic = np.stack([np.clip(plans[name], -1, 1) for name in POLICY_METHODS[1:]])
    if (not _bit_equal(directions['raw_a0'], after)
            or not _bit_equal(directions['critic_a0'], np.clip(after, -1, 1))
            or not _bit_equal(directions['critic_candidates'], expected_critic)):
        raise ValueError('Policy critic representation differs from the actual clipped raw command bank')
    from .bank_audit import audit_raw_bank
    aliases = dict(alarm_replan10='replan', velocity='velocity_matched',
                   direct='direct_matched', post='post_matched')
    raw_audit = audit_raw_bank(after, {aliases[name]: plans[name] for name in POLICY_METHODS[1:]},
                               source['matching'])
    matched_rms = _matched_rms(raw_audit, source['matching'])
    for key in ('episode_id', 'cut_step', 'source_seal_sha256', 'suffix_seed_namespace', 'suffix_protocol'):
        if old.get(key) != new.get(key):
            raise ValueError('Regenerated bank changed source/cut/suffix provenance: '+key)
    return dict(status='passed', episode_id=case['episode_id'], cut=source['cut'],
        old_bank_path=str(old_bank), old_bank_seal_sha256=source['old_bank_seal_sha256'],
        bank_path=str(new_bank), bank_seal_sha256=sha256(new_bank/'complete.json'),
        source_seal_sha256=source['source_seal_sha256'], raw50_a0_bit_exact=True,
        raw_tail_and_mask_preserved=True, critic_command_mapping_exact=True,
        raw_bank_audit=raw_audit, matched_rms=matched_rms,
        base_seed=new['base_seed'], noise_sha256=_noise(new), mask_bit_exact=True,
        raw50_sha256=hashlib.sha256(after.tobytes()).hexdigest(), checked_before_branch=True)


def verify_bank_anchor(bank_path, bound_source):
    """Read-only adapter for the standalone five-arm artifact auditor."""
    case = bound_source['case']
    inputs = dict(sources={case['episode_id']: bound_source},
                  old_protocol_sha256=bound_source['old_protocol_sha256'])
    return compare_bank_identity(inputs, case, bank_path, bound_source['new_protocol_sha256'])


def _matched_rms(raw_audit, matching):
    """Check the existing within-bank matched contract on executed raw deltas."""
    tolerance = float(matching['tolerance'])
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Existing matching tolerance must be finite and positive')
    spreads = {}
    for channel in ('xyz', 'gripper'):
        values = [raw_audit['actual'][name]['actual_delta'][channel+'_rms']
                  for name in ('velocity_matched', 'direct_matched', 'post_matched')]
        spread = max(values)-min(values)
        if not np.isfinite(values).all() or spread > tolerance:
            raise ValueError('Final raw V/D/P '+channel+' RMS is not matched within the frozen tolerance')
        spreads[channel] = float(spread)
    return dict(status='passed', tolerance=tolerance, maximum_spread=spreads,
                comparison='V/D/P within this bank only; no constraint on old versus new bank radii')


class _PolicyLedger:
    """No source capture, replacement, training or unrelated identity can reserve."""
    def __init__(self, delegate, inputs):
        self.delegate, self.inputs = delegate, inputs
        self.allowed = {}
        for identity, row in inputs['sources'].items():
            if row['cut'] is None:
                continue
            tail = f"{inputs['bank_version']}/{identity}/cut{row['cut']:03d}"
            self.allowed['banks/'+tail] = 'candidate_restore'
            for method in POLICY_METHODS:
                for repeat in range(4):
                    self.allowed[f"rollouts/{inputs['stage']}/{tail}/{method}/repeat_{repeat}"] = 'branch_including_restore'

    def reserve(self, stage, kind, identity, *, resource='simulator_attempts', requested=1):
        if (stage != self.inputs['stage'] or resource != 'simulator_attempts' or requested != 1
                or self.allowed.get(str(identity)) != kind):
            raise ValueError('Policy deployment prohibits capture, replacement and unregistered attempts')
        return self.delegate.reserve(stage, kind, identity, resource=resource, requested=requested)


class GuardedPolicyCollector(MainCollector):
    """Original collector semantics with explicit existing-source and bank gates."""
    def __init__(self, engine, config, ledger, stage, *, bank_version, _validated=None):
        _require_main(config, stage)
        self.deployment_inputs = deepcopy(_validated if _validated is not None else validate_deployment_inputs(config, bank_version))
        if (stage != STAGE or self.deployment_inputs['bank_version'] != bank_version
                or self.deployment_inputs['config_binding_sha256'] != canonical_hash(config)):
            raise ValueError('Validated deployment binding does not match the collector config')
        super().__init__(engine, config, _PolicyLedger(ledger, self.deployment_inputs), stage, bank_version=bank_version)

    def capture(self, case):
        raise ValueError('Policy deployment forbids source capture and replacement')

    def _authorize(self, case):
        identity = case.get('episode_id')
        row = self.deployment_inputs['sources'].get(identity)
        if row is None or case != row['case'] or case.get('replacement_of'):
            raise ValueError('Policy deployment permits only the original 100 resolved development sources')
        if canonical_hash(self.config) != self.deployment_inputs['config_binding_sha256']:
            raise ValueError('Deployment configuration changed after validation')
        _file(Path(row['source_path'])/'complete.json', row['source_seal_sha256'])
        _completed(row['resolution_path'], row['resolution_seal_sha256'], protocol=self.deployment_inputs['old_protocol_sha256'])
        super()._authorize(case)

    def _bank(self, case, source, cut):
        bank, plans, metadata = super()._bank(case, source, cut)
        report = compare_bank_identity(self.deployment_inputs, case, bank, self.protocol_sha256)
        folder = ROOT/'policy_guard'/self.stage/self.bank_version/case['episode_id']
        if folder.exists():
            _sealed(folder, [self.protocol_sha256])
            if _read(folder/'bank_check.json') != report:
                raise ValueError('Recorded deployment bank identity check changed')
        else:
            folder.mkdir(parents=True, exist_ok=False)
            dump(folder/'bank_check.json', report)
            seal(folder, protocol_sha256=self.protocol_sha256, role='policy_deployment_bank_check')
        return bank, plans, metadata

    def prepare_bank(self, case, source, cut_step):
        result = super().prepare_bank(case, source, cut_step)
        self._bank(case, source, cut_step)
        return result

    def collect_episode(self, case):
        # Check the old source BEFORE the base method's missing-source fallback.
        self._authorize(case)
        return super().collect_episode(case)


def create_policy_collector(config, stage, *, bank_version, ledger=None):
    """Authorization and all 100 sealed inputs precede any engine construction."""
    _require_main(config, stage)
    inputs = validate_deployment_inputs(config, bank_version)
    if stage != inputs['stage']:
        raise ValueError('Deployment stage mismatch')
    from .engine import create_engine
    engine = create_engine(config, stage)
    try:
        return GuardedPolicyCollector(engine, config, ledger if ledger is not None else AttemptLedger(config),
                                      stage, bank_version=bank_version, _validated=inputs)
    except BaseException:
        engine.close()
        raise


def collect_existing_slot(collector, primary):
    """Use this instead of main_runner.resolve_slot; never creates a resolution."""
    if not isinstance(collector, GuardedPolicyCollector):
        raise TypeError('Existing-slot execution requires the guarded policy collector')
    from .main_runner import _slot_lock
    with _slot_lock(primary['episode_id']):
        destination = collector.collect_episode(primary)
        summary = _read(destination/'summary.json')
        row = collector.deployment_inputs['sources'][primary['episode_id']]
    return dict(status='complete', planned_slot_id=primary['episode_id'],
        resolved_episode_id=primary['episode_id'], completion_path=str(destination),
        completion_sha256=sha256(destination/'complete.json'), resolution_path=row['resolution_path'],
        actual_branch_count=summary['actual_branch_count'], no_cut=summary['no_cut'], ordered_rejections=[])
