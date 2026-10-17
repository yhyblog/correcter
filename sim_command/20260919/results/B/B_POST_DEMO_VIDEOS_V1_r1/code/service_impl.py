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
from paths import ROOT,WORKSPACE,AUTH_SHA,CAMPAIGN,CONFIG
from qio import optional_snapshot,read,new_json,atomic_json,process_identity,same_process,utc,ref,append
from admission import authority,resource_admission,before_cutoff
from reservation import receive_existing_fd
from process_family import drain_group
from wave_timing import observe_restoration
def pump(): return None


def descendant(row,pid):
    seen=set()
    while row and row['pid'] not in seen:
        if row['pid']==pid:return True
        seen.add(row['pid']);row=process_identity(row['ppid'])
    return False


def heartbeat(status,**extra):
    try:
        atomic_json(ROOT/'HEARTBEAT.json',dict(status=status,utc=utc(),process=process_identity(),authorization_sha256=AUTH_SHA,**extra))
        atomic_json(CAMPAIGN/CONFIG['running_receipt'],dict(task_id=CONFIG['task_id'],status=status,at_utc=utc(),package=str(ROOT),process=process_identity(),phases=['qualitative_paired_video_capture'],planned_current_attempts=CONFIG['planned_current'],progress=extra.get('progress'),whole_wave_all_holders_off=True,A_waits_for_B=False))
    except OSError as error:print('TELEMETRY_PENDING',repr(error),file=sys.stderr,flush=True)


def monitor_sample(chain,count,*,active):
    """Control-plane query only while released formal work is active; separately billed."""
    if not active:return
    cap=131072
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

def register_B_event(own):
    identity=dict(hostname=own['host'],boot_id=own['boot_id'],pid=own['pid'],start_ticks=own['start_ticks'],session_id=os.getsid(0))
    claim=ROOT/'CLAIM.json'
    new_json(claim,dict(task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],config=ref(ROOT/'config/CONFIG.json'),sources=ref(ROOT/'SOURCE_INDEX.json'),method_frozen=ref(ROOT/'METHOD_FROZEN.json'),absolute_wall_deadline_unix=read(ROOT/'config/CONFIG.json')['absolute_wall_deadline_unix'],process=identity,authorization_sha256=AUTH_SHA,utc=utc()))
    new_json(ROOT/'PROCESS.json',identity)
    if CONFIG.get('completion_via_queue'):
        new_json(ROOT/'FORMAL_HANDOFF_TO_QUEUE.json',dict(formal_process=identity,terminal_observer=ref(ROOT/'WAKEUP_REGISTRATION.json'),at_utc=utc()))
        return
    manifest=dict(job_id=CONFIG['run_id'],task_id=CONFIG['task_id'],revision=1,run_id=CONFIG['run_id'],attempt=1,
        claim_identity=ref(claim),process_identity=identity,result_path=str(ROOT/'RESULT.json'),error_summary_path=str(ROOT/'daemon.stderr.log'))
    new_json(ROOT/'WAKEUP_REGISTRATION.json',manifest)
    __import__('support').register_manifest(ROOT/'WAKEUP_REGISTRATION.json')


