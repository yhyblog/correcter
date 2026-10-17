from pathlib import Path
import json,hashlib,shlex,ast
b=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
p=b/'results/A/A10_NATIVE_EGL_INTEGRATION_CPU_V1'
g=b/'results/A/A10_EGL_CUDA_MAP_CPU_V1';v4=b/'results/A/A10_PREFLIGHT_REVISION_R2/preflight_v4'
sp=Path('/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/lib/python3.12/site-packages')
def read(f):return json.loads(Path(f).read_text())
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def write(f,x):Path(f).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def ref(f):
 f=Path(f);return dict(path=str(f),realpath=str(f.resolve()),size_bytes=f.stat().st_size,sha256=sha(f))
config=read(p/'config/INTEGRATION.json');proposal=read(v4/'PROPOSAL.json')
old_external=read(v4/'external_source_manifest.json');graphics_external=read(g/'EXTERNAL_SOURCE_MANIFEST.json')
files={r['path']:r for r in graphics_external['files']}
for r in old_external['files']:
 if r['path'] in files:assert r['sha256']==files[r['path']]['sha256']
 files[r['path']]=r
new_sources=['gymnasium/envs/mujoco/mujoco_rendering.py','gymnasium/envs/mujoco/mujoco_env.py',
 'mujoco/__init__.py','mujoco/egl/__init__.py','mujoco/rendering/classic/gl_context.py',
 'mujoco/rendering/classic/renderer.py','torch/_C/__init__.pyi','torch/cuda/__init__.py','torch/random.py']
for s in new_sources:
 r=ref(sp/s)
 if r['path'] in files:assert r['sha256']==files[r['path']]['sha256'],'source drift '+s
 files[r['path']]=r
external=dict(files=list(sorted(files.values(),key=lambda r:r['path'])),source_hooks=old_external['source_hooks'],
 scope='Reuse accepted graphics runtime and native initialization identities; only named integration source files rehashed in CPU task. Full runtime verification deferred to new released entry.',
 inherited_manifests=[ref(v4/'external_source_manifest.json'),ref(g/'EXTERNAL_SOURCE_MANIFEST.json')],
 targeted_sources=[ref(sp/s) for s in new_sources])
write(p/'EXTERNAL_SOURCE_MANIFEST.json',external)
write(p/'proposal/source_manifest.json',read(v4/'source_manifest.json'))
python=proposal['python']
for name,entry in [('run_proposed_native_preflight.sh','launch_preflight.py'),('check_authorization_cpu.sh','authorize_cpu.py')]:
 s='#!/usr/bin/env bash\nset -euo pipefail\nif [[ $# != 1 ]]; then\n  echo "Usage: $0 NEW_RELEASE_JSON" >&2\n  exit 2\nfi\n'
 s+='exec '+shlex.quote(python)+' -B '+shlex.quote(str(p/'code'/entry))+' --campaign '+shlex.quote(str(b))+' --proposal '+shlex.quote(str(p/'proposal/PROPOSAL.json'))+' --release "$1"\n'
 f=p/'commands'/name;f.write_text(s);f.chmod(0o755)
code_files=[dict(path=str(f.relative_to(p/'code')),size_bytes=f.stat().st_size,sha256=sha(f)) for f in sorted((p/'code').rglob('*')) if f.is_file() and f.name!='CODE_MANIFEST.json' and '__pycache__' not in f.parts]
write(p/'code/CODE_MANIFEST.json',dict(schema_version=1,root=str(p/'code'),files=code_files))
# Reuse existing isolated libraries without another copy or fresh large-file hash.
libs=[]
for r in read(g/'BUNDLE_MANIFEST.json')['files']:
 if r['path'].startswith('isolation/'):
  f=g/r['path'];assert f.stat().st_size==r['size_bytes']
  libs.append(dict(r,path=str(f),realpath=str(f.resolve()),identity_basis='accepted graphics bundle; full SHA rechecked only by future released entry'))
