"""One-shot verification of the actual running24-worker B successor and its triggers."""
import json
import sys
import time
from pathlib import Path
from collections import Counter

C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
F=C/'results/B/B_D24_FULL_Q_LOSS_REFRESH_V1'
R=C/'results/B/B_D24_SMOL_MULTI_EVAL_V1/R_unstarted_r2'
S=C/'persistent_queue/nodes/B/wakeup'
sys.path.insert(0,str(F/'code'))
from qio import read,new_json,atomic_json,ref,utc,same_process
from admission import authority

authority()
assert not (R/'RESULT.json').exists(), 'R already terminal; inspect terminal result instead'
assert read(F/'MODEL_INTERFACE_CHECK.json')['status']=='PASS'
fit=read(F/'fit_r1/RESULT.json');candidate=read(F/'CANDIDATES_READY.json')
assert fit['status']=='complete' and fit['all_owned_descendants_exited'] and fit['occupancy_handoff_complete']
assert candidate['new_optimizer_updates']==64000 and candidate['fit_count']==16
queue=read(F/'QUEUE_READY.json');supervisor=read(R/'DAEMON_READY.json');beat=read(R/'chain/HEARTBEAT.json')
assert same_process(queue['process']) and same_process(supervisor['process']) and same_process(beat['manager'])
workers=[];pending=[];units=[];completed_results=[]
for slot in range(8):
    for lane in range(3):
        job='evaluate_'+str(slot)+'_lane'+str(lane);folder=R/'runs'/job;cfg=read(R/'jobs'/(job+'.json'))
        assert cfg['slot']==slot and cfg['lane']==lane and cfg['methods']==['R']
        planned=cfg['sources_by_method']['R'];units.extend(s['source_id'] for s in planned)
        if not all((folder/p).exists() for p in ['MODEL_READY.json','encoder/READY.json']):
            pending.append(job);continue
        native=read(folder/'MODEL_READY.json');encoder=read(folder/'encoder/READY.json')
        assert same_process(native['process']) and same_process(encoder['process'])
        assert encoder['loaded_new_Q']==0
        first=planned[0]['source_id'];entered=R/'evaluation/R'/first/'ENTERED.json'
        if not entered.exists():pending.append(job);continue
        first_result=R/'evaluation/R'/first/'RESULT.json'
        actual=None
        if first_result.exists():
            row=read(first_result)
            assert row['status']=='complete' and row['steps']>0 and row['trigger_mode']=='G0-multi'
            actual=dict(result=ref(first_result),steps=row['steps'],interventions=row['interventions'])
            completed_results.append(actual)
        workers.append(dict(GPU_slot=slot,GPU_uuid=read(R/'config/CONFIG.json')['gpu_uuid_by_slot'][str(slot)],lane=lane,
            job_id=job,planned_sources=len(planned),native_process=native['process'],encoder_process=encoder['process'],
            model_ready=ref(folder/'MODEL_READY.json'),encoder_ready=ref(folder/'encoder/READY.json'),
            first_entered=ref(entered),first_actual_complete=actual))
assert len(units)==len(set(units))==472
if pending or not completed_results:
    print(json.dumps(dict(status='WAIT_INITIAL_REAL_PROGRESS',actual_loaded_and_entered=len(workers),
        actual_first_completed=len(completed_results),pending=pending)))
    raise SystemExit(2)
assert len(workers)==24 and Counter(w['GPU_slot'] for w in workers)=={i:3 for i in range(8)}
guard=read('/tmp/gpu_occupancy_guard/status.json')
assert time.time()-guard['updated']<30 and len(guard['gpus'])==8
assert all(v['state']=='reserved' and not v.get('manager_pid') for v in guard['gpus'].values())
assert read(R/'chain/HOLDER_EXIT_ACK.json')['all_holder_private_sessions_observed_empty']
observer=read(S/'PROCESS.json');assert same_process(dict(observer,host=observer['hostname']))
triggers=[]
for run in ['D24_B_FULLQ_r1','D24_B_SMOL_R_UNSTARTED_r2']:
    p=S/'jobs'/(run+'__'+run+'__1.json');assert p.exists();triggers.append(ref(p))
