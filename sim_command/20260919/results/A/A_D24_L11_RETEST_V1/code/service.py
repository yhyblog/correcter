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
from paths import ROOT,ORIGINAL,WORKSPACE,AUTH_SHA,TASK,EVENT_PREFIX,SELECTION_SHA
from qio import read,new_json,atomic_json,process_identity,same_process,utc,ref,append
from admission import authority,resource_admission,before_cutoff,admissions_allowed
from reservation import receive_existing_fd
from process_family import drain_group
from wave_timing import observe_restoration
from notify import pump
from publication import publish


def descendant(row,pid):
    seen=set()
    while row and row['pid'] not in seen:
        if row['pid']==pid:return True
        seen.add(row['pid']);row=process_identity(row['ppid'])
    return False


def heartbeat(status,**extra):
    atomic_json(ROOT/'HEARTBEAT.json',dict(status=status,utc=utc(),process=process_identity(),authorization_sha256=AUTH_SHA,**extra))


def monitor_sample(chain,count,*,active):
    """Control-plane query only while released formal work is active; separately billed."""
    if not active:return
    cap=3072
    if count>=cap:raise RuntimeError('finite chain utilization query cap')
    started=time.monotonic();query=['nvidia-smi','--query-gpu=index,uuid,utilization.gpu,memory.used,memory.free','--format=csv,noheader,nounits']
    row=dict(event=count+1,utc=utc(),phase='entered',query=query,control_plane=True,science_116_caps=False)
    append(chain/'UTILIZATION.jsonl',row,256*1024**2)
    try:
        result=subprocess.run(query,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=15)
        if result.returncode:raise RuntimeError('NVML monitoring query returned '+str(result.returncode))
        values=[]
        for line in result.stdout.splitlines():
            fields=[x.strip() for x in line.split(',')]
            values.append(dict(index=fields[0],uuid=fields[1],utilization_gpu_percent=fields[2],used_MiB=fields[3],free_MiB=fields[4]))
        append(chain/'UTILIZATION.jsonl',dict(event=count+1,phase='returned',utc=utc(),GPUs=values,seconds=time.monotonic()-started),256*1024**2)
        from qmetrics import accumulate
        summary=chain/'UTILIZATION_SUMMARY.json'
        atomic_json(summary,accumulate(read(summary) if summary.exists() else {},values,time.time()))
    except BaseException as error:
        append(chain/'UTILIZATION.jsonl',dict(event=count+1,phase='raised',utc=utc(),error=str(error),seconds=time.monotonic()-started),256*1024**2)
    return count+1

