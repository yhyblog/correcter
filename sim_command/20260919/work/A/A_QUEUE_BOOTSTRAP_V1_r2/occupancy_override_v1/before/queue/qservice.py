"""Detached per-node supervisor. Only a release-gated A chain enters lifecycle."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
import inheritance
import fcntl
import json
import os
import select
import signal
import socket
import subprocess
import time
import uuid
from qio import PACKAGE,QUEUE,CAMPAIGN,read,ref,new_json,atomic_json,append,process_identity,same_process,utc
from qauthority import AUTH_SHA,current,package_ready,collection_gate,AwaitingRelease,AuthorityFault
from qjobs import next_rows,prepare_next,snapshot,terminal
from qreservation import receive_existing_fd
from qevents import pump,enqueue
from service_primitives import acquire_singleton,detached


def descendant_of(row,pid):
    seen=set()
    while row and row['pid'] not in seen:
        if row['pid']==pid:return True
        seen.add(row['pid']);row=process_identity(row['ppid'])
    return False


def heartbeat(node,status,**extra):
    atomic_json(QUEUE/'nodes'/node/'HEARTBEAT.json',dict(schema='queue_heartbeat_v1',node=node,host=socket.gethostname(),
        process=process_identity(),utc=utc(),status=status,authorization_sha256=AUTH_SHA,
        package=ref(PACKAGE/'PACKAGE_MANIFEST.json'),**extra))


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


def run_chain(release_path,p,node='A'):
    """The daemon retains a duplicate of the SAME lock FD through final publication."""
    from core.handoff import require_handoff_environment
    from core.process_family import drain_group
    from core.wave_timing import observe_restoration
    cfg=read(p['parents'][0]['config']['path']);require_handoff_environment(cfg,os.environ)
    chain=QUEUE/'nodes'/node/'chains'/p['job_id'];chain.mkdir(parents=True,exist_ok=False)
    status=read('/tmp/gpu_occupancy_guard/status.json')
    holders=[process_identity(r['manager_pid']) for r in status.get('gpus',{}).values() if r.get('manager_pid')]
    if any(r is None for r in holders):raise RuntimeError('own holder start identity not observable before handoff')
    sockpath='/tmp/corrector_qfd_'+uuid.uuid4().hex+'.sock'
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);server.bind(sockpath);os.chmod(sockpath,0o600);server.listen(1)
    request=dict(node=node,host=socket.gethostname(),process=process_identity(),socket=sockpath,
                 request_unix=time.time(),holder_processes=holders,first_release=ref(release_path),
                 holder_policy='all8_off_across_runnable_chain',nested_lock_acquisitions=0)
    new_json(chain/'REQUEST.json',request)
    cmd=[cfg['occupancy_lifecycle'],'run','--',cfg['python'],'-B',str(PACKAGE/'queue/qdrain.py'),
         '--first-release',str(release_path),'--chain',str(chain)]
    new_json(chain/'COMMAND.json',dict(argv=cmd,started_utc=utc(),opportunity_consumed=True,
        handoff_seconds=300,formal_wave_seconds_per_batch=p['timeouts']['reserved_wave_seconds'],retries=0))
    fd=None;peer=None;proc=None;primary=None;cleanup=None;count=0;last_monitor=0;last_heartbeat=0
    try:
        with (chain/'stdout.log').open('xb') as so,(chain/'stderr.log').open('xb') as se:
            proc=subprocess.Popen(cmd,cwd=PACKAGE,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),
                stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
        new_json(chain/'LIFECYCLE_STARTED.json',dict(process=process_identity(proc.pid),utc=utc()))
        while proc.poll() is None:
            if fd is None and select.select([server],[],[],0)[0]:
                fd,peer=receive_existing_fd(server,cfg['occupancy_handoff']['formal_lock_path'],
                    lambda row:descendant_of(row,proc.pid))
                new_json(chain/'SUPERVISOR_FD_RECEIVED.json',dict(peer=peer,utc=utc(),same_guard_open_file_description=True,
                    secondary_lock_acquisition=False,release_deferred_until_supervisor_publication=True))
            now=time.monotonic()
            if now-last_heartbeat>=5:
                progress=read(chain/'PROGRESS.json') if (chain/'PROGRESS.json').exists() else None
                heartbeat(node,'formal_chain' if peer else 'holder_handoff',chain=str(chain),progress=progress,
                          reservation='same_node_guard_FD',holders='all8off_until_chain_exit_publication')
                last_heartbeat=now
            if peer and (chain/'HOLDER_EXIT_ACK.json').exists() and now-last_monitor>=15:
                count=monitor_sample(chain,count,active=True);last_monitor=now
            pump(node)
            time.sleep(.2)
        code=proc.wait()
        if peer:cleanup=drain_group(peer['pgid'],peer['pid'])
        else:cleanup=dict(status='no_drain_group_started' if not (chain/'DRAIN_STARTED.json').exists() else 'entry_before_FD_handoff_failed')
        if peer and cleanup['status']!='all_formal_group_members_exited':raise RuntimeError('unknown owned descendants; no reservation release')
        exitdoc=read(chain/'DRAIN_EXIT.json') if (chain/'DRAIN_EXIT.json').exists() else None
        minimum=dict(schema='queue_chain_epilogue_v1',raw_lifecycle_exit=code,cleanup=cleanup,drain_exit=exitdoc,
            query_attempts=count,utc=utc(),holders='off_pending_final_publication',process=process_identity(),
            successful_handoff_raw_poll_count=None,new_handoff_GPU_probes=0)
        new_json(chain/'PRE_RELEASE_EPILOGUE.json',minimum)
        # A crash never resubmits an existing command. Preserve a minimal outer failure and block.
        active=[j for j in snapshot()['jobs'].values() if j['node']==node and j['state']!='terminal']
        for job in active:
            r=read(job['release']['path']);jp=read(r['proposal']['path'])
            if job['state']!='execution_unknown':
                terminal(jp,dict(status='blocked',reason='outer exit before complete batch terminal evidence',
                    process_exit_proven=peer is None or cleanup['status']=='all_formal_group_members_exited',
                    publication_complete=False,validation_ref=ref(chain/'PRE_RELEASE_EPILOGUE.json'),
                    source_dispositions={x:'execution_unknown_no_retry' for x in jp['source_keys']},parents=[]))
            event=QUEUE/'nodes'/node/'outbox'/(node+'__'+jp['job_id']+'__terminal_v1')/'EVENT.json'
            if not event.exists():
                enqueue(node,jp['job_id'],outcome='execution_unknown',proposal=jp,
                    launch=dict(process_exit_proven=minimum['cleanup']['status']=='all_formal_group_members_exited',publication_complete=False,
                                restoration='pending_supervisor_release',primary=minimum['drain_exit']),results=[ref(chain/'PRE_RELEASE_EPILOGUE.json')])
        if exitdoc is None or exitdoc.get('fault'):
            atomic_json(QUEUE/'nodes'/node/'BLOCKED.json',dict(reason='chain terminal/fault requires explicit reconciliation',chain=ref(chain/'PRE_RELEASE_EPILOGUE.json'),utc=utc()))
    except BaseException as error:
        import traceback
        primary=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
        if proc and proc.poll() is None:
            # Only the positively identified lifecycle child, whose guard forwards to its owned group.
            proc.send_signal(signal.SIGTERM);proc.wait()
        if peer:cleanup=drain_group(peer['pgid'],peer['pid'])
        new_json(chain/'SUPERVISOR_FAILURE.json',dict(primary=primary,cleanup=cleanup,utc=utc()))
        atomic_json(QUEUE/'nodes'/node/'BLOCKED.json',dict(reason='supervisor failure',evidence=ref(chain/'SUPERVISOR_FAILURE.json'),utc=utc()))
    finally:
        server.close()  # Leave the unique socket pathname as evidence; no cleanup/deletion task.
        if fd is not None:
            if not cleanup or cleanup.get('status')!='all_formal_group_members_exited':
                heartbeat(node,'blocked_retaining_reservation',chain=str(chain),reason='owned exit unproven')
                # Never resume holders while unknown group computation may remain.
                while True:time.sleep(5)
            os.close(fd)
        restored=observe_restoration(time.time(),120)
        new_json(chain/'RESTORATION.json',restored)
        new_json(chain/'CHAIN_RESULT.json',dict(primary=primary,restoration=restored,
            cleanup=cleanup,utc=utc(),scientific_retry=False,fd_transfer_retained_same_reservation=fd is not None))
        for event in (QUEUE/'nodes'/node/'outbox').glob('*/EVENT.json'):
            e=read(event)
            if not e['synthetic'] and not (event.parent/'OUTER_CHAIN_RESULT.json').exists():
                new_json(event.parent/'OUTER_CHAIN_RESULT.json',dict(chain_result=ref(chain/'CHAIN_RESULT.json'),
                    relation='terminal batch before this chain final barrier',restoration=ref(chain/'RESTORATION.json')))
        if restored['status']!='occupancy_resolved':
            atomic_json(QUEUE/'nodes'/node/'BLOCKED.json',dict(reason='occupancy restoration unresolved',evidence=ref(chain/'RESTORATION.json'),utc=utc()))
    return chain


def serve(node):
    auth,_=current(node);ready=package_ready();root=QUEUE/'nodes'/node;root.mkdir(parents=True,exist_ok=True)
    local=Path('/tmp')/('corrector_queue_'+node+'_'+socket.gethostname());local.mkdir(exist_ok=True)
    singleton=acquire_singleton(local/'daemon.lock')
    if singleton is None:return 0
    own=process_identity();stopping=False
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
        if not (root/'STOP.json').exists():new_json(root/'STOP.json',dict(reason='service signal; drain current batch',signal=signum,utc=utc()))
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,stop)
    history=root/'deployments'/(own['boot_id']+'_'+str(own['start_ticks'])+'.json')
    deployment=dict(status='READY',node=node,host=socket.gethostname(),process=own,utc=utc(),authorization_sha256=AUTH_SHA,
        process_identity=own,package_sha256=ref(QUEUE/'package/READY.json')['sha256'],
        package=ready['manifest'],stdin='DEVNULL',session=os.getsid(0),singleton=str(local/'daemon.lock'),
        control_plane_detach_checks=ready['CPU_READY'],formal_compute_started=False,
        host_reboot_requires_restart=True,training_evaluation_deletion_enabled=False)
    new_json(history,deployment);atomic_json(root/'DAEMON_READY.json',dict(deployment,deployment_ref=ref(history)))
    if not (root/'JOIN_ACK.json').exists():new_json(root/'JOIN_ACK.json',deployment)
    if not (root/'SERVICE_JOIN_ACK_V2.json').exists():new_json(root/'SERVICE_JOIN_ACK_V2.json',deployment)
    while not stopping:
        state='waiting';details={};job=None
        try:
            current(node)
            if (root/'BLOCKED.json').exists():state='blocked';details['reason']=read(root/'BLOCKED.json')
            elif node=='B':state='waiting_B_independent_stage_release';details['common_pool_source_limit']=0
            else:
                rows,sequence=next_rows()
                if not rows:state='collection_stage_exhausted_training_not_authorized'
                else:
                    collection_gate(sequence=sequence,admission=True)
                    job=prepare_next()
                    if job is not None:run_chain(*job,node=node)
                    continue
        except AwaitingRelease as error:state='waiting_first8_release';details['reason']=str(error)
        except BaseException as error:
            state='blocked';details['reason']=dict(type=type(error).__name__,message=str(error))
            atomic_json(root/'BLOCKED.json',dict(details,utc=utc()))
            evidence=root/'control_failures'/(own['boot_id']+'_'+str(own['start_ticks'])+'.json')
            if not evidence.exists():
                new_json(evidence,dict(details,utc=utc(),process=own,scientific_counts=None,
                    missing_reason='inspect any durable command/claim and original ledgers; no inferred zero',no_retry=True))
                enqueue(node,'control_failure_'+str(own['start_ticks']),outcome='blocked_control_plane',
                    results=[ref(evidence)])
        heartbeat(node,state,reservation='none',holders='guard_idle_policy',**details)
        try:pump(node)
        except BaseException as error:atomic_json(root/'NOTIFICATION_ERROR.json',dict(utc=utc(),type=type(error).__name__,message=str(error)))
        for _ in range(25):
            if stopping:break
            time.sleep(.2)
    heartbeat(node,'service_stopped_after_drain',reservation='none',holders='guard_idle_policy')
    return 0


def start(node):
    current(node);package_ready();root=QUEUE/'nodes'/node
    if (root/'DAEMON_READY.json').exists() and same_process(read(root/'DAEMON_READY.json')['process']):
        print(json.dumps(dict(status='already_running',ready=str(root/'DAEMON_READY.json'))));return 0
    root.mkdir(parents=True,exist_ok=True)
    from local_control_check import check
    check(root/'local_checks'/(process_identity()['boot_id']+'_'+uuid.uuid4().hex+'.json'))
    proc=detached([sys.executable,'-B',str(PACKAGE/'queue/main.py'),'serve','--node',node],cwd=PACKAGE,
        log=root/'daemon.log',env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS='300'))
    print(json.dumps(dict(status='spawned_not_yet_READY',pid=proc.pid,node=node)))
    return 0
