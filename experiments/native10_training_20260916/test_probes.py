"""CPU physical stubs for fixed-state, four-attempt raw/clipped probes."""
from types import SimpleNamespace

import numpy as np
import pytest

from .probes import RawClippedProbeError, run_raw_clipped_probe


class Runtime:
    def __init__(self, clamp=True, contacts=True, reward_raw=False, early_success=False, force_only=False):
        self.clamp, self.contacts, self.reward_raw = clamp, contacts, reward_raw
        self.early_success, self.force_only = early_success, force_only
        self.backend = SimpleNamespace(_env=SimpleNamespace(_env=SimpleNamespace()))
        self.native = self.backend._env._env
        self.native.model = SimpleNamespace(nq=2, nv=2, nu=2, ngeom=3,
            actuator_ctrllimited=np.ones(2, dtype=np.uint8), actuator_ctrlrange=np.asarray([[-1.,1.],[-1.,1.]]),
            actuator_forcelimited=np.zeros(2, dtype=np.uint8), actuator_forcerange=np.zeros((2,2)),
            opt=SimpleNamespace(disableflags=0, timestep=.0025), names=b'cpu_probe_stub\x00')

    def reset_at_cut(self, cut):
        self.step_index = cut
        contact = [SimpleNamespace(geom1=0, geom2=2, dist=-.003)] if self.contacts else []
        self.native.data = SimpleNamespace(qpos=np.zeros(2), qvel=np.zeros(2), actuator_force=np.zeros(2),
            qfrc_actuator=np.zeros(2), ctrl=np.zeros(2), ncon=len(contact), contact=contact, time=cut/30,
            act=np.empty(0), qacc_warmstart=np.zeros(2), mocap_pos=np.zeros((1,3)),
            mocap_quat=np.asarray([[1.,0.,0.,0.]]), userdata=np.empty(0))

    def physics_state(self):
        data = self.native.data
        # Match the actual runtime layout, including the raw ctrl buffer that
        # is expressly allowed to differ under equivalent actuator saturation.
        return np.concatenate([np.asarray(getattr(data, name)).reshape(-1)
            for name in ('qpos','qvel','act','ctrl','qacc_warmstart','mocap_pos','mocap_quat','userdata')]
            + [np.asarray([data.time])])

    def execute(self, command):
        data = self.native.data
        data.ctrl = np.asarray([command[3], -command[3]], dtype=np.float64)
        effective = np.clip(data.ctrl, -1, 1) if self.clamp else data.ctrl
        data.actuator_force = effective.copy()
        data.qfrc_actuator = effective.copy()
        if self.force_only:
            data.qfrc_actuator = data.ctrl.copy()
        data.qvel += effective * .01
        data.qpos += data.qvel * .01
        data.time += 1/30
        self.step_index += 1
        reward = float(command[3] if self.reward_raw else effective[0])
        return reward, self.early_success, False


class Trace:
    def __init__(self, runtime, cut):
        self.runtime = runtime
        self.step = cut
        self.rewards, self.successes, self.dones = [], [], []

    @property
    def terminal(self):
        return bool(self.dones and self.dones[-1])

    def execute(self, runtime, command):
        reward, success, done = runtime.execute(command)
        self.rewards.append(reward)
        self.successes.append(success)
        self.dones.append(done or success)
        self.step += 1


class Engine:
    def __init__(self, **kwargs):
        self.runtime = Runtime(**kwargs)
        self.events = []
        self.rows = []
        self.verify_count = 0

    def reserve(self, stage, kind, identity):
        self.events.append(('reserve', identity))
        row = dict(number=len(self.rows)+1, stage=stage, kind=kind, identity=identity)
        self.rows.append(row)
        return row

    def restore(self, case, source, cut):
        self.events.append(('restore', cut))
        self.runtime.reset_at_cut(cut)
        return Trace(self.runtime, cut), None, None

    def verify(self):
        self.verify_count += 1


CASE = dict(case_id='shelf-place-v3__801', env_seed=801, task='shelf-place-v3')


def run(engine, **kwargs):
    return run_raw_clipped_probe(engine, CASE, '/nonexistent/cpu_stub_source', 5,
                                 engine.restore, engine, **kwargs)


