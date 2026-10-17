"""Capture the single authorized CPU file transition; never invokes the guard."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import time

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORK = Path(__file__).resolve().parent
PACKAGE = BASE / 'results/A/A10_PV_HANDOFF_CPU_REPAIR_V1'
TARGET = Path('/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py')
COMMAND = [
    '/usr/bin/python3', '-I', '-S', '-B',
    str(PACKAGE / 'commands/transition_guard_file_cpu.py'),
    '--release', str(BASE / 'releases/P00_A_GUARD_HANDOFF_INSTALL_V1.json'),
    '--operation', 'install',
]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def put(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def target_identity():
    meta = TARGET.lstat()
    raw = TARGET.read_bytes()
    return dict(path=str(TARGET), realpath=str(TARGET.resolve()),
                sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw),
                is_symlink=TARGET.is_symlink(), regular_file=stat.S_ISREG(meta.st_mode),
                mode=oct(stat.S_IMODE(meta.st_mode)), uid=meta.st_uid, gid=meta.st_gid,
                inode=meta.st_ino, device=meta.st_dev,
                mtime_ns=meta.st_mtime_ns, ctime_ns=meta.st_ctime_ns)


def main():
    started = now()
    began = time.monotonic_ns()
    put(WORK / 'COMMAND_STARTED.json', dict(
        task_id='A10_GUARD_HANDOFF_INSTALL_V1', command=COMMAND,
        cwd=str(PACKAGE), host=platform.node(), started_at_utc=started,
        maximum_invocations=1, maximum_retries=0))
    process = None
    code = None
    error = None
    with (WORK / 'INSTALL_STDOUT.txt').open('xb') as stdout, \
            (WORK / 'INSTALL_STDERR.txt').open('xb') as stderr:
        try:
            process = subprocess.Popen(COMMAND, cwd=str(PACKAGE), stdout=stdout, stderr=stderr)
            code = process.wait()
        except Exception as exc:
            error = dict(type=type(exc).__name__, message=str(exc))
        stdout.flush()
        stderr.flush()
        os.fsync(stdout.fileno())
        os.fsync(stderr.fileno())
    finished = now()
    elapsed_ns = time.monotonic_ns() - began
    try:
        after = target_identity()
    except Exception as exc:
        after = dict(path=str(TARGET), observation_error=dict(
            type=type(exc).__name__, message=str(exc)))
    put(WORK / 'TARGET_AFTER.json', after)
    result = dict(
        task_id='A10_GUARD_HANDOFF_INSTALL_V1', recorder='execution_A_outer_capture',
        command=COMMAND, cwd=str(PACKAGE), host=platform.node(),
        started_at_utc=started, finished_at_utc=finished,
        elapsed_monotonic_ns=elapsed_ns, elapsed_seconds=elapsed_ns / 1e9,
        command_invocation_attempts=1, spawned_commands=int(process is not None),
        retries=0, pid=None if process is None else process.pid,
        exit_code=code, child_reaped=process is not None and code is not None,
        outer_exception=error,
        stdout_path=str(WORK / 'INSTALL_STDOUT.txt'),
        stderr_path=str(WORK / 'INSTALL_STDERR.txt'),
        target_after_path=str(WORK / 'TARGET_AFTER.json'),
        automatic_rollback=False)
    put(WORK / 'COMMAND_RESULT.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
