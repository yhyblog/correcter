"""Review and seal the five CPU design deliverables; no executable collection."""
from pathlib import Path
import ast
import datetime
import hashlib
import json

R=Path('/mnt/bn/arnold-recommend/yaohaoyang')
B=R/'Corrector/sim_command/20260919';T='A11_COMMON_POOL_DESIGN_CPU_V1'
P=B/'results/A'/T;W=B/'work/A'/f'{T}_r1'
def read(p):return json.loads(Path(p).read_text())
def ref(p):
    p=Path(p);assert p.stat().st_size<3*1024*1024
    d=p.read_bytes();return dict(path=str(p),sha256=hashlib.sha256(d).hexdigest(),size_bytes=len(d))
def put(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def replace_design(name,obj):
    before=W/'pre_final_review';before.mkdir(exist_ok=True)
    old=P/name
    with (before/name).open('xb') as f:f.write(old.read_bytes())
    old.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

draft=read(P/'COMMON_POOL_DRAFT.json');q=read(P/'RESOURCE_AND_STORAGE_QUOTE.json')
config=read(B/'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1/config/CONFIG.json')
coverage=read(P/'POOL_COVERAGE_AND_GAPS.json')
for row in coverage['rows']:
    row['normal_demonstrations']['executed_action_mapping']='unknown: dataset.action may exceed [-1,1]; collection-time scaling/clamp and exact execution identity require later narrow metadata binding, not an implicit conversion'
for view in draft['method_views']:
    if view['method'] in ['D5','GAF-v1-adapted']:
        view['existing_demo_eligibility_gate']='actual executed-action mapping and legal contiguous windows must be verified; GAF also needs complete target-compatible terminal horizon. Raw demonstration metadata alone does not admit these rows.'
    if view['method']=='VLA-Corrector-adapted':
        view['action_feature_binding']='use B original action_t representation with its frozen normalizer; do not silently reinterpret as bounded execution controls'
replace_design('POOL_COVERAGE_AND_GAPS.json',coverage)
draft['optional_velocity_logging_memo']=dict(status='NOT_SELECTED_NOT_IMPLEMENTED_NOT_EXECUTED',
    scope='only if a later already-planned guided call is independently released; no diagnostic-only replay',
    active_clean_payload_quote_bytes=98624,tensor_exports_upper=32,small_CPU_probability_copies=6,
    scalar_exports_separate=dict(parameter='S_scalar',proposed_upper_per_guided=9,
        basis='at most tau/time/dt each once at each of3 injection stages if export is necessary; reuse CPU scalars where already present; actual dtype/site binding not frozen',
        included_in_32_tensor_exports=False),
    full_clean_logging_selected=False,extra_independent_final_guided_Q_selected=False,
    independent_final_guided_Q=None,actual_x_next='actual Euler output only, never regenerated for logging',
    synchronization_and_peak_staging_unknown=True,model_gradient_sampling_extra_for_logging=0,
    zero_increment_model_calls_does_not_authorize_running_any_guided_call=True)
q['optional_velocity_logging_memo']=draft['optional_velocity_logging_memo']
q['worked_upper_example']['state_normalizer_transforms_upper']='one per actual observation/context request; up to render_observation_readbacks plus demo views; exact future adapter batching pending'
q['initialization_and_restore']['graphics_auxiliary_reference_per_fresh_worker']={
    k:v for k,v in config['native']['graphics_caps'].items()
    if k not in ['render_calls','rgb_readback_calls','mujoco_scene_updates']}
q['initialization_and_restore']['graphics_scaling_scope']='reference mapping/context caps multiply by newly created graphics worker/context; render/readback/scene updates scale by actual observations and extra restore validation; not runtime-measured across MT50'
q['minimal_collector_validation_quote']['VLA_model_loads_cold_process_scenario']=5
q['minimal_collector_validation_quote']['encoder_model_weights']='same pi05 vision tower proposed, no extra learned checkpoint; exact sharing/loader identity needs later implementation review'
q['minimal_collector_validation_quote']['full_terminal_validation']='not covered by short70-control check; require label-mask/true endpoint gate within first already-budgeted complete parent under a new collection release before expansion'
parts=q['storage']['selected_storage_parts_bytes']
old=parts.pop('raw50_noise_and_event_reservation_per_sample')
parts['raw50_noise_and_sample_journal_reservation_64KiB_per_sample']=q['worked_upper_example']['VLA_samples']['total']*65536
q['storage']['total_selected_output_bytes']=sum(parts.values())
q['storage']['journal_storage_estimate_limit']='64KiB/sample and4KiB/control are planning reservations, not measured serialized maxima; coalesced physical count blocks may be used, but all entered costs must survive. Extra init/feature/failure journals and filesystem headers require allowance before release.'
q['storage']['unpriced_allowances']=['initialization and explicit-feature event journals','actual snapshot serialization beyond1MiB estimate','failure/quarantine outputs','filesystem/container headers']
q['storage']['planning_safety_allowance_fraction']=.10
q['storage']['planning_output_bytes_with10pct_allowance']=int(q['storage']['total_selected_output_bytes']*1.1+.999999)
q['storage']['planning_peak_disk_bytes_example']=q['storage']['planning_output_bytes_with10pct_allowance']+q['storage']['peak']['writer_buffer_2_workers_one301frame_episode_RGB_each']+q['storage']['peak']['extra_weight_cache_bytes_example']
q['storage']['peak']['limit']='10% allowance is an estimate, not a guaranteed cap; future release requires actual serialization/cold-init bounds and project quota reservation'
replace_design('COMMON_POOL_DRAFT.json',draft)
replace_design('RESOURCE_AND_STORAGE_QUOTE.json',q)
put(W/'DESIGN_REFINEMENTS.json',dict(
    original_outputs_retained='pre_final_review/',
    changes=['separate optional scalar exports from32 tensor exports; current guided count0',
        'explicit inherited per-worker graphics mapping/cleanup multipliers; no new hardware query',
        'cold model loads and missing real terminal validation gate for proposed collector check',
        'explicit unknown demonstration raw-to-executed action mapping; no implicit clip or automatic GAF admission',
        'sample/noise journal reservation increased8KiB->64KiB,10% planning allowance plus staging/caches; not a guaranteed disk cap'],
    previous_sample_storage_reservation=old,collector_or_logger_code_implemented=False))

c=read(B/'CONTROL.json');board=read(B/'TASK_BOARD.json')
release=read(B/'releases/P00_COMMON_POOL_DESIGN_CPU_V1.json');ack=read(B/'receipts/A'/f'{T}_ACK.json')
assert c['mode']=='prepare' and c['active_common_pool_design_preparation_release']=='releases/P00_COMMON_POOL_DESIGN_CPU_V1.json'
assert not c['formal_gpu_runs_enabled'] and not c['active_compute_task_ids']
assert all(x==0 for x in c['current_compute_limits'].values())
assert next(x for x in board['tasks'] if x['id']==T)['status']=='ready'
assert ref(B/'releases/P00_COMMON_POOL_DESIGN_CPU_V1.json')['sha256']==ack['release']['sha256']
coverage=read(P/'POOL_COVERAGE_AND_GAPS.json');shards=read(P/'COLLECTION_SHARDS_DRAFT.json')
assert len(coverage['rows'])==50 and len({x['environment_task'] for x in coverage['rows']})==50
assert {x['environment_id'] for x in coverage['rows']}==set(range(50))
assert sum(x['normal_demonstrations']['episodes'] for x in coverage['rows'])==2500
assert sum(x['normal_demonstrations']['frames'] for x in coverage['rows'])==204806
assert len({i for x in coverage['rows'] for i in x['language_task_indices']})==49
assert sum(x['historical_train600']['parent_count'] for x in coverage['rows'])==600
assert sum(x['existing_train_development_trajectory_index']['all_indexed_segments'] for x in coverage['rows'])==1300
assert not shards['sources'] and shards['real_seed_list'] is None
assert all(v is None for v in draft['frozen_execution'].values())
assert all(v==0 for v in draft['actual_counts'].values())
assert q['worked_upper_example']['physical_attempts']==4500
assert q['worked_upper_example']['VLA_samples']['total']==136000
assert q['worked_upper_example']['controls']['total']==1350000
assert draft['fixed']['G0_label_commitment']==5 and draft['fixed']['C_Q']==10
assert not draft['optional_velocity_logging_memo']['extra_independent_final_guided_Q_selected']
assert q['worked_upper_example']['optional_velocity_guided_calls']==0
source_manifest=read(P/'INPUT_MANIFEST.json')
for row in source_manifest['files']:
    assert ref(row['path'])['sha256']==row['sha256'],row['path']
for s in [W/'write_design.py',Path(__file__)]:
    tree=ast.parse(s.read_text())
    roots=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):roots.extend(x.name.split('.')[0] for x in n.names)
        elif isinstance(n,ast.ImportFrom):roots.append((n.module or '').split('.')[0])
    assert set(roots)<={'pathlib','collections','hashlib','json','math','ast','datetime'}
