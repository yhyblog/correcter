"""Saved V4 timing and manifest metadata only. No model/driver/holder operations."""
from pathlib import Path
import hashlib,json,statistics,sys
ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang');B=ROOT/'Corrector/sim_command/20260919'
P=B/'results/A/A11_BATCH_SCALING_CPU_V1';W=B/'work/A/A11_BATCH_SCALING_CPU_V1'
RUN=B/'results/A/P11_COMMON_POOL_V4_runs/PROPOSED_A11_shelf_train0000_parent_V4'
sys.path.insert(0,str(P/'code'));import inheritance
from budget import batch_storage,batch_timeouts,scheduler_caps,STORAGE
sources=[]
def load(path):
    path=Path(path);raw=path.read_bytes()
    sources.append(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw)))
    return json.loads(raw)
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
proposal=load(P/'proposal/PROPOSAL.json')
receipt=load(B/'receipts/A/A11_COMMON_POOL_FIRST_PARENT_V4_RESULT.json')
launch=load(RUN/'launcher/LAUNCH_RESULT.json')
storage=load(B/'results/A/A11_COMMON_POOL_FIRST_PARENT_V4/STORAGE_AUDIT.json')
memory=load(W/'CPU_MEMORY_SNAPSHOT.json');mount=load(W/'CGROUP_MOUNT_METADATA.json')
seen=set();manifest_rows=[];file_visits=[]
def metadata_manifest(ref):
    path=Path(ref['path'])
    if str(path) in seen:return
    seen.add(str(path));m=load(path);manifest_rows.append(dict(path=str(path),files=len(m['files'])))
    file_visits.extend(m['files'])
    for inherited in m.get('inherited_manifests',[]):metadata_manifest(inherited)
for key in ('code_manifest','input_manifest','external_manifest','inherited_package_manifest','config_manifest'):
    metadata_manifest(proposal[key])
# Reproduce file visits of one full authorization from manifests without reading
# their target contents. Large model bytes are never opened/stat-probed here.
big=[r for r in file_visits if r.get('size_bytes',0)>=64*1024**2]
checkpoint=next(r for r in file_visits if r['path'].endswith('/030000/pretrained_model/model.safetensors'))
hash_bytes=sum(r['size_bytes'] for r in file_visits if 'size_bytes' in r)
missing_size=[r['path'] for r in file_visits if 'size_bytes' not in r]
names=['load_PI05_SFT030000','policy_safetensors_load','policy_load_state_dict',
       'native_raw50','real_control','format_real_next_observation','vision_tower_and_projector',
       'spatial_features','full_state_capture','full_state_compare','reset_and_observe']
branches=[]
for child in launch['actual_children']['rows']:
    name=child['branch'];path=RUN/name/'numeric_events.jsonl';raw=path.read_bytes()
    sources.append(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw),scope='selected timing fields only; no old full audit rerun'))
    starts={};times={n:[] for n in names};ends=[]
    for line in raw.splitlines():
        row=json.loads(line)
        if row['phase']=='entered':starts[row['event_id']]=row
        else:
            start=starts.get(row['event_id'])
            if start and row['phase']=='returned' and start['name'] in times:
                times[start['name']].append(row['monotonic']-start['monotonic'])
            ends.append(row['monotonic'])
    first=min(r['monotonic'] for r in starts.values());last=max(ends)
    model=next(r['monotonic'] for r in starts.values() if r['name']=='load_PI05_SFT030000')
    branches.append(dict(branch=name,controls=child['result']['controls'],child_wall_seconds=child['elapsed_seconds'],
        numeric_journal_span_seconds=last-first,before_policy_load_after_attempt_entry_seconds=model-first,
        child_wall_minus_numeric_span_seconds=child['elapsed_seconds']-(last-first),
        selected_intervals={n:dict(calls=len(v),sum_seconds=sum(v),min_seconds=min(v) if v else None,max_seconds=max(v) if v else None) for n,v in times.items()},
        interval_note='host monotonic elapsed; nested intervals overlap, GPU kernels may be asynchronous; never sum all categories or call these GPU seconds'))
timing=dict(saved_only=True,outer_wall_seconds=receipt['elapsed_seconds'],launcher_wall_seconds=launch['elapsed_seconds'],
    child_wall_sum_seconds=sum(x['child_wall_seconds'] for x in branches),
    outer_minus_children_seconds=receipt['elapsed_seconds']-sum(x['child_wall_seconds'] for x in branches),
    branches=branches,scope='one accepted shelf cut5 train parent,15 cold children,12 s300 and3 early success; no throughput distribution/new task measurements',
    total_policy_load_interval_seconds=sum(x['selected_intervals']['load_PI05_SFT030000']['sum_seconds'] for x in branches),
    model_load_note='includes construction/load/device movement; safetensors/state_dict are nested, mmap does not establish disk read throughput',
    optimization_only='cold load dominates parts of saved timeline; persistent workers are outside this package and are not implemented',
    successful_handoff_raw_poll_count=None,successful_handoff_missing_reason='existing saved evidence does not contain successful raw poll series')
