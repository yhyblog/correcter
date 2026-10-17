"""Finite detached supervisor of existing queues plus encoded continuations."""
import argparse,fcntl,signal,subprocess,traceback
from queue_common import *
from inventory import inventory,allowed_units
from build_continuation import instantiate
JOB='D24_C_QUOTA_INDEPENDENT_r1'
stopping=False

def stop(*_):
    global stopping
    stopping=True

def extend_CPU_wait():
    """The latest quota grant extends only the idle dependency wait to cutoff."""
    path=P/'QUEUE_DEADLINE.json';proof=ROOT/'CPU_DEPENDENCY_WAIT_EXTENSION.json'
    if proof.exists() or (P/'STAGE_DEADLINE.json').exists():return
    old=read(path)
    if old['stage']!='dependency_wait' or old['deadline_unix']>=CUTOFF:return
    new=dict(old,deadline_unix=CUTOFF,quota_override=str(AUTH),scientific_stage_timeout_unchanged=True)
    new_json(proof,dict(utc=utc(),old=old,new=new,authorization=ref(AUTH),scope='CPU-only dependency waiter; no scientific timeout/budget increase'))
    atomic_json(path,new)

def current():
    return [dict(task_id=r.name,process=snapshot(r/'PROCESS.json'),alive=live(snapshot(r/'PROCESS.json')),heartbeat=snapshot(r/'HEARTBEAT.json'),terminal=snapshot(r/'RESULT.json').get('status')) for r in [X,P]]

def has_progress(root):
    pattern='stages/evaluate/workers/*/MODEL_READY.json' if root==X else 'chains/evaluate/workers/*/MODEL_READY.json'
    return any(root.glob(pattern))

