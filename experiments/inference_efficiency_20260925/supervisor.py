"""Host-scoped finite profiling family; no historical experiment entrypoints."""
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
from worker import write

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]
CHILDREN = []


def read(path):
    return json.loads(Path(path).read_text())


def identity():
    return dict(pid=os.getpid(), pgid=os.getpgrp(), host=socket.gethostname(), time=time.time())


def launch_worker(cfg_path, role):
    cfg = read(cfg_path)
    out = Path(cfg['output'])
    out.mkdir(parents=True, exist_ok=True)
    for sub in ('tmp', 'xdg', 'cache'):
        (out / sub).mkdir(exist_ok=True)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=cfg['gpu_uuid'], CUDA_DEVICE_ORDER='PCI_BUS_ID',
               VLA_RENDERER='mesa', VLA_CPU_THREADS='2', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1',
               MKL_NUM_THREADS='2', NUMEXPR_NUM_THREADS='1', LP_NUM_THREADS='1',
               PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(out / 'tmp'), XDG_RUNTIME_DIR=str(out / 'xdg'))
    for key in ('LD_PRELOAD', 'PYTHONPATH', 'MUJOCO_EGL_DEVICE_ID'):
        env.pop(key, None)
    prefix = 'encoder' if role == 'encoder' else 'native'
    argv = ['bash', read(ROOT / 'assets.json')['common']['runtime_launcher'], cfg[prefix + '_environment_id'],
            cfg[prefix + '_python'], '-B', str(ROOT / ('adapter.py' if role == 'encoder' else 'worker.py'))]
    if role == 'encoder':
        argv += ['--role', 'encoder']
    argv += ['--config', str(cfg_path)]
    with (out / (role + '.log')).open('ab') as log:
        proc = subprocess.Popen(argv, cwd=WORKSPACE, env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    CHILDREN.append(proc)
    write(out / (role + '_PROCESS.json'), dict(pid=proc.pid, pgid=proc.pid, host=socket.gethostname(),
          time=time.time(), gpu_uuid=cfg['gpu_uuid'], command=argv))
    return proc


def cleanup():
    # Only process groups created and recorded by this finite supervisor.
    for proc in CHILDREN:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    until = time.monotonic() + 20
    while time.monotonic() < until and any(proc.poll() is None for proc in CHILDREN):
        time.sleep(.5)
    for proc in CHILDREN:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=10)
    write(ROOT / 'FAMILY_EXIT.json', dict(**identity(), all_owned_children_exited=True,
          child_exit_codes=[p.returncode for p in CHILDREN]))


def supervise():
    config = read(ROOT / 'CONFIG.json')
    started = time.monotonic()
    encoders, workers, failures = {}, {}, []
    paths = [Path(p) for p in config['workers']]
    def stop(*_):
        raise KeyboardInterrupt('Finite profiling supervisor stopped')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def heartbeat(stage):
        write(ROOT / 'HEARTBEAT.json', dict(**identity(), stage=stage,
              encoder_active=sum(p.poll() is None for p in encoders.values()),
              worker_active=sum(p.poll() is None for p in workers.values()), failures=failures))
        if time.monotonic() - started > config.get('max_wall_seconds', 3600):
            raise TimeoutError('One-hour finite profiling budget exhausted')
    try:
        snapshot = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid',
                                           '--format=csv,noheader'], text=True)
        if snapshot.strip():
            raise RuntimeError('Unexpected compute context after guard handoff: ' + snapshot)
        write(ROOT / 'HOLDER_EXIT_CONFIRMED.json', dict(**identity(), compute_contexts=[], scope='all eight GPUs'))
        for path in paths:
            encoders[path] = launch_worker(path, 'encoder')
        pending = set(paths)
        while pending:
            heartbeat('external_encoder_loading')
            for path in list(pending):
                ready = Path(read(path)['output']) / 'ENCODER_READY.json'
                if ready.exists():
                    pending.remove(path)
                elif encoders[path].poll() is not None:
                    failures.append(dict(config=str(path), stage='encoder', exit_code=encoders[path].returncode))
                    pending.remove(path)
            if time.monotonic() - started > 1200:
                raise TimeoutError('External encoder readiness limit')
            if pending:
                time.sleep(3)
        for path in paths:
            if encoders[path].poll() is None:
                workers[path] = launch_worker(path, 'native')
        pending = set(workers)
        native_start = time.monotonic()
        while pending:
            heartbeat('native_models_loading')
            for path in list(pending):
                ready = Path(read(path)['output']) / 'MODEL_READY.json'
                if ready.exists():
                    pending.remove(path)
                elif workers[path].poll() is not None:
                    failures.append(dict(config=str(path), stage='native', exit_code=workers[path].returncode))
                    pending.remove(path)
            if time.monotonic() - native_start > 1200:
                raise TimeoutError('Native model readiness limit')
            if pending:
                time.sleep(3)
        write(ROOT / 'START_MEASUREMENT.json', dict(**identity(), ready_workers=sum(p.poll() is None for p in workers.values())))
        while any(p.poll() is None for p in workers.values()):
            heartbeat('profiling')
            time.sleep(3)
        for path, proc in workers.items():
            result_path = Path(read(path)['output']) / 'RESULT.json'
            result = read(result_path) if result_path.exists() else dict(status='missing')
            if proc.returncode or result['status'] != 'complete':
                failures.append(dict(config=str(path), stage='profiling', exit_code=proc.returncode, result=result))
        write(ROOT / 'FORMAL_RESULT.json', dict(**identity(), status='partial' if failures else 'complete', failures=failures))
    except BaseException as error:
        write(ROOT / 'FORMAL_RESULT.json', dict(**identity(), status='technical_failure', error=repr(error),
              traceback=traceback.format_exc(), failures=failures))
    finally:
        cleanup()
    return 0 if read(ROOT / 'FORMAL_RESULT.json')['status'] == 'complete' else 3


