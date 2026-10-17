"""Finite CPU sidecar: no scientific subprocess except validated next-stage entry."""
import argparse
import fcntl
import os
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path
from policy import (ROOT,CAMPAIGN,ISSUES,ORIGINAL,LIVE,TASK,GRANT_SHA,POST_SHA,THREAD,
                    authority,update_issue,wave_state,fault_kind,safe_id,iso,new_issue)
from qio import read,new_json,atomic_json,utc,process_identity,same_process,ref
from transport import emit,pump


def scan_issues(now):
    rows=[]
    for p in sorted(ISSUES.glob('*.json')):
        if p.name.endswith('.decision.json'):continue
        try:row=read(p)
        except Exception as e:
            rows.append(dict(issue_path=str(p),status='issue_metadata_unreadable',error=str(e)))
            continue
        if row.get('owner')!='A' or 'analysis_response_due_at' not in row:continue
        decision_path=p.with_name(p.stem+'.decision.json')
        decision=read(decision_path) if decision_path.exists() else None
        updated=update_issue(row,decision,now)
        if updated!=row:
            atomic_json(p,updated)
            if updated['status']=='blocked_deferred':
                emit(TASK+'_'+p.stem+'_deferred','issue_timeout',dict(issue=ref(p),next='scan independent authorized candidates now'))
            elif updated['status']=='decision_received_pending_safe_boundary':
                emit(TASK+'_'+p.stem+'_decision','actionable_decision',dict(issue=ref(p),no_interruption_of_healthy_work=True))
        emit(TASK+'_'+p.stem+'_analysis','analysis_issue',dict(issue=str(p)),analysis=True)
        rows.append(dict(issue_id=row['issue_id'],status=updated['status'],due=row['analysis_response_due_at']))
    return rows


def fault_event(root,state):
    marker=ROOT/'snapshots'/(safe_id(Path(root).name)+'_terminal_or_missing.json')
    if marker.exists():return
    final=state.get('final') or {}
    new_json(marker,dict(utc=utc(),state=state,scientific_compute_added=0))
    failed=not final.get('compute_complete',False)
    if failed:
        message=str(final.get('fatal') or (state.get('manager_exit') or {}).get('fatal') or final.get('status') or 'daemon missing without terminal')
        kind=fault_kind(message)
        if kind in ['scientific_decision','authorization_or_budget']:
            issue_id='A_Q_RECOVERY_'+Path(root).name
            new_issue(issue_id,task='A_D24_FULL_Q_AUTORUN_HANDOFF_V2',units=[],error=message,
                attempted_fixes=[],decision_needed='Resolve scientific prerequisite or budget/cutoff; do not bypass selection.',
                blocked_tasks=['selected_Q_followups'],runnable_tasks=['independent_authorized_CPU_work_if_ready'],
                evidence=[str(marker)])
        emit(TASK+'_'+Path(root).name+'_repair','engineering_recovery_required' if kind.endswith('engineering') or kind=='engineering_diagnosis' else 'decision_required',
            dict(snapshot=str(marker),fault_class=kind,action='Privately diagnose exact error, preserve lawful terminals including success=false, inspect terminal logs, register filtered repair candidate. No new approval is needed inside scope.',
                 candidate_interface=str(ROOT/'CONSUMER_INTERFACE.json'),max_documented_same_fault_repairs=2))
    else:
        emit(TASK+'_'+Path(root).name+'_complete','complete_scan_next',dict(snapshot=str(marker),new_scientific_scope=False))


