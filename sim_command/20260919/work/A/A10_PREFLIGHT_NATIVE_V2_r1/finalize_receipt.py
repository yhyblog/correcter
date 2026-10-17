from pathlib import Path
import datetime,hashlib,json,os
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');TASK='A10_PREFLIGHT_NATIVE_V2';W=B/'work/A'/f'{TASK}_r1'
RUN=B/'results/A/P10_launcher_runs/A10_PREFLIGHT_NATIVE_V2_r1_A_wave04';D=Path(json.loads((RUN/'diagnostic_link.json').read_text())['path']);P=B/'results/A/A10_NATIVE_EGL_INTEGRATION_CPU_V1'
RECEIPTS=B/'receipts/A';R=json.loads((W/'inputs/releases/P10_A_NATIVE_PREFLIGHT_V2.json').read_text());ACK=json.loads((RECEIPTS/f'{TASK}_ACK.json').read_text());AUDIT=json.loads((W/'FINAL_AUDIT.json').read_text())
PROPOSAL=json.loads((P/'proposal/PROPOSAL.json').read_text());CLAIM=B/'results/A/P10_native_release_claims/P10_A_NATIVE_PREFLIGHT_V2.json';CACHE=B/'work/A/P10_runtime_cache'/R['run_id']
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def ref(f):f=Path(f);return dict(path=str(f),sha256=sha(f),size_bytes=f.stat().st_size)
def publish(f,value,text=False):
 f=Path(f);tmp=f.with_name(f.name+'.publish.tmp');tmp.write_text(value if text else json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,f)
finished=datetime.datetime.now(datetime.timezone.utc).isoformat()
report='''| 项目 | 实际结果 |
|---|---|
| 本次执行 | 冻结sh执行1次，退出1；技术失败，release已消费，重试0 |
| 失败阶段 | heavy_imports_and_policy_device_binding；`Torch UUID property is not the frozen string ABI` |
| 八设备映射 | 完成；固定PCI 0000:0f:00.0 / GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe唯一匹配 |
| policy UUID | properties调用返回，保存的字符串表示与目标一致；原对象未通过str类型守门，不能记为绑定校验通过；确切Python类型未记录 |
| 模型/诊断/native/flow/控制 | 全0；模型未初始化、诊断attempt未进入，非任务成功率样本 |
| 初始化 | 环境/wrapper/reset/reset_model/初始化及策略物理子步均0 |
| graphics显式操作 | 71 entered /71 returned /0 failed /0 incomplete；语义守门失败独立报告 |
| context/RGB/产物 | EGL/MjrContext、render/readPixels、完整观测/可用NPZ均0；5H/raw50/transition/前后RGB未到达 |
| 清理与恢复 | releaseThread1，cleanup errors=[]；整个进程组退出，8holder恢复；不换卡/库/renderer/seed、不删除 |

实际主要graphics计数：显式cuInit1、枚举1、设备扩展/属性/PCI各8，driver load2、CUDA符号2、EGL核心符号11、getProc4、EGL error23（全EGL_SUCCESS），策略set_device/properties各1、releaseThread1。剩余预算全部作废。全部精确计数见 `ACTUAL_COUNTS.json` / `GRAPHICS_COUNTS.csv`；三套账本已独立重算与LAUNCH_RESULT一致。

`policy_device.json` 的 `torch_uuid_raw` 是冻结入口保存的 `str(properties.uuid)`，不是原对象的类型证据。失败证明原值不是str；不能据其显示值猜测确切类型。映射后535库身份有证据，Torch绑定后的loader快照因守门失败未到达；没有补做GPU/UUID探测。

子进程21.551秒；前置14.145秒、预约/holder释放48.646秒、恢复观察10.006秒；launcher端到端94.378秒，observer全程96.119秒。CPU观测单进程RSS/HWM最大441.492MiB；实际GPU秒和GPU峰值显存未知，保留null。两个正式入口内权重SHA流程已通过，未额外跑CPU checker或第三遍hash。

`process_family_cleanup.json` 确认独立进程组234766无存活成员，无需补发信号；命令退出后的进程检查为空。guard记录八次yield，首显式cuInit为19:39:11.059 UTC；八holder均在进程组退出后于19:39:20恢复（manager234886–234893，guard27508）。guard状态在串行停holder期间可能滞后，不当作逐采样NVML实测。

回执证据：本任务 `RESULT.json`、`LAUNCH_RESULT.json`、`FINAL_AUDIT.json`、资源/初始化/graphics账本、mapping/loader/policy UUID及缺产物表均保留。无RGB可做PNG转换，本轮转换0。旧封存、已验收代码与共享库不改。

建议分析端验收本次技术失败并关闭P10_A_NATIVE_PREFLIGHT_V2；下一步如需修正，应另发CPU任务，核实Torch UUID返回ABI、完善原类型记录和文本身份合同，随后另审新有限release。本次不实施修正，不进入P/V、采集、训练或完整评测。
'''
publish(RECEIPTS/f'{TASK}_REPORT.md',report,text=True)
heartbeat=dict(task_id=TASK,task_revision=1,node_role='A',status='failed_receipt_complete',started_at_utc=ACK['started_at_utc'],finished_at_utc=finished,updated_at_utc=finished,
 progress=dict(real_sh_invocations=1,release_consumed=True,diagnostic_returncode=1,graphics_entered=71,native_sampling_calls=0,flow_forward_calls=0,restored_holders=8),automatic_retries=0)
