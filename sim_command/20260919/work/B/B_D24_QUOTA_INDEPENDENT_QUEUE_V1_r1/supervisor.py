"""Append-only CPU recovery/continuation, preserving both healthy original queues."""
import argparse
import fcntl
import os
import signal
import subprocess
import time
import traceback
from pathlib import Path
import quota_runtime as q
from quota_runtime import read,snapshot,ref,sha,new_json,atomic_json,utc,process_identity

def own_decision(key,reason):
    marker=q.Q/'decisions'/(key+'.json')
    row=q.issue(reason,root=q.BASES[key])
    if not marker.exists():new_json(marker,dict(utc=utc(),issue_id=row['issue_id'],reason=reason))
    return row

def parent_owns(key):
    # The CPU successor has reserved original stage launch rights. Preserve it.
    return q.alive(q.F if key=='native' else q.P)

def last_clean(key):
    started=[r for r in q.roots(key) if (r/'CLAIM.json').exists() or (r/'LAUNCH.json').exists()]
    if started:return started[-1]
    return q.OLD_R

def prerequisites(key):
    if key=='R':return None
    s=q.gates.selection()
    if key.startswith('H'):q.gates.transfer()
    return s

def schedule(key):
    all_roots=q.roots(key)
    for root in all_roots:q.reconcile_dead(root)
    if any(q.alive(r) for r in all_roots):return dict(stage=key,status='own_stage_active')
    unsafe=[str(r) for r in all_roots if (r/'CHAIN_COMMAND.json').exists() and not q.clean_exit(r)]
    if unsafe:return dict(stage=key,status='blocked_cleanup_unknown',roots=unsafe)
    if time.time()>=q.CUTOFF:return dict(stage=key,status='admission_cutoff')
    # R24 is explicitly independent of selection and can fill the current CPU wait.
    independent_R=(key=='R' and not (q.BASES[key]/'CLAIM.json').exists() and len(all_roots)==1
        and not (q.BASES['native']/'CLAIM.json').exists()
        and snapshot(q.F/'QUEUE_HEARTBEAT.json').get('phase')=='waiting_A_scientific_selection')
    if parent_owns(key) and not independent_R:
        # Do not duplicate a healthy original scheduler or its not-yet-entered jobs.
        return dict(stage=key,status='existing_unique_parent_owns_stage')
    try:prerequisites(key)
    except (FileNotFoundError,ValueError,KeyError) as exc:
        return dict(stage=key,status='waiting_scientific_dependency',reason=str(exc))
    valid,latest,claimed,history=q.outcomes(key)
    pending=set(q.expected(key))-set(valid)
    if not pending:return dict(stage=key,status='complete_no_replay',valid=len(valid))
    capacity=q.CAPS[key]-q.stage_attempts(key)
    if capacity<=0:
        return dict(stage=key,status='stage_budget_exhausted',missing=len(pending))
    if sum((r/'CLAIM.json').exists() or (r/'LAUNCH.json').exists() for r in all_roots)>=3:
        return dict(stage=key,status='finite_continuation_cap',missing=len(pending))
    predecessor=last_clean(key)
    if not q.clean_exit(predecessor):return dict(stage=key,status='predecessor_cleanup_pending',root=str(predecessor))
    entered=[r for r in all_roots if (r/'CLAIM.json').exists() and (r/'CHAIN_COMMAND.json').exists()]
    if entered and time.time()>=min(read(r/'config/CONFIG.json')['absolute_wall_deadline_unix'] for r in entered):
        return dict(stage=key,status='original_scientific_wall_cap',missing=len(pending))
    previously_started=any((r/'LAUNCH.json').exists() or (r/'CLAIM.json').exists() for r in all_roots)
    recipe=None;issue_row=None
    if previously_started:
        text=q.collect_error(predecessor)
        previous_cfg=read(predecessor/'config/CONFIG.json')
        recipe=q.choose_recipe(text,previous_cfg.get('target_workers',24),bool(valid),bool(pending-claimed))
        issue_row=own_decision(key,'quota recovery '+q.sha(predecessor/'config/CONFIG.json')[:12]+': '+str(snapshot(predecessor/'RESULT.json').get('fatal') or snapshot(predecessor/'RESULT.json').get('reason') or 'incomplete terminal'))
        if recipe is None:return dict(stage=key,status='unknown_fault_deferred',issue=issue_row['issue_id'],missing=len(pending))
        if recipe.get('never_entered_only'):pending-=claimed
        if recipe['kind']=='restored_io':
            # Actual small frozen prerequisites must now be readable before retry.
            for file in ['config/CONFIG.json','config/BASE.json','SOURCE_INDEX.json']:read(predecessor/file)
            recipe['evidence']=[ref(predecessor/'RESULT.json'),ref(predecessor/'config/BASE.json')]
        else:recipe['evidence']=[ref(predecessor/'RESULT.json')]
        pending=set(sorted(pending)[:capacity])
        import recovery_policy
        issue_path=q.C/'nodes/B/issues'/(issue_row['issue_id']+'.json')
        if len(read(issue_path).get('attempted_repairs',[]))>=2:return dict(stage=key,status='same_fault_two_repairs_exhausted')
        recovery_policy.repair_gate(issue_path,recipe,sorted(pending),{u:'complete' for u in valid},capacity)
    if not pending:return dict(stage=key,status='no_safe_unstarted_units')
    pending=set(sorted(pending)[:capacity])
    reason='independent Q-free original R24; no selected Q dependency' if independent_R else 'original CPU parent ended; continue same authorized finite scope' if not previously_started else 'documented bounded engineering correction'
    root=q.build_wave(key,pending,predecessor,reason,recipe)
    proc=q.launch(root)
    return dict(stage=key,status='launched_once',root=str(root),pid=proc.pid,units=len(pending),recipe=recipe)

