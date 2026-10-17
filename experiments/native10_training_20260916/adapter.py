"""Real-runtime collection semantics, with injected engine for CPU contract tests.

No source is replaced based on outcome. No writes go to legacy repositories.
A counted capture includes its full normal prefix; a counted branch includes
physical restoration of that prefix plus its continuation. Candidate-only
restoration is separately counted because it resets/replays a simulator.
"""
from __future__ import annotations
from collections import deque
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from ac_tmil.idea3.local_collection import Trace
from .semantics import Native10Queue, QueueSnapshot, make_branch_prefix, execute_prefix
from .protocol import source_seed, suffix_seed, episode_key, validate_manifest, seed_for
from .storage import ROOT, arrays, dump, seal, sha256


def digest(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def cpu_values(batch):
    return {name: (value[0].detach().cpu().numpy() if hasattr(value, 'detach') else np.asarray(value)[0])
            for name, value in batch.items()}


class Native10Collector:
    def __init__(self, engine, config, ledger, stage):
        self.engine, self.config, self.ledger, self.stage = engine, config, ledger, stage
        self.runtime = engine.runtime
        self.namespace = config['seed_namespace']
        self.budget = config['control_budget']
        if self.budget != 300 or config['source_horizon'] != 10:
            raise ValueError('This workflow fixes control budget 300 and native10')

    def _case(self, case):
        key = episode_key(case['task'], case['env_seed'])
        registry = validate_manifest(self.config['episode_manifest'])
        if key not in registry or case != registry[key] or case.get('case_id') != key:
            raise ValueError('Case/split/cut rule differs from preregistered episode')
        return key

    def _record_plan(self, trace, plan, seed, stats):
        trace.plans.append(plan.copy())
        trace.generated.append(trace.step)
        trace.seeds.append(seed)
        trace.sampling_steps.append(trace.step)
        trace.policy_calls += stats['policy_calls']
        trace.policy_seconds += stats['seconds']

    def capture(self, case):
        """Capture a first alarm or a preregistered midpoint; retain every case."""
        self._case(case)
        dest = ROOT / 'sources' / case['case_id']
        attempt = self.ledger.reserve(self.stage, 'source_capture', case['case_id'])
        dest.mkdir(parents=True, exist_ok=False)
        dump(dest/'attempt.json', attempt)
        begin = time.perf_counter()
        self.runtime.reset(case, 10)
        trace = Trace(self.runtime)
        queue = Native10Queue(budget=self.budget)
        frames, props = deque(maxlen=5), deque(maxlen=5)
        language = self.runtime.backend.encode_instruction(self.runtime.instruction)
        events, cuts = [], []
        decision_index = 0
        rule = case.get('cut_rule', {'kind': 'first_alarm'})
        if rule['kind'] not in ('first_alarm', 'scheduled'):
            raise ValueError('Unknown preregistered cut rule')
        if rule['kind'] == 'scheduled' and (rule['step'] % 10 != 5 or not 5 <= rule['step'] <= 285):
            raise ValueError('Scheduled cut must be a legal midpoint with a full ten-step window')
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
                exceeds = monitor['gate'] > self.config['gate_threshold']
                eligible = queue.alarm_eligible(t) and t + 10 <= self.budget
                alarm = bool(exceeds and eligible)
                selected = alarm if rule['kind'] == 'first_alarm' else eligible and t == rule['step']
                events.append(dict(step=t, plan_age=queue.age, exceeds_threshold=bool(exceeds),
                    interruption_eligible=bool(eligible), alarm=alarm, selected_cut=bool(selected),
                    intervention_executed=False, **monitor))
                if selected:
                    cut = dest / f'cut{t:03d}'
                    cut.mkdir()
                    snapshot = queue.snapshot(t)
                    arrays(cut/'context.npz', **cpu_values(observed), full_plan=snapshot.raw_plan)
                    dump(cut/'anchor.json', dict(case_id=case['case_id'], episode_key=episode_key(case['task'], case['env_seed']),
                        task=case['task'], step=t, cut_rule=rule, queue=snapshot.to_dict(include_plan=False),
                        source_horizon=10, image_sha256=digest(self.runtime.frame()),
                        world_fingerprint=self.runtime.fingerprint(), gate=monitor['gate'],
                        trigger=alarm, next_source_decision_index=decision_index,
                        environment_command_semantics='unmodified native raw commands'))
                    cuts.append(t)
                    break
            trace.execute(self.runtime, queue.pop(t))
        arrays(dest/'trajectory.npz', **trace.arrays())
        no_cut = not cuts
        dump(dest/'summary.json', dict(status='complete', case=case, episode_id=case['episode_id'],
            task=case['task'],env_seed=case['env_seed'],split=case['split'],cuts=cuts, events=events,
            no_cut=no_cut, no_alarm=not any(event['alarm'] for event in events),
            success=bool(any(trace.successes)), steps=trace.step,
            end_reason=('selected_cut' if cuts else 'success' if any(trace.successes)
                        else 'environment_done' if trace.terminal else 'control_budget'),
            full_episode_outcome_available=no_cut, planned_episode_retained=True,
            outcome_filter_applied=False, policy_calls=trace.policy_calls, policy_seconds=trace.policy_seconds,
            environment_seconds=trace.environment_seconds, wall_seconds=time.perf_counter()-begin,
            budget_attempt=attempt['number'], capture_includes_prefix=True))
        self.engine.verify()
        seal(dest, protocol_sha256=self.config['analysis_approval']['protocol_sha256'])
        return dest

    def restore(self, case, source, cut_step):
        """Internal restore: caller must already reserve its containing attempt."""
        self._case(case)
        source_meta=json.loads((Path(source)/'summary.json').read_text())
        if source_meta['case'] != case:
            raise ValueError('Source provenance differs from registered case')
        with np.load(Path(source)/'trajectory.npz') as archive:
            original = {name: archive[name].copy() for name in archive.files}
        anchor = json.loads((Path(source)/f'cut{cut_step:03d}/anchor.json').read_text())
        with np.load(Path(source)/f'cut{cut_step:03d}/context.npz') as archive:
            snapshot = QueueSnapshot.from_dict(anchor['queue'], raw_plan=archive['full_plan'])
        if snapshot.step != cut_step:
            raise ValueError('Anchor cut mismatch')
        self.runtime.reset(case, 10)
        trace = Trace(self.runtime)
        for t in range(cut_step+1):
            np.testing.assert_allclose(self.runtime.physics_state(), original['physics_states'][t], atol=1e-10, rtol=0)
            if t == cut_step:
                break
            trace.execute(self.runtime, original['actions'][t])
            np.testing.assert_allclose(trace.rewards[-1], original['rewards'][t], atol=1e-8, rtol=0)
            if trace.successes[-1] != bool(original['success_flags'][t]) or trace.terminal:
                raise ValueError('Restored prefix changed success/termination')
        if digest(self.runtime.frame()) != anchor['image_sha256'] or self.runtime.fingerprint() != anchor['world_fingerprint']:
            raise ValueError('Physical/image/RNG/control-clock replay mismatch')
        # Physical replay intentionally makes no model calls. The raw snapshot is
        # the entire valid queue state for normal continuation; hidden normalized
        # policy queues are never populated with these environment commands.
        return trace, snapshot, anchor

    def prepare_bank(self, case, source, cut_step):
        self._case(case)
        dest = ROOT/'candidates'/case['case_id']/f'cut{cut_step:03d}'
        attempt = self.ledger.reserve(self.stage, 'candidate_restore', f"{case['case_id']}:{cut_step}")
        dest.mkdir(parents=True, exist_ok=False)
        dump(dest/'attempt.json', attempt)
        start = time.perf_counter()
        _, snapshot, _ = self.restore(case, source, cut_step)
        restored = time.perf_counter()
        from corrector.critic import STATE_KEYS
        with np.load(Path(source)/f'cut{cut_step:03d}/context.npz') as archive:
            observed = {name: archive[name].copy() for name in STATE_KEYS}
        snapshot_hash = digest(snapshot.raw_plan)
        plans, metadata, directions = self.engine.make_bank(observed, case, cut_step)
        if digest(snapshot.raw_plan) != snapshot_hash:
            raise ValueError('Candidate generation changed saved normal queue')
        aliases = {'replan':'alarm_replan10', 'velocity_matched':'velocity', 'direct_matched':'direct', 'post_matched':'post'}
        plans = {aliases.get(name,name): plan for name,plan in plans.items()}
        arrays(dest/'plans.npz', **plans)
        arrays(dest/'directions.npz', **directions)
        from .candidates13 import construct_candidates13, DEFAULT_CONFIG
        channel_scale = .5 if (case['env_seed']//5)%2 == 0 else 1.
        preview, preview_meta, preview_directions = construct_candidates13(
            directions['raw_a0'], plans, directions['post_internal_metric_direction'],
            seed_for('training_bank_preview',case['episode_id'],cut_step,namespace=self.namespace),
            channel_scale, {key:self.config['matching'][key] for key in DEFAULT_CONFIG})
        arrays(dest/'preview13.npz', **preview)
        arrays(dest/'preview13_directions.npz', **preview_directions)
        dump(dest/'preview13_metadata.json', preview_meta)
        metadata['preview13'] = dict(generated=True,simulated=False,channel_radius_scale=channel_scale)
        metadata.update(restore_seconds=restored-start, generation_wall_seconds=time.perf_counter()-start,
                        budget_attempt=attempt['number'], saved_queue_unchanged=True)
        dump(dest/'generation.json', metadata)
        seal(dest, protocol_sha256=self.config['analysis_approval']['protocol_sha256'])
        return dest

    def branch(self, case, source, cut_step, method, plan, repeat):
        self._case(case)
        limit = self.config.get('heldout_replicates', 8) if case['split']=='heldout' else self.config['replicates']
        if isinstance(repeat, bool) or not isinstance(repeat, int) or not 0 <= repeat < limit:
            raise ValueError('Repeat outside preregistered range')
        if method not in self.config['methods']:
            raise ValueError('Method outside preregistered comparison')
        bank_reference = None
        if self.config.get('require_saved_bank', False):
            bank = ROOT/'candidates'/case['case_id']/f'cut{cut_step:03d}'
            bank_reference = dict(path=str(bank), seal_sha256=sha256(bank/'complete.json'))
            if method != 'continue_native10':
                with np.load(bank/'plans.npz') as archive:
                    np.testing.assert_array_equal(plan, archive[method])
        dest = ROOT/'rollouts'/self.stage/case['case_id']/f'cut{cut_step:03d}'/method/f'repeat_{repeat}'
        attempt = self.ledger.reserve(self.stage, 'branch_including_restore', str(dest.relative_to(ROOT)))
        dest.mkdir(parents=True, exist_ok=False)
        dump(dest/'attempt.json', attempt)
        begin = time.perf_counter()
        trace, snapshot, _ = self.restore(case, source, cut_step)
        restore_seconds = time.perf_counter()-begin
        prefix = make_branch_prefix(snapshot, method, plan)
        execution = execute_prefix(prefix, lambda command: trace.execute(self.runtime, command),
                                   lambda: trace.terminal, lambda: trace.step)
        endpoint_image = digest(self.runtime.frame())
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
        arrays(dest/'trajectory.npz', **trace.arrays())
        dump(dest/'summary.json', dict(status='complete', case_id=case['case_id'], episode_id=case['episode_id'], task=case['task'],
            env_seed=case['env_seed'], split=case['split'], cut_step=cut_step, method=prefix.method,
            repeat=repeat, paired_suffix_id=f"{case['episode_id']}:cut{cut_step}:repeat{repeat}",
            source_seal_sha256=sha256(Path(source)/'complete.json'),candidate_bank_reference=bank_reference,
            source_horizon=10, suffix_horizon=10, success=bool(any(trace.successes)),
            terminal_step=trace.step, requested_prefix_steps=prefix.requested_steps,
            actual_prefix_steps=execution.actual_steps, first_expected_resample=prefix.next_sample_step,
            first_actual_resample=suffix[0]['step'] if suffix else None, suffix_seeds=suffix,
            pairing='episode,cut,repeat,post-prefix decision index; sampling phases may differ',
            endpoint_image_sha256=endpoint_image, command_sha256=digest(prefix.commands),
            clipped_command_proxy_sha256=digest(np.clip(prefix.commands,-1,1)),
            raw_outside_unit_fraction=float((np.abs(prefix.commands)>1).mean()),
            restore_seconds=restore_seconds, policy_calls=trace.policy_calls, policy_seconds=trace.policy_seconds,
            environment_seconds=trace.environment_seconds, wall_seconds=time.perf_counter()-begin,
            budget_attempt=attempt['number'], restore_included_in_attempt=True,
            original_queue_remaining=snapshot.remaining_steps, normalized_queue_injection=False))
        self.engine.verify()
        seal(dest, protocol_sha256=self.config['analysis_approval']['protocol_sha256'])
        return dest
