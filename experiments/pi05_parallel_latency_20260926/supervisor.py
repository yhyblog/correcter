"""Finite host-local inference timing family; imports no model or CUDA code."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import traceback


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]
CHILDREN = []


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def identity():
    return dict(pid=os.getpid(), pgid=os.getpgrp(), host=socket.gethostname(), time=time.time())


def config():
    cfg = read(ROOT / 'CONFIG.json')
    if socket.gethostname() != cfg['host']:
        raise RuntimeError('This finite run belongs to a different host')
    if Path(cfg['root']).resolve() != ROOT:
        raise RuntimeError('CONFIG root differs from supervisor directory')
    return cfg


def live_group_members(pgid):
    """Include descendants after their original worker has already exited."""
    members = []
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
            if int(fields[2]) == pgid and fields[0] not in ('Z', 'X'):
                members.append(int(path.parent.name))
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, IndexError):
            continue
    return members


def stop_groups(processes):
    # Every group here was created by this supervisor using start_new_session.
    for proc in processes:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        for proc in processes:
            proc.poll()
        if not any(live_group_members(proc.pid) for proc in processes):
            break
        time.sleep(.5)
    for proc in processes:
        try:
            if live_group_members(proc.pid):
                os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for proc in processes:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    deadline = time.monotonic() + 5
    survivors = {}
    while True:
        survivors = {str(proc.pid): live_group_members(proc.pid) for proc in processes}
        survivors = {pgid: pids for pgid, pids in survivors.items() if pids}
        if not survivors or time.monotonic() >= deadline:
            break
        time.sleep(.5)
    return survivors


def launch_worker(path, parent):
    cfg = read(path)
    output = Path(cfg['output'])
    output.mkdir(parents=True, exist_ok=True)
    for name in ('tmp', 'xdg'):
        (output / name).mkdir(exist_ok=True)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=cfg['gpu_uuid'], CUDA_DEVICE_ORDER='PCI_BUS_ID',
               VLA_CPU_THREADS='2', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1',
               MKL_NUM_THREADS='2', NUMEXPR_NUM_THREADS='1', LP_NUM_THREADS='1',
               PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1', VLA_RENDERER='mesa',
               TMPDIR=str(output / 'tmp'), XDG_RUNTIME_DIR=str(output / 'xdg'))
    for key in ('LD_PRELOAD', 'PYTHONPATH', 'MUJOCO_EGL_DEVICE_ID'):
        env.pop(key, None)
    argv = ['bash', parent['runtime_launcher'], parent['runtime_environment_id'],
            parent['python'], '-B', str(ROOT / 'worker.py'), '--config', str(path)]
    with (output / 'worker.log').open('ab') as log:
        proc = subprocess.Popen(argv, cwd=WORKSPACE, env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    CHILDREN.append(proc)
    write(output / 'PROCESS.json', dict(**identity(), worker_pid=proc.pid, worker_pgid=proc.pid,
          gpu_index=cfg['gpu_index'], gpu_uuid=cfg['gpu_uuid'], role=cfg['role'], command=argv))
    return dict(config=cfg, path=path, process=proc, launched=time.monotonic(), ready=False)


def supervise():
    cfg = config()
    started = time.monotonic()
    max_wall = float(cfg.get('max_wall_seconds', 1800))
    loading_limit = float(cfg.get('model_loading_seconds', 900))
    workers, failures = [], []
    result = dict(status='technical_failure', failures=failures)

    def stop(*_):
        raise KeyboardInterrupt('Finite inference timing family stopped')

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stop)

    def heartbeat(stage):
        write(ROOT / 'HEARTBEAT.json', dict(**identity(), stage=stage,
              elapsed_seconds=time.monotonic() - started,
              worker_active=sum(w['process'].poll() is None for w in workers),
              workers_ready=sum(w['ready'] for w in workers), failures=failures))
        if time.monotonic() - started >= max_wall:
            raise TimeoutError(f'Finite {max_wall:g}-second formal budget exhausted')

    def fail(worker, stage, reason, **extra):
        item = dict(config=str(worker['path']), gpu_index=worker['config']['gpu_index'],
                    stage=stage, reason=reason, **extra)
        failures.append(item)
        write(Path(worker['config']['output']) / 'SUPERVISOR_FAILURE.json', dict(**identity(), **item))

    try:
        snapshot = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid',
                                   '--format=csv,noheader'], capture_output=True, text=True,
                                  timeout=30, check=True)
        write(ROOT / 'NVML_BEFORE_MODELS.json', dict(**identity(), stdout=snapshot.stdout,
              stderr=snapshot.stderr, compute_contexts_empty=not snapshot.stdout.strip()))
        if snapshot.stdout.strip():
            raise RuntimeError('Compute contexts remain after occupancy handoff; no workers launched')
        write(ROOT / 'HOLDER_EXIT_CONFIRMED.json', dict(**identity(), compute_contexts=[], scope='all eight GPUs'))
        for path_text in cfg['workers']:
            path = Path(path_text)
            try:
                workers.append(launch_worker(path, cfg))
            except Exception as error:
                failures.append(dict(config=str(path), stage='launch', reason=repr(error)))

        pending = list(workers)
        while pending:
            heartbeat('model_loading')
            expired = []
            for worker in list(pending):
                proc, output = worker['process'], Path(worker['config']['output'])
                if proc.poll() is not None:
                    fail(worker, 'model_loading', 'worker_exited_before_start', exit_code=proc.returncode)
                    pending.remove(worker)
                elif (output / 'WORKER_READY.json').exists():
                    worker['ready'] = True
                    pending.remove(worker)
                elif time.monotonic() - worker['launched'] >= loading_limit:
                    fail(worker, 'model_loading', 'model_readiness_timeout', limit_seconds=loading_limit)
                    expired.append(proc)
                    pending.remove(worker)
            if expired:
                survivors = stop_groups(expired)
                if survivors:
                    raise RuntimeError(f'Timed-out worker group failed to exit: {survivors}')
            if pending:
                time.sleep(10)

        starts = {ROOT / 'START.json'}
        starts.update(Path(w['config']['start_file']) for w in workers)
        start_record = dict(**identity(), ready_workers=sum(w['ready'] and w['process'].poll() is None
                            for w in workers), total_workers=len(cfg['workers']), failures=failures)
        for path in starts:
            write(path, start_record)
        while any(w['process'].poll() is None for w in workers):
            heartbeat('measurement')
            time.sleep(10)
        for worker in workers:
            if not worker['ready']:
                continue
            proc = worker['process']
            path = Path(worker['config']['output']) / 'RESULT.json'
            try:
                worker_result = read(path) if path.exists() else dict(status='missing')
            except Exception as error:
                worker_result = dict(status='unreadable', error=repr(error))
            if proc.returncode != 0 or worker_result.get('status') != 'complete':
                fail(worker, 'measurement', 'worker_not_complete', exit_code=proc.returncode,
                     result=worker_result)
        result = dict(status='partial' if failures else 'complete', failures=failures)
    except BaseException as error:
        result = dict(status='technical_failure', error=repr(error), traceback=traceback.format_exc(),
                      failures=failures)
    finally:
        # Give the owned children their cleanup window before the lifecycle may restore holders.
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        survivors = stop_groups(CHILDREN)
        while survivors:
            # A delayed kernel/OS teardown must not let lifecycle restore holders early.
            result.update(status='technical_failure', delayed_owned_group_cleanup=True)
            write(ROOT / 'HEARTBEAT.json', dict(**identity(), stage='owned_group_cleanup',
                  elapsed_seconds=time.monotonic() - started, surviving_owned_groups=survivors))
            time.sleep(10)
            survivors = stop_groups(CHILDREN)
        write(ROOT / 'FAMILY_EXIT.json', dict(**identity(), all_owned_children_exited=not survivors,
              surviving_owned_groups=survivors, child_exit_codes=[p.returncode for p in CHILDREN]))
        write(ROOT / 'FORMAL_RESULT.json', dict(**identity(), **result,
              elapsed_seconds=time.monotonic() - started))
    return 0 if result['status'] == 'complete' else 3


def publish_terminal(cfg, status):
    event = read(ROOT / 'EVENT_REGISTRATION.json')
    write(ROOT / 'outbox' / 'TERMINAL.json', dict(**event, status=status, time=time.time(),
          transport_is_handler_ack=False))
    if (ROOT / 'outbox' / 'TRANSPORT.json').exists():
        return
    message = ('本线程用户授权的 π0.5 并发推理测速进程已终止。读取 ' + str(ROOT / 'RESULT.json') +
               ' 与 REPORT.md，核对真实结果并向用户报告；写 outbox/HANDLER_ACK.json。' +
               '保留工程失败，不重跑完成单元，不递归注册回调。')
    try:
        transport = subprocess.run(['codex', 'queue', '--thread', cfg['thread'], '--message', message],
                                   capture_output=True, text=True, timeout=30)
        write(ROOT / 'outbox' / 'TRANSPORT.json', dict(exit_code=transport.returncode,
              stdout=transport.stdout[-1500:], stderr=transport.stderr[-1500:],
              accepted_not_handler_ack=transport.returncode == 0, retries=0))
    except Exception as error:
        write(ROOT / 'outbox' / 'TRANSPORT.json', dict(error=repr(error), outbox_retained=True,
              accepted_not_handler_ack=False, retries=0))


def run_outer():
    cfg = config()
    local = Path(cfg['local_dir'])
    local.mkdir(parents=True, exist_ok=True)
    lifecycle_exit = None
    outer_error = None
    with (local / 'queue.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        write(ROOT / 'PROCESS.json', dict(**identity(), thread=cfg['thread']))
        proc = None

        def forward(sig, _frame):
            if proc is not None and proc.poll() is None:
                try:
                    os.killpg(proc.pid, sig)
                except ProcessLookupError:
                    pass

        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, forward)
        try:
            proc = subprocess.Popen([str(WORKSPACE / 'gpu_occupancy_lifecycle.sh'), 'run', '--',
                      '/usr/bin/python', '-B', str(ROOT / 'supervisor.py'), 'supervise'], cwd=WORKSPACE,
                      env=dict(os.environ, CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS='300'),
                      start_new_session=True)
            write(ROOT / 'LIFECYCLE_PROCESS.json', dict(**identity(), lifecycle_pid=proc.pid,
                  lifecycle_pgid=proc.pid))
            lifecycle_exit = proc.wait()
        except Exception as error:
            outer_error = repr(error)
            if proc is not None and proc.poll() is None:
                forward(signal.SIGTERM, None)
                lifecycle_exit = proc.wait()
        # The single formal reservation has now ended; analysis and delivery are CPU-only.
        try:
            formal = read(ROOT / 'FORMAL_RESULT.json')
        except Exception as error:
            formal = dict(status='formal_not_started', error=repr(error))
        try:
            analysis = subprocess.run(['/usr/bin/python', '-B', str(ROOT / 'analyze.py')], cwd=ROOT,
                                      env=dict(os.environ, CUDA_VISIBLE_DEVICES=''),
                                      capture_output=True, text=True, timeout=90)
            analysis_result = dict(exit_code=analysis.returncode, stdout=analysis.stdout[-3000:],
                                   stderr=analysis.stderr[-3000:])
        except Exception as error:
            analysis_result = dict(exit_code=None, error=repr(error))
        write(ROOT / 'ANALYSIS_EXIT.json', analysis_result)
        status = formal.get('status', 'technical_failure')
        if status == 'complete' and (lifecycle_exit != 0 or analysis_result['exit_code'] != 0):
            status = 'technical_failure'
        write(ROOT / 'RESULT.json', dict(**identity(), status=status, formal=formal,
              lifecycle_exit=lifecycle_exit, outer_error=outer_error, analysis=analysis_result,
              thread=cfg['thread']))
        publish_terminal(cfg, status)
    return 0 if status == 'complete' else 3


def outer():
    try:
        return run_outer()
    except BaseException as error:
        # Includes a busy local lock and filesystem/analysis bookkeeping failures.
        write(ROOT / 'OUTER_FAILURE.json', dict(**identity(), error=repr(error),
              traceback=traceback.format_exc()))
        if not (ROOT / 'RESULT.json').exists():
            write(ROOT / 'RESULT.json', dict(**identity(), status='technical_failure', error=repr(error)))
        publish_terminal(read(ROOT / 'CONFIG.json'), 'technical_failure')
        return 3


def start():
    cfg = config()
    paths = [Path(p) for p in cfg['workers']]
    workers = [read(p) for p in paths]
    if len(workers) != 8 or len({w['gpu_uuid'] for w in workers}) != 8:
        raise ValueError('Expected eight workers on eight distinct GPU UUIDs')
    if len({str(Path(w['output']).resolve()) for w in workers}) != 8:
        raise ValueError('Worker output directories must be distinct')
    stale = [ROOT / 'RESULT.json', ROOT / 'FORMAL_RESULT.json', ROOT / 'START.json']
    stale += [Path(w['start_file']) for w in workers]
    stale += [Path(w['output']) / name for w in workers
              for name in ('MODEL_READY.json', 'WORKER_READY.json', 'RESULT.json')]
    if any(path.exists() for path in stale):
        raise RuntimeError('Existing results or readiness files found; no duplicate family launched')
    with (ROOT / 'LAUNCH_CLAIM.json').open('x') as stream:
        json.dump(dict(**identity(), thread=cfg['thread']), stream)
    write(ROOT / 'EVENT_REGISTRATION.json', dict(event='terminal_or_failure', thread=cfg['thread'],
          output=str(ROOT / 'RESULT.json'), acknowledgement=str(ROOT / 'outbox' / 'HANDLER_ACK.json'),
          original_executor_thread=True, recursive_callback=False))
    try:
        with (ROOT / 'supervisor.log').open('ab') as log:
            proc = subprocess.Popen(['/usr/bin/python', '-B', str(ROOT / 'supervisor.py'), 'outer'],
                  cwd=WORKSPACE, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                  start_new_session=True)
    except Exception as error:
        write(ROOT / 'RESULT.json', dict(**identity(), status='launch_failure', error=repr(error)))
        write(ROOT / 'outbox' / 'TERMINAL.json', dict(**read(ROOT / 'EVENT_REGISTRATION.json'),
              status='launch_failure', error=repr(error), transport_is_handler_ack=False))
        raise
    record = dict(pid=proc.pid, pgid=proc.pid, host=socket.gethostname(), thread=cfg['thread'],
                  time=time.time())
    write(ROOT / 'LAUNCH.json', record)
    print(json.dumps(record))
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'outer', 'supervise'])
    raise SystemExit(globals()[parser.parse_args().action]())
