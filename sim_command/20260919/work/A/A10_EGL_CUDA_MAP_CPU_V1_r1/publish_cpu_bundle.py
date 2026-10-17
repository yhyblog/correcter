"""Freeze a new CPU-prepared proposal; never execute driver or graphics entry points."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

WORK = Path(__file__).resolve().parent
BASE = WORK.parents[2]
OLD = BASE/'results/A/A10_EGL_CPU_REPAIR_V1'
PUB = BASE/'results/A/A10_EGL_CUDA_MAP_CPU_V1'
STAGE = PUB.with_name(PUB.name + '.pending')
assert not PUB.exists() and not STAGE.exists()
sys.path.insert(0, str(WORK/'code'))
from probe_contract import CAPS, TASK
from cuda_mapping import EXPECTED_ABI
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
STAGE.mkdir()


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def put(rel,obj):
    p=STAGE/rel;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(obj if isinstance(obj,str) else json.dumps(obj,ensure_ascii=False,indent=2)+'\n')


def external(path):
    return dict(path=str(path),realpath=str(path.resolve()),size_bytes=path.stat().st_size,sha256=sha(path))


for name in ['authorize_cpu.py','graphics_probe.py','launch_graphics.py','probe_contract.py',
             'run_reserved_graphics.py','wave_timing.py','cuda_mapping.py']:
    p=STAGE/'code'/name;p.parent.mkdir(exist_ok=True);shutil.copy2(WORK/'code'/name,p)
put('tests/test_cuda_mapping.py',(WORK/'tests/test_cuda_mapping.py').read_text())
put('VISIBILITY_AND_IDENTITY.json',json.loads((WORK/'VISIBILITY_AND_IDENTITY.json').read_text()))
visibility=json.loads((WORK/'VISIBILITY_AND_IDENTITY.json').read_text())
shutil.copytree(OLD/'isolation/lib',STAGE/'isolation/lib',symlinks=True)
cuda_source=Path('/usr/lib/x86_64-linux-gnu/libcuda.so.535.161.08')
cuda_copy=STAGE/'isolation/lib'/cuda_source.name
shutil.copy2(cuda_source,cuda_copy)
assert sha(cuda_copy)=='81b63dae639c3b1bc47692a63cab356419deaabda0fe0ce7f538c52351cc6084'
(STAGE/'isolation/lib/libcuda.so.1').symlink_to(cuda_source.name)
put('isolation/vendor/10_nvidia.json',{'file_format_version':'1.0.0','ICD':{
    'library_path':str(PUB/'isolation/lib/libEGL_nvidia.so.535.161.08')}})
shutil.copy2(OLD/'scene.xml',STAGE/'scene.xml')
for name in ['CUDA_STATIC_DISCOVERY.json','CUDA_DRIVER_ELF.json','CPU_SYNTHETIC_r1.json','CPU_SYNTHETIC_r1.log']:
    put('evidence/'+name,(WORK/name).read_text())
source_manifest=json.loads((OLD/'BUNDLE_MANIFEST.json').read_text())
old_hash={x['path']:x['sha256'] for x in source_manifest['files']}
reused=[]
for p in sorted((STAGE/'isolation/lib').iterdir()):
    rel=str(p.relative_to(STAGE))
    if 'libcuda' not in p.name:
        assert sha(p)==old_hash[rel]
        reused.append(dict(path=rel,sha256=sha(p),source=str(OLD/rel)))
put('REUSED_GRAPHICS_STACK.json',{'original_bundle':external(OLD/'BUNDLE_MANIFEST.json'),'files':reused,
    'scene_unchanged_sha256':sha(OLD/'scene.xml'),'original_modified':False})
ext=json.loads((OLD/'EXTERNAL_SOURCE_MANIFEST.json').read_text())
by_path={r['path']:r for r in ext['files']}
added=[]
for p in [cuda_source,Path('/usr/local/cuda/targets/x86_64-linux/include/cuda.h')]:
    row=external(p);by_path[str(p)]=row;added.append(row)
needed=['libm.so.6','libc.so.6','libdl.so.2','libpthread.so.0','librt.so.1']
envlib=Path(json.loads((OLD/'proposal/PROPOSAL.json').read_text())['python_library_directory'])
closure=[]
for name in needed:
    candidates=[STAGE/'isolation/lib'/name,envlib/name,Path('/usr/lib/x86_64-linux-gnu')/name,Path('/lib/x86_64-linux-gnu')/name]
    chosen=next(p for p in candidates if p.exists())
    row=external(chosen);closure.append(row)
    if row['path'] not in by_path:added.append(row)
    by_path[row['path']]=row
ext['files']=sorted(by_path.values(),key=lambda r:r['path'])
ext['lineage']={'base_manifest':external(OLD/'EXTERNAL_SOURCE_MANIFEST.json'),
    'unchanged_runtime_entries_reused_without_CPU_full_rehash':True,
    'new_entries_statically_read_and_hashed':added,
    'future_real_launcher_policy':'Full bundle and external-file SHA verification before lifecycle and again inside timed child'}
put('EXTERNAL_SOURCE_MANIFEST.json',ext)
put('CUDA_DRIVER_IDENTITY.json',{'source':external(cuda_source),'staged_path':str(PUB/'isolation/lib'/cuda_source.name),
    'staged_sha256':sha(cuda_copy),'driver_version':'535.161.08','ELF_arch':'ELF64 x86-64',
    'SONAME':'libcuda.so.1','required_export_symbols':['cuInit','cuDeviceGetPCIBusId'],
    'DT_NEEDED_static_resolution':closure,
    'loading_order':['absolute staged libcuda.so.535.161.08 RTLD_GLOBAL|RTLD_NOW','absolute staged libEGL.so.1','isolated explicit NVIDIA EGL vendor'],
    'ambient_compat_excluded':'/usr/local/cuda/compat/libcuda.so.550.90.12 (ambient LD_LIBRARY_PATH and ldconfig preferred entry)',
    'runtime_loaded_path_check':'/proc/self/maps must resolve exactly the staged libcuda, before mapping and after mapping; preloaded CUDA library refused',
    'library_loads_in_this_CPU_task':0,'runtime_validated':False})
put('ABI_CONTRACT.json',{'platform':'Linux x86_64 LP64','width_bytes':EXPECTED_ABI,
    'functions':{
        'eglQueryDeviceAttribEXT':'EGLBoolean (void* EGLDeviceEXT, int EGLint, intptr_t* EGLAttrib)',
        'cuInit':'int CUresult (unsigned int flags=0)',
        'cuDeviceGetPCIBusId':'int CUresult (char* out32, int buffer_size=32, int CUdevice)',
        'eglGetError':'int EGLint (void)'},
    'EGL_CUDA_DEVICE_NV':'0x323A','CUdevice_rule':'Use the returned EGLAttrib value unchanged only after 0..INT32_MAX check; 0 is valid; never reinterpret EGL/NVML indices',
    'return_rules':'EGLBoolean exactly1; CUresult exactly0; immediate recorded eglGetError must equal0x3000. Raw outputs retained before semantic validation.',
    'PCI_buffer':'32 bytes initialized to0xa5; require successful return plus NUL; retain whole raw buffer; normalize only lossless4/8digit-domain format',
    'cuda_header':external(Path('/usr/local/cuda/targets/x86_64-linux/include/cuda.h')),
    'header_scope':'Installed CUDA12.4 declaration evidence; unversioned used ABI cross-checked with official12.2 docs and535 ELF exports; no compiler/linker/dlopen probe'})
for name, entry in [('run_proposed_graphics_probe.sh','launch_graphics.py'),('check_authorization_cpu.sh','authorize_cpu.py')]:
    text='#!/usr/bin/env bash\nset -euo pipefail\nif [[ $# != 1 ]]; then echo "usage: $0 /absolute/path/to/new-graphics-release.json" >&2; exit 2; fi\n'
    text+=f'exec /usr/bin/python3 -B {PUB}/code/{entry} --campaign {BASE} --release "$1" --proposal {PUB}/proposal/PROPOSAL.json\n'
    put('commands/'+name,text)
put('MAPPING_DESIGN.md',f'''本轮仅 CPU 准备，真实 CUDA/EGL 调用及库加载为0。待独立 release 的新任务为 `{TASK}`。

单一路径：一次 cuInit(0) → 一次 EGL 枚举（16槽，返回1..8才继续）→ 每候选一次扩展字符串 → EGL_CUDA_DEVICE_NV 属性返回 CUDA handle → 原值经 int32 范围校验交 cuDeviceGetPCIBusId → 规范化 PCI → 当前内核 PCI/UUID 与冻结8卡 inventory核对 → 唯一固定目标才创建display/context。不同 EGL handle 对应同一PCI、零匹配、任何身份冲突或 API失败均拒绝，不调用其他卡context。

CUDA_VISIBLE_DEVICES 冻结为8个完整物理UUID（按静态PCI排序），CUDA_DEVICE_ORDER=PCI_BUS_ID；不收窄到单卡，避免把8个 EGL候选交给受单卡mask限制的 CUDA命名空间。NVIDIA_VISIBLE_DEVICES须等于现有容器元数据，父launcher先检查后继承；这里不宣称环境变量能修改容器挂载。EGL返回handle和CUDA API在同一进程、同一冻结可见性下使用；其整数大小与EGL/NVML索引无映射假设。任何不一致即停止，无变mask重试。

隔离 libcuda来自现有535.161.08，SHA见CUDA_DRIVER_IDENTITY.json；先绝对路径加载CUDA，再加载EGL，libcuda.so.1仅链接到本包535文件。LD_LIBRARY_PATH为本包lib、既有lerobot/lib、系统x86_64库；去除LD_PRELOAD和550 compat优先项。首次加载前拒绝已加载CUDA库，加载后及映射后读取/proc/self/maps核实唯一库路径。未改系统/共享环境。

所有新增CUDA/EGL返回值即时fsync到api_results.jsonl；NULL和空bytes分别编码，属性失败时保留sentinel及output_defined=false。CUresult保留整数，不额外调用CUDA错误字符串接口；每次显式EGL API后恰一次eglGetError，加调用前基线一次，error上限35。GL字符串保留raw，GL error未查询则不推断。returned表示API已返回，不等于语义成功；失败码/错误守门令外层attempt失败，entered仍计费，无退款/重试。

cuInit预算1独立列出。显式CUDA context/primary-context、内存/核函数API不调用；driver内部初始化资源未知，将记录实际显存与用时，不能据显式计数0声称内部消耗0。固定context只属目标GPU；新结果仍不验证VLA或MetaWorld。

规范依据：[EGL_NV_device_cuda](https://registry.khronos.org/EGL/extensions/NV/EGL_NV_device_cuda.txt)、[EGL device query ABI](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_device_query.txt)、[CUDA PCI API](https://docs.nvidia.com/cuda/archive/12.2.2/cuda-driver-api/group__CUDA__MEM.html)、[CUDA环境变量](https://docs.nvidia.com/cuda/archive/12.2.2/cuda-c-programming-guide/index.html#env-vars)。不实现persistent UUID、DRM备用、大小端尝试或平台重建。
''')
put('CAPS_AND_CONTROL.md','''所有预算均是probe应用显式调用上限；GLVND/driver内部调用不冒充显式计数，内部资源留待实际观测。完整caps见proposal/PROPOSAL.json。

eglGetError=35：初始基线1 + getProcAddress5 + 枚举1 + 扩展字符串8 + CUDA属性8 + platformDisplay1 + initialize1 + chooseConfig1 + bindAPI1 + createContext1 + makeCurrent2 + EGL strings2 + destroyContext1 + terminate1 + releaseThread1。含正常与失败清理；不额外drain错误、不重试。GL字符串3；显式核心EGL符号查找11，CUDA符号查找2，显式驱动库加载2。CUDA driver init1 / PCI查询8；错误字符串、UUID、count、DRM、binary查询0。

1 EGL context、1静态model/data、1显式mj_forward、1 render/readback的原路径保留；0 VLA/MetaWorld/reset/时间推进/训练/重试。120秒TERM+10秒KILL只包子进程（含hash、load、cuInit、映射、render、cleanup）；准备/预约/释放/占卡恢复另计。

分析端需使用proposal/RELEASE_TEMPLATE.json生成新的released文件，按proposal/CONTROL_REQUIRED.json更新active release、task、exact caps与对应TASK_BOARD条目。模板不是授权。旧release永不复用；本包checker遇P00或旧task先拒绝，真实launcher不能当dry-run。内部既有lifecycle在整个A进程族期间停全8holder并退出后恢复，B不参与。
''')
for name in ['run_proposed_graphics_probe.sh','check_authorization_cpu.sh']:
    subprocess.run(['bash','-n',str(STAGE/'commands'/name)],check=True)
files=[]
for p in sorted(STAGE.rglob('*')):
    if p.is_file():
        files.append({'path':str(p.relative_to(STAGE)),'size_bytes':p.stat().st_size,'sha256':sha(p)})
put('BUNDLE_MANIFEST.json',{'schema_version':1,'root':str(PUB),'files':files,
    'exclusions':'proposal and release/control templates bind this manifest; no hash cycle'})
proposal=json.loads((OLD/'proposal/PROPOSAL.json').read_text())
proposal.update(task_id=TASK,published_root=str(PUB),created_at_utc=now,
    dependency='P10_A_EGL_GRAPHICS_PROBE_V1 mapping failure accepted and closed; no reuse',
    bundle_manifest_sha256=sha(STAGE/'BUNDLE_MANIFEST.json'),external_source_manifest_sha256=sha(STAGE/'EXTERNAL_SOURCE_MANIFEST.json'),
    resource_caps=CAPS,mapping='EGL_NV_device_cuda -> unchanged returned CUDA handle -> PCI -> kernel UUID -> fixed NVML target; unique only',
    cuda_environment=visibility['environment'],physical_inventory=visibility['inventory'],
    CUDA_driver_identity=str(PUB/'CUDA_DRIVER_IDENTITY.json'),ABI_contract=str(PUB/'ABI_CONTRACT.json'),
    raw_diagnostics='api_results.jsonl records raw NULL/empty/return values and budgeted EGL error observations',
    helper_caps_derivation=str(PUB/'CAPS_AND_CONTROL.md'),
    outputs=proposal['outputs']+['api_results.jsonl','loader_identity.json'],
    platform_action_now='None; no driver/device mounts or container changes. CPU prepared, runtime CUDA/EGL mapping remains unvalidated.')
put('proposal/PROPOSAL.json',proposal)
release_id='P10_A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1'
template={'schema_version':1,'status':'TEMPLATE_NOT_AUTHORIZED','campaign_id':proposal['campaign_id'],
    'task_id':TASK,'task_revision':1,'role':'A','hostname':'trial-303224955-trialrun-303224955-worker-0',
    'release_id':release_id,'run_id':TASK+'_r1_A_wave03','wave_id':'corrector-sim-20260919-A-CUDA-map-graphics-wave03',
    'shard_id':'A-EGL-CUDA-map-static64-device17198167-once',
    'proposal_sha256':sha(STAGE/'proposal/PROPOSAL.json'),
    'bundle_manifest_sha256':sha(STAGE/'BUNDLE_MANIFEST.json'),
    'external_source_manifest_sha256':sha(STAGE/'EXTERNAL_SOURCE_MANIFEST.json'),
    **proposal['device'],**{k:proposal[k] for k in ('resource_caps','max_retries','timeout_seconds','kill_grace_seconds','wave_participants','renderer_route')},
    'proposal_path':str(PUB/'proposal/PROPOSAL.json'),'bundle_manifest_path':str(PUB/'BUNDLE_MANIFEST.json'),
    'command':str(PUB/'commands/run_proposed_graphics_probe.sh'),'working_directory':str(PUB),
    'cuda_environment':proposal['cuda_environment'],'run_extra_cpu_checker':False,
    'timeout_scope':proposal['timeout_scope'],'resource_estimates_not_measured':proposal['resource_estimates_not_measured'],
    'previous_release_reusable':False,'kind':'formal_compute_graphics_only','issued_at_utc':None,'issuer':'analysis_required'}
put('proposal/RELEASE_TEMPLATE.json',template)
put('proposal/CONTROL_REQUIRED.json',{'template_only_not_applied':True,
    'CONTROL_required':{'mode':'preflight','formal_gpu_runs_enabled':True,'stop_requested':False,
        'active_compute_release_id':release_id,'active_compute_release':'releases/'+release_id+'.json',
        'active_compute_task_ids':[TASK],'allowed_task_ids_must_include':[TASK],
        'current_compute_limits':CAPS,'per_task_compute_limits':{TASK:CAPS}},
    'TASK_BOARD_required_entry':{'id':TASK,'owner':'A','revision':1,'status':'released','release':'releases/'+release_id+'.json'},
    'only_participant':'A','all_old_releases_remain_closed':True})
put('proposal/COMMANDS.md',f'''真实命令仅在分析端发布独立新release后可运行一次（本轮未执行）：

```bash
bash {PUB}/commands/run_proposed_graphics_probe.sh {BASE}/releases/{release_id}.json
```

纯CPU授权校验命令（拒绝P00/旧release；真实入口本身已含校验，不需要正式运行前重复执行）：

```bash
bash {PUB}/commands/check_authorization_cpu.sh /absolute/path/to/NEW_RELEASE.json
```

cwd：`{PUB}`。预算及精确CONTROL字段见PROPOSAL、RELEASE_TEMPLATE、CONTROL_REQUIRED。模板status不构成授权。合成测试复现需要CPU_TEST_ARTIFACT_ROOT指向A新目录，运行`{proposal['python']} -B {PUB}/tests/test_cuda_mapping.py`；不导入ctypes/CUDA/EGL，Python audit hook禁止ctypes加载/符号查找。
''')
os.replace(STAGE,PUB)
summary={'published_at_utc':now,'published_root':str(PUB),'proposal_sha256':sha(PUB/'proposal/PROPOSAL.json'),
    'bundle_manifest_sha256':sha(PUB/'BUNDLE_MANIFEST.json'),'bundle_file_count':len(files),
    'external_manifest_sha256':sha(PUB/'EXTERNAL_SOURCE_MANIFEST.json'),'inherited_runtime_file_count':len(ext['files'])-len(added),
    'new_external_identity_entries':len(added),'staged_unique_library_bytes':sum(p.stat().st_size for p in (PUB/'isolation/lib').iterdir() if not p.is_symlink()),
    'real_graphics_CUDA_calls':0,'old_graphics_stack_bytes_reused_unchanged':True}
(WORK/'PUBLICATION.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
