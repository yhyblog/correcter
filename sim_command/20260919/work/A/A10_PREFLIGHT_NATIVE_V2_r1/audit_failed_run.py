"""Read-only CPU reconciliation of this consumed finite run; no driver imports."""
from pathlib import Path
import collections,datetime,hashlib,json,os,re,sys
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');TASK='A10_PREFLIGHT_NATIVE_V2';W=B/'work/A'/f'{TASK}_r1'
RUN=B/'results/A/P10_launcher_runs/A10_PREFLIGHT_NATIVE_V2_r1_A_wave04';P=B/'results/A/A10_NATIVE_EGL_INTEGRATION_CPU_V1'
R=json.loads((W/'inputs/releases/P10_A_NATIVE_PREFLIGHT_V2.json').read_text());D=Path(json.loads((RUN/'diagnostic_link.json').read_text())['path'])
# Only frozen CPU ledger modules, no actual preflight/driver/torch/mujoco import.
def forbidden(event,args):
 if event.startswith(('ctypes.dlopen','ctypes.dlsym')):raise RuntimeError('Foreign library work forbidden in receipt audit')
 if event=='import' and args[0].split('.')[0] in {'torch','mujoco','metaworld','gymnasium','OpenGL','numpy'}:raise RuntimeError('Heavy import forbidden in receipt audit')
sys.addaudithook(forbidden);sys.dont_write_bytecode=True;sys.path.insert(0,str(P/'code'))
from core.accounting import summarize
from core.initialization import summarize_initialization
from core.graphics_contract import reconcile

