#!/usr/bin/env python3
"""Per-GPU idle holders; cooperating formal jobs reserve GPUs before loading CUDA."""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
STATE = Path('/tmp/gpu_occupancy_guard')
STATE.mkdir(exist_ok=True)
ENV = dict(os.environ)
ENV.pop('CUDA_VISIBLE_DEVICES', None)


def query(fields, kind='gpu'):
    output = subprocess.check_output(
        ['nvidia-smi', f'--query-{kind}={fields}', '--format=csv,noheader,nounits'],
        text=True, timeout=15, env=ENV)
    return [[v.strip() for v in row] for row in csv.reader(output.splitlines()) if row]


def descendant(pid, parent):
    seen = set()
    while pid > 1 and pid not in seen:
        if pid == parent:
            return True
        seen.add(pid)
        try:
            pid = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            return False
    return False


def log(message):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), message, flush=True)


def stop(proc):
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)


def guard():
    singleton = (STATE / 'daemon.lock').open('a')
    try:
        fcntl.flock(singleton, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    (STATE / 'pid').write_text(str(os.getpid()))
    reservation = (STATE / 'formal.lock').open('a')
    holders = {}
    driver_pids = {}
    started_at = {}
    running = True

    def halt(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, halt)
    signal.signal(signal.SIGINT, halt)
    try:
        while running:
            locked = False
            try:
                try:
                    fcntl.flock(reservation, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                except BlockingIOError:
                    pass
                gpu_rows = query('index,uuid')
                apps = query('gpu_uuid,pid', 'compute-apps')
                status = {}
                for index, uuid in gpu_rows:
                    proc = holders.get(index)
                    current = {int(pid) for dev, pid in apps if dev == uuid}
                    # NVML reports host PIDs in this container. Each holder starts
                    # only after an empty per-GPU snapshot. Track its single new
                    # CUDA context; any additional PID forces us to yield. Never
                    # signal an NVML PID: only stop our own Popen process group.
                    if (proc is not None and proc.poll() is None and
                            index not in driver_pids and len(current) == 1):
                        driver_pids[index] = current
                    external = [int(pid) for dev, pid in apps if dev == uuid and
                                int(pid) not in driver_pids.get(index, set()) and
                                (proc is None or not descendant(int(pid), proc.pid))]
                    if not locked or external:
                        if proc:
                            stop(proc)
                            holders.pop(index)
                            driver_pids.pop(index, None)
                            log(f'GPU {index}: yielded; external={external}, reserved={not locked}')
                        status[index] = {'state': 'reserved' if not locked else 'external', 'pids': external}
                        continue
                    missing_context = (proc is not None and
                                       time.monotonic() - started_at.get(index, 0) > 45 and
                                       not current.intersection(driver_pids.get(index, set())))
                    if proc is None or proc.poll() is not None or missing_context:
                        if proc is not None:
                            stop(proc)
                        driver_pids.pop(index, None)
                        with (ROOT / 'gpu_occupancy_guard.holders.log').open('a') as output:
                            proc = subprocess.Popen(
                                [sys.executable, str(ROOT / 'gpu_hold.py'), '--devices', index,
                                 '--size', '8192', '--dtype', 'bf16', '--log-interval', '300',
                                 '--target-util', '0.90', '--period-seconds', '0.20'],
                                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                start_new_session=True, env=ENV)
                        holders[index] = proc
                        started_at[index] = time.monotonic()
                        log(f'GPU {index}: started holder manager {proc.pid}')
                    status[index] = {'state': 'holder', 'manager_pid': proc.pid,
                                     'driver_pids': sorted(driver_pids.get(index, set()))}
                data = {'pid': os.getpid(), 'updated': time.time(), 'gpus': status}
                temporary = STATE / 'status.tmp'
                temporary.write_text(json.dumps(data, indent=2) + '\n')
                temporary.replace(STATE / 'status.json')
            except Exception as exc:
                log(f'GPU inspection failed; stopping own holders and retrying: {exc}')
                for proc in holders.values():
                    stop(proc)
                holders.clear()
                driver_pids.clear()
            finally:
                if locked:
                    fcntl.flock(reservation, fcntl.LOCK_UN)
            for _ in range(5):
                if running:
                    time.sleep(1)
    finally:
        for proc in holders.values():
            stop(proc)


def is_running():
    with (STATE / 'daemon.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return False
        except BlockingIOError:
            return True


def start():
    if not is_running():
        with (ROOT / 'gpu_occupancy_guard.log').open('a') as output:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'daemon'],
                             stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                             start_new_session=True, env=ENV)
        for _ in range(50):
            if is_running():
                break
            time.sleep(.1)
    if not is_running():
        raise RuntimeError('guard failed to start')
    print('guard running; pid=' + (STATE / 'pid').read_text())


def handoff_timeout_seconds():
    raw = os.environ.get('CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS', '90')
    if (not raw or not raw.isascii() or not raw.isdecimal()
            or raw.startswith('0') or len(raw) > 3 or not 1 <= int(raw) <= 300):
        raise ValueError('CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS must be an ASCII integer in [1, 300]')
    return int(raw)


def run_formal(command):
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        raise ValueError('run requires a command')
    handoff_seconds = handoff_timeout_seconds()  # validate before start/lock/query
    start()
    with (STATE / 'formal.lock').open('a') as reservation:
        fcntl.flock(reservation, fcntl.LOCK_EX)
        handoff_started = time.monotonic()
        deadline = handoff_started + handoff_seconds
        poll_attempts = 0
        last_observation = None
        reason = 'query_error'
        try:
            while True:
                if time.monotonic() >= deadline:
                    reason = 'handoff_deadline'
                    raise RuntimeError('GPU handoff deadline expired; formal command was not launched')
                query_started = time.monotonic()
                poll_attempts += 1
                reason = 'query_error'
                apps = query('pid', 'compute-apps')
                observed = time.monotonic()
                if not isinstance(apps, list):
                    raise RuntimeError('Invalid compute-apps response; formal command was not launched')
                last_observation = dict(query_started_monotonic=query_started,
                    returned_monotonic=observed, rows=apps[:64], total_rows=len(apps),
                    truncated=len(apps) > 64, pid_namespace='NVML host PID rows; not container holder manager PIDs')
                if observed >= deadline:
                    reason = 'handoff_deadline'
                    raise RuntimeError('GPU handoff deadline expired; formal command was not launched')
                if not apps:
                    break
                time.sleep(min(1, deadline - observed))
        except Exception as error:
            log('HANDOFF_FAILURE_JSON ' + json.dumps(dict(timeout_seconds=handoff_seconds,
                elapsed_seconds=time.monotonic() - handoff_started, reason=reason,
                poll_attempts=poll_attempts, last_observation=last_observation,
                error_type=type(error).__name__, error=str(error)[:2048],
                extra_hardware_queries=0, last_observation_is_not_a_new_deadline_probe=True), sort_keys=True))
            raise
        proc = subprocess.Popen(command, start_new_session=True,
                                pass_fds=(reservation.fileno(),))
        def forward(sig, _):
            if proc.poll() is None:
                os.killpg(proc.pid, sig)
        previous = {sig: signal.signal(sig, forward) for sig in
                    (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        try:
            result = proc.wait()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    # The guard sees the released reservation on its next poll, even on errors.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'daemon', 'active', 'status', 'run'])
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == 'daemon':
        guard()
    elif args.action == 'start':
        start()
    elif args.action == 'active':
        return 0 if is_running() else 1
    elif args.action == 'status':
        print('running=' + str(is_running()))
        print((STATE / 'status.json').read_text())
    else:
        return run_formal(args.command)
    return 0


if __name__ == '__main__':
    sys.exit(main())
