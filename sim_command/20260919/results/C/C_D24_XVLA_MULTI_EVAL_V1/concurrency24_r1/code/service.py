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
from paths import RUNROOT as ROOT, ROOT as DATA, WORKSPACE, CAMPAIGN, AUTH_SHA
from qio import read, new_json, atomic_json, process_identity, same_process, utc, ref, append
from admission import authority, resource_admission, before_cutoff
from reservation import receive_existing_fd
from process_family import drain_group
from wave_timing import observe_restoration
from qoccupancy import session_members

TASK='C_D24_XVLA_MULTI_EVAL_V1'
JOB='D24_C_XVLA_MULTI_c24_r1'
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

def handoff(chain):
    if (ROOT/'STABLE_HANDOFF.json').exists():return
    workers=ROOT/'stages/evaluate/workers'
    ready=list(workers.glob('*/MODEL_READY.json'));encoders=list(workers.glob('*/encoder/READY.json'))
    if len(ready)!=24 or len(encoders)!=24:return
    for p in sorted(workers.glob('*/PROGRESS.json')):
        progress=read(p)
        if progress.get('status')!='complete':continue
        source=DATA/'evaluation'/progress['method']/progress['source_id']/'RESULT.json';row=read(source)
        if row['status']=='complete':
            new_json(ROOT/'STABLE_HANDOFF.json',dict(utc=utc(),task_id=TASK,status='evaluating_multi_24workers',
                native_models_ready=24,external_encoders_ready=24,GPUs=8,workers_per_GPU=3,
                first_new_formal_terminal=str(source),first_source=row['source_id'],first_method=row['method'],
                first_steps=row['steps'],first_interventions=row['interventions'],actual_physics=row.get('physics'),
                formal_holder_exit_ACK=str(chain/'HOLDER_EXIT_ACK.json'),wakeup_registration=str(ROOT/'WAKEUP_REGISTRATION.json'),
                executor_thread_id='01a0c793-10d2-7791-a250-fd65d88e1ccb',shared_scientific_root=str(DATA),
                same1500_first_evaluations=True,new_training_updates=0,new_collection_attempts=0,old_completed_replay=0,
                holder_policy='all off entire formal family',stop_LLM_wait=True))
            from publications import running_receipt
            running_receipt(True)
            break

