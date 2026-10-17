"""Counted raw/clipped gripper effect probes on one preregistered cut.

No runtime is created, no file is written, and no contact state is searched for.
The caller restores the same designated cut for four separately counted runs.
Reward differences are reported separately from physical/binary equivalence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

import numpy as np


PHYSICS_ATOL = 1e-10
REWARD_ATOL = 1e-10
PHYSICS_FIELDS_WITHOUT_CTRL = ('qpos', 'qvel', 'act', 'qacc_warmstart',
                              'mocap_pos', 'mocap_quat', 'userdata')


class RawClippedProbeError(RuntimeError):
    def __init__(self, metadata, arrays):
        self.metadata = metadata
        self.arrays = arrays
        super().__init__('Raw/clipped physical equivalence failed: ' + ', '.join(metadata['failed_checks']))


def _hash(value):
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def _native_env(runtime):
    return runtime.backend._env._env


def loaded_model_metadata(native):
    """Identity of loaded control metadata, explicitly not a full MJB hash."""
    model = native.model
    controls = {}
    for name in ('actuator_ctrllimited', 'actuator_ctrlrange', 'actuator_forcelimited',
                 'actuator_forcerange', 'actuator_gear', 'actuator_trnid',
                 'actuator_gaintype', 'actuator_gainprm', 'actuator_biastype',
                 'actuator_biasprm', 'actuator_dyntype', 'actuator_dynprm'):
        if hasattr(model, name):
            controls[name] = np.asarray(getattr(model, name)).tolist()
    if 'actuator_ctrllimited' not in controls or 'actuator_ctrlrange' not in controls:
        raise ValueError('Loaded model must expose actuator control limits')
    record = dict(identity_scope='loaded actuator/geometry/name metadata, not complete serialized MJB',
                  dimensions={name: int(getattr(model, name)) for name in ('nq', 'nv', 'nu', 'nbody', 'ngeom', 'njnt')
                              if hasattr(model, name)},
                  controls=controls, disableflags=int(model.opt.disableflags),
                  timestep=float(model.opt.timestep))
    for name in ('geom_type', 'geom_bodyid', 'geom_contype', 'geom_conaffinity'):
        if hasattr(model, name):
            record[name + '_sha256'] = _hash(np.asarray(getattr(model, name)))
    if hasattr(model, 'names'):
        names = model.names if isinstance(model.names, bytes) else bytes(model.names)
        record['compiled_names_sha256'] = hashlib.sha256(names).hexdigest()
    clamp_bit = None
    try:
        import mujoco
        clamp_bit = int(mujoco.mjtDisableBit.mjDSBL_CLAMPCTRL)
        record['mujoco_version'] = mujoco.__version__
    except (ImportError, AttributeError):
        pass
    record.update(clampctrl_disable_bit=clamp_bit,
                  control_clamping_disabled=None if clamp_bit is None else bool(record['disableflags'] & clamp_bit),
                  clamp_flag_resolution='unresolved; inspect saved disableflags' if clamp_bit is None else 'loaded mujoco enum')
    record['control_metadata_sha256'] = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':'),
                                                                 allow_nan=False).encode()).hexdigest()
    return record


def _state(runtime):
    native = _native_env(runtime)
    data = native.data
    contacts = []
    for index in range(int(data.ncon)):
        contact = data.contact[index]
        first = int(contact.geom1) if hasattr(contact, 'geom1') else int(contact.geom[0])
        second = int(contact.geom2) if hasattr(contact, 'geom2') else int(contact.geom[1])
        contacts.append((first, second, float(contact.dist)))
    result = {name: np.asarray(getattr(data, name)).copy()
              for name in ('qpos', 'qvel', 'actuator_force', 'qfrc_actuator', 'ctrl')}
    # The existing runtime snapshot includes data.ctrl. Keep that complete
    # snapshot for audit, but compare dynamics without the explicitly exempt
    # raw control buffer. Requiring the real state fields avoids a fallback
    # that might silently drop solver/activation/mocap state from the check.
    without_ctrl = np.concatenate([np.asarray(getattr(data, name)).reshape(-1)
                                   for name in PHYSICS_FIELDS_WITHOUT_CTRL] + [np.asarray([data.time])])
    result.update(physics_state=np.asarray(runtime.physics_state()).copy(),
                  physics_state_without_ctrl=without_ctrl.copy(),
                  simulation_time=np.asarray(float(data.time)), contacts=contacts)
    if any(not np.isfinite(value).all() for key, value in result.items() if key != 'contacts'):
        raise ValueError('Nonfinite physical probe state')
    if any(not np.isfinite(contact[2]) for contact in contacts):
        raise ValueError('Nonfinite contact distance')
    return result


def _stack_states(states):
    result = {name: np.stack([row[name] for row in states])
              for name in ('physics_state', 'physics_state_without_ctrl', 'qpos', 'qvel',
                           'actuator_force', 'qfrc_actuator', 'ctrl', 'simulation_time')}
    counts = np.asarray([len(row['contacts']) for row in states], dtype=np.int64)
    width = int(counts.max()) if len(counts) else 0
    geometry = np.full((len(states), width, 2), -1, dtype=np.int64)
    distances = np.zeros((len(states), width), dtype=np.float64)
    for index, row in enumerate(states):
        for contact_index, (first, second, distance) in enumerate(row['contacts']):
            geometry[index, contact_index] = (first, second)
            distances[index, contact_index] = distance
    result.update(contact_count=counts, contact_geom=geometry, contact_dist=distances)
    return result


def _run(engine, case, source, cut, restore, reserve, stage, label, gripper, steps):
    attempt = reserve(stage, 'raw_clipped_physical_probe', f"{case['case_id']}:{cut}:{label}")
    started = time.perf_counter()
    trace, _, _ = restore(case, source, cut)
    if trace.step != cut:
        raise ValueError('Probe restore returned a different control step')
    runtime = engine.runtime
    model = loaded_model_metadata(_native_env(runtime))
    states = [_state(runtime)]
    restore_seconds = time.perf_counter() - started
    actions, rewards, successes, dones = [], [], [], []
    command = np.asarray([0., 0., 0., gripper], dtype=np.float32)
    for _ in range(steps):
        if trace.terminal or trace.step >= 300:
            break
        trace.execute(runtime, command)
        actions.append(command.copy())
        rewards.append(trace.rewards[-1])
        successes.append(trace.successes[-1])
        dones.append(trace.dones[-1])
        states.append(_state(runtime))
    engine.verify()
    arrays = _stack_states(states)
    arrays.update(commands=np.asarray(actions, dtype=np.float32).reshape(-1, 4),
                  rewards=np.asarray(rewards, dtype=np.float64),
                  success_flags=np.asarray(successes, dtype=np.bool_),
                  done_flags=np.asarray(dones, dtype=np.bool_))
    info = dict(label=label, gripper_command=gripper, attempt=attempt, model=model,
                requested_steps=steps, actual_steps=len(actions), cut_step=cut, terminal_step=trace.step,
                success=bool(any(successes)), terminal=bool(trace.terminal),
                initial_contact_count=int(arrays['contact_count'][0]),
                contact_counts=arrays['contact_count'].tolist(),
                contact_seen=bool(arrays['contact_count'].any()),
                maximum_absolute_actuator_force=float(np.abs(arrays['actuator_force']).max()),
                maximum_absolute_generalized_actuator_force=float(np.abs(arrays['qfrc_actuator']).max()),
                restore_seconds=restore_seconds, wall_seconds=time.perf_counter()-started,
                restoration_included_in_attempt=True, no_contact_based_state_selection=True)
    return info, arrays


def _numeric_comparison(first, second, atol):
    equal_shape = first.shape == second.shape
    return dict(equal_shape=equal_shape,
                maximum_absolute_error=float(np.abs(first-second).max()) if equal_shape and first.size else 0. if equal_shape else None,
                equal=equal_shape and bool(np.allclose(first, second, atol=atol, rtol=0)),
                atol=atol, rtol=0.)


def _compare(raw, clipped):
    comparisons = {name: _numeric_comparison(raw[name], clipped[name], PHYSICS_ATOL)
                   for name in ('physics_state_without_ctrl', 'qpos', 'qvel', 'actuator_force',
                                'qfrc_actuator', 'simulation_time')}
    checks = {name: row['equal'] for name, row in comparisons.items()}
    for name in ('contact_count', 'contact_geom', 'success_flags', 'done_flags'):
        checks[name + '_exact'] = np.array_equal(raw[name], clipped[name])
    contact_distance = _numeric_comparison(raw['contact_dist'], clipped['contact_dist'], PHYSICS_ATOL)
    checks['contact_dist'] = contact_distance['equal']
    comparisons['contact_dist'] = contact_distance
    reward = _numeric_comparison(raw['rewards'], clipped['rewards'], REWARD_ATOL)
    # ctrl deliberately need not equal: raw commands may be retained there even
    # when loaded MuJoCo actuator clamping makes the forces/state equivalent.
    control = _numeric_comparison(raw['ctrl'], clipped['ctrl'], PHYSICS_ATOL)
    return dict(physical_and_flag_checks=checks, physical_comparisons=comparisons,
                physical_and_binary_equivalence=all(checks.values()), reward_comparison=reward,
                ctrl_comparison_for_information_only=control,
                reward_difference_blocks_physical_equivalence=False)


def run_raw_clipped_probe(engine, case, source, cut, collector_restore, ledger,
                         *, stage='p0', steps=3):
    """Four counted fixed-cut branches: +1.5/+1.0, then -1.5/-1.0 gripper.

    XYZ is exactly zero and each command repeats for at most three controls.
    ``collector_restore`` is the existing (case,source,cut)->(trace,snapshot,anchor)
    callable; ledger may alternatively be a reserve(stage,kind,identity) callable.
    Return metadata plus flat NPZ-ready arrays. Physical/contact/binary mismatch
    raises RawClippedProbeError with payload; reward-only differences are recorded
    without declaring different dynamics or preventing the diagnostic from passing.
    Call once on the preregistered state of each task for exactly 20 attempts.
    """
    if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 3:
        raise ValueError('Raw/clipped probe permits one to three fixed controls')
    if isinstance(cut, bool) or not isinstance(cut, int) or not 0 <= cut < 300:
        raise ValueError('Probe cut must be an integer before the original budget')
    reserve = ledger.reserve if hasattr(ledger, 'reserve') else ledger
    if not callable(reserve) or not callable(collector_restore):
        raise TypeError('Probe requires counted reserve and caller-owned restore callbacks')
    runs, arrays_by_run = {}, {}
    for label, gripper in [('positive_raw', 1.5), ('positive_clipped', 1.),
                           ('negative_raw', -1.5), ('negative_clipped', -1.)]:
        runs[label], arrays_by_run[label] = _run(engine, case, source, cut, collector_restore,
                                               reserve, stage, label, gripper, steps)
    pairs = {sign: _compare(arrays_by_run[sign+'_raw'], arrays_by_run[sign+'_clipped'])
             for sign in ('positive', 'negative')}
    model_hashes = [run['model']['control_metadata_sha256'] for run in runs.values()]
    failed = [f'{sign}.{name}' for sign, pair in pairs.items()
              for name, passed in pair['physical_and_flag_checks'].items() if not passed]
    if len(set(model_hashes)) != 1:
        failed.append('loaded_model_metadata_changed_between_restores')
    failed.extend(f'{label}.no_executed_controls' for label, run in runs.items() if run['actual_steps'] == 0)
    initial_contact_seen = any(run['initial_contact_count'] > 0 for run in runs.values())
    contact_seen = any(run['contact_seen'] for run in runs.values())
    metadata = dict(status='failed' if failed else 'passed', diagnostic='fixed_cut_raw_vs_clipped_gripper_physical_effect',
                    task=case['task'], case_id=case['case_id'], env_seed=case['env_seed'],
                    source=str(source), cut_step=cut, counted_runs=4, maximum_controls_per_run=steps,
                    planned_commands=dict(positive_raw=[0.,0.,0.,1.5], positive_clipped=[0.,0.,0.,1.],
                                          negative_raw=[0.,0.,0.,-1.5], negative_clipped=[0.,0.,0.,-1.]),
                    runs=runs, pairs=pairs, failed_checks=failed,
                    initial_contact_seen=initial_contact_seen, contact_seen=contact_seen,
                    contact_coverage='only this preregistered initial/short-prefix state; contact identities saved'
                                     if contact_seen else 'no contacts observed; contact-state equivalence is not established',
                    contact_based_state_search=False, frozen_tolerance=PHYSICS_ATOL,
                    reward_tolerance=REWARD_ATOL, reward_reported_separately=True,
                    raw_ctrl_equality_required=False, effectiveness_evidence=False,
                    physics_comparison_fields=list(PHYSICS_FIELDS_WITHOUT_CTRL) + ['time'],
                    complete_runtime_physics_state_saved_but_ctrl_excluded_from_comparison=True,
                    done_flags_semantics='Trace terminal flag: environment done OR binary success',
                    equivalence_scope='these two saturation signs, prescribed state and at most three controls only',
                    storage_owned_by_caller=True)
    anchor = Path(source)/f'cut{cut:03d}'/'anchor.json'
    if anchor.is_file():
        metadata['source_anchor_sha256'] = hashlib.sha256(anchor.read_bytes()).hexdigest()
    arrays = {f'{label}_{name}': value for label, data in arrays_by_run.items() for name, value in data.items()}
    if failed:
        raise RawClippedProbeError(metadata, arrays)
    return metadata, arrays