write(p/'REUSED_ASSETS.json',dict(libraries=libs,accepted_graphics_bundle=ref(g/'BUNDLE_MANIFEST.json'),
 model=dict(path=proposal['checkpoint'],model_sha256=proposal['model_sha256'],weight_rehashed_this_task=False),
 shared_package_writes=0,original_v4_v5_writes=0))
manifest_files=[ref(p/'code/CODE_MANIFEST.json'),ref(p/'config/INTEGRATION.json'),ref(p/'EXTERNAL_SOURCE_MANIFEST.json'),ref(p/'REUSED_ASSETS.json'),ref(p/'proposal/source_manifest.json')]
for folder in ['commands','tests']:
 manifest_files += [ref(f) for f in sorted((p/folder).iterdir()) if f.is_file()]
for f in [p/'INTEGRATION_NOTES.md',p/'STATIC_CALL_AUDIT.json',p/'CAPS_AND_CONTROL.md']:
 if f.exists():manifest_files.append(ref(f))
manifest_files += libs
write(p/'INTEGRATION_MANIFEST.json',dict(files=manifest_files,exclusions=['PROPOSAL/RELEASE_TEMPLATE/CONTROL_REQUIRED/CPU_READY depend on this manifest; all bound by final receipt'],runtime_verification='Full SHA + realpath checks in new entry'))
proposal.update(proposal_id='A10_NATIVE_PREFLIGHT_V2_EGL_INTEGRATION_R1',task_id='A10_PREFLIGHT_NATIVE_V2',status='proposed_not_released',
 code_manifest_path=str(p/'code/CODE_MANIFEST.json'),source_manifest_path=str(p/'proposal/source_manifest.json'),source_manifest_sha256=sha(p/'proposal/source_manifest.json'),
 external_source_manifest_path=str(p/'EXTERNAL_SOURCE_MANIFEST.json'),external_source_manifest_sha256=sha(p/'EXTERNAL_SOURCE_MANIFEST.json'),
 initialization_source_manifest_path=str(v4/'external_source_manifest.json'),
 integration_manifest_path=str(p/'INTEGRATION_MANIFEST.json'),integration_manifest_sha256=sha(p/'INTEGRATION_MANIFEST.json'),
 integration_config_path=str(p/'config/INTEGRATION.json'),integration_config_sha256=sha(p/'config/INTEGRATION.json'),
 **{k:config[k] for k in ['graphics_caps','device','physical_inventory','cuda_environment','isolation_root','python_library_directory']},
 identity_probe_caps={'native_nvml_identity_queries':2},
 observation_caps=dict(diagnostic_native_resets_returned=1,diagnostic_observations_returned=1,post_control_observations_returned=1,complete_observations_returned=2,usable_observation_artifacts=2),
 private_render_route='mujoco.egl module shim -> Gymnasium OffScreenViewer -> existing native camera/render/readPixels',
 library_call_scope='Explicit adapter API calls only. CUDA/GL calls made internally by torch, MuJoCo and driver are not individually instrumented; no claim of globally one cuInit or zero CUDA kernels.',
 process_family_scope='guard-created isolated session; no detached descendants; retain reservation until all live group members exit including failure; TERM then KILL after 30s; post-KILL drain has no finite wall guarantee',
 real_command=[str(p/'commands/run_proposed_native_preflight.sh'),'NEW_RELEASE_JSON'],
 cpu_authorization_command=[str(p/'commands/check_authorization_cpu.sh'),'NEW_RELEASE_JSON'])
