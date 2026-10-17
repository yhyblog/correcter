"""One-shot evidence and audit, conditioned on actual once recovery progress."""
import json
import sys
import time
from pathlib import Path
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
A=C/'results/B/B_D24_SMOL_AUX_RETRAIN_V1'
R=A/'recovery_r3'
M=C/'results/B/B_D24_SMOL_MULTI_EVAL_V1'
S=C/'persistent_queue/nodes/B/wakeup'
EVENT='B_e3fef864f793fe09c07c5db37c5430f1'
sys.path.insert(0,str(R/'code'))
from qio import read,new_json,atomic_json,utc,ref,same_process
from admission import authority

authority();event=read(S/'outbox'/(EVENT+'.json'))
assert event['task_id']=='B_QUEUE_JOIN_V1' and event['outcome']=='dependency_changed'
for root in [A,A/'recovery_r2']:
    terminal=read(root/'RESULT.json');p=read(root/'CLAIM.json')['process']
    assert terminal['all_owned_descendants_exited'] and not same_process(dict(p,host=p['hostname']))
ready=read(R/'DAEMON_READY.json');assert same_process(ready['process'])
heartbeat=read(R/'chain/HEARTBEAT.json');assert heartbeat['phase']=='evaluate' and heartbeat['living_workers']==8
qready=read(M/'QUEUE_READY.json');assert same_process(qready['process'])
qbeat=read(M/'QUEUE_HEARTBEAT.json');assert qbeat['status']=='waiting_once' and qbeat['predecessor_alive']
assert not (M/'CLAIM.json').exists()
observer=read(S/'PROCESS.json');assert same_process(dict(observer,host=observer.get('hostname',observer.get('host'))))
registrations=[S/'jobs'/(run+'__'+run+'__1.json') for run in ['D24_B_SMOL_AUX_EVAL_r3','D24_B_SMOL_MULTI_r1']]
assert all(p.exists() for p in registrations)
workers=[];waiting=[]
for slot in range(8):
    directory=R/'runs'/('evaluate_'+str(slot))
    if not all((directory/p).exists() for p in ['MODEL_READY.json','encoder/READY.json','PROGRESS.json']):waiting.append(slot);continue
    native=read(directory/'MODEL_READY.json');encoder=read(directory/'encoder/READY.json');progress=read(directory/'PROGRESS.json')
    assert same_process(native['process']) and same_process(encoder['process'])
    assert progress['status']=='complete'
    rp=R/'evaluation'/progress['method']/progress['source_id']/'RESULT.json';row=read(rp)
    assert row['status']=='complete' and row['steps']>0 and row['interventions']<=1
    assert encoder['loaded_new_D']==2 and encoder['loaded_new_G0']==2 and encoder['loaded_new_Q']==4
    workers.append(dict(slot=slot,native=ref(directory/'MODEL_READY.json'),encoder=ref(directory/'encoder/READY.json'),
        native_process=native['process'],encoder_process=encoder['process'],actual_result=ref(rp),progress=progress,
        steps=row['steps'],interventions=row['interventions'],real_counters=row['counters'],real_encoder_counters=row.get('encoder_counters')))
if waiting:print(json.dumps(dict(status='WAIT_REAL_RECOVERY_PROGRESS',waiting_slots=waiting)));raise SystemExit(2)
guard=read('/tmp/gpu_occupancy_guard/status.json');assert time.time()-guard['updated']<30
assert len(guard['gpus'])==8 and all(v['state']=='reserved' and not v.get('manager_pid') for v in guard['gpus'].values())
handoff=dict(status='STABLE_HANDOFF',at_utc=utc(),node='B',task_id='B_D24_SMOL_AUX_RETRAIN_V1',run_id='D24_B_SMOL_AUX_EVAL_r3',
    executor_thread_id=event['executor_thread_id'],supervisor=ready['process'],manager=heartbeat['manager'],phase='evaluate_once_recovery',
    real_live_workers=8,workers=workers,formal_claim=ref(R/'CLAIM.json'),code=ref(R/'CODE_MANIFEST.json'),terminal_trigger=ref(registrations[0]),
    observer_process=observer,retained_once_valid=788,pending_recovery_plan=712,trained_heads_reused=8,training_updates_this_recovery=0,
    whole_wave_all_holders_off=True,holder_exit=ref(R/'chain/HOLDER_EXIT_ACK.json'),guard_cached_status=guard,
    queued_multi=dict(task_id='B_D24_SMOL_MULTI_EVAL_V1',run_id='D24_B_SMOL_MULTI_r1',queue_process=qready['process'],
        queue_claim=ref(M/'QUEUE_CLAIM.json'),queue_ready=ref(M/'QUEUE_READY.json'),terminal_trigger=ref(registrations[1]),
        formal_started=False,planned_evaluations=1500,automatic_after_complete_once_and_own_family_exit=True),
    A_waits_for_B=False,science_complete=False,host_reboot_autostart_certified=False)
