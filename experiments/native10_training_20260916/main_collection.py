"""Versioned main collection, prepared separately from the immutable P0 runner.

No work runs on import. A later frozen config and READY must release the supplied
main stage. Register each version in ``config['main_collection']['banks']`` with
stage, kind (labels13/policy5), episode_ids, generation_round, model_hashes,
critic_member_hashes, random_seed_domain, cut_selection_policy='analysis_lead_v1', and (for
labels13) channel_radius_by_episode. Model hashes are flat SHA256 mappings;
``critic_<member>`` entries must equal the loaded selector's four checkpoint
hashes. vla/d/g0/implementation entries identify the launcher's frozen assets.

The launcher still owns whole-wave GPU lifecycle and code/large-asset freeze
verification. This collector uses no physical alias reuse: every reached label
source costs 13*4 candidate branches plus 4 normal branches, even when commands
coincide. Exact aliases are retained for dataset weighting and integrity checks.
"""
from __future__ import annotations

from copy import deepcopy
from collections import deque
import json
from pathlib import Path
import re
import time

import numpy as np

from .adapter import Native10Collector, Trace, cpu_values, digest
from .candidates13 import CANDIDATE_ORDER, DEFAULT_CONFIG, construct_candidates13
from .protocol import canonical_hash, require_stage_budget, seed_for, suffix_seed
from .semantics import Native10Queue, execute_prefix, make_branch_prefix
from .storage import ROOT, AttemptLedger, arrays, dump, seal, sha256


POLICY_METHODS = ('continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post')
LABEL_METHODS = tuple(CANDIDATE_ORDER)+('continue_native10',)
STATE_KEYS = ('history', 'history_mask', 'proprio', 'proprio_mask', 'past_actions', 'language', 'remaining')
EARLY_ANCHORS = (5, 15, 45, 95)
SCHEDULED_PRIORITY = {15: (15, 5), 45: (45, 15, 5), 95: (95, 45, 15, 5)}
SPLIT_REPLICATES = dict(train=4, development=4, calibration=2, heldout=4)


class MainSourceRejected(RuntimeError):
    """Only these recorded pre-action rejections can activate registered backups."""
    def __init__(self, record):
        self.record = record
        self.reason = record['reason']
        self.before_first_action = record['before_first_action']
        super().__init__(self.reason+': '+record['episode_id'])


def _capture_scene(runtime, case, attempt, config, destination):
    from .scene_identity import capture_scene_identity
    return capture_scene_identity(runtime, case, attempt, config, destination)


def select_cut(case, available_legal_cuts, first_legal_alarm_step):
    """Fixed reachability/alarm-only rule; outcome labels are not arguments."""
    available = sorted(set(available_legal_cuts))
    if any(type(step) is not int or step % 10 != 5 or not 5 <= step <= 285 for step in available):
        raise ValueError('Only live midpoint anchors with ten-step budget are eligible')
    rule, training = case.get('cut_rule', {'kind': 'first_alarm'}), case['split'] == 'train'
    if first_legal_alarm_step is not None and first_legal_alarm_step not in available:
        raise ValueError('First legal alarm must have a saved live anchor')
    kind = rule['kind']
    if kind == 'scheduled':
        if not training or rule.get('step') not in SCHEDULED_PRIORITY:
            raise ValueError('Only training may use scheduled targets 15/45/95')
        requested = rule['step']
        priority = list(SCHEDULED_PRIORITY[requested])
        selected = next((step for step in priority if step in available), None)
        reason = 'no_legal_cut' if selected is None else 'scheduled_target_reached' if selected == requested else 'scheduled_prior_anchor_fallback'
    elif kind == 'first_alarm':
        requested = None
        priority = [first_legal_alarm_step] if first_legal_alarm_step is not None else [15, 5] if training else []
        selected = next((step for step in priority if step in available), None)
        reason = ('first_legal_alarm' if first_legal_alarm_step is not None else
                  'no_alarm_training_anchor_fallback' if selected is not None else
                  'no_legal_cut' if training else 'no_alarm_policy_common_outcome')
    else:
        raise ValueError('Unknown registered cut rule')
    category = ('missing' if selected is None else 'alarm' if reason == 'first_legal_alarm' else
                'scheduled' if reason == 'scheduled_target_reached' else 'fallback')
    return dict(requested_cut=requested, actual_cut=selected, selection_reason=reason, selection_category=category,
        available_legal_cuts=available, first_legal_alarm_step=first_legal_alarm_step,
        selection_audit=dict(available_legal_cuts=available, first_legal_alarm_step=first_legal_alarm_step,
            priority_order=priority, training_fallback_allowed=training, selection_uses_outcome_labels=False,
            policy='analysis_lead_v1'))


