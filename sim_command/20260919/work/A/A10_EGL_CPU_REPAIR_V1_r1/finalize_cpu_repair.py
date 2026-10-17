from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,os,socket

B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W=B/'work/A/A10_EGL_CPU_REPAIR_V1_r1';R=B/'results/A/A10_EGL_CPU_REPAIR_V1'
task='A10_EGL_CPU_REPAIR_V1'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return h.hexdigest()
def atomic(p,d):
 q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');os.replace(q,p)
def identity(p):return {'path':str(p),'sha256':sha(p)}
def save_new(p,d):
 assert not p.exists(),p
 atomic(p,d)

ack=json.loads((B/'receipts/A'/f'{task}_ACK.json').read_text())
proposal=json.loads((R/'proposal/PROPOSAL.json').read_text())
validation=json.loads((W/'evidence/PUBLISHED_CPU_VALIDATION.json').read_text())
assert validation['status']=='passed'
tests=json.loads((W/'evidence/CPU_TESTS_r1.json').read_text());assert tests['returncode']==0
control=json.loads((B/'CONTROL.json').read_text());assert not control['formal_gpu_runs_enabled']
save_new(W/'OBSERVATION_COUNTER_EXAMPLES_V5.json',{'synthetic':True,'examples':[
 {'case':'native_reset_return_then_EGL_render_failure','native_resets_returned_total':52,'diagnostic_native_resets_returned':1,'diagnostic_observations_returned':0,'usable_observation_artifacts':0},
 {'case':'full_observation_return_then_validation_or_save_failure','native_resets_returned_total':52,'diagnostic_native_resets_returned':1,'diagnostic_observations_returned':1,'usable_observation_artifacts':0},
 {'case':'valid_observation_saved','native_resets_returned_total':52,'diagnostic_native_resets_returned':1,'diagnostic_observations_returned':1,'usable_observation_artifacts':1}],
 'old_failure_receipt_modified':False,'counter_units':'Diagnostic native reset count is1; total native resets include51 initialization resets and are a separate dimension'})
