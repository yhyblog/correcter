"""One-shot handoff evidence from real running work; never launch or ACK."""
import json
import sys
import time
from pathlib import Path

C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
R=C/'results/B/B_D24_SMOL_AUX_RETRAIN_V1'
P=C/'results/B/B_D24_POST_TRIGGER_MODES_V1/recovery_r3'
S=C/'persistent_queue/nodes/B/wakeup'
EVENT='B_e61ec13aef31dd7199091b1aad879d62'
sys.path.insert(0,str(R/'code'))
from qio import read,new_json,atomic_json,ref,sha,utc,same_process
from admission import authority
from common import parent_path

authority()
old=read(P/'RESULT.json');old_summary=read(P/'FINAL_SUMMARY.json')
assert old['status']=='complete' and old['all_owned_descendants_exited'] and old['occupancy_handoff_complete']
assert len(old_summary['cells'])==10 and all(x['valid']==500 and x['complete'] for x in old_summary['cells'])
event=read(S/'outbox'/(EVENT+'.json'));assert event['claim_identity']['sha256']==sha(P/'CLAIM.json')
ready=read(R/'DAEMON_READY.json');assert same_process(ready['process'])
heartbeat=read(R/'chain/HEARTBEAT.json')
assert heartbeat['phase']=='collect' and heartbeat['living_workers']==8
observer=read(S/'PROCESS.json')
assert same_process(dict(observer,host=observer.get('hostname',observer.get('host'))))
registration=S/'jobs/D24_B_SMOL_AUX_r1__D24_B_SMOL_AUX_r1__1.json'
assert read(registration)['claim_identity']['sha256']==sha(R/'CLAIM.json')
workers=[];not_ready=[]
for slot in range(8):
    directory=R/'runs'/('collect_'+str(slot));config=read(R/'jobs'/('collect_'+str(slot)+'.json'))
    if not (directory/'MODEL_READY.json').exists() or not (directory/'encoder/READY.json').exists():
        not_ready.append(dict(slot=slot,reason='model loading'));continue
    native=read(directory/'MODEL_READY.json');encoder=read(directory/'encoder/READY.json')
    assert same_process(native['process']) and same_process(encoder['process'])
    examples=[]
    for source in config['parents']:
        folder=parent_path(source)
        for p in sorted(folder.glob('*/RESULT.json')):
            result=read(p)
            if result['status']!='complete':raise RuntimeError('Actual noncomplete collection result: '+str(p))
            if len(examples)<2:examples.append(dict(reference=ref(p),source_id=result['source_id'],candidate=result['candidate'],repeat=result['repeat'],steps=result['steps'],success=result['success']))
        if len(examples)>=2:break
    if len(examples)<2:
        not_ready.append(dict(slot=slot,reason='awaiting first real paired collection progress',complete_examples=len(examples)));continue
    workers.append(dict(slot=slot,native=ref(directory/'MODEL_READY.json'),encoder=ref(directory/'encoder/READY.json'),
        native_process=native['process'],encoder_process=encoder['process'],first_actual_examples=examples,
        progress=read(directory/'PROGRESS.json') if (directory/'PROGRESS.json').exists() else None))
if not_ready:
    print(json.dumps(dict(status='WAIT_REAL_PROGRESS',not_ready=not_ready,ready_slots=[x['slot'] for x in workers])));sys.exit(2)
