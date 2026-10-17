"""Detached supervisor around exactly one original all-GPU lifecycle chain."""
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
from paths import ROOT,WORKSPACE,AUTH_SHA
from qio import read,new_json,atomic_json,process_identity,same_process,utc,ref
from admission import authority,resource_admission,before_cutoff
from reservation import receive_existing_fd
from process_family import drain_group
from wave_timing import observe_restoration
from notify import pump


def descendant(row,pid):
    seen=set()
    while row and row['pid'] not in seen:
        if row['pid']==pid:return True
        seen.add(row['pid']);row=process_identity(row['ppid'])
    return False


def heartbeat(status,**extra):
    atomic_json(ROOT/'HEARTBEAT.json',dict(status=status,utc=utc(),process=process_identity(),authorization_sha256=AUTH_SHA,**extra))


def serve():
    local=Path('/tmp/corrector_D24_A_pilot');local.mkdir(exist_ok=True)
    singleton=(local/'daemon.lock').open('a')
    try:fcntl.flock(singleton,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    authority();own=process_identity()
    new_json(ROOT/'deployments'/(str(own['start_ticks'])+'.json'),dict(process=own,utc=utc()))
    atomic_json(ROOT/'DAEMON_READY.json',dict(status='READY',process=own,host=socket.gethostname(),utc=utc(),
        authorization_sha256=AUTH_SHA,stdin='DEVNULL',session=os.getsid(0),independent_of_Codex_window=True,
        worker_target=8,code=ref(ROOT/'CODE_MANIFEST.json'),host_reboot_requires_restart=True))
    if (ROOT/'CHAIN_COMMAND.json').exists():
        heartbeat('existing_command_not_replayed');return 3
    resource=resource_admission();new_json(ROOT/'RESOURCE_ADMISSION.json',resource)
    if not before_cutoff():heartbeat('cutoff_no_new_admission');return 0
    baseline=WORKSPACE/'Corrector/sim_command/20260919/deadline_20260924/A'
    if (baseline/'CHAIN_COMMAND.json').exists():
        while not (baseline/'chain/CHAIN_RESULT.json').exists():
            heartbeat('waiting_for_existing_N_chain_full_exit',baseline=str(baseline),running_N_interrupted=False)
            time.sleep(5)
        ended=read(baseline/'chain/CHAIN_RESULT.json')
        if ended.get('cleanup',{}).get('status')!='all_formal_group_members_exited':
            raise RuntimeError('baseline group not established exited')
        new_json(ROOT/'BASELINE_HANDOFF.json',dict(result=str(baseline/'chain/CHAIN_RESULT.json'),utc=utc(),running_N_interrupted=False))
    chain=ROOT/'chain';chain.mkdir(exist_ok=False)
    status=read('/tmp/gpu_occupancy_guard/status.json')
    holders=[process_identity(r['manager_pid']) for r in status.get('gpus',{}).values() if r.get('manager_pid')]
    if any(x is None for x in holders):raise RuntimeError('holder identity lost before handoff')
    address='/tmp/corrector_d24_fd_'+uuid.uuid4().hex+'.sock'
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(address);os.chmod(address,0o600);server.listen(1)
    new_json(chain/'REQUEST.json',dict(socket=address,request_unix=time.time(),holder_processes=holders,
        original_status=status,all8off=True,same_original_lock=True))
    argv=[str(WORKSPACE/'gpu_occupancy_lifecycle.sh'),'run','--','/usr/bin/python','-B',str(ROOT/'code/manager.py'),'--chain',str(chain)]
    new_json(ROOT/'CHAIN_COMMAND.json',dict(argv=argv,utc=utc(),opportunity_consumed=True,automatic_retry=False))
    fd=None;peer=None;proc=None;cleanup=None;fatal=None;lastbeat=0
    try:
        with (chain/'stdout.log').open('xb') as so,(chain/'stderr.log').open('xb') as se:
            proc=subprocess.Popen(argv,cwd=ROOT,env=dict(os.environ,CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS='300',PYTHONDONTWRITEBYTECODE='1'),
                stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
        new_json(chain/'LIFECYCLE_STARTED.json',dict(process=process_identity(proc.pid),utc=utc()))
        def stop(*_):
            if proc.poll() is None:proc.send_signal(signal.SIGTERM)
        for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
        while proc.poll() is None:
            if fd is None and select.select([server],[],[],0)[0]:
                fd,peer=receive_existing_fd(server,'/tmp/gpu_occupancy_guard/formal.lock',lambda row:descendant(row,proc.pid))
                new_json(chain/'SAME_LOCK_FD_RETAINED.json',dict(peer=peer,utc=utc(),second_lock_acquisition=False))
            if time.monotonic()-lastbeat>=5:
                progress=read(chain/'HEARTBEAT.json') if (chain/'HEARTBEAT.json').exists() else None
                heartbeat('formal_chain' if peer else 'handoff',progress=progress,holders='all8off_until_whole_chain_exit_and_publication')
                lastbeat=time.monotonic();pump()
            time.sleep(.5)
        code=proc.wait()
        cleanup=drain_group(peer['pgid'],peer['pid']) if peer else dict(status='no_formal_entry')
        new_json(chain/'BEFORE_RESERVATION_RELEASE.json',dict(exit_code=code,cleanup=cleanup,utc=utc(),
            manager_result=read(chain/'MANAGER_EXIT.json') if (chain/'MANAGER_EXIT.json').exists() else None))
    except BaseException as e:
        fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
        if proc and proc.poll() is None:proc.send_signal(signal.SIGTERM);proc.wait()
        if peer:cleanup=drain_group(peer['pgid'],peer['pid'])
        new_json(chain/'SUPERVISOR_FAILURE.json',dict(fatal=fatal,cleanup=cleanup,utc=utc()))
    finally:
        server.close()
        if fd is not None:
            if not cleanup or cleanup.get('status')!='all_formal_group_members_exited':
                heartbeat('blocked_retaining_reservation',reason='owned group exit not established')
                while True:time.sleep(5)
            os.close(fd)
        restoration=observe_restoration(time.time(),120)
        new_json(chain/'RESTORATION.json',restoration)
        new_json(chain/'CHAIN_RESULT.json',dict(fatal=fatal,cleanup=cleanup,restoration=restoration,utc=utc(),
            raw_lifecycle_exit=proc.returncode if proc else None))
    event=ROOT/'outbox/chain_terminal.json'
    if not event.exists():new_json(event,dict(event_id='D24_A_pilot_chain_terminal_r2',kind='chain_terminal',synthetic=False,result=str(chain/'CHAIN_RESULT.json'),utc=utc()))
    heartbeat('idle_after_full_exit_and_publication',restoration=restoration)
    # Keep durable completion transport alive after useful work ends. No GPU/holder polling.
    while True:pump();time.sleep(5)


def start():
    authority()
    ready=ROOT/'DAEMON_READY.json'
    if ready.exists() and same_process(read(ready)['process']):print('ALREADY_RUNNING',read(ready)['process']);return 0
    if (ROOT/'CHAIN_COMMAND.json').exists():raise RuntimeError('previous command exists; reconcile, never implicitly rerun')
    with (ROOT/'daemon.stdout.log').open('ab') as so,(ROOT/'daemon.stderr.log').open('ab') as se:
        proc=subprocess.Popen(['/usr/bin/python','-B',str(ROOT/'code/service.py'),'serve'],cwd=ROOT,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
    print('SPAWNED_NOT_YET_READY',proc.pid)
    return 0


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);a=p.parse_args()
    sys.exit(start() if a.action=='start' else serve())