def serve():
    local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
    singleton=(local/'daemon.lock').open('a')
    try:fcntl.flock(singleton,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    authority();own=process_identity();register_B_event(own)
    from support import acquire_wave
    acquire_wave(ROOT)
    new_json(ROOT/'deployments'/(str(own['start_ticks'])+'.json'),dict(process=own,utc=utc()))
    atomic_json(ROOT/'DAEMON_READY.json',dict(status='READY',process=own,host=socket.gethostname(),utc=utc(),
        authorization_sha256=AUTH_SHA,stdin='DEVNULL',session=os.getsid(0),independent_of_Codex_window=True,
        worker_target=CONFIG.get('target_workers',8),workers_per_gpu=CONFIG.get('workers_per_gpu',1),code=ref(ROOT/'CODE_MANIFEST.json'),host_reboot_requires_restart=True))
    if (ROOT/'CHAIN_COMMAND.json').exists():
        heartbeat('existing_command_not_replayed');return 3
    resource=resource_admission();new_json(ROOT/'RESOURCE_ADMISSION.json',resource)
    if not before_cutoff():heartbeat('cutoff_no_new_admission');return 0
    chain=ROOT/'chain';chain.mkdir(exist_ok=False)
    status=read('/tmp/gpu_occupancy_guard/status.json')
    holders=[process_identity(r['manager_pid']) for r in status.get('gpus',{}).values() if r.get('manager_pid')]
    if any(x is None for x in holders):raise RuntimeError('holder identity lost before handoff')
    address='/tmp/corrector_d24_fd_'+uuid.uuid4().hex+'.sock'
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(address);os.chmod(address,0o600);server.listen(1)
    from qoccupancy import session_members
    descendants=[r for own_holder in holders for r in session_members(own_holder)]
    new_json(chain/'REQUEST.json',dict(socket=address,request_unix=time.time(),holder_processes=holders,
        original_status=status,holder_descendants=descendants,initial_all8off=True,same_original_lock=True,holder_policy='all8off_entire_formal_wave'))
    argv=[str(WORKSPACE/'gpu_occupancy_lifecycle.sh'),'run','--','/usr/bin/python','-B',str(ROOT/'code/manager.py'),'--chain',str(chain)]
    new_json(ROOT/'CHAIN_COMMAND.json',dict(argv=argv,utc=utc(),opportunity_consumed=True,automatic_retry=False))
    fd=None;peer=None;proc=None;cleanup=None;fatal=None;lastbeat=0;lastmonitor=0;monitor_count=0
    try:
        with (chain/'stdout.log').open('xb') as so,(chain/'stderr.log').open('xb') as se:
            proc=subprocess.Popen(argv,cwd=ROOT,env=dict(os.environ,CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS='300',PYTHONDONTWRITEBYTECODE='1'),
                stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
        new_json(chain/'LIFECYCLE_STARTED.json',dict(process=process_identity(proc.pid),utc=utc()))
        def stop(*_):
            if proc.poll() is None:proc.send_signal(signal.SIGTERM)
        for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
        wall_deadline=time.monotonic()+max(0,read(ROOT/"config/CONFIG.json")["absolute_wall_deadline_unix"]-time.time())
        while proc.poll() is None:
            if wall_deadline is not None and time.monotonic()>=wall_deadline:
                fatal=dict(type="WallTimeout",message="two-hour demo formal-family wall cap");proc.send_signal(signal.SIGTERM);wall_deadline=None
            if fd is None and select.select([server],[],[],0)[0]:
                fd,peer=receive_existing_fd(server,'/tmp/gpu_occupancy_guard/formal.lock',lambda row:descendant(row,proc.pid))
                new_json(chain/'SAME_LOCK_FD_RETAINED.json',dict(peer=peer,utc=utc(),second_lock_acquisition=False))
            if time.monotonic()-lastbeat>=5:
                progress=optional_snapshot(chain/'HEARTBEAT.json')
                heartbeat('formal_chain' if peer else 'handoff',progress=progress,holders='all8off_entire_formal_wave; zero auxiliary holders')
                lastbeat=time.monotonic();pump()
            if peer and time.monotonic()-lastmonitor>=15:
                monitor_count=monitor_sample(chain,monitor_count,active=True);lastmonitor=time.monotonic()
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
        new_json(chain/'AUXILIARY_EXIT_BEFORE_RELEASE.json',dict(records=[],utc=utc(),utilization_query_attempts=monitor_count,auxiliary_holders_enabled=False))
        if fd is not None:
            if not cleanup or cleanup.get('status')!='all_formal_group_members_exited':
                heartbeat('blocked_retaining_reservation',reason='owned group exit not established')
                while True:time.sleep(5)
            os.close(fd)
        restoration=observe_restoration(time.time(),120)
        new_json(chain/'RESTORATION.json',restoration)
        new_json(chain/'CHAIN_RESULT.json',dict(fatal=fatal,cleanup=cleanup,restoration=restoration,utc=utc(),
            raw_lifecycle_exit=proc.returncode if proc else None))
    publication_error=None
    try:
        base=read(ROOT/'config/BASE.json')
        published=subprocess.run([base['python'],'-B',str(ROOT/'code/publish.py')],cwd=ROOT,
            env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'),capture_output=True,text=True,timeout=600)
        atomic_json(ROOT/'PUBLICATION_PROCESS.json',dict(exit_code=published.returncode,stdout=published.stdout[-6000:],stderr=published.stderr[-6000:],utc=utc()))
        if published.returncode:raise RuntimeError('terminal publication failed')
    except BaseException as error:
        publication_error=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    final=read(ROOT/'FINAL_SUMMARY.json') if (ROOT/'FINAL_SUMMARY.json').exists() else {}
    complete=proc is not None and proc.returncode==0 and fatal is None and publication_error is None and final.get('status')=='complete'
    status='complete' if complete else 'partial' if final.get('recording_attempts',0) else 'failed'
    atomic_json(ROOT/'RESULT.json',dict(status=status,exit_code=0 if complete else 3,task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],
        fatal=fatal,publication_error=publication_error,publication_completed=publication_error is None,
        all_owned_descendants_exited=bool(cleanup and cleanup.get('status') in ('all_formal_group_members_exited','no_formal_entry')),
        occupancy_handoff_complete=restoration.get('status')=='occupancy_resolved',
        final_summary=str(ROOT/'FINAL_SUMMARY.json'),receipt=str(CAMPAIGN/CONFIG['result_receipt']),at_utc=utc()))
    heartbeat('complete' if complete else 'terminal_partial_or_failed',restoration=restoration)
    return 0 if complete else 3


def start():
    authority()
    ready=ROOT/'DAEMON_READY.json'
    if ready.exists() and same_process(read(ready)['process']):print('ALREADY_RUNNING',read(ready)['process']);return 0
    if (ROOT/'CLAIM.json').exists():print('EXISTING_CLAIM_NO_RESTART',read(ROOT/'CLAIM.json'));return 3
    if (ROOT/'CHAIN_COMMAND.json').exists():raise RuntimeError('previous command exists; reconcile, never implicitly rerun')
    with (ROOT/'daemon.stdout.log').open('ab') as so,(ROOT/'daemon.stderr.log').open('ab') as se:
        proc=subprocess.Popen(['/usr/bin/python','-B',str(ROOT/'code/service.py'),'serve'],cwd=ROOT,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
    print('SPAWNED_NOT_YET_READY',proc.pid)
    return 0


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);a=p.parse_args()
    sys.exit(start() if a.action=='start' else serve())
