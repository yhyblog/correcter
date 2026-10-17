"""Finite CPU issue timers and private metadata/report repairs, zero GPU calls."""
import argparse,fcntl,os,re,signal,subprocess,time,traceback
from pathlib import Path
from c_recovery_policy import ROOT,C,X,P,ISSUES,OUTBOX,ANALYSIS,EXECUTOR,TASK,AUTH,AUTH_SHA,authority,consume,issue,record_fault,snapshot,timers,repair_gate,own_family_exited,unfinished_units,current_budgets,live_identity
from ops_io import read,new_json,atomic_json,ref,utc,process_identity
from selection_bridge import locked_post_choice,maybe_adapt_native
WAKE=C/'work/C/C_TASK_DISCOVERY_SERVICE_V1_r1/wakeup.py'
RUN='D24_C_AUTORECOVERY_r1'

def scan():
    choice=None;selection_error=None
    try:choice=locked_post_choice()
    except (ValueError,KeyError,TypeError) as exc:selection_error=repr(exc)
    transfer=P/'TRANSFER_CONSUMED.json';rows=[]
    for root in [X,P]:
        owner=snapshot(root/'PROCESS.json');heart=snapshot(root/'HEARTBEAT.json');result=snapshot(root/'RESULT.json');alive=live_identity(owner)
        manager=snapshot(root/'chains/evaluate/MANAGER_STARTED.json').get('process');formal=live_identity(manager)
        blockers=[]
        if choice is None:blockers.append('complete immutable Post-only development selection absent or invalid')
        if root==P:
            if not transfer.exists():blockers.append('exact A-to-C source transfer not consumed')
            if not own_family_exited(X):blockers.append('original own X task not reliably terminal with entire family exited')
        if formal:state='formal_active'
        elif result and not alive:state='terminal'
        elif alive and blockers:state='dependency_wait'
        elif alive:state='eligible_for_existing_unique_queue'
        elif (root/'CLAIM.json').exists():state='claimed_owner_exited_requires_reconciliation'
        else:state='not_deployed'
        rows.append(dict(task_id=root.name,root=str(root),state=state,process=owner,owner_alive=alive,formal_active=formal,heartbeat_status=heart.get('status'),blockers=blockers,terminal_status=result.get('status'),terminal_exists=bool(result),launch_owner='existing original C queue; this CPU supervisor never duplicates it'))
        if state=='claimed_owner_exited_requires_reconciliation':record_fault(root,'Unique queue owner exited without reliable task result',kind='engineering_requires_specific_diagnosis',evidence=[str(root/'CLAIM.json'),str(root/'PROCESS.json')],continuable=['other dependency-independent authorized C task'])
        for name in ['SELECTION_REJECTED.json','DEPENDENCY_REJECTED.json']:
            error=snapshot(root/name)
            if error and choice is None and selection_error:
                record_fault(root,selection_error,kind='scientific_or_ownership_dependency',evidence=[str(root/name)],signature='invalid_published_Post_only_selection')
    all_waiting=all(r['state'] in ['dependency_wait','terminal','claimed_owner_exited_requires_reconciliation'] for r in rows) and any(r['state']!='terminal' for r in rows)
    state=dict(utc=utc(),rows=rows,selection_ready=choice is not None,selection_error=selection_error,status='NO_RUNNABLE_TASKS' if all_waiting else 'ACTIVE_OR_ELIGIBLE_OR_TERMINAL',scientific_launches_by_companion=0,prerequisite_bypass=False)
    atomic_json(ROOT/'SCAN.json',state)
    atomic_json(ROOT/'NO_RUNNABLE_TASKS.json',dict(state,current=all_waiting))
    if all_waiting:
        row=issue(ROOT,'All remaining C scientific work currently lacks required selection/ownership/predecessor readiness',kind='dependency_wait',blocked=[r['task_id'] for r in rows if r['state']!='terminal'],continuable=['CPU monitoring, queue preparation and independent eligible work when dependencies change'],evidence=[str(ROOT/'SCAN.json')],decision_required='Publish required valid dependencies; no approval is requested and no deadline can waive selection or ownership.',signature='all_C_scientific_dependencies_pending')
        atomic_json(ROOT/'NO_RUNNABLE_ISSUE.json',dict(issue_id=row['issue_id'],path=str(ISSUES/(row['issue_id']+'.json'))))
    elif (ROOT/'NO_RUNNABLE_ISSUE.json').exists():
        path=Path(read(ROOT/'NO_RUNNABLE_ISSUE.json')['path']);row=read(path)
        if row['status'] not in ['resolved_by_dependency_progress','resolved']:
            row.update(status='resolved_by_dependency_progress',resolved_at=utc(),resolution_evidence=str(ROOT/'SCAN.json'));atomic_json(path,row)
    return rows

