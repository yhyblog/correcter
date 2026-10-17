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
R = C / 'results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1'
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

def authorize(admission=False):
    global _checked
    if socket.gethostname() != HOST:
        raise RuntimeError('C host mismatch')
    if admission and time.time() >= 1790164800:  # 2026-09-23 12:00 UTC
        raise RuntimeError('D24 new experiment admission cutoff reached')
    if time.monotonic() - _checked < 10:
        return
    a = C / 'deadline_20260924/IDLE_NODE_CONTINUATION_AUTHORIZATION_V1.json'
    if hashlib.sha256(retry_read(a.read_bytes)).hexdigest() != AUTH_SHA:
        raise RuntimeError('D24 authorization changed; reconcile before continuation')
    root_ctl = load(C / 'CONTROL.json')
    ctl = load(C / 'persistent_queue/CONTROL.json')
    if root_ctl.get('stop_requested') or ctl.get('global_stop'):
        raise RuntimeError('Global execution stop requested')
    if not root_ctl.get('formal_gpu_runs_enabled') or 'C_D24_BASELINE_GAPS_E8_TABLES_V1' not in root_ctl['allowed_task_ids']:
        raise RuntimeError('C scientific authorization is no longer active')
    if (R / 'STOP.json').exists() or (C/'persistent_queue/nodes/C/STOP.json').exists():
        raise RuntimeError('C local stop requested')
    ident = load(C/'nodes/C/identity.json')
    if ident['hostname'] != HOST or ident['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip():
        raise RuntimeError('C host/boot changed; explicit recovery reconciliation required')
    _checked = time.monotonic()

def boundary(_release=None):
    authorize()

def append(path, value):
    with Path(path).open('a') as f:
        f.write(json.dumps(value, allow_nan=False) + '\n')
        f.flush()

def episode_claim(output, source):
    authorize(admission=True)
    cfg=load(Path(output)/'CONFIG.json')
    disposition=load(R/'N_GAP_DISPOSITION.json')
    gap=next(g for g in disposition['entries'] if g['source']['source_id']==source['source_id'])
    if not gap['eligible_for_C_attempt'] or gap['historical_physical_attempts']!=1:
        raise RuntimeError('Source is not eligible for its single corrected N retry')
    prior=load(cfg['retry_of'])['row']
    if prior['status']!='technical_failure' or prior['success'] is not None or prior['source_id']!=source['source_id']:
        raise RuntimeError('Missing authoritative failed source record')
    if not load(cfg['original_exit_evidence'])['all_owned_descendants_exited']:
        raise RuntimeError('Original B process family has no exit proof')
    if len(list((R/'unit_claims').glob('*.json'))) >= 5:
        raise RuntimeError('The five eligible source attempts have been consumed')
    record=dict(source=source, method='N', attempt=2, C_attempt=1, original_claim=cfg['original_claim'],
                prior_failure=cfg['retry_of'], process=identity(), entered_at_utc=utc(), output=str(output))
    exclusive(R/'unit_claims'/(source['source_id']+'__N__corrected1.json'),record)
    exclusive(Path(output)/'episode_claims'/(source['source_id']+'.json'),record)

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