publish(RECEIPTS/f'{TASK}_HEARTBEAT.json',heartbeat)
# Only this wave's new files; retained cache included without deleting anything.
files=[f for root in [W,RUN,D,CACHE] if root.exists() for f in root.rglob('*') if f.is_file() and f.name not in {'EVIDENCE_MANIFEST.json','RETENTION_INVENTORY.json'}]
files += [CLAIM,RECEIPTS/f'{TASK}_ACK.json',RECEIPTS/f'{TASK}_REPORT.md',RECEIPTS/f'{TASK}_HEARTBEAT.json']
files=sorted(set(files));records=[ref(f) for f in files]
retention=dict(task_id=TASK,delete_authorized=False,deletions=0,policy='Retain all run evidence/cache pending analysis decisions',files=[dict(path=str(f),realpath=str(f.resolve()),size_bytes=f.stat().st_size,project='Corrector',reason='Current consumed native V2 run evidence/cache') for f in files],file_count=len(files),total_bytes=sum(x['size_bytes'] for x in records))
publish(W/'RETENTION_INVENTORY.json',retention);records.append(ref(W/'RETENTION_INVENTORY.json'))
publish(W/'EVIDENCE_MANIFEST.json',dict(task_id=TASK,files=records,exclusions=['manifest itself','final RESULT','post-publication audit/queue delivery receipt'],all_evidence_retained=True))
artifacts=[RECEIPTS/f'{TASK}_REPORT.md',RUN/'LAUNCH_RESULT.json',RUN/'launch_identity.json',RUN/'diagnostic_link.json',RUN/'wave_timing.jsonl',RUN/'process_family_cleanup.json',CLAIM,D/'CLAIM.json',
 D/'failure.json',D/'resource_receipt.json',D/'events.jsonl',D/'initialization_receipt.json',D/'initialization_events.jsonl',D/'graphics_receipt.json',D/'graphics_events.jsonl',D/'graphics_api_results.jsonl',D/'graphics_cleanup.json',D/'observation_events.jsonl',D/'policy_device.json',D/'device_mapping.json',D/'loader_identity.json',D/'artifact_status.json',
 W/'FINAL_AUDIT.json',W/'ACTUAL_COUNTS.json',W/'GRAPHICS_COUNTS.csv',W/'POLICY_UUID_FAILURE_EVIDENCE.json',W/'MISSING_ARTIFACTS.json',W/'COMMAND_EXIT.json',W/'COMMAND_STDOUT_STDERR.log',W/'CPU_PROCESS_AND_GUARD_OBSERVATIONS.jsonl',W/'OCCUPANCY_BEFORE.json',W/'OCCUPANCY_AFTER_COMMAND.json',W/'POST_COMMAND_PROCESSES.json',W/'GUARD_LOG_WINDOW.log',W/'EVIDENCE_MANIFEST.json',W/'RETENTION_INVENTORY.json']
