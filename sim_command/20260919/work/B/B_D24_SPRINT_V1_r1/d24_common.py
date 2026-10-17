"""Small D24 controls shared by the B-owned workers (also Python 3.8)."""
import datetime
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
R = C / 'results/B/B_D24_SPRINT_V1/r1'
HOST = 'trial-303225685-trialrun-303225685-worker-0'
AUTH_SHA = 'd87a62fe7e335ae84cc9b7d3edc82c5a6f0395ff895fb725e31b16c731238f80'
_checked = 0.0

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def load(path):
    return json.loads(Path(path).read_text())

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
        json.dump(value, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())

def identity(pid=None):
    pid = pid or os.getpid()
    fields = Path('/proc/%d/stat' % pid).read_text().rsplit(')', 1)[1].split()
    return dict(hostname=socket.gethostname(), boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                pid=pid, start_ticks=int(fields[19]), session_id=int(fields[3]))

def alive(value):
    try:
        actual = identity(value['pid'])
        return all(actual[k] == value[k] for k in ('hostname', 'boot_id', 'pid', 'start_ticks'))
    except (OSError, ValueError, KeyError):
        return False

def authorize(admission=False):
    global _checked
    if socket.gethostname() != HOST:
        raise RuntimeError('B host mismatch')
    if admission and time.time() >= 1790164800:  # 2026-09-23 12:00 UTC
        raise RuntimeError('D24 new experiment admission cutoff reached')
    if time.monotonic() - _checked < 10:
        return
    a = C / 'deadline_20260924/AUTHORIZATION_V1.json'
    if hashlib.sha256(a.read_bytes()).hexdigest() != AUTH_SHA:
        raise RuntimeError('D24 authorization changed; reconcile before continuation')
    ctl = load(C / 'persistent_queue/CONTROL.json')
    root_ctl = load(C / 'CONTROL.json')
    if ctl.get('global_stop') or not ctl['nodes']['B']['enabled'] or root_ctl.get('stop_requested'):
        raise RuntimeError('B execution stopped by CONTROL')
    ref = ctl.get('deadline_override', {})
    if ref.get('sha256') != AUTH_SHA or root_ctl.get('active_compute_release_id') != 'D24_SPRINT_V1':
        raise RuntimeError('D24 is no longer the current scientific authorization')
    if (R / 'STOP.json').exists():
        raise RuntimeError('B sprint local stop requested')
    _checked = time.monotonic()

def boundary(_release=None):
    authorize()

def append(path, value):
    with Path(path).open('a') as f:
        f.write(json.dumps(value, allow_nan=False) + '\n')
        f.flush()

def episode_claim(output, source):
    authorize(admission=True)
    exclusive(Path(output) / 'episode_claims' / (source['source_id'] + '.json'),
              dict(source=source, entered_at_utc=utc(), process=identity()))

@contextlib.contextmanager
def episode_deadline(seconds=1800):
    def expired(*_):
        raise TimeoutError('planned episode wall timeout')
    old = signal.signal(signal.SIGALRM, expired)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
