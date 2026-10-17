"""Finite detached waiting -> original X exit -> exact Pi05 H40/H50 continuation."""
import argparse,fcntl,os,signal,subprocess,time,traceback
from pathlib import Path
import paths
from paths import ROOT,CAMPAIGN,TASK,JOB,AUTH_SHA,PREVIOUS,SELECTION,TRANSFER
from qio import read,new_json,atomic_json,utc,ref,process_identity,same_process
from admission import authority,admissions_allowed,previous_exited,resource_admission,before_cutoff
from wave import notify_identity,run_wave
from selection import try_consume as selection_ready
from transfer import try_consume as transfer_ready
DISC=CAMPAIGN/'work/C/C_TASK_DISCOVERY_SERVICE_V1_r1'
stopping=False

def stop(*_):
    global stopping
    stopping=True

def receipt(status,**extra):
    row=dict(task_id=TASK,node='C',revision=1,status=status,utc=utc(),claim=str(ROOT/'CLAIM.json'),process=str(ROOT/'PROCESS.json'),heartbeat=str(ROOT/'HEARTBEAT.json'),queue_ready=str(ROOT/'QUEUE_READY.json'),ordered_stages=str(ROOT/'ORDERED_STAGES.json'),stable_handoff=str(ROOT/'STABLE_HANDOFF.json'),terminal_registration=str(ROOT/'WAKEUP_REGISTRATION.json'),previous_native_task=str(PREVIOUS),previous_native_waiter_unchanged=True,first_maximum=2000,stage_attempt_cap=2200,cumulative_attempt_cap=16000,formal_workers=24,workers_per_GPU=3,selection='A complete Post development only, fixed9101',new_collection=0,new_training_updates=0,**extra)
    atomic_json(CAMPAIGN/'receipts/C'/f'{TASK}_RESULT_r1.json',row)
    atomic_json(CAMPAIGN/'nodes/C/PROGRESS.json',row)

def prerequisites():
    selected=selection_ready();previous=previous_exited();transfer=transfer_ready() if selected else None
    return dict(selection=selected,previous_exit=previous,transfer=transfer)

