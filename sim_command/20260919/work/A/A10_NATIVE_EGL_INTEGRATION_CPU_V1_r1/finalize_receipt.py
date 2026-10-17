from pathlib import Path
import json,hashlib,datetime,os
b=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');task='A10_NATIVE_EGL_INTEGRATION_CPU_V1'
p=b/'results/A'/task;w=b/'work/A'/f'{task}_r1';receipts=b/'receipts/A'
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def ref(f):f=Path(f);return dict(path=str(f),sha256=sha(f),size_bytes=f.stat().st_size)
def publish(f,value,text=False):
 f=Path(f);tmp=f.with_name(f.name+'.publish.tmp')
 tmp.write_text(value if text else json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,f)
ack=json.loads((receipts/f'{task}_ACK.json').read_text());proposal=json.loads((p/'proposal/PROPOSAL.json').read_text())
report='''| 项目 | 结果 / 缺口 |
|---|---|
| 本任务 | CPU准备完成；新 native V2 未授权、未执行 |
| 私有 EGL 集成 | 已冻结535库、8卡可见性、CUDA handle→PCI/内核UUID映射；GLContext接收实际handle；Torch文本UUID独立核对 |
| 原生观测链 | 当前 Gymnasium OffScreenViewer；1个EGL context、1个MjrContext复用，初态/步后各1张corner2 480×480 RGB |
| 有限提案 | 1诊断attempt，5 native/50 flow，1控制步/13物理子步；0 rollout/monitor/反向/更新/重试 |
| 初始化报价 | 不变：2原生环境+1wrapper，52reset/104reset_model/5200do_simulation/26000初始化子步 |
| CPU验证 | 18项定向fake通过（22次执行，含改动相关复查）；3授权拒绝；11改动源码AST、2shell语法通过 |
| 实际计算/删除 | GPU/CUDA/EGL/NVML/dlopen/模型/环境/reset/物理推进/训练/删除均0；holder未查询、未停止 |
| 待验证 | 真实模型+535库兼容、两张原生RGB和5次采样尚未实测，须分析另发native V2 release |

新包：`results/A/A10_NATIVE_EGL_INTEGRATION_CPU_V1/CPU_READY.json`。419文件CODE_MANIFEST、22引用INTEGRATION_MANIFEST及3133项继承/定向补充的外部源码身份已发布；本轮未重扫库存、未重hash大权重、未改旧v4/v5或共享包。

完整调用依据见 `STATIC_CALL_AUDIT.json`；相对v5的主要变化是私有映射/上下文接入、策略UUID绑定、前后观测分列计数及RGB产物、release独占claim、进程组退出后才释放全8卡预约。`diagnostic_native_resets_returned` 与完整RGB返回、可用NPZ分开；后观测另列。失败保留已入账/未完成事件、阶段与缺产物原因，cleanup不重试。

唯一真实命令（仅提案）：`commands/run_proposed_native_preflight.sh NEW_RELEASE_JSON`。纯CPU入口：`commands/check_authorization_cpu.sh NEW_RELEASE_JSON`。真实入口自带完整SHA/设备检查，不额外先跑checker；所有旧compute release仍不可用。

显式graphics成功目标108个操作：1枚举/1显式cuInit，扩展/属性/PCI各≤8，1context、2render/readPixels；辅助查询及清理精确caps见 `proposal/PROPOSAL.json` / `CAPS_AND_CONTROL.md`。Torch/MuJoCo/驱动内部API不逐项计量，不将显式cuInit上限解释成全进程调用总数。readPixels内部也填depth，保存的NPZ/PPM为同一次RGB观测，未来仍需视觉核对原生场景。

1800+30秒只包诊断子进程；前置SHA、预约、进程组清理、释放与恢复另计。预估41GiB VRAM/64GiB RAM/2GiB输出，非测量。当前CONTROL15/TASK_BOARD22计算全0；无技术阻塞，不申请复用旧额度。所有新增代码、fake产物和报告保留。
'''
publish(receipts/f'{task}_REPORT.md',report,text=True)
# Finish heartbeat before the final evidence manifest is sealed.
finished=datetime.datetime.now(datetime.timezone.utc).isoformat()
for f in [w/'HEARTBEAT.json',receipts/f'{task}_HEARTBEAT.json']:
 heartbeat=json.loads(f.read_text());heartbeat.update(status='complete',stage='CPU_ready_handoff',finished_at_utc=finished,updated_at_utc=finished);publish(f,heartbeat)
