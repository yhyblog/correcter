"""Write task receipts and hash only own small artifacts / frozen source files."""
from pathlib import Path
import ast,collections,datetime,hashlib,json,socket
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
P=B/'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1';W=B/'work/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1_r1'
T='A10_CAUSAL_EVENT_CPU_REPAIR_V1'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),realpath=str(p.resolve()),sha256=sha(p),size_bytes=p.stat().st_size)
def put(p,v):
    with p.open('x') as f:f.write(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
release=B/'releases/P00_CAUSAL_EVENT_CPU_REPAIR_V1.json';ack=B/'receipts/A'/(T+'_ACK.json')
ackj=read(ack);control=read(B/'CONTROL.json');board=read(B/'TASK_BOARD.json');r=read(release)
assert sha(release)=='29df747ad71306c2b3099ca9c5bbedb90f21c3f22aab7741e3ccda5224552bcd'
assert socket.gethostname()==r['owner_host']==ackj['hostname']
assert sha(B/'CONTROL.json')==ackj['CONTROL']['sha256'] and sha(B/'TASK_BOARD.json')==ackj['TASK_BOARD']['sha256']
assert control['mode']=='prepare' and not control['formal_gpu_runs_enabled'] and not any(control['current_compute_limits'].values())
assert len(control['closed_compute_releases'])==9
assert control['active_causal_event_preparation_release']=='releases/P00_CAUSAL_EVENT_CPU_REPAIR_V1.json'
assert not any(r['limits'].values())
event=read(W/'synthetic_events_v1/RESULT.json');metadata=read(W/'synthetic_publication_v1/RESULT.json');static=read(W/'STATIC_FREEZE_PROOF.json')
assert event['status']==metadata['status']==static['status']=='PASS'
assert len(event['checks'])==54 and len(event['cases'])==50 and metadata['check_count']==16
for f in ['EVENT_CHECK_RUN_v1.json','PUBLICATION_CHECK_RUN_v1.json']:assert read(W/f)['returncode']==0
for p in (P/'cpu_checks').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
paths=read(P/'proposal/PATHS.json')['paths'];assert all(not Path(p).exists() for p in paths.values())
code=read(P/'code/CODE_MANIFEST.json')
for row in code['files']:
    p=P/'code'/row['path'];assert p.stat().st_size==row['size_bytes'] and sha(p)==row['sha256']
proposal=read(P/'proposal/PROPOSAL.json')
for k in ['config','input_manifest','external_sources','code_manifest','integration_manifest','budget','command']:
    row=proposal[k];p=Path(row['path']);assert sha(p)==row['sha256'] and p.stat().st_size==row['size_bytes']
template=read(P/'proposal/RELEASE_TEMPLATE.json')
assert template['status']=='UNAUTHORIZED_TEMPLATE' and template['proposal_sha256']==sha(P/'proposal/PROPOSAL.json')
assert event['old_runtime_stack_backfilled'] is False
history=dict(task_id=T,scope='CPU development and synthetic tests only; no real V2 run',all_products_retained=True,deleted_files=[],
    prior_real_failure=dict(acceptance=ref(B/'manifests/A_CAUSAL_C10_PREFLIGHT_V1_FAILURE_ACCEPTANCE.json'),
        model_initializations=9,language_embedding_forwards=1,environment_and_cut_entered=False,actual_runtime_traceback_available=False,backfilled=False),
    chronological_checks=[
        dict(step=1,name='Old actual run_branch plus old Engine.emit',outcome='EXPECTED_SYNTHETIC_TypeError',
            explanation='Duplicate branch is reproduced before reset/write; this newly captured CPU stack is not the old GPU runtime stack',
            evidence=ref(W/'synthetic_events_v1/synthetic_old_regression/EXPECTED_SYNTHETIC_FAILURE.json')),
        dict(step=2,name='New actual Engine.emit + shared production recorder + real controller',outcome='PASS',branch_cases=50,
            checks_including_regression_conflicts_traceback_and_payloads=54,run=ref(W/'EVENT_CHECK_RUN_v1.json')),
        dict(step=3,name='Targeted changed AST / bash -n / frozen source and budget identity',outcome='PASS',evidence=ref(W/'STATIC_FREEZE_PROOF.json')),
        dict(step=4,name='Pure JSON metadata cases and actual publication-check CLI',outcome='PASS',cases=16,run=ref(W/'PUBLICATION_CHECK_RUN_v1.json'))],
    unexpected_fixture_failures=[],fixture_command_attempts=dict(events=1,publication=1),old_numeric_suites_rerun=False,large_weight_rehashes=0)
put(P/'CPU_FIX_HISTORY.json',history)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
checks=dict(events=ref(W/'synthetic_events_v1/RESULT.json'),source_provenance=ref(W/'synthetic_events_v1/SOURCE_PROVENANCE.json'),
    reserved_conflicts=ref(W/'synthetic_events_v1/synthetic_conflicts/PROOF.json'),payload_audit=ref(W/'synthetic_events_v1/EMIT_PAYLOAD_AUDIT.json'),
    traceback_primary=ref(W/'synthetic_events_v1/synthetic_tracebacks/failure.json'),traceback_cleanup=ref(W/'synthetic_events_v1/synthetic_tracebacks/cleanup_failure__environment_close.json'),
    native_cleanup_traceback=ref(W/'synthetic_events_v1/synthetic_tracebacks/EXTRACTED_GRAPHICS_CLEANUP_PROOF.json'),
    metadata=ref(W/'synthetic_publication_v1/RESULT.json'),metadata_CLI=ref(W/'synthetic_publication_v1/CLI_RUN.json'),
    static_freeze=ref(W/'STATIC_FREEZE_PROOF.json'),budget_identity=ref(W/'BUDGET_AND_IDENTITY_PROOF.json'))
actual={k:0 for k in r['limits']}
ready=dict(status='CPU_READY',task_id=T,revision=1,node_role='A',hostname=socket.gethostname(),at_utc=now,
    compute_authorized=False,CPU_release=ref(release),ACK=ref(ack),CONTROL_revision=34,TASK_BOARD_revision=41,
    proposal=ref(P/'proposal/PROPOSAL.json'),code_manifest=ref(P/'code/CODE_MANIFEST.json'),integration_manifest=ref(P/'INTEGRATION_MANIFEST.json'),
    diff_manifest=ref(P/'DIFF_MANIFEST.json'),input_manifest=ref(P/'INPUT_MANIFEST.json'),external_manifest=ref(P/'EXTERNAL_SOURCE_MANIFEST.json'),
    config=ref(P/'config/CONFIG.json'),CPU_FIX_HISTORY=ref(P/'CPU_FIX_HISTORY.json'),checks=checks,
    validated=['old true recorder/controller duplicate-key reproduction before reset',
        'new shared production recorder with actual controller and extracted Engine.emit: 50 synthetic branch cases',
        'protected identity refusal before file write and event ID commit, including same-value attempts',
        'live primary and cleanup exception type/message/traceback/branch/stage; separate files',
        '111-cap and frozen numeric/input/seed/UUID/loader/timeout/lifecycle invariants',
        '16 pure metadata cases plus actual pure JSON CLI'],
    unvalidated=['real V2 joint native DG0/PV C10/H20 execution','independent replay observable prefix agreement','real V2 exception/hardware behavior'],
    future_task_id=proposal['task_id'],future_release_id=proposal['authorization_identity']['release_id'],future_caps=proposal['resource_caps'],
    future_template_status='UNAUTHORIZED_TEMPLATE',future_paths_absent=paths,closed_old_compute_releases=9,
    actual_this_CPU_task=actual,holders='not queried/stopped/signalled; no lifecycle invocation',
    prior_real_failure_compute_not_zero=True,old_runtime_traceback_backfilled=False,public_interface_modified=False,B_unchanged=True)
put(P/'CPU_READY.json',ready)
report='''A10_CAUSAL_EVENT_CPU_REPAIR_V1：CPU_READY。已按 CONTROL34/TASK_BOARD41、指定 CPU release 核对 host 并写新 ACK。

去掉 branch_start 重复 branch，身份由真实共享 recorder 写入；8 个保留身份字段（另加 synthetic 证据标记）发生冲突时，在写文件和提交事件 ID 前明确拒绝。生产 Engine.emit 与 fixture 使用同一实现；没有另写 Fake.emit。现有诊断/launcher 捕获点补实时 traceback、branch 和已知阶段，主失败与 cleanup 分离；graphics cleanup 保留原始异常栈。

54 项定向事件检查通过，含先复现旧真实组合的 TypeError、50 个新合成分支案例、冲突/序列化/异常证据检查。Post/Velocity、G0 低于/等于/高于 0.05、强制关闭、prefix 不匹配及 reset/prefix/C10 早停均覆盖。正常合成路径验证合法 cut5、C10 10 步、丢弃 raw40、H20 恢复后剩 19。16 项纯 JSON 元数据检查及实际 CLI 通过；已运行变更 AST 和 bash -n。全部合成证据显式标记，详见 CPU_FIX_HISTORY.json 与 CPU_READY.json 的检查引用。

395 份代码中 387 份逐字节不变；6 份原代码修改、2 个标准库模块新增。六份数值文件、strict loader、UUID parser、原配置/输入/种子、111 caps、7采样/70flow/32控制上限、1800+30 child timeout、300 handoff 及同锁/同组生命周期不变，详见 DIFF_MANIFEST.json。

新 V2 身份、命令及同源 BOARD/CONTROL/release 模板已备齐；模板为 UNAUTHORIZED_TEMPLATE，真实 release/claim/output/cache 均未创建。命令和纯 JSON 发布检查用法见 commands/USAGE.md。仍需分析独立 release 才能执行。

本轮实际 Torch/dlopen/CUDA/EGL/NVML/模型/环境/holder 查询停算/真实 launcher/claim/安装/训练/删除/大权重重 hash 全 0。旧运行的模型初始化 9、语言 embedding 1 保留原结论；本轮新合成堆栈不回填旧运行。旧包/回执不改，B 不变。本轮产物全部保留，待分析验收。
'''
with (P/'REPORT.md').open('x') as f:f.write(report)
# All own source/fixtures/preparation evidence, never follow model references in copied manifests.
files=sorted([x for root in [P,W] for x in root.rglob('*') if x.is_file()])
put(P/'EVIDENCE_MANIFEST.json',dict(schema='CPU_event_repair_evidence_manifest_v1',task_id=T,at_utc=now,
    files=[ref(x) for x in files],file_count=len(files),
    exclusions=['this manifest itself','RESULT receipt and delivery audit created after this manifest','queue message/delivery written after completion'],
    input_and_external_weight_identities='frozen manifests copied and hashed as files; referenced weights not opened or hashed',
    synthetic_evidence_roots=[str(W/'synthetic_events_v1'),str(W/'synthetic_publication_v1')],all_local_products_retained=True))
artifacts={k:ref(P/v) for k,v in dict(CPU_READY='CPU_READY.json',REPORT='REPORT.md',proposal='proposal/PROPOSAL.json',
    budget='proposal/RESOURCE_BUDGET.json',code_manifest='code/CODE_MANIFEST.json',integration_manifest='INTEGRATION_MANIFEST.json',
    diff_manifest='DIFF_MANIFEST.json',minimal_patch='MINIMAL_PATCH.diff',CPU_FIX_HISTORY='CPU_FIX_HISTORY.json',
    input_manifest='INPUT_MANIFEST.json',external_manifest='EXTERNAL_SOURCE_MANIFEST.json',config='config/CONFIG.json',
    identity='proposal/IDENTITY.json',paths='proposal/PATHS.json',board_template='proposal/BOARD_TASK_TEMPLATE.json',
    CONTROL_required='proposal/CONTROL_REQUIRED.json',release_template='proposal/RELEASE_TEMPLATE.json',
    command='commands/run_proposed_causal_c10.sh',command_usage='commands/USAGE.md',publication_checker='code/publication_check.py',
    event_fixture='cpu_checks/check_events.py',metadata_fixture='cpu_checks/check_publication.py',evidence_manifest='EVIDENCE_MANIFEST.json').items()}
result=dict(campaign_id=r['campaign_id'],task_id=T,revision=1,node_role='A',hostname=socket.gethostname(),status='CPU_READY',at_utc=now,
    authorization=ref(release),ACK=ref(ack),artifacts=artifacts,checks=checks,
    summary=dict(event_checks=54,synthetic_branch_cases=50,metadata_cases=16,pure_JSON_CLI='PASS',AST_shell='PASS',
        expected_old_synthetic_failure='duplicate branch TypeError reproduced before reset/write',unexpected_fixture_failures=0,
        real_compute_launched=False,V2_authorized=False,code_files=395,unchanged_code_files=387,changed_original_code_files=6,added_stdlib_modules=2),
    synthetic_branch_outcomes=dict(collections.Counter(x['status'] for x in event['cases'])),
    actual_resource_units=actual,private_runtime_ledgers_created=False,future_proposal_caps=proposal['resource_caps'],
    old_releases_reusable=False,old_real_failure_counts=dict(model_initializations=9,language_embedding_forwards=1),
    no_old_runtime_stack_backfill=True,old_artifacts_unchanged=True,public_interface_unchanged=True,shared_guard_unchanged_by_this_task=True,
    holders='no query, stop or signal during CPU task',B_unchanged=True,all_products_retained=True,
    next_action='analysis acceptance and separate new V2 release; do not launch automatically')
receipt=B/'receipts/A'/(T+'_RESULT.json');put(receipt,result)
print(json.dumps(dict(status='CPU_READY',RESULT=ref(receipt),REPORT=ref(P/'REPORT.md'),manifest=ref(P/'EVIDENCE_MANIFEST.json'),artifact_refs=len(artifacts),evidence_files=len(files))))
