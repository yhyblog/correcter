"""Independent CPU metadata review and immutable receipt; never runs collector."""
from pathlib import Path
from collections import Counter
import ast
import datetime
import hashlib
import json
import socket

ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang')
B=ROOT/'Corrector/sim_command/20260919'
TASK='A11_COMMON_POOL_REVISION_CPU_V2'
P=B/'results/A'/TASK
W=B/'work/A'/(TASK+'_r1')
def read(path): return json.loads(Path(path).read_text())
def ref(path):
    path=Path(path).absolute()
    raw=path.read_bytes()
    return dict(path=str(path),realpath=str(path.resolve()),
        sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))
def write(path,data):
    with Path(path).open('x') as f:
        json.dump(data,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
checks=[]
def check(name,ok,evidence):
    checks.append(dict(name=name,passed=bool(ok),evidence=evidence))
    if not ok: raise AssertionError(name)

quote=read(P/'RESOURCE_AND_STORAGE_QUOTE.json')
draft=read(P/'COMMON_POOL_DRAFT.json')
input_manifest=read(P/'INPUT_MANIFEST.json')
coverage=read(P/'POOL_COVERAGE_AND_GAPS.json')
restore=read(P/'RESTORE_FIELD_CONTRACT.json')
shards=read(P/'SYNTHETIC_SHARD_CROSSTAB.json')
release=read(B/'releases/P00_COMMON_POOL_REVISION_CPU_V2.json')
control=read(B/'CONTROL.json');board=read(B/'TASK_BOARD.json')
check('current_release_SHA',ref(B/'releases/P00_COMMON_POOL_REVISION_CPU_V2.json')['sha256']
    =='8f1ff56f06e5868eeb4c17adf66357b55aaf5a0ef5a552df26aa89ac1aa263d6','user-bound release')
check('current_CPU_task_still_published',
    control['revision']==38 and board['revision']==45 and
    control['active_common_pool_revision_preparation_release']=='releases/P00_COMMON_POOL_REVISION_CPU_V2.json'
    and control['mode']=='prepare' and not control['stop_requested']
    and not control['formal_gpu_runs_enabled']
    and all(x==0 for x in control['current_compute_limits'].values())
    and socket.gethostname()==release['owner_host'],'CONTROL38/BOARD45/host/zero')
check('builder_completed',read(W/'DESIGN_BUILD_RUN.json')['returncode']==0,'37 targeted checks recorded')
check('builder_source_identical_to_run',ref(W/'build_revision.py')['sha256']
    ==read(W/'DESIGN_BUILD_RUN.json')['script_sha256'],'exact CPU builder bytes')
for name in ('build_revision.py','finalize_revision.py'):
    tree=ast.parse((W/name).read_text())
    modules=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            modules.extend(a.name.split('.')[0] for a in node.names)
        elif isinstance(node,ast.ImportFrom):
            modules.append(node.module.split('.')[0])
    check('stdlib_AST:'+name,set(modules)<=
        {'pathlib','ast','copy','datetime','fractions','hashlib','json','collections','socket'},
        sorted(set(modules)))

# A separate enumerated decision schedule check, rather than reusing the builder formulas.
independent=[]
for reuse in (False,True):
    attempts=controls=samples=prefix=normal=Qsuffix=Gsuffix=0
    for cut in (5,55):
        for parent_number in range(250):
            attempts+=1;controls+=300
            decisions=list(range(0,300,10))
            samples+=len(decisions)+3;normal+=len(decisions)
            for family,commitment,number in [('Q',10,6),('G0',5,7 if reuse else 8)]:
                for branch_number in range(number):
                    attempts+=1
                    controls+=len(range(0,cut))+len(range(cut,300))
                    before=list(range(0,cut,10))
                    after=list(range(cut+commitment,300,10))
                    samples+=len(before)+len(after);prefix+=len(before)
                    if family=='Q':Qsuffix+=len(after)
                    else:Gsuffix+=len(after)
    row=dict(reuse=reuse,attempts=attempts,controls=controls,samples=samples,
        observations=controls+attempts,prefix_samples=prefix,
        source_samples=normal,Q_suffix_samples=Qsuffix,G0_suffix_samples=Gsuffix)
    independent.append(row)
    s=quote['scenarios'][int(reuse)]
    check('independent_enumerated_schedule:'+str(reuse),
        attempts==s['physical_attempts'] and controls==s['controls'] and samples==s['samples']
        and prefix==s['components']['prefix_samples']
        and Qsuffix==s['components']['Q_suffix_samples'] and Gsuffix==s['components']['G0_suffix_samples'],
        row)
    check('explicit_encoder_preprocessing:'+str(reuse),
        s['explicit_visual_feature_rows']==s['observations']+204806
        and s['policy_visual_forwards']==3*samples
        and s['policy_language_forwards']==samples
        and s['preprocessing']['explicit_padding_images_encoded']==0
        and s['preprocessing']['padded_image_tensors_created']==2*(samples+s['explicit_visual_feature_rows']),
        'padding tensor creation counted, padding encoded only in full sampler')
    check('byte_accounting:'+str(reuse),s['storage']['parts_bytes']['new_RGB_raw_pixels']
        ==s['observations']*691200
        and s['storage']['parts_bytes']['normal_demonstration_tokens_float32']==429509312512
        and s['storage']['selected_output_bytes']==sum(s['storage']['parts_bytes'].values())
        and s['storage']['compression_discount']==0,
        s['storage'])

terminal_table=[
 dict(case='complete_no_success_s300',last_observed_parent_state=300,
      observed_through_target=True,ever_success=False,success_at=None,
      technical_gap=False,absorbing_semantics_frozen=False,label=0,mask=True),
 dict(case='success_on_last_step_s300',last_observed_parent_state=300,
      observed_through_target=True,ever_success=True,success_at=300,
      technical_gap=False,absorbing_semantics_frozen=False,label=1,mask=True),
 dict(case='quota_stop_s299',last_observed_parent_state=299,
      observed_through_target=False,ever_success=False,success_at=None,
      technical_gap=True,absorbing_semantics_frozen=False,label=None,mask=False),
 dict(case='early_true_success_s120',last_observed_parent_state=120,
      observed_through_target=False,ever_success=True,success_at=120,
      technical_gap=False,absorbing_semantics_frozen=False,label=1,mask=True),
 dict(case='unknown_TimeLimit_s80',last_observed_parent_state=80,
      observed_through_target=False,ever_success=False,success_at=None,
      technical_gap=True,absorbing_semantics_frozen=False,label=None,mask=False),
 dict(case='missing_frame_no_success',last_observed_parent_state=300,
      observed_through_target=False,ever_success=False,success_at=None,
      technical_gap=True,absorbing_semantics_frozen=False,label=None,mask=False),
 dict(case='prospectively_defined_absorbing_failure',last_observed_parent_state=75,
      observed_through_target=False,ever_success=False,success_at=None,
      technical_gap=False,absorbing_semantics_frozen=True,label=0,mask=True)]
check('synthetic_endpoint_and_censor_table',
    terminal_table[1]['success_at']==300 and terminal_table[1]['label']==1
    and all(terminal_table[i]['label'] is None for i in (2,4,5)),
    'preassigned metadata table only; no environment/terminal function implementation')
write(P/'SYNTHETIC_TARGET_AND_VIEW_TABLES.json',dict(task_id=TASK,synthetic=True,
    terminal_cases=terminal_table,qualification='symbolic examples, no new absorbing terminal semantics granted to real task',
    views=[
        dict(case='normal_contiguous_tokens_original_action_terminal_unknown',
            LVM_eligible=True,D5_eligible=False,GAF_eligible=False,
            missing=['executed_action_mapping','terminal_target'],
            reason='terminal flags irrelevant to LVM; others not relaxed'),
        dict(case='normal_contiguous_tokens_original_action_executed5_known_terminal_unknown',
            LVM_eligible=True,D5_eligible=True,GAF_eligible=False,
            missing=['complete_GAF_target'],reason='D5 arrival window known; no complete negative outcome'),
        dict(case='normal_token_endpoint_missing',LVM_eligible=False,D5_eligible=None,GAF_eligible=None,
            missing=['token_t_plus10'],reason='cannot fabricate next token from PCA or model') ],
    planned_entered_completed_missing_example=dict(
        target='G0/fresh2/repeat1',planned=True,entered=True,completed=False,missing=True,
        outcome_complete=False,success_label=None,reason='synthetic timeout after entering',
        G0_valid_pair_repeat_ids=[0],G0_target_mask=False,
        incurred_cost_preserved=True,no_retry=True)))

case=read(P/'SYNTHETIC_CANDIDATE_LABELS.json')
complete=case['cases'][0]
check('G0_index_layers',len([x for x in complete['rows'] if x['logical_arm'].startswith('G0/')])==8
    and {x['repeat_id'] for x in complete['rows']}=={0,1}
    and len({x['physical_attempt_id'] for x in complete['rows']})==14,
    'threefresh x two repeats plus old x two; IDs not collapsed')
check('Q_pair_and_C5_C10_separation',complete['pair']==['Q/local_plus','Q/local_minus']
    and case['alias_examples'][2]['same_physical_outcome'] is False,'no raw generation/outcome confusion')
by_task=Counter((x['task_ordinal'],x['split']) for x in shards['synthetic_parent_design_rows'])
by_owner=Counter((x['owner_symbol'],x['split'],x['cut']) for x in shards['synthetic_parent_design_rows'])
check('independent_synthetic_allocation',all(by_task[(t,'train')]==8 and
    by_task[(t,'development')]==2 for t in range(50)) and all(
    by_owner[(h,'train',c)]==100 and by_owner[(h,'development',c)]==25
    for h in ('A','B') for c in (5,55)),dict(rows=500,cells=len(by_task)))
check('restore_no_overclaim',restore['passed_real_roundtrips']==0
    and not restore['observables_only_admits_gain_pair_G0']
    and restore['tolerance_policy']['physical_tolerance'] is None,
    'exact proposed state fields, unresolved closure blocks')
check('LVM_terminal_gate_independent',next(x for x in draft['method_views']
    if x['method']=='VLA-Corrector-adapted')['eligibility_independent_of_outcome_complete'],
    'B adapter confirmation still required')
check('no_current_execution_seed_or_shard',
    draft['not_frozen']['seeds'] is None and draft['not_frozen']['shards'] is None
    and all(v==0 for v in draft['current_real_counts'].values()),
    '130 counters0; all scheduled rows synthetic')
for x in input_manifest['files']:
    current=ref(x['path'])
    check('input_SHA:'+Path(x['path']).name,current['sha256']==x['sha256']
        and current['size_bytes']==x['size_bytes'],x)

final_checks=dict(task_id=TASK,at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    status='PASS',scope='independent schedule arithmetic, synthetic target/view/owner tables, narrow static identities',
    tests=checks,check_count=len(checks),no_real_operations=True,
    independent_schedule_totals=independent)
write(P/'FINAL_CPU_CHECKS.json',final_checks)
s0,s1=quote['scenarios']
report=f"""# A11_COMMON_POOL_REVISION_CPU_V2 — CPU_READY

CONTROL38 / TASK_BOARD45、A主机和用户指定release SHA已核对，新ACK已写。独立五项主交付已完成；本轮仅协议、静态字段、合成表和参数报价。

Q改为a0/local±各2repeat，一份独立平滑随机方向、自身对称半径；G0为3fresh各2对old2，fresh0只共享a0生成。目标固定原parent绝对s300含末步。gain/pair/G0需full_state_verified及双方/四臂两个预定repeat齐全；零方向/别名/缺repeat掩码和源级损失不变。

500父源仅覆盖设计：全50任务各8/2；train各任务各主机各cut2，dev跨50任务各主机各cut25，parent不拆。LVM终局资格独立分流；联合全节点退出后释放预约，数据发布另屏障。真实ID、seed、shard和collector/logger均未产生。

| 全部到达300的报价场景 | 无复用（主） | normal=G0_old0条件复用 |
|---|---:|---:|
| 物理attempt | {s0['physical_attempts']} | {s1['physical_attempts']} |
| 控制步 | {s0['controls']} | {s1['controls']} |
| 完整采样 / flow | {s0['samples']} / {s0['flow_forwards']} | {s1['samples']} / {s1['flow_forwards']} |
| policy视觉 / 语言 | {s0['policy_visual_forwards']} / {s0['policy_language_forwards']} | {s1['policy_visual_forwards']} / {s1['policy_language_forwards']} |
| 显式视觉特征 | {s0['explicit_visual_feature_forwards']} | {s1['explicit_visual_feature_forwards']} |
| 规划输出 / 峰值 TiB | {s0['storage']['selected_output_TiB']:.3f} / {s0['storage']['planning_peak_TiB']:.3f} | {s1['storage']['selected_output_TiB']:.3f} / {s1['storage']['planning_peak_TiB']:.3f} |

每sample三视觉（含两填充）加一语言；预处理/实图/显式特征分计。7500/7000是设计场景，不是可执行完整caps；初始化/状态核验等另列，硬存储上限与实际有效样本数未知。旧4500报价不作新预算。

静态发现get_env_state仅qpos/qvel，_get_obs会改历史；已列MuJoCo3.6/MetaWorld3.0/Gym1.2.3完整状态字段及顺序，但没有真实roundtrip证明。其余49任务初始化cap逐项未知；必须先闭合字段/预算，再在已计划parent验证。项目quota/剩余可用配额仍unknown，定向statvfs不能代替预留容量。共享缓存/记录动作回放/无损编码无未证节省。

初轮37项检查和本次{len(checks)}项定向复核通过。全部130项真实受限操作计数0；模型/环境/投影/holder/真实launcher/claim/训练/安装/删除/大权重hash均0。既定算法/阈值与Velocity决定保持；500父源不保证训练充分。旧包、B、CONTROL/BOARD未改。

结果交分析验收；采集仍未授权，不自动实现或进入下一阶段。细表见本目录五项主文件、RESTORE_FIELD_CONTRACT、TASK_INITIALIZATION_GAPS、合成表和DECISIONS_ALIGNMENT。
"""
with (P/'REPORT.md').open('x') as f:f.write(report)

# Seal direct evidence only. Never follow nested references to large weights or inventories.
evidence_paths={str(Path(x['path']).absolute()) for x in input_manifest['files']}
evidence_paths.update(str(x.absolute()) for x in P.iterdir() if x.is_file())
evidence_paths.update(str(x.absolute()) for x in W.iterdir() if x.is_file())
evidence_paths.update(str(x.absolute()) for x in (W/'authorization_snapshot').iterdir())
evidence_paths.add(str(B/f'receipts/A/{TASK}_ACK.json'))
files=[ref(path) for path in sorted(evidence_paths)]
manifest=dict(schema='CPU-revision-evidence/1',task_id=TASK,
    at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=files,file_count=len(files),
    exclusions=['self and RESULT to avoid circular hashes','later queue delivery receipt and terminal audit'],
    inherited_reference_rule='other49 task source SHAs are accepted-manifest references, not live per-file verification; never recursively follow weights',
    current_computation_counters={k:0 for k in release['limits']},all_created_outputs_retained=True)
write(P/'EVIDENCE_MANIFEST.json',manifest)
artifacts=[ref(x) for x in sorted(P.iterdir()) if x.is_file()]
result=dict(campaign_id=release['campaign_id'],task_id=TASK,task_revision=1,owner='A',
    host=socket.gethostname(),executor_session_id='01a0b91f-7443-71b1-915d-6cdb6d6a1a13',
    status='CPU_READY',outcome='protocol_revision_and_requote_complete_pending_analysis',
    completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    release=ref(B/'releases/P00_COMMON_POOL_REVISION_CPU_V2.json'),
    ACK=ref(B/f'receipts/A/{TASK}_ACK.json'),control_revision=38,task_board_revision=45,
    report=ref(P/'REPORT.md'),evidence_manifest=ref(P/'EVIDENCE_MANIFEST.json'),
    artifacts=artifacts,artifact_count=len(artifacts),manifest_file_count=len(files),
    scope='CPU design/fields/parameter quote and synthetic cross tables; not collector implementation or collection approval',
    decisions_alignment=ref(P/'DECISIONS_ALIGNMENT.json'),
    checks=dict(initial=37,final=len(checks),status='PASS'),
    design_totals=dict(parents=500,valid_sources=None,Q_candidates=3,Q_repeats=2,
        G0_fresh=3,G0_repeats=2,absolute_target_state=300,
        no_reuse_attempts=7500,conditional_reuse_attempts=7000,
        samples=[226500,211500],policy_visual=[679500,634500],
        no_training_sufficiency_claim=True),
    unresolved_before_collection=['full-state field closure and actual proof',
        'other49 initialization/restore caps','project quota and hard serialization/IO limits',
        'actual source/seed/shard identities and finite implementation release',
        'B view/sidecar consumption and later component training recipe'],
    current_actual_counts={k:0 for k in release['limits']},
    actual_candidate_generations=0,actual_action_projections=0,
    real_seed_shard_claim_created=False,collector_or_logger_implemented=False,
    old_outputs_control_board_B_modified=False,
    future_compute_authorized=False,automatic_next_stage=False,
    delivery_target='01a0b91f-355f-7cd1-ae36-412500534ffb')
rp=B/f'receipts/A/{TASK}_RESULT.json'
write(rp,result)
print(json.dumps(dict(status='CPU_READY',result=ref(rp),report=ref(P/'REPORT.md'),
    manifest=ref(P/'EVIDENCE_MANIFEST.json'),artifact_count=len(artifacts),
    manifest_files=len(files),final_checks=len(checks)),ensure_ascii=False))
