"""CPU stubs exercise native/raw comparison and separately counted resets."""
from collections import deque
from types import SimpleNamespace

import numpy as np
import pytest

from .diagnostics import Native10EquivalenceError, run_native10_equivalence


class Ledger:
    def __init__(self, events):
        self.rows = []
        self.events = events

    def reserve(self, stage, kind, identity):
        row = dict(number=len(self.rows)+1, stage=stage, kind=kind, identity=identity)
        self.rows.append(row)
        self.events.append(('reserve', kind))
        return row


class Runtime:
    def __init__(self, events, hook, success_at=None, terminal_at=None):
        self.events, self.hook = events, hook
        self.success_at, self.terminal_at = success_at, terminal_at
        self.backend = SimpleNamespace(policy=SimpleNamespace(_action_queue=deque(maxlen=10)))
        self.clear_steps = []
        self.native_calls = 0
        self.mismatch_first_command = False

    def clear_policy(self, horizon):
        assert horizon == 10
        self.backend.policy._action_queue = deque(maxlen=horizon)
        self.clear_steps.append(self.t)

    def reset(self, case, horizon):
        self.events.append(('reset', horizon))
        self.t = 0
        self.position = np.zeros(4, np.float64)
        self.clear_policy(horizon)

    def native_action(self, seed):
        self.native_calls += 1
        queue = self.backend.policy._action_queue
        plan = None
        if not queue:
            plan = np.random.default_rng(seed).uniform(-.1, .1, (50, 4)).astype(np.float32)
            plan[:10, 3] = np.float32(1.4)
            plan[0, 0] = np.float32(-0.)
            plan[10:] = np.float32(9.)
            queue.extend(command.copy() for command in plan[:10])
            self.hook.last_noise_sha = str(seed)
        action = queue.popleft()
        if plan is not None and self.mismatch_first_command:
            action = action.copy()
            action[0] = np.float32(0.)  # Numerically equal but not bit-identical.
        return action, plan, 0.

    def step(self, command):
        self.t += 1
        self.position += np.asarray(command, np.float64)
        return dict(reward=float(self.position[0]), success=self.t == self.success_at,
                    done=self.t == self.terminal_at)

    def frame(self):
        return np.full((2, 2, 3), self.t % 255, np.uint8)

    def physics_state(self):
        return np.r_[self.t, self.position]

    def fingerprint(self):
        return self.physics_state().tobytes().hex()


class Engine:
    def __init__(self, success_at=None, terminal_at=None):
        self.events = []
        self.hook = SimpleNamespace(begin=lambda loss: None, last_noise_sha=None)
        self.runtime = Runtime(self.events, self.hook, success_at, terminal_at)
        self.proposal_calls = []
        self.corrupt_proposal = False
        self.verified = 0

    def propose(self, seed):
        self.proposal_calls.append((self.runtime.t, seed))
        self.runtime.clear_policy(10)
        _, plan, seconds = self.runtime.native_action(seed)
        if self.corrupt_proposal:
            plan[1, 1] += .01
        return plan, dict(policy_calls=1, seconds=seconds, fallback=None,
                         noise_sha256=self.hook.last_noise_sha)

    def verify(self):
        self.verified += 1


def arguments(engine):
    case = dict(case_id='disassemble-v3__717', task='disassemble-v3', env_seed=717)
    config = dict(control_budget=300, source_horizon=10, seed_namespace='native10_probe_unit')
    ledger = Ledger(engine.events)
    return case, config, ledger


def test_thirty_controls_compare_real_per_step_interface_to_three_raw_proposals():
    engine = Engine()
    case, config, ledger = arguments(engine)
    metadata, arrays = run_native10_equivalence(engine, case, config, ledger)
    assert metadata['status'] == 'passed' and all(metadata['checks'].values())
    assert len(ledger.rows) == 2 and [row['kind'] for row in ledger.rows] == ['native_queue_probe', 'raw_queue_probe']
    assert engine.events == [('reserve', 'native_queue_probe'), ('reset', 10),
                             ('reserve', 'raw_queue_probe'), ('reset', 10)]
    assert engine.runtime.native_calls == 30 + 3
    assert [row[0] for row in engine.proposal_calls] == [0, 10, 20]
    assert engine.verified == 2
    assert arrays['native_actions'].tobytes() == arrays['raw_actions'].tobytes()
    assert (arrays['native_actions'][:, 3] > 1).all(), 'Native raw commands must not be clipped'
    assert metadata['runs']['native']['actual_internal_queue_lengths'] == list(range(9, -1, -1)) * 3
    assert metadata['runs']['raw']['actual_internal_queue_lengths'] == [9] * 30
    assert metadata['initial_flow_noise_available']


@pytest.mark.parametrize('success_at,terminal_at,expected,reason', [(12, None, 12, 'success'),
                                                                  (None, 7, 7, 'environment_done')])
def test_early_success_or_termination_stops_both_paths_without_extra_commands(success_at, terminal_at, expected, reason):
    engine = Engine(success_at, terminal_at)
    case, config, ledger = arguments(engine)
    metadata, arrays = run_native10_equivalence(engine, case, config, ledger.reserve)
    assert metadata['status'] == 'passed' and len(ledger.rows) == 2
    assert len(arrays['native_actions']) == expected and len(arrays['raw_actions']) == expected
    for run in metadata['runs'].values():
        assert run['stop_reason'] == reason and run['terminal']


def test_command_divergence_fails_closed_and_exposes_both_runs_for_saving():
    engine = Engine()
    engine.corrupt_proposal = True
    case, config, ledger = arguments(engine)
    with pytest.raises(Native10EquivalenceError) as error:
        run_native10_equivalence(engine, case, config, ledger, max_steps=10)
    assert 'actions_bit_identical' in error.value.metadata['failed_checks']
    assert error.value.arrays['native_actions'].shape == (10, 4)
    assert error.value.arrays['raw_actions'].shape == (10, 4)
    assert len(ledger.rows) == 2


def test_first_native_action_requires_bitwise_match_even_when_numerically_equal():
    engine = Engine()
    engine.runtime.mismatch_first_command = True
    case, config, ledger = arguments(engine)
    with pytest.raises(Native10EquivalenceError) as error:
        run_native10_equivalence(engine, case, config, ledger, max_steps=1)
    assert 'first_action_matches_captured_plan_zero_bitwise' in error.value.metadata['failed_checks']


def test_original_300_budget_stops_without_a_new_sample_at_300():
    engine = Engine()
    case, config, ledger = arguments(engine)
    metadata, arrays = run_native10_equivalence(engine, case, config, ledger, max_steps=300)
    assert metadata['status'] == 'passed'
    assert len(arrays['native_actions']) == len(arrays['raw_actions']) == 300
    assert [row[0] for row in engine.proposal_calls] == list(range(0, 300, 10))
    assert all(run['stop_reason'] == 'control_budget' for run in metadata['runs'].values())


@pytest.mark.parametrize('limit', [0, -1, 301, True, 3.5])
def test_invalid_probe_limit_is_rejected_before_any_reservation_or_reset(limit):
    engine = Engine()
    case, config, ledger = arguments(engine)
    with pytest.raises(ValueError):
        run_native10_equivalence(engine, case, config, ledger, max_steps=limit)
    assert ledger.rows == [] and engine.events == []
