"""Build current-task delivery from completed saved evidence; no runtime actions."""
from pathlib import Path
import datetime,json
from audit_saved_helpers import load,ref,save
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W=B/'work/A/A11_COMMON_POOL_BATCH1_V1';P=B/'results/A/A11_COMMON_POOL_BATCH1_V1'
task='A11_COMMON_POOL_BATCH1_V1';release=load(W/'authorization/P11_A_COMMON_POOL_BATCH1_V1.json')
outer=load(W/'OUTER_COMMAND_RESULT.json');ledger=load(P/'INDEPENDENT_LEDGER_AUDIT.json')
coverage=load(P/'PARENT_AND_BRANCH_COVERAGE.json');intermediate=load(P/'AUDIT_INTERMEDIATE.json')
artifacts=load(P/'ARTIFACT_REFERENCE_AUDIT.json');storage=load(P/'SAVED_STORAGE_AUDIT.json')
exit_info=load(P/'EXIT_AND_RESTORATION.json');scheduler=load(P/'SCHEDULER_AUX_AUDIT.json')
failures=load(P/'FAILURE_AND_MISSING_EVIDENCE.json');timing=load(P/'SAVED_TIMING_AUDIT.json')
if any(x is None for x in (outer,ledger,coverage,intermediate,artifacts,storage,exit_info,scheduler,failures,timing)):
    raise SystemExit('Required post-exit audit incomplete')
parents=coverage['parents'];n=ledger['entered'];returned=ledger['returned']
audit_error_counts={k:len(artifacts[k]) for k in ('schema_errors','reference_errors','sequence_errors','artifact_errors')}
audit_error_counts['ledger_and_metadata_errors']=len(intermediate['errors'])
audit_clear=not any(audit_error_counts.values()) and ledger['within_all116_caps']
children=sum(x['branches_started'] for x in parents);complete=sum(x['complete_outcomes'] for x in parents)
parent_candidates=sum(x['candidate_qualified_for_analysis'] for x in parents)
restoration=exit_info.get('restoration') or {}
branch_rows=[r for p in parents for r in p['branches'] if r['started']]
technical_failures_present=bool(failures['failures'] or failures['missing'] or failures['wave_primary'] or
    failures['scheduler_primary'] or failures['publication_failures'] or failures['launcher_primary'] or failures['outer_error'] or
    any(r.get('raw_exit_code')!=0 or not r['outcome_complete'] for r in branch_rows))
before_cut_parents=[p['parent_key'] for p in parents if p['normal_complete_before_legal_cut']]
exit_interpretation=('保存证据显示全部已启动child退出0，primary/cleanup及发布失败为空。外层退出3、LAUNCH_RESULT=failed对应调度器的partial_or_failed：p04 normal于s48成功而未到cut55，后续14支按合同未启动；不将此覆盖缺口写成模型技术失败。'
    if outer['raw_exit_code']==3 and not technical_failures_present and before_cut_parents==['p04_disassemble_train0001_cut55']
    else '退出及失败原因以原始LAUNCH_RESULT和逐分支证据为准。')
absolute_s300=sum(p['absolute_s300_outcomes'] for p in parents)
early_success=sum(r.get('reason')=='success' and r['outcome_complete'] for r in branch_rows)
commit_terminal=[dict(parent_key=p['parent_key'],role=r['role'],steps=r['returned_commitment_steps'],
    discarded_raw_tail=r['discarded_raw_tail'],absolute_step=r['controls'],outcome_reason=r['reason'])
    for p in parents for r in p['branches'] if r['started'] and r['role']!='normal' and not r['H10_resumed']]
status='FORMAL_WAVE_EXITED_PENDING_ANALYSIS' if outer['raw_exit_code']==0 and exit_info['group_exit_proven'] else 'TECHNICAL_FAILURE_PENDING_ANALYSIS'
if outer['raw_exit_code']!=0 and exit_info['group_exit_proven']:status='FORMAL_WAVE_PARTIAL_OR_FAILED_PENDING_ANALYSIS'
if not audit_clear:status='AUDIT_REQUIRES_REVIEW'
rows=[]
for p in parents:
    started=[r for r in p['branches'] if r['started']]
    failed=[r['role'] for r in started if r.get('raw_exit_code')!=0 or not r['outcome_complete']]
    note=','.join(failed) or '无技术失败'
    if p['normal_complete_before_legal_cut']:
        normal=p['branches'][0];note=f"normal在s{normal['controls']}因{normal['reason']}终局，cut{p['source']['cut']}未到；后续不启动"
    rows.append('| '+ ' | '.join(map(str,[p['parent_key'],p['branches_started'],p['complete_outcomes'],p['full_state_exact_comparisons'],p['complete_repeat_groups'],note]))+' |')