def deliver_once():
    for path in OUTBOX.glob('C_recovery_*.json'):
        dest=ROOT/'transport'/path.name
        if dest.exists():continue
        event=read(path)
        if event['target_thread_id']!=ANALYSIS:raise ValueError('analysis thread substitution forbidden')
        record=dict(utc=utc(),event=str(path),target_thread=ANALYSIS,attempts=1,handler_ACK=False,status='transport_attempt_entered',automatic_resend=False)
        new_json(dest,record)
        try:
            proc=subprocess.run(['/home/tiger/.local/bin/codex','queue','--thread',ANALYSIS,'--message',event['message']],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30,cwd=C.parents[2])
            record.update(status='transport_accepted_not_handler_ACK' if proc.returncode==0 else 'transport_failed_outbox_retained',exit_code=proc.returncode,stdout=proc.stdout[-2000:],stderr=proc.stderr[-2000:])
        except Exception as exc:record.update(status='transport_failed_outbox_retained',error=repr(exc))
        atomic_json(dest,record)

def terminal_inventories():
    for root in [X,P]:
        out=ROOT/'terminal_inventories'/(root.name+'.json')
        if out.exists() or not own_family_exited(root):continue
        data=unfinished_units(root)
        atomic_json(out,dict(utc=utc(),task_id=root.name,expected=data['expected'],remaining=data['remaining'],legal_terminals_preserved=sum(r.get('status')=='complete' and type(r.get('success')) is bool for r in data['states'].values()),log_recovered_evidence=data.get('log_recovered_evidence',[]),budget=current_budgets()[root.name],launch=False))

