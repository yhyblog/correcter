"""Seal only this CPU task's small outputs; no runtime entry or external payload hash."""
from pathlib import Path
import datetime
import hashlib
import json

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK = 'A11_MT50_CONTINUATION_CPU_V1'
P = B / 'results/A' / TASK
W = B / 'work/A' / TASK
ACK = B / 'receipts/A' / (TASK + '_ACK.json')
RESULT = B / 'receipts/A' / (TASK + '_RESULT.json')

def read(path):
    return json.loads(Path(path).read_text())

def ref(path):
    path = Path(path)
    size = path.stat().st_size
    assert size < 16 * 1024 * 1024, ('not a small CPU artifact', str(path), size)
    return dict(path=str(path), realpath=str(path.resolve()),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size_bytes=size)

def write(path, data):
    with Path(path).open('x') as stream:
        if isinstance(data, str):
            stream.write(data)
        else:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            stream.write('\n')
    return ref(path)

ack = read(ACK)
release = read(W / 'authorization/P00_A_MT50_CONTINUATION_CPU_V1.json')
proposal = read(P / 'proposal/PROPOSAL.json')
table = read(P / 'config/MT50_TASK_TABLE.json')
targeted = read(P / 'checks/targeted01/CHECK_RESULT.json')
final = read(P / 'checks/final_metadata2/CHECK_RESULT.json')
wording = read(P / 'checks/SEMANTICS_WORDING_AST.json')
native_fake = read(P / 'checks/targeted01/SYNTHETIC_INITIALIZATION_SUMMARY.json')
quote = read(P / 'RESOURCE_AND_STORAGE_QUOTE.json')
diff = read(P / 'MINIMAL_DIFF.json')
sources = [row['source'] for row in proposal['parents']]
expected_names = ['assembly-v3', 'basketball-v3', 'bin-picking-v3', 'box-close-v3',
                  'button-press-topdown-v3', 'button-press-topdown-wall-v3',
                  'button-press-v3', 'button-press-wall-v3']
assert [s['task'] for s in sources] == expected_names
assert all(s['split'] == 'train' and s['ordinal'] == 0 and s['cut'] == 5 for s in sources)
assert all(x == 0 for x in release['limits'].values())
assert targeted['status'] == final['status'] == wording['status'] == 'PASS'
assert targeted['passed'] == 89 and all(x['passed'] for x in final['checks'])
assert read(W / 'TARGETED01_EXIT.json')['returncode'] == 0
assert read(W / 'FINAL_METADATA2_EXIT.json')['exit_code'] == 0
assert proposal['status'] == 'UNAUTHORIZED_PROPOSAL' and proposal['actual_compute_authorized'] is False
assert proposal['concurrency'] == 2 and len(proposal['resource_caps']) == 116
assert table['known_task_count'] == 50 and table['unknown_task_count'] == 0
assert ref(P / 'proposal/PROPOSAL.json')['sha256'] == final['final_proposal_sha256']
assert read(P / 'proposal/RELEASE_TEMPLATE.json')['storage_admission']['accepts_monitoring_gaps'] is False
assert not (B / 'releases/P11_A_COMMON_POOL_BATCH2_V1.json').exists()
assert all(not Path(path).exists() for path in proposal['paths'].values())
for row in ack['authorization_refs']:
    assert ref(row['path'])['sha256'] == row['sha256'], ('authorization changed', row['path'])
    assert ref(row['snapshot_path'])['sha256'] == row['sha256']

