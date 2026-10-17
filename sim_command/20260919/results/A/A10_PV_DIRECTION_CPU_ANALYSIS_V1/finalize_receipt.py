"""Seal new CPU analysis evidence. No project imports or numeric-runtime calls."""
import ast
import datetime
import hashlib
import json
import struct
from pathlib import Path

P=Path(__file__).resolve().parent
B=P.parents[2]
TASK='A10_PV_DIRECTION_CPU_ANALYSIS_V1'
W=B/'work/A'/f'{TASK}_r1'
ACK=B/'receipts/A'/f'{TASK}_ACK.json'
RECEIPT=B/'receipts/A'/f'{TASK}_RESULT.json'
assert not RECEIPT.exists()

def read(p):return json.loads(Path(p).read_text())
def absolute(p):return Path(p) if Path(p).is_absolute() else B/p
def ref(p):
    p=Path(p)
    assert p.is_file() and p.stat().st_size<3*1024*1024
    value=p.read_bytes()
    return dict(path=str(p),sha256=hashlib.sha256(value).hexdigest(),size_bytes=len(value))
def verify(r):
    actual=ref(absolute(r['path']))
    assert actual['sha256']==r['sha256'],r['path']
    assert 'size_bytes' not in r or actual['size_bytes']==r['size_bytes'],r['path']
    return actual
def put(path,obj):
    with Path(path).open('x') as f:json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def walkrefs(obj):
    if isinstance(obj,dict):
        if 'path' in obj and 'sha256' in obj:yield obj
        else:
            for v in obj.values():yield from walkrefs(v)
    elif isinstance(obj,list):
        for v in obj:yield from walkrefs(v)

ack=read(ACK)
auth=[]
for key in ['release','CONTROL','TASK_BOARD','task_brief','dependency_acceptance']:
    auth.append(verify(ack[key]))
assert ack['release']['sha256']=='023a3591f71eb759e4bec9aa494f00fbd4b734b395f6e201a6b04ec510d58542'
release=read(ack['release']['path'])
assert all(v==0 for v in release['limits'].values())
assert ack['hostname']==release['owner_host']
assert ack['board_entry']['status']=='ready' and ack['board_entry']['revision']==1

inputs=read(P/'INPUT_MANIFEST.json')
input_refs=[verify(r) for r in inputs['files']]
chains=[]
additional=[]
for state,acceptance in [
    ('step0',B/'manifests/A_PV_OFFLINE_PREFLIGHT_V3_FINAL_ACCEPTANCE.json'),
    ('cut5',B/'manifests/A_CAUSAL_C10_PREFLIGHT_V2_FINAL_ACCEPTANCE.json')]:
    a=read(acceptance)
    receipt_ref=verify(a['receipt'])
    receipt=read(receipt_ref['path'])
    artifact_refs=receipt['artifacts']
    selected=[r for r in walkrefs(artifact_refs) if any(x in r['path'] for x in ['/EVIDENCE_MANIFEST.json','/ARTIFACT_MANIFEST.json'])]
    records=[verify(r) for r in selected]
    if 'evidence_manifest' in a:records.append(verify(a['evidence_manifest']))
    for artifact in records:
        members={r['path']:r for r in read(artifact['path'])['files']}
        for used in input_refs:
            if used['path'] in members:
                assert used['sha256']==members[used['path']]['sha256']
    rows=dict(state=state,acceptance=ref(acceptance),accepted_receipt=receipt_ref,
              selected_manifest_refs=records,
              verification_scope='accepted receipt/manifest SHAs plus already-selected small inputs only; no full historical audit or asset rehash')
    chains.append(rows)
    additional.extend([ref(acceptance),receipt_ref,*records])
put(P/'SOURCE_ACCEPTANCE_CHAIN.json',dict(states=chains,big_asset_rehashes=0))

directions=read(P/'DIRECTION_STAGES.json')
S=directions['states']['step0']['scales']
assert S==directions['states']['cut5']['scales']
f32=lambda x:struct.unpack('<f',struct.pack('<f',x))[0]
put(P/'PARAMETER_UNITS_SUMMARY.json',dict(
    S_saved_float32=S,S_squared_in_Post_float32=[f32(x*x) for x in S],
    alpha=10,tau_saved=[.30000001192092896,.20000000298023224,.10000000149011612],
    dt_static=-.1,dt_units='dimensionless flow time, not physical seconds',
    S_units='raw environment command / internal normalized clean',
    g_anchor_units='probability gain / bounded command',
    dJ_dv_units='probability gain / internal velocity coordinate',
    local_clean_gradient_relation='g_clean=-saved_dJ_dv/tau; includes S and true clamp derivative',
    numeric_offset_c=None,numeric_offset_missing_reason='not saved here; no normalizer reload',
    stage_zero_convention='cosine is null if either vector norm is zero',
    clipping_scope='first10x4 candidate, before clamp if raw; local logs only describe before-update clipping'))