proposal['required_inputs']=[dict(r,verification_now='inherited frozen identity; not freshly revalidated this task') for r in proposal['required_inputs']]
proposal['required_inputs'] += [ref(b/'manifests/A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_FINAL_ACCEPTANCE.json'),ref(g/'BUNDLE_MANIFEST.json'),ref(p/'config/INTEGRATION.json')]
proposal['native_control_minimum_limits']={**proposal['control_minimum_limits'],**proposal['resource_caps'],**proposal['initialization_caps'],**config['graphics_caps'],'completed_rollouts':0,'native_nvml_identity_queries':2,'metaworld_environment_instances':2,'physics_steps':26013}
proposal['resource_estimates']['output_retention'] += ['graphics_events/raw_API_results/mapping/loader/renderer/cleanup','RGB_diagnostic.ppm','RGB_post_control.ppm','RGB_provenance','policy_device','exclusive release claim','process_family_cleanup']
proposal['resource_estimates']['source_package_bytes_hashed']=sum(r.get('size_bytes',r.get('bytes',0)) for r in external['files'])
proposal['resource_estimates']['estimate_note']='40GiB model VRAM + up to1GiB graphics overhead estimate;64GiB RAM/2GiB outputs; two full model SHA passes at real launch, zero this CPU task. Actual GPU/driver/framework internal API counts unmeasured.'
proposal['resource_estimates']['vram_peak_GiB_estimate']=41
proposal['timeout_accounting']['inside'] += ['explicit CUDA/EGL mapping, private native two-observation rendering, GPU binding and graphics cleanup']
proposal['timeout_accounting']['outside'] += ['post-timeout process-group drain while retaining all-GPU reservation']
proposal['counter_scope']['graphics']='graphics_caps meter explicit adapter calls and instrumented Gymnasium/MuJoCo Python boundaries; RGB readPixels also fetches a depth buffer internally'
proposal['counter_scope']['observations']='Native reset1 return is separate from initial full observation1 and post-control full observation1; up to2 saved NPZ artifacts; PPM views add no render/artifact units'
write(p/'proposal/PROPOSAL.json',proposal)
t=read(v4/'RELEASE_TEMPLATE.json')
t.update(status='TEMPLATE_NOT_AUTHORIZED',task_id=proposal['task_id'],release_id='P10_A_NATIVE_PREFLIGHT_V2',
 wave_id='corrector-sim-20260919-A-native-V2-wave04',run_id='A10_PREFLIGHT_NATIVE_V2_r1_A_wave04',shard_id='A-native-V2-shelf-place-once',
 proposal_sha256=sha(p/'proposal/PROPOSAL.json'),code_manifest_sha256=sha(p/'code/CODE_MANIFEST.json'),
 **{k:proposal[k] for k in ['graphics_caps','initialization_caps','external_source_manifest_sha256','integration_manifest_sha256','integration_config_sha256','cuda_environment','physical_inventory','identity_probe_caps']},
 pci_bus_id=config['device']['pci_bus_id'],
 instructions='TEMPLATE ONLY. Analysis must issue new status=released file, update CONTROL with exact active task/release/path and complete global+per-task limits, bind TASK_BOARD. CPU checker does not claim or query NVML. Real launcher already checks all SHA; do not add third model hash. Old releases never authorize native V2.',
 real_command=proposal['real_command'],cpu_authorization_command=proposal['cpu_authorization_command'],max_retries=0)
write(p/'proposal/RELEASE_TEMPLATE.json',t)
write(p/'proposal/CONTROL_REQUIRED.json',dict(status='TEMPLATE_NOT_AUTHORIZED',mode='preflight',formal_gpu_runs_enabled=True,stop_requested=False,
 active_compute_release_id=t['release_id'],active_compute_release='releases/'+t['release_id']+'.json',active_compute_task_ids=[proposal['task_id']],allowed_task_ids=[proposal['task_id']],
 compute_limit_semantics='Replace the old graphics-only limits table; do not carry forward old global cuda_context_creations=0/cuda_kernel_launches=0 into a native model task. Explicit adapter calls are metered; framework internals unmetered at API-call granularity. physics_steps26013 is alias total of26000init+13policy; do not sum with components.',
 current_compute_limits=proposal['native_control_minimum_limits'],per_task_compute_limits={proposal['task_id']:proposal['native_control_minimum_limits']},
 task_board_entry=dict(id=proposal['task_id'],revision=1,owner='A',status='ready',release='releases/'+t['release_id']+'.json')))
print(json.dumps(dict(code_files=len(code_files),external_files=len(external['files']),integration_refs=len(manifest_files),proposal_sha256=sha(p/'proposal/PROPOSAL.json'),status='PROPOSED_NOT_AUTHORIZED')))