new_json(R/'STABLE_HANDOFF.json',handoff)
new_json(C/'receipts/B/B_D24_SMOL_AUX_RETRAIN_V1_STABLE_HANDOFF_r3.json',handoff)
new_json(M/'STABLE_QUEUE_HANDOFF.json',dict(status='STABLE_QUEUED_HANDOFF',at_utc=utc(),queue=qready,predecessor_stable=ref(R/'STABLE_HANDOFF.json'),
    formal_started=False,terminal_trigger=ref(registrations[1]),no_cross_node_dependency=True))
previous=read(S/'STABLE_HANDOFF.json');new_json(R/'evidence/PREVIOUS_WAKEUP_HANDOFF.json',previous)
atomic_json(S/'STABLE_HANDOFF.json',dict(status='STABLE_HANDOFF',node='B',executor_thread_id=event['executor_thread_id'],at_utc=utc(),
    active=ref(R/'STABLE_HANDOFF.json'),queued=ref(M/'STABLE_QUEUE_HANDOFF.json'),A_waits_for_B=False))
original=read(A/'FINAL_SUMMARY.json');data=read(A/'DATA_SUMMARY.json');fit=read(A/'FIT_SUMMARY.json')
audit=dict(schema='B_dependency_event_audit_v1',event_id=EVENT,outcome='audited_complete',at_utc=utc(),
    event=ref(S/'outbox'/(EVENT+'.json')),dependency_change=ref(event['result_path']),
    CONTROL=ref(C/'CONTROL.json'),queue_CONTROL=ref(C/'persistent_queue/CONTROL.json'),task_board_revision=read(C/'TASK_BOARD.json').get('revision'),
    completed_data=dict(parent_complete=data['counts']['parent_complete'],real_rollouts=data['counts']['rollout_complete'],reached_parents=data['reached_parents'],normal_only=data['counts']['normal_only']),
    completed_training=dict(heads=8,total_updates=fit['total_updates'],G0_ready=fit['G0_ready'],Q_ready=fit['Q_ready'],fixed_final_checkpoints=True),
    original_once=dict(result=ref(A/'RESULT.json'),summary=ref(A/'FINAL_SUMMARY.json'),valid=788,R_valid=500,Post_valid=288,Velocity_valid=0,
        attempts=2690,prior_B_attempts=11696,cumulative_B_attempts_at_interruption=14386,technical=6,control_interrupted_marked_budget_truncated=1,unknown=0),
    control_defect='live validator required authorization in followups after task became current; grant remained released and original once continuation explicit',
    control_correction='current released grant in stage_authorizations accepted independent of queue position; actual stop/revocation/disabled/host/budget checks retained',
    startup_r2=dict(result=ref(A/'recovery_r2/RESULT.json'),scientific_attempts=0,encoder_load_failures=8,all_owned_family_exited=True,
        cause='two frozen artifact path references still used recovery root',correction='normalization and Q selected root changed to original ARTIFACTS; CPU bindings checked',logs_preserved=True),
    active_recovery=dict(run_id='D24_B_SMOL_AUX_EVAL_r3',claim=ref(R/'CLAIM.json'),stable=ref(R/'STABLE_HANDOFF.json'),
        original_valid_never_replayed=True,unstarted=705,one_corrected_control_faults=7,new_updates=0,new_collection=0),
    authorized_multi=dict(task_id='B_D24_SMOL_MULTI_EVAL_V1',ACK=ref(C/'receipts/B/B_D24_SMOL_MULTI_EVAL_V1_ACK.json'),
        queue=ref(M/'STABLE_QUEUE_HANDOFF.json'),methods=['R','Post','Velocity'],planned=1500,new_updates=0,new_collection=0,old_N_rerun=False,
        change='episode total intervention cap removed only; C10/legality/strict threshold/RNG/native bridge fixed',
        comparison='same-head once and multi separate; no test-selected refit; repeated local gain is not global-value calibration'),
    duplicate_scientific_units_launched=0,notifier=observer,completion_triggers=[ref(p) for p in registrations],
    whole_wave_all_holders_off=True,A_waits_for_B=False,science_still_running=True)
audit_path=C/'receipts/B/events'/(EVENT+'_AUDIT.json');new_json(audit_path,audit)
print(json.dumps(dict(status='AUDITED_STABLE_RECOVERY_AND_QUEUED_MULTI',audit=str(audit_path),handoff=str(R/'STABLE_HANDOFF.json'))))