def serve():
    authority();local=Path('/tmp/corrector_A_autorecovery_v1');local.mkdir(exist_ok=True)
    lock=(local/'supervisor.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    ready=ROOT/'DAEMON_READY.json'
    if ready.exists():raise RuntimeError('existing control daemon record; do not silently replay')
    own=process_identity();end=read(ROOT/'REGISTRY.json')['observer_end_unix'];stop=False
    def request_stop(*_):
        nonlocal stop
        stop=True
    for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,request_stop)
    new_json(ready,dict(utc=utc(),task_id=TASK,status='CPU_DAEMON_READY',process=own,
        authorization_sha256=GRANT_SHA,Post_override_sha256=POST_SHA,end_unix=end,
        consumed_rule=True,independent_of_Codex_window=True,callback_thread=THREAD,
        CPU_only=True,live_scientific_package_modified=False,scientific_claim_created=False,
        consumer=ref(ROOT/'CONSUMER_INTERFACE.json'),code=ref(ROOT/'CODE_MANIFEST.json')))
    seen_alive=set();last_signatures={};last_pump=0
    while not stop and time.time()<end:
        now=time.time();authority();registry=read(ROOT/'REGISTRY.json')
        issues=scan_issues(now);states=[];changed=False
        for root in registry['wave_roots']:
            state=wave_state(root);states.append(state)
            sig=(state['state'],state['confirmed_formal_exit'],state['progress'].get('stage'))
            changed|=last_signatures.get(root)!=sig;last_signatures[root]=sig
            if state['daemon_alive']:seen_alive.add(root)
            if state['confirmed_formal_exit'] or (root in seen_alive and not state['daemon_alive']):fault_event(root,state)
        alive=any(not s['confirmed_formal_exit'] for s in states)
        pending=[];consumed=[]
        # Completion/failure, dependency changes and expiry are observed at most
        # 15s later. Ready independent tasks do not wait for an issue deadline.
        for p in sorted((ROOT/'candidates').glob('*.json')):
            try:candidate=read(p);cid=safe_id(candidate['candidate_id'])
            except Exception as e:
                pending.append(dict(path=str(p),reason='malformed_candidate: '+str(e)))
                continue
            if (ROOT/'launches'/cid/'LAUNCH_INTENT.json').exists():continue
            if alive:
                pending.append(dict(candidate_id=cid,reason='current_formal_wave_owns_followup_units'))
                continue
            try:
                from next_stage import consume
                result=consume(p)
                if result.get('consumed'):
                    consumed.append(result);alive=True
                else:pending.append(result)
            except Exception as e:
                pending.append(dict(candidate_id=cid,reason=str(e)))
                marker=ROOT/'snapshots'/(cid+'_admission_failure.json')
                if not marker.exists():
                    new_json(marker,dict(utc=utc(),candidate=ref(p),error=dict(type=type(e).__name__,message=str(e)),no_launch=True))
                    emit(TASK+'_'+cid+'_admission_failure','repair_admission_blocked',dict(evidence=str(marker)))
        hb=dict(utc=utc(),task_id=TASK,process=own,status='WATCHING_HEALTHY_OR_OWNED_WAVE' if alive else 'SCANNING_AUTHORIZED_FOLLOWUPS',
            actual_scientific_states=[{k:s[k] for k in ['root','state','daemon_alive','confirmed_formal_exit','heartbeat_utc','progress']} for s in states],
            issues=issues,pending_candidates=pending,consumed_candidates=consumed,
            scan_reason='completion_failure_or_dependency_change' if changed else 'bounded_dependency_and_deadline_timer',
            live_priority_unchanged=True,scientific_compute_added_by_control_task=0,observer_end_unix=end)
        atomic_json(ROOT/'HEARTBEAT.json',hb)
        if not (ROOT/'STABLE_HANDOFF.json').exists():
            new_json(ROOT/'STABLE_HANDOFF.json',dict(utc=utc(),status='CPU_SIDECAR_DEPLOYED',process=own,
                scientific_state_snapshot=hb['actual_scientific_states'],issue_timer_seconds=1800,
                real_failure_recovery_tested=False,CPU_checks=ref(ROOT/'CPU_CHECK.json'),
                callback_event_path=str(ROOT/'outbox'),registered_original_thread=THREAD,
                consumer_ready=True,no_healthy_chain_restart=True))
        if not alive and not consumed:
            no=dict(utc=utc(),status='NO_RUNNABLE_TASKS',issues=issues,candidates=pending,
                barriers=['No registered independent ready A-owned package beyond the finite current scope.'] if not pending else [r.get('reason') for r in pending],
                task_dispositions=[dict(task_id='A_D24_FULL_Q_AUTORUN_HANDOFF_V2',root=s['root'],
                    status='complete' if (s.get('final') or {}).get('compute_complete') else 'requires_eligible_unit_reconciliation_and_private_fix',
                    raw_terminal_status=(s.get('final') or {}).get('status'),
                    family_exit_confirmed=s['confirmed_formal_exit']) for s in states],
                excluded_scopes=['cancelled_Random_multi','remaining475','completed_training','B_C_owned_MAIN'],
                retained_dependency_monitor=True,no_fabricated_GPU_work=True)
            atomic_json(ROOT/'NO_RUNNABLE_TASKS.json',no)
            if not (ROOT/'outbox'/(TASK+'_no_runnable.json')).exists():
                emit(TASK+'_no_runnable','no_runnable_tasks',dict(evidence=str(ROOT/'NO_RUNNABLE_TASKS.json')),analysis=True)
        if now-last_pump>=30:
            pump();last_pump=now
        time.sleep(15)
    new_json(ROOT/'DAEMON_EXIT.json',dict(utc=utc(),process=own,reason='requested_CPU_stop' if stop else 'bounded_deadline',
        scientific_signals=0,holder_actions=0,scientific_processes_unaffected=True))
    return 0


def start():
    authority();ready=ROOT/'DAEMON_READY.json'
    if ready.exists():
        row=read(ready)
        if same_process(row['process']):print('EXISTING_CPU_SUPERVISOR',row['process']['pid']);return 0
        raise RuntimeError('old CPU supervisor exited; preserve record and reconcile')
    local=Path('/tmp/corrector_A_autorecovery_v1');local.mkdir(exist_ok=True)
    with (local/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if (ROOT/'SPAWN.json').exists():raise RuntimeError('existing spawn; no duplicate control service')
        with (ROOT/'stdout.log').open('ab') as out,(ROOT/'stderr.log').open('ab') as err:
            proc=subprocess.Popen(['/usr/bin/python','-B',str(ROOT/'code/supervisor.py'),'serve'],cwd=ROOT,
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,
                stdout=out,stderr=err,start_new_session=True)
        new_json(ROOT/'SPAWN.json',dict(utc=utc(),process=process_identity(proc.pid),CPU_only=True,not_readiness=True))
        print('CPU_SUPERVISOR_SPAWNED_NOT_READY',proc.pid)
    return 0


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);args=p.parse_args()
    try:sys.exit(start() if args.action=='start' else serve())
    except Exception as e:
        atomic_json(ROOT/'SUPERVISOR_ERROR.json',dict(utc=utc(),type=type(e).__name__,message=str(e),traceback=traceback.format_exc(),scientific_signals=0))
        raise