def _require_main(config, stage):
    scope = config.get('stage_release_scopes', {}).get(stage, '')
    if stage == 'p0' or scope == 'p0_anchor_and_native10_diagnostics':
        raise ValueError('Main collection cannot use the P0 stage or release scope')
    return require_stage_budget(config, stage)


def _bit_equal(first, second):
    first, second = np.asarray(first), np.asarray(second)
    return first.shape == second.shape and first.dtype == second.dtype and first.tobytes() == second.tobytes()


def _read(path):
    return json.loads(Path(path).read_text())


def _sealed(folder, allowed_protocols):
    folder = Path(folder)
    record = _read(folder/'complete.json')
    if record.get('status') != 'complete' or record.get('protocol_sha256') not in allowed_protocols:
        raise ValueError('Completed artifact protocol is not registered for this bank')
    paths = {str(path.relative_to(folder)) for path in folder.rglob('*')
             if path.is_file() and path != folder/'complete.json'}
    if paths != set(record['files']):
        raise ValueError('Completed artifact file list changed')
    for relative, expected in record['files'].items():
        path = (folder/relative).resolve()
        if not path.is_relative_to(folder.resolve()) or sha256(path) != expected:
            raise ValueError('Completed artifact SHA changed')
    return record


def _load_arrays(path):
    with np.load(path, allow_pickle=False) as archive:
        return {name: archive[name].copy() for name in archive.files}


def _score_bank(engine, observed, raw_a0, plans):
    # FrozenObjective fixes observed state and slot-zero a0 for every evaluation.
    from corrector.guidance import FrozenObjective
    objective = FrozenObjective(observed, np.clip(raw_a0, -1, 1), selector=engine.selector)
    scores = {name: objective.evaluate(np.clip(plan[:10], -1, 1)) for name, plan in plans.items()}
    objective.verify()
    return scores


