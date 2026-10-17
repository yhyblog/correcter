"""Finite detached train -> idle selection watcher ->24-worker native evaluation."""
import argparse,fcntl,os,signal,subprocess,sys,time,traceback
from pathlib import Path
import paths
from paths import ROOT,CAMPAIGN,TASK,AUTH_SHA,SELECTION
from qio import read,new_json,atomic_json,ref,utc,process_identity
from admission import authority,previous_exited,resource_admission,before_cutoff,boundary
from wave import notify_identity,run_wave
from selection import publish_candidates,try_consume
from publications import publish,terminal_receipt

JOB='D24_C_FULLQ_r1'
DISC=CAMPAIGN/'work/C/C_TASK_DISCOVERY_SERVICE_V1_r1'
stopping=False

def stop(*_):
    global stopping
    stopping=True

def stage_start(stage):
    deadline=min(time.time()+12*3600,read(ROOT/'config/CONFIG.json')['absolute_wall_deadline_unix'])
    atomic_json(ROOT/'STAGE_DEADLINE.json',dict(stage=stage,started_utc=utc(),deadline_unix=deadline,max_stage_seconds=43200))
    boundary(True)

def wave_complete(row):
    return (row['exit_code']==0 and not row['fatal'] and not row['timeout']
        and row['cleanup']['status']=='all_formal_group_members_exited'
        and row['restoration']['status']=='occupancy_resolved')