def test_actuator_saturation_matches_physics_force_contact_and_flags_but_not_ctrl():
    engine = Engine()
    metadata, arrays = run(engine)
    assert metadata['status'] == 'passed' and metadata['counted_runs'] == 4
    assert len(engine.rows) == engine.verify_count == 4
    assert [event[0] for event in engine.events] == ['reserve','restore'] * 4
    assert metadata['initial_contact_seen'] and metadata['contact_seen']
    for sign in ('positive', 'negative'):
        pair = metadata['pairs'][sign]
        assert pair['physical_and_binary_equivalence'] and pair['reward_comparison']['equal']
        assert not pair['ctrl_comparison_for_information_only']['equal']
        assert not np.array_equal(arrays[sign+'_raw_physics_state'], arrays[sign+'_clipped_physics_state'])
        np.testing.assert_array_equal(arrays[sign+'_raw_physics_state_without_ctrl'],
                                      arrays[sign+'_clipped_physics_state_without_ctrl'])
        assert arrays[sign+'_raw_qpos'].shape == (4,2), 'Initial state plus three post-control states'
        assert arrays[sign+'_raw_contact_geom'].shape == (4,1,2)
        np.testing.assert_array_equal(arrays[sign+'_raw_commands'][:,:3], np.zeros((3,3)))
    model = metadata['runs']['positive_raw']['model']
    assert model['controls']['actuator_ctrllimited'] == [1,1]
    assert model['controls']['actuator_ctrlrange'] == [[-1.,1.],[-1.,1.]]
    assert len(model['control_metadata_sha256']) == 64 and model['disableflags'] == 0


def test_reward_only_difference_is_reported_without_claiming_different_dynamics():
    metadata, _ = run(Engine(reward_raw=True))
    assert metadata['status'] == 'passed'
    for pair in metadata['pairs'].values():
        assert pair['physical_and_binary_equivalence'] and not pair['reward_comparison']['equal']
        assert pair['reward_comparison']['maximum_absolute_error'] == .5


@pytest.mark.parametrize('kwargs,expected_failure', [({'clamp':False}, 'positive.qpos'),
                                                    ({'force_only':True}, 'positive.qfrc_actuator')])
def test_non_equivalence_raises_with_all_four_payloads(kwargs, expected_failure):
    engine = Engine(**kwargs)
    with pytest.raises(RawClippedProbeError) as error:
        run(engine)
    assert expected_failure in error.value.metadata['failed_checks']
    assert len(error.value.metadata['runs']) == 4 and len(engine.rows) == 4
    assert 'negative_clipped_qfrc_actuator' in error.value.arrays


def test_absence_of_contacts_is_explicit_and_never_triggers_extra_state_search():
    engine = Engine(contacts=False)
    metadata, arrays = run(engine)
    assert metadata['status'] == 'passed' and not metadata['contact_seen']
    assert not metadata['contact_based_state_search'] and len(engine.rows) == 4
    assert 'not established' in metadata['contact_coverage']
    assert arrays['positive_raw_contact_geom'].shape == (4,0,2)


def test_success_stops_each_short_probe_before_extra_controls():
    engine = Engine(early_success=True)
    metadata, arrays = run(engine)
    assert metadata['status'] == 'passed'
    assert all(row['actual_steps'] == 1 for row in metadata['runs'].values())
    assert arrays['positive_raw_commands'].shape == (1,4)
    assert arrays['positive_raw_qpos'].shape == (2,2)


def test_already_terminal_restore_is_not_misreported_as_a_passed_physical_probe():
    engine = Engine()
    def terminal_restore(case, source, cut):
        trace, snapshot, anchor = engine.restore(case, source, cut)
        trace.dones.append(True)
        return trace, snapshot, anchor
    with pytest.raises(RawClippedProbeError) as error:
        run_raw_clipped_probe(engine, CASE, '/nonexistent/cpu_stub_source', 5,
                              terminal_restore, engine)
    assert all(row['actual_steps'] == 0 for row in error.value.metadata['runs'].values())
    assert 'positive_raw.no_executed_controls' in error.value.metadata['failed_checks']
    assert len(engine.rows) == 4


@pytest.mark.parametrize('steps', [0, 4, True])
def test_unregistered_probe_length_cannot_reserve_or_restore(steps):
    engine = Engine()
    with pytest.raises(ValueError):
        run(engine, steps=steps)
    assert engine.rows == [] and engine.events == []