def report_repairs():
    for stage in [X,P]:
        result=snapshot(stage/'RESULT.json')
        if result.get('report_exit_code') in [None,0] or not own_family_exited(stage):continue
        marker=ROOT/'repairs'/(stage.name+'_publication.json')
        if marker.exists():continue
        log=stage/'report.log'
        if not log.is_file():continue
        with log.open('rb') as f:
            f.seek(max(0,log.stat().st_size-16000));text=f.read().decode(errors='replace')
        row=issue(stage,text[-3000:],kind='engineering',unit='CPU_report',evidence=[str(stage/'RESULT.json'),str(log)],continuable=['next independent already-authorized C task'],signature='CPU_report_nonzero_exit')
        # Only a concrete restored file is automatically retried. Other faults
        # return through the already-armed original executor event for a real fix.
        paths=re.findall(r"(?:No such file or directory|Stale file handle|Input/output error): ['\"]([^'\"]+)['\"]",text)
        recovered=[]
        for name in paths:
            p=Path(name)
            if p.is_absolute() and p.is_relative_to(C.parents[2]) and p.is_file():
                if p.suffix=='.json':read(p)
                else:
                    with p.open('rb') as f:f.read(1024)
                recovered.append(ref(p))
        if not recovered:
            new_json(marker,dict(utc=utc(),status='specific_fix_required_from_original_executor',issue_id=row['issue_id'],scientific_relaunch=False));continue
        fix=dict(change='The exact path in the recorded transient publication failure is now readable',evidence=recovered,science_changed=False)
        repair_gate(ISSUES/(row['issue_id']+'.json'),fix,[],{},0,family_exited=True)
        new_json(marker,dict(utc=utc(),status='CPU_publication_retry_entered',fix=fix,issue_id=row['issue_id'],scientific_relaunch=False))
        output=ROOT/'repairs'/(stage.name+'_publication.log');base=read(stage/'config/BASE.json')
        with output.open('xb') as log:
            proc=subprocess.run([base['python'],'-B',str(stage/'code/report.py')],cwd=stage,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2'),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        atomic_json(marker,dict(utc=utc(),status='CPU_publication_recovered' if proc.returncode==0 else 'CPU_publication_still_failed',exit_code=proc.returncode,issue_id=row['issue_id'],fix=fix,output=str(output),original_scientific_RESULT_preserved=True,new_GPU_calls=0))

def serve():
    local=Path('/tmp/corrector_C_autorecovery_r1');local.mkdir(exist_ok=True)
    with (local/'daemon.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        consume(ROOT,'supervisor');identity=process_identity();own=dict(hostname=identity['host'],boot_id=identity['boot_id'],pid=identity['pid'],start_ticks=identity['start_ticks'],session_id=os.getsid(0))
        if read(ROOT/'CPU_CHECK.json')['status']!='passed':raise ValueError('CPU checks not passed')
        end=min(time.time()+24*3600,1790175600.) # 2026-09-23 15:00 UTC tables deadline; no scientific admissions here.
        new_json(ROOT/'CLAIM.json',dict(task_id=TASK,run_id=RUN,process=own,utc=utc(),authorization_sha256=AUTH_SHA,CPU_only=True,scientific_claims=0))
        new_json(ROOT/'PROCESS.json',own)
        manifest=dict(job_id=RUN,task_id=TASK,revision=1,run_id=RUN,attempt=1,claim_identity=ref(ROOT/'CLAIM.json'),process_identity=own,result_path=str(ROOT/'RESULT.json'),error_summary_path=str(ROOT/'stderr.log'))
        new_json(ROOT/'WAKEUP_REGISTRATION.json',manifest)
        stopping=False
        def stop(*_):
            nonlocal stopping
            stopping=True
        for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,stop)
        fatal=None;rows=[];status='monitoring'
        try:
            subprocess.run(['/usr/bin/python','-B',str(WAKE),'register','--manifest',str(ROOT/'WAKEUP_REGISTRATION.json')],check=True,timeout=30)
            new_json(ROOT/'READY.json',dict(utc=utc(),process=own,finite_end_unix=end,CPU_only=True,scientific_launches=0,terminal_trigger=ref(ROOT/'WAKEUP_REGISTRATION.json'),original_queues_preserved=True))
            while not stopping and time.time()<end:
                authority();bridge_error=None
                try:bridge=maybe_adapt_native()
                except (ValueError,KeyError,TypeError) as exc:
                    bridge_error=repr(exc);bridge=dict(status='selection_bridge_waits_for_specific_correction',error=bridge_error)
                    record_fault(X,bridge_error,kind='scientific_or_ownership_dependency',evidence=[str(ROOT/'NATIVE_SELECTION_BRIDGE.json')],signature='native_Post_selection_bridge_rejected')
                atomic_json(ROOT/'NATIVE_SELECTION_BRIDGE.json',dict(utc=utc(),**bridge))
                rows=scan();timers();terminal_inventories();report_repairs();deliver_once()
                atomic_json(ROOT/'HEARTBEAT.json',dict(utc=utc(),process=own,status='monitoring',scan=rows,bridge=bridge,issue_count=len([p for p in ISSUES.glob('C_recovery_*.json') if not p.name.endswith('_DECISION.json')]),finite_end_unix=end,new_GPU_calls=0,scientific_launches=0,queue_processes_signalled=0))
                if all(r['state']=='terminal' for r in rows):status='monitored_tasks_terminal';break
                time.sleep(15)
            else:status='stopped' if stopping else 'CPU_monitor_deadline'
        except BaseException as exc:
            fatal=dict(error=repr(exc),traceback=traceback.format_exc());status='control_failed'
        new_json(ROOT/'RESULT.json',dict(task_id=TASK,run_id=RUN,status=status,utc=utc(),fatal=fatal,scan=rows,CPU_only=True,new_GPU_calls=0,scientific_launches=0,queue_processes_signalled=0,all_owned_descendants_exited=True,occupancy_handoff_complete=True,actual_scientific_failure_recovery_tested=False,original_task_terminals_unmodified=True))
        return 3 if fatal else 0

def start():
    authority()
    if (ROOT/'CLAIM.json').exists():print('EXISTING_CLAIM_NO_DUPLICATE');return 0
    with (ROOT/'stdout.log').open('ab') as so,(ROOT/'stderr.log').open('ab') as se:
        p=subprocess.Popen(['/usr/bin/python','-B',str(Path(__file__).resolve()),'serve'],cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
    print('SPAWNED_NOT_YET_READY',p.pid);return 0

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','serve']);a=parser.parse_args();raise SystemExit(start() if a.action=='start' else serve())
