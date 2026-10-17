"""CPU timing/receipt helpers; these functions never reserve or compute on GPUs."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def stamp():
    return {'monotonic_seconds': time.monotonic(), 'unix_seconds': time.time(),
            'utc': datetime.now(timezone.utc).isoformat()}


def write_new(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def mark(directory, name, **extra):
    row = {'phase': name, **stamp(), **extra}
    with (Path(directory) / 'wave_timing.jsonl').open('a') as stream:
        stream.write(json.dumps(row, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    return row


def run_forwarded(command, *, cwd, env=None, pass_fds=(), new_session=False):
    process = subprocess.Popen(command, cwd=cwd, env=env, pass_fds=pass_fds, start_new_session=new_session)

    def forward(sig, _):
        if process.poll() is None:
            try:
                if new_session:
                    os.killpg(process.pid, sig)
                else:
                    process.send_signal(sig)
            except ProcessLookupError:
                pass
    previous = {sig: signal.signal(sig, forward) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        return process.wait()
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def held_reservation_fds():
    # Preserve the guard lock through timeout and its child even if this wrapper
    # is killed; never open/acquire/release the lock ourselves.
    result = []
    for entry in Path('/proc/self/fd').iterdir():
        try:
            if str(entry.resolve(strict=True)) == '/tmp/gpu_occupancy_guard/formal.lock':
                result.append(int(entry.name))
        except OSError:
            pass
    return tuple(result)


def observe_restoration(after_unix, seconds=120, read_status=None, clock=time.monotonic, pause=time.sleep):
    read_status = read_status or (lambda: json.loads(Path('/tmp/gpu_occupancy_guard/status.json').read_text()))
    deadline = clock() + seconds
    last, error = None, None
    while True:
        try:
            last = read_status()
            rows = last.get('gpus', {})
            if last.get('updated', 0) >= after_unix and set(rows) == set(map(str, range(8))):
                resolved = all(r.get('state') == 'external' or
                               (r.get('state') == 'holder' and bool(r.get('driver_pids')) and
                                Path('/proc/' + str(r.get('manager_pid'))).exists()) for r in rows.values())
                if resolved:
                    return {'status': 'occupancy_resolved', 'guard_status': last,
                            'external_jobs_preserved': True, 'observed_at': stamp()}
        except (OSError, ValueError) as failure:
            error = str(failure)
        if clock() >= deadline:
            return {'status': 'restoration_observation_timed_out', 'guard_status': last,
                    'error': error, 'restoration_complete': None, 'observed_at': stamp()}
        pause(min(1, max(0, deadline - clock())))


def timing_summary(marks):
    by_name = {r['phase']: r for r in marks}
    def elapsed(first, last):
        if first not in by_name or last not in by_name:
            return None
        return by_name[last]['monotonic_seconds'] - by_name[first]['monotonic_seconds']
    return {
        'preparation_seconds': elapsed('launcher_started', 'lifecycle_requested'),
        'reservation_and_holder_release_seconds': elapsed('lifecycle_requested', 'reserved_command_started'),
        'reserved_wrapper_setup_seconds': elapsed('reserved_command_started', 'timed_process_started'),
        'timed_diagnostic_process_seconds': elapsed('timed_process_started', 'timed_process_exited'),
        'reservation_release_overhead_seconds': elapsed('timed_process_exited', 'lifecycle_returned'),
        'restoration_observation_seconds': elapsed('lifecycle_returned', 'restoration_observed'),
        'end_to_end_observed_seconds': elapsed('launcher_started', 'restoration_observed'),
        'timeout_scope': 'GNU timeout child: CPU authorization and static library checks, EGL device mapping, one context, one static scene RGB render/readback, cleanup',
        'timeout_seconds': 120, 'kill_grace_seconds': 10,
        'end_to_end_strict_upper_bound_seconds': None,
        'missing_reason': 'Pre-launch CPU SHA/device checks, reservation, release and restoration are outside the child timeout; missing markers yield null, never fabricated zero durations',
    }
