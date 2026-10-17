"""Seal this CPU metadata task's small evidence and receipts only."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import platform

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK = 'A10_PV_AUTH_METADATA_CPU_V1'
NEW = B/'results/A'/TASK
OLD = B/'results/A/A10_PV_OFFLINE_PREFLIGHT_CPU_V1'
WORK = B/'work/A'/f'{TASK}_r1'
RECEIPTS = B/'receipts/A'

def read(path):
    return json.loads(path.read_text())

def sha(path):
    assert path.stat().st_size < 2*1024*1024, str(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()

def ref(path):
    return dict(path=str(path),sha256=sha(path),size_bytes=path.stat().st_size)

def put(path,obj):
    with path.open('x') as f:
        f.write(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

def write(path,text):
    with path.open('x') as f:
        f.write(text)

ack=read(RECEIPTS/(TASK+'_ACK.json'))
identity=read(NEW/'proposal/IDENTITY.json')
p=read(NEW/'proposal/PROPOSAL.json')
release=read(NEW/'proposal/RELEASE_TEMPLATE.json')
required=read(NEW/'proposal/CONTROL_REQUIRED.json')
board=read(NEW/'proposal/BOARD_TASK_TEMPLATE.json')
tests=read(WORK/'METADATA_FIXTURE_RESULT.json')
checks=read(WORK/'IDENTITY_CHANGE_STATIC_CHECKS.json')
assert tests['status']=='passed' and checks['diagnostic_run_function_byte_identical']
assert board==required['board_task'] and board['status']=='ready' and release['status']=='UNAUTHORIZED_TEMPLATE'
assert p['resource_caps']==read(OLD/'proposal/PROPOSAL.json')['resource_caps']
assert p['resource_caps']==release['resource_caps']==required['current_compute_limits']==required['per_task_compute_limits'][identity['task_id']]
for rel,row in ack['input_snapshots'].items():
    assert sha(B/rel)==row['sha256'], rel
assert platform.node()==identity['owner_host']
assert not Path(identity['release_path']).exists(), 'Unexpected future compute publication; stop CPU publication for review'
assert not Path(identity['claim_path']).exists()
assert not (Path(identity['output_root'])/identity['run_id']).exists()
assert not (Path(identity['cache_root'])/identity['run_id']).exists()

source_files=[OLD/'proposal/PROPOSAL.json',OLD/'code/CODE_MANIFEST.json',OLD/'config/CONFIG.json',OLD/'INPUT_MANIFEST.json',OLD/'EXTERNAL_SOURCE_MANIFEST.json',B/'manifests/PV_OFFLINE_PREFLIGHT_CPU_V1_ACCEPTANCE.json',B/'manifests/A_PV_OFFLINE_PREFLIGHT_V1_FAILURE_ACCEPTANCE.json',B/'releases/P10_A_PV_OFFLINE_PREFLIGHT_V1_CLOSED.json',B/'contracts/TASK_STATE_CONTRACT_V1.md']
put(NEW/'DERIVATION.json',dict(source_package=str(OLD),source_references=[ref(x) for x in source_files],scope='Independent V2 authorization identity, package/output/claim/cache paths and publishing metadata only',input_SHA_provenance='Copied accepted input/external manifests byte for byte; no referenced model, encoder, Q, projection, binary or saved array bytes read',old_package_and_receipts_mutations=0,algorithm_changes=0,config_changes=0,source_noise_changes=0,cap_changes=0,new_algorithm_validation=False,code_changed_files=['core/contracts.py','launch.py','diagnostic.py'],code_changed_operations='Declared string constants only; normalized AST equal',diagnostic_run_function_byte_identical=True,claim_function_invocations=0,CPU_limits_release=ref(B/'releases/P00_PV_AUTH_METADATA_CPU_V1.json')))

checker=NEW/'commands/check_publication_metadata_cpu.py'
fixture=WORK/'metadata_fixtures'
usage=f'''本入口只做发布前的小 JSON 元数据核对，不授权计算。用同源 `proposal/BOARD_TASK_TEMPLATE.json`（完整条目，status=ready）和 `CONTROL_REQUIRED.json` 构造待发布 CONTROL/board；未来真实 release 的 status 才是 released。保持已关闭记录。release/run/wave/shard 使用 `proposal/IDENTITY.json`，revision=1。

尚未授权的 `RELEASE_TEMPLATE.json` 保持 UNAUTHORIZED_TEMPLATE；不要直接运行真实 sh。分析端可在自己的暂存目录生成拟发布 JSON：候选 release.status=released，拟发布 board.status=ready，其余身份/66 项 caps/五项 SHA 从本包复制。通过检查仍不等于发放计算 release。

对分析端暂存文件的用法（替换三个 JSON 文件路径）：

```sh
/usr/bin/python3 -I -S -B {checker} \\
  --control /path/to/staged_CONTROL.json \\
  --board /path/to/staged_TASK_BOARD.json \\
  --release-json /path/to/staged_RELEASE.json \\
  --release-path {identity['release_path']} \\
  --host {identity['owner_host']}
```

本次实际通过的纯 CPU fixture 命令（仅保留作复核入口，无需重跑整套）：

```sh
/usr/bin/python3 -I -S -B {checker} \\
  --control {fixture/'CONTROL_CANDIDATE.json'} \\
  --board {fixture/'TASK_BOARD_CANDIDATE.json'} \\
  --release-json {fixture/'RELEASE_CANDIDATE.json'}
```

入口复用新包的实际 `core.contracts.validate_metadata`；额外核对 config/input/code/external/identity 小 JSON 的 SHA 与大小、config 设备/可见性/timeout、board/release/IDENTITY 的 run/wave/shard 以及命令元数据。每份 JSON 最多读取 1 MiB，不跟随 manifest 内的代码、模型、数组或外部库条目；只输出 stdout，不写 claim、文件或启动任何子进程。默认主机来自平台主机名，也可用 --host 核对声明的 A 主机；该结果不证明 GPU 实物状态。闭包文件与 CONTROL closed 表保留拒绝语义。

退出码 0 为 PASS_METADATA_ONLY_NOT_AUTHORIZATION；退出码 2 为拒绝。board=running 只为 ACK 后状态兼容，初始发布必须用同源 ready 条目；board=released 会拒绝。JSON fixture 内的 released 只是假数据，位于 work/A，不是 releases/ 下的真实 release。

未来唯一真实命令如下，当前未执行，必须由分析另发 V2 release：

```sh
bash {identity['command_path']} {identity['release_path']}
```

cwd：`{NEW}`。不额外跑硬件探针或完整 CPU checker；正式入口沿用原完整检查和全 8 holder 生命周期。子进程 timeout 1800 秒、TERM 后 30 秒 KILL；整组清理与恢复保持既有边界，不声称端到端 1830 秒硬上限。
'''
write(NEW/'PUBLICATION_CHECK_USAGE.md',usage)
put(NEW/'PROPOSED_COMMAND.json',dict(status='proposed_not_authorized',task_id=identity['task_id'],release_id=identity['release_id'],revision=1,cwd=str(NEW),argv=['bash',identity['command_path'],identity['release_path']],command=ref(Path(identity['command_path'])),claim_path=identity['claim_path'],output_directory=str(Path(identity['output_root'])/identity['run_id']),cache_directory=str(Path(identity['cache_root'])/identity['run_id']),actual_invocations=0))

manifest=read(NEW/'code/CODE_MANIFEST.json')
for row in manifest['files']:
    f=NEW/'code'/row['path']
    assert ref(f)['sha256']==row['sha256'] and f.stat().st_size==row['size_bytes']
for key in ['config','input_manifest','code_manifest','external_sources','command','authorization_identity']:
    assert ref(Path(p[key]['path']))==p[key]
assert release['proposal_sha256']==sha(NEW/'proposal/PROPOSAL.json')
assert all(row['actual']==row['expected'] for row in tests['pure_validator_cases'])
ast.parse(Path(__file__).read_text())
put(WORK/'FINAL_CPU_AUDIT.json',dict(status='passed',control_revision=24,task_board_revision=31,current_control_and_board_unchanged=True,ack_snapshot_refs_unchanged=len(ack['input_snapshots']),future_release_exists=False,future_claim_exists=False,future_run_output_exists=False,code_manifest_files_verified=len(manifest['files']),new_small_proposal_refs_verified=6,template_proposal_SHA_matches=True,board_same_source=True,board_status='ready',real_release_required_status='released',template_status='UNAUTHORIZED_TEMPLATE',caps_entries_exact_equal_to_accepted_V1=len(p['resource_caps']),validator_cases=len(tests['pure_validator_cases']),guard_checks=len(tests['authorization_guard_checks']),publication_helper_checks=2,publication_CLI_fixture_check=1,finalizer_AST_parsed=True,all_model_binary_array_hashes_or_reads=0,holder_queries_or_stops=0,real_launcher_or_claim_function_invocations=0,whole_algorithm_suite_runs=0,deletions=0))

now=datetime.datetime.now(datetime.timezone.utc).isoformat()
ready=dict(status='CPU_READY',task_id=TASK,revision=1,prepared_at_utc=now,actual_execution_authorized=False,publication_is_authorization=False,next_task_id=identity['task_id'],next_release_id=identity['release_id'],next_task_revision=1,board_status='ready',release_status_after_independent_analysis_publication='released',known_blockers=[],required_next_action='Analysis review and independent V2 compute release; current CPU task grants no command opportunity',proposal=ref(NEW/'proposal/PROPOSAL.json'),release_template=ref(NEW/'proposal/RELEASE_TEMPLATE.json'),control_required=ref(NEW/'proposal/CONTROL_REQUIRED.json'),board_task_template=ref(NEW/'proposal/BOARD_TASK_TEMPLATE.json'),identity=ref(NEW/'proposal/IDENTITY.json'),code=ref(NEW/'code/CODE_MANIFEST.json'),config=ref(NEW/'config/CONFIG.json'),inputs=ref(NEW/'INPUT_MANIFEST.json'),external_sources=ref(NEW/'EXTERNAL_SOURCE_MANIFEST.json'),publication_checker=ref(checker),publication_checker_usage=ref(NEW/'PUBLICATION_CHECK_USAGE.md'),targeted_tests=ref(WORK/'METADATA_FIXTURE_RESULT.json'),diff_manifest=ref(NEW/'DIFF_MANIFEST.json'),audit=ref(WORK/'FINAL_CPU_AUDIT.json'),actual_counts=dict(torch_imports=0,driver_dlopen=0,NVML_CUDA_EGL_calls=0,model_forward_backward=0,environment_reset_render_physics=0,real_launcher_invocations=0,compute_release_claims=0,holder_queries_stops=0,large_weight_hashes=0,deletions=0),runtime_validation_pending=p['unvalidated'])
put(NEW/'CPU_READY.json',ready)

report=f'''A10_PV_AUTH_METADATA_CPU_V1 / revision1 已完成，CPU_READY；当前 CONTROL24/TASK_BOARD31 及全部零计算额度未改。新包：`{NEW}`。

未来身份固定为 `{identity['task_id']}` / `{identity['release_id']}` / revision1；完整 `BOARD_TASK_TEMPLATE.json` 与 `CONTROL_REQUIRED.board_task` 同源且逐项相等，初始 board.status=ready（冻结入口亦接受 ACK 后 running），未来 release.status=released。当前 RELEASE_TEMPLATE.status=UNAUTHORIZED_TEMPLATE，V2 真实 release 不存在，真实命令/claim=0。

- 新 PROPOSAL SHA256：`{sha(NEW/'proposal/PROPOSAL.json')}`。
- 新 CODE_MANIFEST SHA256：`{sha(NEW/'code/CODE_MANIFEST.json')}`。
- 新 RELEASE_TEMPLATE SHA256：`{sha(NEW/'proposal/RELEASE_TEMPLATE.json')}`。
- `{identity['run_id']}`、`{identity['wave_id']}`、`{identity['shard_id']}`；claim/output/cache 均采用独立 P10_PV_V2 路径，见 PROPOSED_COMMAND.json。

380 份运行代码中 377 份字节不变；仅 contracts/launch/diagnostic 三文件改身份或路径字符串，归一化 AST 相等，diagnostic.run 源码字节不变。sh 仅改包根。输入清单、外部源清单、CONFIG 字节不变，沿用已验收 SHA；未读取其模型/数组/外部库条目，未 hash 大权重。66 项 caps、step0/raw50/seed/noise、encoder/PCA/norm、严格载入、独立自身半径/只 C10/raw 尾部、私有父子账本、1800+30 子进程 timeout 和全 A8 holder 生命周期不变。逐文件证明见 DIFF_MANIFEST，精确补丁见 work/A/{TASK}_r1/RUNTIME_IDENTITY_PATH.diff 和 AUTHORIZATION_METADATA.diff。

41 项定向实际元数据函数 fixture 全符合预期：ready/running 通过；released、旧 V1、错 active identity/path/caps/revision、五项 SHA、host/device/cuda/timeout 拒绝。另验证关闭文件及独占写入重复拒绝；重复保护仅对已有临时标记调用实际 write_new，并核对 claim 的调用 AST，claim 函数从未执行。纯 JSON 发布入口 2 项检查及实际 CLI fixture 通过；变更 AST 与 bash -n 通过，未重跑完整算法/fake 套件。用法见 PUBLICATION_CHECK_USAGE.md；它不跟随大文件引用、不发放授权。

未来单次预算仍 1 offline attempt / 1 guided / 10 flow，Post1 + Velocity3 动作梯度，10 ensemble / 40 成员前向，完整 66 项及父子分账沿用原提案。缓存诊断 Post0/Velocity1 不能充当部署成本 Post1/Velocity2。数值行为仍待验证；历史五任务 Q 的适用范围未扩大。

本任务 Torch/dlopen/NVML/CUDA/EGL、模型/梯度、环境/reset/render/物理/训练、真实 launcher/claim、holder 查询/停止、删除均 0。旧包/回执未改，B 不变。本次只提交 CPU_READY 与未授权 V2 提案，等待分析独立 release；V1 仍为命令1、claim0、计算0、holder未停的已关闭证据。
'''
report_path=RECEIPTS/(TASK+'_REPORT.md')
write(report_path,report)

evidence_paths=[]
for f in sorted(NEW.rglob('*')):
    if f.is_file() and (not f.is_relative_to(NEW/'code') or f.name=='CODE_MANIFEST.json'):
        evidence_paths.append(f)
evidence_paths.extend(x for x in sorted(WORK.rglob('*')) if x.is_file())
evidence_paths.extend([RECEIPTS/(TASK+'_ACK.json'),report_path])
evidence=NEW/'EVIDENCE_MANIFEST.json'
put(evidence,dict(schema='CPU_metadata_evidence_v1',task_id=TASK,files=[ref(x) for x in evidence_paths],runtime_code_manifest=ref(NEW/'code/CODE_MANIFEST.json'),runtime_code_files=len(manifest['files']),self_and_result_excluded=True,queue_delivery_separate=True,retention='All task evidence and synthetic fixtures retained; deletions zero'))
artifact_paths=[report_path,NEW/'CPU_READY.json',NEW/'proposal/PROPOSAL.json',NEW/'proposal/RELEASE_TEMPLATE.json',NEW/'proposal/CONTROL_REQUIRED.json',NEW/'proposal/BOARD_TASK_TEMPLATE.json',NEW/'proposal/IDENTITY.json',NEW/'PROPOSED_COMMAND.json',NEW/'commands/run_proposed_pv_offline.sh',checker,NEW/'PUBLICATION_CHECK_USAGE.md',NEW/'code/CODE_MANIFEST.json',NEW/'config/CONFIG.json',NEW/'INPUT_MANIFEST.json',NEW/'EXTERNAL_SOURCE_MANIFEST.json',NEW/'DERIVATION.json',NEW/'DIFF_MANIFEST.json',WORK/'RUNTIME_IDENTITY_PATH.diff',WORK/'AUTHORIZATION_METADATA.diff',WORK/'METADATA_FIXTURE_RESULT.json',WORK/'IDENTITY_CHANGE_STATIC_CHECKS.json',WORK/'TARGETED_SYNTAX_CHECKS.json',WORK/'PUBLICATION_CHECK_CLI_RESULT.json',WORK/'FINAL_CPU_AUDIT.json',evidence]
result=dict(campaign_id='corrector-sim-20260919',task_id=TASK,revision=1,role='A',hostname=platform.node(),session_id='01a0b91f-7443-71b1-915d-6cdb6d6a1a13',status='complete',outcome='CPU_READY_V2_auth_metadata_only_compute_not_authorized',started_at_utc=ack['acknowledged_at_utc'],finished_at_utc=now,input_identity=dict(cpu_release=ack['release'],control_revision=24,task_board_revision=31,state_contract=ref(B/'contracts/TASK_STATE_CONTRACT_V1.md'),source_proposal=ref(OLD/'proposal/PROPOSAL.json'),source_code=ref(OLD/'code/CODE_MANIFEST.json')),artifacts=[ref(x) for x in artifact_paths],resource_counts=ack['current_limits'],holder_queried=False,holder_stopped=False,large_model_hash_passes=0,actual_compute_release_claims=0,actual_real_launcher_invocations=0,old_receipts_modified=False,analysis_control_or_board_modified=False,failures_and_retries=[],findings=dict(board_status='ready',real_release_status='released',current_template_status='UNAUTHORIZED_TEMPLATE',code_files=380,byte_identical_code_files=377,changed_runtime_files=['core/contracts.py','launch.py','diagnostic.py'],changes='identity/path strings only',caps_preserved=66,metadata_validator_cases=41,guard_checks=3,publication_entry_checks=2,publication_CLI_fixture_checks=1,claim_function_invocations=0,algorithm_tests_repeated=0,new_numeric_validation=False),blockers=[],runtime_validation_pending=p['unvalidated'],next_task_proposal=dict(task_id=identity['task_id'],release_id=identity['release_id'],revision=1,proposal=ref(NEW/'proposal/PROPOSAL.json'),requires_independent_analysis_release=True,authorized_now=False),publication_is_authorization=False,retained_evidence_files=len(evidence_paths),retained_runtime_code_files=len(manifest['files']))
result_path=RECEIPTS/(TASK+'_RESULT.json')
put(result_path,result)
for row in result['artifacts']:
    assert ref(Path(row['path']))==row
for row in read(evidence)['files']:
    assert ref(Path(row['path']))==row
for f in NEW.rglob('*'):
    if f.is_file():
        f.chmod(0o555 if f.suffix=='.sh' else 0o444)
report_path.chmod(0o444)
result_path.chmod(0o444)
print(json.dumps(dict(status='CPU_READY',result=ref(result_path),report=ref(report_path),CPU_READY=ref(NEW/'CPU_READY.json'),proposal=ref(NEW/'proposal/PROPOSAL.json'),artifacts=len(result['artifacts']),evidence_files=len(evidence_paths),code_files=len(manifest['files']),compute_authorized=False),indent=2))
