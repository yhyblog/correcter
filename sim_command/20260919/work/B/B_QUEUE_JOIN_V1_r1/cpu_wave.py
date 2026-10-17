#!/usr/bin/python
"""Bounded B11 CPU queue under QUEUE_AUTONOMY_V1 control-plane authority.

One detached controller, one lifecycle reservation across tests/consume/publish.
The real collection supervisor remains the separately gated A public package.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import b_join_waiter as b

B11 = b.C/'work/B/B11_COMMON_POOL_VIEWS_CPU_V1_r1'
LIFECYCLE = '/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh'


def plan(wave):
    p = wave/'JOBS.json'; d = b.read(p)
    if d['authorization_sha256'] != b.AUTH_SHA or d['task_id'] != 'B11_COMMON_POOL_VIEWS_CPU_V1':
        raise ValueError('not the admitted CPU task')
    for r in d['files']:
        f=Path(r['path'])
        if not f.is_relative_to(B11) and f != Path(__file__).resolve():
            raise ValueError('CPU code outside isolated package')
        if hashlib.sha256(f.read_bytes()).hexdigest() != r['sha256']:
            raise ValueError('frozen CPU code changed')
    return d


def reservation_fds():
    result=[]
    for p in Path('/proc/self/fd').iterdir():
        try:
            if p.readlink() == Path('/tmp/gpu_occupancy_guard/formal.lock'):
                result.append(int(p.name))
        except OSError:
            pass
    if len(result) != 1:
        raise ValueError('must inherit exactly one outer formal reservation; never reacquire')
    return tuple(result)


def group_alive(pid):
    try:
        os.killpg(pid,0); return True
    except ProcessLookupError:
        return False


def drain(wave):
    d=plan(wave); fds=reservation_fds()
    b.atomic(wave/'RESERVATION.json',dict(inherited_fds=list(fds),nested_acquisitions=0,
             process_identity=b.identity(),authority='QUEUE_AUTONOMY_V1',holder_policy='all8off through tests, consumer and publication'),exclusive=True)
    for job in d['jobs']:
        if (wave/(job['id']+'.ENTERED.json')).exists():
            raise ValueError('CPU command already entered; automatic retry forbidden')
        plan(wave)
        b.atomic(wave/(job['id']+'.ENTERED.json'),dict(argv=job['argv'],at_utc=b.utc(),owner=b.identity()),exclusive=True)
        with (wave/(job['id']+'.log')).open('ab',buffering=0) as log:
            child=subprocess.Popen(job['argv'],cwd=B11,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                                   start_new_session=True,pass_fds=fds,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
            b.atomic(wave/(job['id']+'.PROCESS.json'),b.identity(child.pid),exclusive=True)
            while child.poll() is None:
                b.atomic(wave/'HEARTBEAT.json',dict(node='B',host=b.HOST,at_utc=b.utc(),current_job=job['id'],
                          owner=b.identity(),child_pid=child.pid,reservation='held_inherited',holder_mode='all8off'))
                time.sleep(1)
            code=child.returncode
        remaining=group_alive(child.pid)
        cleanup=[]
        if remaining:
            # Only the session just created and still owned by this controller.
            os.killpg(child.pid,signal.SIGTERM); cleanup.append('owned_group_SIGTERM')
            for _ in range(30):
                if not group_alive(child.pid):break
                time.sleep(1)
            if group_alive(child.pid):
                os.killpg(child.pid,signal.SIGKILL);cleanup.append('owned_group_SIGKILL')
            for _ in range(10):
                if not group_alive(child.pid):break
                time.sleep(1)
        if group_alive(child.pid):
            # Keep inherited reservation in this living controller until an
            # operator reconciles unknown descendants; never restore over them.
            while group_alive(child.pid):
                b.atomic(wave/'HEARTBEAT.json',dict(node='B',host=b.HOST,at_utc=b.utc(),
                    current_job=job['id'],blocked_reason='owned_descendants_not_reaped',reservation='held'))
                time.sleep(5)
        result=dict(status='complete' if code==0 and not remaining else 'failed',exit_code=code,
                    finished_at_utc=b.utc(),remaining_process_group=False,cleanup=cleanup,
                    restoration_deferred_to_queue=True)
        b.atomic(wave/(job['id']+'.RESULT.json'),result,exclusive=True)
        if result['status']!='complete':
            raise SystemExit(code or 1)
    b.atomic(wave/'DRAIN_COMPLETE.json',dict(at_utc=b.utc(),all_jobs_completed=True,
             all_owned_descendants_exited=True,publication_completed=True,reservation_release_allowed=True),exclusive=True)


def supervise(wave):
    with b.lock_path(wave,'singleton.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        b.atomic(wave/'PROCESS.json',b.identity())
        if (wave/'WAVE_ENTERED.json').exists():
            b.atomic(wave/'BLOCKED.json',dict(reason='prior wave execution requires reconciliation; not rerun',at_utc=b.utc()))
            return
        b.authorization();plan(wave)
        b.atomic(wave/'WAVE_ENTERED.json',dict(at_utc=b.utc(),owner=b.identity()),exclusive=True)
        env=dict(os.environ,CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS='300',PYTHONDONTWRITEBYTECODE='1')
        with (wave/'lifecycle.log').open('ab',buffering=0) as log:
            proc=subprocess.Popen([LIFECYCLE,'run','--',b.PYTHON,str(Path(__file__).resolve()),'drain','--wave',str(wave)],
                                  env=env,cwd=b.HERE,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                                  start_new_session=True)
            b.atomic(wave/'LIFECYCLE_PROCESS.json',b.identity(proc.pid),exclusive=True)
            code=proc.wait()
        b.atomic(wave/'WAVE_RESULT.json',dict(status='complete' if code==0 else 'failed',exit_code=code,
                 at_utc=b.utc(),no_automatic_retry=True,holder_restoration='outer lifecycle reservation released after child exit'),exclusive=True)


def start(wave):
    b.authorization();plan(wave)
    with b.lock_path(wave,'startup.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if (wave/'PROCESS.json').exists() and b.alive(b.read(wave/'PROCESS.json')):
            return dict(status='already_running',identity=b.read(wave/'PROCESS.json'))
        if (wave/'WAVE_ENTERED.json').exists():
            return dict(status='already_consumed_or_unknown',result=str(wave/'WAVE_RESULT.json'))
        with (wave/'supervisor.log').open('ab',buffering=0) as log:
            child=subprocess.Popen([b.PYTHON,str(Path(__file__).resolve()),'supervise','--wave',str(wave)],
                                   stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                                   start_new_session=True,close_fds=True,cwd=b.HERE)
        for _ in range(50):
            if (wave/'PROCESS.json').exists():
                return dict(status='started',identity=b.read(wave/'PROCESS.json'))
            if child.poll() is not None:break
            time.sleep(.1)
        return dict(status='start_not_confirmed',pid=child.pid)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['start','supervise','drain','status']);p.add_argument('--wave',type=Path,required=True);a=p.parse_args()
    w=a.wave.resolve()
    if not w.is_relative_to(b.HERE/'cpu_waves'):raise ValueError('fixed B CPU wave root required')
    if a.command=='start':print(json.dumps(start(w)))
    elif a.command=='supervise':supervise(w)
    elif a.command=='drain':drain(w)
    else:
        print(json.dumps({f.name:b.read(f) for f in w.glob('*.json') if f.name in ('PROCESS.json','HEARTBEAT.json','WAVE_RESULT.json','DRAIN_COMPLETE.json','BLOCKED.json')},indent=2))