report=f'''# {task} 执行与审计

状态：{status}。唯一正式命令执行1次，claim1；外层退出码{outer['raw_exit_code']}，保存耗时{outer['elapsed_seconds']:.3f}秒。并发峰值（保存的调度事件）{scheduler['maximum_active_parent_slots']}个父源。

{exit_interpretation}

固定8源中实际启动{sum(p['branches_started']>0 for p in parents)}源、{children}个cold分支；{complete}个完整终局。{parent_candidates}源具备15分支/14次状态比较/4类配对目标的完整候选证据，仍待分析验收。当前有效索引保持1个旧train父源，未加入本批。完整字段/MJB闭合不扩写为普遍物理等价，physical_equality_proven=null。

| 父源 | 启动分支 | 完整终局 | 精确状态比较 | 完整双repeat组 | 停源或失败说明 |
|---|---:|---:|---:|---:|---|
{chr(10).join(rows)}

完整终局包括{absolute_s300}支到达绝对s300、{early_success}支合法提前成功。8支Q在commitment内或边界成功（shelf plus两支8步；stick-pull a0/plus四支9步、minus两支10步），保存尾部丢弃42/41/40；终局后未再采H10，不虚报H10恢复。其余非normal分支的恢复记录逐支可查。Q/D/G0均为冻结采集候选及监督字段，未执行G0触发器。

实际entered：模型载入{n['policy_model_loads']}、采样{n['vla_sampling_calls']}、flow{n['flow_forward_calls']}、控制{n['env_steps']}、观测{n['observation_calls']}、reset{n['environment_reset_calls']}、初始化物理子步{n['initialization_physics_substeps']}。完整116项entered/returned及独立私有账本见INDEPENDENT_LEDGER_AUDIT.json；冻结caps检查={ledger['within_all116_caps']}，审计差异计数={json.dumps(audit_error_counts,ensure_ascii=False)}。Q/D/G0前向={n['critic_forward_calls']}/{n['D_forward_calls']}/{n['G0_forward_calls']}，动作梯度={n['action_gradient_calls']}、训练更新={n['training_updates']}、重试={n['retries']}、删除={n['deletions']}；诊断/采集成本未拼接成公共UUID成本账本，也不作部署成本或方法排名。

整组退出证据={exit_info['group_exit_proven']}；既有lifecycle恢复状态={restoration.get('status')}，保存状态中的holder数={exit_info['eight_holders_recorded']}。数据/成本发布是否在整组退出之后={scheduler['published_after_group_exit']}。未新增holder/硬件查询，未终止无关进程。成功handoff原始poll次数仍null。

最终输出{storage['final_output_paths']}条路径、{storage['final_output_unique_inodes']}个独立inode、{storage['final_output_unique_inode_bytes']}字节（inode去重；partial硬链接不重复计样本）。保存的私有cache采样峰值、容量下界及存储缺项见SAVED_STORAGE_AUDIT.json。全系统峰值、项目quota、外部/unlinked临时写入、监测间超调、RSS/VRAM与实际物理IO仍未知。约1.148TB只是已知尺寸逻辑读取报价小计，严格上界null；实际保存时序见SAVED_TIMING_AUDIT.json，不宣称线性加速。

所有已启动源的成功、技术失败和缺项均保留；父源及每branch覆盖、Q/G0配对资格、源/UUID/严格载入证明及失败栈分别附JSON。旧12计算release不复用，本次未入额度不可复用。完成后停止，等待分析验收关闭；未自动下一批、训练、评测、安装或删除。
'''
with (P/'REPORT.md').open('x') as f:f.write(report)
evidence_paths=[]
for root in (W,P):
    evidence_paths.extend(p for p in root.rglob('*') if p.is_file() and p.name not in ('EVIDENCE_MANIFEST.json',) and not p.name.startswith('QUEUE_FINAL'))
ack=B/'receipts/A'/f'{task}_ACK.json';evidence_paths.append(ack)
for k in ('claim','command_record'):
    path=Path(release['paths'][k])
    if path.exists():evidence_paths.append(path)
evidence_paths=sorted(set(evidence_paths),key=str)
manifest=P/'EVIDENCE_MANIFEST.json'
save(manifest,dict(schema='current_execution_delivery_manifest_v1',task_id=task,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    files=[ref(p) for p in evidence_paths],runtime_files_manifest=ref(P/'RUNTIME_FILES.jsonl'),
    large_model_payloads_rehashed=False,immutable_runtime_outputs_unmodified=True))
result=B/'receipts/A'/f'{task}_RESULT.json'
save(result,dict(task_id=task,task_revision=1,node_role='A',status=status,host=release['owner_host'],
    release_ref=ref(W/'authorization/P11_A_COMMON_POOL_BATCH1_V1.json'),ack=ref(ack),report=ref(P/'REPORT.md'),
    evidence_manifest=ref(manifest),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    command_invocations=1,claims=1,release_opportunity_consumed=True,unused_caps_reusable=False,no_retry=True,
    outer_result=outer,formal_group_exit_proven=exit_info['group_exit_proven'],restoration=restoration,
    saved_holder_count=exit_info['eight_holders_recorded'],resource_entered=n,resource_returned=returned,
    resource_counts_complete=not ledger['missing_or_corrupt_scopes'],
    resource_entered_are_saved_lower_bounds=bool(ledger['missing_or_corrupt_scopes']),
    within_all116_caps=ledger['within_all116_caps'],audit_error_counts=audit_error_counts,
    actual_parent_starts=sum(p['branches_started']>0 for p in parents),actual_branch_starts=children,
    complete_outcomes=complete,all15_and14states_and4paired_targets=parent_candidates,
    raw_exit_interpretation=exit_interpretation,technical_failures_in_saved_evidence=technical_failures_present,
    absolute_s300_outcomes=absolute_s300,legal_early_success_outcomes=early_success,
    terminal_at_or_before_commitment_end_without_H10_resample=commit_terminal,
    source_coverage=[{k:p[k] for k in ('parent_key','source','device','branches_started','complete_outcomes','full_state_exact_comparisons','complete_repeat_groups','candidate_qualified_for_analysis','coverage_note','normal_complete_before_legal_cut')} for p in parents],
    existing_accepted_parent_count=1,new_accepted_parent_count=0,analysis_acceptance_pending=True,
    physical_equality_proven=None,B_participated=False,followup_computation_authorized=False,
    artifacts=[ref(p) for p in sorted(P.iterdir()) if p.is_file() and p!=manifest],
    delivery_interpretation='All started-source evidence retained; launcher completion is not coverage/qualification acceptance; costs are collection evidence only'))
print(json.dumps(dict(result=ref(result),report=ref(P/'REPORT.md'),manifest=ref(manifest),status=status),ensure_ascii=False),flush=True)