def serve():
    local=Path('/tmp/corrector_C_PI05_selected_r1');local.mkdir(exist_ok=True)
    with (local/'daemon.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        authority()
        if read(ROOT/'CPU_CHECK.json')['status']!='passed':raise RuntimeError('targeted CPU checks absent')
        own=notify_identity(process_identity());claim=ROOT/'CLAIM.json';started=time.monotonic();deadline=min(time.time()+43200,read(ROOT/'config/CONFIG.json')['absolute_wall_deadline_unix'])
        new_json(claim,dict(task_id=TASK,run_id=JOB,utc=utc(),process=own,authorization_sha256=AUTH_SHA,config=ref(ROOT/'config/CONFIG.json'),scope='only exact A-transferred pi05 H40/H50 Post/Velocity',prior_waiter_restarted=False,no_automatic_relaunch=True))
        new_json(ROOT/'PROCESS.json',own)
        new_json(ROOT/'QUEUE_DEADLINE.json',dict(stage='dependency_wait',started_utc=utc(),deadline_unix=deadline,maximum_seconds=43200))
        registration=dict(job_id=JOB,task_id=TASK,revision=1,run_id=JOB,attempt=1,claim_identity=dict(path=str(claim),sha256=ref(claim)['sha256']),process_identity=own,result_path=str(ROOT/'RESULT.json'),error_summary_path=str(ROOT/'supervisor.log'))
        new_json(ROOT/'WAKEUP_REGISTRATION.json',registration)
        fatal=None;waves=[];report_rc=None;status='execution_unknown';stage='register';deps={}
        for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,stop)
        try:
            subprocess.run(['/usr/bin/python','-B',str(DISC/'wakeup.py'),'register','--manifest',str(ROOT/'WAKEUP_REGISTRATION.json')],check=True,timeout=60)
            stage='dependencies'
            new_json(ROOT/'ORDERED_STAGES.json',dict(utc=utc(),task_id=TASK,stages=[dict(stage='A_Post_selection',required=str(SELECTION),gate='complete Post only; immutable fit9101'),dict(stage='existing_native_X',root=str(PREVIOUS),unchanged_original_claim=True,wait_for_reliable_terminal_and_entire_own_family_exit=True),dict(stage='A_exact_transfer',required=str(TRANSFER),no_A_whole_host_exit_barrier=True),dict(stage='MAIN_H40',methods=['Post','Velocity'],maximum_first=1000),dict(stage='MAIN_H50',methods=['Post','Velocity'],maximum_first=1000,after='all H40 jobs drained'),dict(stage='CPU_report_and_terminal',Post_paper=True,Velocity_other_work=True)],queue_wait_max_seconds=43200,formal_stage_max_seconds=43200,global_deadline_utc='2026-09-23T12:00:00Z',native_wait_deadline_unchanged=read(PREVIOUS/'STAGE_DEADLINE.json'),formal_workers=24,workers_per_GPU=3))
            new_json(ROOT/'QUEUE_READY.json',dict(utc=utc(),status='deployed_dependency_wait',process=own,science_started=False,stage=stage,notification=ref(ROOT/'WAKEUP_REGISTRATION.json'),original_X_claim=ref(PREVIOUS/'CLAIM.json'),all8_idle_guard=str(CAMPAIGN/'nodes/C/IDLE_OCCUPANCY_POLICY.json'),queue_deadline=read(ROOT/'QUEUE_DEADLINE.json')))
            new_json(ROOT/'STABLE_HANDOFF.json',dict(task_id=TASK,utc=utc(),status='actual_CPU_queue_deployed_waiting_prerequisites',process=own,queue=ref(ROOT/'QUEUE_READY.json'),ordered_stages=ref(ROOT/'ORDERED_STAGES.json'),notification=ref(ROOT/'WAKEUP_REGISTRATION.json'),fixed_original_thread='01a0c793-10d2-7791-a250-fd65d88e1ccb',actual_original_task_ACK=str(CAMPAIGN/'persistent_queue/nodes/C/wakeup/handler_acks/C_1e850ce7f8f1e5cd72363fae063e4f31.json'),real_model_readiness=False,formal_science_started=False,stop_LLM_wait=True,unattended_exec_resume_certified=False))
            receipt('deployed_dependency_wait')
            while True:
                authority()
                if stopping or not before_cutoff() or not admissions_allowed():raise RuntimeError('finite dependency wait stopped/expired')
                error=None
                try:deps=prerequisites()
                except (ValueError,KeyError,TypeError) as exc:
                    error=repr(exc);atomic_json(ROOT/'DEPENDENCY_REJECTED.json',dict(utc=utc(),error=error,formal_GPU_entry=False))
                ready=not error and all(deps.get(k) is not None for k in ['selection','previous_exit','transfer'])
                state=dict(utc=utc(),process=own,status='dependencies_ready' if ready else 'dependency_wait',selection_exists=SELECTION.exists(),transfer_exists=TRANSFER.exists(),selected_configuration_consumed=(ROOT/'SELECTION_CONSUMED.json').exists(),own_predecessor_exited=deps.get('previous_exit') is not None,formal_work_active=False,error=error,dependency_deadline_unix=deadline)
                atomic_json(ROOT/'HEARTBEAT.json',state)
                if ready:break
                time.sleep(15)
            new_json(ROOT/'PREDECESSOR_EXIT.json',deps['previous_exit'])
            stage='evaluate';new_json(ROOT/'STAGE_DEADLINE.json',dict(stage=stage,started_utc=utc(),deadline_unix=min(time.time()+43200,read(ROOT/'config/CONFIG.json')['absolute_wall_deadline_unix']),maximum_seconds=43200))
            new_json(ROOT/'DEPENDENCIES_SATISFIED.json',dict(utc=utc(),selection=ref(ROOT/'SELECTION_CONSUMED.json'),transfer=ref(ROOT/'TRANSFER_CONSUMED.json'),predecessor=ref(ROOT/'PREDECESSOR_EXIT.json')))
            if deps['transfer']['first_count']:
                new_json(ROOT/'RESOURCE_EVALUATE.json',resource_admission());receipt('evaluating',chosen_loss=deps['selection']['chosen_loss'])
                waves.append(run_wave('evaluate'))
            stage='report'
            with (ROOT/'report.log').open('xb') as log:
                result=subprocess.run([read(ROOT/'config/BASE.json')['python'],'-B',str(ROOT/'code/report.py')],cwd=ROOT,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2'),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=300)
            report_rc=result.returncode;summary=read(ROOT/'FINAL_SUMMARY.json') if (ROOT/'FINAL_SUMMARY.json').exists() else None
            status='complete' if report_rc==0 and summary and summary['compute_complete'] and all(w['exit_code']==0 and not w['fatal'] and not w['timeout'] for w in waves) else 'partial_or_publication_pending'
        except BaseException as exc:
            fatal=dict(stage=stage,error=repr(exc),traceback=traceback.format_exc());status='blocked_dependencies' if stage=='dependencies' else 'partial_or_failed'
        all_exited=True;restored=True
        for chain in (ROOT/'chains').glob('*') if (ROOT/'chains').exists() else []:
            release=chain/'BEFORE_RESERVATION_RELEASE.json';rest=chain/'RESTORATION.json'
            if not release.exists() or (read(release).get('cleanup') or {}).get('status') not in ['all_formal_group_members_exited','no_formal_entry']:all_exited=False
            if not rest.exists() or read(rest).get('status')!='occupancy_resolved':restored=False
        new_json(ROOT/'RESULT.json',dict(task_id=TASK,batch_id=JOB,status=status,utc=utc(),fatal=fatal,stage=stage,waves=waves,all_owned_descendants_exited=all_exited,occupancy_handoff_complete=restored,report_exit_code=report_rc,summary_path=str(ROOT/'FINAL_SUMMARY.json'),elapsed_seconds=time.monotonic()-started,automatic_scientific_retries=0,completed_source_replays=0,dependency_stage_exit_is_not_a_scientific_failure=True))
        receipt(status,result=str(ROOT/'RESULT.json'),all_owned_descendants_exited=all_exited,occupancy_handoff_complete=restored)
        atomic_json(ROOT/'HEARTBEAT.json',dict(utc=utc(),process=own,status='terminal',result=str(ROOT/'RESULT.json')))
        return 0 if status=='complete' else 3

def start():
    authority()
    if (ROOT/'CLAIM.json').exists():print('EXISTING_CLAIM_NO_RELAUNCH',ROOT/'CLAIM.json');return 0
    with (ROOT/'supervisor.log').open('ab') as log:
        proc=subprocess.Popen(['/usr/bin/python','-B',str(ROOT/'code/service.py'),'serve'],cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    print('SPAWNED',proc.pid);return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);a=p.parse_args();raise SystemExit(start() if a.action=='start' else serve())
