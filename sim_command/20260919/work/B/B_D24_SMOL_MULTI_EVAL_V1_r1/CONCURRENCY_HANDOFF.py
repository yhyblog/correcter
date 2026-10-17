"""One-shot handoff of actual24-worker work, with existing runtime samples."""
import json
import sys
import time
from collections import Counter
from pathlib import Path
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
M=C/'results/B/B_D24_SMOL_MULTI_EVAL_V1'
R=C/'results/B/B_D24_SMOL_AUX_RETRAIN_V1/recovery_r3'
S=C/'persistent_queue/nodes/B/wakeup'
sys.path.insert(0,str(M/'code'))
from qio import read,new_json,atomic_json,ref,utc,same_process

if not (M/'CLAIM.json').exists():print('WAIT_FORMAL_MULTI_ACTIVATION');raise SystemExit(2)
if (M/'RESULT.json').exists():raise RuntimeError('multi terminal; inspect actual result instead of claiming running')
from admission import authority
authority();cfg=read(M/'config/CONFIG.json');assert cfg['target_workers']==24 and cfg['workers_per_gpu']==3
once=read(R/'RESULT.json');assert once['status']=='complete' and once['all_owned_descendants_exited'] and once['occupancy_handoff_complete']
once_summary=read(R/'FINAL_SUMMARY.json');assert all(x['valid']==500 for x in once_summary['cells'])
supervisor=read(M/'DAEMON_READY.json');q=read(M/'QUEUE_READY.json')
assert same_process(supervisor['process']) and same_process(q['process'])
beat=read(M/'chain/HEARTBEAT.json');workers=[];waiting=[];all_units=[]
for slot in range(8):
    for lane in range(3):
        ident='evaluate_'+str(slot)+'_lane'+str(lane);folder=M/'runs'/ident;job=read(M/'jobs'/(ident+'.json'))
        assert job['slot']==slot and job['lane']==lane
        all_units.extend((method,row['source_id']) for method,rows in job['sources_by_method'].items() for row in rows)
        if not all((folder/p).exists() for p in ['MODEL_READY.json','encoder/READY.json','PROGRESS.json']):waiting.append(ident);continue
        native=read(folder/'MODEL_READY.json');encoder=read(folder/'encoder/READY.json');progress=read(folder/'PROGRESS.json')
        assert same_process(native['process']) and same_process(encoder['process'])
        assert progress['status']=='complete'
        rp=M/'evaluation'/progress['method']/progress['source_id']/'RESULT.json';row=read(rp)
        assert row['status']=='complete' and row['steps']>0 and row['trigger_mode']=='G0-multi'
        workers.append(dict(GPU=slot,lane=lane,job_id=ident,native_process=native['process'],encoder_process=encoder['process'],
            ready=ref(folder/'MODEL_READY.json'),encoder_ready=ref(folder/'encoder/READY.json'),progress=progress,
            actual_result=ref(rp),steps=row['steps'],interventions=row['interventions']))
assert len(all_units)==len(set(all_units))==1500
if waiting:print(json.dumps(dict(status='WAIT_REAL_24_WORKER_PROGRESS',ready_with_results=len(workers),pending=waiting)));raise SystemExit(2)
assert len(workers)==24 and Counter(x['GPU'] for x in workers)=={i:3 for i in range(8)}
g=read('/tmp/gpu_occupancy_guard/status.json');assert time.time()-g['updated']<30
assert len(g['gpus'])==8 and all(v['state']=='reserved' and not v.get('manager_pid') for v in g['gpus'].values())
assert read(M/'chain/HOLDER_EXIT_ACK.json')['all_holder_private_sessions_observed_empty']
samples=[];p=M/'chain/UTILIZATION.jsonl'
with p.open('rb') as stream:
    stream.seek(max(0,p.stat().st_size-32000));lines=stream.read().decode(errors='replace').splitlines()
