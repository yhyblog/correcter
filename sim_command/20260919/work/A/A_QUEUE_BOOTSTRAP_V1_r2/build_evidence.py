from pathlib import Path
import sys,json,socket,tarfile,shutil,statistics
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
Q=B/'persistent_queue';W=B/'work/A/A_QUEUE_BOOTSTRAP_V1_r2';P=Q/'package/versions/queue_v1'
sys.path[:0]=[str(P/'queue'),str(P/'code')]
from qio import ref,new_json,read,utc
legacy=B/'results/A/A11_BATCH3_PREP_CPU_V1'
launch=read(W/'DETACH_TEST_LAUNCH_4.json');fixture=Path(launch['test_root'])
assert read(fixture/'COMPLETE.json')['status']=='PASS'
archive=P/'evidence/DETACHED_CPU_TWO_WAVES.tar.gz'
with tarfile.open(archive,'x:gz') as t:t.add(fixture,arcname='synthetic_two_waves')
for name,source in [('CONTROL_CHECKS.json',W/'control_checks_final/CPU_CHECKS.json'),
 ('WAKEUP_FAKE_CHECKS.json',W/'wakeup_fake_r1/CHECKS.json'),('LOCAL_CONTROL_CHECKS.json',W/'LOCAL_CONTROL_CHECKS.json'),
 ('DRAIN_LOOP_CHECKS.json',Path('/tmp/corrector_real_drain_loop_cpu_v1/CHECKS.json')),('DETACHED_COMPLETE.json',fixture/'COMPLETE.json')]:
 shutil.copyfile(source,P/'evidence'/name)
obs=read(W/'resources/RESOURCE_OBSERVATIONS.json');osrow=obs['OS_sets'][0]
memtxt=osrow['files']['/proc/meminfo']['text']
mem={line.split(':')[0]:int(line.split()[1])*1024 for line in memtxt.splitlines() if line.endswith('kB')}
timingpath=B/'results/A/A11_COMMON_POOL_BATCH3_V1/SAVED_TIMING_AUDIT.json';timing=read(timingpath)
loadtimes=[r['selected_numeric_intervals']['load_PI05_SFT030000']['seconds'] for r in timing['attempts']]
parent_sums={}
for r in timing['attempts']:parent_sums[r['parent']]=parent_sums.get(r['parent'],0)+r['child_elapsed_seconds']
resource=dict(schema='corrector_queue8_resource_admission_v1',created_utc=utc(),node='A',host=socket.gethostname(),requested=8,
 status='concrete_requested8_configuration_with_declared_unknowns_pending_independent_release',supported_max=None,
 engineering_planning_supported=8,hardware_hard_limit_rejecting8_observed=False,
 observation=dict(cpu_OS_sets=3,GPU_readonly_snapshot_invocations=1,later_attempt_skipped_before_sampling=True,
  source=ref(W/'resources/RESOURCE_OBSERVATIONS.json'),cgroup_resolution=ref(W/'resources/CGROUP_PATH_RESOLUTION.json'),
  closed_window=ref(W/'resources/CGROUP_ESCALATED_RESOLUTION_OR_CLOSED.json')),
 RAM=dict(host_MemAvailable_bytes=mem['MemAvailable'],host_MemTotal_bytes=mem['MemTotal'],cgroup_limit_bytes=None,cgroup_current_bytes=None,cgroup_peak_bytes=None,
  cgroup_reason='memory controller not visible; host MemAvailable is not container quota',engineering_reservation_per_parent_bytes=64*1024**3,
  other_workload_margin_bytes=16*1024**3,requested8_planning_bytes=528*1024**3,host_visible_planning_margin_bytes=mem['MemAvailable']-528*1024**3,
  actual_worker_RSS_HWM_bytes=None,actual_family_peak_bytes=None,peak_shared_pages_loading_temporaries_unknown=True,planning_is_not_measured_minimum=True),
 CPU=dict(affinity_CPUs=len(osrow['sched_affinity']),effective_cgroup_CPU_limit=None,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1,OPENBLAS_NUM_THREADS=1,
  NUMEXPR_NUM_THREADS=1,TOKENIZERS_PARALLELISM=False,formal_workers=8),
 GPU=dict(fixed_UUID_inventory=ref(Q/'plan/NEXT8_FORMAL_CONCURRENCY_V1.json'),model='H10080GB',observed_total_MiB_each=81559,
  observed_free_MiB_each=79994,observed_used_MiB_each=1013,releasable_holder_memory_exact_bytes=None,actual_model_peak_VRAM_bytes=None,
  holder_process_exit_required_before_formal_entry=True,kill_external_processes=False,new_GPU_probe_authorized=False),
 storage=dict(required_available_bytes=93952475136,required_available_inodes=564096,per_parent_bytes=11609841664,batch_auxiliary_bytes=536870912,
  free_floor_bytes=536870912,current_observations=osrow['statvfs'],project_quota=None,exclusive_filesystem_quota=False,
  statvfs_FUSE_capacity_not_physical_quota=True,per_worker_private_temp_cache_threshold_bytes=2147483648,concurrent8_private_cache_threshold_bytes=17179869184,
  shared_ledger_atomic_hardlink_CAS_test_passed=True,shared_filesystem_flock_supported=False,local_formal_lock_unchanged=True,
  A_B_reservation_subtraction='all active logical reservations; B extra priority=max(0,93952475136-A_reserved)',
  monitoring_gaps=['outside/unlinked temp','between-poll overshoot','actual quota','RSS/VRAM peaks','physical/shared-backend IO']),
 IO=dict(saved_quote=ref(B/'results/A/A11_BATCH_SCALING_CPU_V1/CAPACITY_AND_THROUGHPUT.json'),known_checkpoint_bytes=9354050752,
  cold_checkpoint_logical_bytes_for120=1122486090240,legacy_known_full_check_logical_bytes_for121=1148482473490,
  logical_bytes_strict_upper=False,exact_new_metadata_read_bytes=None,measured_physical_backend_bytes=None,measured_shared_read_Bps=None,
  page_cache_effect_unknown=True,saved_Batch3_timing=ref(timingpath),cold_load_saved_seconds=dict(count=120,sum=sum(loadtimes),min=min(loadtimes),max=max(loadtimes),median=statistics.median(loadtimes)),
  saved_Batch3_outer_seconds=timing['outer_elapsed_seconds'],saved_branch_host_seconds_sum=timing['sum_known_child_elapsed_seconds'],
  saved_longest_parent_child_sum_seconds=max(parent_sums.values()),saved_timing_not_uncontended_benchmark=True,
  temporary_holder_override_in_Batch3_not_reused=True,real8_speedup=None,no_linear_speedup_claim=True,new_large_weight_hashes=0),
 configuration=dict(concurrency=8,one_parent_per_GPU=True,cold_branches_per_parent=15,worker_reuse=False,automatic_fallback=False,
  all8_holders_off_until_queue_no_runnable_and_group_publication_complete=True,stagger_seconds=0),
 decisions=dict(recommended='first frozen8 at explicit8 after analyst accepts declared resource unknowns',fallback_to2=False,
  new_benchmark_or_engineering_GPU_experiment=False,actual8_GPU_success_claimed=False))