def read(f):return json.loads(Path(f).read_text())
def rows(f):return [json.loads(x) for x in Path(f).read_text().splitlines()]
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def ref(f):f=Path(f);return dict(path=str(f),sha256=sha(f),size_bytes=f.stat().st_size)
def publish(f,value):
 f=Path(f);tmp=f.with_name(f.name+'.publish.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,f)
launch=read(RUN/'LAUNCH_RESULT.json');failure=read(D/'failure.json');resource=read(D/'resource_receipt.json')
public=summarize(rows(D/'events.jsonl'));initialization=summarize_initialization(rows(D/'initialization_events.jsonl'),R['initialization_caps']);graphics=reconcile(D/'graphics_events.jsonl')
assert public==launch['resources']['public_events']
assert initialization==launch['resources']['initialization']==read(D/'initialization_receipt.json')
assert graphics==launch['resources']['graphics']==read(D/'graphics_receipt.json')
assert resource==launch['resources']['diagnostic_receipt']
assert launch['status']=='failed' and launch['diagnostic_returncode']==1 and launch['release_consumed'] and not launch['remaining_caps_reusable']
assert all(v==0 for v in public['counts'].values()) and all(v==0 for v in initialization['entered_budget_usage'].values())
assert failure['error']=='Torch UUID property is not the frozen string ABI' and failure['failure_stage']=='heavy_imports_and_policy_device_binding'
assert not failure['measurements_completed'] and not failure['automatic_retry']
assert graphics['returned']==71 and graphics['failed']==0 and graphics['incomplete']==0 and sum(graphics['entered_budget_usage'].values())==71
ledger=rows(D/'graphics_events.jsonl');entered={r['event_id']:r for r in ledger if r['phase']=='entered'};terminal={r['event_id']:r for r in ledger if r['phase']!='entered'}
returned=collections.Counter()
for eid,row in terminal.items():
 assert row['phase']=='returned' and row['resource_units']==entered[eid]['resource_units']
 returned.update(row['resource_units'])
for key,cap in R['graphics_caps'].items():assert 0<=graphics['entered_budget_usage'][key]<=cap
api=rows(D/'graphics_api_results.jsonl');errors=[r for r in api if r['operation']=='egl_error_queries']
assert len(errors)==23 and all(r['raw']==0x3000 for r in errors)
assert read(D/'graphics_cleanup.json')['errors']==[]
assert graphics['entered_budget_usage']['egl_release_thread_calls']==1
mapping=read(D/'device_mapping.json');policy=read(D/'policy_device.json');loader=read(D/'loader_identity.json')
assert mapping['stage']=='unique_mapping_complete' and len(mapping['devices'])==8
expected={row['gpu_uuid']:row['pci_bus_id'] for row in R['physical_inventory']};observed={row['mapping']['gpu_uuid']:row['mapping']['pci_bus_id'] for row in mapping['devices']};assert expected==observed
selected=[row for row in mapping['devices'] if row['decision']=='target'];assert len(selected)==1
assert selected[0]['mapping']=={k:R[k] for k in ['gpu_uuid','pci_bus_id']}
assert 'GPU-'+policy['torch_uuid_raw']==R['gpu_uuid']
assert 'after_torch_device_binding' not in loader
claim=read(B/'results/A/P10_native_release_claims/P10_A_NATIVE_PREFLIGHT_V2.json');assert claim['release_sha256']=='bd38ccbf541af9d52ade18da27e64c3ef04c853c9aa76d7f363ec2712b671c04'
assert read(W/'COMMAND_EXIT.json')['real_sh_invocations']==1 and read(W/'COMMAND_EXIT.json')['automatic_retries']==0
family=read(RUN/'process_family_cleanup.json');assert family['status']=='all_formal_group_members_exited' and family['actions']==[]
assert read(W/'POST_COMMAND_PROCESSES.json')['matching_native_processes']==[]
restoration=launch['restoration'];assert restoration['status']=='occupancy_resolved'
gpus=restoration['guard_status']['gpus'];assert set(gpus)==set(map(str,range(8))) and all(r['state']=='holder' and r['driver_pids'] for r in gpus.values())
marks=rows(RUN/'wave_timing.jsonl');times={r['phase']:r for r in marks};offset=marks[0]['unix_seconds']-marks[0]['monotonic_seconds']
first_cuda=next(r['monotonic_ns']/1e9+offset for r in ledger if r['phase']=='entered' and r['operation']=='cuda_driver_initializations')
guardlog=(W/'GUARD_LOG_WINDOW.log').read_text();yield_times={};restart_times={}
for line in guardlog.splitlines():
 m=re.match(r'(\S+) GPU (\d): (.*)',line)
 if not m:continue
 when=datetime.datetime.fromisoformat(m[1].replace('Z','+00:00')).timestamp()
 if 'yielded' in m[3]:yield_times[m[2]]=when
 if 'started holder manager' in m[3]:restart_times[m[2]]=when
assert set(yield_times)==set(map(str,range(8))) and set(restart_times)==set(map(str,range(8)))
assert max(yield_times.values())+1<=first_cuda # guard logs are only second-resolution
assert min(restart_times.values())>=times['timed_process_exited']['unix_seconds']
observations=rows(W/'CPU_PROCESS_AND_GUARD_OBSERVATIONS.jsonl')
assert len(observations)==read(W/'COMMAND_EXIT.json')['CPU_observation_samples']
# Stale guard snapshots during serial holder shutdown are kept as observations,
# never reinterpreted as per-sample NVML GPU activity measurements.
counts=dict(public=public,initialization=initialization,graphics=graphics,
 observations={k:resource[k] for k in ['diagnostic_native_resets_returned','diagnostic_observations_returned','post_control_observations_returned','complete_observations_returned','usable_observation_artifacts']},
 single_release_claim=1,real_sh_invocations=1,diagnostic_attempts_entered=0,retries=0,deletions=0,
 explicit_identity_query_scope='Frozen launcher and child verify_device paths reached; 2 NVML identity CLI calls by source path, no extra observer query',
 total_GPU_seconds=None,peak_GPU_memory_bytes=None,unmetered_framework_cuda_context_or_kernel_count=None,
 missing_GPU_measurements_reason='Failure before sampler timing and CUDA peak-memory reporting; no extra NVML observation added after release consumption')
publish(W/'ACTUAL_COUNTS.json',counts)
with (W/'GRAPHICS_COUNTS.csv').open('x') as f:
 f.write('operation,cap,entered,returned,failed,incomplete\n')
 for key,cap in R['graphics_caps'].items():f.write(f"{key},{cap},{graphics['entered_budget_usage'][key]},{returned[key]},0,0\n")
policy_evidence=dict(mapping_physical_identity_passed=True,selected_EGL_index=selected[0]['egl_index'],selected_EGL_handle=selected[0]['egl_handle'],selected_CUDA_attribute_handle=selected[0]['attribute']['value'],physical_target=selected[0]['mapping'],
 policy_logical_index=policy['logical_index'],torch_uuid_saved_string_representation=policy['torch_uuid_raw'],text_representation_matches_target=True,
 policy_uuid_guard_passed=False,actual_runtime_UUID_python_type=None,
 missing_type_reason='Frozen entry saved str(properties.uuid), not its Python type. Failure proves original value did not satisfy isinstance(value,str); do not infer the exact class from the displayed text.',
 after_torch_loaded_library_identity_verified=False,after_torch_missing_reason='Guard failed before after_torch_device_binding loader snapshot',
 no_new_runtime_probe=True,evidence=[ref(D/'policy_device.json'),ref(D/'failure.json'),ref(D/'device_mapping.json'),ref(D/'loader_identity.json'),ref(P/'code/core/native_egl.py')])
publish(W/'POLICY_UUID_FAILURE_EVIDENCE.json',policy_evidence)
missing=read(D/'artifact_status.json');assert all(not item['present'] for item in missing['artifacts'].values())
missing['requested_outputs_not_reached']=['5H paired-noise/raw50 plans/queue checks','one real transition','initial and post-control RGB','renderer identity']
missing['RGB_visual_validation']='not possible:0renders/0readbacks/0saved images';missing['CPU_PNG_conversions']=0
publish(W/'MISSING_ARTIFACTS.json',missing)
audit=dict(status='technical_failure_evidence_consistent',native_preflight_outcome='failed',failure_stage=failure['failure_stage'],error=failure['error'],
 independent_ledger_reconciliation=True,graphics_entered=71,graphics_returned=71,graphics_failed=0,graphics_incomplete=0,EGL_error_queries=23,EGL_errors_all_success=True,
 semantic_failure_is_not_a_failed_EGL_call=True,counts=counts,policy_UUID=policy_evidence,
 occupancy=dict(guard_pid=restoration['guard_status']['pid'],restored_holder_managers={k:v['manager_pid'] for k,v in gpus.items()},all_eight_restored=True,
 process_family_cleanup=family,no_matching_processes_after_command=True,yield_times_unix=yield_times,restart_times_unix=restart_times,
 first_explicit_cuInit_unix=first_cuda,all_yield_log_seconds_end_before_first_cuInit=True,all_holder_restarts_after_group_exit=True,
 guard_snapshot_scope='Existing guard status samples, not new NVML samples; shutdown snapshots may be stale until guard finishes its loop'),
 timing=launch['timing'],CPU_observation=read(W/'COMMAND_EXIT.json'),
 no_retries_or_extra_checker=True,current_release_sha256=sha(B/'releases/P10_A_NATIVE_PREFLIGHT_V2.json'),
 code_manifest_still_matches_release=sha(P/'code/CODE_MANIFEST.json')==R['code_manifest_sha256'],
 proposal_still_matches_release=sha(P/'proposal/PROPOSAL.json')==R['proposal_sha256'],
 GPU_queries_by_this_audit=0,large_weight_rehashes_by_this_audit=0,checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
publish(W/'FINAL_AUDIT.json',audit)
print(json.dumps(dict(status=audit['status'],graphics_entered=71,model_initializations=0,native_resets=0,native_samples=0,flow_calls=0,policy_steps=0,RGB_frames=0,restored_holders=8,CPU_peak_observed_process_MiB=read(W/'COMMAND_EXIT.json')['peak_observed_per_process_RSS_KiB']/1024)))
