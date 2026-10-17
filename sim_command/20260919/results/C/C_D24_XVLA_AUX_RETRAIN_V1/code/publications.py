"""C own receipts; shared dispatch and other nodes remain read-only."""
from paths import ROOT,CAMPAIGN,TASK
from qio import read,atomic_json,utc
def running_receipt(stable):
    row=dict(task_id=TASK,revision=1,node='C',status='running',utc=utc(),claim=str(ROOT/'CLAIM.json'),
        process=str(ROOT/'PROCESS.json'),heartbeat=str(ROOT/'HEARTBEAT.json'),stable_handoff=str(ROOT/'STABLE_HANDOFF.json') if stable else None,
        authorized_chain=['collect','D2/G02/Q4 train from scratch','new R/Post/Velocity500each'],
        whole_wave_holders='all off until formal descendants exit',old_completed_replays=0,
        notification_registration=str(ROOT/'WAKEUP_REGISTRATION.json'),prior_actual_attempts=7013,stage_attempt_cap=4000,updates_cap=32000)
    atomic_json(CAMPAIGN/'receipts/C'/f'{TASK}_RESULT_r1.json',row)
    atomic_json(CAMPAIGN/'nodes/C/PROGRESS.json',row)
def terminal_receipt():
    result=read(ROOT/'RESULT.json');summary=read(ROOT/'FINAL_SUMMARY.json') if (ROOT/'FINAL_SUMMARY.json').exists() else None
    row=dict(task_id=TASK,revision=1,node='C',utc=utc(),status=result['status'],result=str(ROOT/'RESULT.json'),summary=str(ROOT/'FINAL_SUMMARY.json'),
        all_owned_descendants_exited=result['all_owned_descendants_exited'],occupancy_handoff_complete=result.get('occupancy_handoff_complete'),
        attempts=summary.get('attempts') if summary else None,fit_updates=summary.get('fit_updates') if summary else None,
        cumulative_C_attempts=7013+summary['attempts'] if summary else None,old_completed_replays=0)
    atomic_json(CAMPAIGN/'receipts/C'/f'{TASK}_RESULT_r1.json',row);atomic_json(CAMPAIGN/'nodes/C/PROGRESS.json',row)