at = datetime.datetime.now(datetime.timezone.utc).isoformat()
check_index = write(P / 'CHECK_INDEX.json', dict(
    status='PASS', targeted_checks_passed=89,
    targeted=ref(P / 'checks/targeted01/CHECK_RESULT.json'),
    native_fake=ref(P / 'checks/targeted01/SYNTHETIC_INITIALIZATION_SUMMARY.json'),
    final_metadata=ref(P / 'checks/final_metadata2/CHECK_RESULT.json'),
    single_summary_literal_AST_equivalence=ref(P / 'checks/SEMANTICS_WORDING_AST.json'),
    final_checks=[dict(name=r['name'], passed=r['passed']) for r in final['checks']],
    runtime_code_AST_files=28, changed_runtime_code_files=6, unchanged_runtime_code_files=22,
    preserved_prior_checks=[ref(P / 'checks/final_metadata/CHECK_RESULT.json')],
    final_metadata_recheck_reason='physics_semantics text now explicitly includes direct mj_step; behavior AST unchanged',
    raw_command_evidence=[ref(W / n) for n in ['TARGETED01.stdout', 'TARGETED01.stderr',
        'TARGETED01_EXIT.json', 'FINAL_METADATA2.stdout', 'FINAL_METADATA2.stderr', 'FINAL_METADATA2_EXIT.json']],
    synthetic_counts=targeted['synthetic_counts'], native_fake_invocations=native_fake['native_fake_invocations'],
    real_runtime_operations=release['limits'], old_suites_executed=0,
    synthetic_future_release_fixtures_are_not_authorization=True))

ready = write(P / 'CPU_READY.json', dict(
    status='CPU_READY', task_id=TASK, task_revision=1, owner='A', at_utc=at, host=ack['host'],
    release_id=release['release_id'], release_sha256=ack['release_sha256'], ACK=ref(ACK),
    current_CONTROL_revision=47, current_TASK_BOARD_revision=55,
    static_initialization=dict(total_tasks=50, known=50, unknown=0, new_narrow_audits=45,
        accepted_old_task_evidence_reused=5, new_real_initialization_qualifications=0,
        unknown_cap_policy='retain selected source; reject before model/hardware; no substitution'),
    selected_sources=sources, proposed_concurrency=2, proposed_parents=8, branches_per_parent=15,
    proposal=ref(P / 'proposal/PROPOSAL.json'), future_compute_authorized=False,
    Batch1_storage_risk_acceptance_reused=False,
    Batch2_storage_risk_acceptance=False, separate_analysis_decision_required=True,
    future_runtime_paths_absent={k:not Path(v).exists() for k,v in proposal['paths'].items()},
    actual_new_sources=0, actual_seed_applications=0, active_shards_created=0,
    actual_full_state_or_MJB_qualifications=0, physical_equality_proven=None,
    new_task_state_qualification='must pass original exact closure/MJB gates within each released planned parent',
    real_runtime_operations=release['limits'], synthetic_counts=targeted['synthetic_counts'],
    checks=check_index, unknown_task_source_blockers=[],
    acceptance_history=dict(accepted_train=8, accepted_development=0, processed_plan_slots=9,
        normal_only=1, remaining_unexecuted=491, old_closed_compute_releases=13),
    next_action='analysis review only; do not run proposal automatically'))

