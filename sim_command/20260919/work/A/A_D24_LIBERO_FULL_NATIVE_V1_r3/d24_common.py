"""A-owned finite LIBERO adaptation; ordinary bounded controls only."""
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import time

W=Path(__file__).resolve().parent
C=W.parents[2]
ROOT=C.parents[2]
R=C/'results/A/A_D24_LIBERO_FULL_NATIVE_V1/launch_r3'
TASK='A_D24_LIBERO_FULL_NATIVE_V1'
AUTH_SHA='f9e3f3693b5b035a2a5498818f0068569c65b582bc85b9a08062233eab1bba97'
HOST='trial-303224955-trialrun-303224955-worker-0'
_checked=0.

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def load(path):
    deadline=time.monotonic()+30
    while True:
        try:return json.loads(Path(path).read_text())
        except (OSError,json.JSONDecodeError):
            if time.monotonic()>deadline:raise
            time.sleep(.25)

def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.%d.tmp'%os.getpid())
    temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');os.replace(str(temp),str(path))

def exclusive(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def append(path,value):
    with Path(path).open('a') as f:f.write(json.dumps(value,allow_nan=False)+'\n');f.flush()

def identity(pid=None):
    pid=pid or os.getpid();fields=Path('/proc/%d/stat'%pid).read_text().rsplit(')',1)[1].split()
    if fields[0]=='Z':raise ProcessLookupError(pid)
    return dict(hostname=socket.gethostname(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        pid=pid,start_ticks=int(fields[19]),session_id=int(fields[3]))

def alive(value):
    try:
        actual=identity(value['pid']);return all(actual[k]==value[k] for k in ('hostname','boot_id','pid','start_ticks'))
    except (OSError,ValueError,KeyError):return False

def authorize(admission=False):
    global _checked
    if socket.gethostname()!=HOST:raise RuntimeError('A host mismatch')
    if admission and time.time()>=1790164800:raise RuntimeError('D24 admission cutoff')
    if (R/'STOP.json').exists():raise RuntimeError('A local stop')
    if (R/'CLAIM.json').exists() and time.time()-load(R.parent/'CLAIM.json')['started_unix']>8*3600:
        raise TimeoutError('Task8hour wall deadline')
    if time.monotonic()-_checked<10:return
    p=C/'deadline_20260924/IDLE_NODE_CONTINUATION_AUTHORIZATION_V1.json'
    if hashlib.sha256(p.read_bytes()).hexdigest()!=AUTH_SHA:raise RuntimeError('Task authorization changed')
    a=load(p);ctl=load(C/'persistent_queue/CONTROL.json');main=load(C/'CONTROL.json')
    if a['status']!='released' or a['A']['task_id']!=TASK or a['A']['host']!=HOST:
        raise RuntimeError('Task identity inactive')
    if ctl.get('global_stop') or not ctl['nodes']['A']['enabled'] or main.get('stop_requested'):
        raise RuntimeError('A disabled by CONTROL')
    _checked=time.monotonic()

def episode_claim(output,source,phase,method):
    authorize(admission=True)
    assert phase in ('development','Full-Post','Full-Velocity')
    if phase=='development':
        assert source['split'] in ('adapt_train','adapt_validation') and source['branch'] in ('old','fresh')
    else:assert source['split']=='test' and (R/'METHOD_FROZEN.json').exists()
    exclusive(Path(output)/'episode_claims'/(phase+'__'+source['source_id']+'.json'),
        dict(source=source,phase=phase,method=method,entered_at_utc=utc(),process=identity()))

@contextlib.contextmanager
def episode_deadline(seconds=1800):
    def expired(*_):raise TimeoutError('planned episode wall timeout')
    old=signal.signal(signal.SIGALRM,expired);signal.alarm(seconds)
    try:yield
    finally:signal.alarm(0);signal.signal(signal.SIGALRM,old)

def failed():return (R/'PIPELINE_FAILED.json').exists() or (R/'SCIENTIFIC_GAP.json').exists()

def event(name,**payload):
    p=R/'outbox'/(name+'.json')
    if not p.exists():exclusive(p,dict(event_id=TASK+'_launch_r3_'+name,synthetic=False,utc=utc(),task_id=TASK,**payload))