guard=read('/tmp/gpu_occupancy_guard/status.json')
assert time.time()-guard['updated']<30 and len(guard['gpus'])==8
assert all(x['state']=='reserved' and not x.get('manager_pid') for x in guard['gpus'].values())
assert read(R/'chain/HOLDER_EXIT_ACK.json')['all_holder_private_sessions_observed_empty']
handoff=dict(status='STABLE_HANDOFF',at_utc=utc(),node='B',task_id='B_D24_SMOL_AUX_RETRAIN_V1',run_id='D24_B_SMOL_AUX_r1',
    executor_thread_id=event['executor_thread_id'],supervisor=ready['process'],manager=heartbeat['manager'],phase='collect',actual_live_workers=8,
    workers=workers,formal_claim=ref(R/'CLAIM.json'),code=ref(R/'CODE_MANIFEST.json'),queue=ref(R/'CHAIN_COMMAND.json'),
    terminal_trigger=ref(registration),observer_process=observer,wakeup_status=read(S/'WAKEUP_STATUS.json'),
    real_scientific_progress=True,whole_wave_holder_policy='all8off until all collection/training/evaluation descendants exit, including failures',
    holder_exit=ref(R/'chain/HOLDER_EXIT_ACK.json'),cached_guard_status=guard,
    automatic_phases=['collect','prepare_data','fit_D_Q','fit_G0','evaluate','publish','restore_occupancy'],
    scientific_gap_stops_affected_units=True,absolute_wall_deadline_unix=read(R/'config/CONFIG.json')['absolute_wall_deadline_unix'],
    no_other_node_dependency=True,A_waits_for_B=False,completed=False,reboot_autostart_certified=False)
new_json(R/'STABLE_HANDOFF.json',handoff)
new_json(C/'receipts/B/B_D24_SMOL_AUX_RETRAIN_V1_STABLE_HANDOFF_r1.json',handoff)
previous=read(S/'STABLE_HANDOFF.json') if (S/'STABLE_HANDOFF.json').exists() else None
new_json(R/'evidence/PREVIOUS_WAKEUP_HANDOFF.json',dict(previous=previous,at_utc=utc()))
atomic_json(S/'STABLE_HANDOFF.json',dict(handoff_ref=ref(R/'STABLE_HANDOFF.json'),status='STABLE_HANDOFF',at_utc=utc(),
    node='B',executor_thread_id=event['executor_thread_id'],task_id=handoff['task_id'],run_id=handoff['run_id'],A_waits_for_B=False))
board=read(C/'TASK_BOARD.json')
audit=dict(schema='B_original_event_audit_v1',at_utc=utc(),event_id=EVENT,outcome='audited_complete',
    event=ref(S/'outbox'/(EVENT+'.json')),claim=ref(P/'CLAIM.json'),terminal=ref(P/'RESULT.json'),summary=ref(P/'FINAL_SUMMARY.json'),
    completed_task='B_D24_POST_TRIGGER_MODES_V1',completed_run='D24_B_POST_TRIGGER_MODES_r3',
    valid=5000,planned=5000,attempts=old_summary['attempts'],cumulative_B_attempts_before_successor=old_summary['cumulative_B_attempts'],
    current_technical=0,current_unknown=0,current_unstarted=0,historical_attempts_preserved=True,
    cells=[{k:x[k] for k in ['cell','valid','successes','technical_failures','execution_unknown','unstarted']} for x in old_summary['cells']],
    control=dict(root=ref(C/'CONTROL.json'),queue=ref(C/'persistent_queue/CONTROL.json'),task_board_revision=board.get('revision'),
        explicit_authorized_followup='B_D24_SMOL_AUX_RETRAIN_V1; after own predecessor family exit',no_new_approval_required=True),
    successor=dict(task_id=handoff['task_id'],run_id=handoff['run_id'],status='running_collect',real_live_workers=8,
        claim=ref(R/'CLAIM.json'),stable_handoff=ref(R/'STABLE_HANDOFF.json'),terminal_trigger=ref(registration),automatic_finite_pipeline=True),
    duplicate_launches=0,Post_restarted=False,old_N_restarted=False,whole_wave_all_holders_off=True,A_waits_for_B=False,
    conclusion='Post event complete and audited; authorized independent Smol successor has real8worker progress and durable terminal trigger; successor science remains running')
path=C/'receipts/B/events'/(EVENT+'_AUDIT.json');new_json(path,audit)
print(json.dumps(dict(status='STABLE_HANDOFF_AND_AUDIT_SAVED',audit=str(path),handoff=str(R/'STABLE_HANDOFF.json'))))
