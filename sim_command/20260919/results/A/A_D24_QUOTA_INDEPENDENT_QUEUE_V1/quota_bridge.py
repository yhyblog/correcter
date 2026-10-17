"""CPU-only final dependency/export/unknown-issue bridge, no LLM launch gate."""
import argparse
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CAMPAIGN=ROOT.parents[2]
RECOVERY=ROOT.parent/'A_D24_AUTORECOVERY_QUEUE_RULE_V1'
LIVE=ROOT.parent/'A_D24_FULL_Q_AUTORUN_POST_LED_V1'
ORIGINAL=ROOT.parent/'A_D24_FULL_Q_LOSS_SELECTION_V1'
sys.path.insert(0,str(RECOVERY/'code'))
from qio import read,new_json,atomic_json,utc,ref,sha,process_identity,same_process
from policy import new_issue,update_issue,wave_state,ISSUES,THREAD,ANALYSIS_THREAD

GRANT=CAMPAIGN/'deadline_20260924/QUOTA_INDEPENDENT_AUTORUN_AUTHORIZATION_V1.json'
GRANT_SHA='651a1b85faf16e3d13e0a722f1253fc465f5fcbeeab99b692f51f674de30af98'
TABLES_END=1790175600  # 2026-09-23 15:00 UTC; CPU only, not scientific extension.


def authority():
    if sha(GRANT)!=GRANT_SHA:raise ValueError('quota directive changed')
    grant=read(GRANT)
    import socket
    if grant['status']!='released' or grant['nodes']['A']['host']!=socket.gethostname():raise ValueError('host/status mismatch')
    if sha(CAMPAIGN/grant['rule']['path'])!=grant['rule']['sha256']:raise ValueError('quota rule changed')
    return grant


def alive_record(path):
    if not path.exists():return False
    row=read(path);return bool(row.get('process') and same_process(row['process']))


def unknown_fault_to_issue(root,state):
    """No Codex response is needed to start the fixed 1800s timeout."""
    final=state.get('final') or {}
    if not final or final.get('compute_complete'):return None
    marker=ROOT/'faults'/(Path(root).name+'.json')
    if marker.exists():return read(marker)['issue_id']
    error=final.get('fatal') or (state.get('manager_exit') or {}).get('fatal') or dict(message='incomplete finite queue; inspect missing units, no known safe general repair')
    issue_id='A_Q_QUOTA_'+Path(root).name
    candidates=[str(p) for p in (RECOVERY/'candidates').glob('*.json')]
    issue=new_issue(issue_id,task='A_D24_FULL_Q_AUTORUN_HANDOFF_V2',units=[],
        error=error,attempted_fixes=['Already encoded compatible grant admission, deterministic Post selector, immutable handoff paths, CPU-only serialization null/identity handling, bounded publication retries.'],
        decision_needed='Unrecognized fault is preserved; do not require LLM to keep independent authorized tasks moving. Any scientific prerequisite still needs a concrete decision.',
        blocked_tasks=[str(root)],runnable_tasks=candidates,evidence=[str(Path(root)/'RESULT.json'),str(Path(root)/'chain/MANAGER_EXIT.json')])
    new_json(marker,dict(utc=utc(),issue_id=issue_id,issue_path=str(ISSUES/(issue_id+'.json')),scientific_relaunch=False))
    # Existing recovery transport is optional. The persistent issue and timer
    # exist before transport; no callback is ever awaited here.
    from transport import emit
    emit('A_D24_AUTORECOVERY_QUEUE_RULE_V1_'+issue_id+'_analysis','analysis_issue',dict(issue=str(ISSUES/(issue_id+'.json'))),analysis=True)
    return issue_id


def timers_and_candidates(now):
    statuses=[]
    old_alive=alive_record(RECOVERY/'DAEMON_READY.json') and not (RECOVERY/'DAEMON_EXIT.json').exists()
    for p in sorted(ISSUES.glob('*.json')):
        if p.name.endswith('.decision.json'):continue
        row=read(p)
        if row.get('owner')!='A' or 'analysis_response_due_at' not in row:continue
        decision_path=p.with_name(p.stem+'.decision.json')
        decision=read(decision_path) if decision_path.exists() else None
        updated=update_issue(row,decision,now)
        if not old_alive and updated!=row:atomic_json(p,updated)
        statuses.append(dict(issue_id=row['issue_id'],status=updated['status'],due=row['analysis_response_due_at']))
    attempts=[]
    if not old_alive:
        # Same registered consumer and launch lock, not another scientific
        # scheduler. Deadline, selection and budget checks remain mandatory.
        from next_stage import consume
        for p in sorted((RECOVERY/'candidates').glob('*.json')):
            try:attempts.append(consume(p))
            except Exception as e:attempts.append(dict(candidate=str(p),blocked_reason=str(e)))
    return dict(primary_recovery_supervisor_alive=old_alive,issues=statuses,candidate_scan=attempts)