files=sorted([f for directory in [p,w] for f in directory.rglob('*') if f.is_file() and f.name not in ['EVIDENCE_MANIFEST.json','RETENTION_INVENTORY.json']])
records=[ref(f) for f in files]
retention=dict(task_id=task,decision='retain_all_task_evidence',delete_authorization=False,total_files=len(records),total_bytes=sum(r['size_bytes'] for r in records),files=[dict(path=r['path'],realpath=str(Path(r['path']).resolve()),size_bytes=r['size_bytes'],project='Corrector',reason='Current authorized CPU integration/proposal/fake evidence') for r in records])
publish(w/'RETENTION_INVENTORY.json',retention)
records.append(ref(w/'RETENTION_INVENTORY.json'))
records += [ref(receipts/f'{task}_{suffix}') for suffix in ['ACK.json','REPORT.md','HEARTBEAT.json']]
publish(w/'EVIDENCE_MANIFEST.json',dict(task_id=task,files=records,exclusions=['This self manifest','final RESULT','post-RESULT read-only audit and queue delivery receipt'],scope='Only current new task outputs; all evidence retained'))
artifact_paths=[receipts/f'{task}_REPORT.md',p/'CPU_READY.json',p/'proposal/PROPOSAL.json',p/'proposal/RELEASE_TEMPLATE.json',p/'proposal/CONTROL_REQUIRED.json',p/'code/CODE_MANIFEST.json',p/'INTEGRATION_MANIFEST.json',p/'EXTERNAL_SOURCE_MANIFEST.json',p/'config/INTEGRATION.json',p/'STATIC_CALL_AUDIT.json',p/'INTEGRATION_NOTES.md',p/'CAPS_AND_CONTROL.md',p/'REUSED_ASSETS.json',w/'FINAL_CPU_AUDIT.json',w/'CPU_STATIC_CHECKS.json',w/'CPU_AUTHORIZATION_DENIALS.json',w/'CPU_FAKE_CHECKS_run1.log',w/'CPU_NATIVE_CHAIN_FAKE_run1.log',w/'CPU_REVIEW_FIX_CHECKS_run1.log',w/'EVIDENCE_MANIFEST.json',w/'RETENTION_INVENTORY.json',p/'commands/run_proposed_native_preflight.sh',p/'commands/check_authorization_cpu.sh']
result=dict(campaign_id='corrector-sim-20260919',task_id=task,revision=1,task_revision=1,role='A',node_role='A',
 hostname=ack['hostname'],session_id=ack['executor_session_id'],status='complete',
 started_at_utc=ack['started_at_utc'],finished_at_utc=finished,
 input_identity=dict(protocol=ref(b/'tasks'/f'{task}.md'),CPU_release=ref(b/'releases/P00_NATIVE_EGL_INTEGRATION_CPU_V1.json'),
 accepted_graphics=ref(b/'manifests/A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_FINAL_ACCEPTANCE.json'),
 code=ref(p/'code/CODE_MANIFEST.json'),config=ref(p/'config/INTEGRATION.json'),
 data=ref(p/'proposal/source_manifest.json'),
 model=dict(path=str(Path(proposal['checkpoint'])/'model.safetensors'),sha256=proposal['model_sha256'],
 verification_scope='Inherited previously verified v4/native input identity; current CPU task does not hash or load large weights; new real entry must rehash'),
 original_v5=ref(b/'results/A/A10_EGL_CPU_REPAIR_V1/native_code_snapshot_v5/CODE_MANIFEST.json'),
 inherited_library_and_external_identity_scope='Accepted graphics/native manifests reused; only targeted integration sources refreshed; no full old runtime rescan'),
 artifacts=[ref(f) for f in artifact_paths],
 resource_counts=dict(simulator_attempts=0,completed_rollouts=0,vla_sampling_calls=0,flow_forward_calls=0,optimizer_updates=0,gpu_seconds=0,
 EGL_CUDA_NVML_calls=0,driver_library_dlopen=0,model_initializations=0,environment_instances=0,environment_reset_calls=0,physics_steps=0,
 GPU_training=0,deletions=0,real_launcher_invocations=0,large_weight_hash_passes=0,
 task_output_bytes_before_final_receipt=retention['total_bytes'],fake_tests_distinct=18,fake_test_executions=22,
 successful_authorization_denial_checks=3,changed_source_AST_checks=11,shell_syntax_checks=2),
 failures_and_retries=[],
 expected_denials=dict(count=3,status='passed',no_compute_or_weight_hash_started=True),
 occupancy=dict(action='none',holders='Existing occupancy left running; no status/NVML query or holder stop/start in CPU task',restoration='not applicable; no formal wave entered'),
 findings=[
 'Private mapping routes exact selected EGL handle into actual Gymnasium GLContext without shared package mutation or ordinal guessing.',
 'Policy logical CUDA device comes from frozen UUID visibility and one future Torch textual UUID cross-check; full eight-device mapping required before policy binding.',
 'Native initial and post-control observations use one OffScreenViewer/EGL/MjrContext and two480x480corner2 renders/readbacks, not a repeated static sphere.',
 'Initialization quote unchanged:2native+1wrapper,52reset,104reset_model,5200do_simulation/26000init substeps;one policy step13substeps.',
 'H/C/raw actions/dual ledgers/interface_v1 unchanged; proposal retains5native/50flow and0fullrollout/backward/monitor/update/retry.',
 'Reset returned, initial RGB returned, post-control RGB returned and two usable NPZ artifacts are distinct; PPM views add no render; missing stages/artifacts recorded.',
 '18targeted CPU fake cases passed; includes actual installed Gymnasium Python classes with fake bindings; runtime driver/heavy imports blocked during tests.',
 'Exclusive release claim precedes full hash/device checks; all8holder lifecycle retained through isolated process-group exit and failure cleanup.',
 'Explicit adapter/API caps frozen; framework/driver internal API counts remain unmetered rather than fabricated.',
 'No GPU/CUDA/EGL/NVML/reset/model/training/deletion this task; proposal/template not authorization; old releases remain closed.'
 ],blockers=[],
 limitations=['Real native observations/model compatibility not yet tested','Persistent holder occupancy deliberately not re-probed during CPU-only task','Inherited large model/runtime identities will receive full verification only at new released real entry'],
 next_task_proposal=dict(task_id='A10_PREFLIGHT_NATIVE_V2',status='proposed_not_released',proposal=ref(p/'proposal/PROPOSAL.json'),release_template=ref(p/'proposal/RELEASE_TEMPLATE.json'),control_required=ref(p/'proposal/CONTROL_REQUIRED.json'),real_command=proposal['real_command'],CPU_authorization_command=proposal['cpu_authorization_command'],native_sampling_calls=5,flow_forward_calls=50,diagnostic_attempts=1,policy_steps=1,raw_native_resets=52,init_physics_substeps=26000,policy_physics_substeps=13,contexts=1,frames=2,frame_size=[480,480],retries=0),
 final_manifest_files=len(records),all_new_evidence_retained=True)
# Final RESULT is the last substantive task publication.
out=receipts/f'{task}_RESULT.json'
assert not out.exists()
publish(out,result)
print(json.dumps(dict(RESULT=ref(out),REPORT=ref(receipts/f'{task}_REPORT.md'),artifacts=len(result['artifacts']),manifest_files=len(records),proposal_sha256=sha(p/'proposal/PROPOSAL.json')),ensure_ascii=False))
