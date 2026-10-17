"""Read-only P0 verification and episode-level descriptive statistics.

Running the CLI writes only its new audit/report artifacts. It never constructs
an engine, resets an environment, samples a policy, reserves an attempt or fits
a model. ``technical`` gates the second P0 wave without an effectiveness claim;
``native20`` requires every registered episode and every applicable 5 x 4 arm.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from .protocol import candidate_seed, source_seed, suffix_seed, seed_for, validate_protocol
from .storage import ROOT, dump


METHODS = ('continue_native10', 'alarm_replan10', 'velocity', 'direct', 'post')
PRIMARY_COMPARISONS = (
    ('interruption', 'alarm_replan10', 'continue_native10'),
    ('velocity_correction', 'velocity', 'alarm_replan10'),
    ('direct_correction', 'direct', 'alarm_replan10'),
    ('post_correction', 'post', 'alarm_replan10'),
    ('direct_minus_velocity', 'direct', 'velocity'),
    ('post_minus_velocity', 'post', 'velocity'),
    ('post_minus_direct', 'post', 'direct'),
)
SYSTEM_COMPARISONS = tuple((name+'_system', name, 'continue_native10')
                           for name in ('velocity', 'direct', 'post'))
LEGACY_CASES = ('shelf-place-v3__2026104012', 'stick-pull-v3__2026104028',
                'disassemble-v3__2026104005')
BOOTSTRAP_SEED = 2026091613
BOOTSTRAP_DRAWS = 10000
PHYSICS_ATOL = 1e-10
REWARD_ATOL = 1e-8
COMMAND_ATOL = 1e-6


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _array_hash(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def _same(first, second):
    first, second = np.asarray(first), np.asarray(second)
    return first.shape == second.shape and first.dtype == second.dtype and first.tobytes() == second.tobytes()


def _close(first, second, tolerance):
    first, second = np.asarray(first), np.asarray(second)
    return first.shape == second.shape and bool(np.allclose(first, second, atol=tolerance, rtol=0))


def _ci(samples):
    return np.quantile(samples, [.025, .975]).astype(float).tolist()


def statistics(source_rows):
    """Task-stratified episode bootstrap; four suffixes stay inside their source."""
    outcomes = np.asarray([row['outcomes'] for row in source_rows], dtype=np.float64)
    if outcomes.shape != (20, 5, 4) or not np.isin(outcomes, [0, 1]).all():
        raise ValueError('Statistics require all 20 x 5 x 4 registered outcomes')
    means = outcomes.mean(axis=2)
    tasks = np.asarray([row['task'] for row in source_rows])
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.concatenate([
        rng.choice(np.flatnonzero(tasks == task), (BOOTSTRAP_DRAWS, int((tasks == task).sum())), replace=True)
        for task in sorted(set(tasks))
    ], axis=1)
    boot = means[draws].mean(axis=1)
    arm_stats = {}
    for index, method in enumerate(METHODS):
        arm_stats[method] = dict(success_rate=float(means[:, index].mean()),
            success_rate_ci95=_ci(boot[:, index]), episode_count=20,
            paired_outcome_slots=80, success_slots=int(outcomes[:, index].sum()),
            no_cut_slots_are_common_outcome_broadcast=True)

    def compare(key, treatment, reference):
        i, j = METHODS.index(treatment), METHODS.index(reference)
        rescue = (outcomes[:, i] == 1) & (outcomes[:, j] == 0)
        harm = (outcomes[:, i] == 0) & (outcomes[:, j] == 1)
        return dict(name=key, treatment=treatment, reference=reference,
            gain_pp=100*float((means[:, i]-means[:, j]).mean()),
            gain_ci95_pp=(100*np.asarray(_ci(boot[:, i]-boot[:, j]))).tolist(),
            rescue_count=int(rescue.sum()), harm_count=int(harm.sum()),
            discordant_count=int(rescue.sum()+harm.sum()),
            rescue_rate_pp=100*float(rescue.mean()), harm_rate_pp=100*float(harm.mean()),
            rescued_episodes=int(rescue.any(axis=1).sum()), harmed_episodes=int(harm.any(axis=1).sum()),
            both_rescue_and_harm_episodes=int((rescue.any(axis=1) & harm.any(axis=1)).sum()),
            episode_gain_pp=(100*(means[:, i]-means[:, j])).tolist())

    comparisons = {name: compare(name, first, second) for name, first, second in PRIMARY_COMPARISONS}
    systems = {name: compare(name, first, second) for name, first, second in SYSTEM_COMPARISONS}
    task_rows = {}
    for task in sorted(set(tasks)):
        take = tasks == task
        task_rows[task] = dict(episodes=int(take.sum()),
            cut_episodes=sum(bool(row['cuts']) for row in source_rows if row['task'] == task),
            no_cut_episodes=sum(not row['cuts'] for row in source_rows if row['task'] == task),
            success_rate={method: float(means[take, index].mean()) for index, method in enumerate(METHODS)},
            comparisons={name: dict(gain_pp=100*float((means[take, METHODS.index(first)]-means[take, METHODS.index(second)]).mean()),
                rescue_count=int(((outcomes[take, METHODS.index(first)] == 1) & (outcomes[take, METHODS.index(second)] == 0)).sum()),
                harm_count=int(((outcomes[take, METHODS.index(first)] == 0) & (outcomes[take, METHODS.index(second)] == 1)).sum()))
                for name, first, second in PRIMARY_COMPARISONS+SYSTEM_COMPARISONS})
    return dict(arms=arm_stats, primary_comparisons=comparisons, descriptive_system_comparisons=systems,
        tasks=task_rows, bootstrap=dict(unit='registered episode', stratification='task',
            seed=BOOTSTRAP_SEED, draws=BOOTSTRAP_DRAWS, interval='percentile 95%',
            repeats_are_not_independent_sources=True, simultaneous_interval=False),
        interpretation='P0 descriptive diagnostics; no winner selected, no independent validation claim',
        pairing='same episode/cut/repeat and suffix decision index; normal and intervention sampling phases differ')


class Auditor:
    def __init__(self, root, phase):
        self.root, self.phase = Path(root).resolve(), phase
        self.errors, self.warnings, self.inputs = [], [], {}
        self.passed_checks = 0
        self.artifact_files, self.claimed_attempts = set(), {}
        self.branches, self.banks, self.sources = [], [], []
        self.ledger = {}
        self.config = {}

    def check(self, condition, message, path=None):
        if condition:
            self.passed_checks += 1
        else:
            self.errors.append(dict(check=message, path=str(path) if path is not None else None))
        return bool(condition)

    def guard(self, name, function):
        try:
            return function()
        except Exception as error:
            self.errors.append(dict(check=name, exception=type(error).__name__, detail=str(error)))
            return None

    def read_json(self, path):
        path = Path(path)
        value = json.loads(path.read_text())
        self.inputs[str(path)] = _hash(path)
        return value

    def arrays(self, path):
        path = Path(path)
        with np.load(path, allow_pickle=False) as archive:
            result = {key: archive[key].copy() for key in archive.files}
        self.inputs[str(path)] = _hash(path)
        for name, array in result.items():
            self.check(array.dtype.kind != 'O' and (array.dtype.kind not in 'fc' or np.isfinite(array).all()),
                       f'finite numeric archive field {name}', path)
        return result

    def seal(self, folder, protocol=True):
        folder = Path(folder)
        seal = self.read_json(folder/'complete.json')
        self.check(seal.get('status') == 'complete', 'completed immutable artifact', folder)
        if protocol:
            self.check(seal.get('protocol_sha256') == self.config['analysis_approval']['protocol_sha256'],
                       'artifact protocol SHA', folder)
        files = seal['files']
        actual = {str(path.relative_to(folder)) for path in folder.rglob('*')
                  if path.is_file() and path != folder/'complete.json'}
        self.check(set(files) == actual, 'seal contains exact artifact file set', folder)
        for relative, expected in files.items():
            path = (folder/relative).resolve()
            if not self.check(path.is_relative_to(folder.resolve()), 'seal path stays inside artifact', path):
                continue
            self.check(path.is_file() and _hash(path) == expected, 'artifact content SHA', path)
            if path.is_file():
                self.artifact_files.add(path)
        self.artifact_files.add(folder/'complete.json')
        return seal

    def claim(self, row, evidence, kind=None):
        number = row['number']
        self.check(number in self.ledger and self.ledger[number] == row, 'attempt matches complete ledger row', evidence)
        if kind is not None:
            self.check(row.get('kind') == kind, 'attempt kind matches work', evidence)
        previous = self.claimed_attempts.setdefault(number, str(evidence))
        self.check(previous == str(evidence), 'one attempt is not reused for separate simulator runs', evidence)
        return number

    def attempt_file(self, folder, summary, kind):
        row = self.read_json(folder/'attempt.json')
        self.check(summary.get('budget_attempt') == row['number'], 'summary attempt number', folder)
        return self.claim(row, folder, kind)

    def setup(self):
        self.config = self.read_json(self.root/'p0/config.json')
        validation = validate_protocol(self.config, require_runnable=True)
        self.check(validation['runnable'], 'frozen protocol is runnable')
        self.check(self.config['methods'] == list(METHODS), 'fixed five P0 methods and order')
        self.check(self.config['replicates'] == 4, 'four paired suffixes')
        self.check(self.config['control_budget'] == 300, 'control budget 300')
        for name in ('source_horizon', 'prefix_horizon', 'suffix_horizon'):
            self.check(self.config[name] == 10, f'{name} fixed ten')
        cases = self.config['episode_manifest']
        self.check(len(cases) == 20 and all(case['split'] == 'p0' for case in cases), 'exactly twenty P0 episodes')
        self.check(Counter(case['task'] for case in cases) == Counter({task: 4 for task in self.config['tasks']}),
                   'four registered P0 episodes per task')
        self.check(all(case.get('cut_rule', {}).get('kind') == 'first_alarm' for case in cases),
                   'P0 uses first eligible alarm without outcome selection')
        frozen = self.read_json(self.root/'p0/freeze.json')
        for name, expected in frozen['files'].items():
            self.check(Path(name).is_file() and _hash(name) == expected, 'frozen code/config/dependency SHA', name)
        for name, identity in frozen.get('large_files_verified_once_then_stat', {}).items():
            stat = Path(name).stat()
            self.check(stat.st_size == identity['bytes'] and stat.st_mtime_ns == identity['mtime_ns']
                       and stat.st_ino == identity['inode'] and stat.st_dev == identity['device'],
                       'byte-verified frozen large checkpoint identity remains unchanged', name)
        self.check(str(self.root/'p0/config.json') in frozen['files'], 'P0 config included in freeze manifest')
        ledger_path = self.root/'budget/attempts.jsonl'
        rows = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
        self.inputs[str(ledger_path)] = _hash(ledger_path)
        total = Counter()
        for number, row in enumerate(rows, 1):
            self.check(row['number'] == number, 'ledger sequence is contiguous', ledger_path)
            self.check(type(row['amount']) is int and row['amount'] > 0, 'positive integer attempt amount', ledger_path)
            self.check(row['stage'] == 'p0' and row['resource'] == 'simulator_attempts',
                       'no main collection or optimizer updates started', ledger_path)
            self.check(row['protocol_sha256'] == self.config['analysis_approval']['protocol_sha256'],
                       'ledger protocol SHA', ledger_path)
            self.ledger[row['number']] = row
            total[row['resource']] += row['amount']
        self.check(total['simulator_attempts'] <= 600, 'P0 attempt hard cap 600', ledger_path)
        self.check(total['training_updates'] == 0, 'no optimizer updates', ledger_path)
        self.check(total['simulator_attempts'] == len(rows), 'one simulator run per ledger reservation', ledger_path)
        failures = set()
        for location in ('sources', 'candidates', 'rollouts', 'diagnostics', 'p0/errors'):
            failures.update(str(path) for path in (self.root/location).rglob('failure.json'))
        self.check(not failures, 'no unresolved or hidden failed P0 attempts', self.root)
        if failures:
            self.errors.append(dict(check='failure artifacts', paths=sorted(failures)))
        for path in (self.root/'rollouts').iterdir() if (self.root/'rollouts').is_dir() else []:
            self.check(path.name == 'p0' or not any(path.rglob('*')), 'no main rollout artifacts', path)
        self.budget = dict(ledger_rows=len(rows), simulator_attempts=total['simulator_attempts'],
            training_updates=total['training_updates'], hard_limit=600,
            remaining=600-total['simulator_attempts'],
            by_kind=dict(Counter(row['kind'] for row in rows)), by_stage=dict(Counter(row['stage'] for row in rows)))
        return cases

    def trace(self, folder):
        data = self.arrays(folder/'trajectory.npz')
        steps = len(data['actions'])
        self.check(data['actions'].shape == (steps, 4) and data['actions'].dtype == np.float32,
                   'raw float32 four-channel actions', folder)
        self.check(len(data['physics_states']) == steps+1, 'physics includes initial state', folder)
        for key in ('rewards', 'success_flags', 'done_flags'):
            self.check(len(data[key]) == steps, 'one outcome flag per executed step', folder)
        self.check(not data['done_flags'][:-1].any(), 'no controls executed after termination', folder)
        self.check(not np.any(data['success_flags'] & ~data['done_flags']), 'success terminates trace', folder)
        self.check(0 <= steps <= 300, 'trace within original episode budget', folder)
        self.check(_same(data['generated_steps'], data['actual_sampling_steps']), 'generated/actual sampling clock', folder)
        count = len(data['generated_steps'])
        self.check(data['generated_plans'].shape == (count, 50, 4), 'fifty-command captured plans', folder)
        self.check(len(data['actual_sampling_seeds']) == count, 'sampling seeds cover generated plans', folder)
        return data

    def source(self, case):
        folder = self.root/'sources'/case['case_id']
        before = len(self.errors)
        self.seal(folder)
        summary = self.read_json(folder/'summary.json')
        self.attempt_file(folder, summary, 'source_capture')
        self.check(summary['case'] == case, 'source exactly matches registered episode', folder)
        self.check(summary['status'] == 'complete' and summary['planned_episode_retained'] is True,
                   'completed source retained', folder)
        self.check(summary['outcome_filter_applied'] is False, 'no outcome filter', folder)
        data = self.trace(folder)
        steps, cuts = summary['steps'], summary['cuts']
        self.check(steps == len(data['actions']), 'source step metadata', folder)
        expected_steps = np.arange(0, steps, 10, dtype=np.int64)
        self.check(_same(data['actual_sampling_steps'], expected_steps), 'source plans at initial 0 then natural 10-step boundaries', folder)
        seeds = np.asarray([source_seed(case, index, namespace=self.config['seed_namespace'])
                            for index in range(len(expected_steps))], dtype=np.int64)
        self.check(_same(data['actual_sampling_seeds'], seeds), 'source natural decision seed stream', folder)
        for index, start in enumerate(expected_steps):
            count = min(10, steps-int(start))
            self.check(_same(data['actions'][start:start+count], data['generated_plans'][index, :count]),
                       'source uses only first ten raw commands of each natural plan', folder)
        self.check(summary['success'] == bool(data['success_flags'].any()), 'source actual success flag', folder)
        events = summary['events']
        expected_events = list(range(0, steps+1 if cuts else steps, 5))
        self.check([event['step'] for event in events] == expected_events, 'every-five-step monitoring includes selected cut', folder)
        for event in events:
            t = event['step']
            eligible = t % 10 == 5 and t+10 <= 300
            alarm = event['gate'] > self.config['gate_threshold'] and eligible
            self.check(event['plan_age'] == t % 10, 'natural refresh precedes boundary monitoring', folder)
            self.check(event['interruption_eligible'] == eligible and event['alarm'] == alarm,
                       'alarm eligibility excludes boundary and late truncated windows', folder)
            self.check(event['selected_cut'] == alarm and event['intervention_executed'] is False,
                       'capture selects first alarm without executing treatment', folder)
        alarms = [event['step'] for event in events if event['alarm']]
        self.check(cuts == alarms[:1] and len(cuts) <= 1, 'first eligible alarm is the sole cut', folder)
        self.check(summary['no_cut'] == (not cuts) and summary['no_alarm'] == (not alarms), 'no-cut/no-alarm flags', folder)
        self.check(summary['full_episode_outcome_available'] == (not cuts), 'no-cut common outcome availability', folder)
        anchor = context = None
        if cuts:
            cut = cuts[0]
            self.check(cut == steps and cut % 10 == 5 and cut <= 285, 'legal unexecuted midpoint cut', folder)
            anchor = self.read_json(folder/f'cut{cut:03d}'/'anchor.json')
            context = self.arrays(folder/f'cut{cut:03d}'/'context.npz')
            queue = anchor['queue']
            self.check(anchor['step'] == cut and anchor['source_horizon'] == 10 and anchor['trigger'] is True,
                       'cut anchor native10 trigger', folder)
            self.check(queue['horizon'] == 10 and queue['step'] == cut and queue['age'] == 5 and queue['remaining_steps'] == 5,
                       'original queue contains exactly five legal remaining commands', folder)
            self.check(queue['plan_start_step'] == cut-5 and queue['budget'] == 300, 'saved queue origin and budget', folder)
            self.check(_array_hash(context['full_plan']) == queue['raw_plan_sha256'], 'saved raw queue SHA', folder)
            self.check(_same(context['full_plan'], data['generated_plans'][-1]), 'cut queue is last natural source plan', folder)
        else:
            self.check(steps == 300 or bool(data['done_flags'][-1]), 'no-cut source ran to true terminal/budget', folder)
            self.check(not (self.root/'candidates'/case['case_id']).exists(), 'no candidate bank invented for no-cut source', folder)
            self.check(not (self.root/'rollouts/p0'/case['case_id']).exists(), 'no counterfactual cut invented for no-cut source', folder)
        row = dict(case_id=case['case_id'], episode_id=case['episode_id'], task=case['task'], env_seed=case['env_seed'],
            cuts=cuts, no_cut=not cuts, no_alarm=summary['no_alarm'], source_steps=steps,
            end_reason=summary['end_reason'], actual_sampling_steps=data['actual_sampling_steps'].tolist(),
            source_wall_seconds=summary['wall_seconds'], source_policy_seconds=summary['policy_seconds'],
            boundary_threshold_crossings=sum(event['exceeds_threshold'] and event['step'] % 10 == 0 for event in events),
            late_threshold_crossings=sum(event['exceeds_threshold'] and event['step']+10 > 300 for event in events),
            technical_passed=len(self.errors) == before)
        self.sources.append(row)
        return row, summary, data, anchor, context

    def bank(self, case, cut):
        folder = self.root/'candidates'/case['case_id']/f'cut{cut:03d}'
        self.seal(folder)
        generation = self.read_json(folder/'generation.json')
        self.attempt_file(folder, generation, 'candidate_restore')
        self.check(generation['saved_queue_unchanged'] is True and generation['saved_before_any_branch'] is True,
                   'bank leaves original queue intact and predates outcomes', folder)
        self.check(generation['raw_bank_audit']['status'] == 'passed', 'real raw bank invariant audit passed', folder)
        self.check(generation['a0_slot'] == 0, 'a0 critic slot zero', folder)
        self.check(generation['base_seed'] == candidate_seed(case, cut, namespace=self.config['seed_namespace']),
                   'specified a0 uses registered candidate seed', folder)
        noise = list(generation['noise_hashes'].values())
        self.check(generation['same_noise'] is True and noise and all(isinstance(x, str) and len(x) == 64 for x in noise)
                   and len(set(noise)) == 1, 'base/velocity/direct use identical actual flow noise', folder)
        plans, directions = self.arrays(folder/'plans.npz'), self.arrays(folder/'directions.npz')
        raw = directions['raw_a0']
        self.check(_same(plans['alarm_replan10'], raw), 'replan is bit-identical raw a0', folder)
        self.check(_same(directions['critic_a0'], np.clip(raw, -1, 1)), 'saved bounded critic anchor', folder)
        mask = 1-np.abs(np.clip(raw[:10].astype(float), -1, 1)) >= .05
        self.check(np.array_equal(directions['mask'], mask), 'saved exact .05 clearance mask', folder)
        original_names = dict(alarm_replan10='replan', velocity='velocity_matched', direct='direct_matched', post='post_matched')
        for method in METHODS[1:]:
            plan = plans[method]
            self.check(plan.shape == (50, 4) and plan.dtype == np.float32, 'raw bank plan dimensions/dtype', folder)
            self.check(_same(plan[10:], raw[10:]) and _same(plan[:10][~mask], raw[:10][~mask]),
                       'bank preserves tail and every masked raw coordinate', folder)
            delta = plan[:10].astype(float)-raw[:10].astype(float)
            proxy = np.clip(plan[:10], -1, 1)
            self.check(_close(proxy.astype(float)-np.clip(raw[:10].astype(float), -1, 1), delta, COMMAND_ATOL),
                       'actual raw and critic command deltas agree', folder)
            self.check(_close(directions[original_names[method]+'_actual_delta'], delta, COMMAND_ATOL),
                       'saved actual perturbation matches execution', folder)
            self.check(_same(directions[original_names[method]+'_critic_commands'], proxy),
                       'saved scored commands match actual raw mapping', folder)
            for group, indices in (('xyz', slice(0, 3)), ('gripper', slice(3, 4))):
                rms = float(np.sqrt(np.mean(delta[:, indices]**2)))
                maximum = float(np.abs(delta[:, indices]).max())
                self.check(rms <= self.config['matching'][group+'_rms']+COMMAND_ATOL
                           and maximum <= self.config['matching'][group+'_linf']+COMMAND_ATOL,
                           'final actual command perturbation stays inside caps', folder)
        self.check(generation['predictions']['replan']['mean_gain'] == 0, 'critic gain of designated a0 exactly zero', folder)
        preview = self.arrays(folder/'preview13.npz')
        preview_meta = self.read_json(folder/'preview13_metadata.json')
        from .candidates13 import CANDIDATE_ORDER, PAIRS
        self.check(list(preview) == list(CANDIDATE_ORDER) and preview_meta['candidate_order'] == list(CANDIDATE_ORDER)
                   and preview_meta['a0_slot'] == 0, 'real P0 preview contains all thirteen correctly ordered candidates', folder)
        self.check(preview_meta['retained_all'] is True and generation['preview13']['simulated'] is False,
                   'thirteen-candidate schema preview retained but not simulated', folder)
        self.check(preview_meta['random_provenance']['seed'] == seed_for('training_bank_preview', case['episode_id'], cut,
                   namespace=self.config['seed_namespace']), 'preview independent random seed preregistered', folder)
        expected_scale = .5 if (case['env_seed']//5) % 2 == 0 else 1.
        self.check(preview_meta['channel_radius_scale'] == expected_scale, 'preview channel radius chosen without outcomes', folder)
        preview_delta = {name: value[:10].astype(float)-raw[:10].astype(float) for name, value in preview.items()}
        self.check(_same(preview['a0'], raw), 'preview a0 raw identity', folder)
        for method in ('velocity', 'direct', 'post'):
            self.check(_same(preview[method], plans[method]), 'preview leaves formal deployment plan unchanged', folder)
        for name, value in preview.items():
            record = preview_meta['candidates'][name]
            self.check(record['retained'] is True and _same(value, preview[record['alias']]),
                       'preview alias preserves exact raw command identity', folder)
            self.check(record['command_sha256'] == _array_hash(value[:10]), 'preview alias SHA is raw prefix SHA', folder)
            self.check(_same(value[10:], raw[10:]) and _same(value[:10][~mask], raw[:10][~mask]),
                       'preview preserves all masked coordinates and suffix tail', folder)
            self.check(_close(np.clip(value[:10], -1, 1).astype(float)-np.clip(raw[:10], -1, 1).astype(float),
                              preview_delta[name], COMMAND_ATOL), 'preview raw/critic delta consistency', folder)
        for positive, negative in PAIRS:
            self.check(_close(preview_delta[positive], -preview_delta[negative], COMMAND_ATOL),
                       'real thirteen-candidate preview positive/negative symmetry', folder)
        for sign in ('positive', 'negative'):
            self.check(_close(preview_delta['random_half_'+sign], .5*preview_delta['random_full_'+sign], COMMAND_ATOL),
                       'real preview same-direction half/full relationship', folder)
        self.banks.append(dict(case_id=case['case_id'], cut=cut,
            generation_wall_seconds=generation['generation_wall_seconds'],
            candidate_bank_seconds=generation['candidate_bank_seconds'], restore_seconds=generation['restore_seconds'],
            raw_bank_audit=generation['raw_bank_audit'], matching=generation['matching'],
            base_generation=generation['base_generation'], guidance=generation['guidance'],
            post_gradient=generation['post_gradient'], preview13=preview_meta))
        return plans

    def branch(self, case, cut, method, repeat, source_data, anchor, context, plans):
        folder = self.root/'rollouts/p0'/case['case_id']/f'cut{cut:03d}'/method/f'repeat_{repeat}'
        self.seal(folder)
        summary = self.read_json(folder/'summary.json')
        self.attempt_file(folder, summary, 'branch_including_restore')
        for key, value in dict(status='complete', case_id=case['case_id'], episode_id=case['episode_id'],
                               task=case['task'], env_seed=case['env_seed'], split='p0', cut_step=cut,
                               method=method, repeat=repeat, source_horizon=10, suffix_horizon=10,
                               restore_included_in_attempt=True, normalized_queue_injection=False).items():
            self.check(summary[key] == value, f'branch {key} provenance', folder)
        self.check(summary['source_seal_sha256'] == _hash(self.root/'sources'/case['case_id']/'complete.json'),
                   'branch references exact sealed source', folder)
        if self.config.get('require_saved_bank', False):
            bank = self.root/'candidates'/case['case_id']/f'cut{cut:03d}'
            self.check(summary['candidate_bank_reference'] == dict(path=str(bank), seal_sha256=_hash(bank/'complete.json')),
                       'branch references exact sealed candidate bank', folder)
        data = self.trace(folder)
        steps = len(data['actions'])
        self.check(summary['terminal_step'] == steps and (steps == 300 or bool(data['done_flags'][-1])),
                   'complete branch reaches true terminal or budget', folder)
        self.check(summary['success'] == bool(data['success_flags'].any()), 'branch actual success', folder)
        self.check(_same(data['actions'][:cut], source_data['actions']), 'source replay raw command prefix', folder)
        self.check(_close(data['physics_states'][:cut+1], source_data['physics_states'], PHYSICS_ATOL),
                   'source replay physical trajectory', folder)
        self.check(_close(data['rewards'][:cut], source_data['rewards'], REWARD_ATOL), 'source replay rewards', folder)
        for key in ('success_flags', 'done_flags'):
            self.check(_same(data[key][:cut], source_data[key]), 'source replay terminal flags', folder)
        expected = context['full_plan'][5:10] if method == 'continue_native10' else plans[method][:10]
        requested = 5 if method == 'continue_native10' else 10
        self.check(summary['requested_prefix_steps'] == requested and summary['original_queue_remaining'] == 5,
                   'normal executes five old commands; interventions execute ten new commands', folder)
        actual = min(requested, steps-cut)
        self.check(summary['actual_prefix_steps'] == actual and actual > 0, 'actual prefix ends only at terminal/budget', folder)
        self.check(_same(data['actions'][cut:cut+actual], expected[:actual]), 'executed prefix equals specified raw commands', folder)
        self.check(summary['command_sha256'] == _array_hash(expected), 'full specified raw prefix hash', folder)
        self.check(summary['clipped_command_proxy_sha256'] == _array_hash(np.clip(expected, -1, 1)),
                   'specified prefix critic proxy hash', folder)
        first = cut+requested
        self.check(summary['first_expected_resample'] == first, 'continuation starts at natural or intervention-shifted boundary', folder)
        suffix = summary['suffix_seeds']
        expected_steps = list(range(first, steps, 10))
        self.check([item['step'] for item in suffix] == expected_steps, 'suffix samples at exact fixed10 cadence', folder)
        self.check(summary['first_actual_resample'] == (expected_steps[0] if expected_steps else None),
                   'actual first suffix sample time', folder)
        self.check(data['actual_sampling_steps'].tolist() == expected_steps, 'trajectory actual suffix sampling times', folder)
        self.check(data['actual_sampling_seeds'].tolist() == [item['seed'] for item in suffix],
                   'trajectory actual suffix seeds', folder)
        for index, item in enumerate(suffix):
            self.check(item['decision_index'] == index and item['seed'] == suffix_seed(
                case, cut, repeat, index, namespace=self.config['seed_namespace']), 'registered paired suffix decision seed', folder)
            self.check(isinstance(item.get('noise_sha256'), str) and len(item['noise_sha256']) == 64,
                       'actual suffix initial-noise SHA recorded', folder)
            start, count = item['step'], min(10, steps-item['step'])
            self.check(_same(data['actions'][start:start+count], data['generated_plans'][index, :count]),
                       'suffix uses first ten raw commands from actual sampled plan', folder)
        expected_id = f"{case['episode_id']}:cut{cut}:repeat{repeat}"
        self.check(summary['paired_suffix_id'] == expected_id, 'paired suffix identity ignores method/absolute phase', folder)
        self.branches.append(summary)
        return summary, data

    def case(self, case):
        row, summary, source_data, anchor, context = self.source(case)
        if not row['cuts']:
            if self.phase == 'native20':
                row.update(outcomes=[[int(summary['success'])]*4 for _ in METHODS],
                           common_outcome_broadcast=True, actual_branch_count=0)
            return row
        cut = row['cuts'][0]
        plans = self.bank(case, cut)
        selected_methods = METHODS if self.phase == 'native20' else ('alarm_replan10',)
        repeats = range(4) if self.phase == 'native20' else range(1)
        branch_root = self.root/'rollouts/p0'/case['case_id']
        self.check({path.name for path in branch_root.iterdir() if path.is_dir()} == {f'cut{cut:03d}'},
                   'exactly the registered cut has branch artifacts', branch_root)
        method_root = branch_root/f'cut{cut:03d}'
        self.check({path.name for path in method_root.iterdir() if path.is_dir()} == set(selected_methods),
                   'exactly the phase methods have branch artifacts', method_root)
        rows, traces = {}, {}
        for method in selected_methods:
            self.check({path.name for path in (method_root/method).iterdir() if path.is_dir()}
                       == {f'repeat_{repeat}' for repeat in repeats}, 'exactly registered repeats exist', method_root/method)
            rows[method], traces[method] = [], []
            for repeat in repeats:
                result = self.branch(case, cut, method, repeat, source_data, anchor, context, plans)
                rows[method].append(result[0])
                traces[method].append(result[1])
            for repeat in list(repeats)[1:]:
                count = min(rows[method][0]['actual_prefix_steps'], rows[method][repeat]['actual_prefix_steps'])
                self.check(rows[method][0]['actual_prefix_steps'] == rows[method][repeat]['actual_prefix_steps'],
                           'same deterministic prefix termination across replicates', case['case_id'])
                self.check(rows[method][0]['endpoint_image_sha256'] == rows[method][repeat]['endpoint_image_sha256'],
                           'same method prefix endpoint image across replicates', case['case_id'])
                self.check(_same(traces[method][0]['actions'][:cut+count], traces[method][repeat]['actions'][:cut+count]),
                           'same method prefix independent of replicate', case['case_id'])
                self.check(_close(traces[method][0]['physics_states'][:cut+count+1],
                                  traces[method][repeat]['physics_states'][:cut+count+1], PHYSICS_ATOL),
                           'same method prefix physical trajectory independent of replicate', case['case_id'])
        if self.phase == 'native20':
            for repeat in range(4):
                available = {}
                for method in METHODS:
                    for item in rows[method][repeat]['suffix_seeds']:
                        identity = (item['seed'], item.get('noise_sha256'))
                        previous = available.setdefault(item['decision_index'], identity)
                        self.check(previous == identity, 'same replicate/decision index shares actual seed and flow noise across arms', case['case_id'])
            row.update(outcomes=[[int(item['success']) for item in rows[method]] for method in METHODS],
                       common_outcome_broadcast=False, actual_branch_count=20)
        return row

    def diagnostic(self, case, kind):
        folder = self.root/'diagnostics'/kind/case['case_id']
        self.seal(folder, protocol=False)
        result = self.read_json(folder/'summary.json')
        self.check(result['status'] == 'passed' and not result['failed_checks'], f'{kind} real-runtime probe passed', folder)
        self.check(result['case_id'] == case['case_id'] and result['task'] == case['task'], 'probe preregistered task/source', folder)
        self.check(result['effectiveness_evidence'] is False, 'technical probe excluded from effectiveness evidence', folder)
        if kind == 'native10_queue':
            self.check(result['counted_runs'] == 2 and result['source_horizon'] == 10, 'two counted native10 queue paths', folder)
            self.check(result['checks'] and all(value is True for value in result['checks'].values()), 'all real queue checks passed', folder)
            self.check(result['actual_native_queue_lengths_available'] and result['initial_flow_noise_available'],
                       'actual queue exhaustion and shared flow noise measured', folder)
            for name in ('native', 'raw'):
                self.claim(result['runs'][name]['attempt'], folder/name, name+'_queue_probe')
        else:
            self.check(result['counted_runs'] == 4, 'four counted raw/clipped physical runs', folder)
            for sign in ('positive', 'negative'):
                pair = result['pairs'][sign]
                self.check(pair['physical_and_binary_equivalence'] is True and all(pair['physical_and_flag_checks'].values()),
                           'raw/clipped state force contact and binary flags equivalent', folder)
                if not pair['reward_comparison']['equal']:
                    self.warnings.append(dict(check='reward difference recorded separately from physical equivalence', path=str(folder), sign=sign))
            for name, run in result['runs'].items():
                self.claim(run['attempt'], folder/name, 'raw_clipped_physical_probe')
                model = run['model']
                self.check(model['control_clamping_disabled'] is False, 'loaded MuJoCo control clamping enabled', folder)
                limited = np.asarray(model['controls']['actuator_ctrllimited'])
                ranges = np.asarray(model['controls']['actuator_ctrlrange'])
                self.check(limited.size > 0 and limited.all() and ranges.shape == (limited.size, 2)
                           and np.all(ranges == np.array([-1., 1.])), 'loaded actuator controls limited to [-1,1]', folder)
            if not result['contact_seen']:
                self.warnings.append(dict(check='physical probe has no observed contacts; contact-state equivalence unestablished', path=str(folder)))
        return dict(case_id=case['case_id'], task=case['task'], kind=kind, status=result['status'],
                    contact_seen=result.get('contact_seen'), counted_runs=result['counted_runs'])

    def legacy(self, case_id):
        folder = self.root/'diagnostics/legacy'/case_id
        self.seal(folder)
        result = self.read_json(folder/'result.json')
        self.check(result['status'] == 'passed' and result['all_passed'] is True, 'legacy dual implementation and archive comparisons passed', folder)
        self.check(result['case_id'] == case_id and result['archived_inputs_unchanged'] is True,
                   'legacy identity and sealed historical inputs unchanged', folder)
        self.check(result['diagnostic_only'] is True and result['native10_effectiveness_evidence'] is False,
                   'legacy source excluded from native10 effectiveness', folder)
        numbers = result['attempt_numbers']
        self.check(result['new_attempts'] == 10 and len(numbers) == len(set(numbers)) == 10,
                   'two legacy implementations count two generation restores and eight branches', folder)
        actual_numbers = []
        for implementation in ('act', 'corrector'):
            generation = folder/implementation/'generation'
            self.seal(generation)
            for name in ('plans.npz', 'directions.npz', 'intermediates.npz', 'generation.json'):
                self.check((generation/name).is_file(), 'legacy generation evidence present', generation/name)
            metadata = self.read_json(generation/'generation.json')
            actual_numbers.append(self.attempt_file(generation, metadata, 'legacy_generation_including_restore'))
            for method in ('replan', 'post_matched'):
                for repeat in (0, 1):
                    branch = folder/implementation/'rollouts'/method/f'replicate_{repeat}'
                    self.seal(branch)
                    summary = self.read_json(branch/'summary.json')
                    self.check(summary.get('status') == 'complete', 'legacy dual branch complete', branch)
                    self.check((branch/'trajectory.npz').is_file(), 'legacy physical trajectory evidence', branch)
                    self.check(summary['source_horizon'] == 50 and summary['horizon'] == 10,
                               'legacy diagnostics keep original bounded native50 source protocol', branch)
                    actual_numbers.append(self.attempt_file(branch, summary, 'legacy_branch_including_restore'))
        self.check(set(numbers) == set(actual_numbers), 'legacy result attempt list matches individual work artifacts', folder)
        comparisons = sorted((folder/'comparisons').glob('*.json'))
        self.check(len(comparisons) == result['expected_comparisons'] == 15
                   and {path.name for path in comparisons} == set(result['comparisons']),
                   'all fifteen legacy generation/branch/archive comparisons exist', folder)
        for path in comparisons:
            comparison = self.read_json(path)
            self.check(comparison['status'] == 'passed' and comparison['passed'] is True
                       and comparison['checks'] and all(row['passed'] is True for row in comparison['checks'].values()),
                       'each legacy comparison and every constituent check passed', path)
            self.check(comparison['diagnostic_only'] is True and comparison['native10_effectiveness_evidence'] is False,
                       'individual legacy comparison excluded from effectiveness', path)
        return dict(case_id=case_id, status=result['status'], attempts=result['new_attempts'], comparisons=len(comparisons))

    def wave_status(self, mode):
        result = []
        for rank in range(8):
            path = self.root/'p0/wave_status'/mode/f'worker_{rank}.json'
            record = self.read_json(path)
            self.check(record['status'] == 'complete' and record['rank'] == rank and record['mode'] == mode,
                       'all eight wave workers completed without failure', path)
            result.append(record)
        return dict(workers=result, maximum_worker_wall_seconds=max(row['wall_seconds'] for row in result),
                    timing_scope='worker entry through completion; maximum is not exact launcher end-to-end wall')

    def run(self):
        cases = self.guard('configuration/freeze/ledger', self.setup)
        source_rows, diagnostics, legacy, waves = [], [], [], {}
        if cases is not None:
            selected = cases if self.phase == 'native20' else cases[:5]
            self.check(len({case['task'] for case in cases[:5]}) == 5, 'first five technical sources cover five tasks')
            for case in selected:
                row = self.guard('source/bank/paired branches '+case['case_id'], lambda case=case: self.case(case))
                if row is not None:
                    source_rows.append(row)
            expected = {case['case_id'] for case in selected}
            for location in ('sources', 'candidates', 'rollouts/p0'):
                actual = {path.name for path in (self.root/location).iterdir() if path.is_dir()} if (self.root/location).is_dir() else set()
                self.check(actual <= expected, 'no unregistered or prematurely captured episodes', self.root/location)
            for case in cases[:5]:
                for kind in ('native10_queue', 'raw_clipped'):
                    result = self.guard(kind+' '+case['case_id'], lambda case=case, kind=kind: self.diagnostic(case, kind))
                    if result is not None:
                        diagnostics.append(result)
            for case_id in LEGACY_CASES:
                result = self.guard('legacy '+case_id, lambda case_id=case_id: self.legacy(case_id))
                if result is not None:
                    legacy.append(result)
            for mode in ('technical', 'native20') if self.phase == 'native20' else ('technical',):
                waves[mode] = self.guard('wave status '+mode, lambda mode=mode: self.wave_status(mode))
            self.check(len(source_rows) == len(selected), 'all planned phase sources audited')
            self.check(set(self.claimed_attempts) == set(self.ledger), 'every counted attempt has one completed evidence artifact')
        stats = None
        if self.phase == 'native20' and len(source_rows) == 20 and not self.errors:
            stats = self.guard('episode-level paired descriptive statistics', lambda: statistics(source_rows))
        costs = {}
        if self.branches:
            seconds = np.asarray([row['wall_seconds'] for row in self.branches], dtype=float)
            costs = dict(branch_count=len(self.branches), branch_wall_worker_seconds=float(seconds.sum()),
                mean_branch_wall_seconds=float(seconds.mean()), median_branch_wall_seconds=float(np.median(seconds)),
                p90_branch_wall_seconds=float(np.quantile(seconds, .9)),
                branch_environment_seconds=float(sum(row['environment_seconds'] for row in self.branches)),
                branch_policy_seconds=float(sum(row['policy_seconds'] for row in self.branches)),
                branch_policy_calls=int(sum(row['policy_calls'] for row in self.branches)),
                branch_restore_seconds=float(sum(row['restore_seconds'] for row in self.branches)),
                branch_simulated_steps_including_restore=int(sum(row['terminal_step'] for row in self.branches)))
        costs.update(source_capture_wall_worker_seconds=sum(row['source_wall_seconds'] for row in self.sources),
                     candidate_generation_wall_worker_seconds=sum(row['generation_wall_seconds'] for row in self.banks),
                     sealed_artifact_files=len(self.artifact_files),
                     sealed_artifact_bytes=sum(path.stat().st_size for path in self.artifact_files if path.is_file()),
                     waves=waves)
        return dict(schema='native10_p0_audit_v1', phase=self.phase,
            status='passed' if not self.errors else 'failed', utc=datetime.now(timezone.utc).isoformat(),
            root=str(self.root), config_sha256=self.inputs.get(str(self.root/'p0/config.json')),
            passed_checks=self.passed_checks, errors=self.errors, warnings=self.warnings,
            budget=getattr(self, 'budget', None), claimed_attempts=len(self.claimed_attempts),
            expected_episode_count=20 if self.phase == 'native20' else 5,
            audited_episode_count=len(source_rows), planned_p0_episode_count=20,
            source_rows=source_rows,
            source_coverage=dict(task_counts=dict(Counter(row['task'] for row in source_rows)),
                cut_episode_count=sum(bool(row['cuts']) for row in source_rows),
                no_cut_episode_count=sum(not row['cuts'] for row in source_rows),
                no_alarm_episode_count=sum(row['no_alarm'] for row in source_rows),
                cut_histogram=dict(Counter(str(row['cuts'][0]) for row in source_rows if row['cuts'])),
                late_threshold_crossings=sum(row['late_threshold_crossings'] for row in source_rows),
                boundary_threshold_crossings=sum(row['boundary_threshold_crossings'] for row in source_rows)),
            diagnostics=diagnostics, legacy_diagnostics=legacy, bank_diagnostics=self.banks,
            statistics=stats, costs=costs, input_sha256=self.inputs,
            main_collection_started=False if not any(row.get('stage') != 'p0' for row in self.ledger.values()) else True,
            new_simulation_or_training_performed_by_audit=False,
            conclusions=dict(technical_passed=not self.errors, winner_selected=False,
                independent_validation_success_claimed=False,
                scope='technical partial P0; twenty-episode effects unavailable' if self.phase == 'technical'
                      else 'twenty-episode P0 diagnostics; all episodes retained; source-level descriptive CIs'))


def audit(root=ROOT, phase='native20'):
    if phase not in ('technical', 'native20'):
        raise ValueError('Expected technical or native20 phase')
    return Auditor(root, phase).run()


def report(result):
    lines = ['# Native10 P0 技术审查与配对结果', '',
        f"阶段：`{result['phase']}`；审计状态：**{result['status']}**；通过检查：{result['passed_checks']}。", '',
        '本报告只读取已完成产物；审计本身未运行仿真、训练或GPU工作。P0不用于选择最好方法，也不是独立有效性验证。', '',
        f"预登记P0共20个episode；本阶段已审查 {result['audited_episode_count']}/{result['expected_episode_count']}。"]
    if result['budget'] is not None:
        budget = result['budget']
        lines += [f"全部计费仿真attempt：{budget['simulator_attempts']}/600；优化更新：{budget['training_updates']}；"
                  f"具备完成证据的attempt：{result['claimed_attempts']}。"]
    coverage = result['source_coverage']
    lines += [f"有cut源：{coverage['cut_episode_count']}；无cut：{coverage['no_cut_episode_count']}；"
              f"无合法报警：{coverage['no_alarm_episode_count']}。切点分布：`{json.dumps(coverage['cut_histogram'], ensure_ascii=False)}`。", '',
              '正常臂执行原生十步队列剩余五步，再于自然边界采样；中断臂执行指定新动作十步，再按十步后缀采样。'
              '后缀按episode、cut、repeat、决策序号共享seed和初始噪声；不同臂的绝对采样时刻及状态不必相同。', '']
    stats = result['statistics']
    if stats is None:
        lines += ['完整20源对照尚未通过审计，本报告不发布总体成功率或算法效果判断。', '']
    else:
        lines += ['## 五臂成功率', '', '| 方法 | 成功率 | 源级95%区间 |', '| --- | ---: | ---: |']
        for method, row in stats['arms'].items():
            low, high = row['success_rate_ci95']
            lines.append(f"| {method} | {100*row['success_rate']:.2f}% | [{100*low:.2f}, {100*high:.2f}]% |")
        lines += ['', '无cut源将完整正常episode结局广播到五臂和四个配对槽，仍只占一个独立episode。'
                  '95%区间以episode为单位、按任务分层bootstrap；四次后缀不是四个独立源，区间未作多重比较校正。', '',
                  '## 七项预定比较', '', '| 比较 | 净增益pp | 源级95%区间pp | 救回/损害配对数 |', '| --- | ---: | ---: | ---: |']
        for name, row in stats['primary_comparisons'].items():
            low, high = row['gain_ci95_pp']
            lines.append(f"| {name} | {row['gain_pp']:+.2f} | [{low:+.2f}, {high:+.2f}] | {row['rescue_count']}/{row['harm_count']} |")
        lines += ['', '## 总体系统增益（描述性）', '']
        for name, row in stats['descriptive_system_comparisons'].items():
            low, high = row['gain_ci95_pp']
            lines.append(f"- {name}：{row['gain_pp']:+.2f}pp，95%区间 [{low:+.2f}, {high:+.2f}]pp；救回/损害 {row['rescue_count']}/{row['harm_count']}。")
        lines += ['', '## 按任务分解', '', '| 任务 | episode / cut | normal | replan | velocity | direct | post |', '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
        for task, row in stats['tasks'].items():
            rates = ' | '.join(f"{100*row['success_rate'][method]:.1f}%" for method in METHODS)
            lines.append(f"| {task} | {row['episodes']} / {row['cut_episodes']} | {rates} |")
        lines += ['', '逐源四重复二值结局、逐任务净增益和救回/损害均保存在同名审计JSON。'
                  '开发/诊断上最高成绩不能称为独立验证成功；此处没有选择后续训练赢家。', '']
    lines += ['## 技术证据与成本', '',
        f"真实队列/物理探针完成记录 {len(result['diagnostics'])}；旧协议双实现诊断 {len(result['legacy_diagnostics'])}。"
        '旧正例及非正例只验证迁移一致性，不纳入native10成功率。',
        f"封存产物：{result['costs']['sealed_artifact_files']}个文件，{result['costs']['sealed_artifact_bytes']/2**20:.2f}MiB。"]
    costs = result['costs']
    if 'branch_count' in costs:
        lines += [f"原生P0分支：{costs['branch_count']}；每分支wall均值 {costs['mean_branch_wall_seconds']:.3f}秒，"
                  f"P90 {costs['p90_branch_wall_seconds']:.3f}秒；总计 {costs['branch_wall_worker_seconds']:.1f}worker秒。"
                  '累计worker秒不能直接当作并行波次wall或GPU小时。']
    lines += ['', '原始输入SHA、冻结代码核对、账本、真实候选幅度与退化、模型调用耗时、各worker耗时均在审计JSON。'
              '后续主采集与训练是否放行由分析端升级READY决定；本审计不会启动下一阶段。', '']
    if result['errors']:
        lines += ['## 未通过项', '']
        lines += ['- '+json.dumps(row, ensure_ascii=False) for row in result['errors']]
        lines += ['']
    if result['warnings']:
        lines += ['## 已记录的限制', '']
        lines += ['- '+json.dumps(row, ensure_ascii=False) for row in result['warnings']]
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('technical', 'native20'), required=True)
    parser.add_argument('--replace', action='store_true', help='explicitly replace this unsealed phase audit/report')
    args = parser.parse_args()
    json_path = ROOT/'p0'/f'audit_{args.phase}.json'
    report_path = ROOT/'p0'/('report_technical.md' if args.phase == 'technical' else 'report.md')
    if not args.replace and (json_path.exists() or report_path.exists()):
        raise FileExistsError('Preserve existing audit/report or explicitly pass --replace')
    result = audit(ROOT, args.phase)
    dump(json_path, result, exclusive=not args.replace)
    report_path.write_text(report(result))
    print(json.dumps(dict(status=result['status'], phase=args.phase, errors=len(result['errors']),
                          audit=str(json_path), report=str(report_path)), ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'passed' else 1)


if __name__ == '__main__':
    main()