put(P/'CPU_REVIEW_NOTES.json',dict(
    numerical_analysis_runs=[ref(W/'CPU_ARITHMETIC_RUN_v1.json'),ref(W/'CPU_WRITEBACK_RUN_v1.json')],
    evidence_assembly_run=ref(W/'CPU_ASSEMBLY_RUN_v1.json'),
    helper_issue=dict(scope='read-only source excerpt printer',tool_chunk_id='80582f',returncode=1,
        error='IndexError: list index out of range',
        cause='requested actions.py line 31 from a 30-line file',
        correction='remaining source text read with endpoint bounded by actual line count; frozen files untouched',
        effect_on_numeric_or_runtime='none; no model, array analysis or experiment rerun'),
    report_editorial_update='REPORT now records the four additional saved-writeback checks; original assembly run preserved',
    old_files_modified=0,real_launcher_calls=0,compute_claims=0))

scripts=[]
for file in sorted(P.glob('*.py')):
    tree=ast.parse(file.read_text())
    names=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):names.extend(n.name for n in node.names)
        elif isinstance(node,ast.ImportFrom):names.append(node.module or '')
    forbidden={'torch','numpy','ctypes','mujoco','metaworld','gym','gymnasium','pynvml','OpenGL','safetensors','corrector','subprocess','socket'}
    assert all(n.split('.')[0] not in forbidden for n in names)
    scripts.append(dict(**ref(file),AST_parse_pass=True,static_imports=sorted(set(names)),forbidden_imports=[]))
base=read(P/'CPU_ARITHMETIC_RESULT.json');writeback=read(P/'WRITEBACK_AND_CLIP_CHECKS.json')
assert base['status']==writeback['status']=='PASS'
for name in ['CPU_ARITHMETIC_RUN_v1.json','CPU_ASSEMBLY_RUN_v1.json','CPU_WRITEBACK_RUN_v1.json']:
    assert read(W/name)['returncode']==0
put(P/'CPU_FINAL_AUDIT.json',dict(
    status='PASS',scope='this task input preservation, authored-script AST, new report refs; no repeated historical runtime/ledger audit',
    current_authorization_matches_ACK=True,authorization_refs=auth,
    selected_small_input_files_verified=len(input_refs),source_acceptance_chains=2,
    formula_file_text_SHA_checks=12,base_saved_relation_checks=78,saved_float32_writeback_checks=4,
    scripts=scripts,all_release_resource_actuals_zero=True,
    holder_inspection_performed=False,holder_live_state=None,
    holder_state_reason='CPU task expressly forbids querying or changing holders; no restoration claim needed',
    historical_weight_bytes_opened=0))

files={}
for folder in [P,W]:
    for f in sorted(folder.rglob('*')):
        if f.is_file() and f.name not in ['EVIDENCE_MANIFEST.json','QUEUE_MESSAGE.txt','QUEUE_DELIVERY.json']:
            files[str(f)]=ref(f)
for r in [ref(ACK),*auth,*input_refs,*additional]:files[r['path']]=r
manifest=dict(task_id=TASK,revision=1,created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              scope='all new private evidence, ACK/authentication and selected small read-only inputs; weight identity refs are not followed',
              files=list(files.values()),file_count=len(files),
              excludes=['manifest self','RESULT to avoid circular hash','later queue message/delivery'],
              big_model_files_opened_or_rehashed=0)
put(P/'EVIDENCE_MANIFEST.json',manifest)

