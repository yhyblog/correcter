"""Only C owned receipts; no shared master edits."""
from paths import ROOT,CAMPAIGN,TASK
from qio import read,atomic_json,utc

def publish(row):
    atomic_json(CAMPAIGN/'receipts/C'/f'{TASK}_RESULT_r1.json',row)
    atomic_json(CAMPAIGN/'nodes/C/PROGRESS.json',row)

def running_receipt(stable):
    publish(dict(task_id=TASK,revision=1,node='C',status='running',utc=utc(),claim=str(ROOT/'CLAIM.json'),
        process=str(ROOT/'PROCESS.json'),heartbeat=str(ROOT/'HEARTBEAT.json'),stable_handoff=str(ROOT/'STABLE_HANDOFF.json') if stable else None,
        scope='frozen X heads; new R/Post/Velocity G0-multi500each',
        whole_wave_holders='all off until formal descendants exit',old_completed_replays=0,
        notification_registration=str(ROOT/'WAKEUP_REGISTRATION.json'),prior_actual_attempts=10443,stage_attempt_cap=1650,
        cumulative_cap=14000,new_optimizer_updates=0,new_collection_attempts=0,N_reruns=0))

def terminal_receipt():
    result=read(ROOT/'RESULT.json');summary=read(ROOT/'FINAL_SUMMARY.json') if (ROOT/'FINAL_SUMMARY.json').exists() else None
    publish(dict(task_id=TASK,revision=1,node='C',utc=utc(),status=result['status'],result=str(ROOT/'RESULT.json'),summary=str(ROOT/'FINAL_SUMMARY.json'),
        all_owned_descendants_exited=result['all_owned_descendants_exited'],occupancy_handoff_complete=result.get('occupancy_handoff_complete'),
        attempts=summary.get('attempts') if summary else None,new_optimizer_updates=0,new_collection_attempts=0,N_reruns=0,
        cumulative_C_attempts=10443+summary['attempts'] if summary else None,old_completed_replays=0))
