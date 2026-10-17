"""Audit saved evidence from the one V2 command, without model/GPU calls."""
import datetime
import hashlib
import json
from pathlib import Path

B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK='A10_PV_OFFLINE_PREFLIGHT_V2'
RID='P10_A_PV_OFFLINE_PREFLIGHT_V2'
W=B/'work/A'/f'{TASK}_r1'
OUT=B/'results/A'/TASK
PKG=B/'results/A/A10_PV_AUTH_METADATA_CPU_V1'
RUN=B/'results/A/P10_PV_V2_launcher_runs/A10_PV_OFFLINE_PREFLIGHT_V2_r1_A_wave07'
CLAIM=B/'results/A/P10_PV_V2_release_claims'/f'{RID}.json'
RCP=B/'receipts/A'

def read(path):
    return json.loads(path.read_text())

def ref(path):
    assert path.stat().st_size<2*1024*1024, str(path)
    data=path.read_bytes()
    return dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),size_bytes=len(data))

def put(path,obj):
    with path.open('x') as f:
        f.write(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

ack=read(RCP/f'{TASK}_ACK.json')
proposal=read(PKG/'proposal/PROPOSAL.json')
release=read(W/'authorization_snapshot/releases'/f'{RID}.json')
outer=read(OUT/'OUTER_COMMAND_RESULT.json')
launch=read(RUN/'LAUNCH_RESULT.json')
claim=read(CLAIM)
cleanup=read(OUT/'PROCESS_EXIT_AUDIT.json')
holders=read(OUT/'HOLDER_RESTORATION_AUDIT.json')
marks=[json.loads(s) for s in (RUN/'wave_timing.jsonl').read_text().splitlines()]
events=[json.loads(s) for s in (RUN/'launcher_events.jsonl').read_text().splitlines()]
assert len(events)==2 and events[0]['event_id']==events[1]['event_id']==1
assert events[0]['phase']=='entered' and events[1]['phase']=='returned'
assert events[0]['units']=={'native_nvml_identity_queries':1} and events[1]['error'] is None
assert claim['release_id']==RID and claim['release_sha256']==ack['release_sha256']==ref(B/'releases'/f'{RID}.json')['sha256']
assert claim['run_id']==release['run_id'] and claim['launcher_pid']==outer['command_pid']
assert claim['consumed_on_any_outcome'] is True and claim['unused_caps_reusable'] is False
assert outer['command_invocations']==1 and outer['returncode']==3 and outer['command_reaped'] is True
assert launch['status']=='failed' and launch['returncode']==1 and launch['release_consumed'] is True
assert launch['restoration']['status']=='occupancy_resolved' and len(holders['managers'])==8
assert holders['all_eight_yield_log_count']==holders['all_eight_restart_log_count']==8
assert cleanup['remaining_members']==[] and not cleanup['diagnostic_process_group_created']
assert launch['process_family_cleanup'] is None and not (RUN/'diagnostic').exists()
assert all(x['phase'] not in ['reserved_command_started','timed_process_started'] for x in marks)
expected={k:0 for k in release['resource_caps']};expected['native_nvml_identity_queries']=1
assert launch['total_entered']==launch['total_returned']==expected
assert launch['counts_complete'] is True
assert launch['launch_ledger']['entered']==launch['launch_ledger']['returned']=={'native_nvml_identity_queries':1}
assert launch['diagnostic_ledger']['status']=='not_entered'
assert all(v==0 for v in launch['diagnostic_ledger']['entered'].values())
assert all(v==0 for v in launch['diagnostic_ledger']['returned'].values())
assert all(expected[k]<=release['resource_caps'][k] for k in expected)
by={x['phase']:x for x in marks}
handoff=by['lifecycle_returned']['monotonic_seconds']-by['lifecycle_requested']['monotonic_seconds']
log=(W/'COMMAND.log').read_text()
assert 'GPUs still occupied; formal command was not launched' in log
now=datetime.datetime.now(datetime.timezone.utc).isoformat()

put(OUT/'RESOURCE_ACCOUNTING.json',dict(status='audited',scope='Private parent and child operation journals; not public interface_v1 UUID events',command_invocations=1,claim_count=1,claim_consumed=True,offline_attempts=0,parent=dict(journal=ref(RUN/'launcher_events.jsonl'),event_id_scope='parent-private integer IDs',entered_events=1,returned_events=1,ledger=launch['launch_ledger']),child=dict(journal_path=str(RUN/'diagnostic/events.jsonl'),journal_exists=False,event_id_scope='child-private integer IDs; never instantiated',entered_events=0,returned_events=0,ledger=launch['diagnostic_ledger'],absence_reason='Occupancy handoff failed before reserved.py and diagnostic.py were spawned'),resource_caps=release['resource_caps'],total_entered=expected,total_returned=expected,counts_complete=True,cap_violations=[],aliases_not_summed=True,persistent_guard_queries_and_holder_work_excluded_from_diagnostic_counters=True,guard_internal_query_count=None,guard_internal_query_count_reason='Existing lifecycle does not journal each poll; no extra hardware inspection added',extra_checker_or_probe_invocations=0,large_weight_hash_passes_returned=1,large_weight_hash_basis='Parent full authorization check returned before recorded NVML event; child repeated verification not entered',GPU_utilization_seconds=None,model_peak_VRAM_bytes=None,unused_caps_reusable=False))

absent=['policy_device_type.json','policy_device.json','policy_loader.json','cached_raw_a0.npy','bounded_anchor.npy','same_source_encoder_outputs.npz','Q_observed_context.npz','context_provenance.json','Post_arrays.npz','Post_result.json','reconstructed_noise.npy','noise_reconstruction.json','Velocity_arrays.npz','Velocity_result.json','numeric_checks.json','RESOURCE_LEDGER.json','ARTIFACT_MANIFEST.json']
put(OUT/'STAGE_DISPOSITION.json',dict(status='technical_failure_before_diagnostic',stages=dict(metadata_and_claim='passed_claim_consumed',parent_full_SHA='returned',parent_NVML_identity='entered_1_returned_1',occupancy_handoff='failed_90_second_empty_compute_wait',reserved_wrapper='not_spawned',timed_child='not_spawned',diagnostic_attempt='not_entered',policy_UUID_and_model_loader='not_entered',encoder_context_mask='not_entered',Q_PCA_normalizer='not_entered',Post_gradient_projection_constraints='not_entered',noise_reconstruction='not_entered',Velocity_flow_gradient_constraints='not_entered',frozen_parameter_runtime_checks='not_entered',model_process_cleanup='not_applicable_no_model_process_created',outer_and_lifecycle_exit='verified_no_remaining_members',all_A8_holders='restored'),absent_expected_diagnostic_artifacts=[dict(path=str(RUN/'diagnostic'/s),reason='Diagnostic process not spawned after occupancy timeout; no replacement or fabricated evidence') for s in absent],numerical_validation=False,task_success_rate_sample=False,deployment_cost_comparison=False,cached_diagnostic_sampling_actual=dict(Post=0,Velocity=0),deployment_sampling_convention=dict(Post=1,Velocity=2),future_stage_authorized=False))

source=ref(W/'failure_source/gpu_occupancy_guard.py')
put(OUT/'FAILURE_ANALYSIS.json',dict(status='observed_failure_with_source_supported_explanation',failure_stage='all_GPU_occupancy_handoff_before_reserved_wrapper',exception_type='RuntimeError',message='GPUs still occupied; formal command was not launched',recorded_in=ref(W/'COMMAND.log'),guard_source_snapshot=source,guard_empty_wait_nominal_seconds=90,measured_lifecycle_request_to_return_seconds=handoff,guard_stop_order='serial for-loop over eight holder managers; each stop waits 15s after TERM then up to5s after KILL',lifecycle_returned_utc=by['lifecycle_returned']['utc'],GPU6_yielded_utc='2026-09-19T21:57:24Z',GPU7_yielded_utc='2026-09-19T21:57:39Z',all8_restart_utc='2026-09-19T21:57:44Z',guard_log=ref(W/'HOLDER_LIFECYCLE_WAVE.log'),supported_explanation='Serial holder release exceeded the fixed 90-second empty-compute wait; GPU6 and GPU7 yielded after the lifecycle had already failed. This was before the diagnostic timeout and before any model import/load.',exact_NVML_app_rows_at_deadline=None,limitation='Guard does not retain per-poll application rows; no new probe was run to recreate the failure.',shared_guard_or_lifecycle_changed=False,retries=0))

audit=dict(status='passed_failure_evidence_audit',audited_at_utc=now,command_invocations=1,claim_count=1,offline_attempts=0,parent_private_event_pairs=1,child_private_event_pairs=0,resource_cap_entries=66,counts_match_frozen_LAUNCH_RESULT=True,all_known_command_sessions_exited=True,all8_holders_restored=True,diagnostic_group_created=False,diagnostic_cleanup_receipt_created=False,private_ledgers_not_concatenated=True,extra_GPU_or_model_probes=0,extra_full_input_hash_passes=0,retries=0,deletions=0,old_packages_or_receipts_modified=False,analysis_control_or_board_modified=False,release_consumed=True,remaining_caps_reusable=False,await_analysis_release_closure=True)
put(W/'FINAL_AUDIT.json',audit)

report=f'''A10_PV_OFFLINE_PREFLIGHT_V2 / revision1 已执行唯一冻结命令，结果为 occupancy 交接技术失败；无重试。本次命令1、claim1（已消费）、诊断attempt0。release SHA256：`{ack['release_sha256']}`。CONTROL25/TASK_BOARD32、固定主机/设备、输入及冻结包均未改。

guard 在清空等待约 {handoff:.3f} 秒后抛出 `GPUs still occupied; formal command was not launched`，早于 reserved.py/诊断子进程创建。源码的等待上限为90秒，holder按卡串行退出，每卡TERM等待最多15秒后KILL再等5秒；波次日志中GPU6/7到21:57:24/21:57:39才yield，晚于21:57:22.687的失败返回。现有证据支持串行holder交接超过固定等待上限；未保存超时瞬间NVML逐进程行，不追加探针还原，也不修改共享guard。

父层私有账本只有1个完整entered/returned事件：NVML身份核验1/1；子层账本未创建，全部计数0。66项资源汇总与冻结LAUNCH_RESULT逐项一致，无超额：模型初始化/载入、encoder/Q、guided/flow、Post/Velocity梯度、噪声重建、环境/reset/render/物理/训练全部0。父层完整SHA校验已返回（大权重1遍）；子层第二遍未进入，无额外checker/大权重hash。两账本未拼接成公共UUID事件流。

数值、mask/features、raw锚点、loader/策略UUID、噪声SHA、P/V约束、冻结参数产物均未产生，具体缺阶段见 STAGE_DISPOSITION.json；未生成替代数据。固定物理GPU的父层NVML证据保存在 pre_reservation_device.json。1800+30诊断timeout未启动，不把它解释成本次90秒guard等待。

冻结launcher返回3（内部lifecycle返回1），外层实测 {outer['wall_seconds']:.3f} 秒；已reap，外层和lifecycle会话均无残留成员。内部process_family_cleanup=null是因为reserved wrapper未启动，另交只读/proc退出审计。8holder于21:57:44重新启动，21:57:56.699被入口确认恢复；manager PID270938–270945，现有guard缓存及/proc复核通过。父层准备 {launch['timing']['preparation_seconds']:.3f} 秒，恢复观察 {launch['timing']['restoration_observation_seconds']:.3f} 秒。GPU利用时间、模型VRAM峰值未测，留null。

LAUNCH_RESULT：`{RUN/'LAUNCH_RESULT.json'}`。
外层回执、私有账本汇总、阶段缺失、失败源码/日志、进程退出和holder恢复审计位于 `{OUT}` 与 `{W}`；完整manifest随RESULT交付。

本次不提供数值成功、部署成本或任务成功率结论。诊断实际Post0/Velocity0采样；原部署Post1/Velocity2口径未变。旧六份release不复用，B未参与，删除0；本次剩余额度不可复用，请分析关闭P10_A_PV_OFFLINE_PREFLIGHT_V2，之后等待新任务。
'''
report_path=RCP/f'{TASK}_REPORT.md'
with report_path.open('x') as f:f.write(report)

files=sorted(x for x in W.rglob('*') if x.is_file())+sorted(x for x in OUT.rglob('*') if x.is_file())+sorted(x for x in RUN.rglob('*') if x.is_file())+[CLAIM,RCP/f'{TASK}_ACK.json',report_path]
manifest_path=OUT/'EVIDENCE_MANIFEST.json'
put(manifest_path,dict(schema='A_PV_one_attempt_failure_evidence_v1',task_id=TASK,files=[ref(x) for x in files],self_and_RESULT_excluded=True,queue_delivery_separate=True,retention='All new logs, caches, snapshots and receipts retained; no deletion'))
artifacts=[report_path,RCP/f'{TASK}_ACK.json',RUN/'LAUNCH_RESULT.json',OUT/'OUTER_COMMAND_RESULT.json',CLAIM,RUN/'launch_identity.json',RUN/'pre_reservation_device.json',RUN/'launcher_events.jsonl',RUN/'wave_timing.jsonl',OUT/'RESOURCE_ACCOUNTING.json',OUT/'STAGE_DISPOSITION.json',OUT/'FAILURE_ANALYSIS.json',OUT/'PROCESS_EXIT_AUDIT.json',OUT/'HOLDER_RESTORATION_AUDIT.json',W/'COMMAND.log',W/'HEARTBEAT.jsonl',W/'HOLDER_GUARD_BEFORE.json',W/'HOLDER_GUARD_AFTER_COMMAND.json',W/'HOLDER_LIFECYCLE_WAVE.log',W/'failure_source/gpu_occupancy_guard.py',W/'failure_source/gpu_occupancy_lifecycle.sh',W/'FINAL_AUDIT.json',manifest_path]
result=dict(campaign_id='corrector-sim-20260919',task_id=TASK,revision=1,role='A',hostname=ack['hostname'],session_id=ack['session_id'],status='failed',outcome='technical_failure_occupancy_handoff_before_diagnostic',started_at_utc=outer['started_at']['utc'],command_finished_at_utc=outer['finished_at']['utc'],finished_at_utc=now,input_identity=dict(control_revision=25,task_board_revision=32,release_id=RID,release_sha256=ack['release_sha256'],proposal_sha256=release['proposal_sha256'],code_manifest_sha256=release['code_manifest_sha256'],input_manifest_sha256=release['input_manifest_sha256'],config_sha256=release['config_sha256'],external_source_manifest_sha256=release['external_source_manifest_sha256'],run_id=release['run_id'],wave_id=release['wave_id'],shard_id=release['shard_id']),artifacts=[ref(x) for x in artifacts],command_invocations=1,actual_compute_release_claims=1,claim_consumed=True,command_opportunity_consumed=True,resource_counts=expected,returned_resource_counts=expected,counts_complete=True,private_ledgers=dict(parent_entered_events=1,parent_returned_events=1,child_status='not_entered',child_entered_events=0,child_returned_events=0,global_UUID_ledger_created=False),failure=dict(stage='occupancy_handoff_before_reserved_wrapper',message='GPUs still occupied; formal command was not launched',lifecycle_returncode=1,launcher_returncode=3,analysis=ref(OUT/'FAILURE_ANALYSIS.json')),formal_diagnostic_process_group_created=False,known_command_sessions_remaining=0,occupancy=dict(status='all8_holders_restored',lifecycle_was_entered=True,holder_yielded_count=8,holder_restarted_count=8,proof=ref(OUT/'HOLDER_RESTORATION_AUDIT.json')),observed_resources=dict(outer_wall_seconds=outer['wall_seconds'],parent_full_hash_passes_returned=1,child_full_hash_passes_returned=0,extra_full_hash_passes=0,child_usage=outer['child_usage'],GPU_utilization_seconds=None,model_peak_VRAM_bytes=None),extra_checker_or_probe_invocations=0,retries=0,deletions=0,numeric_validation=False,deployment_cost_comparison=False,task_success_rate_sample=False,old_receipts_modified=False,analysis_metadata_modified=False,release_consumed=True,remaining_caps_reusable=False,automatic_next_stage=False,requested_analysis_action='Accept failure evidence and close P10_A_PV_OFFLINE_PREFLIGHT_V2; no rerun under this release',retained_evidence_files=len(files))
result_path=RCP/f'{TASK}_RESULT.json'
put(result_path,result)
for row in result['artifacts']+read(manifest_path)['files']:
    assert ref(Path(row['path']))==row
for x in OUT.rglob('*'):
    if x.is_file():x.chmod(0o444)
report_path.chmod(0o444);result_path.chmod(0o444)
print(json.dumps(dict(status='failed_evidence_complete',RESULT=ref(result_path),REPORT=ref(report_path),artifacts=len(artifacts),evidence_files=len(files),command_invocations=1,claim_count=1,offline_attempts=0,holders_restored=8),indent=2))
