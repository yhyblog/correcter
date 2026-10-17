"""Write the requested B-owned audit after an observed stable handoff."""
import os
import sys
from pathlib import Path

C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
N=C/'results/B/B_D24_CROSSBASE_H_SWEEP_V1';R=N/'recovery/velocity_r3'
sys.path.insert(0,str(R/'code'))
from qio import read,ref,atomic_json,utc,same_process
from admission import authority

authority()
event_id='B_010be046ec18416d856c83114f42149b'
event=C/'persistent_queue/nodes/B/wakeup/outbox'/(event_id+'.json')
e=read(event);stable=read(R/'STABLE_HANDOFF.json')
assert e['event_id']==event_id and e['claim_identity']['sha256']==ref(N/'CLAIM.json')['sha256']
assert stable['status']=='STABLE_HANDOFF' and all(stable['checks'].values())
assert same_process(stable['service']) and same_process(stable['manager'])
assert os.environ.get('CODEX_THREAD_ID')==e['executor_thread_id']
c=read(C/'CONTROL.json');q=read(C/'persistent_queue/CONTROL.json')
d=dict(schema='B_terminal_event_recovery_audit_v1',utc=utc(),event_id=event_id,outcome='audited_complete',
    event=ref(event),small_result=ref(N/'RESULT.json'),original_summary=ref(N/'FINAL_SUMMARY.json'),
    original_claim=ref(N/'CLAIM.json'),original_claim_verified=True,
    current_CONTROL=dict(revision=c['revision'],stop_requested=c['stop_requested'],active_authorization=c['active_crossbase_H_sweep']),
    queue_CONTROL=dict(revision=q['revision'],global_stop=q['global_stop'],active_runtime_authorization=q['nodes']['B']['active_runtime_authorization']),
    authorization=ref(Path(read(R/'config/CONFIG.json')['grant'])),
    finding='Original run partial: 3055 valid, 384 technical failures from cached inference normalization tensors, 561 unstarted. Exact private repair validated on CPU and first planned real guidance on all eight GPUs. Only 945 missing units admitted to finite recovery.',
    no_valid_scientific_failure_replayed=True,duplicate_scientific_launches=0,old_process_family_exited=True,
    original_attempts=3439,prior_cumulative_B_attempts=25561,recovery_planned_attempts=945,recovery_max_attempts=961,
    repair=ref(R/'METHOD_FROZEN.json'),recovery_manifest=ref(R/'RECOVERY_MANIFEST.json'),
    predecessor_exit=ref(R/'PREDECESSOR_EXIT_CHECK.json'),
    startup_r2_failure=ref(N/'recovery/velocity_r2/RESULT.json'),startup_r2_scientific_attempts=0,
    recovery_claim=ref(R/'CLAIM.json'),recovery_run=stable['run_id'],stable_handoff=ref(R/'STABLE_HANDOFF.json'),
    background_stable=True,terminal_trigger_registered=True,all_holders_off=True,
    active_environment_snapshot=stable['concurrency_snapshot'],
    original_thread=e['executor_thread_id'],science_complete=False,
    automatic_H40_H50_continuation=True,automatic_final_publication=True,callback_does_not_gate_science=True,
    original_failed_costs_preserved=True,unknown_costs_not_imputed=True,technical_missing_not_success_false=True,
    shared_CONTROL_TASK_BOARD_unmodified=True,A_waits_for_B=False)
out=N/'audits'/(event_id+'.json');atomic_json(out,d)
atomic_json(R/'AUDIT_COMPLETED.json',dict(utc=utc(),event_id=event_id,audit=ref(out),ACK_must_be_called_in_original_turn=True))
print(out)
