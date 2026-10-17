"""C-owned status records; no notification dispatch or scientific launch."""
from paths import ROOT, CAMPAIGN
from qio import read, atomic_json, utc

TASK='C_D24_R_TRIGGER_MODES_V1'


def running_receipt(stable=False):
    p=CAMPAIGN/'receipts/C'/(TASK+'_RUNNING.json')
    record=dict(task_id=TASK,revision=1,at_utc=utc(),status='stable_background_running' if stable else 'background_starting',
                results=str(ROOT),claim=str(ROOT/'CLAIM.json'),supervisor=read(ROOT/'PROCESS.json'),planned_episodes=5000,
                prior_C_attempts=2013,stage_attempt_cap=5500,cumulative_attempt_cap=7900,target_concurrency=8,
                wakeup_registration=str(ROOT/'WAKEUP_REGISTRATION.json'),method_frozen=str(ROOT/'METHOD_FROZEN.json'),
                CPU_check=str(ROOT/'CPU_CHECK.json'),stable_handoff=str(ROOT/'STABLE_HANDOFF.json') if stable else None,
                old_completed_sources_replayed=0,holder_policy='all holders off entire formal wave',
                executor_thread_id='01a0c793-10d2-7791-a250-fd65d88e1ccb')
    atomic_json(p,record)
    ap=CAMPAIGN/'receipts/C'/(TASK+'_ACK.json');ack=read(ap)
    ack.update(status=record['status'],running_receipt=str(p),claim=record['claim']);atomic_json(ap,ack)
    atomic_json(CAMPAIGN/'nodes/C/PROGRESS.json',dict(task_id=TASK,at_utc=utc(),status=record['status'],receipt=str(p),heartbeat=str(ROOT/'HEARTBEAT.json')))


def terminal_receipt():
    result=read(ROOT/'RESULT.json')
    p=CAMPAIGN/'receipts/C'/(TASK+'_RESULT.json')
    record=dict(task_id=TASK,revision=1,at_utc=utc(),status=result['status'],terminal_result=str(ROOT/'RESULT.json'),
                results=str(ROOT),claim=str(ROOT/'CLAIM.json'),summary=read(ROOT/'SUMMARY.json') if (ROOT/'SUMMARY.json').exists() else None,
                callback_audit_and_ACK='pending original handler',all_owned_descendants_exited=result.get('all_owned_descendants_exited'),
                occupancy_handoff_complete=result.get('occupancy_handoff_complete'),old_completed_sources_replayed=0,
                artifacts={name:str(ROOT/name) for name in ['METHOD_FROZEN.json','FINAL_CELLS.csv','FINAL_EPISODES.csv','INTERVENTIONS.csv','FINAL_PAIRED.csv','RESOURCE_SUMMARY.json','REPORT.md']})
    atomic_json(p,record)
    atomic_json(CAMPAIGN/'nodes/C/PROGRESS.json',dict(task_id=TASK,at_utc=utc(),status='terminal_pending_audit',receipt=str(p),terminal_result=str(ROOT/'RESULT.json')))
