"""Private diagnostic counters; the public interface v1 is unchanged.

Hooks are installed only in the released diagnostic process, never in the
shared environment on disk. The CPU test uses fake classes and callbacks.
"""
from contextlib import contextmanager
from functools import wraps
import inspect
import json
import os
from pathlib import Path
import time
import uuid

from .resume import sha
from .validation import ContractError


EXPECTED_CAPS = {
    'model_initializations': 1,
    'environment_instances': 2,
    'wrapper_instances': 1,
    'taskset_constructions': 1,
    'taskset_reset_calls': 50,
    'wrapper_initialization_reset_calls': 1,
    'initialization_reset_calls': 51,
    'diagnostic_reset_calls': 1,
    'environment_reset_calls': 52,
    'reset_model_calls': 104,
    'initialization_do_simulation_calls': 5200,
    'initialization_physics_substeps': 26000,
    'policy_do_simulation_calls': 1,
    'policy_physics_substeps': 13,
}

CONTROL_MINIMUM_LIMITS = {
    'model_gpu_inference_calls': 5, 'simulator_attempts': 1, 'training_updates': 0,
    'model_initializations': 1, 'environment_instances': 2,
    'initialization_reset_calls': 51, 'diagnostic_reset_calls': 1,
    'environment_reset_calls': 52, 'initialization_physics_substeps': 26000,
    'policy_physics_substeps': 13,
}


def summarize_initialization(rows, caps):
    entered, ends = {}, {}
    for row in rows:
        key = row['event_id']
        if row['phase'] == 'entered':
            if key in entered:
                raise ContractError('Duplicate initialization entry')
            entered[key] = row
        else:
            if key not in entered or key in ends:
                raise ContractError('Unmatched initialization end')
            for field in ('units', 'source', 'stage', 'wall_start'):
                if row[field] != entered[key][field]:
                    raise ContractError('Initialization identity drift: ' + field)
            ends[key] = row
    counts = {key: sum(r['units'].get(key, 0) for r in entered.values()) for key in caps}
    returned = {key: sum(entered[e]['units'].get(key, 0) for e, r in ends.items()
                         if r['phase'] == 'returned') for key in caps}
    by_source = {}
    for row in entered.values():
        group = by_source.setdefault(row['stage'] + ':' + row['source'], {})
        for key, value in row['units'].items():
            group[key] = group.get(key, 0) + value
    if any(counts[k] > v for k, v in caps.items()):
        raise ContractError('Observed initialization cap exceeded')
    return {'caps': caps, 'entered_budget_usage': counts,
            'returned_operation_units': returned, 'entered_usage_by_source': by_source,
            'failed_events': sum(r['phase'] == 'failed' for r in ends.values()),
            'incomplete_event_ids': sorted(entered.keys() - ends.keys()),
            'count_semantics': 'durable entry attempts; terminal repeats metadata, no refund; returned units report completed calls separately',
            'physics_semantics': 'initialization frames are internal do_simulation work, not policy controls or diagnostic episodes; entered frames need not have all completed on failure'}