def continuation(root):
    # Exactly one encoded recovery pass per original task; source attempt limits
    # are additionally enforced in the per-unit durable admission adapter.
    if len(runs(root))>1:return None
    # A failed preparation is a retained issue, not an unlimited retry loop.
    if (ROOT/'preparation_attempts'/(root.name+'.json')).exists():return None
    if any((root/n).exists() for n in ['STOP.json','DRAIN.json']):return None
    terminal=snapshot(root/'RESULT.json')
    if not terminal or not family(root)['exited']:return None
    inv=inventory(root)
    if not inv['remaining']:return None
    issue_row=issue(root,'Unfinished units after reliable family exit; preserve all valid true/false outcomes','quota_unfinished_units_v1',[str(root/'RESULT.json')])
    if issue_row is None:return None
    # A partial chunk parent claim is an identified scheduler obstruction. The
    # new namespace + source mask removes it without retrying unknown sources.
    fatal=json.dumps(terminal.get('fatal') or {},ensure_ascii=False).lower()
    forbidden=any(s in fatal for s in ['selection','hash mismatch','configuration changed','ownership','physics','boot mismatch','source changed'])
    service_fault=not forbidden and (has_progress(root) or terminal.get('stage') in ['register','dependencies','selection_dependency'])
    selected=__import__('selection_bridge').locked_post_choice()
    if selected is None:return None
    allowed,deferred=allowed_units(inv,service_fault,io_fixed=True)
    nx,np,total=counts();used=nx if root==X else np;available=min((1100 if root==X else 2200)-used,(14000 if root==X else 16000)-total)
    if available<len(allowed):deferred+= [dict(r,reason='unchanged stage/node budget') for r in allowed[max(0,available):]];allowed=allowed[:max(0,available)]
    atomic_json(ROOT/(root.name+'_DEFERRED.json'),dict(utc=utc(),issue_id=issue_row['issue_id'],units=deferred,remaining_budget=available,unknown_not_failure=True))
    if not allowed:return None
    deadline=snapshot(root/'STAGE_DEADLINE.json')
    if deadline.get('stage')=='evaluate' and deadline['deadline_unix']<=time.time():return None
    if root==P:
        from subprocess import run
        # Consumption is already present in the normal chain. Missing ownership
        # remains a dependency, never an inferred transfer.
        if not (root/'TRANSFER_CONSUMED.json').exists() or not (root/'PREDECESSOR_EXIT.json').exists():return None
        verify(read(root/'TRANSFER_CONSUMED.json')['transfer'],base=C)
    fix=dict(change='New evaluation-only namespace, exact unentered-source mask and original counter/claim lineage; retry only evidenced transient qio JSON commits using atomic exclusive bounded IO adapter',science_changed=False,evidence=[ref(WORK/'continuation_adapter.py'),ref(WORK/'atomic_json_commit.py'),ref(WORK/'build_continuation.py')])
    attempts={r['unit_id']:r['prior_attempts'] for r in allowed}
    path=policy.ISSUES/(issue_row['issue_id']+'.json')
    new_json(ROOT/'preparation_attempts'/(root.name+'.json'),dict(utc=utc(),issue_id=issue_row['issue_id'],units=[r['unit_id'] for r in allowed],fix=fix,unchanged_blind_retry=False))
    policy.repair_gate(path,fix,[r['unit_id'] for r in allowed],inv['states'],available,family_exited=True,attempts_by_unit=attempts)
    run,record=instantiate(root,allowed,issue_row,fix,1)
    with (run/'stdout.log').open('xb') as so,(run/'stderr.log').open('xb') as se:
        proc=subprocess.Popen(['/usr/bin/python','-B',str(run/'code/resume_service.py')],cwd=run,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
    identity=process_identity(proc.pid)
    atomic_json(record,dict(read(record),state='spawned',process=identity,utc=utc()))
    return dict(root=str(run),process=identity)

def publish_tables(root):
    if not family(root)['exited']:return
    signature=__import__('hashlib').sha256(json.dumps([(str(r),snapshot(r/'RESULT.json'),snapshot(r/'ATTEMPT_COUNTER.json')) for r in runs(root)],sort_keys=True).encode()).hexdigest()
    marker=ROOT/'exports'/(root.name+'.json');old=snapshot(marker)
    if old.get('signature')==signature:return
    out=ROOT/'exports';out.mkdir(exist_ok=True)
    with (out/(root.name+'.log')).open('ab') as log:
        try:
            proc=subprocess.run(['/usr/bin/python','-B',str(WORK/'export_task.py'),str(root)],cwd=WORK,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2'),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=300)
            result=dict(signature=signature,exit_code=proc.returncode,utc=utc(),blocks_next_stage=False)
        except Exception as exc:result=dict(signature=signature,error=repr(exc),utc=utc(),blocks_next_stage=False)
    atomic_json(marker,result)
    if result.get('exit_code')!=0:issue(root,result,'quota_CPU_export_failure',[str(out/(root.name+'.log'))])

def serve():
    authority();LOCAL.mkdir(exist_ok=True);ROOT.mkdir(exist_ok=True)
    if read(ROOT/'CPU_CHECK.json')['status']!='passed':raise RuntimeError('CPU continuation checks required')
    with (LOCAL/'daemon.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        own=process_identity();identity=dict(hostname=own['host'],boot_id=own['boot_id'],pid=own['pid'],start_ticks=own['start_ticks'],session_id=os.getsid(own['pid']))
        new_json(ROOT/'PROCESS.json',identity)
        new_json(ROOT/'CLAIM.json',dict(task_id=TASK,run_id=JOB,process=identity,authorization_sha256=AUTH_SHA,utc=utc(),CPU_only=True,new_scientific_units=0,new_training_updates=0))
        new_json(ROOT/'WAKEUP_REGISTRATION.json',dict(job_id=JOB,task_id=TASK,revision=1,run_id=JOB,attempt=1,claim_identity=ref(ROOT/'CLAIM.json'),process_identity=identity,result_path=str(ROOT/'RESULT.json'),error_summary_path=str(ROOT/'stderr.log')))
        notify(ROOT/'WAKEUP_REGISTRATION.json');extend_CPU_wait()
        for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,stop)
        fatal=None
        while not stopping and time.time()<TABLES_DUE:
            try:
                authority();policy.timers()
                for root in [X,P]:recover_missing_terminal(root)
                running=[]
                for root in [X,P]:
                    for run in runs(root)[1:]:
                        recover_missing_terminal(run)
                        if not family(run)['exited']:running.append(str(run))
                owners=current()
                # Preserve existing healthy ownership. Even an idle scientific
                # waiter has priority over retroactive recovery of its predecessor.
                if all_original_owners_exited() and not running and time.time()<CUTOFF:
                    for root in [P,X]:
                        next_run=continuation(root)
                        if next_run:running.append(next_run['root']);break
                if not running:
                    for root in [X,P]:
                        if family(root)['exited']:publish_tables(root)
                no_runnable=not running and not any(o['alive'] and o['heartbeat'].get('status') in ['evaluate','handoff'] for o in owners)
                if no_runnable:atomic_json(ROOT/'NO_RUNNABLE_TASKS.json',dict(utc=utc(),owners=owners,reasons='No independent eligible stage right now; retain exact dependencies, issues, finite budgets and deadlines',monitoring_continues=time.time()<CUTOFF))
                atomic_json(ROOT/'HEARTBEAT.json',dict(utc=utc(),status='monitoring',process=identity,owners=owners,continuations=running,LLM_required=False,notification_failure_blocks=False,admission_cutoff=CUTOFF,tables_due=TABLES_DUE))
                if time.time()>=CUTOFF and all_original_owners_exited() and not running:break
            except BaseException as exc:
                # Unencoded faults are evidence, never an invitation to replay.
                atomic_json(ROOT/'SUPERVISION_ERROR.json',dict(utc=utc(),error=repr(exc),traceback=traceback.format_exc(),scientific_queues_unchanged=True))
                issue(ROOT,repr(exc),'quota_supervisor_exception',[str(ROOT/'SUPERVISION_ERROR.json')])
            for _ in range(15):
                if stopping:break
                time.sleep(1)
        for root in [X,P]:
            if family(root)['exited'] and all(family(r)['exited'] for r in runs(root)[1:]):publish_tables(root)
        new_json(ROOT/'RESULT.json',dict(task_id=TASK,utc=utc(),status='CPU_queue_supervision_terminal',owners=current(),continuations=[str(r) for root in [X,P] for r in runs(root)[1:]],tables=str(ROOT/'tables'),new_scientific_units=0,new_training_updates=0,unknowns_preserved=True,callback_completion_does_not_emit_event=True))
        return 0

def start():
    authority()
    if (ROOT/'CLAIM.json').exists():print('EXISTING_CPU_CLAIM_NO_RELAUNCH');return 0
    with (ROOT/'stdout.log').open('ab') as so,(ROOT/'stderr.log').open('ab') as se:
        p=subprocess.Popen(['/usr/bin/python','-B',str(WORK/'supervisor.py'),'serve'],cwd=WORK,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
    print(p.pid);return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);a=p.parse_args();sys.exit(start() if a.action=='start' else serve())