def serve():
    local=Path('/tmp/corrector_D24_A_L11_retest_v1');local.mkdir(exist_ok=True)
    singleton=(local/'daemon.lock').open('a')
    try:fcntl.flock(singleton,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    authority();own=process_identity()
    from admission import original_exit_verified
    original_exit_verified()
    new_json(ROOT/'deployments'/(str(own['start_ticks'])+'.json'),dict(process=own,utc=utc()))
    atomic_json(ROOT/'DAEMON_READY.json',dict(status='READY',process=own,host=socket.gethostname(),utc=utc(),
        authorization_sha256=AUTH_SHA,stdin='DEVNULL',session=os.getsid(0),independent_of_Codex_window=True,
        worker_target=8,logical_context_target=192,code=ref(ROOT/'CODE_MANIFEST.json'),host_reboot_requires_restart=True))
    if (ROOT/'CHAIN_COMMAND.json').exists():
        heartbeat('existing_command_not_replayed');return 3
    resource=resource_admission();new_json(ROOT/'RESOURCE_ADMISSION.json',resource)
    if not admissions_allowed():heartbeat('current_authority_no_new_admission');return 0
    chain=ROOT/'chain';chain.mkdir(exist_ok=False)
    status=read('/tmp/gpu_occupancy_guard/status.json')
    holders=[process_identity(r['manager_pid']) for r in status.get('gpus',{}).values() if r.get('manager_pid')]
    if any(x is None for x in holders):raise RuntimeError('holder identity lost before handoff')
    address='/tmp/corrector_d24_fd_'+uuid.uuid4().hex+'.sock'
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(address);os.chmod(address,0o600);server.listen(1)
    from qoccupancy import session_members
    descendants=[r for own_holder in holders for r in session_members(own_holder)]
    new_json(chain/'REQUEST.json',dict(socket=address,request_unix=time.time(),holder_processes=holders,
        original_status=status,holder_descendants=descendants,initial_all8off=True,same_original_lock=True,holder_override='all8_off_entire_wave_no_auxiliary'))
    argv=[str(WORKSPACE/'gpu_occupancy_lifecycle.sh'),'run','--','/usr/bin/python','-B',str(ROOT/'code/manager.py'),'--chain',str(chain)]
    timer=ROOT/'RUN_TIME_BUDGET.json'
    new_json(timer,dict(utc=utc(),wall_seconds=43200,absolute_end_unix=min(time.time()+43200,1790175600),admission_cutoff_unix=1790164800,new_independent_stage=True,old_attempts_not_reset=True))
    new_json(ROOT/'CLAIM.json',dict(task_id=TASK,authorization_sha256=AUTH_SHA,process=own,utc=utc(),first_evaluations=2900,reused_evaluations=100,stage_attempt_cap=3200,prior_A_attempts=20496,L11_selection_override_sha256=SELECTION_SHA,cumulative_cap=30200,model_processes=8,contexts_per_GPU=24,no_blind_retry=True))
    new_json(ROOT/'CHAIN_COMMAND.json',dict(task_id=TASK,argv=argv,utc=utc(),opportunity_consumed=True,automatic_retry=False))
    fd=None;peer=None;proc=None;cleanup=None;fatal=None;publication_state=None;lastbeat=0;lastmonitor=0;monitor_count=0;deadline_signal_at=None
    try:
        with (chain/'stdout.log').open('xb') as so,(chain/'stderr.log').open('xb') as se:
            proc=subprocess.Popen(argv,cwd=ROOT,env=dict(os.environ,CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS='300',PYTHONDONTWRITEBYTECODE='1'),
                stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
        new_json(chain/'LIFECYCLE_STARTED.json',dict(process=process_identity(proc.pid),utc=utc()))
        def stop(*_):
            if proc.poll() is None:proc.send_signal(signal.SIGTERM)
        for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
        while proc.poll() is None:
            if time.time()>=read(ROOT/'RUN_TIME_BUDGET.json')['absolute_end_unix']:
                if deadline_signal_at is None:proc.send_signal(signal.SIGTERM);deadline_signal_at=time.monotonic()
                elif time.monotonic()-deadline_signal_at>30:proc.kill()
            if fd is None and select.select([server],[],[],0)[0]:
                fd,peer=receive_existing_fd(server,'/tmp/gpu_occupancy_guard/formal.lock',lambda row:descendant(row,proc.pid))
                new_json(chain/'SAME_LOCK_FD_RETAINED.json',dict(peer=peer,utc=utc(),second_lock_acquisition=False))
            if time.monotonic()-lastbeat>=5:
                progress=read(chain/'HEARTBEAT.json') if (chain/'HEARTBEAT.json').exists() else None
                heartbeat('formal_chain' if peer else 'handoff',progress=progress,holders='all8_off_whole_wave_including_loading_and_tail')
                lastbeat=time.monotonic();pump()
            if peer and time.monotonic()-lastmonitor>=15:
                monitor_count=monitor_sample(chain,monitor_count,active=True);lastmonitor=time.monotonic()
            time.sleep(.5)
        code=proc.wait()
        cleanup=drain_group(peer['pgid'],peer['pid']) if peer else dict(status='no_formal_entry')
        for _ in range(3):
            publication_state=publish(terminal=True,force=True)
            if publication_state['status']=='published' or publication_state['attempts']>=3:break
        new_json(chain/'BEFORE_RESERVATION_RELEASE.json',dict(exit_code=code,cleanup=cleanup,utc=utc(),publication_state=publication_state,
            manager_result=read(chain/'MANAGER_EXIT.json') if (chain/'MANAGER_EXIT.json').exists() else None))
    except BaseException as e:
        fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
        if proc and proc.poll() is None:proc.send_signal(signal.SIGTERM);proc.wait()
        if peer:cleanup=drain_group(peer['pgid'],peer['pid'])
        new_json(chain/'SUPERVISOR_FAILURE.json',dict(fatal=fatal,cleanup=cleanup,utc=utc()))
    finally:
        server.close()
        new_json(chain/'AUXILIARY_EXIT_BEFORE_RELEASE.json',dict(records=[],utc=utc(),auxiliary_holder_launches=0,policy='all8_off_whole_wave',utilization_query_attempts=monitor_count))
        if fd is not None:
            if not cleanup or cleanup.get('status')!='all_formal_group_members_exited':
                heartbeat('blocked_retaining_reservation',reason='owned group exit not established')
                while True:time.sleep(5)
            os.close(fd)
        restoration=observe_restoration(time.time(),120)
        new_json(chain/'RESTORATION.json',restoration)
        new_json(chain/'CHAIN_RESULT.json',dict(fatal=fatal,cleanup=cleanup,restoration=restoration,utc=utc(),
            raw_lifecycle_exit=proc.returncode if proc else None))
    summary=read(ROOT/'FINAL_SUMMARY.json') if (ROOT/'FINAL_SUMMARY.json').exists() else None
    compute=read(ROOT/'COMPUTE_SUMMARY.json') if (ROOT/'COMPUTE_SUMMARY.json').exists() else None
    compute_complete=bool(compute and compute['compute_complete'] and proc and proc.returncode==0)
    publication_complete=bool(publication_state and publication_state['status']=='published')
    complete=compute_complete and publication_complete and fatal is None
    status='complete' if complete else 'compute_complete_publication_pending' if compute_complete and fatal is None else 'partial_or_failed'
    new_json(ROOT/'RESULT.json',dict(task_id=TASK,revision=1,utc=utc(),status=status,compute_complete=compute_complete,
        publication_pending=not publication_complete,raw_lifecycle_exit=proc.returncode if proc else None,fatal=fatal,summary=summary,compute_summary=compute,
        all_owned_descendants_exited=bool(cleanup and cleanup.get('status')=='all_formal_group_members_exited'),
        restoration=restoration,publication_completed=publication_complete,publication_state=publication_state,training_updates=0,original_training_updates=192000,automatic_retry=False))
    from paths import CAMPAIGN
    receipt=CAMPAIGN/'receipts/A'/ (TASK+'_RESULT_r1.json')
    if not receipt.exists():new_json(receipt,dict(task_id=TASK,utc=utc(),status=status,result=ref(ROOT/'RESULT.json'),summary=summary,compute_complete=compute_complete,publication_completed=publication_complete,holder_restoration=restoration,training_updates=0,original_results_preserved=True))
    report=CAMPAIGN/'receipts/A'/ (TASK+'_REPORT.md')
    if not report.exists():report.write_text('L11 / fit9101 new finite A scope. Status: '+status+'\n\nRaw terminal, attempts, result denominators, separate Post/Velocity tables and all-family exit/holder restoration are in '+str(ROOT)+' . Costs come from this task; 100 exact reused L11 units are explicitly marked and overlap the prior ablation selection.\n')
    event=ROOT/'outbox/chain_terminal.json'
    if not event.exists():new_json(event,dict(event_id=EVENT_PREFIX+'_chain_terminal_v1',kind='chain_terminal',synthetic=False,result=str(ROOT/'RESULT.json'),utc=utc()))
    heartbeat('idle_after_full_exit',compute_complete=compute_complete,publication_complete=publication_complete,restoration=restoration)
    # Keep durable completion transport alive after useful work ends. No GPU/holder polling.
    transport_end=time.monotonic()+1810
    while time.monotonic()<transport_end:
        pump();time.sleep(5)
        records=[read(p) for p in (ROOT/'notifications').glob('*/TRANSPORT.json')]
        if records and all(r.get('attempts',0)>=3 for r in records):break


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
