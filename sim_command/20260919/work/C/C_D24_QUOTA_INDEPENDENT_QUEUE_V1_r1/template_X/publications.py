"""C-owned receipts only, including waiting on the scientific selection dependency."""
from paths import ROOT,CAMPAIGN,TASK
from qio import read,atomic_json,utc

def publish(status,**extra):
    row=dict(task_id=TASK,revision=1,node='C',status=status,utc=utc(),claim=str(ROOT/'CLAIM.json'),
        process=str(ROOT/'PROCESS.json'),heartbeat=str(ROOT/'HEARTBEAT.json'),
        candidates=str(ROOT/'CANDIDATES_READY.json'),stable_handoff=str(ROOT/'STABLE_HANDOFF.json'),
        notification_registration=str(ROOT/'WAKEUP_REGISTRATION.json'),prior_actual_attempts=11943,
        planned_first_evaluations=1000,stage_attempt_cap=1100,cumulative_cap=14000,
        new_optimizer_update_cap=64000,new_collection=0,D_G0_updates=0,N_R_reruns=0,
        evaluation_workers=24,workers_per_GPU=3,whole_wave_holders='all off until entire formal family exits',**extra)
    atomic_json(CAMPAIGN/'receipts/C'/f'{TASK}_RESULT_r1.json',row)
    atomic_json(CAMPAIGN/'nodes/C/PROGRESS.json',row)

def terminal_receipt():
    result=read(ROOT/'RESULT.json')
    publish(result['status'],result=str(ROOT/'RESULT.json'),all_owned_descendants_exited=result.get('all_owned_descendants_exited'),
        occupancy_handoff_complete=result.get('occupancy_handoff_complete'),summary=str(ROOT/'FINAL_SUMMARY.json'))
