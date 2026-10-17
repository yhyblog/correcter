"""Build current-task delivery from completed saved evidence; no runtime actions."""
from pathlib import Path
import datetime,json
from audit_saved_helpers import load,ref,save
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W=B/'work/A/A11_COMMON_POOL_BATCH3_V1';P=B/'results/A/A11_COMMON_POOL_BATCH3_V1'
task='A11_COMMON_POOL_BATCH3_V1';release=load(W/'authorization/P11_A_COMMON_POOL_BATCH3_V1.json')
outer=load(P/'OUTER_EXIT.json');ledger=load(P/'INDEPENDENT_LEDGER_AUDIT.json')
coverage=load(P/'PARENT_AND_BRANCH_COVERAGE.json');intermediate=load(P/'AUDIT_INTERMEDIATE.json')
artifacts=load(P/'ARTIFACT_REFERENCE_AUDIT.json');storage=load(P/'SAVED_STORAGE_AUDIT.json')
exit_info=load(P/'EXIT_AND_RESTORATION.json');scheduler=load(P/'SCHEDULER_AUX_AUDIT.json')
failures=load(P/'FAILURE_AND_MISSING_EVIDENCE.json');timing=load(P/'SAVED_TIMING_AUDIT.json')
occupancy=load(P/'OCCUPANCY_POLICY_OVERRIDE.json')
qualification=load(P/'DATA_QUALIFICATION_NOTE.json')
if qualification is None:raise SystemExit('Saved raw-alias qualification note required')
if occupancy is None:raise SystemExit('User occupancy override requires its separate saved audit')
if any(x is None for x in (outer,ledger,coverage,intermediate,artifacts,storage,exit_info,scheduler,failures,timing)):
    raise SystemExit('Required post-exit audit incomplete')
parents=coverage['parents'];n=ledger['entered'];returned=ledger['returned']
audit_error_counts={k:len(artifacts[k]) for k in ('schema_errors','reference_errors','sequence_errors','artifact_errors')}
audit_error_counts['ledger_and_metadata_errors']=len(intermediate['errors'])
audit_clear=not any(audit_error_counts.values()) and ledger['within_all116_caps'] and ledger['entered_equals_returned_plus_failed_plus_incomplete']
children=sum(x['branches_started'] for x in parents);complete=sum(x['complete_outcomes'] for x in parents)
parent_candidates=sum(x['candidate_qualified_for_analysis'] for x in parents)
restoration=exit_info.get('restoration') or {}
branch_rows=[r for p in parents for r in p['branches'] if r['started']]
claims=int(Path(release['paths']['claim']).is_file())
non_normal=[r for r in branch_rows if r['role']!='normal']
old_controls=[r for r in non_normal if r['role'].startswith('G0_old_')]
replacement_branches=[r for r in non_normal if not r['role'].startswith('G0_old_')]
branch_semantics=dict(non_normal_comparison_branches_started=len(non_normal),candidate_replacement_branches_started=len(replacement_branches),G0_old_control_branches_started=len(old_controls),actual_plan_replaced_true=sum((r.get('intervention_evidence') or {}).get('plan_replaced') is True for r in non_normal),G0_old_plan_replaced_true=sum((r.get('intervention_evidence') or {}).get('plan_replaced') is True for r in old_controls),public_episode_audit=artifacts.get('branch_semantics'),online_G0_calls=n['G0_forward_calls'])
technical_failures_present=bool(failures['failures'] or failures['missing'] or failures['wave_primary'] or
    failures['scheduler_primary'] or failures['publication_failures'] or failures['launcher_primary'] or failures['outer_error'] or
    any(r.get('raw_exit_code')!=0 or not r['outcome_complete'] for r in branch_rows))
before_cut_parents=[p['parent_key'] for p in parents if p['normal_complete_before_legal_cut']]
exit_interpretation=('所有已启动child的完整终局与退出证据均无技术失败；非零外层状态需结合合法cut前终局覆盖缺口解释，原始退出码不改。'
    if not technical_failures_present and before_cut_parents else
    '所有已启动child均完整终局且退出0；原始外层exit0和LAUNCH_RESULT complete保留，覆盖和配对资格另行核验。'
    if not technical_failures_present and outer['returncode']==0 else
    '退出及技术失败原因以原始LAUNCH_RESULT、完整计量和逐分支证据为准。')
absolute_s300=sum(p['absolute_s300_outcomes'] for p in parents)
early_success=sum(r.get('reason')=='success' and r['outcome_complete'] and r['controls']<300 for r in branch_rows)
without_saved_H10=[dict(parent_key=p['parent_key'],role=r['role'],steps=r['returned_commitment_steps'],
    discarded_raw_tail=r['discarded_raw_tail'],absolute_step=r['controls'],outcome_reason=r['reason'])
    for p in parents for r in p['branches'] if r['started'] and r['role']!='normal' and not r['H10_resumed']]
