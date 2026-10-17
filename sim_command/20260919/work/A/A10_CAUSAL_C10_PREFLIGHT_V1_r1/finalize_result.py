from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re
ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang');B=ROOT/'Corrector/sim_command/20260919';T='A10_CAUSAL_C10_PREFLIGHT_V1';RID='P10_A_CAUSAL_C10_PREFLIGHT_V1'
W=B/'work/A'/(T+'_r1');O=B/'results/A'/T;R=B/'results/A/P10_CAUSAL_C10_V1_launcher_runs'/(T+'_r1_A_wave09');P=B/'results/A/A10_CAUSAL_C10_CPU_V1'
def read(p):return json.loads(p.read_text())
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size_bytes=p.stat().st_size)
def put(p,x):
 with p.open('x') as f:f.write(x if isinstance(x,str) else json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
cmd=read(W/'COMMAND_RESULT.json');launch=read(R/'LAUNCH_RESULT.json');audit=read(O/'INDEPENDENT_LEDGER_AUDIT.json');coverage=read(O/'BRANCH_COVERAGE.json');failure=read(R/'Post/failure.json')
assert cmd['command_invocations']==1 and cmd['exit_code']==3 and cmd['claim_exists']
assert audit['all_within_caps'] and audit['counts_complete'] and audit['agrees_with_launcher'] and audit['total_entered']==audit['total_returned']
assert launch['completed_C10_branches']==coverage['completed_C10_branches']==[]
assert launch['restoration']['status']=='occupancy_resolved'
assert launch['process_family_cleanup']['status']=='all_formal_group_members_exited'
rest=launch['restoration']['guard_status'];before=read(W/'guard_status_before.json');assert rest['pid']==before['pid']==27508
assert set(rest['gpus'])==set(map(str,range(8))) and all(v['state']=='holder' for v in rest['gpus'].values())
marks=[json.loads(x) for x in (R/'wave_timing.jsonl').read_text().splitlines()];timepoints={x['phase']:x['monotonic_seconds'] for x in marks}
timing=dict(parent_full_checks_and_identity_seconds=timepoints['lifecycle_requested']-timepoints['launcher_started'],
    observed_lifecycle_request_to_reserved_entry_seconds=timepoints['reserved_command_started']-timepoints['lifecycle_requested'],
    Post_timed_child_seconds=timepoints['timed_process_exited']-timepoints['timed_process_started'],
    post_reservation_group_exit_to_restoration_observed_seconds=timepoints['restoration_observed']-timepoints['lifecycle_returned'],
    outer_command_seconds=cmd['elapsed_seconds'],whole_end_to_end_hard_cap=None,handoff_nominal_cap_seconds=300,per_child_timeout_seconds=1800,per_child_kill_grace_seconds=30,
    guard_successful_poll_count=None,guard_poll_scope='not included in parent/branch NVML identity calls; successful raw polling sequence absent',GPU_seconds=None,peak_RAM_bytes=None,peak_VRAM_bytes=None)
lines=(W/'gpu_occupancy_guard.log.captured_tail').read_text().splitlines()
start=datetime.fromisoformat(cmd['started_at_utc']);end=datetime.fromisoformat(cmd['ended_at_utc']);window=[]
for line in lines:
 try:t=datetime.fromisoformat(line.split(' ',1)[0].replace('Z','+00:00'))
 except ValueError:continue
 if start<=t<=end:window.append(line)
put(O/'HOLDER_LOG_WINDOW.txt','\n'.join(window)+'\n')
yields=[x for x in window if ': yielded;' in x];starts=[x for x in window if ': started holder manager ' in x]
assert sorted(int(re.search(r'GPU (\d+):',x).group(1)) for x in yields)==list(range(8))
assert sorted(int(re.search(r'GPU (\d+):',x).group(1)) for x in starts)==list(range(8))
put(O/'TIMING_AND_HOLDER_AUDIT.json',dict(status='PASS',timing=timing,baseline_guard_pid=before['pid'],restored_guard_pid=rest['pid'],
    before_holders=before['gpus'],restored_holders=rest['gpus'],observed_yield_manager_log_rows=yields,observed_restart_manager_log_rows=starts,
    log_meaning='manager log timestamps only; not reconstructed GPU last-compute times or successful empty-app poll evidence',
    all_formal_processes_exited=True,cleanup_signal_actions=launch['process_family_cleanup']['actions'],holder_count_restored=8,
    holder_restore_after_lifecycle_exit=True,shared_daemon_restarted=False,auditor_GPU_queries=0))
counts=audit['total_entered'];post=audit['branches']['Post']
missing=['live observations/RGB','native prefix actions/transitions','legal cut','matured D residual','G0 decision/real-vs-forced flag',
    'Post/Velocity new anchor/noise/flow/numerics/constraints','C10 execution','raw tail discard','H20 restore/remaining19','final parameter-version verification']
put(O/'STAGE_AVAILABILITY.json',dict(status='NOT_REACHED_AFTER_TECHNICAL_SETUP_FAILURE',completed_C10_branches=[],
    available=['policy strict loader: 813 tensors, no missing/unexpected keys','actual Torch _CUuuid identity accepted; one conversion',
        'fixed EGL-CUDA handle/PCI/UUID mapping and loader path','9 model initializations and auxiliary checkpoint loads',
        'one language embedding; no visual encoder','resource/cleanup/holder restoration evidence'],
    unentered_or_unavailable={name:None for name in missing},unavailable_is_not_numerical_failure_label=True,
    G0_trigger=None,forced_engineering_intervention=None,success_rate_sample=False,paired_performance_estimate=False,hidden_state_equivalence_claim=False,
    hardware_or_simulator_calls_by_postrun_auditor=0,CPU_lossless_RGB_conversion_count=0))
report=f'''# A10_CAUSAL_C10_PREFLIGHT_V1 — 技术失败，机会已消费

冻结 bash 命令执行 **1次 / claim1 / Post branch attempt1**，退出码3，耗时 {cmd['elapsed_seconds']:.3f}s。Post 在首次 `branch_start` 事件记录处失败：`TypeError: dict() got multiple values for keyword argument 'branch'`。Velocity 未启动；`completed_C10_branches=[]`。

静态定位：`run_branch()` 传入 `branch=branch`，真实 `Engine.emit()` 又在 `dict(..., branch=self.branch, **data)` 中传入同名键，异常发生在事件写入及 `engine.reset()` 之前。此前 controller fake 的 emit 实现不同，漏掉了此处组合检查。未运行新探针或修复，不改冻结包；定位依据与原始错误分别保存，未伪造运行栈。

| 阶段 | Post | Velocity |
|---|---|---|
| 实际启动 / branch attempt | 已启动 / 1 | 未启动 / 0 |
| 模型初始化 / language embedding | 9 / 1 | 未进入 |
| 环境实例 / native reset / 控制步 / RGB | 0 / 0 / 0 / 0 | 未进入，资源0 |
| 合法 cut / 真实G0与强制标记 | 未到达 / 未评估（null） | 未进入（null） |
| 实际 C10 控制 / 尾部丢弃 / H20恢复 | 0 / 未进入 / 未进入 | 未进入 |

VLA采样、flow、D/G0前向、Q前向、动作梯度、初始化/控制物理子步均0；已实际发生 policy1＋Q4＋D2＋G0 2 的9次模型初始化，以及1次语言 embedding，不能称整次计算为0。身份NVML父1＋Post1＝2；CUDA driver init1、EGL枚举1、属性/PCI各8；EGL display/context/render均0。全部111项 entered/returned见 `INDEPENDENT_LEDGER_AUDIT.json`，均在caps内且与LAUNCH_RESULT一致。

父私有账本1对、Post数值28对、初始化0对、graphics71对，已记录调用全部返回、无悬空末事件。真实事件记录器在计量调用之外报错，因此这些已返回计数不代表整体成功。strict loader证明813 tensors完整加载；固定UUID原类型为 `torch._C._CUuuid`，一次str转换匹配目标。最终参数版本核验和P/V数值/约束阶段未进入，没有RGB可查看；这些缺项不填写为数值失败或方法结果。

生命周期：预约入口在00:09:50.958进入，Post于00:12:58.912退出；完整进程组305957已空，cleanup signals为空。全部8holder在整组退出后恢复，daemon仍27508，manager 306666–306673；00:13:07.946观察到occupancy_resolved。记录的交接等待 {timing['observed_lifecycle_request_to_reserved_entry_seconds']:.3f}s，Post计时子进程 {timing['Post_timed_child_seconds']:.3f}s。manager yield日志只作管理事件时间，成功poll原始次数/时间仍null，未补硬件查询。

本次是源事件记录集成故障，不是任务失败样本、触发有效性或P/V排名结果。命令/claim均已消费，未用额度不可复用；旧八release未动，B未参与，安装/重启/训练/重试/删除0。请分析端关闭本release；不自动进入下一阶段。
'''
put(O/'REPORT.md',report)
# Final manifest includes immutable raw run evidence plus scoped wrapper/audit
# files. Continuous shared logs are represented by passive captured bytes.
files=[]
for root in [R,O,W]:
 for p in sorted(root.rglob('*')):
  if p.is_file() and p.name not in ['EVIDENCE_MANIFEST.json','QUEUE_MESSAGE.txt','QUEUE_DELIVERY.json']:files.append(ref(p))
put(O/'EVIDENCE_MANIFEST.json',dict(task_id=T,created_at_utc=datetime.now(timezone.utc).isoformat(),files=files,
    scopes=dict(runtime=str(R),delivery=str(O),outer_command_and_authorization=str(W)),new_hardware_queries=0,large_weight_rehashes_by_auditor=0,
    excluded_self=str(O/'EVIDENCE_MANIFEST.json'),later_created=['receipts/A/'+T+'_RESULT.json','QUEUE_MESSAGE.txt','QUEUE_DELIVERY.json']))
artifact_paths=[O/'REPORT.md',O/'LAUNCH_RESULT.json',O/'EVIDENCE_MANIFEST.json',O/'BRANCH_COVERAGE.json',O/'INDEPENDENT_LEDGER_AUDIT.json',O/'EXIT_AND_RESTORATION.json',
    O/'TIMING_AND_HOLDER_AUDIT.json',O/'HOLDER_LOG_WINDOW.txt',O/'FAILURE_SOURCE_ANALYSIS.json',O/'STAGE_AVAILABILITY.json',O/'SAVED_RGB_ARRAY_AUDIT.json',O/'RUNTIME_MANIFEST_AUDIT.json',
    W/'COMMAND_ENTERED.json',W/'COMMAND_PROCESS.json',W/'COMMAND_RESULT.json',W/'command.stdout',W/'command.stderr',
    R/'LAUNCH_RESULT.json',R/'launch_identity.json',R/'pre_reservation_device.json',R/'handoff_environment.json',R/'launcher_events.jsonl',R/'wave_timing.jsonl',R/'process_family_cleanup.json',R/'branch_process_exit.json',
    R/'Post/ARTIFACT_MANIFEST.json',R/'Post/RESOURCE_LEDGER.json',R/'Post/failure.json',R/'Post/numeric_events.jsonl',R/'Post/initialization_events.jsonl',R/'Post/graphics_events.jsonl',R/'Post/graphics_receipt.json',R/'Post/graphics_cleanup.json',
    R/'Post/graphics_api_results.jsonl',R/'Post/device_mapping.json',R/'Post/loader_identity.json',R/'Post/policy_device_type.json',R/'Post/policy_device.json',R/'Post/policy_loader.json',R/'Post/model_identity.json',R/'Post/nvml_identity.json']
assert all(p.exists() for p in artifact_paths)
claim=B/'results/A/P10_CAUSAL_C10_V1_release_claims'/(RID+'.json')
result=dict(campaign_id='corrector-sim-20260919',task_id=T,revision=1,owner='A',hostname='trial-303224955-trialrun-303224955-worker-0',
    status='TECHNICAL_FAILURE',at_utc=datetime.now(timezone.utc).isoformat(),ACK=ref(B/'receipts/A'/(T+'_ACK.json')),
    release=ref(B/'releases'/(RID+'.json')),claim=ref(claim),command_invocations=1,claim_count=1,actual_branch_attempts=1,
    release_consumed=True,release_closure_by_analysis_pending=True,remaining_caps_reusable=False,automatic_retry=False,
    raw_exit_code=3,elapsed_seconds=cmd['elapsed_seconds'],failure=failure,failure_stage='Post branch_start private event serialization before environment reset',
    source_analysis=ref(O/'FAILURE_SOURCE_ANALYSIS.json'),planned_branches=['Post','Velocity'],actually_started_branches=['Post'],completed_C10_branches=[],
    per_branch_coverage=coverage['branches'],resource_entered=counts,resource_returned=audit['total_returned'],counts_complete=True,within_caps=True,
    private_ledger_event_pairs=dict(parent=1,Post_numeric=28,Post_initialization=0,Post_graphics=71,Velocity_not_entered=True),
    stage_unavailable=missing,G0_real_trigger=None,forced_engineering_intervention=None,final_frozen_parameter_version_check=None,
    process_family_cleanup=launch['process_family_cleanup'],holder_restoration=launch['restoration'],holder_count_restored=8,guard_daemon_restarted=False,
    timing=timing,artifacts=[ref(p) for p in artifact_paths],runtime_manifest_verified_files=15,evidence_manifest_files=len(files),
    audit_operations=dict(saved_file_reads_only=True,additional_GPU_NVML_EGL_queries=0,extra_render=0,extra_models=0,weight_rehashes=0),
    deletions=0,shared_installations=0,training_updates=0,B_participated=False,old_releases_reused=False,public_interface_modified=False,
    conclusion='new event emitter integration failed before environment/cut; no numerical or method-success inference',
    scientific_interpretation=dict(success_rate_sample=False,ranking=False,paired_performance=False,full_hidden_state_equivalence=False,MT50_training_completed=False),
    next_action='await analysis close; no automatic repair/rerun/next stage')
receipt=B/'receipts/A'/(T+'_RESULT.json');put(receipt,result)
# Final consistency check reads only this task's evidence.
for row in result['artifacts']+files:
 p=Path(row['path']);assert ref(p)==row
print(json.dumps(dict(status='TECHNICAL_FAILURE',RESULT=ref(receipt),REPORT=ref(O/'REPORT.md'),LAUNCH_RESULT=ref(O/'LAUNCH_RESULT.json'),
    EVIDENCE_MANIFEST=ref(O/'EVIDENCE_MANIFEST.json'),artifact_refs=len(result['artifacts']),manifest_files=len(files),command=1,claim=1,branch_attempts=1,completed_C10_branches=[],restored_holders=8),indent=2,ensure_ascii=False))
