"""One detached A whole-wave lifecycle; bounded terminal notification observer."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
import d24_common as d
from batch import group_members,stop_owned

def proc_table():
    rows={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            f=(p/'stat').read_text().rsplit(')',1)[1].split()
            if f[0]!='Z':rows[int(p.name)]=dict(d.identity(int(p.name)),ppid=int(f[1]))
        except (OSError,ValueError,IndexError):pass
    return rows

def holder_snapshot():
    status=d.load('/tmp/gpu_occupancy_guard/status.json');table=proc_table()
    roots={int(v['manager_pid']) for v in status.get('gpus',{}).values() if v.get('manager_pid')}
    descendants=set(roots)
    for _ in range(32):
        new={pid for pid,r in table.items() if r['ppid'] in descendants}-descendants
        if not new:break
        descendants|=new
    return dict(utc=d.utc(),owned_processes=[table[p] for p in sorted(descendants) if p in table],original_guard_status=status)

def serve():
    d.authorize(admission=True);local=Path('/tmp/corrector_A_libero_full_native_v1_r4');local.mkdir(exist_ok=True)
    lock=(local/'service.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (d.R/'CLAIM.json').exists():return
    budget=d.load(d.R/'NODE_BUDGET_SCOPE.json')
    if budget['A_attempt_upper_bound_after_this_stage']>18000 or budget['A_small_update_upper_bound_after_this_stage']>200000:
        raise RuntimeError('Cumulative A cap, not a reset')
    d.exclusive(d.R/'CLAIM.json',dict(utc=d.utc(),started_unix=time.time(),task_id=d.TASK,process=d.identity(),authorization_sha256=d.AUTH_SHA))
    d.atomic(d.R/'DAEMON_READY.json',dict(utc=d.utc(),status='READY',process=d.identity(),session=os.getsid(0),independent_of_terminal=True,
        model_ready=False,scientific_execution_proven=False,background_completion_observer='existing fixed A thread notify.py'))
    info={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        fields=line.split()
        if fields[0] in ['MemAvailable:','MemTotal:']:info[fields[0][:-1]]=int(fields[1])*1024
    disk=os.statvfs(d.R);available=disk.f_bavail*disk.f_frsize
    if info.get('MemAvailable',0)<(8*64+16)*1024**3 or available<20*1024**3:raise RuntimeError('Ordinary eight-worker RAM/storage capacity insufficient')
    d.atomic(d.R/'RESOURCE_ADMISSION.json',dict(utc=d.utc(),memory=info,available_bytes=available,
        reservation_estimate_not_measured_peak_RAM_bytes=(8*64+16)*1024**3,CPU_affinity=len(os.sched_getaffinity(0)),
        quota_unknown=True,no_standalone_GPU_probe=True))
    d.exclusive(d.R/'HOLDER_HANDOFF_REQUEST.json',holder_snapshot())
    argv=['bash',str(d.ROOT/'gpu_occupancy_lifecycle.sh'),'run','--','/usr/bin/python','-B',str(d.W/'batch.py'),'--batch',str(d.W/'BATCH.json')]
    d.exclusive(d.R/'COMMAND.json',dict(argv=argv,utc=d.utc(),attempt=1,replay=False))
    proc=None;error=None;exit_code=None
    from notify import pump
    try:
        with (d.R/'formal.log').open('a') as log:
            proc=subprocess.Popen(argv,cwd=d.W,env=dict(os.environ,CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS='300',PYTHONDONTWRITEBYTECODE='1'),
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        d.atomic(d.R/'LIFECYCLE_PROCESS.json',d.identity(proc.pid))
        def stop(*_):
            if proc.poll() is None:proc.send_signal(signal.SIGTERM)
        for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,stop)
        while proc.poll() is None:
            if time.time()-d.load(d.R.parent/'CLAIM.json')['started_unix']>8*3600:proc.send_signal(signal.SIGTERM)
            ready=[];started=[]
            for slot in range(8):
                worker=d.R/'workers'/str(slot)
                if (worker/'SERVER_READY.json').exists():ready.append(slot)
                if (worker/'status.json').exists():started.append(dict(slot=slot,status=d.load(worker/'status.json')))
            d.atomic(d.R/'HEARTBEAT.json',dict(utc=d.utc(),process=d.identity(),model_ready_workers=ready,workers=started,all_holder_computation_reserved=True))
            if len(ready)==8 and any(x['status'].get('physical_attempts',0)>0 for x in started) and not (d.R/'STABLE_HANDOFF.json').exists():
                d.exclusive(d.R/'STABLE_HANDOFF.json',dict(utc=d.utc(),actual_models_ready=8,worker_status=started,
                    holder_exit_ack=str(d.R/'HOLDER_EXIT_ACK.json'),automatic_sequence='40 old/fresh dev -> truthful label gate -> fixed32000 updates ->400 Full-Post ->400 Full-Velocity',
                    termination_observer_registered=True,original_thread='01a0b91f-7443-71b1-915d-6cdb6d6a1a13'))
            pump();time.sleep(3)
        exit_code=proc.wait()
    except BaseException as e:
        error=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
        if proc is not None:stop_owned(proc)
    finally:
        from summarize import publish
        result=publish();drain=d.load(d.R/'DRAIN.json') if (d.R/'DRAIN.json').exists() else {}
        if proc is not None and group_members(proc.pid):stop_owned(proc)
        restored=None
        for _ in range(12):
            state=d.load('/tmp/gpu_occupancy_guard/status.json');g=state.get('gpus',{})
            if len(g)==8 and all(v.get('state')!='reserved' for v in g.values()):restored=state;break
            time.sleep(2)
        result.update(outer_exit_code=exit_code,supervisor_error=error,cleanup=drain,
            guard_restoration_observed=restored is not None,guard_snapshot=restored,completed_at_utc=d.utc())
        d.atomic(d.R/'RESULT.json',result)
        d.atomic(d.C/'receipts/A'/('A_D24_LIBERO_FULL_NATIVE_V1_RESULT_r8.json'),result)
        d.event('chain_terminal',result=str(d.R/'RESULT.json'),status=result['status'])
        # Finite notification retries never rerun science, including after failure.
        until=time.monotonic()+1900
        while time.monotonic()<until:
            pump()
            if (d.R/'notifications/chain_terminal/HANDLER_ACK.json').exists():break
            time.sleep(10)

def start():
    d.authorize(admission=True)
    if (d.R/'CLAIM.json').exists():return dict(status='existing_claim_no_restart',claim=d.load(d.R/'CLAIM.json'))
    if (d.R/'SPAWN.json').exists() and d.alive(d.load(d.R/'SPAWN.json')['process']):return d.load(d.R/'SPAWN.json')
    with (d.R/'supervisor.log').open('a') as log:
        proc=subprocess.Popen(['/usr/bin/python','-B',str(d.W/'service.py'),'serve'],cwd=d.W,
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    value=dict(utc=d.utc(),status='spawned_not_model_ready',process=d.identity(proc.pid),output=str(d.R))
    d.atomic(d.R/'SPAWN.json',value);return value

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['start','serve']);a=p.parse_args()
    try:
        value=globals()[a.command]()
        if value is not None:print(json.dumps(value,indent=2))
    except BaseException as exc:
        d.atomic(d.R/'STARTUP_ERROR.json',dict(utc=d.utc(),phase=a.command,error=repr(exc),traceback=traceback.format_exc(),
            scientific_command_exists=(d.R/'COMMAND.json').exists(),no_automatic_retry=True))
        raise