report = f'''A11_MT50_CONTINUATION_CPU_V1 revision1 已完成 CPU_READY。ACK 核对 CONTROL47/TASK_BOARD55、A host 及 CPU release SHA；本轮所有真实操作计数为 0，未创建正式 run/cache/shard/claim，未查询或停止 holder。旧13份计算 release、旧证据、公共接口和 B 文件保持原状。

50任务静态可报价50、未知0：既有5任务复用验收证据，新增45任务只核受调用源码和XML；任务字典index、wrapper ID和语言index分列（push与push-back共享语言40）。逐task/阶段预算及窄行SHA见 MT50_INITIALIZATION_BUDGET.md、config/MT50_TASK_TABLE.json、TASK_SOURCE_EVIDENCE.json。box-close、door-lock 的 reset_model 各含5个直接 mj_step，104次 reset_model 额外520子步/attempt；隔离钩子纳入原 initialization_physics_substeps，do_simulation 内不重复计费，异常保持 entered 消耗。仅本批 box-close 增加7800子步。静态支持不证明新任务实际初始化或 full-state/MJB 资格；仍须在同一已授权 parent 内过原门，physical_equality_proven=null。

唯一 Batch2 提案按真实50任务 ASCII 顺序、已处理身份排除后选取：assembly-v3、basketball-v3、bin-picking-v3、box-close-v3、button-press-topdown-v3、button-press-topdown-wall-v3、button-press-v3、button-press-wall-v3。全部 A/train ordinal0/cut5；源/seed 按原规则提议，未实际使用。p04 normal-only 与 shelf0 均保留已处理身份，不补源。500槽元数据仍为处理9、未执行491，已验收8train/dev0；不是新增采样或训练充分性证明。

隔离包保持并发2、每parent15顺序cold分支、每parent固定GPU UUID、单外层预约与整组退出/发布后统一恢复；数值、终局、标签、容差和原 partial_or_failed 调度语义未改。28代码文件中6个新增/修改、22个相同；旧 full-state schema 名称沿用，编码/字段/容差不变。差异见 MINIMAL_DIFF.json/patch。89项真实组件+合成边界定向检查通过，覆盖新映射、未知cap拒绝、身份/RNG、两repeat、C10/C5及cut前/commit内/边界终局。最终纯JSON ready/running通过、未授权/缺新风险接受拒绝，2个shell仅语法检查；28文件AST通过。末次只修计量说明字符串并用归一AST证明行为不变，未重跑旧全集。

满120分支预算保持116caps+调度aux：3624sample、36240flow、36000control、36120obs；初始化6240 native reset、12480 reset_model、3127800物理子步、12720显式forward。预算不借提前成功减额。计时引用保存的Batch1 16143.591s/106 loads/并发2，平均载入124.798277s、child host区间占46.4456%；这些不是GPU秒、实际IO、可消除耗时或下一批工期。完整参数式及分开timeout见 RESOURCE_AND_STORAGE_QUOTE.json；preparation900、handoff300、child1800+30、parent27900、reserved111900+30、publication300、恢复观察120秒；最终清理/锁等待/端到端硬上界null。

新的 bounded_batch2 准入加floor为93,952,475,136B及564096 inode；128GiB RAM仅规划。项目quota、容器内存、RSS/VRAM峰值、物理IO、第三方temp、监测超调和当前容量仍未知，未作探针。121遍完整校验的已知尺寸逻辑读取小计 {quote['IO_quote']['known_sized_hash_read_subtotal_121checks_bytes']:,}B，另有每遍116次未知尺寸引用，严格上界null；大权重未读取或重hash。Batch1存储风险接受不继承，Batch2模板 accepts_monitoring_gaps=false，真实采集须分析独立决定并发布新release。

交付 CPU_READY.json、CHECK_INDEX.json、EVIDENCE_MANIFEST.json、唯一 proposal/PROPOSAL.json 与未授权发布模板。未来命令及cwd已冻结在提案，只供审核，本轮未执行。完成后停止，等待分析验收。
'''
report_ref = write(P / 'REPORT.md', report)

# Only this task's own small files. External sources and inherited payloads remain
# separately indexed; no historical 17GB result tree or model payload is traversed.
files = []
for root in (P, W):
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name != 'EVIDENCE_MANIFEST.json' and not path.name.startswith('QUEUE_'):
            assert not path.is_symlink()
            files.append(ref(path))
files.append(ref(ACK))
assert len({x['path'] for x in files}) == len(files)
manifest = write(P / 'EVIDENCE_MANIFEST.json', dict(
    task_id=TASK, task_revision=1, at_utc=at, scope='own small CPU evidence and ACK only',
    files=files, file_count=len(files), logical_file_bytes=sum(x['size_bytes'] for x in files),
    external_static_source_index=ref(P / 'evidence/NEW_STATIC_EXTERNAL_FILES.json'),
    external_static_source_files=140, runtime_code_files=28,
    inherited_payload_verification='frozen SHA references reused; no payload rehash this task',
    exclusions=['manifest itself', 'RESULT references this manifest', 'queue delivery evidence created after sealing'],
    final_proposal_sha256=ref(P / 'proposal/PROPOSAL.json')['sha256']))

