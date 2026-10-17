"""Behavioral checks for the native-queue baseline, without GPUs or MetaWorld."""
import json

import numpy as np
import pytest

from ac_tmil.idea3.local_collection import Trace
from . import collection


class Runtime:
    def __init__(self):
        self.step_index = 0
        self.remaining = 0
        self.horizon = 50
        self.clears = []

    def physics_state(self):
        return np.asarray([self.step_index], dtype=np.float64)

    def frame(self):
        return np.full((2, 2, 3), self.step_index % 256, dtype=np.uint8)

    def step(self, action):
        self.step_index += 1
        return dict(reward=0., success=False, done=False)

    def clear_policy(self, horizon):
        self.clears.append((self.step_index, horizon))
        self.horizon, self.remaining = horizon, 0

    def native_action(self, seed):
        plan = None
        if not self.remaining:
            self.remaining = self.horizon
            plan = np.full((50, 4), .2, dtype=np.float32)
        self.remaining -= 1
        return np.full(4, .2, dtype=np.float32), plan, 0.


@pytest.mark.parametrize('method,cut,age,expected_clear,expected_horizon', [
    ('continue_old', 5, 5, 50, 50),
    ('continue_old', 45, 45, 50, 50),
    ('continue_old', 285, 35, 300, 50),
    ('replan', 5, 5, 15, 10),
])
def test_original_queue_reaches_natural_boundary_before_sampling(
        tmp_path, monkeypatch, method, cut, age, expected_clear, expected_horizon):
    monkeypatch.setattr(collection, 'ROOT', tmp_path)
    monkeypatch.setattr(collection, 'reserve_branch', lambda kind, identity: dict(number=1, kind=kind, identity=str(identity)))
    (tmp_path/'config.json').write_text('{}')
    source = tmp_path/'source'
    anchor = source/f'cut{cut:03d}'
    anchor.mkdir(parents=True)
    (anchor/'anchor.json').write_text(json.dumps(dict(plan_age=age)))
    engine = object.__new__(collection.FlowEngine)
    engine.runtime = Runtime()
    engine.study = dict(suffix_seed_namespace='behavioral_test')
    trace = Trace(engine.runtime)
    for _ in range(cut):
        trace.execute(engine.runtime, np.zeros(4, dtype=np.float32))
    engine.restore = lambda *args: (trace, {})
    case = dict(case_id='synthetic', task='synthetic-v3', env_seed=1, split='preflight')
    plan = np.full((50, 4), 2.25 if method == 'continue_old' else .25, dtype=np.float32)
    target = tmp_path/'branch'
    engine.branch(case, source, cut, method, plan, 0, target)
    summary = json.loads((target/'summary.json').read_text())
    assert engine.runtime.clears == [(expected_clear, expected_horizon)]
    expected_samples = list(range(expected_clear, 300, expected_horizon))
    assert [item['step'] for item in summary['suffix_seeds']] == expected_samples
    assert summary['suffix_policy_calls'] == len(expected_samples)
    assert summary['first_actual_resample_step'] == (expected_samples[0] if expected_samples else None)
    with np.load(target/'trajectory.npz') as archive:
        # A raw native action above one must survive in the recorded history.
        np.testing.assert_array_equal(archive['actions'][cut:expected_clear], plan[:expected_clear-cut])
        np.testing.assert_array_equal(archive['actual_sampling_steps'], expected_samples)