required=['POOL_COVERAGE_AND_GAPS.json','COMMON_POOL_DRAFT.json','FIELD_VIEW_MATRIX.md',
          'COLLECTION_AND_REPLAY_PROTOCOL.md','COLLECTION_SHARDS_DRAFT.json','RESOURCE_AND_STORAGE_QUOTE.json']
assert all((P/x).stat().st_size>0 for x in required)
put(P/'FINAL_CPU_CHECKS.json',dict(status='PASS',scope='small metadata joins, required design fields and integer quotation arithmetic; no collector fixture or runtime test suite',
    task_id=T,environment_rows=50,normal_demos=2500,language_indices=49,historical_rows=1300,
    input_file_SHAs_verified=len(source_manifest['files']),real_seeds_and_shards_frozen=False,
    public_v1_and_B_contracts_unchanged=True,all_runtime_actuals_zero=True,
    current_CONTROL_revision=c['revision'],current_BOARD_revision=board['revision'],
    no_environment_or_payload_probe=True,collector_logger_implemented=False,
    production_blockers=['quantities/IDs/seeds/target-completion rules','full-state/comparability and49 task-specific init caps',
        'new collector/sidecar/feature binding and first complete-parent endpoint check','project storage quota and explicit A/B releases']))

body=f'''A11_COMMON_POOL_DESIGN_CPU_V1 revision1：CPU_READY，五项设计与报价已完成，待分析冻结。当前计算全0；A11/B11实际采集仍planned。

50个实际环境已逐项映射，每环境现有50示范；共2500 episode/204806帧。push-back/push共用语言index40，49语言索引不替代50环境。已有示范含RGB/state/action/reward/success的元数据证据，但独立terminated/truncated与末next未知；历史700 prefix＋600 a0 repeat0 suffix独立列出，train600不补采，未读held轨迹。

推荐报价稿：每任务8 train＋2 development，共500父源；每父源一个结果无关的预定cut，在5/55交替分配；Q采用a0＋一个独立普通重规划候选，各2后缀，另给G0 old/fresh5各2后缀。所有数量/candidate/repeat/真实seed均未冻结；合法cut不足不补源，不依赖五任务G0报警。normal与a0、G0五步与Q十步目标分开；无Post/Velocity新候选或扫参，额外最终guidedQ保持null。

| 项目 | 冷独立policy回放的报价情形（不是授权） |
|---|---:|
| 父源/候选后缀物理attempt | 500＋4000＝4500 |
| 真实控制步上界情形 | 1,350,000，其中prefix回放120,000 |
| 完整VLA / flow | 136,000 / 1,360,000 |
| RGB/真实观测 | 1,354,500 |
| 额外共享视觉提取（含原示范） | 1,559,306；同签名只计一次 |
| Q/D/G0/梯度/训练 | 推荐原始采集均0，组件训练另报价 |
| 主体存储估计 | {q['storage']['total_selected_output_bytes']:,} B，约{q['storage']['total_selected_output_bytes']/1024**4:.3f} TiB |
| 含10%规划余量、双worker暂存/双主机权重cache的峰值估计 | 约{q['storage']['planning_peak_disk_bytes_example']/1024**4:.3f} TiB；不是实测硬上界或项目配额 |

shelf-place已验收的每次冷入口52 native reset/104 reset_model/26000初始化子步单独报价；其他49任务的对应上界unknown，不能直接乘成全MT50正式caps。通用snapshot未证，回放不当免费restore，不将可观测相等称隐藏状态等价。gain/pair/G0比较资格须先冻结；预算截尾/技术失败/未知终局不标0。

共享原始池的D5/G0/Q、LVM正常token cosine与GAF-v1 MSE视图已列字段矩阵和历史初始化差异。public v1不改；新增repeat/target/mask/恢复证据走SHA sidecar，B消费与collector尚待实现。分片草案不含真实源/seed/claim；同parent全归一个owner，明确幂等、整组退出、两端发布屏障及未来联合wave条件。

最小新collector验收也仅报价：5物理attempt/70controls/12采样120flow/75RGB，初始化另计；不代表完整终局或50任务通过。真实完整标签需在后续已计划首个完整parent中另设验收门。Velocity active-clean只留待以后已计划guided调用，32张量导出/6CPU拷贝之外另列scalar导出，当前不实现。

分析待定：数量和cut/candidate/repeat/seed；完整终局时域与标签规则；恢复/比较标准与各任务初始化caps；特征/训练初始化、项目空间额度及显式A/B release。现只做小元数据/引用/算术检查，未实现collector/logger、未跑硬件/模型/环境/holder/launcher/claim/安装/训练/删除或大权重hash。五项主交付、字段矩阵和输入SHA见本目录；旧回执与B未修改。
'''
with (P/'REPORT.md').open('x') as f:f.write(body)

