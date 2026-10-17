"""Capture one frozen V3 command. No extra device or holder queries."""
import datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import time

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORK = Path(__file__).resolve().parent
PACKAGE = BASE / 'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1'
LAUNCH = BASE / 'results/A/P10_PV_V3_launcher_runs/A10_PV_OFFLINE_PREFLIGHT_V3_r1_A_wave08'
COMMAND = ['bash', str(PACKAGE / 'commands/run_proposed_pv_offline.sh'),
           str(BASE / 'releases/P10_A_PV_OFFLINE_PREFLIGHT_V3.json')]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def put(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def heartbeat(phase, pid=None, code=None):
    last_mark = None
    timing = LAUNCH / 'wave_timing.jsonl'
    try:
        if timing.exists():
            rows = timing.read_text().splitlines()
            if rows:
                last_mark = json.loads(rows[-1])
    except (OSError, ValueError):
        pass
    record = dict(at_utc=now(), phase=phase, command_pid=pid,
                  exit_code=code, last_existing_wave_marker=last_mark,
                  additional_hardware_or_holder_queries=0)
    with (WORK / 'HEARTBEAT.jsonl').open('a') as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def main():
    started = now()
    began = time.monotonic_ns()
    put(WORK / 'COMMAND_STARTED.json', dict(
        task_id='A10_PV_OFFLINE_PREFLIGHT_V3', command=COMMAND,
        cwd=str(PACKAGE), hostname=platform.node(), started_at_utc=started,
        maximum_invocations=1, maximum_retries=0,
        lifecycle_and_timeout='Exclusively managed by frozen launcher; no outer timeout or lock.'))
    child = None
    code = None
    error = None
    with (WORK / 'COMMAND_STDOUT.txt').open('xb') as stdout, \
            (WORK / 'COMMAND_STDERR.txt').open('xb') as stderr:
        try:
            child = subprocess.Popen(COMMAND, cwd=str(PACKAGE), stdout=stdout, stderr=stderr)
            heartbeat('frozen_command_spawned', child.pid)
            print(json.dumps(dict(started_at_utc=started, pid=child.pid, command=COMMAND)), flush=True)
            while True:
                try:
                    code = child.wait(timeout=30)
                    break
                except subprocess.TimeoutExpired:
                    heartbeat('frozen_command_running', child.pid)
        except Exception as exc:
            error = dict(type=type(exc).__name__, message=str(exc))
        stdout.flush()
        stderr.flush()
        os.fsync(stdout.fileno())
        os.fsync(stderr.fileno())
    finished = now()
    elapsed = time.monotonic_ns() - began
    heartbeat('frozen_command_exited' if code is not None else 'outer_error',
              None if child is None else child.pid, code)
    result = dict(task_id='A10_PV_OFFLINE_PREFLIGHT_V3', recorder='execution_A_outer_capture',
                  command=COMMAND, cwd=str(PACKAGE), hostname=platform.node(),
                  started_at_utc=started, finished_at_utc=finished,
                  elapsed_monotonic_ns=elapsed, elapsed_seconds=elapsed / 1e9,
                  command_invocation_attempts=1, spawned_commands=int(child is not None),
                  retries=0, pid=None if child is None else child.pid,
                  exit_code=code, child_reaped=child is not None and code is not None,
                  outer_exception=error,
                  stdout_path=str(WORK / 'COMMAND_STDOUT.txt'),
                  stderr_path=str(WORK / 'COMMAND_STDERR.txt'),
                  launch_directory=str(LAUNCH),
                  automatic_retry=False)
    put(WORK / 'COMMAND_RESULT.json', result)
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
    return code if code is not None else 99


if __name__ == '__main__':
    raise SystemExit(main())