new_json(P/'RESOURCE_ADMISSION.json',resource)
aux=dict(schema='queue_control_plane_aux_v1',science_original116_unchanged=True,stage_source_limit=475,batches_max=60,
 one_outer_reservation_per_continuous_chain=True,chain_lifecycle_invocations_max_without_new_authority=1,
 chain_FD_transfers=1,secondary_lock_acquisitions=0,terminal_outbox_events_max=61,synthetic_callback_events_max=2,transport_attempts_per_event_max=3,
 metrics=dict(scope='control-plane only, not116 policy counts',interval_seconds=15,full_GPU_CLI_queries_per_chain_max=120000,
  query_timeout_seconds=15,journal_bytes_max=268435456,driver_internal_NVML_calls=None,actual_query_failures_recorded=True),
 each_batch=dict(CPU_memory_snapshot_sets=1,statvfs_path_queries=2,preparation_seconds=900,technical_validation_seconds=1800,
  max_metadata_CAS_attempts=32,shared_ledger_generations_max=4096),
 state_journals=dict(atomic_heartbeat_interval_seconds=5,append_log_file_bytes_max=67108864),
 timeouts_note='300 nominal handoff;lock wait unbounded;1800+30 child;27900 parent;28200+30 wave;300 publication;1800 technical validation;120 restoration; no strict end-to-end GPU seconds')
new_json(P/'CONTROL_PLANE_AUX.json',aux)
changes=[]
for target in sorted((P/'code').rglob('*.py')):
 old=legacy/'code'/target.relative_to(P/'code');oldref=ref(old) if old.exists() else None
 changes.append(dict(path=str(target),old=oldref,new=ref(target),changed=oldref is None or oldref['sha256']!=ref(target)['sha256']))
new_json(P/'MINIMAL_DIFF.json',dict(files=changes,changed=[r['path'] for r in changes if r['changed']],
 scope='authority/scheduling/source-split/device/thread configuration; numeric controller/budget/state/native graphics byte-equal'))
print(json.dumps(dict(resource=str(P/'RESOURCE_ADMISSION.json'),RAM_visible=mem['MemAvailable'],synthetic_archive_bytes=archive.stat().st_size,changed_code_files=sum(r['changed'] for r in changes))))
