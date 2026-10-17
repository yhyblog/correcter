from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import os
import shlex
import shutil
import sys
import xml.etree.ElementTree as ET

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W = B/'work/A/A10_EGL_CPU_REPAIR_V1_r1'
FINAL = B/'results/A/A10_EGL_CPU_REPAIR_V1'
STAGE = B/'results/A/A10_EGL_CPU_REPAIR_V1.publishing_r1'
ENV = Path('/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/environments/lerobot')
sys.path.insert(0, str(W/'code'))
from probe_contract import CAPS, TASK

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()

def save(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

assert not FINAL.exists() and not STAGE.exists()
STAGE.mkdir()
for name in ['code','isolation','native_code_snapshot_v5']:
    shutil.copytree(W/name,STAGE/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copyfile(W/'scene.xml',STAGE/'scene.xml')
(STAGE/'proposal').mkdir();(STAGE/'commands').mkdir();(STAGE/'evidence').mkdir()
save(STAGE/'isolation/vendor/10_nvidia.json', {'file_format_version':'1.0.0',
    'ICD':{'library_path':str(FINAL/'isolation/lib/libEGL_nvidia.so.535.161.08')}})
for name in ['HOST_STATIC_LOADER.json','RUNTIME_METADATA.json','ELF_AND_VENDOR_STATIC.json',
             'NVIDIA_DYNAMIC_LIBRARY_HINTS.json','STATIC_DEPENDENCY_CLOSURE.json']:
    shutil.copyfile(W/name,STAGE/'evidence'/name)
shutil.copyfile(W/'evidence/CPU_TESTS_r1.json',STAGE/'evidence/CPU_TESTS_r1.json')
for name in ['OFFICIAL_PACKAGE_RECORDS.json','DOWNLOADED_PACKAGES.json','SHADER_PACKAGE.json']:
    shutil.copyfile(W/'downloads'/name,STAGE/'evidence'/name)

# Freeze only sources/libraries used by this graphics loader and explicit runtime.
sp=ENV/'lib/python3.12/site-packages'
external={ENV/'bin/python',Path('/usr/bin/nvidia-smi'),Path('/usr/bin/timeout'),
    Path('/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh'),
    Path('/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py')}
for name in ['mujoco','OpenGL']:
    for p in (sp/name).rglob('*'):
        if p.is_file() and (p.suffix=='.py' or '.so' in p.name):external.add(p)
for name in ['mujoco-3.6.0.dist-info','pyopengl-3.1.10.dist-info','numpy-2.2.6.dist-info']:
    external.update([sp/name/'METADATA',sp/name/'RECORD'])
external.update((sp/'numpy/_core').glob('*.so'))
external.update((ENV/'lib/python3.12/lib-dynload').glob('_ctypes.cpython*.so'))
closure=json.loads((W/'STATIC_DEPENDENCY_CLOSURE.json').read_text())
external.update(Path(r['path']) for r in closure['closure'] if not Path(r['path']).is_relative_to(W))
ext=[]
for p in sorted(external):
    assert p.is_file(),p
    ext.append(dict(path=str(p),realpath=str(p.resolve()),size_bytes=p.stat().st_size,sha256=sha(p)))
save(STAGE/'EXTERNAL_SOURCE_MANIFEST.json',{'files':ext,'scope':'Installed graphics/Python source identities, exact bindings and static ELF dependencies; no code imported for this manifest'})

old=B/'results/A/A10_PREFLIGHT_REVISION_R2/code_snapshot_v4'
native=STAGE/'native_code_snapshot_v5'
rows=[];changes=[]
for p in sorted(native.rglob('*')):
    if not p.is_file() or p.name=='CODE_MANIFEST.json':continue
    rel=str(p.relative_to(native));value=sha(p)
    rows.append(dict(path=rel,sha256=value,size_bytes=p.stat().st_size))
    if not (old/rel).exists() or sha(old/rel)!=value:changes.append(rel)
assert set(changes)=={'preflight_pi05.py','core/observation_accounting.py'},changes
save(native/'CODE_MANIFEST.json',dict(version='v5_CPU_observation_counter_correction_only',
    root=str(FINAL/'native_code_snapshot_v5'),files=rows,changes_from_v4=changes,
    parent_manifest_sha256=sha(old/'CODE_MANIFEST.json'),native_GPU_release=None,
    execution_status='Code-only correction; no new native proposal/release. Closed v4 release is not reusable.'))

for script,entry in [('check_authorization_cpu.sh','authorize_cpu.py'),('run_proposed_graphics_probe.sh','launch_graphics.py')]:
    s='#!/usr/bin/env bash\nset -euo pipefail\nif [[ $# != 1 ]]; then echo "usage: $0 /absolute/path/to/new-graphics-release.json" >&2; exit 2; fi\n'
    s+='exec /usr/bin/python3 -B '+shlex.quote(str(FINAL/'code'/entry))+' --campaign '+shlex.quote(str(B))+' --release "$1" --proposal '+shlex.quote(str(FINAL/'proposal/PROPOSAL.json'))+'\n'
    p=STAGE/'commands'/script;p.write_text(s);p.chmod(0o755)

device=dict(gpu_uuid='GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe',gpu_index=0,
            gpu_model='NVIDIA H100 80GB HBM3',driver='535.161.08',pci_bus_id='0000:0f:00.0')
isolated_env=dict(MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',
    __EGL_VENDOR_LIBRARY_FILENAMES=str(FINAL/'isolation/vendor/10_nvidia.json'),
    LD_LIBRARY_PATH=':'.join([str(FINAL/'isolation/lib'),str(ENV/'lib'),'/usr/lib/x86_64-linux-gnu','/lib/x86_64-linux-gnu']),
    CUDA_VISIBLE_DEVICES=device['gpu_uuid'],__GL_SHADER_DISK_CACHE='0',
    unset=['LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID'])
save(STAGE/'ISOLATED_ENVIRONMENT.json',{'scope':'Future released process only; does not change existing container capability mounts','environment':isolated_env})
source_urls=[
 'https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html',
 'https://developer.download.nvidia.com/compute/cuda/repos/debian11/x86_64/',
 'https://raw.githubusercontent.com/NVIDIA/libglvnd/master/src/EGL/libeglvendor.c',
 'https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_device_drm.txt',
 'https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_device_drm_render_node.txt',
 'https://mujoco.readthedocs.io/en/3.6.0/python.html']
save(STAGE/'TECHNICAL_REFERENCES.json',{'sources':source_urls,'source_version_policy':'Installed source/ELF SHA governs this proposal; web docs explain capabilities and mapping, not actual graphics outcome'})
save(STAGE/'DEPENDENCIES.json',{'staged_files':[dict(path=str(FINAL/p.relative_to(STAGE)),size_bytes=p.stat().st_size,sha256=sha(p)) for p in sorted((STAGE/'isolation/lib').iterdir())],
    'package_download_bytes':21961782,'package_source':'NVIDIA official HTTPS repository; exact Packages SHA256 matched before extraction',
    'nvidia_userspace_version':'535.161.08','kernel_version_match_source':'/proc/driver/nvidia/version; actual launch also checks NVML',
    'GLVND_source':'Existing conda-forge1.7.0 libraries copied byte-identically',
    'static_ELF_unresolved_DT_NEEDED':closure['unresolved_DT_NEEDED'],'shared_installation':False,
    'remaining_unknown':'Driver/device graphics support, mapping extension availability and runtime dynamic dependencies await exactly one independently released probe'})

static_files=list((STAGE/'code').glob('*.py'))+[native/'preflight_pi05.py',native/'core/observation_accounting.py']
for p in static_files:ast.parse(p.read_text(),filename=str(p))
xml=ET.parse(STAGE/'scene.xml').getroot()
assert not xml.findall('.//joint') and not xml.findall('.//freejoint') and not xml.findall('.//actuator')
save(STAGE/'evidence/STATIC_CODE_CHECK.json',dict(status='passed',AST_files=[str(FINAL/p.relative_to(STAGE)) for p in static_files],
    static_scene_no_dynamic_joints_or_actuators=True,native_v5_changes=changes,
    GPU_or_graphics_or_environment_execution=False))

# Content identity covers executable/config/library material; no recursive proposal hash.
bound=[]
for p in sorted(STAGE.rglob('*')):
    if p.is_file() and p.relative_to(STAGE).parts[0] not in ['proposal','evidence']:
        bound.append(dict(path=str(p.relative_to(STAGE)),sha256=sha(p),size_bytes=p.stat().st_size))
save(STAGE/'BUNDLE_MANIFEST.json',dict(schema_version=1,root=str(FINAL),files=bound))
proposal=dict(schema_version=1,status='proposed_not_released',campaign_id='corrector-sim-20260919',task_id=TASK,
    task_revision=1,role='A',published_root=str(FINAL),created_at_utc=datetime.now(timezone.utc).isoformat(),
    dependency='P10_A_NATIVE_PREFLIGHT_V1 consumed technical failure, closed; no reuse',
    bundle_manifest_sha256=sha(STAGE/'BUNDLE_MANIFEST.json'),external_source_manifest_sha256=sha(STAGE/'EXTERNAL_SOURCE_MANIFEST.json'),
    device=device,python=str(ENV/'bin/python'),python_library_directory=str(ENV/'lib'),
    renderer_route='NVIDIA_EGL',resource_caps=CAPS,max_retries=0,timeout_seconds=120,kill_grace_seconds=10,
    wave_participants=['A'],occupancy_lifecycle='/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh',
    occupancy_policy='Reserve all8 A GPUs; stop all A holder compute for entire child process family, including failure; restore only after wave exit; B unaffected',
    graphics_worker_processes=1,initialization='One static MuJoCo model/data, no joints or actuators, one explicit mj_forward; no mj_step/reset/MetaWorld/policy',
    mapping='One eglQueryDevicesEXT with16 slots; reject empty/truncated list; <=48 device strings via DRM/sysfs PCI/kernel UUID; select unique fixed GPU before one display initialization; no ordinal assumption or device retry',
    counter_boundary='Counts are probe application API invocations; GLVND internal per-vendor dispatch and OpenGL driver internal work are not separately claimed. Explicit lookup/string counters are named accordingly.',
    physical_time_advance_seconds=0,timeout_scope='Timed graphics child includes repeated CPU SHA, imports, EGL mapping/init, static scene, one render/readback, cleanup; pre-hash/reservation/release/restoration outside',
    end_to_end_strict_upper_bound_seconds=None,restoration_observation_timeout_seconds=120,
    outputs=['device_mapping.json','renderer_identity.json','rgb.npy','rgb.ppm','shape/dtype/hash','cleanup.json','phase events','RESULT.json','LAUNCH_RESULT.json'],
    resource_estimates_not_measured={'peak_GPU_memory_MiB':1024,'peak_process_RAM_MiB':2048,'new_run_output_disk_MiB':32},
    limits_of_success='Proves single static EGL RGB readback only; not MetaWorld full reset/render chain, VLA/P/V, rollout or training',
    platform_action_now='None required to finish CPU preparation. Local matched userspace isolation prepared. Need platform only if future bounded probe proves device/mount/driver capability issue.')
save(STAGE/'proposal/PROPOSAL.json',proposal)
template=dict(schema_version=1,status='NOT_RELEASED_TEMPLATE',campaign_id='corrector-sim-20260919',task_id=TASK,task_revision=1,
    role='A',hostname='trial-303224955-trialrun-303224955-worker-0',release_id=None,run_id=None,wave_id=None,shard_id=None,
    proposal_sha256=sha(STAGE/'proposal/PROPOSAL.json'),bundle_manifest_sha256=proposal['bundle_manifest_sha256'],**device,
    renderer_route='NVIDIA_EGL',resource_caps=CAPS,max_retries=0,timeout_seconds=120,kill_grace_seconds=10,wave_participants=['A'],
    required_CONTROL='New active release ID/path and task; formal_gpu_runs_enabled=true; graphics caps at least as specified; analysis task board owner A/revision1/status ready or released',
    previous_release_reusable=False)
save(STAGE/'proposal/RELEASE_TEMPLATE.json',template)
os.rename(STAGE,FINAL)
print(json.dumps({'published_root':str(FINAL),'proposal_sha256':sha(FINAL/'proposal/PROPOSAL.json'),
    'bundle_manifest_sha256':sha(FINAL/'BUNDLE_MANIFEST.json'),'external_files':len(ext),'native_changed_files':changes,
    'staged_library_bytes':sum(p.stat().st_size for p in (FINAL/'isolation/lib').iterdir())},indent=2))
