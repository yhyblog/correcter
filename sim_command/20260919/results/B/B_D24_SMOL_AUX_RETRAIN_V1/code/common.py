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

LOCAL=Path('/tmp/corrector_B_SMOL_AUX_r1')

def parent_key(source):return '%03d_%s_%d'%(source['task_ascii_index'],source['split'],source['ordinal'])
def parent_path(source):return ROOT/'collection'/parent_key(source)

def claim_attempt(identity,**extra):
    boundary(admission=True);LOCAL.mkdir(exist_ok=True)
    key=hashlib.sha256(identity.encode()).hexdigest()
    with (LOCAL/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        target=ROOT/'claims/attempts'/(key+'.json')
        if target.exists():raise RuntimeError('existing attempt identity; never implicit replay')
        counter=ROOT/'ATTEMPT_COUNTER.json'
        n=read(counter).get('reserved_attempts',0) if counter.exists() else 0
        cfg=read(ROOT/'config/CONFIG.json')
        if n>=cfg['stage_attempt_cap'] or n+cfg['planned_prior_attempts']>=cfg['node_cumulative_attempt_cap']:
            raise AdmissionStop('hard attempt budget')
        atomic_json(counter,dict(reserved_attempts=n+1,prior_B_attempts=cfg['planned_prior_attempts'],
            cumulative_B_reserved=cfg['planned_prior_attempts']+n+1,at_utc=utc()))
        new_json(target,dict(identity=identity,number=n+1,process=process_identity(),at_utc=utc(),**extra))
        return str(target)

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
