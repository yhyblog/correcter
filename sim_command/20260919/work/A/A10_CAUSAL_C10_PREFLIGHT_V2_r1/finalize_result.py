"""Finalize this one command from saved receipts; no new experiment/probe."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
T='A10_CAUSAL_C10_PREFLIGHT_V2';RID='P10_A_CAUSAL_C10_PREFLIGHT_V2'
W=B/'work/A'/(T+'_r1');O=B/'results/A'/T;R=B/'results/A/P10_CAUSAL_C10_V2_launcher_runs'/(T+'_r1_A_wave10')
def read(p):return json.loads(p.read_text())
def ref(p):return dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),size_bytes=p.stat().st_size)
def put(p,x):
    with p.open('x') as f:f.write(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
cmd=read(W/'COMMAND_RESULT.json');launch=read(R/'LAUNCH_RESULT.json');audit=read(O/'INDEPENDENT_LEDGER_AUDIT.json')
coverage=read(O/'BRANCH_COVERAGE.json');holder=read(O/'TIMING_AND_HOLDER_AUDIT.json');rgb=read(O/'SAVED_RGB_ARRAY_AUDIT.json');man=read(O/'RUNTIME_MANIFEST_AUDIT.json')
assert cmd['real_command_attempts']==1 and cmd['claim_exists']
assert audit['all_within_caps'] and audit['counts_complete'] and audit['agrees_with_launcher']
assert coverage['completed_C10_branches']==launch['completed_C10_branches']
assert man['status']=='PASS'
for c in coverage['branches']:
    assert c['all_real_events'] is not False and c['causal_identity_consistent'] is not False and c['causal_event_ids_contiguous']
completed=coverage['completed_C10_branches'];counts=audit['total_entered'];started=[x['branch'] for x in coverage['branches'] if x['process_started']]
if launch['status']!='complete':status='TECHNICAL_FAILURE'
elif completed==['Post','Velocity']:status='FINITE_ENGINEERING_COMPLETE'
else:status='FINITE_ENGINEERING_PARTIAL_COVERAGE'
numeric={};identity={}
for branch in started:
    d=R/branch
    identity[branch]={n:read(d/n) if (d/n).exists() else None for n in ['policy_device_type.json','policy_device.json','policy_loader.json']}
    path=d/(branch+'_numeric.json');q=read(path) if path.exists() else None
    g=read(d/'G0_outputs.json') if (d/'G0_outputs.json').exists() else None
    numeric[branch]=dict(G0=g,numeric=q,prefix_comparison=read(d/'PREFIX_COMPARISON.json') if (d/'PREFIX_COMPARISON.json').exists() else None,
        deployment_sampling_calls=1 if branch=='Post' else 2,hidden_state_equivalence_claim=False)
put(O/'NUMERIC_AND_DEVICE_SUMMARY.json',dict(branches=numeric,identity=identity,interpretation='one fixed development source; not success rate/ranking',
    local_or_member_Q_decreases_retained=True,Q_acceptance_gate=False,CPU_audit_model_calls=0))
pairs=dict(parent=audit['parent']['entered_events'])
for branch,row in audit['branches'].items():
    for scope in ['numeric','initialization','graphics']:pairs[branch+'_'+scope]=dict(entered=row[scope]['entered_events'],terminal=row[scope]['terminal_events'],failed=len(row[scope]['failed']),unresolved=len(row[scope]['unresolved']))
report=[f'{T}：{status}，待分析验收关闭。',
    f'冻结命令执行 1 次，claim 1；退出码 {cmd["returncode"]}，总耗时 {cmd["elapsed_seconds"]:.3f}s。实际启动 {started}；completed_C10_branches={completed}。阶段覆盖来自实际事件和分支回执。',
    '| 分支 | 合法 cut | C10 返回步数 | 丢尾 | H20 恢复/余量 | 真实 G0 / 强制干预 |',
    '|---|---|---|---|---|---|']
for c in coverage['branches']:
    report.append(f'| {c["branch"]} | {c["legal_cut_reached"]} | {c["C10_steps_actual"]} | {c["C10_tail_discarded"]} | {c["H20_restored"]} / {c["H20_remaining"]} | {c["real_G0_trigger"]} / {c["forced_engineering_intervention"]} |')
report+=['',f'实际 VLA {counts["vla_sampling_calls"]} / flow {counts["flow_forward_calls"]} / 控制 {counts["env_steps"]} / RGB {counts["rgb_readback_calls"]}；模型初始化 {counts["model_initializations"]}、encoder {counts["encoder_forward_calls"]}、D {counts["D_forward_calls"]}、G0 {counts["G0_forward_calls"]}、Q ensemble {counts["objective_forward_calls"]}/成员 {counts["critic_forward_calls"]}、动作梯度 {counts["action_gradient_calls"]}。初始化 native reset {counts["environment_reset_calls"]}、reset_model {counts["reset_model_calls"]}、初始化物理子步 {counts["initialization_physics_substeps"]}，控制子步 {counts["policy_physics_substeps"]}。111 项独立 entered/returned 核对与 launcher 一致，均在上限内；父/数值/初始化/graphics 私有账本分别核算。']
for branch,item in numeric.items():
    g=item['G0'];q=item['numeric'];prefix=item['prefix_comparison']
    if g:report.append(f'{branch} G0 两成员={g["member_scores"]}，均值={g["mean"]:.9f}，阈值严格 >{g["threshold"]}；成熟残差只作诊断。')
    if q:report.append(f'{branch} Q 均值增量={q["score"]["mean_gain"]:.9f}；约束检查={q["audit"]["status"]}，独立自身半径、无 Q 接受门、模型冻结；单成员/局部下降保留。')
    if prefix:report.append(f'Velocity 可观测 prefix 一致={prefix["observable_prefix_matches"]}；隐藏状态等价仍不作声明。')
for c in coverage['branches']:
    if not c['completed_C10_and_H20']:report.append(f'{c["branch"]} 未覆盖原因：{c["missing_stage_reason"]}。缺失阶段不作为数值或方法失败标签。')
report+=[f'已保存 {len(rgb["images"])} 张 RGB 的 CPU 无损 PNG，均从本次已存 NPZ 编码并做逐字节回读比较；新增 render 0。raw 尾部/噪声核对见 SAVED_RGB_ARRAY_AUDIT.json；完整 D 预测、transition、G0、P/V 数组、设备与 strict loader 证据见 manifest。',
    f'全组退出状态={launch.get("process_family_cleanup",{}).get("status")}，occupancy={launch.get("restoration",{}).get("status")}，已恢复 holder {holder["holder_count_restored"]}/8；没有中途启用闲置 holder。manager 日志只表示管理事件时间，成功 GPU 空闲轮询原始次数仍 null，未补探针。',
    '真实事件 synthetic=false。未重跑/换 seed/修补运行包；安装、训练、删除 0，B 不参与。旧九份计算 release 不复用，本次命令机会已消费，剩余额度作废；请分析关闭本 release。此为有限工程预检，不是任务成功率、触发有效性、方法排名或部署成本优势样本；Post1/Velocity2 部署口径保持。']
put(O/'REPORT.md','\n\n'.join(report[:2])+'\n\n'+'\n'.join(report[2:6])+'\n'+'\n\n'.join(report[6:])+'\n')
files=[ref(p) for root in [R,O,W] for p in sorted(root.rglob('*')) if p.is_file() and p.name not in ['EVIDENCE_MANIFEST.json','QUEUE_MESSAGE.txt','QUEUE_DELIVERY.json','POST_AUDIT_RUN.json']]
put(O/'EVIDENCE_MANIFEST.json',dict(task_id=T,at_utc=datetime.now(timezone.utc).isoformat(),files=files,
    scopes=dict(runtime=str(R),delivery=str(O),command_and_authorization=str(W)),all_products_retained=True,
    exclusions=['this manifest','RESULT receipt','POST_AUDIT_RUN after completion','queue delivery after completion'],new_hardware_queries=0,large_weight_rehashes_by_auditor=0))
artifact_paths=[p for p in O.iterdir() if p.is_file() and p.suffix!='.png']+[p for p in W.iterdir() if p.is_file() and p.name in ['COMMAND_STARTED.json','COMMAND_PROCESS.json','COMMAND_RESULT.json','command.stdout.log','command.stderr.log']]
artifact_paths += [p for p in R.iterdir() if p.is_file()]
for branch in started:artifact_paths += [p for p in (R/branch).iterdir() if p.is_file() and p.suffix in ['.json','.jsonl']]
claim=B/'results/A/P10_CAUSAL_C10_V2_release_claims'/(RID+'.json')
result=dict(campaign_id='corrector-sim-20260919',task_id=T,revision=1,owner='A',hostname='trial-303224955-trialrun-303224955-worker-0',status=status,at_utc=datetime.now(timezone.utc).isoformat(),
    ACK=ref(B/'receipts/A'/(T+'_ACK.json')),release=ref(B/'releases'/(RID+'.json')),claim=ref(claim),command_invocations=1,claim_count=1,
    actual_branch_attempts=counts['simulator_attempts'],raw_exit_code=cmd['returncode'],elapsed_seconds=cmd['elapsed_seconds'],
    planned_branches=['Post','Velocity'],actually_started_branches=started,completed_C10_branches=completed,per_branch_coverage=coverage['branches'],
    resource_entered=counts,resource_returned=audit['total_returned'],counts_complete=audit['counts_complete'],within_caps=audit['all_within_caps'],private_ledger_events=pairs,
    failures=[dict(branch=x['branch'],primary=x['failure'],cleanup=x['cleanup_failures']) for x in coverage['branches'] if x['failure'] or x['cleanup_failures']],
    process_family_cleanup=launch.get('process_family_cleanup'),holder_restoration=launch.get('restoration'),holder_count_restored=holder['holder_count_restored'],timing=holder['timing'],
    images_saved=len(rgb['images']),runtime_manifest_verified_files=man['checked_files'],evidence_manifest_files=len(files),artifacts=[ref(p) for p in sorted(set(artifact_paths))],
    release_consumed=True,release_closure_by_analysis_pending=True,remaining_caps_reusable=False,automatic_retry=False,old_releases_reused=False,
    scientific_interpretation=dict(success_rate_sample=False,ranking=False,paired_performance=False,full_hidden_state_equivalence=False,MT50_training_completed=False,deployment_sampling=dict(Post=1,Velocity=2)),
    postrun_audit=dict(saved_files_only=True,extra_GPU_NVML_EGL_queries=0,extra_model_calls=0,extra_render=0,large_weight_rehashes=0),
    shared_installations=0,daemon_restarts=0,training_updates=0,deletions=0,B_participated=False,public_interface_modified=False,next_action='await analysis acceptance and release closure; no automatic next phase')
receipt=B/'receipts/A'/(T+'_RESULT.json');put(receipt,result)
for row in result['artifacts']+files:
    p=Path(row['path']);assert ref(p)==row
print(json.dumps(dict(status=status,RESULT=ref(receipt),REPORT=ref(O/'REPORT.md'),LAUNCH_RESULT=ref(O/'LAUNCH_RESULT.json'),EVIDENCE_MANIFEST=ref(O/'EVIDENCE_MANIFEST.json'),
    artifact_refs=len(result['artifacts']),evidence_files=len(files),runtime_manifest_files=man['checked_files'],completed_C10_branches=completed,restored_holders=holder['holder_count_restored']),ensure_ascii=False))
