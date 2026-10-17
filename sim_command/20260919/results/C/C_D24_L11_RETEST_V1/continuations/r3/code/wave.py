"""Detached C chain, retained original lock, terminal publication and wakeup."""
import argparse
import fcntl
import os
import select
import signal
import socket
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path
import paths
from paths import ROOT, WORKSPACE, CAMPAIGN, AUTH_SHA
from qio import read, new_json, atomic_json, process_identity, same_process, utc, ref, append
from admission import authority, resource_admission, before_cutoff
from reservation import receive_existing_fd
from process_family import drain_group
from wave_timing import observe_restoration
from qoccupancy import session_members

TASK='C_D24_L11_RETEST_V1'
JOB='D24_C_L11_RETEST_r3'
W=CAMPAIGN/'work/C/C_TASK_DISCOVERY_SERVICE_V1_r1'

def descendant(row,pid):
    seen=set()
    while row and row['pid'] not in seen:
        if row['pid']==pid:return True
        seen.add(row['pid']);row=process_identity(row['ppid'])
    return False

def notify_identity(row):
    return dict(hostname=row['host'],boot_id=row['boot_id'],pid=row['pid'],
                start_ticks=row['start_ticks'],session_id=os.getsid(row['pid']))

def monitor_sample(chain):
    begin=time.monotonic()
    try:
        result=subprocess.run(['nvidia-smi','--query-gpu=index,uuid,utilization.gpu,memory.used,memory.free',
            '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=15)
        if result.returncode:raise RuntimeError(result.stderr)
        rows=[]
        for line in result.stdout.splitlines():
            f=[x.strip() for x in line.split(',')]
            rows.append(dict(index=f[0],uuid=f[1],utilization_gpu_percent=f[2],used_MiB=f[3],free_MiB=f[4]))
        append(chain/'UTILIZATION.jsonl',dict(utc=utc(),GPUs=rows,seconds=time.monotonic()-begin,
            control_plane=True,scientific_budget=False),32*1024**2)
        from qmetrics import accumulate
        p=chain/'UTILIZATION_SUMMARY.json'
        atomic_json(p,accumulate(read(p) if p.exists() else {},rows,time.time()))
    except Exception as e:
        append(chain/'UTILIZATION_ERRORS.jsonl',dict(utc=utc(),error=str(e)))

def evaluation_handoff(chain):
    p=ROOT/'EVALUATION_HANDOFF.json'
    if p.exists():return
    heart=read(chain/'HEARTBEAT.json') if (chain/'HEARTBEAT.json').exists() else {}
    if list(ROOT.glob('PAUSE_ADMISSIONS_*.json')):return
    if heart.get('loaded_model_workers',0)!=24 or heart.get('peak_active_rollout_contexts',0)<192:return
    paths=list((ROOT/'evaluation').glob('*/*/RESULT.json'))+list((ROOT/'pi_evaluation').glob('*/*/RESULT.json'))
    for episode in paths:
        row=read(episode)
        if row.get('status')=='complete':
            new_json(p,dict(utc=utc(),status='evaluating',resident_model_workers=24,contexts_per_worker=8,peak_live_contexts=heart['peak_active_rollout_contexts'],first_terminal=ref(episode),holder_exit_ACK=str(chain/'HOLDER_EXIT_ACK.json'),selection='user fixed L11/fit9101',old_sources_replayed=0,notification_registered=(ROOT/'WAKEUP_REGISTRATION.json').exists()))
            break

def run_wave(stage):
    own=process_identity()
    chain=ROOT/'chains'/stage;chain.mkdir(parents=True,exist_ok=False)
    status=read('/tmp/gpu_occupancy_guard/status.json')
    holders=[process_identity(r['manager_pid']) for r in status.get('gpus',{}).values() if r.get('manager_pid')]
    if len(holders)!=8 or any(x is None for x in holders):raise RuntimeError('Eight holder identities required before handoff')
    descendants=[r for holder in holders for r in session_members(holder)]
    address='/tmp/corrector_C_PI05_fd_'+uuid.uuid4().hex+'.sock'
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(address);os.chmod(address,0o600);server.listen(1)
    new_json(chain/'REQUEST.json',dict(socket=address,request_unix=time.time(),holder_processes=holders,
        holder_descendants=descendants,original_status=status,all_holders_off_whole_wave=True))
    argv=[str(WORKSPACE/'gpu_occupancy_lifecycle.sh'),'run','--','/usr/bin/python','-B',str(ROOT/'code/manager.py'),'--chain',str(chain),'--stage',stage]
    new_json(chain/'COMMAND.json',dict(argv=argv,utc=utc(),automatic_retry=False))
    fd=None;peer=None;proc=None;cleanup=None;fatal=None;lastbeat=0;lastmonitor=0;started=time.monotonic();timed_out=False;previous_handlers={}
    try:
        with (chain/'stdout.log').open('xb') as so,(chain/'stderr.log').open('xb') as se:
            proc=subprocess.Popen(argv,cwd=ROOT,env=dict(os.environ,CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS='300',PYTHONDONTWRITEBYTECODE='1'),
                stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
        new_json(chain/'LIFECYCLE_STARTED.json',dict(process=process_identity(proc.pid),utc=utc()))
        def stop(*_):
            if proc.poll() is None:proc.send_signal(signal.SIGTERM)
        previous_handlers={sig:signal.signal(sig,stop) for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP)}
        while proc.poll() is None:
            if fd is None and select.select([server],[],[],0)[0]:
                fd,peer=receive_existing_fd(server,'/tmp/gpu_occupancy_guard/formal.lock',lambda row:descendant(row,proc.pid))
                new_json(chain/'SAME_LOCK_FD_RETAINED.json',dict(peer=peer,utc=utc(),second_lock_acquisition=False))
            if (time.monotonic()-started>=12*3600) and not timed_out:
                timed_out=True;stop()
            if time.monotonic()-lastbeat>=10:
                progress=read(chain/'HEARTBEAT.json') if (chain/'HEARTBEAT.json').exists() else None
                atomic_json(ROOT/'HEARTBEAT.json',dict(utc=utc(),process=notify_identity(own),status=stage if peer else 'handoff',progress=progress))
                evaluation_handoff(chain) if stage=='evaluate' else None
                if (ROOT/'EVALUATION_HANDOFF.json').exists() and not (ROOT/'STABLE_HANDOFF.json').exists():
                    notification=read(ROOT/'NOTIFICATION_REGISTRATION_RESULT.json')
                    if notification.get('exit_code')==0:new_json(ROOT/'STABLE_HANDOFF.json',dict(utc=utc(),status='stable_background',progress=ref(ROOT/'EVALUATION_HANDOFF.json'),notification=ref(ROOT/'WAKEUP_REGISTRATION.json'),finite=True,LLM_wait_required=False,original_thread='01a0c793-10d2-7791-a250-fd65d88e1ccb',whole_wave_holders_off=True))
                lastbeat=time.monotonic()
            if peer and time.monotonic()-lastmonitor>=15:
                monitor_sample(chain);lastmonitor=time.monotonic()
            time.sleep(.5)
        proc.wait()
        cleanup=drain_group(peer['pgid'],peer['pid']) if peer else dict(status='no_formal_entry')
    except BaseException as e:
        fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
        if proc and proc.poll() is None:proc.send_signal(signal.SIGTERM)
        if peer:cleanup=drain_group(peer['pgid'],peer['pid'])
        if proc:proc.wait()
    finally:
        server.close()
        try:Path(address).unlink()
        except FileNotFoundError:pass
        new_json(chain/'BEFORE_RESERVATION_RELEASE.json',dict(utc=utc(),cleanup=cleanup,fatal=fatal,
            raw_lifecycle_exit=proc.returncode if proc else None,auxiliary_holder_launches=0))
        if fd is not None:
            if not cleanup or cleanup.get('status')!='all_formal_group_members_exited':
                raise RuntimeError('Cannot release retained reservation before owned family exit')
            os.close(fd)
    restoration=observe_restoration(time.time(),300)
    new_json(chain/'RESTORATION.json',restoration)
    for sig,handler in previous_handlers.items():signal.signal(sig,handler)
    outcome=dict(stage=stage,exit_code=proc.returncode if proc else None,fatal=fatal,timeout=timed_out,cleanup=cleanup,restoration=restoration,utc=utc())
    new_json(chain/'RESULT.json',outcome)
    return outcome
