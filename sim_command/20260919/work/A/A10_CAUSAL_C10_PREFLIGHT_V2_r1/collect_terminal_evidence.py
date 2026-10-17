"""Post-exit saved-file audit only; no runtime imports or hardware queries."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re
ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang');B=ROOT/'Corrector/sim_command/20260919'
T='A10_CAUSAL_C10_PREFLIGHT_V2';W=B/'work/A'/(T+'_r1');O=B/'results/A'/T
R=B/'results/A/P10_CAUSAL_C10_V2_launcher_runs'/(T+'_r1_A_wave10')
def read(p):return json.loads(p.read_text())
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size_bytes=p.stat().st_size)
def put(p,x):
    with p.open('x') as f:f.write(x if isinstance(x,str) else json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
cmd=read(W/'COMMAND_RESULT.json');launch=read(R/'LAUNCH_RESULT.json')
assert cmd['returncode'] is not None
with (O/'LAUNCH_RESULT.json').open('xb') as f:f.write((R/'LAUNCH_RESULT.json').read_bytes())
checked=[];mismatches=[]
for branch in ['Post','Velocity']:
    path=R/branch/'ARTIFACT_MANIFEST.json'
    if not path.exists():continue
    for row in read(path)['files']:
        p=Path(row['path']);actual=ref(p)
        ok=actual['sha256']==row['sha256'] and actual['size_bytes']==row['size_bytes']
        checked.append(dict(branch=branch,expected=row,actual=actual,match=ok))
        if not ok:mismatches.append(str(p))
put(O/'RUNTIME_MANIFEST_AUDIT.json',dict(status='PASS' if not mismatches else 'MISMATCH',checked_files=len(checked),files=checked,mismatches=mismatches,hardware_queries=0))
marks=[json.loads(x) for x in (R/'wave_timing.jsonl').read_text().splitlines()]
def mark(name,branch=None):return next((r for r in marks if r['phase']==name and (branch is None or r.get('branch')==branch)),None)
def elapsed(a,b):return None if a is None or b is None else b['monotonic_seconds']-a['monotonic_seconds']
timing=dict(parent_preparation_seconds=elapsed(mark('launcher_started'),mark('lifecycle_requested')),
    observed_lifecycle_request_to_reserved_entry_seconds=elapsed(mark('lifecycle_requested'),mark('reserved_command_started')),
    timed_child_seconds={b:elapsed(mark('timed_process_started',b),mark('timed_process_exited',b)) for b in ['Post','Velocity']},
    lifecycle_exit_to_restoration_observed_seconds=elapsed(mark('lifecycle_returned'),mark('restoration_observed')),
    outer_command_seconds=cmd['elapsed_seconds'],handoff_nominal_seconds=300,per_child_timeout_seconds=1800,kill_grace_seconds=30,
    end_to_end_strict_upper_bound_seconds=None,successful_guard_raw_poll_count=None,GPU_seconds=None,
    successful_poll_note='No successful raw polling sequence saved; manager timestamps do not substitute for it.')
guard_log=ROOT/'gpu_occupancy_guard.log'
with guard_log.open('rb') as f:
    f.seek(0,2);size=f.tell();f.seek(max(0,size-4*1024*1024));tail=f.read()
with (W/'gpu_occupancy_guard.log.captured_tail').open('xb') as f:f.write(tail)
start=datetime.fromisoformat(cmd['started_at_utc']);end=datetime.fromisoformat(cmd['finished_at_utc']);window=[]
for line in tail.decode(errors='replace').splitlines():
    try:stamp=datetime.fromisoformat(line.split(' ',1)[0].replace('Z','+00:00'))
    except ValueError:continue
    if start<=stamp<=end:window.append(line)
put(O/'HOLDER_LOG_WINDOW.txt','\n'.join(window)+'\n')
yield_rows=[x for x in window if ': yielded;' in x];restart_rows=[x for x in window if ': started holder manager ' in x]
restore=launch.get('restoration') or {};status=restore.get('guard_status') or {};gpu_rows=status.get('gpus',{})
cleanup=launch.get('process_family_cleanup') or {}
put(O/'TIMING_AND_HOLDER_AUDIT.json',dict(status='EVIDENCE_COLLECTED',timing=timing,
    holder_count_restored=sum(x.get('state')=='holder' and bool(x.get('driver_pids')) for x in gpu_rows.values()),
    external_count_preserved=sum(x.get('state')=='external' for x in gpu_rows.values()),
    restored_guard_pid=status.get('pid'),restored_holders=gpu_rows,occupancy_observation=restore,
    manager_yield_rows=yield_rows,manager_start_rows=restart_rows,
    manager_timestamps_are_not_GPU_last_compute_times=True,successful_empty_app_poll_evidence=None,
    full_group_exit=cleanup,restoration_after_lifecycle_exit=bool(mark('restoration_observed') and mark('lifecycle_returned') and mark('restoration_observed')['monotonic_seconds']>=mark('lifecycle_returned')['monotonic_seconds']),
    guard_restart_invoked=False,extra_hardware_queries=0,source='saved launcher evidence plus passive existing manager log bytes'))
availability=[]
for branch in ['Post','Velocity']:
    d=R/branch;files=[x.name for x in d.iterdir() if x.is_file()] if d.exists() else []
    ev=[json.loads(x) for x in (d/'causal_events.jsonl').read_text().splitlines()] if (d/'causal_events.jsonl').exists() else []
    trigger=next((x for x in ev if x['event']=='trigger_decision'),None)
    required=dict(policy_UUID_original_type='policy_device_type.json',policy_UUID_final='policy_device.json',strict_loader='policy_loader.json',model_identity='model_identity.json',
        G0_members='G0_outputs.json',numeric_constraints=branch+'_numeric.json',action_gradients=branch+'_arrays.npz',
        prefix_raw='prefix_raw50.npy',cut_anchor='cut_anchor_raw50.npy',proposed_raw=branch+'_proposed_raw50.npy',restore_raw='restore_raw50.npy')
    artifacts={k:ref(d/name) if (d/name).exists() else None for k,name in required.items()}
    fail=read(d/'failure.json') if (d/'failure.json').exists() else None
    availability.append(dict(branch=branch,available_files=files,artifacts=artifacts,
        observations_saved=len(list(d.glob('observation_step*.npz'))) if d.exists() else 0,
        D_forecast_files=[ref(x) for x in sorted(d.glob('D_*.npz'))],trigger=trigger,
        primary_failure=fail,cleanup_failures=[read(x) for x in sorted(d.glob('cleanup_failure__*.json'))],
        missing_artifacts_mean_unreached_or_unavailable=True,missing_is_not_method_failure_label=True))
put(O/'STAGE_AVAILABILITY.json',dict(branches=availability,extra_model_calls=0,extra_render_calls=0,
    success_rate_sample=False,ranking=False,hidden_state_equivalence_claim=False))
print(json.dumps(dict(runtime_manifest_files=len(checked),manifest_mismatches=mismatches,
    restored_holders=sum(x.get('state')=='holder' for x in gpu_rows.values()),launcher_status=launch['status'],
    completed_C10_branches=launch['completed_C10_branches'],timing=timing)))