paths={}
for folder in [P,W]:
    for x in sorted(folder.rglob('*')):
        if x.is_file() and x.name not in ['EVIDENCE_MANIFEST.json','QUEUE_MESSAGE.txt','QUEUE_DELIVERY.json']:
            paths[str(x)]=ref(x)
for item in source_manifest['files']:paths[item['path']]=item
manifest=dict(task_id=T,revision=1,files=list(paths.values()),file_count=len(paths),
    note='all new design/evidence plus selected small input files; no model/data payload refs followed; excludes self and later RESULT/queue')
put(P/'EVIDENCE_MANIFEST.json',manifest)
artifacts=[ref(x) for x in sorted(P.iterdir()) if x.is_file()]
artifacts.extend(ref(x) for x in [W/'write_design.py',W/'finalize_design.py',W/'DESIGN_BUILD_RUN.json',W/'DESIGN_REFINEMENTS.json'])
result=dict(campaign_id=ack['campaign_id'],task_id=T,revision=1,owner='A',hostname=ack['hostname'],session_id=ack['session_id'],
    status='CPU_READY',outcome='common_pool_design_and_parameterized_quote_complete_pending_analysis',
    started_at_utc=ack['at_utc'],finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    ACK=ref(B/'receipts/A'/f'{T}_ACK.json'),release=ack['release'],
    CONTROL_revision_start=37,CONTROL_revision_finish=c['revision'],TASK_BOARD_revision_start=44,TASK_BOARD_revision_finish=board['revision'],
    artifacts=artifacts,artifact_count=len(artifacts),evidence_manifest=ref(P/'EVIDENCE_MANIFEST.json'),manifest_file_count=len(paths),
    report=ref(P/'REPORT.md'),required_five_deliverables_complete=True,
    findings=dict(environments=50,demos=2500,language_indices=49,historical_segments_separate=1300,train600_recollect=False,
        new_source_recommendation=500,source_ids_frozen=False,seed_ids_frozen=False,candidate_or_repeat_counts_frozen=False,
        quotation_attempts=4500,quotation_VLA=136000,quotation_flow=1360000,quotation_control_steps=1350000,
        selected_storage_estimate_bytes=q['storage']['total_selected_output_bytes'],project_quota=None,
        restoration_equivalence_proven=False,all50_runtime_initialization_caps_frozen=False,
        independent_final_guided_Q=None),
    actual_resource_counts={k:0 for k in release['limits']},
    collector_or_logger_implemented=False,real_seed_shard_or_release_created=False,
    historical_held_payloads_opened=0,weight_or_raw_trajectory_payloads_opened=0,
    old_receipts_modified=False,public_v1_modified=False,B_modified=False,
    holder_queries_or_changes=0,holder_restoration_required=False,
    future_compute_authorized=False,actual_A11_B11_collection='planned_not_released',
    next_action='queue the new CPU design receipt for analysis decisions; no automatic implementation, collection or training')
