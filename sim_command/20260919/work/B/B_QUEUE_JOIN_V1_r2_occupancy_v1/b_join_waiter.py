#!/usr/bin/python
"""B-owned, stdlib-only bootstrap. This is not the collection supervisor.

Only the immutable A package at the authorized READY path can supply an
installer. No shell, recursive script discovery, or experiment retry is used.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

C = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
Q = C / 'persistent_queue'
NODE = Q / 'nodes/B'
HOST = 'trial-303225685-trialrun-303225685-worker-0'
AUTH_SHA = 'd73448042b71ecb06940e8d891caf0ef8bef005018f155ee2743903981992928'
HERE = Path(__file__).resolve().parent
PYTHON = '/usr/bin/python'
CHECKS = ['detached_two_jobs', 'idempotent_start', 'unknown_execution_blocks',
          'duplicate_claim', 'cross_node_storage', 'no_nested_reservation',
          'continuous_queue_reservation', 'idle_restores_holders',
          'same_gpu_holder_exit_before_compute', 'no_holder_on_active_formal_gpu',
          'temporary_holders_reaped_before_guard',
          'protocol_gate', 'capacity_gate', 'resource_admission_memory', 'worker_refill',
          'node_failure_isolation', 'current_authority_gate']


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def atomic(path, obj, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp.' + uuid.uuid4().hex)
    with tmp.open('x') as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    try:
        if exclusive:
            os.link(tmp, path)
        else:
            os.replace(tmp, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        tmp.unlink(missing_ok=True)


def identity(pid=None):
    pid = pid or os.getpid()
    stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return dict(node='B', host=os.uname().nodename,
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                pid=pid, start_ticks=int(stat[19]), session_id=os.getsid(pid))


def alive(record):
    try:
        if Path(f"/proc/{record['pid']}/stat").read_text().rsplit(')', 1)[1].split()[0] == 'Z':
            return False
        actual = identity(int(record['pid']))
        return all(actual[k] == record[k] for k in ('host', 'boot_id', 'pid', 'start_ticks'))
    except (OSError, KeyError, ValueError, ProcessLookupError):
        return False


def authorization():
    raw = (Q / 'AUTHORIZATION_V2.json').read_bytes()
    if digest(raw) != AUTH_SHA or os.uname().nodename != HOST:
        raise ValueError('authorization_or_host_mismatch')
    auth = json.loads(raw)
    for ref in [auth['contract'], auth['task_briefs']['B'],
                *auth['plan'].values(), *auth['scientific_baseline'].values(), *auth['amendments']]:
        if digest((C / ref['path']).read_bytes()) != ref['sha256']:
            raise ValueError('frozen_input_changed: ' + ref['path'])
    ctrl = read(Q / 'CONTROL.json')
    if ctrl['authorization']['sha256'] != AUTH_SHA:
        raise ValueError('queue_control_authorization_mismatch')
    if ctrl['global_stop'] or not ctrl['nodes']['B']['enabled']:
        raise ValueError('queue_stop_or_node_disabled')
    if auth['collection_source_limits_by_node']['B'] != 0 or auth['training_or_formal_evaluation_authorized']:
        raise ValueError('B_role_authority_mismatch')
    overrides = {}
    for ref in ctrl.get('operational_overrides', []):
        raw_override = (C / ref['path']).read_bytes()
        if digest(raw_override) != ref['sha256']:
            raise ValueError('operational_override_SHA_mismatch')
        item = json.loads(raw_override)
        if (item.get('base_queue_authorization', {}).get('sha256') != AUTH_SHA
                or 'B' not in item.get('nodes', [])
                or item.get('extra_training_or_evaluation_authorized') is not False):
            raise ValueError('operational_override_role_or_science_mismatch')
        contract = item['contract']
        if digest((C / contract['path']).read_bytes()) != contract['sha256']:
            raise ValueError('operational_override_contract_SHA_mismatch')
        if item.get('id') != 'OCCUPANCY_OVERRIDE_V1':
            raise ValueError('unknown_operational_override_requires_adapter')
        overrides[ref['path']] = ref['sha256']
    auth['_operational_overrides_sha256'] = overrides
    return auth


def checked_package(ready_path, auth):
    """Validate the explicit B join descriptor in A's immutable READY.

    A may put this descriptor directly under b_join or in a SHA-covered
    b_join_manifest reference. Formats are advertised in B/JOIN_GATE_V2.json.
    A's internal service/collector schema is otherwise opaque to this waiter.
    """
    package = ready_path.parent.resolve()
    raw = ready_path.read_bytes()
    ready = json.loads(raw)
    if ready.get('publisher') != 'A' or ready.get('status') != 'READY':
        raise ValueError('A_READY_identity_missing')
    if ready.get('immutable_after_publication') is not True:
        raise ValueError('immutable_package_declaration_missing')
    files = ready.get('files', [])
    if not files or len(files) > 10000:
        raise ValueError('missing_or_oversized_file_manifest')
    verified = {}
    total = 0
    for ref in files:
        p = Path(ref['path'])
        if not p.is_absolute():
            p = package / p
        p = p.resolve()
        if not p.is_relative_to(package) or p == ready_path.resolve() or '.partial_' in p.name:
            raise ValueError('file_outside_immutable_package')
        total += p.stat().st_size
        if total > 128 * 1024 * 1024:
            raise ValueError('package_code_metadata_byte_budget_exceeded')
        data = p.read_bytes()
        if digest(data) != ref['sha256']:
            raise ValueError('package_file_sha_mismatch: ' + str(p))
        verified[p] = ref['sha256']
    descriptor = ready.get('b_join')
    if descriptor is None:
        ref = ready.get('b_join_manifest', {})
        p = Path(ref.get('path', 'MISSING'))
        if not p.is_absolute():
            p = package / p
        p = p.resolve()
        if p not in verified or ref.get('sha256') != verified[p]:
            raise ValueError('B_join_descriptor_missing_or_unbound')
        descriptor = read(p)
    if descriptor.get('authorization_sha256') != AUTH_SHA:
        raise ValueError('package_authorization_mismatch')
    if descriptor.get('contract_sha256') != auth['contract']['sha256']:
        raise ValueError('package_protocol_mismatch')
    for k, v in auth['plan'].items():
        if descriptor.get('plan_sha256', {}).get(k) != v['sha256']:
            raise ValueError('package_plan_mismatch: ' + k)
    for k, v in auth['scientific_baseline'].items():
        if descriptor.get('scientific_baseline_sha256', {}).get(k) != v['sha256']:
            raise ValueError('package_science_mismatch: ' + k)
    if descriptor.get('operational_overrides_sha256', {}) != auth.get('_operational_overrides_sha256', {}):
        raise ValueError('package_operational_override_mismatch')
    if auth.get('_operational_overrides_sha256') and descriptor.get('same_gpu_holder_exit_before_compute') is not True:
        raise ValueError('package_holder_handoff_not_declared')
    testref = descriptor.get('tests', {})
    testpath = Path(testref.get('path', 'MISSING'))
    if not testpath.is_absolute():
        testpath = package / testpath
    testpath = testpath.resolve()
    if testpath not in verified or testref.get('sha256') != verified[testpath]:
        raise ValueError('test_evidence_not_sha_bound')
    tests = read(testpath)
    if tests.get('synthetic_only') is not True or tests.get('status') != 'PASS':
        raise ValueError('control_plane_tests_not_passed')
    mapping = descriptor.get('test_check_keys', {k: k for k in CHECKS})
    for k in CHECKS:
        result = tests.get('checks', {}).get(mapping.get(k, k))
        if isinstance(result, dict):
            result = result.get('passed', result.get('status'))
        if result is not True and result != 'PASS':
            raise ValueError('missing_control_plane_evidence: ' + k)
    argv = descriptor.get('argv')
    if not isinstance(argv, list) or len(argv) < 2 or not all(isinstance(x, str) for x in argv):
        raise ValueError('explicit_B_install_argv_missing')
    # One Python entry, without -c, shell expansion, or a discovered script.
    if argv[0] != PYTHON:
        raise ValueError('installer_must_use_system_stdlib_python')
    entry = Path(argv[1])
    if not entry.is_absolute():
        entry = package / entry
    entry = entry.resolve()
    if entry not in verified or entry.suffix != '.py':
        raise ValueError('installer_not_in_verified_package')
    if descriptor.get('node') != 'B' or descriptor.get('host') != HOST:
        raise ValueError('installer_node_binding_missing')
    if descriptor.get('performs_local_machine_gates_before_admission') is not True:
        raise ValueError('local_machine_gates_not_declared')
    if descriptor.get('non_nested_reservation') is not True:
        raise ValueError('nested_reservation_not_excluded')
    if descriptor.get('collection_source_limit') != 0 or descriptor.get('training_evaluation_requires_stage_authorization') is not True:
        raise ValueError('B_V2_role_or_stage_gate_missing')
    return dict(ready_sha256=digest(raw), manifest=ready, descriptor=descriptor,
                argv=[PYTHON, str(entry), *argv[2:]], files=verified)


def service_ready(package_sha):
    path = NODE / 'DAEMON_READY.json'
    if not path.exists():
        return False
    data = read(path)
    proc = data.get('process_identity', data)
    return (data.get('node') == 'B' and data.get('package_sha256') == package_sha
            and data.get('authorization_sha256') == AUTH_SHA and alive(proc))


def checkpoint(state, mode, **extra):
    record = dict(node='B', host=HOST, updated_at_utc=utc(), mode=mode,
                  process_identity=identity(), authorization_sha256=AUTH_SHA,
                  join_waiter_code_sha256=digest(Path(__file__).read_bytes()),
                  collection_daemon_ready=False, current_job=None,
                  holder_mode='unchanged; idle waiter is not compute',
                  occupancy_override_support='V1 explicit same-GPU holder exit before model entry; auxiliary accounting separate', **extra)
    atomic(state / 'JOIN_WAITER_STATUS.json', record)
    # Deliberately separate from the real queue daemon's heartbeat/READY.
    atomic(state / 'JOIN_WAITER_HEARTBEAT.json', record)


def lock_path(state, name):
    # Shared object storage need not implement flock. The service is host
    # scoped; use the host's local kernel lock and persist identity separately.
    root = Path('/tmp/corrector_B_join_locks') / digest(str(state).encode())
    root.mkdir(parents=True, exist_ok=True)
    return root / name


def run_once(state, key, argv, cwd):
    """At-most-once entry. An uncertain start is never silently retried."""
    claim = state / (key + '.ENTERED.json')
    result = state / (key + '.RESULT.json')
    if result.exists():
        return read(result)
    if claim.exists():
        return dict(status='blocked', reason='unknown_execution; reconcile before restart',
                    claim=str(claim), original=read(claim))
    atomic(claim, dict(command=argv, cwd=str(cwd), owner=identity(),
                       entered_at_utc=utc(), command_id=uuid.uuid4().hex), exclusive=True)
    with (state / (key + '.log')).open('ab', buffering=0) as log:
        proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True, close_fds=True)
        atomic(state / (key + '.PROCESS.json'), identity(proc.pid), exclusive=True)
        while proc.poll() is None:
            if state == NODE:
                checkpoint(state, 'installing_verified_A_package', installer_identity=identity(proc.pid))
            time.sleep(.2 if state != NODE else 5)
        code = proc.returncode
    record = dict(status='complete' if code == 0 else 'failed', exit_code=code,
                  finished_at_utc=utc(), command_id=read(claim)['command_id'])
    atomic(result, record, exclusive=True)
    return record


def daemon(state, synthetic=False):
    state.mkdir(parents=True, exist_ok=True)
    with lock_path(state, 'singleton.lock').open('a') as singleton:
        try:
            fcntl.flock(singleton, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        atomic(state / 'PROCESS.json', identity())
        stop = False
        def halt(*_):
            nonlocal stop
            stop = True
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, halt)
        if synthetic:
            for index in (1, 2):
                r = run_once(state, 'fake_' + str(index),
                             [PYTHON, str(Path(__file__).resolve()), 'synthetic-job',
                              '--state', str(state), '--number', str(index)], HERE)
                if r['status'] != 'complete':
                    atomic(state / 'SYNTHETIC_RESULT.json', r)
                    return
            atomic(state / 'SYNTHETIC_RESULT.json', dict(status='PASS', synthetic_only=True,
                                                       process_identity=identity()))
            return
        while not stop and not (state / 'STOP_REQUEST.json').exists():
            try:
                auth = authorization()
                path = Q / 'package/READY.json'
                if not path.exists():
                    checkpoint(state, 'waiting_for_A_package', blocked_reason='fixed READY absent')
                else:
                    package = checked_package(path, auth)
                    atomic(state / 'PACKAGE_VERIFIED.json', dict(
                        verified_at_utc=utc(), ready_sha256=package['ready_sha256'],
                        authorization_sha256=AUTH_SHA, argv=package['argv'],
                        verified_file_count=len(package['files'])))
                    checkpoint(state, 'installing_verified_A_package',
                               package_sha256=package['ready_sha256'])
                    result = run_once(state, 'A_PACKAGE_JOIN', package['argv'], path.parent)
                    good = result['status'] == 'complete' and service_ready(package['ready_sha256'])
                    checkpoint(state, 'joined_daemon_live' if good else 'join_blocked',
                               package_sha256=package['ready_sha256'],
                               observed_daemon_ready=good, install_result=result,
                               blocked_reason=None if good else 'installer failed/uncertain or real DAEMON_READY not verified')
            except Exception as exc:
                checkpoint(state, 'gate_blocked', blocked_reason=f'{type(exc).__name__}: {exc}')
            for _ in range(30):
                if stop or (state / 'STOP_REQUEST.json').exists():
                    break
                time.sleep(1)
        checkpoint(state, 'waiter_stopped', blocked_reason='local stop; no experiment signals sent')


def start(state, synthetic=False):
    state.mkdir(parents=True, exist_ok=True)
    with lock_path(state, 'startup.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        procpath = state / 'PROCESS.json'
        if procpath.exists() and alive(read(procpath)):
            return dict(status='already_running', process_identity=read(procpath))
        if (state / 'STOP_REQUEST.json').exists():
            return dict(status='stopped', reason='use explicit resume to clear only the waiter stop request')
        argv = [PYTHON, str(Path(__file__).resolve()), 'synthetic-daemon' if synthetic else 'daemon',
                '--state', str(state)]
        with (state / 'join_waiter.log').open('ab', buffering=0) as log:
            child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=log,
                                     stderr=subprocess.STDOUT, start_new_session=True,
                                     close_fds=True, cwd=HERE)
        for _ in range(50):
            if procpath.exists():
                owner = read(procpath)
                if owner['pid'] == child.pid and alive(owner):
                    return dict(status='started', process_identity=owner)
            if child.poll() is not None:
                break
            time.sleep(.1)
        return dict(status='start_not_confirmed', pid=child.pid)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['start', 'resume', 'stop', 'status', 'daemon',
                                     'synthetic-start', 'synthetic-daemon', 'synthetic-job'])
    p.add_argument('--state', type=Path, default=NODE)
    p.add_argument('--number', type=int)
    a = p.parse_args()
    a.state = a.state.resolve()
    synthetic = a.command.startswith('synthetic-')
    if synthetic:
        if not a.state.is_relative_to(HERE / 'selftests'):
            raise ValueError('synthetic state must be in isolated selftests directory')
    elif a.state != NODE:
        raise ValueError('production state path is fixed')
    if a.command in ('daemon', 'synthetic-daemon'):
        daemon(a.state, synthetic)
    elif a.command == 'synthetic-job':
        time.sleep(2)
        atomic(a.state / f'fake_{a.number}.OUTPUT.json', dict(
            synthetic_only=True, number=a.number, process_identity=identity(), at_utc=utc()), exclusive=True)
    elif a.command in ('start', 'resume', 'synthetic-start'):
        if not synthetic:
            authorization()
        if a.command == 'resume':
            a.state.joinpath('STOP_REQUEST.json').unlink(missing_ok=True)
        print(json.dumps(start(a.state, synthetic)))
    elif a.command == 'stop':
        atomic(a.state / 'STOP_REQUEST.json', dict(requested_at_utc=utc(), scope='B join-waiter admission only'))
        print('Stop requested; existing installer is drained. Use the public service stop command after joining.')
    else:
        record = read(a.state / 'JOIN_WAITER_STATUS.json') if (a.state / 'JOIN_WAITER_STATUS.json').exists() else {}
        proc = read(a.state / 'PROCESS.json') if (a.state / 'PROCESS.json').exists() else {}
        print(json.dumps(dict(record, waiter_process_alive=alive(proc)), indent=2))


if __name__ == '__main__':
    main()