def serve():
    local=Path('/tmp/corrector_C_XVLA_MULTI_c24_r1');local.mkdir(exist_ok=True)
    with (local/'daemon.lock').open('a') as singleton:
        fcntl.flock(singleton,fcntl.LOCK_EX|fcntl.LOCK_NB)
        authority();resource=resource_admission()
        if read(ROOT/'CPU_CHECK.json')['status']!='passed':raise RuntimeError('C private CPU checks not passed')
        if not before_cutoff():raise RuntimeError('New experiment admission closed')
        own=process_identity();claim=ROOT/'CLAIM.json'
        new_json(claim,dict(task_id=TASK,run_id=JOB,utc=utc(),process=notify_identity(own),
            authorization_sha256=AUTH_SHA,config=ref(ROOT/'config/CONFIG.json'),no_automatic_relaunch=True,
            method_frozen=ref(ROOT/'METHOD_FROZEN.json'),CPU_check=ref(ROOT/'CPU_CHECK.json')))
        new_json(ROOT/'PROCESS.json',notify_identity(own));new_json(ROOT/'RESOURCE_ADMISSION.json',resource)
        registration=dict(job_id=JOB,task_id=TASK,revision=1,run_id=JOB,attempt=1,
            claim_identity=dict(path=str(claim),sha256=ref(claim)['sha256']),process_identity=notify_identity(own),
            result_path=str(ROOT/'RESULT.json'),error_summary_path=str(ROOT/'supervisor.log'))
        new_json(ROOT/'WAKEUP_REGISTRATION.json',registration)
        subprocess.run(['/usr/bin/python','-B',str(W/'wakeup.py'),'register','--manifest',str(ROOT/'WAKEUP_REGISTRATION.json')],check=True)
        from publications import running_receipt
        running_receipt(False)
        from transfer import prepare_and_wait
        prepare_and_wait(own,JOB)
        running_receipt(False)
        chain=ROOT/'chain';chain.mkdir(exist_ok=False)
        status=read('/tmp/gpu_occupancy_guard/status.json')
        holders=[process_identity(r['manager_pid']) for r in status.get('gpus',{}).values() if r.get('manager_pid')]
        if len(holders)!=8 or any(x is None for x in holders):raise RuntimeError('Eight holder identities required before handoff')
        descendants=[r for holder in holders for r in session_members(holder)]
        address='/tmp/corrector_C_XM24_fd_'+uuid.uuid4().hex+'.sock'
        server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(address);os.chmod(address,0o600);server.listen(1)
        new_json(chain/'REQUEST.json',dict(socket=address,request_unix=time.time(),holder_processes=holders,
            holder_descendants=descendants,original_status=status,all_holders_off_whole_wave=True))
        argv=[str(WORKSPACE/'gpu_occupancy_lifecycle.sh'),'run','--','/usr/bin/python','-B',str(ROOT/'code/manager.py'),'--chain',str(chain)]
        new_json(ROOT/'CHAIN_COMMAND.json',dict(argv=argv,utc=utc(),automatic_retry=False))
        fd=None;peer=None;proc=None;cleanup=None;fatal=None;lastbeat=0;lastmonitor=0;started=time.monotonic();timed_out=False
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
                if (time.monotonic()-started>=12*3600 or not before_cutoff()) and not timed_out:
                    timed_out=True;stop()
                if time.monotonic()-lastbeat>=10:
                    progress=read(chain/'HEARTBEAT.json') if (chain/'HEARTBEAT.json').exists() else None
                    atomic_json(ROOT/'HEARTBEAT.json',dict(utc=utc(),process=notify_identity(own),status='formal_chain' if peer else 'handoff',progress=progress))
                    handoff(chain);lastbeat=time.monotonic()
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
        report_rc=None
        try:
            report=subprocess.run([read(ROOT/'config/BASE.json')['python'],'-B',str(ROOT/'code/report.py')],
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2'),
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=300)
            report_rc=report.returncode
            (ROOT/'report.log').write_text(report.stdout)
        except Exception as exc:
            new_json(ROOT/'PUBLICATION_PENDING.json',dict(utc=utc(),error=repr(exc),scientific_replay_allowed=False))
        if report_rc not in (0,None):
            new_json(ROOT/'PUBLICATION_PENDING.json',dict(utc=utc(),exit_code=report_rc,scientific_replay_allowed=False))
        summary=read(DATA/'FINAL_SUMMARY.json') if (DATA/'FINAL_SUMMARY.json').exists() else None
        complete=bool(summary and summary.get('evaluation_valid')==1500 and summary.get('new_training_updates')==0 and report_rc==0 and not fatal
                      and proc and proc.returncode==0 and cleanup and cleanup.get('status')=='all_formal_group_members_exited'
                      and restoration['status']=='occupancy_resolved')
        all_exited=bool(cleanup and cleanup.get('status') in ('all_formal_group_members_exited','no_formal_entry'))
        scientific_exit_clean=bool(proc and proc.returncode==0 and all_exited and not fatal)
        new_json(ROOT/'RESULT.json',dict(task_id=TASK,batch_id=JOB,status='complete' if complete else 'publication_pending' if scientific_exit_clean and report_rc!=0 else 'partial_or_failed',
            utc=utc(),exit_code=proc.returncode if proc else None,fatal=fatal,timeout=timed_out,
            summary_path=str(DATA/'FINAL_SUMMARY.json'),report_exit_code=report_rc,
            all_owned_descendants_exited=all_exited,publication_completed=report_rc==0,
            occupancy_handoff_complete=restoration['status']=='occupancy_resolved',restoration=str(chain/'RESTORATION.json'),
            elapsed_seconds=time.monotonic()-started,new_automatic_retries=0))
        from publications import terminal_receipt
        terminal_receipt()
        atomic_json(ROOT/'HEARTBEAT.json',dict(utc=utc(),status='terminal',result=str(ROOT/'RESULT.json')))
        return 0 if complete else 3

def start():
    authority()
    if (ROOT/'CLAIM.json').exists():
        print('EXISTING_CLAIM_NO_RELAUNCH',ROOT/'CLAIM.json');return 0
    with (ROOT/'supervisor.log').open('ab') as log:
        proc=subprocess.Popen(['/usr/bin/python','-B',str(ROOT/'code/service.py'),'serve'],cwd=ROOT,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    print('SPAWNED',proc.pid);return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);a=p.parse_args()
    try:sys.exit(start() if a.action=='start' else serve())
    except Exception as e:
        if (ROOT/'CLAIM.json').exists() and not (ROOT/'RESULT.json').exists():
            new_json(ROOT/'RESULT.json',dict(task_id=TASK,status='execution_unknown',utc=utc(),error=repr(e),
                traceback=traceback.format_exc(),all_owned_descendants_exited=None,publication_completed=False))
        raise