commit_terminal=[x for x in without_saved_H10 if x['outcome_reason']=='success' and type(x['absolute_step']) is int and type(x['steps']) is int and x['steps']>0 and x['absolute_step']<=next(p['source']['cut'] for p in parents if p['parent_key']==x['parent_key'])+(10 if x['role'].startswith('Q_') else 5)]
commit_rows=[r for r in branch_rows if r['role']!='normal']
commit_full=sum(r['returned_commitment_steps']==(10 if r['role'].startswith('Q_') else 5) and r['discarded_raw_tail']==(45 if r['role'].startswith('G0_fresh') else 40) and r['H10_resumed'] for r in commit_rows)
commit_description=(f'{commit_full}个非normal比较分支均完成对应C10/C5、丢弃raw尾部并恢复H10。' if commit_full==len(commit_rows) else
    f'{len(without_saved_H10)}个已启动非normal比较分支没有保存H10恢复记录，逐支结合终局、实际commit步数和失败证据解释。')
status='FORMAL_WAVE_EXITED_PENDING_ANALYSIS' if outer['returncode']==0 and exit_info['group_exit_proven'] else 'TECHNICAL_FAILURE_PENDING_ANALYSIS'
if outer['returncode']!=0 and exit_info['group_exit_proven']:status='FORMAL_WAVE_PARTIAL_OR_FAILED_PENDING_ANALYSIS'
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

状态：{status}。唯一正式命令执行1次，claim{claims}；外层退出码{outer['returncode']}，保存耗时{outer['elapsed_seconds']:.3f}秒。并发峰值（保存的调度事件）{scheduler['maximum_active_parent_slots']}个父源。

{exit_interpretation}

固定8源中实际启动{sum(p['branches_started']>0 for p in parents)}源、{children}个cold分支；{complete}个完整终局。{parent_candidates}源具备15分支/14次状态比较/4类配对目标的完整候选证据，仍待分析验收。当前有效索引保持16个旧train父源、17个已处理槽（含1个normal-only），未预加入本批。完整字段/MJB闭合不扩写为普遍物理等价，physical_equality_proven=null。

| 父源 | 启动分支 | 完整终局 | 精确状态比较 | 完整双repeat组 | 停源或失败说明 |
|---|---:|---:|---:|---:|---|
{chr(10).join(rows)}

p04 door-close的a0/local_plus/local_minus引用同一800字节raw50，逐位相同。三个Q目标按raw-alias合同屏蔽（target=null、mask=false），G0目标仍有效（target=0、mask=true）；15完整终局、14次精确状态比较和7个双repeat组均保留。故本批为7源具备全部4类目标，另1源具备部分目标；不把后者写成模型技术失败，也不自行决定各视图是否接受。不推断raw-alias根因，不重采或重投影；见DATA_QUALIFICATION_NOTE.json。

完整终局包括{absolute_s300}支到达绝对s300、{early_success}支合法提前成功。{commit_description}非normal比较实际启动{len(non_normal)}支，其中候选替换分支{len(replacement_branches)}支、G0_old控制{len(old_controls)}支；实际标记与公共episode核对见branch_semantics，old控制不称为干预。未执行G0触发器。

实际entered：模型载入{n['policy_model_loads']}、采样{n['vla_sampling_calls']}、flow{n['flow_forward_calls']}、控制{n['env_steps']}、观测{n['observation_calls']}、reset{n['environment_reset_calls']}、初始化物理子步{n['initialization_physics_substeps']}。完整116项entered/returned/failed/incomplete及独立私有账本见INDEPENDENT_LEDGER_AUDIT.json；冻结caps检查={ledger['within_all116_caps']}，审计差异计数={json.dumps(audit_error_counts,ensure_ascii=False)}。Q/D/G0前向={n['critic_forward_calls']}/{n['D_forward_calls']}/{n['G0_forward_calls']}，动作梯度={n['action_gradient_calls']}、训练更新={n['training_updates']}、重试={n['retries']}、删除={n['deletions']}；诊断/采集成本未拼接成公共UUID成本账本，也不作部署成本或方法排名。