class MainCollector(Native10Collector):
    """Reuse the tested capture/replay/raw-prefix semantics with versioned banks."""

    def __init__(self, engine, config, ledger, stage, *, bank_version):
        _require_main(config, stage)
        if not isinstance(bank_version, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', bank_version):
            raise ValueError('bank_version must be one safe registered path component')
        registration = config.get('main_collection', {}).get('banks', {}).get(bank_version)
        if not isinstance(registration, dict) or registration.get('stage') != stage:
            raise ValueError('Bank version and stage must be preregistered in the frozen config')
        self.registration = deepcopy(registration)
        self.bank_version = bank_version
        self.bank_kind = registration.get('kind')
        if self.bank_kind not in ('labels13', 'policy5'):
            raise ValueError('Bank kind must be labels13 or policy5')
        ids = registration.get('episode_ids', [])
        if not ids or len(ids) != len(set(ids)):
            raise ValueError('Bank requires unique preregistered episode_ids')
        self.allowed_episodes = frozenset(ids)
        self.model_hashes = deepcopy(registration.get('model_hashes', {}))
        required = {'vla', 'd', 'g0', 'implementation'}
        if not required <= set(self.model_hashes) or any(not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value)
                                                       for value in self.model_hashes.values()):
            raise ValueError('Model identity requires frozen vla/d/g0/implementation SHA256 hashes')
        self.critic_hashes = deepcopy(registration.get('critic_member_hashes', {}))
        if len(self.critic_hashes) != 4 or any(self.model_hashes.get('critic_'+str(member)) != value
                                              for member, value in self.critic_hashes.items()):
            raise ValueError('Exactly four critic member hashes must be included in model_hashes')
        if registration.get('generation_round') not in (1, 2):
            raise ValueError('Generation round must be one or two')
        if registration.get('cut_selection_policy') != 'analysis_lead_v1':
            raise ValueError('Main source selection must register the approved analysis_lead_v1 fallback')
        if not isinstance(registration.get('random_seed_domain'), str) or not registration['random_seed_domain']:
            raise ValueError('An outcome-independent candidate random seed domain is required')
        if self.bank_kind == 'labels13':
            radii = registration.get('channel_radius_by_episode', {})
            if set(radii) != set(ids) or any(isinstance(value, bool) or value not in (.5, 1.) for value in radii.values()):
                raise ValueError('Each label episode needs a preregistered .5 or 1 channel radius')
        self.model_identity_sha256 = canonical_hash(self.model_hashes)
        self.protocol_sha256 = config['analysis_approval']['protocol_sha256']
        super().__init__(engine, config, ledger, stage)
        if config.get('split_replicates') != SPLIT_REPLICATES:
            raise ValueError('EVAL20 fixes split_replicates to train4/development4/calibration2/heldout4')
        manifest = {case['episode_id']: case for case in config['episode_manifest']}
        if not set(ids) <= set(manifest):
            raise ValueError('Bank references episodes outside the frozen manifest')
        for identity in ids:
            self._case(manifest[identity])
        self._verify_models()

    def _case(self, case):
        key = super()._case(case)
        primary = case.get('replacement_of', case['episode_id'])
        if primary not in self.allowed_episodes or case['split'] == 'p0':
            raise ValueError('Episode is outside this registered main bank')
        if primary != case['episode_id']:
            registered = self.config['main_collection'].get('replacement_candidates', {}).get(primary, [])
            if case['episode_id'] not in registered:
                raise ValueError('Backup is not in this primary slot ordered replacement registry')
            lookup = {row['episode_id']: row for row in self.config['episode_manifest']}
            original = lookup[primary]
            for field in ('task', 'split', 'round', 'cut_rule'):
                if case.get(field) != original.get(field):
                    raise ValueError('Replacement must inherit primary task/split/round/cut rule')
        allowed = {'train', 'development'} if self.bank_kind == 'labels13' else {'development', 'calibration', 'heldout'}
        if case['split'] not in allowed:
            raise ValueError('Episode split is incompatible with bank purpose')
        if case['split'] == 'train' and case.get('round') != self.registration['generation_round']:
            raise ValueError('Training source round differs from frozen generation critic round')
        rule = case.get('cut_rule', {'kind': 'first_alarm'})
        if rule['kind'] == 'scheduled' and (case['split'] != 'train' or rule.get('step') not in SCHEDULED_PRIORITY):
            raise ValueError('Scheduled cuts are restricted to registered training targets 15/45/95')
        if rule['kind'] not in ('scheduled', 'first_alarm'):
            raise ValueError('Unknown registered cut rule')
        return key

    def _authorize(self, case):
        _require_main(self.config, self.stage)
        self._case(case)
        if self.registration != self.config['main_collection']['banks'][self.bank_version]:
            raise ValueError('Bank registration changed after collector construction')
        if case.get('replacement_of'):
            primary = case['replacement_of']
            backups = self.config['main_collection']['replacement_candidates'][primary]
            preceding = [primary]+backups[:backups.index(case['episode_id'])]
            for identity in preceding:
                folder = ROOT/'sources'/identity
                _sealed(folder, [self.protocol_sha256]+self.registration.get('allowed_source_protocol_sha256', []))
                rejection = _read(folder/'rejection.json')
                if rejection.get('before_first_action') is not True or rejection.get('reason') not in (
                        'duplicate_initial_scene', 'initialization_failed') or rejection.get('episode_id') != identity or (
                        rejection.get('outcome_not_observed') is not True or rejection.get('success') is not None
                        or rejection.get('control_steps_executed') != 0 or rejection.get('planned_slot_id') != primary):
                    raise ValueError('Backup requires each prior candidate to be rejected before its first action')
        self._verify_models()

    def _verify_models(self):
        if self.engine.selector.ranking['model_hashes'] != self.critic_hashes:
            raise ValueError('Loaded critic differs from registered generation model hashes')
        self.engine.verify()

    def methods(self):
        return LABEL_METHODS if self.bank_kind == 'labels13' else POLICY_METHODS

    def repeats(self, case):
        return self.config['split_replicates'][case['split']]

    def bank_path(self, case, cut):
        return ROOT/'banks'/self.bank_version/case['case_id']/f'cut{cut:03d}'

    def branch_path(self, case, cut, name, repeat):
        return ROOT/'rollouts'/self.stage/self.bank_version/case['case_id']/f'cut{cut:03d}'/name/f'repeat_{repeat}'

    def _source(self, case, source):
        expected = ROOT/'sources'/case['case_id']
        if Path(source).resolve() != expected.resolve():
            raise ValueError('Main source must be the registered native10 episode capture')
        protocols = [self.protocol_sha256]+self.registration.get('allowed_source_protocol_sha256', [])
        record = _sealed(source, protocols)
        summary = _read(Path(source)/'summary.json')
        if summary['case'] != case or not summary['planned_episode_retained'] or summary['outcome_filter_applied']:
            raise ValueError('Source identity or retained-episode contract changed')
        if summary.get('cut_selection_policy') != 'analysis_lead_v1':
            raise ValueError('Source did not implement the approved main fallback protocol')
        if any(summary.get('model_hashes', {}).get(key) != self.model_hashes[key] for key in ('vla', 'd', 'g0')):
            raise ValueError('Source VLA/D/G0 identity differs from the frozen main models')
        expected_selection = select_cut(case, summary['available_legal_cuts'], summary['first_legal_alarm_step'])
        if any(summary.get(key) != value for key, value in expected_selection.items()):
            raise ValueError('Source cut selection disagrees with registered reachability priority')
        saved = sorted(int(path.name[3:]) for path in Path(source).glob('cut[0-9][0-9][0-9]') if path.is_dir())
        if saved != summary['available_legal_cuts']:
            raise ValueError('Available legal cut list differs from saved anchors')
        selected = expected_selection['actual_cut']
        if summary['cuts'] != ([] if selected is None else [selected]):
            raise ValueError('Selected source cut list disagrees with fallback audit')
        return summary, record

    def _provenance(self, case, source, bank=None):
        source_seal = _read(Path(source)/'complete.json')
        return dict(episode_id=case['episode_id'], case_id=case['case_id'], task=case['task'], env_seed=case['env_seed'],
            split=case['split'], round=case.get('round'), generation_round=self.registration['generation_round'],
            planned_slot_id=case.get('replacement_of', case['episode_id']),
            bank_version=self.bank_version, bank_kind=self.bank_kind, stage=self.stage,
            protocol_sha256=self.protocol_sha256, source_protocol_sha256=source_seal['protocol_sha256'],
            source_seal_sha256=sha256(Path(source)/'complete.json'),
            candidate_bank_sha256=sha256(Path(bank)/'complete.json') if bank is not None else None,
            model_hashes=deepcopy(self.model_hashes), critic_member_hashes=deepcopy(self.critic_hashes),
            model_identity_sha256=self.model_identity_sha256,
            generation_critic_sha256=canonical_hash(self.critic_hashes), suffix_seed_namespace=self.namespace,
            suffix_protocol='native10_first_ten_raw_commands_v1')

    def capture(self, case):
        self._authorize(case)
        dest = ROOT/'sources'/case['case_id']
        if dest.exists():
            raise FileExistsError('Existing capture is immutable; never replace an episode to obtain a cut')
        capture_stage = self.stage
        if case.get('replacement_of'):
            capture_stage = self.config['main_collection'].get('replacement_capture_stage', 'technical_reserve')
            _require_main(self.config, capture_stage)
        attempt = self.ledger.reserve(capture_stage, 'source_capture', case['case_id'])
        dest.mkdir(parents=True, exist_ok=False)
        dump(dest/'attempt.json', attempt)
        begin = time.perf_counter()
        try:
            self.runtime.reset(case, 10)
        except Exception as error:
            self._reject_source(case, dest, attempt, 'initialization_failed',
                                detail=dict(exception=type(error).__name__, message=str(error)))
        scene = _capture_scene(self.runtime, case, attempt, self.config, dest/'initial_scene')
        if scene.get('status') == 'duplicate':
            self._reject_source(case, dest, attempt, 'duplicate_initial_scene', detail=scene)
        if scene.get('status') != 'accepted':
            raise ValueError('Initial scene audit did not accept the new physical state')
        trace, queue = Trace(self.runtime), Native10Queue(budget=self.budget)
        frames, props = deque(maxlen=5), deque(maxlen=5)
        language = self.runtime.backend.encode_instruction(self.runtime.instruction)
        rule = case.get('cut_rule', {'kind': 'first_alarm'})
        events, available, decision_index, first_alarm = [], [], 0, None
        from .protocol import source_seed
        while not trace.terminal and trace.step < self.budget:
            t = trace.step
            frames.append(self.runtime.frame().copy())
            props.append(self.runtime.proprio().copy())
            if queue.needs_plan(t):
                seed = source_seed(case, decision_index, namespace=self.namespace)
                plan, stats = self.engine.propose(seed)
                queue.replace(plan, t)
                self._record_plan(trace, plan, seed, stats)
                decision_index += 1
            if t % 5 == 0:
                observed = self.engine.context(frames, list(props), trace.actions[-4:], language, t)
                monitor = self.engine.monitor(observed, queue.peek_block(5, t))
                eligible = queue.alarm_eligible(t) and t+10 <= self.budget
                exceeds = monitor['gate'] > self.config['gate_threshold']
                alarm = bool(exceeds and eligible)
                first_here = alarm and first_alarm is None
                if first_here:
                    first_alarm = t
                primary = (alarm if rule['kind'] == 'first_alarm' else eligible and t == rule['step'])
                # Anchors are recorded before their next action, only while live.
                # Extra states are not independent episodes or extra simulations.
                save_anchor = eligible and (t in EARLY_ANCHORS or first_here or primary)
                if save_anchor:
                    cut = dest/f'cut{t:03d}'
                    cut.mkdir()
                    snapshot = queue.snapshot(t)
                    arrays(cut/'context.npz', **cpu_values(observed), full_plan=snapshot.raw_plan)
                    dump(cut/'anchor.json', dict(case_id=case['case_id'], episode_key=case['episode_id'],
                        task=case['task'], step=t, cut_rule=rule, queue=snapshot.to_dict(include_plan=False),
                        source_horizon=10, image_sha256=digest(self.runtime.frame()),
                        world_fingerprint=self.runtime.fingerprint(), gate=monitor['gate'], trigger=alarm,
                        next_source_decision_index=decision_index, live_nonterminal=True,
                        environment_command_semantics='unmodified native raw commands',
                        anchor_saved_without_outcome_selection=True))
                    available.append(t)
                events.append(dict(step=t, plan_age=queue.age, exceeds_threshold=bool(exceeds),
                    interruption_eligible=bool(eligible), alarm=alarm, selected_cut=False,
                    anchor_saved=bool(save_anchor), intervention_executed=False, **monitor))
                if primary:
                    break
            trace.execute(self.runtime, queue.pop(t))
        selection = select_cut(case, available, first_alarm)
        actual = selection['actual_cut']
        for event in events:
            event['selected_cut'] = event['step'] == actual
        full_outcome = trace.terminal or trace.step >= self.budget
        arrays(dest/'trajectory.npz', **trace.arrays())
        dump(dest/'summary.json', dict(status='complete', case=case, episode_id=case['episode_id'], task=case['task'],
            env_seed=case['env_seed'], split=case['split'], cuts=[] if actual is None else [actual], events=events,
            planned_slot_id=case.get('replacement_of', case['episode_id']), source_capture_stage=capture_stage,
            **selection, no_cut=actual is None, no_alarm=first_alarm is None,
            success=bool(any(trace.successes)), steps=trace.step,
            end_reason='success' if any(trace.successes) else 'environment_done' if trace.terminal
                       else 'control_budget' if trace.step >= self.budget else 'selected_primary_cut',
            full_episode_outcome_available=bool(full_outcome), planned_episode_retained=True,
            outcome_filter_applied=False, source_replaced=False, fallback_deployment_claim=False,
            source_horizon=10, control_budget=300, seed_namespace=self.namespace,
            scene_fingerprint=scene['scene_fingerprint'], exact_state_sha256=scene['exact_state_sha256'],
            initial_scene=scene, initial_scene_seal_sha256=sha256(dest/'initial_scene/complete.json'),
            cut_selection_policy='analysis_lead_v1', protocol_sha256=self.protocol_sha256,
            model_hashes=deepcopy(self.model_hashes), policy_calls=trace.policy_calls,
            policy_seconds=trace.policy_seconds, environment_seconds=trace.environment_seconds,
            wall_seconds=time.perf_counter()-begin, budget_attempt=attempt['number'], capture_includes_prefix=True))
        self._verify_models()
        seal(dest, protocol_sha256=self.protocol_sha256)
        return dest

    def _reject_source(self, case, dest, attempt, reason, detail):
        record = dict(status='rejected_before_first_action', reason=reason, before_first_action=True,
            episode_id=case['episode_id'], case=case, task=case['task'], split=case['split'],
            env_seed=case['env_seed'], planned_slot_id=case.get('replacement_of', case['episode_id']),
            budget_attempt=attempt['number'], protocol_sha256=self.protocol_sha256,
            model_hashes=deepcopy(self.model_hashes), details=detail,
            outcome_not_observed=True, success=None, control_steps_executed=0,
            source_replaced=False, replacement_requires_registered_order=True)
        dump(dest/'rejection.json', record)
        seal(dest, protocol_sha256=self.protocol_sha256, rejected_before_first_action=True)
        raise MainSourceRejected(record)

    def prepare_bank(self, case, source, cut_step):
        self._authorize(case)
        source_summary, _ = self._source(case, source)
        if source_summary['cuts'] != [cut_step]:
            raise ValueError('Bank cut must be the sole preregistered reached source cut')
        dest = self.bank_path(case, cut_step)
        if dest.exists():
            raise FileExistsError('Existing bank is immutable; use verified resume or a new registered version')
        attempt = self.ledger.reserve(self.stage, 'candidate_restore', str(dest.relative_to(ROOT)))
        dest.mkdir(parents=True, exist_ok=False)
        dump(dest/'attempt.json', attempt)
        begin = time.perf_counter()
        _, snapshot, _ = self.restore(case, source, cut_step)
        restored = time.perf_counter()
        context = _load_arrays(Path(source)/f'cut{cut_step:03d}'/'context.npz')
        observed = {name: context[name] for name in STATE_KEYS}
        queue_hash, world = digest(snapshot.raw_plan), self.runtime.fingerprint()
        formal, generation, original_directions = self.engine.make_bank(observed, case, cut_step)
        aliases = dict(replan='alarm_replan10', velocity_matched='velocity', direct_matched='direct', post_matched='post')
        formal = {aliases.get(name, name): plan for name, plan in formal.items()}
        raw = original_directions['raw_a0']
        if not _bit_equal(formal['alarm_replan10'], raw):
            raise ValueError('Formal replan changed raw a0')
        if self.bank_kind == 'labels13':
            random_seed = seed_for(self.registration['random_seed_domain'], case['episode_id'], cut_step, namespace=self.namespace)
            plans, metadata, directions = construct_candidates13(raw, formal,
                original_directions['post_internal_metric_direction'], random_seed,
                self.registration['channel_radius_by_episode'][case.get('replacement_of', case['episode_id'])],
                {name: self.config['matching'][name] for name in DEFAULT_CONFIG})
        else:
            plans = {name: formal[name] for name in POLICY_METHODS if name != 'continue_native10'}
            metadata = dict(schema='native10_policy5_bank_v1', candidate_order=list(plans),
                a0_name='alarm_replan10', normal_control_in_bank=False, retained_all=True)
            directions = dict(raw_a0=raw, critic_a0=np.clip(raw, -1, 1),
                critic_candidates=np.stack([np.clip(plan, -1, 1) for plan in plans.values()]))
        predictions = _score_bank(self.engine, observed, raw, plans)
        a0_name = 'a0' if self.bank_kind == 'labels13' else 'alarm_replan10'
        if predictions[a0_name]['mean_gain'] != 0:
            raise ValueError('Candidate scoring moved the designated a0 anchor')
        if digest(snapshot.raw_plan) != queue_hash or self.runtime.fingerprint() != world:
            raise ValueError('Bank generation/scoring changed saved normal queue or physical state')
        self._verify_models()
        arrays(dest/'plans.npz', **plans)
        arrays(dest/'directions.npz', **directions)
        arrays(dest/'formal_directions.npz', **original_directions)
        dump(dest/'metadata.json', metadata)
        dump(dest/'generation.json', dict(generation, **self._provenance(case, source), cut_step=cut_step,
            predictions13=predictions if self.bank_kind == 'labels13' else None,
            bank_predictions=predictions, budget_attempt=attempt['number'],
            restore_seconds=restored-begin, generation_wall_seconds=time.perf_counter()-begin,
            candidate_names=list(plans), saved_queue_unchanged=True, saved_before_any_branch=True,
            normal_control_in_critic=False, physical_outcome_reuse_enabled=False,
            registered_cut_rule=case.get('cut_rule', {'kind': 'first_alarm'}),
            raw_command_scoring='same clipped C(raw) used by fixed-a0 critic; raw commands are executed'))
        seal(dest, protocol_sha256=self.protocol_sha256, model_identity_sha256=self.model_identity_sha256)
        return dest

    def _bank(self, case, source, cut):
        bank = self.bank_path(case, cut)
        _sealed(bank, [self.protocol_sha256])
        generation = _read(bank/'generation.json')
        expected = self._provenance(case, source)
        for name, value in expected.items():
            if name != 'candidate_bank_sha256' and generation.get(name) != value:
                raise ValueError('Bank provenance mismatch: '+name)
        if generation['cut_step'] != cut or not generation['saved_queue_unchanged']:
            raise ValueError('Bank cut/queue provenance changed')
        return bank, _load_arrays(bank/'plans.npz'), _read(bank/'metadata.json')

    def branch(self, case, source, cut_step, candidate_name, plan, repeat):
        self._authorize(case)
        self._source(case, source)
        if candidate_name not in self.methods():
            raise ValueError('Candidate is not in the registered bank kind')
        if isinstance(repeat, bool) or not isinstance(repeat, int) or not 0 <= repeat < self.repeats(case):
            raise ValueError('Repeat is outside the registered range')
        bank, plans, metadata = self._bank(case, source, cut_step)
        normal = candidate_name == 'continue_native10'
        if normal and plan is not None:
            raise ValueError('Normal continuation cannot replace its original queue')
        if not normal and (plan is None or not _bit_equal(plan, plans[candidate_name])):
            raise ValueError('Branch plan must equal the saved raw bank plan bit-for-bit')
        dest = self.branch_path(case, cut_step, candidate_name, repeat)
        if dest.exists():
            raise FileExistsError('Existing branch is immutable; verify before resuming')
        attempt = self.ledger.reserve(self.stage, 'branch_including_restore', str(dest.relative_to(ROOT)))
        dest.mkdir(parents=True, exist_ok=False)
        dump(dest/'attempt.json', attempt)
        begin = time.perf_counter()
        trace, snapshot, _ = self.restore(case, source, cut_step)
        restore_seconds = time.perf_counter()-begin
        # All thirteen interventions share the already-tested ten-step prefix;
        # their training identity remains the original candidate_name below.
        role = 'continue_native10' if normal else 'alarm_replan10'
        prefix = make_branch_prefix(snapshot, role, None if normal else plan)
        execution = execute_prefix(prefix, lambda command: trace.execute(self.runtime, command),
                                   lambda: trace.terminal, lambda: trace.step)
        endpoint = digest(self.runtime.frame())
        suffix = []
        queue = Native10Queue(start_step=trace.step, budget=self.budget)
        while not trace.terminal and trace.step < self.budget:
            t = trace.step
            if queue.needs_plan(t):
                index = len(suffix)
                seed = suffix_seed(case, cut_step, repeat, index, namespace=self.namespace)
                raw, stats = self.engine.propose(seed)
                queue.replace(raw, t)
                self._record_plan(trace, raw, seed, stats)
                suffix.append(dict(step=t, decision_index=index, seed=seed, noise_sha256=stats.get('noise_sha256')))
            trace.execute(self.runtime, queue.pop(t))
        self._verify_models()
        arrays(dest/'trajectory.npz', **trace.arrays())
        alias = metadata.get('aliases', {}).get(candidate_name, candidate_name) if not normal else None
        dump(dest/'summary.json', dict(self._provenance(case, source, bank), status='complete',
            cut_step=cut_step, method=candidate_name, candidate_name=candidate_name, execution_role=role,
            candidate_slot=CANDIDATE_ORDER.index(candidate_name) if self.bank_kind == 'labels13' and not normal else None,
            critic_candidate=not normal, normal_control_in_critic=False, raw_command_alias=alias,
            physical_outcome_reused=False, repeat=repeat, budget_attempt=attempt['number'],
            paired_suffix_id=f"{case['episode_id']}:cut{cut_step}:repeat{repeat}",
            pairing='episode/cut/repeat/suffix decision index; arm absolute phases and states can differ',
            source_horizon=10, suffix_horizon=10, generated_horizon=50, success=bool(any(trace.successes)),
            terminal_step=trace.step, requested_prefix_steps=prefix.requested_steps,
            actual_prefix_steps=execution.actual_steps, first_expected_resample=prefix.next_sample_step,
            first_actual_resample=suffix[0]['step'] if suffix else None, suffix_seeds=suffix,
            endpoint_image_sha256=endpoint, command_sha256=digest(prefix.commands),
            clipped_command_proxy_sha256=digest(np.clip(prefix.commands, -1, 1)),
            raw_outside_unit_fraction=float((np.abs(prefix.commands) > 1).mean()),
            restore_seconds=restore_seconds, policy_calls=trace.policy_calls, policy_seconds=trace.policy_seconds,
            environment_seconds=trace.environment_seconds, wall_seconds=time.perf_counter()-begin,
            original_queue_remaining=snapshot.remaining_steps, restore_included_in_attempt=True,
            normalized_queue_injection=False))
        seal(dest, protocol_sha256=self.protocol_sha256, model_identity_sha256=self.model_identity_sha256)
        return dest

    def _completed_branch(self, case, source, bank, cut, name, repeat):
        folder = self.branch_path(case, cut, name, repeat)
        _sealed(folder, [self.protocol_sha256])
        summary = _read(folder/'summary.json')
        expected = dict(self._provenance(case, source, bank), cut_step=cut, candidate_name=name,
                        method=name, repeat=repeat, status='complete')
        if any(summary.get(key) != value for key, value in expected.items()):
            raise ValueError('Completed branch provenance differs; no unsafe trajectory reuse')
        return summary

    def collect_episode(self, case):
        """Authorized entry point; no implicit source replacement or failed retry."""
        self._authorize(case)
        dest = ROOT/'collections'/self.stage/self.bank_version/case['case_id']
        if dest.exists():
            _sealed(dest, [self.protocol_sha256])
            summary = _read(dest/'summary.json')
            if summary['model_hashes'] != self.model_hashes or summary['case'] != case:
                raise ValueError('Completed episode provenance changed')
            source = ROOT/'sources'/case['case_id']
            self._source(case, source)
            if summary['source_seal_sha256'] != sha256(source/'complete.json'):
                raise ValueError('Completed episode references a changed source seal')
            if summary['cuts']:
                cut = summary['cuts'][0]
                bank, _, _ = self._bank(case, source, cut)
                if summary['candidate_bank_sha256'] != sha256(bank/'complete.json'):
                    raise ValueError('Completed episode references a changed candidate seal')
                records = {(row['method'], row['repeat']): row for row in summary['branch_records']}
                expected = {(name, repeat) for name in self.methods() for repeat in range(self.repeats(case))}
                if set(records) != expected or len(records) != len(summary['branch_records']):
                    raise ValueError('Completed episode is missing registered branch records')
                for (name, repeat), row in records.items():
                    self._completed_branch(case, source, bank, cut, name, repeat)
                    if row['seal_sha256'] != sha256(self.branch_path(case, cut, name, repeat)/'complete.json'):
                        raise ValueError('Completed episode references a changed branch seal')
            return dest
        source = ROOT/'sources'/case['case_id']
        if not source.exists():
            self.capture(case)
        if (source/'rejection.json').exists():
            _sealed(source, [self.protocol_sha256])
            raise MainSourceRejected(_read(source/'rejection.json'))
        source_summary, _ = self._source(case, source)
        cut = source_summary['cuts'][0] if source_summary['cuts'] else None
        branch_rows, bank = [], None
        if cut is not None:
            bank = self.bank_path(case, cut)
            if not bank.exists():
                self.prepare_bank(case, source, cut)
            bank, plans, _ = self._bank(case, source, cut)
            rng = np.random.default_rng(seed_for('main_branch_order', case['episode_id'], cut,
                                                self.bank_version, namespace=self.namespace))
            for repeat in range(self.repeats(case)):
                for candidate_name in rng.permutation(self.methods()):
                    name = str(candidate_name)
                    branch = self.branch_path(case, cut, name, repeat)
                    if not branch.exists():
                        self.branch(case, source, cut, name, None if name == 'continue_native10' else plans[name], repeat)
                    branch_rows.append(self._completed_branch(case, source, bank, cut, name, repeat))
        elif not source_summary['full_episode_outcome_available']:
            raise ValueError('Missing cut cannot be replaced by an unknown common outcome')
        dest.mkdir(parents=True, exist_ok=False)
        dump(dest/'summary.json', dict(self._provenance(case, source, bank), status='complete', case=case,
            source_path=str(source), bank_path=str(bank) if bank else None, cuts=[] if cut is None else [cut],
            no_cut=cut is None, no_alarm=source_summary['no_alarm'],
            planned_episode_retained=True, outcome_filter_applied=False, source_replaced=False,
            registered_cut_rule=case.get('cut_rule', {'kind': 'first_alarm'}),
            cut_selection_policy=self.registration['cut_selection_policy'],
            requested_cut=source_summary['requested_cut'], actual_cut=source_summary['actual_cut'],
            selection_reason=source_summary['selection_reason'], selection_category=source_summary['selection_category'],
            selection_audit=source_summary['selection_audit'],
            missing_cut_reason=source_summary['end_reason'] if cut is None else None,
            common_outcome=bool(source_summary['success']) if cut is None else None,
            common_outcome_available=cut is None, fabricate_critic_input_for_no_cut=False,
            methods=list(self.methods()), replicates=self.repeats(case),
            logical_branch_count=len(self.methods())*self.repeats(case), actual_branch_count=len(branch_rows),
            candidate_bank_sha256=sha256(bank/'complete.json') if bank else None,
            branch_records=[dict(method=row['method'], repeat=row['repeat'], success=row['success'],
                budget_attempt=row['budget_attempt'], command_sha256=row['command_sha256'],
                summary_path=str(self.branch_path(case, cut, row['method'], row['repeat'])/'summary.json'),
                seal_sha256=sha256(self.branch_path(case, cut, row['method'], row['repeat'])/'complete.json')) for row in branch_rows]))
        seal(dest, protocol_sha256=self.protocol_sha256, model_identity_sha256=self.model_identity_sha256)
        return dest


def create_main_collector(config, stage, *, bank_version, ledger=None):
    """Explicit lazy factory; authorization precedes any GPU/runtime construction."""
    _require_main(config, stage)
    from .engine import create_engine
    engine = create_engine(config, stage)
    try:
        return MainCollector(engine, config, ledger if ledger is not None else AttemptLedger(config),
                             stage, bank_version=bank_version)
    except BaseException:
        engine.close()
        raise
