"""Audit and receipt for the single pre-claim metadata failure; no reexecution."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK='A10_PV_OFFLINE_PREFLIGHT_V1';RID='P10_A_PV_OFFLINE_PREFLIGHT_V1'
W=Path(__file__).parent;OUT=B/'results/A'/TASK;REC=B/'receipts/A'
P=B/'results/A/A10_PV_OFFLINE_PREFLIGHT_CPU_V1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p),size_bytes=p.stat().st_size)
def write(p,v):
    with Path(p).open('x') as f:f.write(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

def main():
    OUT.mkdir(exist_ok=False)
    ack=read(REC/(TASK+'_ACK.json'));r=read(B/'releases'/ (RID+'.json'));prop=read(P/'proposal/PROPOSAL.json')
    exit=read(W/'COMMAND_EXIT.json');attempt=read(W/'COMMAND_ATTEMPT.json');failure=read(W/'FAILURE_ANALYSIS.json')
    process=read(W/'PROCESS_EXIT_AUDIT.json');occupancy=read(W/'OCCUPANCY_FINAL.json')
    native=B/'results/A/P10_PV_launcher_runs'/r['run_id'];claim=B/'results/A/P10_PV_release_claims'/ (RID+'.json')
    assert exit['returncode']==1 and not claim.exists() and not native.exists()
    assert exit['child_wait_returned'] and not process['matching_processes']
    assert occupancy['same_manager_pids_as_before'] and occupancy['cache_timestamp_after_command_exit']
    for row in ack['inputs_checked']:assert sha(row['path'])==row['sha256']
    assert sha(B/'releases'/ (RID+'.json'))==ack['release_sha256']
    contract=P/'code/core/contracts.py';code_manifest=read(P/'code/CODE_MANIFEST.json')
    assert sha(contract)==next(x['sha256'] for x in code_manifest['files'] if x['path']=='core/contracts.py')
    now=datetime.now(timezone.utc).isoformat()
    source_proof=dict(failure,source_matches_accepted_code_manifest=True,source_manifest=ref(P/'code/CODE_MANIFEST.json'),
        runtime_trace=ref(W/'launcher.log'),task_board_snapshot=next(x for x in ack['inputs_checked'] if x['path'].endswith('/TASK_BOARD.json')))
    write(OUT/'FAILURE.json',source_proof)
    ledgers={}
    for name,caps,path in [('launcher',prop['launcher_caps'],native/'launcher_events.jsonl'),('diagnostic',prop['diagnostic_caps'],native/'diagnostic/events.jsonl')]:
        ledgers[name]=dict(ledger_namespace=name,private_ledger=True,public_interface_uuid_stream=False,
            path=str(path),exists=False,status='not_created_before_claim' if name=='launcher' else 'child_not_spawned',
            entered=dict.fromkeys(caps,0),returned=dict.fromkeys(caps,0),events_entered=0,events_returned=0,events_unresolved=[],
            zero_basis='Runtime stack exits at launch.py:26 metadata guard, before claim at27, launcher Meter/identity/full hash/lifecycle or child creation. No missing event is treated as a refunded entry.')
    counts=dict.fromkeys(r['resource_caps'],0)
    ledger=dict(status='not_entered_verified_preclaim_exit',private_ledgers=ledgers,total_entered=counts,total_returned=counts,
        command_invocations=1,claim_creations=0,offline_attempts=0,parent_child_ids_concatenated=False,
        resource_counts_exact_for_explicit_scope=True,whole_host_holder_compute_excluded=True,
        framework_internal_GPU_calls='not entered: Torch/CUDA/model child was not imported or spawned',
        remaining_caps_reusable_by_executor=False,automatic_retry=False)
    write(OUT/'RESOURCE_LEDGER.json',ledger)
    stages={name:dict(status='not_entered',reason='pre-claim Task board mismatch; no diagnostic process',artifact=None)
        for name in ['full_weight_SHA','NVML_device_binding','Torch_UUID','strict_policy_loader','same_source_encoder',
            'Q_context_and_mask','bounded_anchor','four_Q_loads','Post_gradient_and_projection','noise_reconstruction_SHA',
            'Velocity_sample_flow_gradients','final_constraint_audits','frozen_parameter_verification','numeric_results']}
    stages['launcher_native_LAUNCH_RESULT']=dict(status='not_created',artifact=None,reason='Frozen launcher fails before its claim/output directory/try-finally receipt initialization; executor supplies explicitly marked outer receipt')
    stages['occupancy_lifecycle']=dict(status='not_entered',reason='Metadata refusal before guard active check or lifecycle reservation',holders_stopped=0,holders_restored=0,restoration_required=False)
    write(OUT/'ARTIFACT_STATUS.json',dict(stages=stages,old_inputs_not_copied_as_new_results=True,old_task_results_not_resubmitted=True))
    write(OUT/'PROCESS_CLEANUP.json',dict(process,status='complete_no_formal_process_started',source=ref(W/'PROCESS_EXIT_AUDIT.json'),
        scope='Executor-launched frozen command process/session exited; reserved formal process group never created; no signals/deletion'))
    write(OUT/'HOLDER_STATE.json',dict(occupancy,source=ref(W/'OCCUPANCY_FINAL.json')))
    launch=dict(status='failed',receipt_origin='executor_outer_receipt_for_preclaim_exit_not_emitted_by_frozen_launcher',
        task_id=TASK,release_id=RID,release_sha256=ack['release_sha256'],run_id=r['run_id'],command=attempt['command'],cwd=attempt['cwd'],
        command_invocations=1,returncode=exit['returncode'],failure_stage='metadata_authorization_before_claim',exception='Task board mismatch',
        actual_task_board_status='released',frozen_guard_accepted_statuses=['ready','running'],
        release_claim_created=False,claim_consumption_occurred=False,release_closed_by_executor=False,
        automatic_retry=False,remaining_caps_reusable_by_executor=False,native_launcher_result=None,
        native_launcher_result_missing_reason=stages['launcher_native_LAUNCH_RESULT']['reason'],
        command_started_at=exit['started_at'],command_finished_at=exit['finished_at'],command_wall_seconds=exit['observed_wall_seconds'],
        resource_ledger=ref(OUT/'RESOURCE_LEDGER.json'),process_cleanup=ref(OUT/'PROCESS_CLEANUP.json'),holder_state=ref(OUT/'HOLDER_STATE.json'),
        GPU_numeric_work_entered=False,GPU_utilization_seconds=None,GPU_utilization_missing_reason='Not measured; no formal GPU task started; ongoing occupancy holders excluded',
        deployment_cost_comparison=False,deployment_sampling_calls=dict(Post=1,Velocity=2),
        next_step='Analysis resolves released versus ready/running task-board metadata and decides closure/new authorization. No executor correction or retry.')
    write(OUT/'LAUNCH_RESULT.json',launch)
    write(OUT/'INPUT_BINDING.json',dict(protocol=ack['inputs_checked'],release=ref(B/'releases'/ (RID+'.json')),
        proposal=ref(P/'proposal/PROPOSAL.json'),code_manifest=ref(P/'code/CODE_MANIFEST.json'),config=ref(P/'config/CONFIG.json'),
        input_manifest=ref(P/'INPUT_MANIFEST.json'),host_verified=ack['hostname'],planned_device=r['device'],actual_device_binding=None,
        actual_device_binding_missing_reason='metadata rejection occurred before NVML/Torch identity calls',
        full_SHA_checker_entered=False,large_weight_hash_passes=0,extra_checker_or_probe_calls=0))
    report=REC/(TASK+'_REPORT.md')
    with report.open('x') as f:
        f.write(f'''# {TASK} — 授权元数据阶段失败，未进入计算

冻结真实命令已按任务书执行 **1 次**，21:23:15–21:23:16 UTC 退出，returncode=1，命令壁钟 {exit['observed_wall_seconds']:.6f}s。当前 TASK_BOARD29 将任务标为 `released`，冻结 `code/core/contracts.py:44` 只接受 `ready` / `running`，因此抛出 `Task board mismatch`。未修改冻结包或分析端控制文件，未重试。

| 核对项 | 实际结果 |
|---|---|
| release / host | SHA与用户给定值一致；A主机匹配，CONTROL22/唯一任务与caps一致。 |
| claim / compute | claim **0**；offline attempt、NVML、Torch/device、模型载入、encoder、Q、guided/flow/梯度全部 **0**。完整SHA检查尚未进入，大权重hash0。 |
| P/V及约束证据 | 未进入，不能报告通过或填补数值；各缺失阶段见 ARTIFACT_STATUS.json。step1未使用、无补基线。 |
| 进程 / holder | 命令进程261577已reap，进程组/session无遗留；formal group/lifecycle未创建。新鲜guard缓存显示8个holder仍是原PID245508–245515且存活，未停卡，无恢复动作需求。仅CPU读取既有状态与/proc，未加GPU探针。 |
| 禁止项 | 环境/reset/render/物理/D/G0/训练/重试/删除0；B未参与，旧五份release保持关闭。 |

本次失败发生在 `launch.py:26`，早于claim及launcher账本/目录初始化，冻结launcher未产出自身LAUNCH_RESULT。已在 `results/A/{TASK}/LAUNCH_RESULT.json` 提供**明确标为executor外层补充回执**的失败结果，并分别记录未创建的父、子私有账本；未拼接为public UUID流。

请求分析端按本次失败回执关闭或处置release，并统一TASK_BOARD状态与冻结入口合同。虽然没有claim消费标记，本执行端不会复用本轮命令机会或自行重跑。部署口径仍Post1/Velocity2；本次不产生数值成功、任务成功率或部署成本结论。所有新证据保留。
''')
    write(W/'FINAL_AUDIT.json',dict(status='passed_failure_evidence_audit',failure_scope='preclaim_metadata_guard',
        release_SHA_matches=True,protocol_snapshots_unchanged=True,guard_source_matches_frozen_manifest=True,
        command_invocations=1,claim_exists=False,formal_launcher_directory_exists=False,compute_counts_zero=True,
        process_session_empty=True,holders_8_unchanged_and_live=True,guard_cache_newer_than_command_exit=True,
        no_GPU_probe_or_extra_checker=True,no_old_artifact_mutation=True,deletions=0,
        actual_numeric_path_validated=False,finished_at_utc=now))
    write(W/'RETENTION.json',dict(status='retain_all_pending_analysis_decision',delete_release=None,deletions=0,
        roots=[str(W),str(OUT)],receipts=[str(REC/(TASK+'_ACK.json')),str(report),str(REC/(TASK+'_RESULT.json'))],
        includes=['raw stdout/stderr','command/exit evidence','guard snapshots','metadata snapshots','outer failure receipts','later queue transport']))
    files=[p for root in [W,OUT] for p in root.rglob('*') if p.is_file()]+[REC/(TASK+'_ACK.json'),report]
    manifest=W/'EVIDENCE_MANIFEST.json'
    write(manifest,dict(task_id=TASK,files=[ref(p) for p in sorted(files)],excluded=['self','RESULT','mutable heartbeat','later queue delivery'],retained=True))
    artifacts=[report,*[OUT/n for n in ['LAUNCH_RESULT.json','RESOURCE_LEDGER.json','FAILURE.json','ARTIFACT_STATUS.json','PROCESS_CLEANUP.json','HOLDER_STATE.json','INPUT_BINDING.json']],
        *[W/n for n in ['launcher.log','COMMAND_ATTEMPT.json','COMMAND_PROCESS.json','COMMAND_EXIT.json','GUARD_BEFORE.json','GUARD_AFTER.json','PROCESS_EXIT_AUDIT.json','OCCUPANCY_FINAL.json','FAILURE_ANALYSIS.json','FINAL_AUDIT.json','RETENTION.json','EVIDENCE_MANIFEST.json']]]
    result=dict(campaign_id=r['campaign_id'],task_id=TASK,revision=1,role='A',hostname=ack['hostname'],session_id=ack['executor_session_id'],status='failed',
        outcome='preclaim_authorization_metadata_failure_no_compute',started_at_utc=ack['started_at_utc'],finished_at_utc=now,
        release_id=RID,release_sha256=ack['release_sha256'],run_id=r['run_id'],wave_id=r['wave_id'],shard_id=r['shard_id'],
        input_identity=read(OUT/'INPUT_BINDING.json'),artifacts=[ref(p) for p in artifacts],resource_counts=counts,
        private_launcher_accounting=ledgers['launcher'],private_diagnostic_accounting=ledgers['diagnostic'],public_UUID_events_emitted=0,
        command_invocations=1,actual_compute_release_claims=0,claim_consumption_occurred=False,
        failures_and_retries=dict(command_failures=1,compute_attempts=0,compute_failures=0,automatic_retries=0,failure_stage='metadata_authorization_before_claim',error='Task board mismatch'),
        numerical_results=None,numerical_missing_reason='diagnostic child never spawned',model_freeze_result=None,model_freeze_missing_reason='no model initialized',
        process_cleanup=ref(OUT/'PROCESS_CLEANUP.json'),occupancy=ref(OUT/'HOLDER_STATE.json'),
        findings=['Release/host/claim were checked and ACK written before the single frozen command.',
            'Task-board state released conflicts with unchanged ready/running-only guard; launcher refused before claim.',
            'No full SHA, NVML, Torch, encoder/Q/PV model calls, environment or lifecycle work entered.',
            'Frozen launcher produced no own LAUNCH_RESULT; explicit executor outer failure receipt supplied, never misattributed.',
            'Command process/session exited; all eight original holders remain live and unchanged; restoration is not applicable.',
            'Private parent/child accounting kept separate; missing stages remain unavailable, not fabricated as success.'],
        blockers=[dict(field='TASK_BOARD.tasks[id=A10_PV_OFFLINE_PREFLIGHT_V1].status',actual='released',frozen_allowed=['ready','running'],owner='analysis')],
        next_action='Analysis disposition/closure and any explicit new authorization; no retry or next stage by executor',
        remaining_caps_reusable_by_executor=False,release_closed_by_executor=False,old_receipts_modified=False,
        deployment_sampling_calls=dict(Post=1,Velocity=2),deployment_cost_comparison=False,task_success_rate_sample=False,
        retained_evidence_files=len(files),deletions=0)
    write(REC/(TASK+'_RESULT.json'),result)
    hb=B/'nodes/A'/ (TASK+'_HEARTBEAT.json');h=read(hb);h.update(status='failed',updated_at_utc=now,progress='Single command refused before claim: task-board released versus guard ready/running; zero compute; eight holders unchanged; receipts sealed',actual_launches=1,claim_exists=False,result=ref(REC/(TASK+'_RESULT.json')));hb.write_text(json.dumps(h,indent=2)+'\n')
    print(json.dumps(dict(result=ref(REC/(TASK+'_RESULT.json')),report=ref(report),artifacts=len(artifacts),evidence_files=len(files),launch_result=ref(OUT/'LAUNCH_RESULT.json')),indent=2))

if __name__=='__main__':main()