整组退出证据={exit_info['group_exit_proven']}；既有lifecycle恢复状态={restoration.get('status')}，保存状态中的holder数={exit_info['eight_holders_recorded']}。数据/成本发布是否在整组退出之后={scheduler['published_after_group_exit']}。用户在运行中明确要求8卡占用以防低于50%被停机，已从临时占卡启动时起覆盖原“整波全8holder停算”约束。正式并发仍为2，另启闲置卡holder并在新正式START时让卡；额外占卡/利用率核查单独记于OCCUPANCY_POLICY_OVERRIDE.json，不并入116正式账本。共享guard与formal.lock未改，未终止无关进程。临时holder全部退出证据={occupancy["all_started_holder_managers_have_saved_exit"]}，后续常驻holder快照数={occupancy["post_exit_baseline_holder_count"]}。时序条件已改变，不作可比吞吐结论。成功handoff原始poll次数仍null。

最终输出{storage['final_output_paths']}条路径、{storage['final_output_unique_inodes']}个独立inode、{storage['final_output_unique_inode_bytes']}字节（inode去重；partial硬链接不重复计样本）。保存的私有cache采样峰值、容量下界及存储缺项见SAVED_STORAGE_AUDIT.json。全系统峰值、项目quota、外部/unlinked临时写入、监测间超调、RSS/VRAM与实际物理IO仍未知。约1.148TB只是已知尺寸逻辑读取报价小计，严格上界null；实际保存时序见SAVED_TIMING_AUDIT.json，不宣称线性加速。

所有已启动源的成功、技术失败和缺项均保留；父源及每branch覆盖、Q/G0配对资格、源/UUID/严格载入证明及失败栈分别附JSON。旧14计算release不复用，本次未入额度不可复用。完成后停止，等待分析验收关闭；未自动下一批、训练、评测、安装或删除。door-lock直接mj_step的阶段计量另见INITIALIZATION_STAGE_AUDIT.json；本批风险仅按独立Batch3合同，未扩写为全500源容量承诺。
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
    release_ref=ref(W/'authorization/P11_A_COMMON_POOL_BATCH3_V1.json'),ack=ref(ack),report=ref(P/'REPORT.md'),
    evidence_manifest=ref(manifest),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    command_invocations=1,claims=claims,release_opportunity_consumed=True,unused_caps_reusable=False,no_retry=True,
    outer_result=outer,formal_group_exit_proven=exit_info['group_exit_proven'],restoration=restoration,
    saved_holder_count=exit_info['eight_holders_recorded'],user_occupancy_override=ref(P/'OCCUPANCY_POLICY_OVERRIDE.json'),original_all8_stop_preserved_entire_wave=False,post_override_baseline_holder_count=occupancy['post_exit_baseline_holder_count'],auxiliary_occupancy_operation_counts_known=False,resource_entered=n,resource_returned=returned,
    resource_failed=ledger['failed_units'],resource_incomplete_entered=ledger['incomplete_entered_units'],
    resource_counts_complete=not ledger['missing_or_corrupt_scopes'] and ledger['event_pairs']['incomplete']==0,
    all_observed_entries_have_terminal=ledger['event_pairs']['incomplete']==0,
    resource_entered_are_saved_lower_bounds=bool(ledger['missing_or_corrupt_scopes']),
    within_all116_caps=ledger['within_all116_caps'],audit_error_counts=audit_error_counts,
    actual_parent_starts=sum(p['branches_started']>0 for p in parents),actual_branch_starts=children,
    complete_outcomes=complete,all15_and14states_and4paired_targets=parent_candidates,branch_semantics=branch_semantics,
    data_qualification_note=ref(P/'DATA_QUALIFICATION_NOTE.json'),partial_target_parent_candidates=qualification['partial_target_parent_candidates_in_batch'],
    raw_exit_interpretation=exit_interpretation,technical_failures_in_saved_evidence=technical_failures_present,
    absolute_s300_outcomes=absolute_s300,legal_early_success_outcomes=early_success,
    full_C10_or_C5_tail_discard_and_H10_resume_branches=commit_full,
    terminal_at_or_before_commitment_end_without_H10_resample=commit_terminal,
    all_non_normal_comparison_branches_without_saved_H10_resume=without_saved_H10,
    source_coverage=[{k:p[k] for k in ('parent_key','source','device','branches_started','complete_outcomes','full_state_exact_comparisons','complete_repeat_groups','candidate_qualified_for_analysis','coverage_note','normal_complete_before_legal_cut')} for p in parents],
    existing_accepted_parent_count=16,new_accepted_parent_count=0,analysis_acceptance_pending=True,
    physical_equality_proven=None,B_participated=False,followup_computation_authorized=False,
    artifacts=[ref(p) for p in sorted(P.iterdir()) if p.is_file() and p!=manifest],
    delivery_interpretation='All started-source evidence retained; launcher completion is not coverage/qualification acceptance; costs are collection evidence only'))
print(json.dumps(dict(result=ref(result),report=ref(P/'REPORT.md'),manifest=ref(manifest),status=status),ensure_ascii=False),flush=True)
