"""Seal only this task's narrow CPU outputs and inherited manifest anchors."""
import datetime,hashlib,json,socket
from pathlib import Path
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK='A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1'
P=B/'results/A'/TASK;W=B/'work/A'/(TASK+'_r1')
S=B/'results/A/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1';O=B/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1'
def read(p):return json.loads(Path(p).read_text())
def ref(p):
    p=Path(p);raw=p.read_bytes();return dict(path=str(p),realpath=str(p.resolve()),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
ackpath=B/'receipts/A'/(TASK+'_ACK.json');ack=read(ackpath)
release=B/'releases/P00_A_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1.json'
assert ref(release)['sha256']=='03d90c3c07274a8738714eb0b18c5398e51a183f1118fd72ef4d77ef28139b37'
assert socket.gethostname()==ack['host']
for name in ('CONTROL.json','TASK_BOARD.json'):
    row=next(r for r in ack['inputs'] if r['path']==str(B/name));assert ref(B/name)['sha256']==row['sha256']
control=read(B/'CONTROL.json');board=read(B/'TASK_BOARD.json')
assert control['revision']==41 and board['revision']==48 and control['mode']=='prepare' and not control['formal_gpu_runs_enabled']
assert all(v==0 for v in control['current_compute_limits'].values())
counts=read(release)['limits'];assert len(counts)==130 and all(v==0 for v in counts.values())

protected=[]
for ready_path in (O/'sidecar_v1/READY.json',S/'supplement_v1/READY.json'):
    ready=read(ready_path)
    for r in ready['files']:
        actual=ref(r['path']);assert actual['sha256']==r['sha256'];protected.append(actual)
for path,expected in [(O/'sidecar_v1/READY.json','56adfa1657553af79e0b740c643ddcc0616520c62c50983594e0cfa72e9650d9'),
    (S/'supplement_v1/READY.json','dd330a43d5a7b0e6304975d399c561388b3bbb7befd2e609dd223f4a41de9edd'),
    (B/'results/A/A10/interface_v1/interface.schema.json','7d52f22e9d2e622a18a9a71fdac822ed50413aa3838aa3ad40d98e0bee10500f'),
    (S/'EVIDENCE_MANIFEST.json','0403896fb4dab14412c68e0d6a14db56aa8a22014272fc6d5f2f74a8aec6d646'),
    (B/'receipts/A/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1_RESULT.json','bd3dc31d6c792653af6d8614b81be12e2107c464319e4848af6567c72176f22e')]:
    actual=ref(path);assert actual['sha256']==expected;protected.append(actual)
write(P/'PROTECTED_IDENTITIES.json',dict(status='PASS',files=protected,old_public_sidecar_supplement_modified=False,scope='narrow immutable anchors; no old full-tree re-audit'))

groups=[]
for name,f in [('loader_controller_publishers',W/'targeted_v1/CHECKS.json'),('strict_types_late_mutation',W/'binding_delta_v1/CHECKS.json'),('V3_metadata_final_writer',W/'v3_metadata_v1/CHECKS.json')]:
    x=read(f);assert x['status']=='PASS' and all(c['passed'] for c in x['checks']);groups.append(dict(name=name,count=len(x['checks']),ref=ref(f)))
assert sum(g['count'] for g in groups)==80
assert read(W/'FINAL_ENTRY_CHECKS.json')['status']=='PASS'
assert read(P/'NUMERICAL_PATH_STATIC_DIFF.json')['status']=='PASS'
write(P/'CPU_CHECKS.json',dict(status='PASS',targeted_assertions=80,narrow_numerical_AST_checks=3,final_JSON_shell_entry_checks=2,groups=groups,
    numerical_path_diff_ref=ref(P/'NUMERICAL_PATH_STATIC_DIFF.json'),entry_ref=ref(W/'FINAL_ENTRY_CHECKS.json'),
    synthetic_counts=read(W/'targeted_v1/CHECKS.json')['synthetic_counts'],old104_suite_run=False,old133_suite_run=False,
    actual_loader_bound_as_Engine_method=True,old_actual_failure_reproduced=True,all_real_operations_zero=True))

proposal=read(P/'proposal/PROPOSAL.json');prior=read(S/'proposal/PROPOSAL.json')
assert proposal['status']=='UNAUTHORIZED_TEMPLATE' and all(proposal[k]==prior[k] for k in ('source','resource_caps','timeouts','storage'))
assert all(not Path(v).exists() for v in proposal['paths'].values())
assert not (B/'releases/P11_A_COMMON_POOL_FIRST_PARENT_V3.json').exists()
for key in ('config','budget','code_manifest','input_manifest','external_manifest','closure','sidecar_ready','command_ref','preparation_manifest','supplementary_protocol_ref','reference_CPU_delta_ref'):
    r=proposal[key];assert ref(r['path'])['sha256']==r['sha256'],key
for r in read(P/'code/CODE_MANIFEST.json')['files']:assert ref(r['path'])['sha256']==r['sha256']
ready=read(P/'supplement_v2/READY.json')
for r in ready['files']+ready['producer_refs']:assert ref(r['path'])['sha256']==r['sha256']

(P/'DIFF.md').write_text('''本轮只修共享计划引用与实际干预标志，另做独立V3包身份/继承路径调整。CODE_DIFF.json列逐文件旧/新SHA，MINIMAL.patch保留精确差异。

- 实际Engine.load_bank直接绑定纯CPU可测shared_plans.load_bank。normal BANK增加私有身份/plan_key/别名/shape/dtype/realpath；normal RESULT锚定其SHA。分支loader核验同parent/cut/source/source-manifest/run及全部六计划，记录小型白名单，不复制BANK数据。
- public builder按当前请求plan_key选定引用，publisher仅对该精确白名单开放shared generated_chunk_ref；BANK和raw内容再核SHA。obs/next仍本branch。G0_old保留自己的prefix引用；native suffix仍本branch。相同字节不替代plan_key匹配。
- controller只增加实际entry/返回承诺步/替换标志；未改engine调用顺序、参数或数值方法。public intervened要求候选替换且返回承诺步>0；normal/precut/介入前失败/G0_old为false。G0_old记old_queue_control，所有分支online_G0_triggered=false。失败ledger保存既有实际证据。
- sidecar按选定共享key取得精确raw/noise引用，公共schema和sidecar_v1字段不变。新增supplement_v2继承旧聚合/私有成本说明，仅替换过严的shared chunk规则并解释intervened。
- V3复用已验收bounded storage、输入和116caps/timeout；新增小元数据/CPU SHA次数单列CPU_REFERENCE_DELTA。无新资源准入设计、quota/硬件探针或大权重hash。
''')
command=' '.join(proposal['command'])
(P/'REPORT.md').write_text(f'''A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1 revision1：CPU_READY，待分析验收。已核对CONTROL41/TASK_BOARD48、host和CPU release；130项真实操作均0。

已用旧实际load_bank和旧publisher复现合法normal/BANK引用被拒绝。新实际loader/publisher以同parent/cut/source/source-manifest/run、BANK精确path/SHA及plan_key/逻辑别名建立白名单，绑定真实path/realpath、format、50×4/<f4/800B和raw SHA。Q a0/±、G0 fresh0/1/2共享路径通过；G0_old与native suffix保持本branch。跨branch obs/next、错身份/manifest/plan_key/内容及任意外路径均拒绝，相同字节也不能冒充请求key；不复制BANK。

intervened改为有实际候选替换且至少1个承诺step返回。precut/normal/介入前失败为false；G0_old为旧队列对照false，保留commitment证据。全部强制采集分支明确online_G0_triggered=false，不声明收益触发。失败私有ledger保留实际entry状态；不回填旧证据。

80项定向断言、3项窄数值AST对比、2项JSON入口/shell检查PASS；未跑旧104/133套。测试均stdlib小型synthetic文件：191 fake controls、217 fake observations、28 fake native plans，80个synthetic BANK文件含隔离负例，均非真实模型/环境调用。public/sidecar_v1/supplement_v1及旧回执manifest锚点SHA一致。

新补充供B CPU消费：supplement_v2/READY.json，SHA256={ref(P/'supplement_v2/READY.json')['sha256']}。未改B包/dispatch，也未向B会话发命令。

独立未授权V3沿用原未执行source/seed、116caps、453sample/4530flow/4500control/4515obs、timeout和bounded_first_parent合同。资源风险原则接受只沿用，不重新设计或探针；新增引用CPU SHA/最多14个小白名单文件在CPU_REFERENCE_DELTA中报价，原writer/log/temp限额不扩。新run/claim/output/cache均独立且未创建。

Torch/硬件/holder/真实launcher/claim/采集/安装/训练/删除/大权重hash均0，旧十份计算release不复用。真实MJB/full_state资格仍须在原计划parent内验证。完成等待分析，不自动下一阶段。

仅供后续独立release审核，未执行：
```sh
cd {P}
{command}
```
''')
write(P/'CPU_READY.json',dict(status='CPU_READY',task_id=TASK,task_revision=1,report_ref=ref(P/'REPORT.md'),
    checks_ref=ref(P/'CPU_CHECKS.json'),proposal_ref=ref(P/'proposal/PROPOSAL.json'),caps_diff_ref=ref(P/'CAPS_IDENTITY_DIFF.json'),
    numerical_path_ref=ref(P/'NUMERICAL_PATH_STATIC_DIFF.json'),supplement_ready_ref=ref(P/'supplement_v2/READY.json'),
    reference_delta_ref=ref(P/'CPU_REFERENCE_DELTA.json'),predecessor_supplement_unchanged=True,
    future_compute_authorized=False,future_command=proposal['command'],future_cwd=str(P),future_paths_created=False,
    B_consumption='immutable successor on shared filesystem; analysis dispatch and B acknowledgement remain external',
    next_action='analysis acceptance only; do not execute V3 without independent release'))

artifacts=[P/name for name in ['CPU_READY.json','REPORT.md','CPU_CHECKS.json','DIFF.md','MINIMAL.patch','CODE_DIFF.json',
    'CAPS_IDENTITY_DIFF.json','NUMERICAL_PATH_STATIC_DIFF.json','CPU_REFERENCE_DELTA.json','PROTECTED_IDENTITIES.json',
    'INPUT_MANIFEST.json','EXTERNAL_SOURCE_MANIFEST.json','PREPARATION_INPUT_MANIFEST.json','code/CODE_MANIFEST.json',
    'config/CONFIG.json','proposal/PROPOSAL.json','proposal/RESOURCE_BUDGET.json','proposal/SOURCE_PROPOSAL.json',
    'proposal/RELEASE_TEMPLATE.json','proposal/CONTROL_TEMPLATE.json','proposal/BOARD_TEMPLATE.json',
    'commands/run_proposed_first_parent.sh','supplement_v2/READY.json','supplement_v2/README.md','supplement_v2/SYNTHETIC_EXAMPLES.json']]
excluded={'EVIDENCE_MANIFEST.json','FINAL_VERIFICATION.json','QUEUE_MESSAGE.json','QUEUE_DELIVERY.json'}
files=sorted({p for root in (P,W) for p in root.rglob('*') if p.is_file() and p.name not in excluded} |
    {ackpath,B/'receipts/A'/(TASK+'_SUPPLEMENT_READY.json')})
manifest_rows=[ref(f) for f in files]
write(P/'EVIDENCE_MANIFEST.json',dict(schema='shared_plan_CPU_repair_evidence_v1',task_id=TASK,files=manifest_rows,
    file_count=len(manifest_rows),scope='new isolated CPU package/work/ACK/supplement receipt only; inherited manifests referenced without weight traversal',
    code_overlay_files=14,inherited_base_manifest_refs=[ref(S/'code/CODE_MANIFEST.json'),ref(O/'code/CODE_MANIFEST.json')]))
result=dict(campaign_id='corrector-sim-20260919',task_id=TASK,task_revision=1,status='CPU_READY',owner='A',host=socket.gethostname(),
    executor_session_id=ack['executor_session_id'],completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    control_revision=41,task_board_revision=48,release_ref=ref(release),ack_ref=ref(ackpath),
    report_ref=ref(P/'REPORT.md'),cpu_ready_ref=ref(P/'CPU_READY.json'),manifest_ref=ref(P/'EVIDENCE_MANIFEST.json'),
    artifact_refs=[ref(f) for f in artifacts],actual_counts=counts,
    synthetic_counts=read(W/'targeted_v1/CHECKS.json')['synthetic_counts'],
    validation=dict(status='PASS',targeted_assertions=80,narrow_numerical_AST_checks=3,final_JSON_shell_entry_checks=2,
        old104_suite_run=False,old133_suite_run=False,old_actual_failure_reproduced=True),
    future_proposal_ref=ref(P/'proposal/PROPOSAL.json'),future_compute_authorized=False,actual_collection_authorized=False,
    future_source_seed_unchanged=True,numerical_caps_unchanged=116,storage_and_timeouts_unchanged=True,
    future_paths_created=False,old_ten_compute_releases_reused=False,
    public_sidecar_supplement_v1_modified=False,B_dispatch_or_session_modified=False,
    successor_supplement_ref=ref(P/'supplement_v2/READY.json'),
    unresolved=['real full-state/MJB qualification remains in the same planned parent',
        'previously accepted bounded-first-parent monitoring gaps are inherited, not new hard guarantees',
        'B CPU consumption has not been claimed as acknowledged'],
    next_action='wait for analysis acceptance; no automatic collection or next stage')
rp=B/'receipts/A'/(TASK+'_RESULT.json');write(rp,result)
print(json.dumps(dict(status='CPU_READY',artifact_refs=len(artifacts),evidence_files=len(files),result_ref=ref(rp),manifest_ref=ref(P/'EVIDENCE_MANIFEST.json'))))