def timers():
    for path in (q.C/'nodes/B/issues').glob('B_recovery_*.json'):
        if path.name.endswith('_DECISION.json'):continue
        row=read(path);decision=snapshot(row['response_path'])
        actionable=decision.get('status') in ['released','actionable'] and decision.get('action') and (decision.get('evidence') or decision.get('authorization'))
        if not actionable and row['status']=='reported' and time.time()>=row['analysis_response_due_unix']:
            row.update(status='blocked_deferred',deferred_at=utc(),next_action='CPU quota controller continues independent eligible stages; no scientific gate bypass')
            atomic_json(path,row)

def cpu_publications():
    # Also continues after the old finite recovery monitor exits.
    if q.alive(q.C/'results/B/B_D24_AUTORECOVERY_QUEUE_RULE_V1'):return
    for root in q.all_roots():
        result=snapshot(root/'RESULT.json')
        if not result.get('publication_error') or not q.clean_exit(root):continue
        key=sha(root/'config/CONFIG.json')[:20];marker=q.Q/'publication_repairs'/(key+'.json')
        if marker.exists():continue
        text=str(result['publication_error']).lower()
        if not any(s in text for s in ['stale','input/output','filenotfound','jsondecode']):continue
        for path in ['config/CONFIG.json','config/BASE.json','SOURCE_INDEX.json']:read(root/path)
        new_json(marker,dict(status='entered_once',utc=utc(),prior_error=result['publication_error'],science_relaunch=False))
        base=read(root/'config/BASE.json')
        p=subprocess.run([base['python'],'-B',str(root/'code/publish.py')],cwd=root,capture_output=True,text=True,timeout=600,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'))
        atomic_json(marker,dict(utc=utc(),status='complete' if p.returncode==0 else 'failed',exit_code=p.returncode,stderr=p.stderr[-3000:],original_RESULT_preserved=True,science_relaunch=False))

def serve():
    q.LOCAL.mkdir(exist_ok=True);lock=(q.LOCAL/'supervisor.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    q.authority();own=process_identity();stopping=False
    def halt(*_):
        nonlocal stopping
        stopping=True
    for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,halt)
    new_json(q.Q/'CLAIM.json',dict(utc=utc(),process=own,task_id=q.TASK,run_id=q.RUN,CPU_control_plane=True))
    trigger=q.register(q.Q,own,q.TASK,q.RUN)
    new_json(q.Q/'READY.json',dict(utc=utc(),process=own,finite_dependency_wait_until=q.CUTOFF,finite_drain_end=q.DRAIN_END,trigger=trigger,original_queues_retained=True,LLM_required=False,notification_failure_blocks_science=False))
    previous=None;cycles=0;final='blocked'
    while not stopping and time.time()<q.DRAIN_END:
        try:
            q.authority();timers();rows=[]
            for key in ['native','R','H20','H30']:
                try:rows.append(schedule(key))
                except Exception as exc:
                    row=q.issue(dict(type=type(exc).__name__,message=str(exc)),root=q.BASES[key])
                    rows.append(dict(stage=key,status='engineering_issue_deferred',issue=row['issue_id'],error=str(exc)))
            cpu_publications()
            signature=[(str(r),snapshot(r/'RESULT.json').get('at_utc',snapshot(r/'RESULT.json').get('utc'))) for r in q.all_roots() if (r/'RESULT.json').exists()]
            if signature!=previous:q.publish();previous=signature
            atomic_json(q.Q/'HEARTBEAT.json',dict(utc=utc(),process=own,status='supervising',cycle=cycles,scan=rows,original_native_alive=q.alive(q.F),original_successor_alive=q.alive(q.P),science_admission_cutoff=q.CUTOFF,finite_drain_end=q.DRAIN_END))
            if not any(r['status'] in ['launched_once','own_stage_active'] for r in rows):
                atomic_json(q.Q/'NO_RUNNABLE_TASKS.json',dict(utc=utc(),rows=rows,LLM_required=False))
            if time.time()>=q.CUTOFF and not any(q.alive(r) for r in q.all_roots()):break
            if all(r['status']=='complete_no_replay' for r in rows):final='complete';break
        except Exception as exc:
            atomic_json(q.Q/'CONTROL_ERROR.json',dict(utc=utc(),error=repr(exc),traceback=traceback.format_exc(),science_not_relaunched=True))
        cycles+=1;time.sleep(15)
    summary=q.publish();unknown=[str(r) for r in q.all_roots() if (r/'CHAIN_COMMAND.json').exists() and not q.clean_exit(r)]
    new_json(q.Q/'RESULT.json',dict(utc=utc(),status='execution_unknown' if unknown else final,task_id=q.TASK,run_id=q.RUN,summary=summary,unresolved_families=unknown,all_owned_descendants_exited=not unknown,occupancy_handoff_complete=not unknown,original_scientific_results_preserved=True))
    return 0 if final=='complete' else 3

def start():
    if (q.Q/'CLAIM.json').exists():print('EXISTING_CLAIM_NO_DUPLICATE');return 0
    q.authority()
    with (q.Q/'stdout.log').open('ab') as so,(q.Q/'stderr.log').open('ab') as se:
        p=subprocess.Popen(['/usr/bin/python','-B',str(Path(__file__)),'serve'],cwd=q.Q,stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    print('SPAWNED_NOT_YET_READY',p.pid);return 0

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','serve']);args=parser.parse_args()
    raise SystemExit(start() if args.action=='start' else serve())