rp=B/'receipts/A'/f'{T}_RESULT.json';put(rp,result)
message=f'''A11_COMMON_POOL_DESIGN_CPU_V1 revision1 CPU_READY，五项CPU设计/参数化报价提交，等待分析冻结。
RESULT {rp}
SHA256 {ref(rp)['sha256']}
REPORT {P/'REPORT.md'}
SHA256 {ref(P/'REPORT.md')['sha256']}
EVIDENCE_MANIFEST {P/'EVIDENCE_MANIFEST.json'}
SHA256 {ref(P/'EVIDENCE_MANIFEST.json')['sha256']}
{len(artifacts)}产物引用/{len(paths)}manifest文件。50实际任务逐项有50示范，push-back/push共享语言index40；历史700prefix+600a0 suffix单列，旧train600不补采。
推荐而未冻结：每任务8train+2dev=500父源，各1个预定5/55cut；Q=a0+独立普通计划，各2repeat；G0 old/fresh5各2repeat。源/cut不靠五任务G0报警，normal/a0与G0五步/Q十步不混，无默认13x4。独立policy回放全满额情形4500物理attempt、1350000controls、136000采样/1360000flow；原始采集Q/D/G0/梯度0。主体存储约{q['storage']['total_selected_output_bytes']/1024**4:.3f}TiB，含规划余量/暂存/双cache峰估{q['storage']['planning_peak_disk_bytes_example']/1024**4:.3f}TiB，项目quota unknown。
冷初始化52/104/26000仅shelf参考，其他49任务caps未知；snapshot/隐藏状态等价未证，paired监督资格待冻结；技术失败/预算截尾不标0。5attempt70controls的新collector有限验收仅报价，未实现；完整终局验收仍需首个已计划完整parent。字段/视图/sidecar、父源分片幂等和两端退出/发布屏障已列；B现有CPU任务不变。
Velocity active-clean只留未来已计划guided调用，32tensor/6CPUcopy外另列scalar导出；当前没有guided/Q追加、改参或实现。真实seed/shard/compute release/claim为空。当前全部实际计算/硬件/holder/环境/安装/训练/删除/权重hash0；旧证据与公共v1未改，不自动下一阶段。
'''
with (W/'QUEUE_MESSAGE.txt').open('x') as f:f.write(message)
print(json.dumps(dict(status='CPU_READY',RESULT=ref(rp),REPORT=ref(P/'REPORT.md'),manifest=ref(P/'EVIDENCE_MANIFEST.json'),artifact_count=len(artifacts),manifest_files=len(paths)),ensure_ascii=False))
