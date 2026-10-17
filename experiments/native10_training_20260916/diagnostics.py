"""Counted P0 comparison of actual native_action and an independent raw queue.

This module creates no runtime and writes no files. The caller must construct an
approved frozen engine, run this probe through the GPU lifecycle, and save the
returned metadata/arrays (also attached to Native10EquivalenceError on mismatch).
This is an execution diagnostic, never an effectiveness trial or training datum.
"""
from __future__ import annotations

import hashlib
import time

import numpy as np

from ac_tmil.idea3.local_collection import Trace
from .protocol import source_seed
from .semantics import Native10Queue


class Native10EquivalenceError(RuntimeError):
    def __init__(self, metadata, arrays):
        self.metadata = metadata
        self.arrays = arrays
        super().__init__('Native10/raw queue equivalence failed: ' + ', '.join(metadata['failed_checks']))


def _hash(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _bit_equal(first, second):
    first, second = np.asarray(first), np.asarray(second)
    return first.shape == second.shape and first.dtype == second.dtype and first.tobytes() == second.tobytes()


def _queue_length(runtime):
    policy = getattr(getattr(runtime, 'backend', None), 'policy', None)
    queue = getattr(policy, '_action_queue', None)
    return None if queue is None else len(queue)


def _run(engine, case, config, reserve, stage, side, max_steps):
    runtime = engine.runtime
    # The reservation precedes reset/environment creation, including its failure.
    attempt = reserve(stage, side + '_queue_probe', f"{case['case_id']}:{max_steps}")
    runtime.reset(case, 10)
    if hasattr(engine, 'hook'):
        engine.hook.begin(None)
    trace = Trace(runtime)
    initial_image = _hash(runtime.frame())
    initial_fingerprint = runtime.fingerprint()
    raw_queue = Native10Queue(budget=config['control_budget']) if side == 'raw' else None
    decisions = []
    first_command_checks = []
    within_chunk_checks = []
    freshness_checks = []
    queue_lengths = []
    last_plan = None
    start = time.perf_counter()
    while not trace.terminal and trace.step < max_steps:
        step = trace.step
        index = len(decisions)
        seed = source_seed(case, index, namespace=config['seed_namespace'])
        if side == 'native':
            # Deliberately invoke the real per-step preprocessing/select_action/
            # postprocessing path, including all nine cached-action selections.
            command, new_plan, seconds = runtime.native_action(seed)
            fresh = new_plan is not None
            freshness_checks.append(fresh == (step % 10 == 0))
            queue_lengths.append(_queue_length(runtime))
            if fresh:
                last_plan = np.array(new_plan, copy=True)
                first_command_checks.append(_bit_equal(command, last_plan[0]))
                stats = dict(policy_calls=1, seconds=seconds,
                             noise_sha256=getattr(getattr(engine, 'hook', None), 'last_noise_sha', None))
            if last_plan is None:
                raise ValueError('Native runtime failed to generate an initial plan')
            within_chunk_checks.append(_bit_equal(command, last_plan[step % 10]))
        else:
            fresh = raw_queue.needs_plan(step)
            freshness_checks.append(fresh == (step % 10 == 0))
            if fresh:
                last_plan, stats = engine.propose(seed)
                last_plan = np.array(last_plan, copy=True)
                if stats.get('fallback') is not None or stats['policy_calls'] != 1:
                    raise ValueError('Unguided raw-queue probe unexpectedly retried/fell back')
                raw_queue.replace(last_plan, step)
            command = raw_queue.pop(step)
            if fresh:
                first_command_checks.append(_bit_equal(command, last_plan[0]))
            within_chunk_checks.append(_bit_equal(command, last_plan[step % 10]))
            queue_lengths.append(_queue_length(runtime))
        if fresh:
            if last_plan.shape != (50, 4) or not np.isfinite(last_plan).all():
                raise ValueError('Probe requires finite captured raw 50x4 plans')
            trace.plans.append(last_plan.copy())
            trace.generated.append(step)
            trace.seeds.append(seed)
            trace.sampling_steps.append(step)
            trace.policy_calls += stats['policy_calls']
            trace.policy_seconds += stats['seconds']
            decisions.append(dict(step=step, decision_index=index, seed=seed,
                                  noise_sha256=stats.get('noise_sha256'),
                                  captured_plan_sha256=_hash(last_plan)))
        trace.execute(runtime, command)
    engine.verify()
    data = trace.arrays()
    info = dict(side=side, attempt=attempt, actual_steps=trace.step,
                stop_reason='success' if any(trace.successes) else 'environment_done' if trace.terminal
                            else 'control_budget' if trace.step >= config['control_budget'] else 'probe_limit',
                success=bool(any(trace.successes)), terminal=trace.terminal,
                decisions=decisions, initial_image_sha256=initial_image,
                endpoint_image_sha256=_hash(runtime.frame()),
                initial_fingerprint=initial_fingerprint, final_fingerprint=runtime.fingerprint(),
                fresh_at_exact_natural_boundaries=all(freshness_checks),
                first_action_matches_captured_plan_zero_bitwise=all(first_command_checks),
                every_action_matches_captured_first_ten_bitwise=all(within_chunk_checks),
                first_action_checks=first_command_checks, within_chunk_checks=within_chunk_checks,
                actual_internal_queue_lengths=queue_lengths,
                raw_commands_outside_unit_fraction=float((np.abs(data['actions']) > 1).mean()) if len(data['actions']) else 0.,
                policy_calls=trace.policy_calls, policy_seconds=trace.policy_seconds,
                environment_seconds=trace.environment_seconds, wall_seconds=time.perf_counter()-start)
    return info, data


def run_native10_equivalence(engine, case, config, reserve, *, stage='p0', max_steps=30):
    """Compare two separately counted runs from the same episode initial state.

    ``reserve`` is a ledger or callable ``(stage,kind,identity)->attempt_dict``.
    Each run independently resets horizon=10 and stops after max_steps, success,
    environment termination, or the original 300-step cap. Only source_seed's
    natural-decision index is used; no candidate/suffix seeds or G0 decisions.
    Returned arrays have flat ``native_*`` and ``raw_*`` keys for NPZ storage.

    Commands, captured plans and sampling streams must be bit-identical; physics
    allows the existing absolute 1e-10 replay tolerance and no relative tolerance.
    Failure raises Native10EquivalenceError with both results for caller sealing.
    """
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or not 1 <= max_steps <= 300:
        raise ValueError('Probe max_steps must be an integer in [1,300]')
    if config.get('control_budget') != 300 or config.get('source_horizon') != 10:
        raise ValueError('Probe requires the registered native10 / total300 protocol')
    callback = reserve.reserve if hasattr(reserve, 'reserve') else reserve
    if not callable(callback):
        raise TypeError('reserve must be a ledger or callable')
    native, native_arrays = _run(engine, case, config, callback, stage, 'native', max_steps)
    raw, raw_arrays = _run(engine, case, config, callback, stage, 'raw', max_steps)
    arrays = {f'{side}_{name}': value for side, data in [('native', native_arrays), ('raw', raw_arrays)]
              for name, value in data.items()}
    checks = {}
    for name in ('actions', 'generated_plans', 'generated_steps', 'actual_sampling_seeds',
                 'actual_sampling_steps', 'success_flags', 'done_flags'):
        checks[name + '_bit_identical'] = _bit_equal(native_arrays[name], raw_arrays[name])
    first, second = native_arrays['physics_states'], raw_arrays['physics_states']
    same_shape = first.shape == second.shape
    physics_error = float(np.abs(first - second).max()) if same_shape else None
    checks['physics_within_1e_10'] = same_shape and bool(np.allclose(first, second, atol=1e-10, rtol=0))
    checks['rewards_within_1e_8'] = (native_arrays['rewards'].shape == raw_arrays['rewards'].shape and
                                   bool(np.allclose(native_arrays['rewards'], raw_arrays['rewards'], atol=1e-8, rtol=0)))
    for name in ('actual_steps', 'success', 'terminal', 'stop_reason', 'initial_image_sha256',
                 'endpoint_image_sha256', 'initial_fingerprint', 'final_fingerprint'):
        checks[name + '_equal'] = native[name] == raw[name]
    for name in ('fresh_at_exact_natural_boundaries', 'first_action_matches_captured_plan_zero_bitwise',
                 'every_action_matches_captured_first_ten_bitwise'):
        checks[name] = native[name] and raw[name]
    native_lengths = native['actual_internal_queue_lengths']
    lengths_available = all(value is not None for value in native_lengths)
    if lengths_available:
        checks['actual_native_queue_naturally_exhausted'] = all(value == 9 - step % 10
                                                               for step, value in enumerate(native_lengths))
    native_noise = [row['noise_sha256'] for row in native['decisions']]
    raw_noise = [row['noise_sha256'] for row in raw['decisions']]
    noise_available = bool(native_noise and raw_noise) and all(value is not None for value in native_noise + raw_noise)
    if hasattr(engine, 'hook'):
        checks['initial_flow_noise_available_and_equal'] = noise_available and native_noise == raw_noise
    failed = [name for name, passed in checks.items() if not passed]
    metadata = dict(status='failed' if failed else 'passed', diagnostic='actual_native_action_vs_independent_raw_native10',
                    case_id=case['case_id'], env_seed=case['env_seed'], task=case['task'],
                    source_horizon=10, generated_horizon=50, control_budget=300,
                    maximum_control_steps_per_run=max_steps, counted_runs=2,
                    seed_namespace=config['seed_namespace'], seed_index='source natural decision index',
                    G0_monitoring_executed=False, effectiveness_evidence=False,
                    checks=checks, failed_checks=failed, runs={'native': native, 'raw': raw},
                    physics_maximum_absolute_error=physics_error, physics_absolute_tolerance=1e-10,
                    actual_native_queue_lengths_available=lengths_available,
                    initial_flow_noise_available=noise_available, storage_owned_by_caller=True)
    if failed:
        raise Native10EquivalenceError(metadata, arrays)
    return metadata, arrays
