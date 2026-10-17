"""Saved-only accounting of the later explicit user occupancy instruction."""
from pathlib import Path
import datetime, json
from audit_saved_helpers import load, ref, save
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W=B/'work/A/A11_COMMON_POOL_BATCH3_V1';P=B/'results/A/A11_COMMON_POOL_BATCH3_V1'
E=W/'OCCUPANCY_OVERRIDE'
assert (P/'OUTER_EXIT.json').exists(), 'formal command must already have exited'
assert (E/'SUPERVISOR_EXIT.json').exists(), 'wait for temporary-holder cleanup evidence'
events=[json.loads(x) for x in (E/'EVENTS.jsonl').read_text().splitlines()]
started=[e for e in events if e['event']=='own_holder_started']
exited=[e for e in events if e['event']=='own_holder_exited']
exit_by_pid={e['manager_pid']:e for e in exited}
rows=[dict(start=e,exit=exit_by_pid.get(e['manager_pid']),has_exit=e['manager_pid'] in exit_by_pid) for e in started]
checks=[]
for path in sorted(E.glob('UTILIZATION_CHECK_*.json')):
    doc=load(path);util=[]
    for line in doc.get('stdout','').splitlines():
        parts=[x.strip() for x in line.split(',')]
        if len(parts)==4:
            try:util.append(dict(gpu_index=int(parts[0]),UUID=parts[1],percent=float(parts[2]),memory_MiB=float(parts[3])))
            except ValueError:pass
    checks.append(dict(ref=ref(path),rows=util,mean_snapshot_percent=sum(x['percent'] for x in util)/len(util) if len(util)==8 else None,not_sustained_average=True))
release=load(W/'authorization/P11_A_COMMON_POOL_BATCH3_V1.json')
gpu7=next(p for p in release['parents'] if p['device']['gpu_index']==7)
start_path=Path(gpu7['paths']['output'])/'reserved/normal_START.json'
guard=load(Path('/tmp/gpu_occupancy_guard/status.json'))
guard_capture=dict(captured_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),existing_daemon_status=guard,live_GPU_query_performed=False)
save(E/'POST_EXIT_EXISTING_GUARD_STATUS.json',guard_capture)
record=dict(user_authorization=ref(E/'USER_AUTHORIZATION.json'),supervisor_started=load(E/'SUPERVISOR_STARTED.json'),supervisor_exit=load(E/'SUPERVISOR_EXIT.json'),
    holders=rows,all_started_holder_managers_have_saved_exit=all(x['has_exit'] for x in rows),
    forced_own_holder_stops=[e for e in events if e['event']=='own_holder_KILL_after_grace'],
    unrelated_processes_signaled=False,shared_guard_modified=False,formal_lock_modified=False,
    formal_concurrency=2,formal_sources_seeds_algorithm_caps_unchanged=True,formal_command_repeated=False,
    original_all8_stop_for_entire_wave_preserved=False,
    override_reason='Later explicit user instruction: keep all GPUs occupied to prevent server reclamation below50% utilization',
    temporary_holder_target_duty_cycle=.95,temporary_holder_work_is_additional_to_formal116_ledger=True,
    occupancy_torch_CUDA_and_GEMM_counts=None,occupancy_count_missing_reason='holder logs save iterations periodically, not a complete operation ledger; never add them to formal collection counts',
    additional_nvidia_smi_verification_invocations=len(checks),utilization_snapshots=checks,
    GPU7_formal_START_ref=ref(start_path) if start_path.exists() else None,
    GPU7_formal_START_file_mtime_ns=start_path.stat().st_mtime_ns if start_path.exists() else None,
    GPU7_file_mtime_is_not_exact_Popen_or_GPU_context_time=True,
    GPU7_holder_exits=[e for e in exited if e['gpu_index']=='7'],
    helper_yield_trigger='saved first formal START, before the branch reaches model loading; preserve actual recorded timestamps without inferring exact context overlap',
    post_exit_guard_status=ref(E/'POST_EXIT_EXISTING_GUARD_STATUS.json'),
    post_exit_baseline_holder_count=sum(v.get('state')=='holder' for v in (guard or {}).get('gpus',{}).values()),
    auxiliary_GPU_occupancy_changes_timing_conditions=True,not_a_comparable_throughput_benchmark=True,
    original_runtime_outputs_unmodified=True,new_model_environment_probe_calls=0)
save(P/'OCCUPANCY_POLICY_OVERRIDE.json',record)
print(json.dumps(dict(auxiliary_holder_starts=len(started),all_exited=record['all_started_holder_managers_have_saved_exit'],baseline_holders=record['post_exit_baseline_holder_count'],nvidia_smi_checks=len(checks))))
