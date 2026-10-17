"""Finite CPU receipt publisher. It never launches science or emits wakeups."""
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path
import d24_common as d

TASK='C_D24_R_H40_H50_V1'
ROOT=d.C/'results/C'/TASK
RUN=ROOT/'r2'
STATE=RUN/'receipt_observer'
RECEIPTS=d.C/'receipts/C'

def publish_running(stable):
    p=RECEIPTS/(TASK+'_RUNNING.json')
    current=d.load(p) if p.exists() else {}
    current.update(task_id=TASK,revision=1,startup_revision=2,at_utc=d.utc(),
        status='stable_background_running' if stable else 'background_r2_startup',
        results=str(RUN),claim=str(RUN/'CLAIM.json'),supervisor=d.load(RUN/'PROCESS.json'),
        wakeup_registration=str(d.C/'persistent_queue/nodes/C/wakeup/jobs/D24_C_R_H40_H50_r2.json'),
        source_protocol=str(RUN/'NUMERICAL_BINDING.md'),startup_repair=str(RUN/'STARTUP_REPAIR.json'),
        frozen_science_CPU_check=str(RUN/'CPU_CHECK.json'),
        handoff_evidence=str(RUN/'chain/HOLDER_EXIT_ACK.json'),
        stable_handoff=str(RUN/'STABLE_HANDOFF.json') if stable else None,
        snapshot=d.load(RUN/'HEARTBEAT.json') if (RUN/'HEARTBEAT.json').exists() else None)
    d.atomic(p,current)
    ack=RECEIPTS/(TASK+'_ACK.json');a=d.load(ack)
    a.update(status=current['status'],startup_revision=2,claim=str(RUN/'CLAIM.json'),running_receipt=str(p))
    d.atomic(ack,a)
    d.atomic(ROOT/'LATEST_RUN.json',dict(task_id=TASK,revision=2,results=str(RUN),status=current['status'],
        previous_startup_terminal=str(ROOT/'RESULT.json')))
    d.atomic(d.C/'nodes/C/PROGRESS.json',dict(task_id=TASK,at_utc=d.utc(),status=current['status'],
        receipt=str(p),heartbeat=str(RUN/'HEARTBEAT.json')))

def serve():
    STATE.mkdir(exist_ok=True)
    d.exclusive(STATE/'CLAIM.json',dict(process=d.identity(),utc=d.utc(),CPU_only=True,scientific_launches=0,wakeup_events=0))
    cfg=d.load(RUN/'config/CONFIG.json')
    deadline=datetime.datetime.fromisoformat(cfg['stage_wall_deadline_utc']).timestamp()+600
    published=False;initial=False
    while time.time()<deadline:
        if (RUN/'PROCESS.json').exists() and not initial:
            publish_running(False);initial=True
        stable=(RUN/'STABLE_HANDOFF.json').exists()
        if stable and not published:
            publish_running(True);published=True
        if (RUN/'RESULT.json').exists() and not d.alive(d.load(RUN/'PROCESS.json')):
            result=d.load(RUN/'RESULT.json');summary=d.load(RUN/'SUMMARY.json') if (RUN/'SUMMARY.json').exists() else None
            old=d.load(ROOT/'RESULT.json')
            record=dict(task_id=TASK,revision=1,startup_revision=2,at_utc=d.utc(),
                status=result['status'],terminal_result=str(RUN/'RESULT.json'),summary=summary,
                results=str(RUN),claim=str(RUN/'CLAIM.json'),
                all_owned_descendants_exited=result.get('all_owned_descendants_exited'),
                occupancy_handoff_complete=result.get('occupancy_handoff_complete'),
                startup_failure=dict(result=str(ROOT/'RESULT.json'),entered_sources=0,
                    sampled_policy_plans=0,elapsed_seconds=old['elapsed_seconds'],model_loads=8,
                    repair=str(RUN/'STARTUP_REPAIR.json')),
                cumulative_budget_reset=False,stage_wall_budget_reset=False,
                prior_Velocity_N_Post_replays=0,callback_audit_and_ACK='pending original handler',
                artifacts={n:str(RUN/n) for n in ['EPISODES.csv','TASK_RESULTS.csv','PAIRED_COMPARISONS.csv','REPORT.md']},
                scientific_launches_by_observer=0,wakeup_events_by_observer=0)
            d.atomic(RECEIPTS/(TASK+'_RESULT.json'),record)
            d.atomic(STATE/'RESULT.json',dict(status='published_terminal_receipt',utc=d.utc(),scientific_launches=0,wakeup_events=0))
            return
        d.atomic(STATE/'HEARTBEAT.json',dict(process=d.identity(),utc=d.utc(),status='observing',stable=stable,scientific_launches=0,wakeup_events=0))
        time.sleep(15)
    d.atomic(STATE/'RESULT.json',dict(status='bounded_observer_deadline',utc=d.utc(),scientific_launches=0,wakeup_events=0))

if __name__=='__main__':
    STATE.mkdir(exist_ok=True)
    if sys.argv[1]=='start':
        if (STATE/'CLAIM.json').exists():
            print('EXISTING_OBSERVER_NO_RESTART')
        else:
            with (STATE/'observer.log').open('ab') as f:
                p=subprocess.Popen(['/usr/bin/python','-B',__file__,'serve'],stdin=subprocess.DEVNULL,
                    stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
            print(json.dumps(d.identity(p.pid)))
    else:serve()
