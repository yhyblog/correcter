import contextlib
import signal
import os
import time
from pathlib import Path
from paths import ROOT, CONFIG, WORKSPACE
from admission import boundary, AdmissionStop, claim_unit, units
LOCAL=Path(CONFIG['local_dir'])

def claim_attempt(identity, **extra):
    method,sid=identity.split('/',1)
    matches=[u for u in units().values() if u['model']=='SmolVLA' and u['method']==method and u['source_id']==sid]
    if len(matches)!=1: raise ValueError('ambiguous native unit')
    return claim_unit(matches[0])

def parent_path(source): raise RuntimeError('collection not authorized')
def remaining_seconds():return CONFIG['absolute_wall_deadline_unix']-time.time()
@contextlib.contextmanager
def episode_deadline(seconds=1800):
    def expired(*_):raise AdmissionStop('episode wall deadline')
    old=signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,seconds)
    try:yield
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)

def reservation_fds():
    rows=[]
    for p in Path('/proc/self/fd').iterdir():
        try:
            if os.readlink(p)=='/tmp/gpu_occupancy_guard/formal.lock':rows.append(int(p.name))
        except OSError:pass
    if len(rows)!=1:raise RuntimeError('single inherited formal reservation required')
    return tuple(rows)

def runtime_command(environment, script, *args):
    b=WORKSPACE/'embodied-ai-workspace';prefix='lerobot' if environment=='mw-pi05-legacy' else environment
    return ['bash',str(b/'projects/vla-baselines/launchers/runtime.sh'),environment,str(b/'environments'/prefix/'bin/python'),'-B',str(ROOT/'code'/script),*map(str,args)]
