"""One bounded host-local verification; never launches or retries scientific work."""
import json
import os
import sys
import time
from pathlib import Path

C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
N=C/'results/B/B_D24_CROSSBASE_H_SWEEP_V1'
R=N/'recovery/velocity_r3'
sys.path.insert(0,str(R/'code'))
from qio import read,atomic_json,ref,utc,same_process,process_identity
from admission import authority

def main():
    authority()
    phase=R/'phases/01_Smol_Velocity_H40'
    checks={}
    ready=R/'DAEMON_READY.json'
    checks['service_alive']=ready.exists() and same_process(read(ready)['process'])
    manager=R/'chain/MANAGER_STARTED.json'
    checks['manager_alive']=manager.exists() and same_process(read(manager)['process'])
    checks['no_terminal_or_error']=not any((R/p).exists() for p in ('RESULT.json','ENGINEERING_FAILURE.json','chain/MANAGER_EXIT.json'))
    model_ready=list(phase.glob('model_*/MODEL_READY.json'))+list(phase.glob('encoder_*/MODEL_READY.json'))
    checks['all16_models_ready']=len(model_ready)==16
    guidance=[phase/f'branch_{g}_0/NATIVE_GUIDANCE_VERIFIED.json' for g in range(8)]
    checks['native_guidance_on_all8']=all(p.exists() for p in guidance)
    ramp=phase/'FIRST_PLANNED_PROGRESS.json'
    checks['ramp_released']=ramp.exists() and read(ramp).get('real_native_guidance_verified_on_all8',False)
    concurrency=phase/'CONCURRENCY.json'
    checks['formal_progress_recorded']=concurrency.exists() and read(concurrency).get('observed_environment_steps',0)>0
    holder_ack=R/'chain/HOLDER_EXIT_ACK.json'
    guard=read('/tmp/gpu_occupancy_guard/status.json')
    checks['holder_descendants_exited']=holder_ack.exists() and read(holder_ack)['all_holder_private_sessions_observed_empty']
    # In reserved state, pids are NVML identities of formal model services.
    # They must not be confused with a live holder manager or its descendants.
    checks['all8_reserved_no_holders']=len(guard['gpus'])==8 and all(g['state']=='reserved' and not g.get('manager_pid') for g in guard['gpus'].values())
    checks['old_holder_descendants_still_exited']=holder_ack.exists() and all(not same_process(p) for p in read(holder_ack)['old_descendant_identities'])
    checks['guard_state_fresh']=time.time()-guard['updated']<60
    trigger=R/'TRIGGER_REGISTRATION_STATUS.json'
    checks['trigger_registered']=trigger.exists() and read(trigger)['registered']
    registration=R/'WAKEUP_REGISTRATION.json'
    manifest=read(registration)
    registry=C/'persistent_queue/nodes/B/wakeup/jobs'/f"{manifest['job_id']}__{manifest['run_id']}__1.json"
    checks['durable_trigger_exists']=registry.exists()
    checks['original_thread']=os.environ.get('CODEX_THREAD_ID')=='01a0b9c5-1e4b-7b73-9336-229e6df349a2'
    if not all(checks.values()):
        print(json.dumps(dict(status='not_stable_yet',utc=utc(),checks=checks)))
        return 2
    # Actual terminal outcomes only; no inference from progress or exit codes.
    terminals=[]
    for p in (R/'episodes').glob('*/SUMMARY_ROW.json'):
        d=read(p)
        if d['status']=='complete' and isinstance(d['success'],bool):terminals.append(p)
    live=read(concurrency)
    d=dict(schema='B_stable_handoff_v1',utc=utc(),status='STABLE_HANDOFF',task_id=manifest['task_id'],run_id=manifest['run_id'],
        checks=checks,service=read(ready)['process'],manager=read(manager)['process'],host=process_identity()['host'],
        fixed_original_thread=os.environ['CODEX_THREAD_ID'],all16_models_ready=[ref(p) for p in model_ready],
        first8_native_guidance=[ref(p) for p in guidance],first_formal_progress=ref(ramp),concurrency_snapshot=live,
        valid_recovery_terminals_observed=len(terminals),actual_terminal_examples=[ref(p) for p in terminals[:8]],
        holder_exit=ref(holder_ack),guard_snapshot=guard,terminal_trigger=ref(registry),
        source_manifest=ref(R/'SOURCE_INDEX.json'),repair=ref(R/'METHOD_FROZEN.json'),original_valid_preserved=3055,
        planned_remaining_at_admission=945,automatic_sequence=['Velocity H40 missing472','Velocity H50 missing473'],
        terminal_autopublication=True,completion_independent_of_callback=True,science_complete=False,
        original_failure_evidence_preserved=True,startup_r2_consumed_science_attempts=0,
        whole_formal_family_holders_off=True,occupancy_restored_only_after_family_exit=True,
        sampled_concurrency_not_continuous_utilization_guarantee=True,A_waits_for_B=False)
    atomic_json(R/'STABLE_HANDOFF.json',d)
    atomic_json(C/'receipts/B/B_D24_CROSSBASE_H_SWEEP_V1_RECOVERY_STABLE_HANDOFF.json',d)
    print(json.dumps(dict(status='STABLE_HANDOFF',path=str(R/'STABLE_HANDOFF.json'),active=live['active_environments'],
        peak=live['peak_simultaneous_active_environments'],valid_recovery_terminals_observed=len(terminals))))
    return 0

if __name__=='__main__':raise SystemExit(main())
