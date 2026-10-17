"""C-only authorization, host identity and durable episode admission."""
import datetime
import errno
import contextlib
import hashlib
import json
import os
from pathlib import Path
import socket
import signal
import time

W = Path(__file__).resolve().parent
C = W.parents[2]
ROOT = C.parents[2]
R = C / 'results/C/C_D24_R_H40_H50_V1'
HOST = 'trial-303269581-trialrun-303269581-worker-0'
AUTH_SHA = 'f9e3f3693b5b035a2a5498818f0068569c65b582bc85b9a08062233eab1bba97'
_checked = 0.0

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def retry_read(reader, *, timeout=30.0, interval=0.25):
    # Stop at the read boundary while a publication is temporarily unavailable.
    # Never return cached authorization as a substitute for a failed read.
    deadline = time.monotonic() + timeout
    while True:
        try:
            return reader()
        except (OSError, json.JSONDecodeError) as exc:
            if isinstance(exc, OSError) and exc.errno not in (errno.ENOENT, errno.ESTALE, errno.EIO, errno.EAGAIN, errno.ETIMEDOUT):
                raise
            if time.monotonic() >= deadline:
                raise RuntimeError('Required metadata unavailable after bounded read wait: ' + repr(exc)) from exc
            time.sleep(min(interval, max(0, deadline - time.monotonic())))

def load(path):
    return retry_read(lambda: json.loads(Path(path).read_text()))

def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.%d.tmp' % os.getpid())
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    os.replace(str(temp), str(path))

def exclusive(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())

def identity(pid=None):
    pid = pid or os.getpid()
    fields = Path('/proc/%d/stat' % pid).read_text().rsplit(')', 1)[1].split()
    if fields[0] == 'Z':
        raise ProcessLookupError(pid)
    return dict(hostname=socket.gethostname(), boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                pid=pid, start_ticks=int(fields[19]), session_id=int(fields[3]))

def alive(value):
    try:
        actual = identity(value['pid'])
        return all(actual[k] == value[k] for k in ('hostname', 'boot_id', 'pid', 'start_ticks'))
    except (OSError, ValueError, KeyError):
        return False