report=f'''# A10 EGL CPU 修复准备 V1

| 项目 | 交付 / 缺口 |
|---|---|
| 实际加载路径 | conda有GLVND1.7.0的libEGL；Python/_ctypes的RPATH可找到私有库。系统ldconfig缺项不能推出没有EGL |
| 根因证据 | 实际查找目录缺NVIDIA EGL vendor/core/glsi和vendor JSON；启动能力为compute,utility。此证据支持vendor栈缺失，未执行EGL，尚未排除设备/扩展等第二问题 |
| 隔离修复 | 复制4个既有GLVND库；从NVIDIA官方下载3个535.161.08拆分包共21,961,782字节，仓库SHA全部匹配；4个NVIDIA库加4个GLVND库共88,876,552字节。无系统安装 |
| 静态依赖 | 18个ELF对象的DT_NEEDED候选均可解析；额外补齐动态引用的同版本shader库。未使用dlopen/ldd验证，不把静态通过写成运行通过 |
| 设备挂载 | 沙箱外nvidia0/ctl/uvm存在；dri/modeset不存在。sysfs card1/renderD128均指向目标PCI0f:00.0。当前不能断言这些缺项对headless EGL必然致命 |
| CPU验证 | 16项定向合成测试、9个相关Python AST、2条shell语法、3次纯CPU拒绝路径、438项发布文件SHA通过 |
| 当前资源 | 模型GPU、graphics、EGL枚举/初始化/context、渲染、仿真/reset、训练、删除全部0；只读guard状态显示8holder存活 |

发布入口：`{R}`。`proposal/PROPOSAL.json` SHA=`{sha(R/'proposal/PROPOSAL.json')}`；`BUNDLE_MANIFEST.json` SHA=`{sha(R/'BUNDLE_MANIFEST.json')}`。共享系统/conda及旧v1/v3/v4/失败回执均未改。

隔离vendor JSON固定指向本任务NVIDIA535.161.08库，子进程使用明确库路径、不继承CUDA550compat优先项；保持NVIDIA/EGL，无软件renderer回退。实际安装的MuJoCo3.6.0、PyOpenGL3.1.10及绑定文件共3006项外部源身份冻结；没有导入这些图形包作探针。

原MuJoCo在未设置MUJOCO_EGL_DEVICE_ID时可遍历EGL设备并尝试初始化；该ID也不等于CUDA序号。新独立探针只枚举一次，借EGL DRM路径→sysfs PCI→内核GPU UUID选择唯一目标GPU-17198167…/PCI0000:0f:00.0。映射缺失/歧义即失败，不逐卡试context。最多16槽、48次设备字符串查询，精确计数上限见proposal。

未来探针限1进程、1attempt、1display初始化、1EGL context、1个64×64静态MuJoCo场景、1次显式mj_forward（data.time不推进）、1render/1RGB readback；MetaWorld/策略模型/采样/reset/物理步/训练全0，重试0。成功只证明这次EGL RGB读回，不证明MetaWorld完整链路或P/V。

预估显存1GiB、进程RAM2GiB、运行新输出32MiB，均未实测。120秒TERM+10秒KILL仅限graphics子进程，含其hash/import/初始化/清理；前置检查、全A预约与holder释放、恢复观察另计，端到端严格上界null。复用已有全A holder生命周期，B不参与。

纯CPU授权检查：`{R}/commands/check_authorization_cpu.sh NEW_RELEASE`。本次对两份P00及已关闭旧P10均按预期exit2，未用实际启动脚本作dry-run。未来唯一启动命令：`{R}/commands/run_proposed_graphics_probe.sh NEW_RELEASE`，本次未执行；分析还须独立发布graphics任务/CONTROL预算及RELEASE_TEMPLATE实值。

新`native_code_snapshot_v5`仅改原生预检计数：`diagnostic_native_resets_returned`、`diagnostic_observations_returned`、`usable_observation_artifacts`分开，观测返回后及有效文件写完后分别持久化标记。旧失败对应1/0/0，而总native reset是52；三个合成例子位于work同名JSON。v5只是代码修正，没有新的native预检授权。

平台当前无已证实必须操作：可先审核本隔离依赖与一次有限探针提案；若探针暴露设备/接口缺项，再按`work/A/A10_EGL_CPU_REPAIR_V1_r1/PLATFORM_FALLBACK.md`配置启动时graphics暴露。仅在现容器export能力变量不会补齐启动挂载。依据：[NVIDIA能力文档](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)、[官方拆分包仓库](https://developer.download.nvidia.com/compute/cuda/repos/debian11/x86_64/)、[EGL DRM映射规范](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_device_drm.txt)。

工程检查失败记录：初次unittest命令遗漏CPU_TEST_ARTIFACT_ROOT，16项均在setUp报错、用例未执行；补齐命令环境后在实际Python3.12环境16项全过，未扩展旧验收。官方535.161.08 README网页不可访问，改以实际固定库、官方包索引及源码取证。所有下载、解包、测试临时证据保留并入manifest，删除0。
'''
report_path=B/'receipts/A'/f'{task}_REPORT.md';assert not report_path.exists();q=report_path.with_name(report_path.name+'.tmp');q.write_text(report);os.replace(q,report_path)
files=[]
for scope in [W,R]:
 for p in sorted(scope.rglob('*')):
  if p.is_file() and not p.is_symlink():files.append({'path':str(p),'realpath':str(p.resolve()),'size_bytes':p.stat().st_size,'sha256':sha(p)})
manifest_path=W/'FINAL_ARTIFACT_MANIFEST.json';save_new(manifest_path,{'files':files,'all_retained':True,'deletion_release':None,'scope':'Only this new CPU repair task; no repeated historical retention inventory'})
save_new(W/'NEW_ARTIFACTS_INVENTORY.json',{'role':'A','decision_owner':'analysis','current_action':'retain_pending_analysis_decision','deletions':0,'roots':[
 {'path':str(scope),'realpath':str(scope.resolve()),'logical_file_bytes':sum(x['size_bytes'] for x in files if Path(x['path']).is_relative_to(scope)),
  'purpose':'CPU repair source/provenance/synthetic evidence' if scope==W else 'Frozen proposed graphics bundle and native receipt code correction','needed_for':'A10_EGL_CPU_REPAIR_V1 audit and proposed next graphics probe'} for scope in [W,R]],
 'manifest':identity(manifest_path),'size_note':'Logical regular-file bytes in manifest; excludes this inventory/manifest itself; not physical freed-space estimate'})