samples=[];p=R/'chain/UTILIZATION.jsonl'
with p.open('rb') as stream:
    stream.seek(max(0,p.stat().st_size-32000));lines=stream.read().decode(errors='replace').splitlines()
for line in lines:
    try:row=json.loads(line)
    except ValueError:continue
    if row.get('GPUs') and row.get('phase')=='returned':samples.append(row)
samples=samples[-3:]
choice=Path(read(F/'config/CONFIG.json')['selection_path'])
handoff=dict(status='STABLE_HANDOFF',at_utc=utc(),node='B',host=queue['process']['host'],
    executor_thread_id='01a0b9c5-1e4b-7b73-9336-229e6df349a2',task_id='B_D24_FULL_Q_LOSS_REFRESH_V1',run_id='D24_B_FULLQ_r1',
    active_subtask='B_D24_SMOL_MULTI_EVAL_V1 Q-free unstarted R',physical_GPUs=8,workers_per_GPU=3,
    actual_live_model_ready_workers=24,actual_workers_entered_first_planned_episode=24,first_completed_count=len(completed_results),
    workers=workers,queue_process=queue['process'],formal_supervisor=supervisor['process'],manager=beat['manager'],
    source_units=472,no_duplicate_units=True,actual_attempt_snapshot=read(R/'ATTEMPT_COUNTER.json'),
    completed_Q_candidates=ref(F/'CANDIDATES_READY.json'),new_Q_optimizer_updates=64000,new_collection=0,D_G0_base_updates=0,
    user_cancellation=ref(F/'OLD_QUEUE_DISPOSITION.json'),old_R_valid_retained=4,old_R_user_cancelled_unknown=24,old_PV_unstarted_cancelled=1000,
    future_native_PV_test_units=1000,future_native_PV_workers=24,future_Q_choice='A published development choice; fixed fit9101; own four Q weights only',
    scientific_selection_path=str(choice),scientific_selection_exists=choice.exists(),no_cross_node_exit_barrier=True,
    whole_formal_wave_all_holders_off=True,holder_exit=ref(R/'chain/HOLDER_EXIT_ACK.json'),guard_cached_status=guard,
    restore_holders_only_after_all_formal_descendants_exit=True,capacity=ref(F/'CONCURRENCY_CAPACITY.json'),
    CPU_sharding_check=ref(F/'CPU_CHECKS.json'),model_interface_check=ref(F/'MODEL_INTERFACE_CHECK.json'),
    recent_existing_GPU_utilization_samples=samples,utilization_measurement='sampled utilization.gpu; not continuous SM occupancy or a shutdown guarantee',
    completion_failure_triggers=triggers,notifier=observer,scientific_task_complete=False,A_waits_for_B=False)
new_json(F/'STABLE_HANDOFF.json',handoff)
new_json(C/'receipts/B/B_D24_FULL_Q_LOSS_REFRESH_V1_STABLE_HANDOFF_r1.json',handoff)
new_json(F/'PREVIOUS_WAKEUP_HANDOFF.json',read(S/'STABLE_HANDOFF.json'))
atomic_json(S/'STABLE_HANDOFF.json',dict(status='STABLE_HANDOFF',node='B',at_utc=utc(),executor_thread_id=handoff['executor_thread_id'],
    task_id=handoff['task_id'],run_id=handoff['run_id'],active=ref(F/'STABLE_HANDOFF.json'),actual_workers=24,workers_per_GPU=3,A_waits_for_B=False))
new_json(C/'receipts/B/B_GPU_CONCURRENCY_20260922_RESULT.json',dict(status='implemented_and_running',at_utc=utc(),physical_GPUs=8,
    workers_per_GPU=3,actual_workers=24,stable=ref(F/'STABLE_HANDOFF.json'),scientific_scope='authorized472unstarted Q-free R; next1000selected full-Q native P/V',
    Q_candidates_complete=16,Q_optimizer_updates=64000,whole_formal_wave_holders_off=True,A_waits_for_B=False))
latest=samples[-1] if samples else None
print(json.dumps(dict(status='STABLE_24_WORKERS_3_PER_GPU',handoff=str(F/'STABLE_HANDOFF.json'),first_completed=len(completed_results),latest_existing_utilization=latest)))
