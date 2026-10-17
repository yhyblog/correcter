"""Pure CPU native10 queue tests: cadence, branch prefixes and raw commands."""
import json

import numpy as np
import pytest

from experiments.native10_training_20260916.semantics import (
    INTERVENTION_METHODS, NORMAL_METHOD, Native10Queue, QueueSnapshot,
    execute_prefix, make_branch_prefix,
)


def plan(offset=0.):
    # Deliberately outside [-1,1], with distinct timesteps and coordinates.
    return (np.arange(200, dtype=np.float32).reshape(50, 4) / 100 + offset)


def cut_snapshot(cut=5, budget=300):
    queue = Native10Queue(budget=budget)
    for t in range(cut + 1):
        if queue.needs_plan(t):
            queue.replace(plan(t), t)
        if t == cut:
            return queue.snapshot(t)
        queue.pop(t)


def test_sources_sample_every_ten_from_initial_and_boundary_age_zero_cannot_alarm():
    queue = Native10Queue()
    samples, alarms, actions = [], [], []
    for t in range(300):
        if queue.needs_plan(t):
            samples.append(t)
            queue.replace(plan(t), t)
        if t % 5 == 0:
            assert queue.peek_block(5, t).shape == (5, 4)
            if t % 10 == 0:
                assert queue.age == 0 and not queue.alarm_eligible(t)
            if queue.alarm_eligible(t):
                alarms.append(t)
        actions.append(queue.pop(t))
    assert samples == list(range(0, 300, 10))
    assert alarms == list(range(5, 290, 10))
    assert not queue.needs_plan(300) and not queue.alarm_eligible(300)
    for t, action in enumerate(actions):
        np.testing.assert_array_equal(action, plan((t // 10) * 10)[t % 10])
    with pytest.raises(ValueError):
        queue.pop(300)


def test_cut_five_normal_prefix_preserves_only_original_five_raw_commands():
    snapshot = cut_snapshot()
    prefix = make_branch_prefix(snapshot, NORMAL_METHOD)
    assert prefix.requested_steps == 5 and prefix.next_sample_step == 10
    np.testing.assert_array_equal(prefix.commands, plan()[5:10])
    restored = Native10Queue.from_snapshot(snapshot)
    actual = [restored.pop(t) for t in range(5, 10)]
    np.testing.assert_array_equal(actual, plan()[5:10])
    assert restored.needs_plan(10)
    with pytest.raises(ValueError):
        restored.peek_block(5, 10)
    with pytest.raises(ValueError):
        make_branch_prefix(snapshot, NORMAL_METHOD, plan(9))


@pytest.mark.parametrize('method', sorted(INTERVENTION_METHODS))
def test_interventions_execute_ten_from_cut_and_shift_continuation_cadence(method):
    prefix = make_branch_prefix(cut_snapshot(), method, plan(2.25))
    assert prefix.requested_steps == 10 and prefix.next_sample_step == 15
    np.testing.assert_array_equal(prefix.commands, plan(2.25)[:10])
    suffix = Native10Queue(start_step=prefix.next_sample_step, budget=46)
    samples = []
    for t in range(15, 46):
        if suffix.needs_plan(t):
            samples.append(t)
            suffix.replace(plan(t), t)
        suffix.pop(t)
    assert samples == [15, 25, 35, 45]
    assert not suffix.needs_plan(46)


def test_snapshot_roundtrip_and_external_mutation_cannot_change_raw_original_queue():
    original = plan(-2.25)
    queue = Native10Queue()
    queue.replace(original)
    for t in range(5):
        queue.pop(t)
    snapshot = queue.snapshot(5)
    original.fill(0)
    expected = plan(-2.25)
    np.testing.assert_array_equal(snapshot.raw_plan, expected)
    assert snapshot.raw_plan.min() < -1
    full = QueueSnapshot.from_dict(json.loads(json.dumps(snapshot.to_dict())))
    separate = QueueSnapshot.from_dict(json.loads(json.dumps(snapshot.to_dict(include_plan=False))),
                                       raw_plan=expected)
    for restored in [full, separate]:
        assert restored.age == 5 and restored.remaining_steps == 5
        assert restored.raw_plan.dtype == expected.dtype
        np.testing.assert_array_equal(restored.raw_plan, expected)
    damaged = expected.copy()
    damaged[0, 0] += .01
    with pytest.raises(ValueError, match='SHA'):
        QueueSnapshot.from_dict(snapshot.to_dict(include_plan=False), raw_plan=damaged)
    with pytest.raises(ValueError):
        snapshot.raw_plan[0, 0] = 0


def test_replacing_pending_natural_queue_or_using_stale_clock_is_rejected():
    queue = Native10Queue()
    queue.replace(plan(), 0)
    with pytest.raises(ValueError, match='empty/exhausted'):
        queue.replace(plan(2), 0)
    with pytest.raises(ValueError, match='clock'):
        queue.pop(1)
    for t in range(10):
        queue.pop(t)
    assert not queue.alarm_eligible(10)
    with pytest.raises(ValueError, match='live'):
        queue.snapshot(10)
    queue.replace(plan(10), 10)
    assert queue.age == 0 and not queue.alarm_eligible(10)


class Trace:
    def __init__(self, cut, terminal_at=None):
        self.step = cut
        self.terminal_at = terminal_at
        self.commands = []
        # A fake policy queue catches accidental coupling or mutation.
        self.internal_normalized_queue = ('untouched',)

    @property
    def terminal(self):
        return self.terminal_at is not None and self.step >= self.terminal_at

    def execute(self, command):
        self.commands.append(command.copy())
        self.step += 1


@pytest.mark.parametrize('method,expected_stop', [(NORMAL_METHOD, 10), ('replan', 15)])
def test_prefix_executor_preserves_raw_commands_and_does_not_touch_internal_queue(method, expected_stop):
    prefix = make_branch_prefix(cut_snapshot(), method, None if method == NORMAL_METHOD else plan(2.25))
    trace = Trace(5)
    result = execute_prefix(prefix, trace.execute, lambda: trace.terminal, lambda: trace.step)
    assert result.stop_step == expected_stop and result.next_sample_step == expected_stop
    assert result.prefix_complete and not result.terminated and not result.budget_exhausted
    assert trace.internal_normalized_queue == ('untouched',)
    np.testing.assert_array_equal(np.asarray(trace.commands), prefix.commands)


@pytest.mark.parametrize('terminal_at,expected_count', [(5, 0), (8, 3), (15, 10)])
def test_success_or_terminal_stops_before_any_extra_execution_or_sampling(terminal_at, expected_count):
    prefix = make_branch_prefix(cut_snapshot(), 'direct_matched', plan(.25))
    trace = Trace(5, terminal_at)
    result = execute_prefix(prefix, trace.execute, lambda: trace.terminal, lambda: trace.step)
    assert result.actual_steps == expected_count and result.stop_step == terminal_at
    assert result.terminated and result.next_sample_step is None


def test_original_budget_300_ends_normal_queue_without_new_episode_budget():
    snapshot = cut_snapshot(295)
    prefix = make_branch_prefix(snapshot, NORMAL_METHOD)
    assert prefix.requested_steps == 5 and len(prefix.commands) == 5
    assert not prefix.budget_truncated
    trace = Trace(295)
    result = execute_prefix(prefix, trace.execute, lambda: trace.terminal, lambda: trace.step)
    assert result.actual_steps == 5 and result.stop_step == 300 and result.budget_exhausted
    assert result.next_sample_step is None


@pytest.mark.parametrize('cut', [0, 10, 11, 290, 295])
def test_active_intervention_rejects_natural_boundaries_off_schedule_and_late_cuts(cut):
    snapshot = cut_snapshot(cut)
    queue = Native10Queue.from_snapshot(snapshot)
    assert not queue.alarm_eligible()
    with pytest.raises(ValueError, match='legal nonboundary midpoint'):
        make_branch_prefix(snapshot, 'alarm_replan10', plan())
    if cut in [0, 10, 290, 295]:
        assert queue.monitor_ready(), 'Forbidden intervention must not suppress feasible monitoring'


def test_last_legal_intervention_is_complete_then_native_suffix_stops_at_300():
    prefix = make_branch_prefix(cut_snapshot(285), 'post', plan(.1))
    trace = Trace(285)
    result = execute_prefix(prefix, trace.execute, lambda: trace.terminal, lambda: trace.step)
    assert result.actual_steps == 10 and result.next_sample_step == 295
    queue = Native10Queue(start_step=295)
    queue.replace(plan(.2), 295)
    for t in range(295, 300):
        trace.execute(queue.pop(t))
    assert trace.step == 300 and not queue.needs_plan(300)


def test_legacy_method_aliases_emit_only_new_protocol_names():
    snapshot = cut_snapshot()
    for old, new in [('normal_native10', 'continue_native10'), ('replan', 'alarm_replan10'),
                     ('velocity_matched', 'velocity'), ('direct_matched', 'direct'), ('post_matched', 'post')]:
        prefix = make_branch_prefix(snapshot, old, None if new == NORMAL_METHOD else plan())
        assert prefix.method == new


def test_monitor_does_not_cross_budget_or_legal_queue_remainder():
    queue = Native10Queue(start_step=290, budget=297)
    queue.replace(plan(), 290)
    for t in range(290, 295):
        queue.pop(t)
    assert queue.remaining_steps == 2 and not queue.alarm_eligible(295)
    with pytest.raises(ValueError, match='remainder or budget'):
        queue.peek_block(5, 295)


def test_raw_plan_tail_after_first_ten_never_changes_native_execution():
    first, second = plan(), plan()
    second[10:] = -123.25
    queues = [Native10Queue(), Native10Queue()]
    for queue, value in zip(queues, [first, second]):
        queue.replace(value)
    for t in range(10):
        np.testing.assert_array_equal(queues[0].pop(t), queues[1].pop(t))
    assert all(queue.needs_plan(10) for queue in queues)
