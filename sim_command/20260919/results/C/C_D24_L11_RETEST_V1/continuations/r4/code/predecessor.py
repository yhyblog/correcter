"""Read-only finite host-scoped predecessor wait; no signal or GPU calls."""
import time
from pathlib import Path
from paths import ROOT
from qio import read,new_json,atomic_json,utc,process_identity,same_process,ref
from admission import authority,before_cutoff,AdmissionClosed
from process_family import group_members

def wait_for_exit():
    plan=read(ROOT/'RECOVERY_PLAN.json');previous=Path(plan['previous_run_root'])
    while before_cutoff():
        authority()
        owner=read(previous/'PROCESS.json');owner['host']=owner['hostname']
        terminal=read(previous/'RESULT.json') if (previous/'RESULT.json').exists() else None
        if terminal and not same_process(owner):
            manager=read(previous/'chains/evaluate/MANAGER_STARTED.json')['process']
            if not same_process(manager) and not group_members(manager['pgid'],manager['pid']):
                if not terminal.get('all_owned_descendants_exited') or not terminal.get('occupancy_handoff_complete'):raise RuntimeError('predecessor did not resolve complete occupancy exit')
                units=read(ROOT/'UNIT_INDEX.json')
                if any((previous/'claims/units'/(u['storage_key']+'.json')).exists() for u in units):raise RuntimeError('PI owner overlap; no replay')
                n=read(previous/'ATTEMPT_COUNTER.json')['count'] if (previous/'ATTEMPT_COUNTER.json').exists() else 0
                prior=640+n
                if prior+len(units)>2750:raise RuntimeError('remaining full PI queue exceeds budget')
                result=dict(utc=utc(),previous_terminal=ref(previous/'RESULT.json'),previous_claim=ref(previous/'CLAIM.json'),all_previous_formal_exited=True,occupancy_restored=True,prior_task_attempts=prior,remaining_units=len(units),maximum_cumulative_attempts=prior+len(units),new_GPU_calls=0)
                new_json(ROOT/'DEPENDENCY_EXIT.json',result);return result
        atomic_json(ROOT/'HEARTBEAT.json',dict(utc=utc(),status='CPU_predecessor_wait',previous_run=str(previous),previous_owner_alive=same_process(owner),new_GPU_calls=0,queued_PI_units=1500,no_LLМ_dependency=True))
        time.sleep(15)
    raise AdmissionClosed('cutoff reached before predecessor exit; no GPU entry')
