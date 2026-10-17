from dataclasses import dataclass
import hashlib
import json
import numpy as np

from .validation import ContractError


@dataclass(frozen=True)
class Protocol:
    H: int = 10
    C: int = 10
    generated_length: int = 50
    monitor_interval: int = 5
    forecast_steps: int = 5
    budget: int = 300
    max_interventions: int = 1
    gate_threshold: float = .05
    historical_label_commitment: int = 5
    q_suffix_horizon: int = 10

    def __post_init__(self):
        if (self.H not in (10, 20, 30, 40, 50) or self.C != 10 or self.generated_length != 50
                or self.monitor_interval != 5 or self.forecast_steps != 5 or self.budget != 300
                or self.max_interventions != 1 or self.gate_threshold != .05
                or self.historical_label_commitment != 5 or self.q_suffix_horizon != 10):
            raise ContractError('Protocol differs from P00 core method contract')


class CoreQueue:
    """Explicit normal-H / intervention-C clock, independent of model/internal queues."""
    def __init__(self, protocol, method):
        if method not in ('N', 'R', 'Post', 'Velocity'):
            raise ContractError('Unknown core method')
        self.protocol, self.method = protocol, method
        self.step, self.interventions = 0, 0
        self.plan, self.plan_id, self.plan_start = None, None, None
        self.commitment = protocol.H
        self.phase = 'normal'
        self.terminal = False
        self.termination_reason = None
        self.cut_step = None

    @property
    def age(self):
        return 0 if self.plan is None else self.step - self.plan_start

    @property
    def remaining(self):
        return 0 if self.plan is None else min(self.commitment - self.age, self.protocol.budget - self.step)

    @property
    def needs_plan(self):
        return not self.terminal and self.step < self.protocol.budget and self.plan is None

    def observe_terminal(self, *, success=False, terminated=False, truncated=False):
        if success or terminated or truncated or self.step >= self.protocol.budget:
            self.terminal = True
            self.termination_reason = ('success' if success else 'environment_terminated' if terminated
                                       else 'environment_truncated' if truncated else 'budget')
            self.plan = None

    def _install(self, plan, plan_id, commitment, phase):
        raw = np.asarray(plan)
        if raw.shape != (50, 4) or raw.dtype != np.float32 or not np.isfinite(raw).all():
            raise ContractError('Expected finite float32 raw50x4, without replan-only clipping')
        self.plan = raw.copy()
        self.plan_id, self.plan_start = plan_id, self.step
        self.commitment, self.phase = commitment, phase

    def install_natural(self, plan, plan_id):
        if not self.needs_plan:
            raise ContractError('Only an empty normal queue may receive a new nativeH plan')
        self._install(plan, plan_id, self.protocol.H, 'normal')

    def monitor_eligible(self):
        p = self.protocol
        return bool(not self.terminal and self.plan is not None and self.phase == 'normal'
                    and self.interventions == 0 and self.step % p.monitor_interval == 0
                    and self.age > 0 and self.remaining >= p.forecast_steps
                    and p.budget - self.step >= p.C)

    def alarm(self, gate):
        if not np.isfinite(gate):
            raise ContractError('Nonfinite G0 value')
        return self.method != 'N' and self.monitor_eligible() and gate > self.protocol.gate_threshold

    def install_intervention(self, plan, plan_id, gate):
        if not self.alarm(gate):
            raise ContractError('Intervention outside first legal G0 alarm')
        self.interventions += 1
        self.cut_step = self.step
        self._install(plan, plan_id, self.protocol.C, 'intervention')

    def command(self):
        if self.terminal or self.plan is None or self.remaining <= 0:
            raise ContractError('No executable command')
        return self.plan[self.age].copy()

    def advance(self, *, success=False, terminated=False, truncated=False):
        if self.terminal or self.plan is None:
            raise ContractError('No action to account for')
        self.step += 1
        exhausted = self.age == self.commitment
        old_phase = self.phase
        self.observe_terminal(success=success, terminated=terminated, truncated=truncated)
        if self.terminal:
            return self.termination_reason
        if exhausted:
            # The remaining generated tail is always discarded, including after C10.
            self.plan = None
            self.plan_id, self.plan_start = None, None
            self.commitment, self.phase = self.protocol.H, 'normal'
            return 'intervention_complete' if old_phase == 'intervention' else 'natural_exhaustion'
        return None


def paired_seed(namespace, source_id, H, cut, repeat, decision, purpose):
    """Host and method are deliberately absent. H identifies its own trajectory."""
    payload = json.dumps([namespace, source_id, H, cut, repeat, decision, purpose], separators=(',', ':'))
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], 'big') % (2**31 - 1)


def legal_cuts(H):
    p = Protocol(H=H)
    return [t for t in range(0, p.budget, p.monitor_interval)
            if t % H > 0 and H - t % H >= p.forecast_steps and p.budget - t >= p.C]