resource=dict.fromkeys(['model_gpu_inference_calls','model_initializations','graphics_probe_attempts','egl_device_enumerations','egl_initialize_calls','graphics_context_creations','render_calls','rgb_readback_calls','simulator_attempts','environment_instances','environment_reset_calls','explicit_mj_forward_calls','physics_steps','completed_rollouts','vla_sampling_calls','flow_forward_calls','optimizer_updates','gpu_seconds','deleted_paths','deleted_bytes'],0)
now=datetime.now(timezone.utc).isoformat()
result={'campaign_id':'corrector-sim-20260919','task_id':task,'revision':1,'role':'A','hostname':socket.gethostname(),'session_id':ack['executor_session_id'],'status':'complete','started_at_utc':ack['started_at_utc'],'finished_at_utc':now,
 'input_identity':{'protocol':ack['inputs_checked'],'code':identity(R/'BUNDLE_MANIFEST.json'),'config':identity(R/'proposal/PROPOSAL.json'),'data':identity(R/'scene.xml'),'model':{'path':None,'sha256':None,'reason':'No policy model used; static graphics preparation only'},'external_source':identity(R/'EXTERNAL_SOURCE_MANIFEST.json')},
 'artifacts':[identity(p) for p in [report_path,manifest_path,W/'NEW_ARTIFACTS_INVENTORY.json',W/'PLATFORM_FALLBACK.md',W/'HOST_DEVICE_VISIBILITY_ESCALATED.json',W/'evidence/PUBLISHED_CPU_VALIDATION.json',W/'evidence/CPU_TESTS_r1.json',R/'proposal/RELEASE_TEMPLATE.json',R/'native_code_snapshot_v5/CODE_MANIFEST.json']],
 'resource_counts':resource,'failures_and_retries':[{'kind':'CPU_test_harness_environment_missing','exit_code':1,'detail':'16 setup errors before case bodies due missing CPU_TEST_ARTIFACT_ROOT; corrected invocation only, actual Python3.12 run16passed','scientific_retries':0},{'kind':'reference_web_read_unavailable','detail':'Exact535.161.08 README unavailable via web tool; used installed source/ELF and NVIDIA official split-package index'},{'kind':'expected_CPU_authorization_denials','exit_code':2,'count':3,'graphics_started':False}],
 'findings':['Conda libEGL/GLVND exists; system ldconfig absence is not complete loader evidence',
 'NVIDIA vendor/core/config absent in actual loader locations; compute,utility capability is supporting context, not proof of sole root cause',
 'Prepared matched535.161.08 isolated EGL/core/glsi/shader stack from3 NVIDIA official packages,21,961,782download bytes; no shared installation',
 '18ELF objects statically resolved DT_NEEDED, graphics runtime remains untested',
 'Escalated read-only device check separates sandbox-hidden NVIDIA nodes from genuinely absent DRM/modeset paths; target sysfs PCI/kernel UUID mapping recorded',
 'Proposed1graphics attempt/1enumeration/1display/1context/1static scene/1explicit mj_forward/1RGB readback; zero policy/MetaWorld/reset/physics/training and0retries',
 'Physical EGL identity required before display init; no CUDA ordinal assumption or trial of other GPUs; independent A-only holder lifecycle',
 'Native v5 splits1diagnostic native reset return from0full observation and0usable artifact in EGL failure case; old records unchanged',
 '16targeted CPU cases,9AST files,2shells,3CPU denial paths,438bundle file SHAs passed; no graphics imports executed for diagnosis',
 'R2 specialized ACK/REPORT/RESULT were requeued separately; this is new released CPU repair work, no old inventory rerun or deletion'],
 'blockers':[],'remaining_unvalidated':['EGL runtime/device-extension availability and actual readback','whether absent DRM/modeset nodes affect this headless path','MetaWorld native render chain and VLA/P/V unaffected and not revalidated'],
 'next_task_proposal':'Analysis reviews frozen isolation+graphics-only finite proposal. Execute only after a new exact graphics release and CONTROL/TASK_BOARD grant; current CPU preparation is not authorization.',
 'platform_action_required_now':False,'platform_action_contingency':str(W/'PLATFORM_FALLBACK.md'),
 'current_control_revision':control['revision'],'all_new_artifacts_retained':True,'existing_occupancy_status':str(W/'DEVICE_MOUNT_AND_GUARD_SNAPSHOT.json')}
result_path=B/'receipts/A'/f'{task}_RESULT.json';save_new(result_path,result)
atomic(B/'receipts/A'/f'{task}_HEARTBEAT.json',{'task_id':task,'status':'complete_CPU_only','updated_at_utc':now,'result_path':str(result_path),'resource_counts':resource})
print(json.dumps({'report':str(report_path),'report_lines':len(report.splitlines()),'result':str(result_path),'result_sha256':sha(result_path),'artifact_files':len(files),'resource_counts':resource},ensure_ascii=False,indent=2))
