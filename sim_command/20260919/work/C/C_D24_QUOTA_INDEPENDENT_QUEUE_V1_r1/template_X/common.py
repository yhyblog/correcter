import contextlib
import fcntl
import hashlib
import os
import signal
import time
from pathlib import Path
from paths import ROOT,CAMPAIGN,WORKSPACE
from qio import read,new_json,atomic_json,utc,process_identity
from admission import boundary,AdmissionStop
from operational_hook import reject_completed_terminal

LOCAL=Path('/tmp/corrector_C_FULLQ_r1')

from continuation_adapter import claim_attempt


def claim_work(kind,key,**extra):
    """An exclusive parent/task claim permits prompt backfill by resident workers."""
    boundary(admission=True)
    target=ROOT/'claims'/kind/(hashlib.sha256(key.encode()).hexdigest()+'.json')
    try:new_json(target,dict(identity=key,process=process_identity(),at_utc=utc(),**extra))
    except FileExistsError:return False
    return True

@contextlib.contextmanager
def episode_deadline(seconds=1800):
    def expired(*_):raise AdmissionStop('episode finite wall budget expired')
    old=signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,seconds)
    try:yield
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)

def remaining_seconds():return read(ROOT/'config/CONFIG.json')['absolute_wall_deadline_unix']-time.time()

def reservation_fds():
    result=[]
    for p in Path('/proc/self/fd').iterdir():
        try:
            if os.readlink(p)=='/tmp/gpu_occupancy_guard/formal.lock':result.append(int(p.name))
        except OSError:pass
    if len(result)!=1:raise RuntimeError('requires existing whole-wave reservation')
    return tuple(result)

def runtime_command(environment,script,*arguments):
    prefix='lerobot' if environment=='mw-pi05-legacy' else environment
    base=WORKSPACE/'embodied-ai-workspace'
    return ['bash',str(base/'projects/vla-baselines/launchers/runtime.sh'),environment,
            str(base/'environments'/prefix/'bin/python'),'-B',str(ROOT/'code'/script),*map(str,arguments)]