class InitializationAudit:
    def __init__(self, path, caps, gate=lambda: None, clock=time.monotonic):
        if caps != EXPECTED_CAPS or any(type(v) is not int for v in caps.values()):
            raise ContractError('Initialization caps differ from the audited standard shelf-place path')
        self.path = Path(path)
        self.path.touch(exist_ok=False)
        self.caps, self.used = dict(caps), dict.fromkeys(caps, 0)
        self.gate, self.clock = gate, clock
        self.stage, self.patches = 'initialization', []

    def append(self, row):
        with self.path.open('a') as stream:
            stream.write(json.dumps(row, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    @contextmanager
    def scope(self, stage):
        previous, self.stage = self.stage, stage
        try:
            yield
        finally:
            self.stage = previous

    def invoke(self, source, units, function):
        self.gate()
        if any(k not in self.caps or type(v) is not int or v < 0 for k, v in units.items()):
            raise ContractError('Invalid initialization units')
        if any(self.used[k] + v > self.caps[k] for k, v in units.items()):
            raise ContractError('Initialization budget exhausted before operation entry: ' + source)
        row = {'event_id': uuid.uuid4().hex, 'phase': 'entered', 'stage': self.stage,
               'source': source, 'units': dict(units), 'wall_start': self.clock(),
               'wall_end': None, 'error': None}
        self.append(row)
        for key, value in units.items():
            self.used[key] += value
        try:
            result = function()
        except BaseException as error:
            self.append({**row, 'phase': 'failed', 'wall_end': self.clock(), 'error': str(error)})
            raise
        self.append({**row, 'phase': 'returned', 'wall_end': self.clock()})
        return result

    def _patch(self, owner, name, factory):
        original = getattr(owner, name)
        # All patched attributes are owned directly by their class/module.
        if name not in vars(owner):
            raise ContractError('Expected direct source binding: ' + name)
        setattr(owner, name, factory(original))
        self.patches.append((owner, name, original))

    def install(self, task_module, native_class, native_base, mujoco_base, wrapper_class):
        def stage_call(stage, source, units):
            def factory(original):
                @wraps(original)
                def hooked(*args, **kwargs):
                    with self.scope(stage):
                        return self.invoke(source, units, lambda: original(*args, **kwargs))
                return hooked
            return factory

        self._patch(task_module, '_make_tasks', stage_call('taskset', 'metaworld._make_tasks', {'taskset_constructions': 1}))
        self._patch(wrapper_class, '__init__', stage_call('wrapper_initialization', 'MetaworldEnv.__init__', {'wrapper_instances': 1}))
        self._patch(wrapper_class, '_make_envs_task', stage_call('wrapper_initialization', 'MetaworldEnv._make_envs_task', {}))

        def native_constructor(original):
            @wraps(original)
            def hooked(*args, **kwargs):
                return self.invoke('SawyerShelfPlaceEnvV3.__init__', {'environment_instances': 1}, lambda: original(*args, **kwargs))
            return hooked
        self._patch(native_class, '__init__', native_constructor)

        def reset(original):
            @wraps(original)
            def hooked(env, *args, **kwargs):
                if not isinstance(env, native_class):
                    raise ContractError('Unexpected environment class in diagnostic')
                units = {'environment_reset_calls': 1}
                if self.stage == 'taskset':
                    units.update(taskset_reset_calls=1, initialization_reset_calls=1)
                elif self.stage == 'wrapper_initialization':
                    units.update(wrapper_initialization_reset_calls=1, initialization_reset_calls=1)
                elif self.stage == 'diagnostic_reset':
                    units['diagnostic_reset_calls'] = 1
                else:
                    raise ContractError('Unexpected native reset origin: ' + self.stage)
                return self.invoke('SawyerXYZEnv.reset', units, lambda: original(env, *args, **kwargs))
            return hooked
        self._patch(native_base, 'reset', reset)

        def reset_model(original):
            @wraps(original)
            def hooked(*args, **kwargs):
                return self.invoke('SawyerShelfPlaceEnvV3.reset_model', {'reset_model_calls': 1}, lambda: original(*args, **kwargs))
            return hooked
        self._patch(native_class, 'reset_model', reset_model)

        def do_simulation(original):
            @wraps(original)
            def hooked(env, ctrl, n_frames):
                if type(n_frames) is not int:
                    raise ContractError('Noninteger physics frame request')
                if self.stage == 'policy_control':
                    if n_frames != 13:
                        raise ContractError('First 30Hz control must request 13 physics substeps')
                    units = {'policy_do_simulation_calls': 1, 'policy_physics_substeps': n_frames}
                elif self.stage in ('taskset', 'wrapper_initialization', 'diagnostic_reset'):
                    if n_frames != 5:
                        raise ContractError('Standard initialization frame_skip drifted')
                    units = {'initialization_do_simulation_calls': 1, 'initialization_physics_substeps': n_frames}
                else:
                    raise ContractError('Unclassified simulation work: ' + self.stage)
                return self.invoke('MujocoEnv.do_simulation', units, lambda: original(env, ctrl, n_frames))
            return hooked
        self._patch(mujoco_base, 'do_simulation', do_simulation)

    def install_real(self, wrapper_class, source_manifest, wrapper_source):
        # Called only below the compute gate in preflight_pi05, never CPU validation.
        import metaworld
        from metaworld.envs.sawyer_shelf_place_v3 import SawyerShelfPlaceEnvV3
        from metaworld.sawyer_xyz_env import SawyerXYZEnv
        from gymnasium.envs.mujoco.mujoco_env import MujocoEnv
        targets = {'metaworld': metaworld, 'native_class': SawyerShelfPlaceEnvV3,
                   'native_base': SawyerXYZEnv, 'mujoco_base': MujocoEnv}
        for key, target in targets.items():
            if Path(inspect.getfile(target)).resolve() != Path(source_manifest['source_hooks'][key]).resolve():
                raise ContractError('Loaded external source differs from manifest: ' + key)
        if Path(inspect.getfile(wrapper_class)).resolve() != Path(wrapper_source).resolve():
            raise ContractError('Loaded wrapper is not the frozen vendored source')
        for ref in source_manifest['files']:
            if sha(ref['path']) != ref['sha256']:
                raise ContractError('External initialization source changed: ' + ref['path'])
        if metaworld._N_GOALS != 50 or metaworld.MT1.ENV_NAMES.count('shelf-place-v3') != 1:
            raise ContractError('Standard MetaWorld task-set configuration drifted')
        self.install(metaworld, SawyerShelfPlaceEnvV3, SawyerXYZEnv, MujocoEnv, wrapper_class)

    def uninstall(self):
        for owner, name, original in reversed(self.patches):
            setattr(owner, name, original)
        self.patches.clear()

    def summary(self):
        return summarize_initialization([json.loads(x) for x in self.path.read_text().splitlines()], self.caps)

    def assert_complete(self):
        receipt = self.summary()
        if receipt['entered_budget_usage'] != self.caps or receipt['returned_operation_units'] != self.caps or receipt['incomplete_event_ids'] or receipt['failed_events']:
            raise ContractError('Actual standard initialization counts differ from the finite proposal')
