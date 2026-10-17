"""Targeted R2 checks. All simulated callbacks below are plain Python fakes."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

from core.accounting import RESOURCE_KEYS
from core.initialization import InitializationAudit, EXPECTED_CAPS, CONTROL_MINIMUM_LIMITS, summarize_initialization
from core.release import authorize, check_task_board, verify_device, check_current_authorization
from core.resume import sha
from core.validation import ContractError
from core.wave_timing import timing_summary, observe_restoration


def release_fixture():
    caps = dict.fromkeys(RESOURCE_KEYS, 0)
    caps.update(simulator_attempts=1, env_steps=1, vla_sampling_calls=5, flow_forward_calls=50)
    proposal = {'task_id': 'A10_PREFLIGHT_NATIVE_V1', 'task_revision': 1, '_sha256': 'a' * 64,
        'max_retries': 0, 'resource_caps': caps, 'timeout_seconds': 1800, 'kill_grace_seconds': 30,
        'timeout_scope': 'diagnostic_process', 'initialization_caps': deepcopy(EXPECTED_CAPS),
        'control_minimum_limits': deepcopy(CONTROL_MINIMUM_LIMITS), 'external_source_manifest_sha256': 'b' * 64}
    control = {'campaign_id': 'corrector-sim-20260919', 'stop_requested': False,
        'formal_gpu_runs_enabled': True, 'mode': 'preflight', 'active_compute_release_id': 'SYNTHETIC',
        'allowed_task_ids': [proposal['task_id']], 'current_compute_limits': deepcopy(CONTROL_MINIMUM_LIMITS)}
    release = {'campaign_id': control['campaign_id'], 'task_id': proposal['task_id'], 'task_revision': 1,
        'owner_host': 'synthetic-A', 'node_role': 'A', 'release_id': 'SYNTHETIC', 'status': 'released',
        'proposal_sha256': proposal['_sha256'], 'resource_caps': deepcopy(caps), 'max_retries': 0,
        'wave_id': 'synth-wave', 'shard_id': 'synth-shard', 'run_id': 'synth-run', 'gpu_uuid': 'GPU-synthetic',
        'gpu_index': 0, 'driver': 'synthetic-driver', 'runtime': 'synthetic-runtime', 'gpu_model': 'synthetic-GPU',
        'timeout_seconds': 1800, 'kill_grace_seconds': 30, 'wave_participants': ['A'],
        'timeout_scope': proposal['timeout_scope'], 'initialization_caps': deepcopy(EXPECTED_CAPS),
        'external_source_manifest_sha256': proposal['external_source_manifest_sha256']}
    return control, release, proposal


def test_complete_release_declares_all_initialization_budgets():
    control, release, proposal = release_fixture()
    assert authorize(control, release, proposal, hostname='synthetic-A') == proposal['resource_caps']


@pytest.mark.parametrize('key', list(CONTROL_MINIMUM_LIMITS))
def test_missing_global_budget_rejected(key):
    control, release, proposal = release_fixture()
    control['current_compute_limits'].pop(key)
    with pytest.raises(ContractError):
        authorize(control, release, proposal, hostname='synthetic-A')


@pytest.mark.parametrize('field,bad', [
    ('initialization_caps', {'environment_instances': 1, 'environment_reset_calls': 1}),
    ('status', 'DRAFT_NOT_AUTHORIZED'), ('max_retries', 1), ('wave_participants', ['A', 'B']),
    ('kill_grace_seconds', 0), ('timeout_scope', 'entire_operation_1830s'),
    ('external_source_manifest_sha256', 'drift'), ('run_id', '../outside'), ('gpu_index', None)])
def test_release_correction_and_identity_denials(field, bad):
    control, release, proposal = release_fixture()
    release[field] = bad
    with pytest.raises(ContractError):
        authorize(control, release, proposal, hostname='synthetic-A')


def test_boolean_initialization_budget_rejected():
    control, release, proposal = release_fixture()
    release['initialization_caps']['model_initializations'] = True
    with pytest.raises(ContractError):
        authorize(control, release, proposal, hostname='synthetic-A')


def test_nonreleased_control_cannot_start_diagnostic():
    control, release, proposal = release_fixture()
    for change in ({'stop_requested': True}, {'formal_gpu_runs_enabled': False},
                   {'active_compute_release_id': 'another'}, {'mode': 'prepare'}):
        with pytest.raises(ContractError):
            authorize({**control, **change}, release, proposal, hostname='synthetic-A')


def test_task_board_and_midrun_release_binding(tmp_path):
    control, release, proposal = release_fixture()
    release['owner_host'] = __import__('platform').node()
    path = tmp_path / 'release.json'
    path.write_text(json.dumps(release))
    release['_sha256'] = sha(path)
    row = {'id': proposal['task_id'], 'owner': 'A', 'revision': 1, 'status': 'ready', 'release': 'release.json'}
    (tmp_path / 'CONTROL.json').write_text(json.dumps(control))
    (tmp_path / 'TASK_BOARD.json').write_text(json.dumps({'tasks': [row]}))
    check_current_authorization(tmp_path, path, release, proposal)
    path.write_text(json.dumps({**release, 'status': 'revoked'}))
    with pytest.raises(ContractError):
        check_current_authorization(tmp_path, path, release, proposal)
    row['status'] = 'complete'
    (tmp_path / 'TASK_BOARD.json').write_text(json.dumps({'tasks': [row]}))
    with pytest.raises(ContractError):
        check_task_board(tmp_path, release, proposal, path)


def fake_targets():
    class Mujoco:
        def reset(self):
            self.reset_model()
        def do_simulation(self, ctrl, n_frames):
            return None
    class Base(Mujoco):
        def reset(self):
            self.reset_model()
            super().reset()
    class Native(Base):
        def __init__(self):
            pass
        def reset_model(self):
            for _ in range(50):
                self.do_simulation([-1, 1], 5)
    module = SimpleNamespace()
    def make_tasks():
        env = Native()
        for _ in range(50):
            env.reset()
    module._make_tasks = make_tasks
    class Wrapper:
        def __init__(self):
            self.env = self._make_envs_task()
        def _make_envs_task(self):
            module._make_tasks()
            env = Native()
            env.reset()
            return env
    return module, Native, Base, Mujoco, Wrapper


def test_synthetic_standard_path_counts_origins_and_completed_work(tmp_path):
    audit = InitializationAudit(tmp_path / 'synthetic.jsonl', EXPECTED_CAPS)
    module, Native, Base, Mujoco, Wrapper = fake_targets()
    original_reset = Base.reset
    audit.install(module, Native, Base, Mujoco, Wrapper)
    try:
        audit.invoke('synthetic-model-constructor', {'model_initializations': 1}, lambda: None)
        with audit.scope('diagnostic_reset'):
            wrapper = Wrapper()
            wrapper.env.reset()
        with audit.scope('policy_control'):
            wrapper.env.do_simulation([0, 0], 13)
        audit.assert_complete()
        summary = audit.summary()
        assert summary['entered_budget_usage'] == summary['returned_operation_units'] == EXPECTED_CAPS
        source = summary['entered_usage_by_source']
        assert source['taskset:SawyerXYZEnv.reset']['taskset_reset_calls'] == 50
        assert source['wrapper_initialization:SawyerXYZEnv.reset']['wrapper_initialization_reset_calls'] == 1
        assert source['diagnostic_reset:SawyerXYZEnv.reset']['diagnostic_reset_calls'] == 1
        assert summary['entered_budget_usage']['initialization_physics_substeps'] == 26000
    finally:
        audit.uninstall()
    assert Base.reset is original_reset


def test_budget_failure_prevents_operation_and_keeps_entered_work(tmp_path):
    audit = InitializationAudit(tmp_path / 'synthetic.jsonl', EXPECTED_CAPS)
    effects = []
    audit.invoke('model', {'model_initializations': 1}, lambda: effects.append('first'))
    with pytest.raises(ContractError):
        audit.invoke('model', {'model_initializations': 1}, lambda: effects.append('forbidden-second'))
    assert effects == ['first']
    def failed():
        raise RuntimeError('synthetic partial initialization failure')
    with pytest.raises(RuntimeError):
        audit.invoke('native-constructor', {'environment_instances': 1}, failed)
    summary = audit.summary()
    assert summary['entered_budget_usage']['environment_instances'] == 1
    assert summary['returned_operation_units']['environment_instances'] == 0
    assert summary['failed_events'] == 1
    rows = [json.loads(x) for x in audit.path.read_text().splitlines()]
    missing = summarize_initialization(rows[:-1], EXPECTED_CAPS)
    assert len(missing['incomplete_event_ids']) == 1
    assert missing['entered_budget_usage']['environment_instances'] == 1


def test_source_ast_proves_two_model_resets_and_finite_native_path():
    pkg = Path('/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/lib/python3.12/site-packages')
    mw = ast.parse((pkg / 'metaworld/__init__.py').read_text())
    goals = [n.value.value for n in mw.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == '_N_GOALS' for t in n.targets)]
    assert goals == [50]
    native = ast.parse((pkg / 'metaworld/sawyer_xyz_env.py').read_text())
    xyz = next(n for n in native.body if isinstance(n, ast.ClassDef) and n.name == 'SawyerXYZEnv')
    reset = next(n for n in xyz.body if isinstance(n, ast.FunctionDef) and n.name == 'reset')
    calls = [n.func.attr for n in ast.walk(reset) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
    assert calls.count('reset_model') == 1 and calls.count('reset') == 1
    gym = ast.parse((pkg / 'gymnasium/envs/mujoco/mujoco_env.py').read_text())
    gym_reset = next(n for n in ast.walk(gym) if isinstance(n, ast.FunctionDef) and n.name == 'reset')
    assert sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'reset_model' for n in ast.walk(gym_reset)) == 1
    hand = next(n for n in xyz.body if isinstance(n, ast.FunctionDef) and n.name == '_reset_hand')
    assert hand.args.defaults[0].value == 50
    shelf = ast.parse((pkg / 'metaworld/envs/sawyer_shelf_place_v3.py').read_text())
    shelf_reset = next(n for n in ast.walk(shelf) if isinstance(n, ast.FunctionDef) and n.name == 'reset_model')
    assert sum(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == '_reset_hand' for n in ast.walk(shelf_reset)) == 1


def test_timing_splits_do_not_claim_end_to_end_timeout():
    names = ['launcher_started', 'lifecycle_requested', 'reserved_command_started', 'timed_process_started',
             'timed_process_exited', 'lifecycle_returned', 'restoration_observed']
    values = [0, 20, 26, 27, 100, 101, 111]
    result = timing_summary([{'phase': name, 'monotonic_seconds': value} for name, value in zip(names, values)])
    assert result['preparation_seconds'] == 20
    assert result['reservation_and_holder_release_seconds'] == 6
    assert result['timed_diagnostic_process_seconds'] == 73
    assert result['restoration_observation_seconds'] == 10
    assert result['end_to_end_observed_seconds'] == 111
    assert result['end_to_end_strict_upper_bound_seconds'] is None
    assert timing_summary([])['timed_diagnostic_process_seconds'] is None


def test_restoration_observer_is_read_only_and_preserves_external_work():
    result = observe_restoration(10, seconds=0, clock=lambda: 0,
        read_status=lambda: {'updated': 11, 'gpus': {str(i): {'state': 'external', 'pids': [123]} for i in range(8)}})
    assert result['status'] == 'occupancy_resolved'
    stale = observe_restoration(10, seconds=0, clock=lambda: 0, read_status=lambda: {'updated': 9, 'gpus': {}})
    assert stale['restoration_complete'] is None


def test_timeout_command_failure_is_recorded_without_retry(tmp_path, monkeypatch):
    import run_reserved_diagnostic as runner
    proposal = tmp_path / 'proposal.json'
    proposal.write_text(json.dumps({'timeout_seconds': 1800, 'python': '/synthetic/python'}))
    monkeypatch.setattr(runner, 'held_reservation_fds', lambda: (123,))
    commands = []
    def fake_run(command, **kwargs):
        commands.append(command)
        assert kwargs['pass_fds'] == (123,)
        return 124
    monkeypatch.setattr(runner, 'run_forwarded', fake_run)
    monkeypatch.setattr(sys, 'argv', ['synthetic', '--campaign', str(tmp_path), '--release', 'synthetic.json',
        '--proposal', str(proposal), '--launch-directory', str(tmp_path)])
    assert runner.main() == 124
    assert len(commands) == 1 and '--kill-after=30s' in commands[0] and '1800s' in commands[0]
    rows = [json.loads(s) for s in (tmp_path / 'wave_timing.jsonl').read_text().splitlines()]
    assert rows[-1]['phase'] == 'timed_process_exited' and rows[-1]['returncode'] == 124


def test_CPU_validator_imports_no_simulator_or_model():
    import authorize_cpu
    assert callable(authorize_cpu.main)
    for name in ('torch', 'metaworld', 'mujoco', 'lerobot'):
        assert name not in sys.modules