def outer():
    cfg = read(ROOT / 'CONFIG.json')
    local = Path(cfg['local_dir'])
    local.mkdir(parents=True, exist_ok=True)
    with (local / 'queue.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        write(ROOT / 'PROCESS.json', identity())
        result = subprocess.run([str(WORKSPACE / 'gpu_occupancy_lifecycle.sh'), 'run', '--',
                  '/usr/bin/python', '-B', str(ROOT / 'supervisor.py'), 'supervise'], cwd=WORKSPACE,
                  env=dict(os.environ, CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS='300'))
        formal = read(ROOT / 'FORMAL_RESULT.json') if (ROOT / 'FORMAL_RESULT.json').exists() else dict(status='formal_not_started')
        try:
            analysis = subprocess.run(['/usr/bin/python', '-B', str(ROOT / 'analyze.py')], cwd=ROOT,
                                      capture_output=True, text=True, timeout=90)
            analysis_result = dict(exit_code=analysis.returncode, stdout=analysis.stdout[-3000:], stderr=analysis.stderr[-3000:])
        except Exception as error:
            analysis_result = dict(exit_code=None, error=repr(error))
        write(ROOT / 'ANALYSIS_EXIT.json', analysis_result)
        write(ROOT / 'RESULT.json', dict(**identity(), status=formal['status'], formal=formal,
              lifecycle_exit=result.returncode, analysis_exit=analysis_result['exit_code'], thread=cfg['thread']))
        write(ROOT / 'outbox' / 'TERMINAL.json', dict(**read(ROOT / 'EVENT_REGISTRATION.json'),
              status=formal['status'], time=time.time(), transport_is_handler_ack=False))
        message = ('本线程用户授权的Smol/X小批量推理效率补测已终止。读取 ' + str(ROOT / 'RESULT.json') +
                   ' 与 REPORT.md，核对真实结果并补全效率表；写 outbox/HANDLER_ACK.json。' +
                   '保留工程失败，不重跑完成单元，不递归注册回调。')
        try:
            transport = subprocess.run(['codex', 'queue', '--thread', cfg['thread'], '--message', message],
                                       capture_output=True, text=True, timeout=30)
            write(ROOT / 'outbox' / 'TRANSPORT.json', dict(exit_code=transport.returncode,
                  stdout=transport.stdout[-1500:], stderr=transport.stderr[-1500:], accepted_not_handler_ack=transport.returncode == 0))
        except Exception as error:
            write(ROOT / 'outbox' / 'TRANSPORT.json', dict(error=repr(error), outbox_retained=True))


def start():
    cfg = read(ROOT / 'CONFIG.json')
    if socket.gethostname() != cfg['host']:
        raise RuntimeError('Host identity differs from this finite run configuration')
    with (ROOT / 'LAUNCH_CLAIM.json').open('x') as stream:
        json.dump(identity(), stream)
    write(ROOT / 'EVENT_REGISTRATION.json', dict(event='terminal_or_failure', thread=cfg['thread'],
          output=str(ROOT / 'RESULT.json'), acknowledgement=str(ROOT / 'outbox' / 'HANDLER_ACK.json'),
          original_executor_thread=True, recursive_callback=False))
    with (ROOT / 'supervisor.log').open('ab') as log:
        proc = subprocess.Popen(['/usr/bin/python', '-B', str(ROOT / 'supervisor.py'), 'outer'],
              cwd=WORKSPACE, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    write(ROOT / 'LAUNCH.json', dict(pid=proc.pid, pgid=proc.pid, host=socket.gethostname(), thread=cfg['thread'], time=time.time()))
    print(json.dumps(read(ROOT / 'LAUNCH.json')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'outer', 'supervise'])
    raise SystemExit(globals()[parser.parse_args().action]())