for line in lines:
    try:row=json.loads(line)
    except ValueError:continue
    if row.get('phase')=='returned' and row.get('GPUs'):samples.append(row)
samples=samples[-3:]
registration=S/'jobs/D24_B_SMOL_MULTI_r1__D24_B_SMOL_MULTI_r1__1.json';assert registration.exists()
observer=read(S/'PROCESS.json');assert same_process(dict(observer,host=observer.get('hostname',observer.get('host'))))
handoff=dict(status='STABLE_HANDOFF',at_utc=utc(),node='B',task_id=cfg['task_id'],run_id=cfg['run_id'],
    user_requested_concurrency='2-3 useful tasks per GPU after low-utilization alert; configured3',
    physical_GPUs=8,actual_workers_per_GPU=3,actual_loaded_live_workers=24,workers=workers,
    completed_once=ref(R/'RESULT.json'),completed_once_summary=ref(R/'FINAL_SUMMARY.json'),
    formal_claim=ref(M/'CLAIM.json'),supervisor=supervisor['process'],queue_process=q['process'],manager=beat['manager'],
    fixed_source_count=500,unique_method_source_units=1500,duplicate_units=0,new_training_updates=0,new_collection=0,N_rerun=False,
    same_fixed_heads=True,concurrency_revision=ref(M/'concurrency_r2/CODE_REVISION.json'),
    CPU_sharding_checks=ref(M/'concurrency_r2/CPU_CHECKS.json'),CPU_import_checks=ref(M/'concurrency_r2/CPU_IMPORT_CHECK.json'),
    frozen_actual_code=ref(M/'CODE_MANIFEST.json'),resources=ref(M/'RESOURCE_ADMISSION.json'),
    current_attempt_snapshot=read(M/'ATTEMPT_COUNTER.json'),attempt_counter_is_not_completed_count=True,
    whole_wave_all_holders_off=True,holder_exit=ref(M/'chain/HOLDER_EXIT_ACK.json'),guard_cached_status=g,
    recent_existing_GPU_utilization_samples=samples,utilization_measurement='sampled nvidia-smi utilization.gpu, not continuous SM occupancy or shutdown guarantee',
    completion_trigger=ref(registration),observer_process=observer,scientific_work_complete=False,
    deadline_unix=cfg['absolute_wall_deadline_unix'],A_waits_for_B=False,host_reboot_autostart_certified=False)
new_json(M/'STABLE_HANDOFF.json',handoff)
new_json(C/'receipts/B/B_D24_SMOL_MULTI_EVAL_V1_STABLE_HANDOFF_r2.json',handoff)
new_json(M/'concurrency_r2/PREVIOUS_WAKEUP_HANDOFF.json',read(S/'STABLE_HANDOFF.json'))
atomic_json(S/'STABLE_HANDOFF.json',dict(status='STABLE_HANDOFF',node='B',at_utc=utc(),executor_thread_id='01a0b9c5-1e4b-7b73-9336-229e6df349a2',
    task_id=cfg['task_id'],run_id=cfg['run_id'],active=ref(M/'STABLE_HANDOFF.json'),actual_workers=24,workers_per_GPU=3,A_waits_for_B=False))
new_json(C/'receipts/B/B_GPU_CONCURRENCY_20260922_RESULT.json',dict(status='implemented_and_running',at_utc=utc(),physical_GPUs=8,workers_per_GPU=3,
    actual_workers=24,stable=ref(M/'STABLE_HANDOFF.json'),scientific_scope='already-authorized1500multi evaluations only; no extra training/collection/rollouts',
    completed_once_1500=True,prior_r2_event_ACK=ref(S/'handler_acks/B_e3d46490c946a3c07ec401beb7cb10d0.json'),A_waits_for_B=False))
latest=samples[-1] if samples else None
print(json.dumps(dict(status='STABLE_24_WORKERS_3_PER_GPU',handoff=str(M/'STABLE_HANDOFF.json'),latest_existing_utilization=latest)))
