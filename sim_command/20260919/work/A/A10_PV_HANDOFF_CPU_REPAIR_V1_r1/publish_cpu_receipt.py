"""Freeze the CPU-only handoff repair package and reviewable proposals."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import platform

B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK='A10_PV_HANDOFF_CPU_REPAIR_V1'
P=B/'results/A'/TASK
W=B/'work/A'/f'{TASK}_r1'
OLD=B/'results/A/A10_PV_AUTH_METADATA_CPU_V1'
RCP=B/'receipts/A'

def read(path):return json.loads(path.read_text())
def ref(path):
    assert path.stat().st_size<2*1024*1024,str(path)
    raw=path.read_bytes();return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))
def put(path,obj):
    with path.open('x') as f:f.write(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def write(path,text):
    with path.open('x') as f:f.write(text)

ack=read(RCP/f'{TASK}_ACK.json')
spec=read(P/'guard_patch/HANDOFF_SPEC.json')
patch=read(P/'guard_patch/PATCH_IDENTITY.json')
identity=read(P/'proposal/IDENTITY.json')
proposal=read(P/'proposal/PROPOSAL.json')
release=read(P/'proposal/RELEASE_TEMPLATE.json')
control=read(P/'proposal/CONTROL_REQUIRED.json')
board=read(P/'proposal/BOARD_TASK_TEMPLATE.json')
fake=read(W/'TARGETED_FAKE_RESULT.json');integration=read(W/'CHANGED_INTEGRATION_AND_SYNTAX_CHECKS.json')
assert fake['status']==integration['status']=='passed'
assert platform.node()==ack['hostname']
for rel,snapshot in ack['input_snapshots'].items():assert ref(B/rel)['sha256']==snapshot['sha256'],rel
assert ref(Path(spec['guard_path']))['sha256']==patch['original_shared_sha256']
assert ref(Path(spec['guard_path']))['sha256']!=spec['guard_expected_sha256']
assert board==control['board_task'] and board['status']=='ready' and release['status']=='UNAUTHORIZED_TEMPLATE'
assert spec==proposal['occupancy_handoff']==release['occupancy_handoff']==control['active_occupancy_handoff']==read(P/'config/CONFIG.json')['occupancy_handoff']
assert proposal['resource_caps']==read(OLD/'proposal/PROPOSAL.json')['resource_caps']==release['resource_caps']==control['current_compute_limits']==control['per_task_compute_limits'][identity['task_id']]
assert len(proposal['resource_caps'])==66
for name in ['INPUT_MANIFEST.json','EXTERNAL_SOURCE_MANIFEST.json']:
    rows=[x for x in read(P/name)['files'] if x['path']==spec['guard_path']]
    assert len(rows)==1 and rows[0]['sha256']==spec['guard_expected_sha256'] and rows[0]['size_bytes']==spec['guard_expected_size_bytes']
for key in ['config','input_manifest','code_manifest','external_sources','command','authorization_identity']:
    assert ref(Path(proposal[key]['path']))==proposal[key]
assert release['proposal_sha256']==ref(P/'proposal/PROPOSAL.json')['sha256']
cm=read(P/'code/CODE_MANIFEST.json')
for row in cm['files']:
    actual=ref(P/'code'/row['path']);assert actual['sha256']==row['sha256'] and actual['size_bytes']==row['size_bytes']
assert len(cm['files'])==381
for path in [Path(identity['release_path']),Path(identity['claim_path']),Path(identity['output_root'])/identity['run_id'],Path(identity['cache_root'])/identity['run_id']]:assert not path.exists()
ast.parse(Path(__file__).read_text())

provenance=[OLD/'proposal/PROPOSAL.json',OLD/'code/CODE_MANIFEST.json',OLD/'INPUT_MANIFEST.json',OLD/'EXTERNAL_SOURCE_MANIFEST.json',OLD/'config/CONFIG.json',B/'manifests/PV_AUTH_METADATA_CPU_V1_ACCEPTANCE.json',B/'manifests/A_PV_OFFLINE_PREFLIGHT_V2_FAILURE_ACCEPTANCE.json',B/'releases/P10_A_PV_OFFLINE_PREFLIGHT_V2_CLOSED.json',B/'work/A/A10_PV_OFFLINE_PREFLIGHT_V2_r1/HOLDER_LIFECYCLE_WAVE.log',B/'contracts/TASK_STATE_CONTRACT_V1.md']
put(P/'DERIVATION.json',dict(source_package=str(OLD),source_references=[ref(x) for x in provenance],patch_original_SHA_matches_saved_V2_source=True,
    diagnosis_scope='Saved V2 logs/source support serial holder shutdown exceeding90s; no deadline NVML rows, no new claim that all other causes are excluded',
    allowed_changes='V3 identity/path, handoff environment/spec gate, private run-client patch and expected guard SHA in both runtime manifests',
    referenced_weights_arrays_and_external_library_bytes_read=0,large_weight_hashes=0,old_packages_receipts_and_shared_sources_modified=0,
    runtime_guard_SHA_expectation='Only patched SHA in INPUT and EXTERNAL files rows; original SHA solely installation precondition/rollback provenance',
    installation_pending=True,compute_release_pending=True,new_algorithm_validation=False))

checker=P/'commands/check_publication_metadata_cpu.py'
fixtures=W/'targeted_fixtures'
usage=f'''本包只是 A10_PV_HANDOFF_CPU_REPAIR_V1 的 CPU_READY。当前共享guard仍是原SHA，安装和V3计算均未授权。先由分析审阅 guard_patch/INSTALLATION_PROPOSAL.json、INSTALL_AND_ROLLBACK.md，独立授权安装并核验新SHA；本包真实sh不安装共享文件，也不重启daemon。

未来唯一计算身份：{identity['task_id']} / {identity['release_id']} / revision1。由 proposal/BOARD_TASK_TEMPLATE.json 原样构造board条目，status=ready；ACK后可running。真实release的status=released，当前RELEASE_TEMPLATE保持UNAUTHORIZED_TEMPLATE。CONTROL_REQUIRED中active_occupancy_handoff、提案、release、CONFIG必须使用同一HANDOFF_SPEC。旧七release保留关闭。

分析发布前对暂存JSON的核对命令（替换三个JSON路径；只读小metadata/manifest，不验证已安装共享字节、不加载模型/驱动、不写claim）：

```sh
/usr/bin/python3 -I -S -B {checker} \\
  --control /path/to/staged_CONTROL.json \\
  --board /path/to/staged_TASK_BOARD.json \\
  --release-json /path/to/staged_RELEASE.json \\
  --release-path {identity['release_path']} \\
  --host {identity['owner_host']}
```

本次已通过的纯JSON fixture 命令：

```sh
/usr/bin/python3 -I -S -B {checker} \\
  --control {fixtures/'CONTROL_CANDIDATE.json'} \\
  --board {fixtures/'TASK_BOARD_CANDIDATE.json'} \\
  --release-json {fixtures/'RELEASE_CANDIDATE.json'}
```

PASS_METADATA_ONLY_NOT_AUTHORIZATION只表示拟发布元数据一致，不是安装/计算授权或GPU实测成功。入口复用实际validate_metadata，并核对小manifest SHA、完整V3身份与run/wave/shard、handoff spec和两个manifest内的未来guard引用；不会跟随模型/代码/库条目。guard安装后的真实SHA还须由独立安装结果及真实入口完整检查确认；当前原文件不应被这个只读JSON检查改动。

未来唯一真实命令（仅在独立安装与计算授权条件齐全后）：

```sh
bash {identity['command_path']} {identity['release_path']}
```

cwd=`{P}`。冻结sh显式export CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300；launcher先通过完整SHA检查，再在父NVML前检查实际环境，child_environment保持该值，原lifecycle active分支传给新run客户端。缺失/错值不回落90，未装或错patch在完整输入/外部SHA检查处拒绝。默认90只保留给不使用V3合同的其他guard客户端；GPU_HOLDER_STOP_TIMEOUT_SECONDS不能替代此参数。

handoff300为单独名义空GPU等待，父层hash、锁等待、1800+30诊断、组清理与holder恢复各有原作用域。守门轮询只复用原query，失败最多记录一条JSON及最后64行NVML host PID，保留实际查询起止而非伪造deadline采样；查询失败不当空GPU。每poll一次原nvidia-smi，名义最多300个尝试，独立于父1+子1的身份核验计数，不叠加进66项模型/辅助caps；持久daemon轮询和holder负载亦单列范围。

数值算法、step0/raw50/noise、单帧mask、encoder/Q/PCA/norm、严格载入、独立自身半径、66caps及私有账本原样保留。诊断缓存Post0/Velocity1不等于部署Post1/Velocity2。所有当前fake/安装模板均不是实测，不自动进入下一阶段。
'''
write(P/'PUBLICATION_CHECK_USAGE.md',usage)
put(P/'PROPOSED_COMMAND.json',dict(status='proposed_not_authorized',task_id=identity['task_id'],release_id=identity['release_id'],revision=1,cwd=str(P),argv=['bash',identity['command_path'],identity['release_path']],command=ref(Path(identity['command_path'])),required_installed_guard_sha256=spec['guard_expected_sha256'],required_environment={spec['environment_variable']:spec['required_value']},claim_path=identity['claim_path'],output_directory=str(Path(identity['output_root'])/identity['run_id']),cache_directory=str(Path(identity['cache_root'])/identity['run_id']),actual_command_or_claim_count=0,automatic_installation=False))

now=datetime.datetime.now(datetime.timezone.utc).isoformat()
put(W/'FINAL_CPU_AUDIT.json',dict(status='passed',audited_at_utc=now,CONTROL_revision=27,TASK_BOARD_revision=34,current_state_snapshot_hashes_unchanged=True,current_shared_guard_SHA=patch['original_shared_sha256'],expected_future_guard_SHA=spec['guard_expected_sha256'],shared_installations=0,daemon_restarts=0,current_holder_GPU_queries_stops=0,current_real_launcher_claim_or_live_signals=0,code_files_SHA_verified=381,small_proposal_refs_verified=6,caps_unchanged=66,board_same_source=True,board_status='ready',current_template_status='UNAUTHORIZED_TEMPLATE',runtime_expected_guard_rows=2,both_expected_guard_rows_use_only_new_SHA=True,guard_fake_cases=26,metadata_cases=10,environment_and_manifest_cases_passed=True,installation_metadata_cases=6,changed_AST_and_shell_passed=True,large_weight_hashes=0,whole_algorithm_suite_runs=0,deletions=0,future_release_claim_output_cache_absent=True,publication_helper_is_CPU_only=True,future_installation_and_compute_require_independent_analysis_release=True))
ready=dict(status='CPU_READY',task_id=TASK,revision=1,prepared_at_utc=now,publication_is_authorization=False,actual_execution_authorized=False,shared_installation_authorized=False,shared_patch_installed=False,daemon_restart_required=False,next_task_id=identity['task_id'],next_release_id=identity['release_id'],next_task_revision=1,runtime_prerequisites_pending=['Analysis independently authorizes exact shared guard file installation, verifies newSHA; do not restart daemon','Analysis independently publishes V3 compute release and same-source ready board/control metadata'],known_new_numeric_input_blockers=[],proposal=ref(P/'proposal/PROPOSAL.json'),release_template=ref(P/'proposal/RELEASE_TEMPLATE.json'),control_required=ref(P/'proposal/CONTROL_REQUIRED.json'),board_task_template=ref(P/'proposal/BOARD_TASK_TEMPLATE.json'),identity=ref(P/'proposal/IDENTITY.json'),patch_identity=ref(P/'guard_patch/PATCH_IDENTITY.json'),patch=ref(P/'guard_patch/gpu_occupancy_guard.patch'),installation_proposal=ref(P/'guard_patch/INSTALLATION_PROPOSAL.json'),operation_quote=ref(P/'guard_patch/HANDOFF_OPERATION_QUOTE.json'),code=ref(P/'code/CODE_MANIFEST.json'),config=ref(P/'config/CONFIG.json'),inputs=ref(P/'INPUT_MANIFEST.json'),external_sources=ref(P/'EXTERNAL_SOURCE_MANIFEST.json'),publication_checker=ref(checker),publication_usage=ref(P/'PUBLICATION_CHECK_USAGE.md'),targeted_tests=ref(W/'TARGETED_FAKE_RESULT.json'),changed_integration_tests=ref(W/'CHANGED_INTEGRATION_AND_SYNTAX_CHECKS.json'),diff_manifest=ref(P/'DIFF_MANIFEST.json'),audit=ref(W/'FINAL_CPU_AUDIT.json'),actual_counts=ack['limits'])
put(P/'CPU_READY.json',ready)

report=f'''A10_PV_HANDOFF_CPU_REPAIR_V1 / revision1 已完成CPU_READY。当前CONTROL27/TASK_BOARD34、共享guard和旧包/回执未改；无安装、daemon重启、holder查询/停止、真实launcher/claim/GPU或模型调用。V3计算和共享安装均待分析独立授权。

最小补丁只改变新run客户端等待：CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS接受ASCII整数1..300，未设仍90；本V3固定300，非法值在start/锁/query前拒绝。300来自8×(15+5)=160加140秒调度/轮询余量；query仍原15秒timeout，超时后才返回空也不启动，非端到端上界。daemon全部函数及run的spawn/信号/等待/锁尾部字节未改。未来沿用原lifecycle active路径、同一formal.lock及继承FD，无嵌套预约/释放重拿；无需重启daemon。GPU_HOLDER_STOP_TIMEOUT_SECONDS未用作修复。

- 唯一未来共享替换路径：`{spec['guard_path']}`。
- 原SHA：`{patch['original_shared_sha256']}`。
- 新SHA：`{spec['guard_expected_sha256']}`。
- 精确patch、原字节回退、安装/回退命令和独立未授权模板位于 guard_patch/；INSTALLATION_PROPOSAL列出前置SHA/CONTROL及原子替换范围。当前只准备，真实sh不安装共享文件。

V3：{identity['task_id']} / {identity['release_id']} / revision1；新包 `{P}`。PROPOSAL SHA=`{ref(P/'proposal/PROPOSAL.json')['sha256']}`。run/wave/shard/claim/output/cache独立；board ready、正式release released、当前模板UNAUTHORIZED_TEMPLATE同源。INPUT与EXTERNAL两处guard引用均只预期新SHA；原SHA仅用于安装前比对/回退。sh显式export300，实际launcher在父NVML前校验环境，原lifecycle传给新run客户端；缺参数或未装预期补丁会拒绝。

381份运行代码中377份沿用字节不变，3份仅改身份/路径和handoff守门，新增1份纯元数据helper；诊断run数值函数字节不变。所有其他input/external条目、数值CONFIG字段、66caps、step0/raw50/noise/encoder/Q/PCA/norm、严格载入、独立自身半径、父子私有账本与1800+30诊断timeout保持。未读模型/数组/外部库字节，未hash大权重或重跑算法全套。

26个guard fake通过：120秒清空时旧90拒绝/新300只启动1次；持续外部占用、driver异常、无效值、晚返回空拒绝；原锁和继承FD覆盖组退出，TERM/KILL及信号转发只触及fake自有组。10个元数据case、实际环境/manifest临时fixture、6个安装/回退纯元数据case、发布CLI及变更AST/bash-n通过。无真实guard导入、formal.lock、进程信号、GPU/holder操作或安装入口main调用。

失败证据仅复用原poll最后观测，最多1条JSON/64行NVML host PID、错误2048字符；记录查询起止、尝试数，缺观测null，不伪称deadline新快照或container PID。run-client轮询独立于66caps中的身份核验父1+子1；名义最多300个尝试，无额外query。继承V2失败的其他原因未被新实测排除，本次无数值/硬件成功结论。短报告及manifest随RESULT；等待分析决定安装和计算后续授权，B不变、删除0。
'''
report_path=RCP/f'{TASK}_REPORT.md';write(report_path,report)
evidence_paths=[]
for x in sorted(P.rglob('*')):
    if x.is_file() and (not x.is_relative_to(P/'code') or x.name=='CODE_MANIFEST.json'):evidence_paths.append(x)
evidence_paths.extend(x for x in sorted(W.rglob('*')) if x.is_file())
evidence_paths.extend([RCP/f'{TASK}_ACK.json',report_path])
manifest=P/'EVIDENCE_MANIFEST.json'
put(manifest,dict(schema='CPU_handoff_patch_evidence_v1',task_id=TASK,files=[ref(x) for x in evidence_paths],runtime_code_manifest=ref(P/'code/CODE_MANIFEST.json'),runtime_code_files=381,self_and_RESULT_excluded=True,queue_delivery_separate=True,retention='All new evidence and fake fixtures retained; no deletion'))
paths=[report_path,P/'CPU_READY.json',P/'proposal/PROPOSAL.json',P/'proposal/RELEASE_TEMPLATE.json',P/'proposal/CONTROL_REQUIRED.json',P/'proposal/BOARD_TASK_TEMPLATE.json',P/'proposal/IDENTITY.json',P/'PROPOSED_COMMAND.json',P/'commands/run_proposed_pv_offline.sh',checker,P/'PUBLICATION_CHECK_USAGE.md',P/'guard_patch/PATCH_IDENTITY.json',P/'guard_patch/gpu_occupancy_guard.original.py',P/'guard_patch/gpu_occupancy_guard.patched.py',P/'guard_patch/gpu_occupancy_guard.patch',P/'guard_patch/HANDOFF_SPEC.json',P/'guard_patch/HANDOFF_OPERATION_QUOTE.json',P/'guard_patch/INSTALLATION_PROPOSAL.json',P/'guard_patch/INSTALL_AND_ROLLBACK.md',P/'guard_patch/INSTALL_RELEASE_TEMPLATE.json',P/'guard_patch/ROLLBACK_RELEASE_TEMPLATE.json',P/'commands/transition_guard_file_cpu.py',P/'code/CODE_MANIFEST.json',P/'config/CONFIG.json',P/'INPUT_MANIFEST.json',P/'EXTERNAL_SOURCE_MANIFEST.json',P/'DERIVATION.json',P/'DIFF_MANIFEST.json',W/'V2_TO_V3.diff',W/'GUARD_PATCH_STATIC_CHECKS.json',W/'NUMERIC_AND_LIFECYCLE_PRESERVATION.json',W/'TARGETED_FAKE_RESULT.json',W/'CHANGED_INTEGRATION_AND_SYNTAX_CHECKS.json',W/'FINAL_CPU_AUDIT.json',manifest]
result=dict(campaign_id='corrector-sim-20260919',task_id=TASK,revision=1,role='A',hostname=platform.node(),session_id=ack['session_id'],status='complete',outcome='CPU_READY_private_handoff_patch_and_V3_proposal_not_installed_or_authorized',started_at_utc=ack['acknowledged_at_utc'],finished_at_utc=now,input_identity=dict(CPU_release=ack['CPU_release'],control_revision=27,task_board_revision=34,source_proposal=ref(OLD/'proposal/PROPOSAL.json'),source_code=ref(OLD/'code/CODE_MANIFEST.json')),artifacts=[ref(x) for x in paths],resource_counts=ack['limits'],holder_queried=False,holder_stopped=False,shared_file_installations=0,daemon_restarts=0,real_process_signals=0,actual_compute_release_claims=0,actual_real_launcher_invocations=0,large_model_hash_passes=0,old_receipts_modified=False,analysis_control_or_board_modified=False,failures_and_retries=[],findings=dict(guard_original_SHA=patch['original_shared_sha256'],guard_patched_SHA=spec['guard_expected_sha256'],default_timeout_seconds=90,V3_timeout_seconds=300,guard_patch_installed=False,code_files=381,unchanged_copied_code_files=377,changed_existing_runtime_files=['core/contracts.py','launch.py','diagnostic.py'],added_runtime_file='core/handoff.py',caps_unchanged=66,guard_fake_cases=26,metadata_cases=10,installation_metadata_cases=6,whole_algorithm_suite_runs=0,new_numeric_validation=False),runtime_prerequisites_pending=ready['runtime_prerequisites_pending'],next_task_proposal=dict(task_id=identity['task_id'],release_id=identity['release_id'],revision=1,proposal=ref(P/'proposal/PROPOSAL.json'),requires_separate_patch_installation_authorization=True,requires_independent_compute_release=True,authorized_now=False),publication_is_authorization=False,retained_evidence_files=len(evidence_paths),retained_runtime_code_files=381,deletions=0)
result_path=RCP/f'{TASK}_RESULT.json';put(result_path,result)
for row in result['artifacts']+read(manifest)['files']:assert ref(Path(row['path']))==row
for x in P.rglob('*'):
    if x.is_file():x.chmod(0o555 if x.suffix=='.sh' else 0o444)
report_path.chmod(0o444);result_path.chmod(0o444)
print(json.dumps(dict(status='CPU_READY',RESULT=ref(result_path),REPORT=ref(report_path),CPU_READY=ref(P/'CPU_READY.json'),PROPOSAL=ref(P/'proposal/PROPOSAL.json'),artifact_refs=len(paths),evidence_files=len(evidence_paths),code_files=381,current_shared_guard_SHA=patch['original_shared_sha256'],future_installed_guard_SHA=spec['guard_expected_sha256'],shared_installations=0,compute_authorized=False),indent=2))
