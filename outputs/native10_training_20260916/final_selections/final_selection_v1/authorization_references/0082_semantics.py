"""Independent raw-command queues for native10 sources and paired branches.

This module never reads or mutates a policy's internal normalized-action queue.
The adapter supplies each captured raw 50x4 command plan. Only its first ten
commands enter a natural native10 queue, and commands retain their original
floating dtype and values, including values outside [-1, 1].
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, Mapping

import numpy as np


HORIZON = 10
PLAN_SHAPE = (50, 4)
NORMAL_METHOD = 'continue_native10'
INTERVENTION_METHODS = frozenset(('alarm_replan10', 'velocity', 'direct', 'post'))
METHOD_ALIASES = dict(normal_native10=NORMAL_METHOD, replan='alarm_replan10',
                      velocity_matched='velocity', direct_matched='direct', post_matched='post')


def _method(name):
    canonical = METHOD_ALIASES.get(name, name)
    if canonical not in INTERVENTION_METHODS | {NORMAL_METHOD}:
        raise ValueError('Unknown native10 branch method')
    return canonical


def _integer(value, name):
    if isinstance(value, (bool, np.bool_)) or int(value) != value:
        raise ValueError(f'{name} must be an integer')
    return int(value)


def _plan(raw_plan):
    result = np.array(raw_plan, copy=True)
    if result.shape != PLAN_SHAPE or result.dtype.kind != 'f' or not np.isfinite(result).all():
        raise ValueError('Expected one finite floating raw 50x4 command plan')
    result.setflags(write=False)
    return result


def _sha(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


@dataclass(frozen=True)
class QueueSnapshot:
    """Frozen cut state of an independently managed raw native10 queue."""

    raw_plan: np.ndarray
    plan_start_step: int
    step: int
    budget: int = 300

    def __post_init__(self):
        for name in ('plan_start_step', 'step', 'budget'):
            object.__setattr__(self, name, _integer(getattr(self, name), name))
        if not 0 <= self.plan_start_step <= self.step < self.budget:
            raise ValueError('Snapshot must describe a live, nonnegative cut before the budget')
        if not 0 <= self.age < HORIZON:
            raise ValueError('Snapshot requires the current natural queue; replace an exhausted plan first')
        object.__setattr__(self, 'raw_plan', _plan(self.raw_plan))

    @property
    def age(self):
        return self.step - self.plan_start_step

    @property
    def remaining_steps(self):
        """Remaining commands in the ten-step queue, before budget truncation."""
        return HORIZON - self.age

    @property
    def remaining_commands(self):
        return self.raw_plan[self.age:HORIZON].copy()

    def to_dict(self, include_plan=True):
        """JSON-ready metadata; raw_plan may instead be saved separately in NPZ."""
        result = dict(plan_start_step=self.plan_start_step, step=self.step, budget=self.budget,
                      horizon=HORIZON, age=self.age, remaining_steps=self.remaining_steps,
                      raw_plan_dtype=self.raw_plan.dtype.str, raw_plan_sha256=_sha(self.raw_plan))
        if include_plan:
            result['raw_plan'] = self.raw_plan.tolist()
        return result

    @classmethod
    def from_dict(cls, metadata: Mapping, raw_plan=None):
        if metadata.get('horizon') != HORIZON:
            raise ValueError('Snapshot horizon must be ten')
        values = metadata.get('raw_plan') if raw_plan is None else raw_plan
        if values is None:
            raise ValueError('Supply the separately saved raw_plan')
        plan = np.asarray(values, dtype=np.dtype(metadata['raw_plan_dtype']))
        if _sha(plan) != metadata['raw_plan_sha256']:
            raise ValueError('Snapshot raw command SHA changed')
        result = cls(plan, metadata['plan_start_step'], metadata['step'], metadata['budget'])
        if metadata.get('age') != result.age or metadata.get('remaining_steps') != result.remaining_steps:
            raise ValueError('Snapshot queue metadata is inconsistent')
        return result


class Native10Queue:
    """Raw queue with a checked environment-step clock.

    Source loop: if ``needs_plan(t)``, capture a raw plan then ``replace(plan,t)``;
    perform monitoring; finally execute ``pop(t)``. Natural boundaries therefore
    install the next plan before the alarm eligibility check sees age zero.
    Starting at zero gives source replans at 0,10,20,...; starting after an
    intervention gives its correctly shifted continuation cadence.
    """

    def __init__(self, start_step=0, budget=300):
        self.step = _integer(start_step, 'start_step')
        self.budget = _integer(budget, 'budget')
        if not 0 <= self.step <= self.budget:
            raise ValueError('Invalid queue start or budget')
        self._raw_plan = None
        self._plan_start_step = None

    def _check_step(self, step):
        if step is not None and _integer(step, 'step') != self.step:
            raise ValueError(f'Raw queue clock mismatch: expected {self.step}, received {step}')

    @property
    def age(self):
        return None if self._plan_start_step is None else self.step - self._plan_start_step

    @property
    def remaining_steps(self):
        if self._raw_plan is None:
            return 0
        return min(HORIZON - self.age, self.budget - self.step)

    def needs_plan(self, step=None):
        self._check_step(step)
        return self.step < self.budget and (self._raw_plan is None or self.age == HORIZON)

    def replace(self, raw_plan, step=None):
        self._check_step(step)
        if not self.needs_plan():
            raise ValueError('May replace only an empty/exhausted natural queue before the budget')
        self._raw_plan = _plan(raw_plan)
        self._plan_start_step = self.step

    def peek_block(self, length=5, step=None):
        self._check_step(step)
        length = _integer(length, 'length')
        if length <= 0 or length > self.remaining_steps:
            raise ValueError('Requested block extends beyond the legal queue remainder or budget')
        return self._raw_plan[self.age:self.age + length].copy()

    def peek(self, step=None):
        return self.peek_block(1, step)[0]

    def pop(self, step=None):
        command = self.peek(step)
        self.step += 1
        return command

    def monitor_ready(self, step=None, monitor_interval=5, forecast_steps=5):
        """Five-step monitoring can still be logged when active intervention is forbidden."""
        self._check_step(step)
        monitor_interval = _integer(monitor_interval, 'monitor_interval')
        forecast_steps = _integer(forecast_steps, 'forecast_steps')
        if monitor_interval <= 0 or forecast_steps <= 0:
            raise ValueError('Monitor interval and forecast window must be positive')
        return bool(self._raw_plan is not None and 0 <= self.age < HORIZON
                    and self.step % monitor_interval == 0
                    and self.remaining_steps >= forecast_steps)

    def alarm_eligible(self, step=None, monitor_interval=5, forecast_steps=5):
        return bool(self.monitor_ready(step, monitor_interval, forecast_steps)
                    and self.age > 0 and self.budget - self.step >= HORIZON)

    def snapshot(self, step=None):
        self._check_step(step)
        if self._raw_plan is None or self.age == HORIZON or self.step >= self.budget:
            raise ValueError('Snapshot requires a live, populated natural queue')
        return QueueSnapshot(self._raw_plan, self._plan_start_step, self.step, self.budget)

    @classmethod
    def from_snapshot(cls, snapshot):
        result = cls(snapshot.step, snapshot.budget)
        result._raw_plan = _plan(snapshot.raw_plan)
        result._plan_start_step = snapshot.plan_start_step
        return result


@dataclass(frozen=True)
class BranchPrefix:
    method: str
    commands: np.ndarray
    cut_step: int
    requested_steps: int
    budget: int

    def __post_init__(self):
        object.__setattr__(self, 'method', _method(self.method))
        for name in ('cut_step', 'requested_steps', 'budget'):
            object.__setattr__(self, name, _integer(getattr(self, name), name))
        if not 0 <= self.cut_step < self.budget or not 1 <= self.requested_steps <= HORIZON:
            raise ValueError('Invalid prefix clock or requested length')
        if self.method in INTERVENTION_METHODS and (self.requested_steps != HORIZON or self.budget - self.cut_step < HORIZON):
            raise ValueError('Active intervention requires a complete ten-step budget')
        commands = np.array(self.commands, copy=True)
        expected = min(self.requested_steps, self.budget - self.cut_step)
        if commands.shape != (expected, 4) or commands.dtype.kind != 'f' or not np.isfinite(commands).all():
            raise ValueError('Prefix must contain exactly the finite budget-limited raw commands')
        commands.setflags(write=False)
        object.__setattr__(self, 'commands', commands)

    @property
    def stop_step(self):
        return self.cut_step + len(self.commands)

    @property
    def budget_truncated(self):
        return len(self.commands) < self.requested_steps

    @property
    def next_sample_step(self):
        """First continuation sample if the prefix completes without termination."""
        return self.stop_step if self.stop_step < self.budget else None


def make_branch_prefix(snapshot, method, intervention_plan=None):
    """Choose legal original remainder or a fresh ten-step intervention prefix."""
    method = _method(method)
    if method == NORMAL_METHOD:
        if intervention_plan is not None:
            raise ValueError('Normal branch must retain its original raw queue, without a new proposal')
        requested = snapshot.remaining_steps
        commands = snapshot.remaining_commands
    elif method in INTERVENTION_METHODS:
        if not Native10Queue.from_snapshot(snapshot).alarm_eligible():
            raise ValueError('Active intervention requires a legal nonboundary midpoint and at least ten remaining steps')
        if intervention_plan is None:
            raise ValueError('Intervention requires its specified raw 50x4 plan')
        requested = HORIZON
        commands = _plan(intervention_plan)[:HORIZON]
    else:
        raise ValueError('Unknown native10 branch method')
    commands = commands[:max(0, snapshot.budget - snapshot.step)]
    return BranchPrefix(method, commands, snapshot.step, requested, snapshot.budget)


@dataclass(frozen=True)
class PrefixExecution:
    actual_steps: int
    stop_step: int
    terminated: bool
    budget_exhausted: bool
    prefix_complete: bool
    next_sample_step: int | None


def execute_prefix(prefix: BranchPrefix, execute: Callable, terminal: Callable,
                   step: Callable | None = None):
    """Execute via a caller-owned Trace; perform no sampling or queue mutation.

    ``execute(command)`` should execute one raw command, ``terminal()`` reports
    done/success, and optional ``step()`` supplies Trace.step for clock checks.
    The caller starts an empty Native10Queue at the returned next_sample_step;
    a None value means success/termination or the original budget ended first.
    """
    current = prefix.cut_step
    if step is not None and step() != current:
        raise ValueError('Trace does not start at the specified cut')
    actual = 0
    for command in prefix.commands:
        if terminal() or current >= prefix.budget:
            break
        execute(command.copy())
        actual += 1
        current += 1
        if step is not None and step() != current:
            raise ValueError('execute must advance the environment exactly one control step')
    ended = bool(terminal())
    complete = actual == len(prefix.commands)
    exhausted = current >= prefix.budget
    next_sample = current if complete and not ended and not exhausted else None
    return PrefixExecution(actual, current, ended, exhausted, complete, next_sample)
