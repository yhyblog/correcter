"""Finite control-plane cancellation at the existing per-source admission lock."""
from pathlib import Path
import sys,fcntl,os,signal,time,json
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
OLD=C/'results/C/C_D24_XVLA_MULTI_EVAL_V1';WAVE=OLD/'concurrency24_r1'
NEW=C/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1'
sys.path.insert(0,str(OLD/'code'))
from qio import read,new_json,atomic_json,ref,utc,process_identity,same_process
from process_family import group_members

def main():
    new_json(NEW/'evidence/CANCELLATION_CONTROLLER_PROCESS.json',process_identity())
    proc=read(WAVE/'PROCESS.json');expected=dict(proc,host=proc['hostname'])
    manager=read(WAVE/'chain/MANAGER_STARTED.json')['process']
    with Path('/tmp/corrector_C_XVLA_MULTI_r1/attempts.lock').open('a') as gate:
        # No scientific counter or claim is fabricated. Current episodes do not
        # need this lock again until their next source, so they can finish.
        fcntl.flock(gate,fcntl.LOCK_EX)
        effective=utc();counter=read(OLD/'ATTEMPT_COUNTER.json')
        claims=[read(p) for p in (OLD/'claims/attempts').glob('*.json')]
        expected_paths=[OLD/'evaluation'/r['method']/r['source_id']/'RESULT.json' for r in claims]
        pending=[p for p in expected_paths if not p.exists()]
        new_json(OLD/'USER_CANCELLATION_ADMISSION_CLOSED.json',dict(utc=effective,
            override=ref(C/'deadline_20260924/Q_LOSS_PRIORITY_OVERRIDE_V1.json'),
            new_task='C_D24_FULL_Q_LOSS_REFRESH_V1',mechanism='hold existing per-source attempts.lock; current episodes finish before next admission',
            controller=process_identity(),counter=counter,entered_claims=len(claims),inflight_or_terminal_pending=len(pending),
            original_science_code_unchanged=True,new_scientific_claims_created_by_controller=0))
        natural_deadline=time.monotonic()+180
        while pending and time.monotonic()<natural_deadline and same_process(expected):
            atomic_json(NEW/'evidence/CANCELLATION_HEARTBEAT.json',dict(utc=utc(),status='admissions_closed_draining_entered',pending_terminals=len(pending),reserved=counter['reserved_attempts']))
            time.sleep(1);pending=[p for p in pending if not p.exists()]
        before_signal=utc()
        if same_process(expected):os.kill(proc['pid'],signal.SIGTERM)
        stop_deadline=time.monotonic()+240
        while same_process(expected) and time.monotonic()<stop_deadline:
            time.sleep(1)
        if same_process(expected) or same_process(manager) or group_members(manager['pgid'],manager['pid']):
            raise RuntimeError('owned family not yet exited; preserve cancellation evidence and reconcile')
        final_counter=read(OLD/'ATTEMPT_COUNTER.json')
        assert final_counter['reserved_attempts']==counter['reserved_attempts'],'new source entered after admission closure'
    raw=read(WAVE/'RESULT.json');saved=[read(p) for p in expected_paths if p.exists()]
    complete=[r for r in saved if r.get('status')=='complete']
    unresolved=len(claims)-len(complete)
    row=dict(utc=utc(),status='user_cancelled_old_configuration',task_id='C_D24_XVLA_MULTI_EVAL_V1',
        reason='user prioritizes complete Q loss ablation and development selection; old P/V unstarted cancelled',
        admission_effective_utc=effective,signal_after_drain_utc=before_signal,
        actual_prior_C_attempts=10443+counter['reserved_attempts'],old_task_attempts=counter['reserved_attempts'],
        preserved_valid=len(complete),preserved_by_method={m:sum(r['method']==m for r in complete) for m in ['R','Post','Velocity']},
        entered_user_cancelled_unknown=unresolved,not_entered_user_cancelled=1500-len(claims),
        no_new_admissions_after_gate=True,completed_sources_replayed=0,automatic_retries=0,
        original_claims_and_raw_results_preserved=True,raw_scheduler_result=ref(WAVE/'RESULT.json'),
        all_formal_descendants_exited=True,occupancy_handoff_complete=raw.get('occupancy_handoff_complete'),
        saved_outcomes_are_not_relabelled=False,cancelled_missing_not_success_false=True,
        previous_current_process=proc,previous_manager=manager,previous_notification_job='D24_C_XVLA_MULTI_c24_r1')
    # Raw runner statuses remain evidence; this operational overlay is canonical
    # for distinguishing user cancellation from scientific/technical failure.
    row['saved_outcomes_are_not_relabelled']=True
    new_json(OLD/'USER_CANCELLATION_RESULT.json',row)
    new_json(NEW/'evidence/PREDECESSOR_CANCELLATION.json',row)
    receipt=C/'receipts/C/C_D24_XVLA_MULTI_EVAL_V1_RESULT_r1.json';oldreceipt=read(receipt)
    oldreceipt.update(status='user_cancelled_old_configuration',cancellation_result=str(OLD/'USER_CANCELLATION_RESULT.json'),
        actual_attempts=counter['reserved_attempts'],unstarted_user_cancelled=1500-len(claims),entered_user_cancelled_unknown=unresolved,
        valid_preserved=len(complete),all_owned_descendants_exited=True,updated_utc=utc())
    atomic_json(receipt,oldreceipt)
    print(json.dumps(row),flush=True)

if __name__=='__main__':main()