artifact_paths = ['CPU_READY.json', 'REPORT.md', 'CHECK_INDEX.json', 'EVIDENCE_MANIFEST.json',
    'MT50_INITIALIZATION_BUDGET.md', 'config/MT50_TASK_TABLE.json', 'TASK_SOURCE_EVIDENCE.json',
    'SOURCE_AND_SEED_PROPOSALS.json', 'REMAINING_PLAN_IDENTITIES.json', 'STATE_FIELD_CLOSURE.json',
    'RESOURCE_AND_STORAGE_QUOTE.json', 'RESOURCE_QUOTE.md', 'SAVED_TIMING_REFERENCE.json',
    'MINIMAL_DIFF.json', 'MINIMAL_DIFF.patch', 'proposal/PROPOSAL.json', 'proposal/RELEASE_TEMPLATE.json',
    'proposal/BOARD_TEMPLATE.json', 'proposal/CONTROL_TEMPLATE.json',
    'proposal/CANDIDATE_PUBLICATION_DOCUMENTS.json', 'proposal/RESOURCE_BUDGET.json',
    'commands/run_proposed_batch2.sh', 'commands/check_publication_metadata.sh',
    'code/CODE_MANIFEST.json', 'CONFIG_MANIFEST.json', 'EXTERNAL_SOURCE_MANIFEST.json',
    'INPUT_MANIFEST.json', 'INHERITED_PACKAGE_MANIFEST.json']
result = dict(task_id=TASK, task_revision=1, node_role='A', host=ack['host'], status='CPU_READY',
    completed_at_utc=at, release_id=release['release_id'], release_sha256=ack['release_sha256'],
    ACK=ref(ACK), report=report_ref, CPU_READY=ready, manifest=manifest,
    artifacts=[ref(P / name) for name in artifact_paths],
    real_runtime_operations=release['limits'], synthetic_counts=targeted['synthetic_counts'],
    synthetic_native_function_invocations=native_fake['native_fake_invocations'],
    static_tasks=dict(known=50, unknown=0, remaining45_narrow_audited=45, old5_evidence_reused=5),
    fixed_next8_tasks=expected_names, selection='ASCII first8 unprocessed A/train0/cut5; identity-only',
    source_seed_rule='common_pool_batch_source_v1; proposed only',
    proposed_concurrency=2, proposed_attempts=120, proposed_resource_caps=proposal['resource_caps'],
    proposed_scheduler_caps=proposal['scheduler_caps'], proposal=ref(P / 'proposal/PROPOSAL.json'),
    future_compute_authorized=False, Batch2_storage_risk_acceptance=False,
    requires_independent_analysis_storage_decision_and_compute_release=True,
    new_task_actual_full_state_MJB_qualification=None, physical_equality_proven=None,
    checks=dict(targeted_passed=89, final_metadata_and_shell_passed=6, AST_files=28,
        single_literal_AST_equivalence=True, old_suites_executed=0),
    actual_new_parents=0, actual_seed_applications=0, actual_active_shards=0,
    formal_runtime_paths_created=False, holder_query_stop_operations=0,
    accepted_data_unchanged=dict(train=8, development=0, processed=9, normal_only=1, remaining=491),
    old_closed_compute_releases=13, old_releases_reused=False, B_files_or_dispatch_modified=False,
    B_session_messages_sent=0, final_action='stop after CPU delivery; await analysis acceptance')
result_ref = write(RESULT, result)
print(json.dumps(dict(status='CPU_READY', RESULT=result_ref, manifest=manifest,
    artifact_count=len(artifact_paths), evidence_files=len(files),
    proposal_sha256=ref(P / 'proposal/PROPOSAL.json')['sha256'], real_runtime_operations=0)))