def serve():
    local=Path('/tmp/corrector_C_FULLQ_r1');local.mkdir(exist_ok=True)
    with (local/'daemon.lock').open('a') as singleton:
        fcntl.flock(singleton,fcntl.LOCK_EX|fcntl.LOCK_NB)
        authority();previous_exited()
        assert read(ROOT/'CPU_CHECK.json')['status']=='passed'
        own=notify_identity(process_identity());claim=ROOT/'CLAIM.json'
        new_json(claim,dict(task_id=TASK,run_id=JOB,utc=utc(),process=own,authorization_sha256=AUTH_SHA,
            config=ref(ROOT/'config/CONFIG.json'),method=ref(ROOT/'METHOD_FROZEN.json'),CPU_check=ref(ROOT/'CPU_CHECK.json'),
            no_automatic_relaunch=True,scientific_scope='16 full-Q fits then selected Post/Velocity1000'))
        new_json(ROOT/'PROCESS.json',own)
        registration=dict(job_id=JOB,task_id=TASK,revision=1,run_id=JOB,attempt=1,
            claim_identity=dict(path=str(claim),sha256=ref(claim)['sha256']),process_identity=own,
            result_path=str(ROOT/'RESULT.json'),error_summary_path=str(ROOT/'supervisor.log'))
        new_json(ROOT/'WAKEUP_REGISTRATION.json',registration)
        fatal=None;waves=[];report_rc=None;stage='register';started=time.monotonic();status='execution_unknown'
        for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,stop)
        try:
            subprocess.run(['/usr/bin/python','-B',str(DISC/'wakeup.py'),'register','--manifest',str(ROOT/'WAKEUP_REGISTRATION.json')],check=True,timeout=60)
            stage='train';stage_start(stage);new_json(ROOT/'RESOURCE_TRAIN.json',resource_admission(stage));publish('training')
            waves.append(run_wave(stage))
            if not wave_complete(waves[-1]):raise RuntimeError('training wave incomplete; no implicit fit retry')
            candidates=publish_candidates()
            stage='selection_dependency';stage_start(stage)
            new_json(ROOT/'SELECTION_WATCHER_ARMED.json',dict(utc=utc(),process=own,selection_path=str(SELECTION),
                dependency='shared dev-only loss; not cross-node process barrier',interval_seconds=15,
                deadline=read(ROOT/'STAGE_DEADLINE.json'),selection_required_before_GPU_entry=True,
                formal_reservation_held=False,automatic_evaluation_workers=24,terminal_notification=str(ROOT/'WAKEUP_REGISTRATION.json')))
            new_json(ROOT/'STABLE_HANDOFF.json',dict(utc=utc(),task_id=TASK,status='CANDIDATES_READY_waiting_for_A_selection',
                fits_complete=16,actual_optimizer_updates=64000,candidates=ref(ROOT/'CANDIDATES_READY.json'),
                training_wave_exit=str(ROOT/'chains/train/RESULT.json'),occupancy_restored=True,
                watcher=ref(ROOT/'SELECTION_WATCHER_ARMED.json'),notification=ref(ROOT/'WAKEUP_REGISTRATION.json'),
                original_executor_thread='01a0c793-10d2-7791-a250-fd65d88e1ccb',stop_LLM_wait=True,
                actual_original_task_ACK=str(CAMPAIGN/'persistent_queue/nodes/C/wakeup/handler_acks/C_7e99dfdf5a30dcf9eb7bc001c3d963e0.json'),
                unattended_exec_resume_certified=False))
            publish('CANDIDATES_READY_waiting_selection',actual_optimizer_updates=64000)
            selected=None
            while selected is None:
                boundary()
                if stopping:raise RuntimeError('supervisor stopped while idle selection wait')
                try:
                    selected=try_consume();error=None
                except (ValueError,KeyError,TypeError) as exc:
                    error=repr(exc)
                    atomic_json(ROOT/'SELECTION_REJECTED.json',dict(utc=utc(),error=error,selection_path=str(SELECTION),
                        outcome='no test admitted; awaiting valid complete immutable selection',automatic_local_selection=False))
                atomic_json(ROOT/'HEARTBEAT.json',dict(utc=utc(),process=own,status='selection_dependency' if selected is None else 'selection_consumed',
                    selection_exists=SELECTION.exists(),selection_error=error,formal_work_active=False))
                if selected is None:time.sleep(15)
            stage='evaluate';stage_start(stage);previous_exited()
            new_json(ROOT/'RESOURCE_EVALUATE.json',resource_admission(stage));publish('evaluating',chosen_loss=selected['chosen_loss'],actual_optimizer_updates=64000)
            waves.append(run_wave(stage))
            stage='report'
            with (ROOT/'report.log').open('xb') as log:
                report=subprocess.run(['/usr/bin/python','-B',str(ROOT/'code/report.py')],cwd=ROOT,
                    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2'),
                    stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=300)
            report_rc=report.returncode
            summary=read(ROOT/'FINAL_SUMMARY.json') if (ROOT/'FINAL_SUMMARY.json').exists() else None
            status='complete' if report_rc==0 and summary and summary['evaluation_valid']==1000 and wave_complete(waves[-1]) else 'partial_or_publication_pending'
        except BaseException as exc:
            fatal=dict(stage=stage,error=repr(exc),traceback=traceback.format_exc())
            status='blocked_selection' if stage=='selection_dependency' else 'partial_or_failed'
        all_exited=all(w.get('cleanup',{}).get('status') in ['all_formal_group_members_exited','no_formal_entry'] for w in waves)
        # If a wave raised before returning, its cleanup records are required rather than assuming exit.
        restored=all(w.get('restoration',{}).get('status')=='occupancy_resolved' for w in waves)
        for directory in (ROOT/'chains').glob('*') if (ROOT/'chains').exists() else []:
            p=directory/'BEFORE_RESERVATION_RELEASE.json'
            if not p.exists() or (read(p).get('cleanup') or {}).get('status') not in ['all_formal_group_members_exited','no_formal_entry']:all_exited=False
            restoration=directory/'RESTORATION.json'
            if not restoration.exists() or read(restoration).get('status')!='occupancy_resolved':restored=False
        new_json(ROOT/'RESULT.json',dict(task_id=TASK,batch_id=JOB,status=status,utc=utc(),fatal=fatal,stage=stage,
            waves=waves,all_owned_descendants_exited=all_exited,occupancy_handoff_complete=restored,
            report_exit_code=report_rc,summary_path=str(ROOT/'FINAL_SUMMARY.json'),
            candidates_path=str(ROOT/'CANDIDATES_READY.json'),elapsed_seconds=time.monotonic()-started,
            automatic_scientific_retries=0,completed_source_replays=0))
        terminal_receipt();atomic_json(ROOT/'HEARTBEAT.json',dict(utc=utc(),status='terminal',result=str(ROOT/'RESULT.json')))
        return 0 if status=='complete' else 3

def start():
    authority();previous_exited()
    if (ROOT/'CLAIM.json').exists():
        print('EXISTING_CLAIM_NO_RELAUNCH',ROOT/'CLAIM.json');return 0
    with (ROOT/'supervisor.log').open('ab') as log:
        proc=subprocess.Popen(['/usr/bin/python','-B',str(ROOT/'code/service.py'),'serve'],cwd=ROOT,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    print('SPAWNED',proc.pid);return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);a=p.parse_args();raise SystemExit(start() if a.action=='start' else serve())
