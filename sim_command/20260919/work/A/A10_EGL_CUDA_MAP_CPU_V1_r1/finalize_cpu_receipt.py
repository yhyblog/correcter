"""Publish the CPU task's evidence receipt, leaving compute authority with analysis."""
import datetime
import hashlib
import json
import os
from pathlib import Path

WORK=Path(__file__).resolve().parent
BASE=WORK.parents[2]
TASK='A10_EGL_CUDA_MAP_CPU_V1'
PUB=BASE/'results/A'/TASK
R=BASE/'receipts/A'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(p):return json.loads(p.read_text())


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as s:
        for b in iter(lambda:s.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def ident(p):return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}


def publish(p,obj,replace=False):
    assert replace or not p.exists(),p
    temp=p.with_name(p.name+'.pending')
    with temp.open('x') as s:
        s.write(obj if isinstance(obj,str) else json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
        s.flush();os.fsync(s.fileno())
    os.replace(temp,p)


ack=read(R/f'{TASK}_ACK.json')
proposal=read(PUB/'proposal/PROPOSAL.json')
publication=read(WORK/'PUBLICATION.json')
checks=read(WORK/'CPU_FINAL_CHECKS.json')
control=read(BASE/'CONTROL.json')
assert control['formal_gpu_runs_enabled'] is False and all(x==0 for x in control['current_compute_limits'].values())
assert control['active_egl_mapping_preparation_release']=='releases/P00_EGL_CUDA_MAP_CPU_V1.json'
for item in ack['inputs_checked']:
    assert sha(Path(item['frozen_copy']))==item['sha256']
    # Existing task inputs and accepted earlier artifacts are unchanged at handoff.
    assert sha(Path(item['path']))==item['sha256']
assert checks['synthetic_tests_passed']==31 and checks['actual_graphics_CUDA_calls']==0
counts={key:0 for key in proposal['resource_caps']}
counts.update(gpu_seconds=0,training_updates=0,deletions=0)
inventory={
    'task_id':TASK,'created_at_utc':now,'created_roots':[str(WORK),str(PUB)],
    'receipt_prefix':str(R/TASK),'current_retention':'Retain all until analysis makes an exact keep/delete/defer decision; no deletion release',
    'new_unique_library_bytes':publication['staged_unique_library_bytes'],
    'existing_graphics_libraries_reused_unchanged_count':8,'new_CUDA_driver_library_bytes':29380752,
    'all_synthetic_fixture_directories_retained':True,'actual_deletions':0,
    'note':'CPU evidence, temporary scripts, copied source, publication, tests, and later queue records all retained; no unrelated project touched'}
publish(WORK/'NEW_ARTIFACTS_INVENTORY.json',inventory)
report=f'''| 项目 | 可用 / 缺口 |
|---|---|
| CPU 修订 | complete；本任务实际 CUDA/EGL/dlopen/模型/仿真/训练均0，未执行提案 |
| 物理映射 | 单一路径 EGL_CUDA_DEVICE_NV → 原样 CUDA handle → PCI → 内核 UUID；与固定 NVML 目标核对，唯一匹配才进入context |
| CUDA 库 | 现有535.161.08，SHA `81b63dae639c3b1bc47692a63cab356419deaabda0fe0ce7f538c52351cc6084`；新隔离包绝对路径优先加载，排除550 compat；旧EGL/GLVND 8库内容相同 |
| 可见性 / ABI | 冻结8个完整UUID及PCI_BUS_ID顺序；EGLAttrib 8字节、CUdevice/CUresult 4字节，handle 0合法，不以任何API索引互猜 |
| raw / 错误 | NULL与空bytes分开，EGL属性/返回码/CUDA PCI buffer即时记录；EGL error按调用点预算查询，未查状态不推断 |
| 检查 / 未验证 | 31 CPU fake检查通过，3授权拒绝通过，7 AST/2 shell检查及33 bundle SHA通过；真实cuInit/映射/context/RGB尚未验证 |

新graphics任务建议ID：`{proposal['task_id']}`。当前只有本CPU任务获准；下列预算和命令均为待新release提案。

| 下一次 graphics 显式调用 | 上限 |
|---|---:|
| attempt / EGL枚举 / cuInit（各） | 1 |
| 扩展字符串 / CUDA属性 / CUDA PCI（各） | 8 |
| eglGetProcAddress / 核心EGL符号 / CUDA符号 | 5 / 11 / 2 |
| eglGetError（含初始基线和清理） / 显式驱动库加载 | 35 / 2 |
| display初始化 / EGLcontext / 静态model+data / mj_forward / render+RGB（各） | 1 |
| EGL字符串 / GL字符串 / makeCurrent | 2 / 3 / 2 |
| context销毁 / terminate / releaseThread / MjrContext free（各） | 1 |
| CUDA context/kernel、DRM/binary/UUID额外查询、VLA/MetaWorld/reset/物理推进/训练/重试 | 0 |

`cuInit`单列计费；driver内部资源未知，不能由显式CUDA context调用0推断内部消耗0。VRAM1GiB/RAM2GiB/output32MiB仍是估计。子进程120s TERM+10s KILL覆盖hash/load/cuInit/映射/单帧/cleanup，前后准备、全A holder预约与恢复另计；A全8卡停到进程族退出含失败再恢复，B不参与。

真实命令（本轮未执行）：`bash {PUB}/commands/run_proposed_graphics_probe.sh {BASE}/releases/P10_A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1.json`。cwd=`{PUB}`。

纯CPU授权命令与精确CONTROL/TASK_BOARD字段见 [COMMANDS]({PUB/'proposal/COMMANDS.md'})、[CONTROL_REQUIRED]({PUB/'proposal/CONTROL_REQUIRED.json'})；分析端生成独立新release后才可运行，不复用关闭的v1。所有候选的EGL属性/PCI/UUID必须可信，任何失败或重复映射即停，不尝试其他context、库、renderer或字节序。

设计和规范依据见 [MAPPING_DESIGN]({PUB/'MAPPING_DESIGN.md'})；ABI、库来源/顺序和完整caps均已冻结。[CPU证据]({WORK/'CPU_FINAL_CHECKS.json'})覆盖本次改动，未重跑旧CPU全套。原bundle、失败记录、native v4/v5均保持；本轮不要求平台补挂载或重建容器。

[PROPOSAL]({PUB/'proposal/PROPOSAL.json'}) SHA `{publication['proposal_sha256']}`；[BUNDLE]({PUB/'BUNDLE_MANIFEST.json'}) SHA `{publication['bundle_manifest_sha256']}`。当前guard自报8 holder，CPU任务未停卡；新增产物全部保留，无删除。
'''
publish(R/f'{TASK}_REPORT.md',report)
publish(R/f'{TASK}_HEARTBEAT.json',{'task_id':TASK,'status':'CPU_preparation_complete',
    'updated_at_utc':now,'synthetic_tests_passed':31,'denial_checks_passed':3,
    'actual_resource_counts':counts,'published_root':str(PUB),
    'future_graphics_release_required':True},replace=True)
files={p for root in (WORK,PUB) for p in root.rglob('*') if p.is_file()}
files.update(R/f'{TASK}_{name}' for name in ('ACK.json','REPORT.md','HEARTBEAT.json'))
manifest={'task_id':TASK,'created_at_utc':now,'files':[ident(p) for p in sorted(files)],
    'scope':'New work evidence, code/scripts, synthetic fixtures, published bundle/proposal/templates, ACK/report/final heartbeat; manifest itself, final RESULT and later queue files excluded to avoid cycles',
    'file_count':len(files),'symlink_note':'SHA follows contained library alias; logical file sizes are not deduplicated disk usage'}
publish(WORK/'FINAL_ARTIFACT_MANIFEST.json',manifest)
artifacts={
    'short_report':R/f'{TASK}_REPORT.md','proposal':PUB/'proposal/PROPOSAL.json',
    'release_template':PUB/'proposal/RELEASE_TEMPLATE.json','required_CONTROL':PUB/'proposal/CONTROL_REQUIRED.json',
    'commands':PUB/'proposal/COMMANDS.md','bundle_manifest':PUB/'BUNDLE_MANIFEST.json',
    'external_manifest':PUB/'EXTERNAL_SOURCE_MANIFEST.json','CUDA_library_identity':PUB/'CUDA_DRIVER_IDENTITY.json',
    'ABI_contract':PUB/'ABI_CONTRACT.json','mapping_design':PUB/'MAPPING_DESIGN.md',
    'caps_derivation':PUB/'CAPS_AND_CONTROL.md','CPU_checks':WORK/'CPU_FINAL_CHECKS.json',
    'synthetic_test_log':WORK/'CPU_SYNTHETIC_r1.log','complete_manifest':WORK/'FINAL_ARTIFACT_MANIFEST.json',
    'new_artifacts_inventory':WORK/'NEW_ARTIFACTS_INVENTORY.json',
}
result={
    'campaign_id':ack['campaign_id'],'task_id':TASK,'revision':1,'role':'A','hostname':ack['hostname'],
    'session_id':ack['executor_session_id'],'status':'complete','started_at_utc':ack['started_at_utc'],'finished_at_utc':now,
    'release_id':ack['release_id'],'current_CONTROL_revision':control['revision'],
    'input_identity':{
        'protocol':[ident(WORK/'inputs'/rel) for rel in ['CONTROL.json','TASK_BOARD.json','tasks/'+TASK+'.md','releases/P00_EGL_CUDA_MAP_CPU_V1.json','contracts/REPORT_CONTRACT.md']],
        'code':{'source_graphics_bundle':ident(WORK/'inputs/results/A/A10_EGL_CPU_REPAIR_V1/BUNDLE_MANIFEST.json'),
                'published_new_bundle':ident(PUB/'BUNDLE_MANIFEST.json'),
                'added_CUDA_driver':read(PUB/'CUDA_DRIVER_IDENTITY.json')['source']},
        'config':ident(PUB/'proposal/PROPOSAL.json'),
        'data':{'path':None,'sha256':None,'reason':'No dataset; CPU fixtures only. Future static scene kept unchanged and hashed in bundle.'},
        'model':{'path':None,'sha256':None,'reason':'No VLA weights loaded or rehashed; zero model operations'},
        'accepted_previous_failure':ident(WORK/'inputs/receipts/A/A10_EGL_GRAPHICS_PROBE_V1_RESULT.json'),
    },
    'artifacts':{k:ident(p) for k,p in artifacts.items()},'resource_counts':counts,
    'resource_scope':'Actual CPU task operations only; fake synthetic journal entries are test data, not GPU calls. Existing user-required occupancy holders are outside task compute accounting.',
    'failures_and_retries':[],
    'expected_denials':{'count':3,'expected_exit_code':2,'cases':['P00 preparation release','closed prior graphics task','new unreleased template'],'unexpected_failures':0},
    'findings':[
        'Implemented only EGL_NV_device_cuda attribute -> unchanged CUDA handle -> PCI -> frozen kernel/NVML UUID target; unique mapping before display.',
        '535.161.08 driver library source, SHA, ABI, dependencies and isolated loading order frozen; ambient550 compat excluded; original535 EGL/GLVND bytes reused.',
        'Frozen all8 CUDA-visible physical UUIDs and PCI_BUS_ID ordering; no CUDA/EGL/NVML ordinal equality assumed, no mask retries.',
        'Raw NULL/empty, attribute output/sentinel, CUDA return code and PCI buffer preserved; budgeted immediate EGL error reads add no unqueried error inference.',
        '31 new CPU synthetic checks passed including handle0/overflow, permutation, identity conflicts, failure and caps; ctypes operations forbidden by test audit hook.',
        'P00, prior graphics release and unreleased template all denied before runtime work;33 bundle files SHA verified; changed source parsed and command syntax checked.',
        'New proposal lists cuInit1, attribute8, PCI8, eglGetProcAddress5, error35, symbol lookups13 and driver loads2 in addition to original single-frame path.',
        'All real library/EGL/CUDA/model/reset/physics/training operations0; old release not reused and new graphics/native probe not run.',
        'Original bundle/failure receipts remain intact, all new evidence retained, no deletion/shared-driver/container changes; guard snapshot still reports8holders.',
    ],
    'blockers':[],
    'remaining_unvalidated':['Actual CUDA initialization with the frozen535 library','Actual EGL-CUDA handle/PCI/UUID uniqueness under frozen visibility','One-context NVIDIA rendering/readback and cleanup','VLA/MetaWorld/native chain, which remains separately unauthorized'],
    'next_task_proposal':{'task_id':proposal['task_id'],'owner':'analysis','status':'proposed_not_released',
        'release_template_path':str(PUB/'proposal/RELEASE_TEMPLATE.json'),'required_control_path':str(PUB/'proposal/CONTROL_REQUIRED.json'),
        'real_command':['bash',str(PUB/'commands/run_proposed_graphics_probe.sh'),str(BASE/'releases/P10_A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1.json')],
        'cwd':str(PUB),'resource_caps':proposal['resource_caps'],'max_retries':0,'automatically_started':False,
        'success_scope':'single static graphics frame only; never authorizes native v5'},
    'all_new_artifacts_retained':True,'current_deletion_authority':None,
}
publish(R/f'{TASK}_RESULT.json',result)
print(json.dumps({'RESULT':ident(R/f'{TASK}_RESULT.json'),'report_lines':len(report.splitlines()),
    'artifact_count':len(artifacts),'complete_manifest_file_count':len(files),
    'proposal_sha256':publication['proposal_sha256'],'bundle_sha256':publication['bundle_manifest_sha256']},ensure_ascii=False))