result=dict(campaign_id='corrector-sim-20260919',task_id=TASK,revision=1,task_revision=1,role='A',node_role='A',hostname=ACK['hostname'],session_id=ACK['executor_session_id'],status='failed',technical_failure=True,receipt_work_complete=True,
 started_at_utc=ACK['started_at_utc'],finished_at_utc=finished,release_id=R['release_id'],run_id=R['run_id'],wave_id=R['wave_id'],shard_id=R['shard_id'],
 input_identity=dict(protocol=ref(W/'inputs/tasks/A10_PREFLIGHT_NATIVE_V2.md'),release=ref(W/'inputs/releases/P10_A_NATIVE_PREFLIGHT_V2.json'),CONTROL=ref(W/'inputs/CONTROL.json'),TASK_BOARD=ref(W/'inputs/TASK_BOARD.json'),
 code=ref(P/'code/CODE_MANIFEST.json'),config=ref(P/'proposal/PROPOSAL.json'),integration=ref(P/'INTEGRATION_MANIFEST.json'),data=ref(P/'proposal/source_manifest.json'),
 model=dict(path=str(Path(PROPOSAL['checkpoint'])/'model.safetensors'),sha256=PROPOSAL['model_sha256'],size_bytes=9354050752,verification_basis='Both frozen launcher and diagnostic load_authorization completed full SHA before observed driver/policy stage; no extra checker/hash',model_loaded=False)),
 artifacts=[ref(f) for f in artifacts],
 resource_counts=dict(**AUDIT['counts']['public']['counts'],completed_rollouts=0,gpu_seconds=None,GPU_seconds_missing_reason=AUDIT['counts']['missing_GPU_measurements_reason'],
 real_sh_invocations=1,release_claims=1,model_initializations=0,environment_instances=0,environment_reset_calls=0,reset_model_calls=0,initialization_physics_substeps=0,policy_physics_substeps=0,
 diagnostic_native_resets_returned=0,diagnostic_observations_returned=0,post_control_observations_returned=0,usable_observation_artifacts=0,
 explicit_graphics_entered=71,explicit_graphics_returned=71,explicit_graphics_failed=0,explicit_graphics_incomplete=0,graphics_counts=AUDIT['counts']['graphics']['entered_budget_usage'],
 peak_GPU_memory_bytes=None,observed_peak_process_RSS_MiB=441.4921875,observed_peak_process_HWM_MiB=441.4921875,CPU_memory_scope='maximum observed single matching process, not process-tree sum or guaranteed final peak',
 CPU_PNG_conversions=0,extra_CPU_checker_invocations=0,extra_GPU_queries_by_observer_or_audit=0,deletions=0,retries=0,new_evidence_bytes_before_final_receipt=retention['total_bytes']),
 failures_and_retries=[dict(command=ACK['command'],returncode=1,stage='heavy_imports_and_policy_device_binding',error_type='ContractError',error='Torch UUID property is not the frozen string ABI',
 evidence=ref(D/'failure.json'),retries=0,cleanup_errors=[],process_group_exited=True,holders_restored=8,release_consumed=True)],
 timing=AUDIT['timing'],occupancy=AUDIT['occupancy'],policy_UUID=AUDIT['policy_UUID'],
 requested_outputs_missing=json.loads((W/'MISSING_ARTIFACTS.json').read_text()),
 findings=[
 'One frozen sh invocation completed with technical failure before model initialization; no retry, seed/device/library/renderer substitution or deletion.',
 'All8 EGL CUDA-handle mappings completed and matched frozen PCI/kernel UUID inventory; fixed target unique.',
 'Torch device selection and property query returned; saved str(UUID) equals target, but raw non-str value failed frozen type guard; exact Python type not retained.',
 '71explicit graphics entries all returned,0failed/incomplete; semantic UUID guard failure remains an overall technical failure.',
 'Model initialization/diagnostic attempt/VLA/flow/environment/reset/physics/control/monitor/critic/backward/update/rollout counts all0.',
 'No native RGB,raw50 plans,H queue checks or transition was reached; missing reasons preserved, no PNG fabricated or extra render.',
 'Cleanup releaseThread1 succeeded with no errors; independent process group fully exited, no matching residual process.',
 'All8holder managers restored only after process-group exit; existing guard27508 retained.',
 'Actual GPU-seconds and peak GPU memory are unknown; wall time and CPU process observations reported separately.',
 'Release consumed on claim; allunused caps void; old receipts/bundles unchanged and no automatic subsequent phase.'
 ],
 blockers=[dict(issue='Runtime Torch UUID value is not str, contrary to the frozen guard expectation',impact='Native model/environment/RGB/sampler preflight unvalidated',evidence=ref(W/'POLICY_UUID_FAILURE_EVIDENCE.json'),resolution='Analysis may issue a separate CPU ABI repair task and later new finite compute release; do not reuse this release')],
 next_task_proposal=dict(status='analysis_decision_required_not_authorized',scope='CPU-only investigation of installed Torch UUID binding type and conservative canonical text identity contract with raw type evidence and synthetic checks; no GPU probes or edits under this consumed task',compute_budget=0,reuse_current_release=False),
 release_consumed=True,remaining_budget_reusable=False,analysis_closure_requested=True,formal_task_success_rate_sample=False,all_evidence_retained=True,artifact_reference_count=len(artifacts),evidence_manifest_files=len(records))
out=RECEIPTS/f'{TASK}_RESULT.json';assert not out.exists();publish(out,result)
print(json.dumps(dict(RESULT=ref(out),REPORT=ref(RECEIPTS/f'{TASK}_REPORT.md'),LAUNCH_RESULT=ref(RUN/'LAUNCH_RESULT.json'),artifact_references=len(artifacts),evidence_manifest_files=len(records)),ensure_ascii=False))