def remaining_table():
    p=LIVE/'SUMMARY.json';rows=[]
    if p.exists():
        summary=read(p)
        for key,c in summary.get('cells',{}).items():
            if not c.get('full_cell_complete'):
                rows.append(dict(cell_id=key,planned=c.get('planned_episodes'),valid=c.get('terminals'),
                    unstarted=c.get('unstarted'),technical=c.get('technical_failures'),
                    missing_reason='pending_or_technical; outcomes not coerced to success=false'))
    else:rows=[dict(missing_reason='no committed summary yet')]
    atomic_json(ROOT/'MISSING_UNITS_BY_CELL.json',dict(utc=utc(),summary_path=str(p),rows=rows,scientific_compute=0))


def late_merge(previous_signature):
    # The running original observer remains the sole table updater. This
    # extends only CPU dependency waiting after that finite observer exits.
    old=LIVE/'QUEUE_READY.json'
    if alive_record(old) and not (LIVE/'QUEUE_EXIT.json').exists():return previous_signature,dict(status='existing_CPU_observer_owns_exports')
    sources=[LIVE/'MAIN_CELLS.csv']
    for node,task in [('B','B_D24_PI05_SELECTED_H20_H30_V1'),('C','C_D24_PI05_SELECTED_H40_H50_V1')]:
        r=CAMPAIGN/'results'/node/task
        f=r/'MAIN_CELLS.csv';sources.append(f if f.exists() else r/'FINAL_CELLS.csv')
    signature=[]
    for p in sources:
        if p.exists():s=p.stat();signature.append((str(p),s.st_size,s.st_mtime_ns))
    if signature==previous_signature:return signature,dict(status='unchanged_sources')
    base=read(LIVE/'config/BASE.json')
    try:
        r=subprocess.run([base['python'],'-B',str(LIVE/'code/merge_remote.py')],cwd=LIVE,
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
        result=dict(utc=utc(),exit_code=r.returncode,stdout=r.stdout[-2000:],stderr=r.stderr[-4000:],scientific_compute=0)
    except Exception as e:result=dict(utc=utc(),publication_error=str(e),scientific_compute=0)
    atomic_json(ROOT/'LATE_MERGE_LAST_RESULT.json',result)
    return signature,result


def serve():
    authority();local=Path('/tmp/corrector_A_quota_independent_v1');local.mkdir(exist_ok=True)
    lock=(local/'bridge.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    own=process_identity();stop=False
    def stopping(*_):
        nonlocal stop
        stop=True
    for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,stopping)
    new_json(ROOT/'CPU_BRIDGE_READY.json',dict(utc=utc(),process=own,host=own['host'],CPU_only=True,
        scientific_queue_reused=str(LIVE),LLM_required=False,callback_failure_blocks_science=False,
        CPU_wait_end_unix=TABLES_END,scientific_deadline_unchanged=True,code=ref(ROOT/'quota_bridge.py')))
    signature=None;last_merge=0
    while not stop and time.time()<TABLES_END:
        now=time.time()
        try:
            authority();registry=read(RECOVERY/'REGISTRY.json');states=[]
            for root in registry['wave_roots']:
                s=wave_state(root)
                if s['confirmed_formal_exit']:unknown_fault_to_issue(root,s)
                states.append(dict(root=root,state=s['state'],confirmed_formal_exit=s['confirmed_formal_exit'],daemon_alive=s['daemon_alive'],stage=s['progress'].get('stage')))
            rules=timers_and_candidates(now)
            remaining_table()
            publication=None
            if now-last_merge>=120:
                signature,publication=late_merge(signature);last_merge=now
            atomic_json(ROOT/'HEARTBEAT.json',dict(utc=utc(),process=own,states=states,recovery=rules,
                publication=publication,LLM_required=False,callback_failure_blocks_science=False,
                science_admissions_added_by_control_task=0,priority_changed=False))
        except Exception as e:
            atomic_json(ROOT/'CPU_BRIDGE_ERROR.json',dict(utc=utc(),type=type(e).__name__,message=str(e),scientific_processes_unaffected=True))
        time.sleep(30)
    new_json(ROOT/'CPU_BRIDGE_EXIT.json',dict(utc=utc(),process=own,reason='CPU_stop' if stop else 'tables_deadline',scientific_signals=0))
    return 0


def start():
    authority();ready=ROOT/'CPU_BRIDGE_READY.json'
    if ready.exists():
        if alive_record(ready):print('EXISTING_CPU_BRIDGE',read(ready)['process']['pid']);return 0
        raise RuntimeError('previous bridge record exists; no duplicate automatic start')
    local=Path('/tmp/corrector_A_quota_independent_v1');local.mkdir(exist_ok=True)
    with (local/'start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if (ROOT/'SPAWN.json').exists():raise RuntimeError('existing spawn opportunity')
        with (ROOT/'stdout.log').open('ab') as out,(ROOT/'stderr.log').open('ab') as err:
            p=subprocess.Popen(['/usr/bin/python','-B',str(ROOT/'quota_bridge.py'),'serve'],cwd=ROOT,
                stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
        new_json(ROOT/'SPAWN.json',dict(utc=utc(),process=process_identity(p.pid),not_readiness=True,CPU_only=True))
        print('CPU_BRIDGE_SPAWNED_NOT_READY',p.pid)
    return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','serve']);args=parser.parse_args()
    sys.exit(start() if args.action=='start' else serve())