stage=lambda s,b,n:next(r for r in directions['rows'] if (r['state'],r['branch'],r['stage'])==(s,b,n))
artifact_paths=[x for x in sorted(P.iterdir()) if x.is_file()]
artifacts=[ref(x) for x in artifact_paths]
artifacts.extend(ref(W/f) for f in ['CPU_ARITHMETIC_RUN_v1.json','CPU_ASSEMBLY_RUN_v1.json','CPU_WRITEBACK_RUN_v1.json'])
report=ref(P/'REPORT.md')
put(RECEIPT,dict(
    campaign_id='corrector-sim-20260919',task_id=TASK,revision=1,role='A',hostname=ack['hostname'],
    session_id='01a0b91f-7443-71b1-915d-6cdb6d6a1a13',status='CPU_READY',
    outcome='saved_PV_direction_analysis_complete_pending_analysis_acceptance',
    started_at_utc=ack['at_utc'],receipt_created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    ACK=ref(ACK),release=ack['release'],CONTROL=ack['CONTROL'],TASK_BOARD=ack['TASK_BOARD'],
    report=report,artifacts=artifacts,artifact_count=len(artifacts),
    evidence_manifest=ref(P/'EVIDENCE_MANIFEST.json'),manifest_file_count=len(files),
    checks=dict(saved_relation_checks=78,saved_writeback_checks=4,formula_files_text_SHA_checked=12,
                source_states=2,per_stage_rows=32,per_tau_rows=6,per_member_objective_rows=8),
    findings=dict(
        cut5_Velocity_dot_stages={n:stage('cut5','Velocity',n)['dot_g'] for n in
            ['guided_native_raw_delta','guided_clamped_delta','masked_direction','unit_direction','requested_delta','actual_delta']},
        step0_Velocity_dot_stages={n:stage('step0','Velocity',n)['dot_g'] for n in
            ['guided_native_raw_delta','guided_clamped_delta','masked_direction','actual_delta']},
        negative_direction_already_at_saved_guided_output=True,
        first_negative_tau=None,root_cause=None,
        independent_final_guided_Q=None,
        local_member_probabilities_recomputed=False,
        local_scalar_J_differences_computed=True,
        final_J_from_saved_probabilities={r['state']+'_'+r['branch']:r['J_recomputed_f64'] for r in
            read(P/'OBJECTIVE_RECOMPUTATION.json')['rows'] if r['evaluation_object'].startswith('clamp(')},
        accepted_flag_means='fixed update executed; no Q acceptance gate',
        genuine_G0_trigger=False,forced_engineering_intervention=True,
        G0_value_inherited_accepted_evidence=-.057708123698830605),
    actual_resource_counts={k:0 for k in release['limits']},
    new_projection_or_candidate_generated=False,new_noise_or_sample=False,
    holder_queries_or_changes=0,holder_live_state=None,restoration_required=False,
    real_launcher_invocations=0,compute_release_claims=0,release_consumed_as_compute=False,
    algorithm_or_shared_code_changes=0,old_evidence_modified=0,B_modified=False,
    control_or_board_modified=False,future_compute_authorized=False,
    optional_logging=dict(implemented=False,executed=False,authorized=False,
        payload_bytes_with_active_clean=98624,payload_bytes_with_full_clean=136064,
        model_calls_increment_for_reuse_logging=0,tensor_export_upper_bound=32,
        separate_final_guided_score_ensemble_calls=1,separate_final_guided_score_member_calls=4),
    scientific_limits=['two states are not a controlled ablation or error-rate denominator',
        'same saved context/Q/anchor identity permits within-state geometry only',
        'cut5 forced intervention with no G0 trigger is not a full-method failure sample',
        'historical five-task Q is compatibility evidence, not MT50 completion',
        'no branch ranking, Q gate, new alpha, radius, seed or winner selection'],
    next_action='queue this new CPU receipt to analysis for acceptance and decision; no automatic next phase'))
result_ref=ref(RECEIPT)
message=f'''A 执行端提交新 CPU 任务 {TASK} revision1：CPU_READY，待分析验收。
RESULT: {RECEIPT}
SHA256: {result_ref['sha256']}
REPORT: {report['path']}
SHA256: {report['sha256']}
EVIDENCE_MANIFEST: {P/'EVIDENCE_MANIFEST.json'}
SHA256: {ref(P/'EVIDENCE_MANIFEST.json')['sha256']}
产物引用 {len(artifacts)}，manifest 文件 {len(files)}。仅既有 step0/cut5 小数组与窄公式；78 项关系 +4 项保存 float32 写回通过，12 个源码文本 SHA，未重做旧账本/库存。
cut5 V 与同状态锚点 g：guided raw −0.118639497 → clamp −0.115827395 → mask −0.116817487 → actual −0.068514917；负号在独立半径处理前已存在。step0 同口径均为正。最终 J 重算 step0 P +0.053056207 / V +0.061526142；cut5 P +0.013589136 / V −0.156066865。每 τ 向量/局部成员概率缺失，独立最终 guided Q=null，首次反向 τ/根因未知；末 τ local-after 不顶替。S/S²、−τ、负 dt 的理想一阶符号相容，有限步下降不授权改 α/符号或加 Q 门。
附字段/单位、hypotheses/missing 表和可选日志报价（未授权/未实现）：98,624 B 活跃 clean 或136,064 B完整 clean，最多32额外张量导出，复用日志模型计算增量0；独立最终 guided Q 另需1ensemble/4member forward。
本任务全部计算/投影实现/硬件/holder/launcher/claim/安装/训练/删除/大权重hash为0；旧证据、CONTROL/BOARD、B均未改。cut5 G0不触发/强制工程性质及风险保留，不做排名或完整方法失败率。无新实验 release/proposal，交分析决定后续。
'''
with (W/'QUEUE_MESSAGE.txt').open('x') as handle:handle.write(message)
print(json.dumps(dict(status='CPU_READY',RESULT=result_ref,REPORT=report,
    evidence_manifest=ref(P/'EVIDENCE_MANIFEST.json'),artifact_count=len(artifacts),manifest_file_count=len(files)),ensure_ascii=False))
