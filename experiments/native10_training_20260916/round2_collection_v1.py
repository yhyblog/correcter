"""Isolated round2 labels13 collector; no model or simulator work on import.

New primary capture and the original ordered pre-action replacement chain are
allowed only under their separate released stages. No policy5 a0 comparison or
capture prohibition is inherited. All action construction remains MainCollector.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
import re

from .main_collection import MainCollector, LABEL_METHODS, SPLIT_REPLICATES, _read, _sealed
from .protocol import TASKS, canonical_hash, require_stage_budget, validate_manifest
from .storage import ROOT, AttemptLedger, sha256


STAGE = 'round2_labels'
SCOPE = 'round2_native10_local_labels'
BANK = 'round2_labels_v1'
REPLACEMENT_STAGE = 'technical_reserve'
REPLACEMENT_SCOPE = 'preregistered_initialization_replacements'
SELECTED_SEAL = '931c6f6043db92b5d9003eb2833dfc8edd0ab6c860a1979db3983cd7d893725f'
EFFECTIVE_CUT_POLICY = dict(policy='analysis_lead_v1',
    scheduled_priority={'15': [15, 5], '45': [45, 15, 5], '95': [95, 45, 15, 5]},
    no_alarm_training_priority=[15, 5], eligible='reached_live_midpoint_with_at_least_10_steps_remaining',
    original_request_fields_preserved=True)
UNCHANGED = ('episode_manifest', 'seed_namespace', 'source_horizon', 'prefix_horizon',
             'suffix_horizon', 'control_budget', 'gate_threshold', 'guidance', 'matching',
             'cpu', 'split_replicates', 'scene_identity', 'methods')


def _inside(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()) or path.is_relative_to((ROOT/'p0').resolve()):
        raise ValueError('Round2 binding must remain inside new workflow outputs, outside P0')
    return path


def _checked(path, digest):
    path = _inside(path)
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or sha256(path) != digest:
        raise ValueError('Round2 bound file SHA changed: '+str(path))
    return path


def _complete(path, digest):
    path = _inside(path)
    _checked(path/'complete.json', digest)
    record = _read(path/'complete.json')
    _sealed(path, [record.get('protocol_sha256')])
    return record


def _selected(config, binding, registration):
    if binding['selected_seal_sha256'] != SELECTED_SEAL:
        raise ValueError('Round2 only permits the fixed B200 selected seal')
    path = _inside(binding['path']); selected = path/'selected'
    training_seal = _complete(path, binding['seal_sha256'])
    selected_seal = _complete(selected, binding['selected_seal_sha256'])
    result, ranking = _read(path/'result.json'), _read(selected/'ranking.json')
    if (training_seal.get('role') != 'native10_two_path_training' or training_seal.get('phase') != 'round1'
            or result.get('status') != 'complete' or result.get('phase') != 'round1'
            or result.get('selection', {}).get('path') != 'B' or result['selection'].get('step') != 200
            or result.get('optimizer_updates') != 19200 or _inside(result['selected_assets']) != selected
            or _inside(config['critic_assets']) != selected
            or selected_seal.get('role') != 'four_member_critic_export'):
        raise ValueError('Round2 requires the completed fixed B200 training export')
    hashes = ranking.get('model_hashes', {})
    if (set(hashes) != {'0', '1', '2', '3'} or ranking.get('horizon') != 10 or ranking.get('a0_slot') != 0
            or any(record.get('model_hashes') != hashes for record in (result, training_seal, selected_seal))
            or registration['critic_member_hashes'] != hashes):
        raise ValueError('Round2 selected four-member hashes disagree')
    for member, digest in hashes.items():
        _checked(selected/f'models/refit/member_{member}/selected.pt', digest)
        if registration['model_hashes'].get('critic_'+member) != digest:
            raise ValueError('Round2 critic identity differs from the bank registration')
    if _read(path/'selected_reload_audit.json').get('status') != 'passed':
        raise ValueError('Round2 selected export reload audit did not pass')
    return dict(path=str(path), selected_path=str(selected), model_hashes=hashes,
                seal_sha256=binding['seal_sha256'], selected_seal_sha256=binding['selected_seal_sha256'])


def _scene_prefix(config):
    binding = config.get('round2_preparation', {}).get('scene_registry_before')
    if not isinstance(binding, dict):
        raise ValueError('Round2 requires the immutable pre-collection scene registry prefix')
    snapshot = _checked(binding['snapshot_path'], binding['sha256'])
    prefix = snapshot.read_bytes()
    live = _inside(binding['live_path'])
    if live != (ROOT/'scene_registry/entries.jsonl').resolve():
        raise ValueError('Round2 scene registry must use the existing shared registry')
    if (binding.get('bytes') != len(prefix) or binding.get('records') != len(prefix.splitlines())
            or prefix and not prefix.endswith(b'\n')):
        raise ValueError('Scene registry snapshot size/record boundary differs')
    with live.open('rb') as stream:
        if stream.read(len(prefix)) != prefix:
            raise ValueError('Existing scene registry prefix changed; append-only growth is permitted')
    return deepcopy(binding)


def validate_round2_inputs(config, bank_version=BANK, *, require_release=False):
    """Pure CPU binding validation; pending configs never authorize execution."""
    if bank_version != BANK:
        raise ValueError('Only round2_labels_v1 is registered for this collector')
    if (config.get('stage_release_scopes', {}).get(STAGE) != SCOPE
            or config.get('stage_release_scopes', {}).get(REPLACEMENT_STAGE) != REPLACEMENT_SCOPE):
        raise ValueError('Round2 and technical replacements require their separate exact release scopes')
    if require_release:
        require_stage_budget(config, STAGE)
        require_stage_budget(config, REPLACEMENT_STAGE)
    limits = config['budget']
    if (limits['stages'][STAGE] != dict(simulator_attempts=17400, training_updates=0)
            or limits['stages'][REPLACEMENT_STAGE] != dict(simulator_attempts=1200, training_updates=0)
            or limits.get('hard_total') != 50000 or limits.get('training_update_total') != 51200
            or limits.get('count_failures') is not True or limits.get('count_retries') is not True):
        raise ValueError('Round2 budgets must preserve 17400 main, 1200 shared reserve and zero updates')
    binding = config['round2_collection']
    if binding.get('schema') != 'native10_round2_collection_v1' or binding.get('effective_cut_policy') != EFFECTIVE_CUT_POLICY:
        raise ValueError('Round2 must explicitly resolve the original request fields using approved LEAD fallback')
    original = binding['original_collection']
    old_path = _checked(original['config_path'], original['config_sha256'])
    frozen_path = _checked(original['freeze_path'], original['freeze_sha256'])
    old, frozen = _read(old_path), _read(frozen_path)
    if frozen.get('files', {}).get(str(old_path)) != original['config_sha256']:
        raise ValueError('Original collection freeze does not bind its config')
    old_registration = old['main_collection']['banks'][original['bank_version']]
    registration = config['main_collection']['banks'][bank_version]
    if (registration.get('kind') != 'labels13' or registration.get('stage') != STAGE
            or registration.get('generation_round') != 2 or registration.get('cut_selection_policy') != 'analysis_lead_v1'):
        raise ValueError('Round2 must use generation round2 labels13 with approved source fallback')
    for key in UNCHANGED:
        if key not in old or config.get(key) != old[key]:
            raise ValueError('Round2 changed existing scientific/execution semantics: '+key)
    if config.get('split_replicates') != SPLIT_REPLICATES:
        raise ValueError('Round2 must retain four training suffix repeats')
    for key in ('replacement_candidates', 'replacement_capture_stage', 'concurrency'):
        if config['main_collection'].get(key) != old['main_collection'].get(key):
            raise ValueError('Round2 changed original replacement registry or concurrency: '+key)
    if (config['main_collection']['replacement_capture_stage'] != REPLACEMENT_STAGE
            or config['main_collection']['concurrency']['workers_per_gpu'] != 4):
        raise ValueError('Round2 requires the original shared replacement stage and 8x4 workers')
    if registration.get('random_seed_domain') != old_registration.get('random_seed_domain'):
        raise ValueError('Round2 changed the labels13 random seed domain')
    if any(registration['model_hashes'].get(key) != old_registration['model_hashes'][key]
           for key in ('vla', 'd', 'g0', 'implementation')):
        raise ValueError('Round2 must preserve VLA/D/G0 and existing collection implementation')
    lookup = validate_manifest(old['episode_manifest'])
    primaries = [row for row in old['episode_manifest'] if row['split'] == 'train'
                 and row.get('round') == 2 and not row.get('replacement_of')]
    ids = [row['episode_id'] for row in primaries]
    if (len(ids) != 300 or set(row['env_seed'] for row in primaries) != set(range(2026111300, 2026111600))
            or registration.get('episode_ids') != ids or Counter(row['task'] for row in primaries) != Counter({task: 60 for task in TASKS})):
        raise ValueError('Round2 must retain the original ordered 300 primary train round2 episodes')
    requested = {row['episode_id']: row['cut_rule'] for row in primaries}
    if binding.get('requested_cut_rules_sha256') != canonical_hash(requested):
        raise ValueError('Original round2 requested cut fields changed')
    counter, expected_radii, cases = defaultdict(int), {}, {}
    for row in primaries:
        identity, task = row['episode_id'], row['task']
        index = counter[task]; counter[task] += 1
        expected_radii[identity] = .5 if (index//2) % 2 == 0 else 1.
        if row.get('case_id') != identity or row.get('source_horizon') != 10:
            raise ValueError('Round2 primary case identity/horizon changed')
        cases[identity] = deepcopy(row)
        backups = config['main_collection']['replacement_candidates'].get(identity, [])
        if len(backups) != 2 or len(set(backups)) != 2:
            raise ValueError('Each round2 primary must retain exactly two ordered registered backups')
        for backup in backups:
            candidate = lookup[backup]
            if (candidate.get('replacement_of') != identity or candidate.get('case_id') != backup
                    or any(candidate.get(key) != row.get(key) for key in ('task', 'split', 'round', 'cut_rule', 'source_horizon'))):
                raise ValueError('Round2 backup changed its inherited source registration')
            cases[backup] = deepcopy(candidate)
    for task in TASKS:
        rules = [row['cut_rule'] for row in primaries if row['task'] == task]
        if (Counter(rule['kind'] for rule in rules) != Counter(first_alarm=30, scheduled=30)
                or Counter(rule.get('step') for rule in rules if rule['kind'] == 'scheduled') != Counter({15: 10, 45: 10, 95: 10})):
            raise ValueError('Round2 must preserve 30 alarm and 30 scheduled cuts per task')
    if registration.get('channel_radius_by_episode') != expected_radii:
        raise ValueError('Round2 labels13 radius assignment changed from per-task adjacent-pair balancing')
    selected = _selected(config, binding['selected_training'], registration)
    scene = _scene_prefix(config)
    return dict(status='passed', stage=STAGE, scope=SCOPE, bank_version=bank_version,
        episode_ids=ids, cases=cases, primary_capture_limit=300, planned_primary_sources=300,
        expected_max_attempts=17400, replacement_stage=REPLACEMENT_STAGE,
        selected_training=selected, scene_registry_before=scene,
        config_binding_sha256=canonical_hash(config), simulator_calls=0, model_calls=0,
        optimizer_updates=0, old_guided_action_reuse_allowed=False, cross_bank_a0_identity_required=False)


class _Round2Ledger:
    def __init__(self, delegate, inputs):
        self.delegate, self.inputs = delegate, inputs

    def reserve(self, stage, kind, identity, *, resource='simulator_attempts', requested=1):
        if resource != 'simulator_attempts' or type(requested) is not int or requested != 1:
            raise ValueError('Round2 collector cannot reserve optimizer updates or batches')
        value = str(identity); cases = self.inputs['cases']
        if kind == 'source_capture':
            case = cases.get(value)
            expected = REPLACEMENT_STAGE if case and case.get('replacement_of') else STAGE
            allowed = case is not None and stage == expected
        else:
            parts = value.split('/'); allowed = False
            if stage == STAGE and kind == 'candidate_restore' and len(parts) == 4:
                allowed = parts[:2] == ['banks', BANK] and parts[2] in cases and _legal_cut(parts[3])
            if stage == STAGE and kind == 'branch_including_restore' and len(parts) == 7:
                allowed = (parts[:3] == ['rollouts', STAGE, BANK] and parts[3] in cases
                    and _legal_cut(parts[4]) and parts[5] in LABEL_METHODS and parts[6] in {f'repeat_{i}' for i in range(4)})
        if not allowed:
            raise ValueError('Round2 attempt is outside the registered stage/kind/source/candidate interface')
        return self.delegate.reserve(stage, kind, value, resource=resource, requested=requested)


def _legal_cut(value):
    return bool(re.fullmatch(r'cut[0-9]{3}', value)) and 5 <= int(value[3:]) <= 285 and int(value[3:]) % 10 == 5


class Round2Collector(MainCollector):
    def __init__(self, engine, config, ledger, stage=STAGE, *, bank_version=BANK, _validated=None):
        inputs = deepcopy(_validated if _validated is not None else validate_round2_inputs(config, bank_version, require_release=True))
        if stage != STAGE or inputs['config_binding_sha256'] != canonical_hash(config):
            raise ValueError('Round2 collector config differs from validated inputs')
        self.round2_inputs = inputs
        super().__init__(engine, config, _Round2Ledger(ledger, inputs), stage, bank_version=bank_version)
        self.loaded_identity = self.actual_loaded_identity()

    def actual_loaded_identity(self):
        selector = self.engine.selector
        selected = Path(self.round2_inputs['selected_training']['selected_path'])
        if Path(selector.assets_dir).resolve() != selected.resolve():
            raise ValueError('Actual loaded critic directory differs from fixed B200')
        expected_paths = [selected/f'models/refit/member_{member}/selected.pt' for member in self.critic_hashes]
        if [Path(path).resolve() for path in selector.model_paths] != [path.resolve() for path in expected_paths]:
            raise ValueError('Actual loaded critic member paths differ from fixed B200')
        selector.verify(check_files=True)
        self._verify_models()
        return dict(status='passed', selected_path=str(selected), model_hashes=deepcopy(selector.ranking['model_hashes']),
            model_paths=[str(path) for path in expected_paths], selected_seal_sha256=SELECTED_SEAL,
            checks=['actual_selector_paths', 'checkpoint_file_sha', 'frozen_parameter_buffer_versions', 'eval_cpu_no_parameter_grad'],
            candidate_generation_only=True, optimizer_updates=0)

    def _authorize(self, case):
        if (self.round2_inputs['cases'].get(case.get('episode_id')) != case
                or canonical_hash(self.config) != self.round2_inputs['config_binding_sha256']):
            raise ValueError('Round2 case or frozen config changed')
        # Inherited authorization verifies ordered, sealed pre-action rejections
        # before any backup can be captured; outcomes cannot activate backups.
        super()._authorize(case)


def create_round2_collector(config, stage=STAGE, *, bank_version=BANK, ledger=None):
    inputs = validate_round2_inputs(config, bank_version, require_release=True)
    if stage != STAGE:
        raise ValueError('Round2 factory cannot enter another stage')
    from .engine import create_engine
    engine = create_engine(config, stage)
    try:
        return Round2Collector(engine, config, ledger if ledger is not None else AttemptLedger(config),
                               stage, bank_version=bank_version, _validated=inputs)
    except BaseException:
        engine.close()
        raise


def collect_round2_slot(collector, primary):
    if not isinstance(collector, Round2Collector) or primary.get('replacement_of'):
        raise ValueError('Round2 slot entry requires the guarded collector and an original primary')
    if primary.get('episode_id') not in collector.round2_inputs['episode_ids']:
        raise ValueError('Round2 slot is outside the original 300 primaries')
    from .main_runner import resolve_slot
    return resolve_slot(collector, primary)