write(P/'SAVED_TIMING_ANALYSIS.json',timing)
memtext=next(r['text'] for r in memory['rows'] if r['path']=='/proc/meminfo')
mem={line.split(':')[0]:int(line.split()[1])*1024 for line in memtext.splitlines() if line.startswith(('MemTotal:','MemAvailable:','SwapTotal:'))}
total_hash=hash_bytes*121 # 1 launcher plus120 sequential cold branch authorizations
total_model=checkpoint['size_bytes']*120
rows=[]
for c in (1,2,4,8):
    s=batch_storage(c);t=batch_timeouts(c);scenario=receipt['elapsed_seconds']*8/c
    rows.append(dict(concurrency=c,max_resident_policy_instances=c,parents_per_GPU=1,
        fixed_physical_assignments=8,host_RAM_planning_bytes=s['RAM_planning_bytes'],
        host_RAM_peak_measured_bytes=None,container_memory_limit_bytes=None,
        per_GPU_peak_VRAM_measured_bytes=None,per_GPU_hardware_model_saved='NVIDIA H10080GB HBM3',
        VRAM_capacity_saved_label='80GB per GPU; usable bytes and peak were not recorded',
        active_controlled_payload_upper_bytes=c*STORAGE['attempt_bytes'],
        active_private_cache_threshold_bytes=c*STORAGE['private_temp_cache_budget_bytes'],
        retained_eight_parent_private_cache_threshold_bytes=8*STORAGE['private_temp_cache_budget_bytes'],
        entire_batch_admission_bytes=s['admission_bytes'],remaining_floor_bytes=s['minimum_remaining_space_bytes'],
        required_available_bytes=s['admission_bytes']+s['minimum_remaining_space_bytes'],
        required_available_inodes=s['minimum_available_inodes'],
        controlled_per_attempt_bytes=STORAGE['attempt_bytes'],controlled_per_attempt_entries=STORAGE['attempt_physical_directory_entries'],
        input_hash_read_logical_bytes_if_all120_start=total_hash,
        checkpoint_state_file_logical_load_bytes_if_all120_start=total_model,
        concurrent_cold_hash_plus_checkpoint_logical_bytes=c*(hash_bytes+checkpoint['size_bytes']),
        shared_storage_read_rate_measured_Bps=None,
        single_parent_saved_output_amortized_Bps=storage['unique_inode_payload_bytes']/receipt['elapsed_seconds'],
        same_speed_no_contention_reference_seconds=scenario,
        no_contention_scenario_is_prediction=False,measured_speedup=None,
        timeout_quote=t,scheduler_caps=scheduler_caps(c)))
value=dict(status='CPU_QUOTE_NO_RUNTIME_AUTHORIZATION',recommended_concurrency=2,
    recommendation_evidence='one-parent saved run, eight recorded H100 UUIDs,64GiB/worker planning and large host-visible MemAvailable; choose2 as a conservative first parallel candidate, not a measured safe throughput point',
    recommendation_limit='only concurrency1 has execution evidence. Container memory limit, RSS/VRAM peaks and shared IO are unknown; analysis must explicitly accept batch risk or freeze concurrency1 before any release. Do not change concurrency at execution.',
    measured_baseline=dict(wall_seconds=receipt['elapsed_seconds'],unique_inode_payload_bytes=storage['unique_inode_payload_bytes'],
        file_paths=storage['runtime_file_paths'],unique_inodes=storage['unique_inodes'],parents=1,
        real_new_task_or_cut55_measurements=0,concurrent_measurements=0),
    host_CPU_memory_snapshot=dict(at_utc=memory['at_utc'],**mem,cgroup_limit_bytes=None,
        cgroup_limit_missing_reason='no memory controller is mounted in this container; exposed cgroup directory is empty, not proof of unlimited RAM'),
    storage_budget=dict(per_parent_admission_bytes=STORAGE['first_parent_admission_bytes'],
        per_parent_components={k:STORAGE[k] for k in ['wave_new_payload_bytes','wave_log_bytes','pre_gate_JSON_total_hard_bytes','metadata_filesystem_overhead_planning_bytes','private_temp_cache_budget_bytes']},
        scope='new explicit bounded_batch1 acceptance required; old first-parent risk acceptance does not authorize this batch',
        actual_current_capacity_query=False,capacity_at_runtime_only=True,
        physical_tmp_or_unlinked_hard_bound_bytes=None,quota_guarantee=False,shared_outside_cache_budget_bytes=None,
        monitor_overshoot_bytes=None,total_RSS_hard_bound_bytes=None,
        root_controlled_budget_check=dict(launcher_bytes=256*1024**2,reserved_bytes=64*1024**2,
            lifecycle_stdout_stderr_bytes=64*1024**2,pre_gate_json_bytes=8192,batch_auxiliary_bytes=512*1024**2)),
    IO_quote=dict(manifest_file_visits_per_full_authorization=len(file_visits),manifest_files_with_unknown_size=missing_size,
        metadata_based_logical_hash_read_bytes_per_full_authorization=hash_bytes,
        large_file_visits_per_authorization=big,full_authorizations_max=121,
        input_hash_logical_bytes_upper=total_hash,checkpoint_logical_file_load_bytes_upper=total_model,
        actual_disk_or_network_bytes=None,pagecache_reuse_unknown=True,physical_IOPS_unknown=True,
        large_weight_contents_read_or_hashed_this_CPU_task=0),
    concurrency_options=rows,unchanged_numerical_budget=proposal['resource_caps'],
    source_proposals=proposal['parents'],sources=[dict(t) for t in {r['path']:r for r in sources}.values()])
write(P/'CAPACITY_AND_THROUGHPUT.json',value)
print(json.dumps(dict(status=value['status'],recommended_concurrency=2,hash_read_bytes_per_authorization=hash_bytes,
    hash_bytes_total=total_hash,model_file_bytes=checkpoint['size_bytes'],policy_load_wall_seconds=timing['total_policy_load_interval_seconds'],
    child_wall_sum=timing['child_wall_sum_seconds'],runtime_calls=0,weight_content_reads=0)))
