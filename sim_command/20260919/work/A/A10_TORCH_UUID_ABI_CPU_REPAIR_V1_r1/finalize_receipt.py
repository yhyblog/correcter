from pathlib import Path
import datetime
import hashlib
import json
import os
import socket

B = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK = 'A10_TORCH_UUID_ABI_CPU_REPAIR_V1'
P, W = B/'results/A'/TASK, B/'work/A'/f'{TASK}_r1'
R = B/'receipts/A'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path)
    return dict(path=str(path), sha256=sha(path), size_bytes=path.stat().st_size)


def write(path, value):
    path = Path(path)
    assert not path.exists(), 'Final publication cannot overwrite: ' + str(path)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, path)


ack = read(R/f'{TASK}_ACK.json')
audit = read(W/'FINAL_CPU_AUDIT.json')
tests = read(W/'targeted_tests_01/TEST_RESULT.json')
proposal = read(P/'proposal/PROPOSAL.json')
assert audit['status'] == tests['status'] == 'passed' and tests['passed'] == 50
assert not (R/f'{TASK}_RESULT.json').exists()
ready = dict(task_id=TASK, task_revision=1, status='CPU_READY_NOT_COMPUTE_AUTHORIZED',
    proposal=ref(P/'proposal/PROPOSAL.json'), release_template=ref(P/'proposal/RELEASE_TEMPLATE.json'),
    control_required=ref(P/'proposal/CONTROL_REQUIRED.json'), code_manifest=ref(P/'code/CODE_MANIFEST.json'),
    integration_manifest=ref(P/'INTEGRATION_MANIFEST.json'), external_source_manifest=ref(P/'EXTERNAL_SOURCE_MANIFEST.json'),
    ABI_source_review=ref(P/'ABI_SOURCE_REVIEW.json'), CPU_checks=ref(W/'FINAL_CPU_AUDIT.json'),
    targeted_test_result=ref(W/'targeted_tests_01/TEST_RESULT.json'),
    real_command=proposal['real_command'], CPU_authorization_command=proposal['cpu_authorization_command'],
    real_command_executed=False, targeted_cases_passed=50, current_actual_resource_counts=audit['resource_counts'],
    holder_queried=False, holder_stopped=False, old_V2_runtime_uuid_type=None,
    old_V2_runtime_uuid_type_status='unknown; no backfill', native_runtime_validated=False,
    release_required='New analysis P10_A_NATIVE_PREFLIGHT_V3 plus CONTROL/TASK_BOARD binding; no old quota reuse',
    no_additional_standalone_CPU_checker_before_real_launch=True, all_new_evidence_retained=True)
write(P/'CPU_READY.json', ready)
report = R/f'{TASK}_REPORT.md'
assert not report.exists()
report_text = f'''| 项目 | 可用 / 缺口 |
|---|---|
| 状态 | CPU 修正完成；native V3 仅提案，未授权、未执行 |
| ABI 依据 | 本地 Torch 2.7.1+cu126 / e2d141…：stub uuid:str；官方绑定 `_CUuuid` 与 `__str__`，直接绑定 properties.uuid |
| 最小差异 | 新快照 419 文件中 417 不变；仅 UUID 处理/证据及 V3 release 身份两文件变化 |
| UUID 合同 | 原生 str 或实际类 token 身份；可信非字符串转换一次；完整 ASCII UUID + 可选字面 GPU-，严格目标比较 |
| 证据 | properties 仍一次；转换前持久化原类型，决策前持久化转换/异常/格式/目标结果；旧运行具体类型仍未知 |
| CPU 检查 | 50/50 fake 与授权拒绝检查通过；新增 419 文件 SHA / 16 新集成引用核对，11 旧隔离库引用原样继承 |
| 本轮实际计算 | Torch import / 显式 dlopen / CUDA / EGL / NVML / 模型 / 环境 / reset / 训练 / 删除均 0；holder 未查询、未停止 |
| 待分析放行 | 固定 shelf-place 同源同 seed：1 attempt，5 native/50 flow，1 step/13 子步，2 张 corner2 RGB；52 reset/26000 初始化子步、108 显式 graphics 均不变 |

静态依据：[冻结源码核对]({P}/ABI_SOURCE_REVIEW.json)；[官方对应提交](https://raw.githubusercontent.com/pytorch/pytorch/e2d141dbde55c2a4370fac5165b0561b6af4798b/torch/csrc/cuda/Module.cpp)。静态绑定信息不替代旧运行未记录的对象类型。

[精确差异]({P}/UUID_ONLY_DIFF.patch) · [定向测试]({W}/targeted_tests_01/TEST_RESULT.json) · [CPU_READY]({P}/CPU_READY.json) · [V3 提案]({P}/proposal/PROPOSAL.json)。PROPOSAL SHA256 `{sha(P/'proposal/PROPOSAL.json')}`。

唯一真实入口：`{P}/commands/run_proposed_native_preflight.sh NEW_RELEASE_JSON`；纯 CPU 授权入口同目录 `check_authorization_cpu.sh NEW_RELEASE_JSON`。本轮两入口均未执行；真实入口自带完整 SHA，未来放行后无需额外 CPU checker。

独占 claim、A-only 全 8 holder 停至整个进程组退出（含失败）、1800+30 仅约束诊断子进程规则不变。完整 rollout/monitor/critic/反向/更新/重试/删除均 0，无独立 UUID 探针或球体渲染。旧包与回执不改，全部本轮证据保留。

公开源码首次数下载受沙箱 DNS 限制失败，取得网络权限后定向下载成功；这是 CPU 取证恢复，无计算重试。无工程阻塞；真实 native V3 结果仍须另行 release 后取得。
'''
temp = report.with_name(report.name + '.tmp'); temp.write_text(report_text); os.replace(temp, report)
write(W/'RETENTION.json', dict(task_id=TASK, retained_paths=[str(P), str(W), str(report), str(R/f'{TASK}_ACK.json'), str(R/f'{TASK}_RESULT.json')],
    scope='Only current-task artifacts and CPU fake evidence; no old inventory rescan',
    disposition='retained; any future delete/keep/defer decision belongs to analysis', deletions=0,
    temporary_artifacts_deleted=0, note='Publication temp files atomically rename to final identity; no retained evidence is discarded.'))

paths = sorted({p for root in [P, W] for p in root.rglob('*') if p.is_file()} | {report, R/f'{TASK}_ACK.json'})
write(W/'EVIDENCE_MANIFEST.json', dict(task_id=TASK, files=[ref(p) for p in paths],
    exclusions=['This manifest and RESULT cannot self-reference', 'Mutable task heartbeat',
                'Post-publication audit and queue message/delivery records appended after RESULT; retained in the same work directory'],
    model_weights_rehashed=False, no_deletions=True))
artifact_paths = [report, P/'CPU_READY.json', P/'proposal/PROPOSAL.json', P/'proposal/RELEASE_TEMPLATE.json',
    P/'proposal/CONTROL_REQUIRED.json', P/'code/CODE_MANIFEST.json', P/'INTEGRATION_MANIFEST.json',
    P/'EXTERNAL_SOURCE_MANIFEST.json', P/'config/INTEGRATION.json', P/'ABI_SOURCE_REVIEW.json',
    P/'DERIVATION.json', P/'UUID_ONLY_DIFF.patch', P/'UUID_REPAIR_NOTES.md',
    P/'commands/run_proposed_native_preflight.sh', P/'commands/check_authorization_cpu.sh',
    P/'tests/test_uuid_contract_cpu.py', W/'targeted_tests_01/TEST_RESULT.json', W/'FINAL_CPU_AUDIT.json',
    W/'RETENTION.json', W/'EVIDENCE_MANIFEST.json']
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
result = dict(campaign_id='corrector-sim-20260919', task_id=TASK, revision=1, role='A',
    hostname=socket.gethostname(), session_id=ack['executor_session_id'], status='complete',
    started_at_utc=ack['started_at_utc'], finished_at_utc=now,
    input_identity=dict(protocol=ack['inputs_checked'], code=ref(P/'code/CODE_MANIFEST.json'),
        config=ref(P/'config/INTEGRATION.json'), data=ref(P/'proposal/source_manifest.json'),
        model=dict(path=proposal['checkpoint'], sha256=proposal['model_sha256'],
            verification='Inherited accepted V2 identity; no weight bytes rehashed in this CPU task; future released entry must perform full verification'),
        external_sources=dict(manifest=ref(P/'EXTERNAL_SOURCE_MANIFEST.json'),
            verification='3133 accepted identities inherited; Torch stub/version only reread, version.py added; no other package scan')),
    artifacts=[ref(p) for p in artifact_paths], resource_counts=audit['resource_counts'],
    failures_and_retries=[dict(scope='CPU official-source fetch', failed_command='sandbox urllib.request.urlopen of the exact official Module.cpp URL',
        exit_code=1, reason='Sandbox DNS resolution failed', recovery='One approved network escalation fetched the exact public source; SHA recorded',
        evidence=ref(W/'SOURCE_FETCH_SANDBOX_FAILURE.txt'), compute_retries=0)],
    findings=[
        'Local stub annotates uuid:str; the corresponding official source registers _CUuuid, __str__, and direct properties.uuid binding.',
        'Only native str or exact trusted class-token identity is accepted; spoofed names, subclasses and arbitrary stringifiable objects are rejected.',
        'Trusted non-string UUID converts once; full ASCII canonical format and fixed target equality are required.',
        'Existing properties call remains one. Raw module/qualname persists before conversion; decision evidence persists before accept/refuse.',
        '50 targeted CPU cases pass, including conversion errors, evidence ordering, strict formatting, current/old/template release refusal.',
        '419 code files: two changed, 417 unchanged. Physical mapping, visibility, library route, sampler, claim/lifecycle and all compute caps unchanged.',
        'Old V2 runtime UUID object type remains unknown; no retrospective type inference or hardware probe.',
        'Native V3 is only an unauthorized proposal; no heavy imports, driver/GPU APIs, holder queries/stops, real entry or deletion executed.'
    ], blockers=[],
    next_task_proposal=dict(task_id='A10_PREFLIGHT_NATIVE_V3', release_id='P10_A_NATIVE_PREFLIGHT_V3',
        status='PROPOSED_NOT_AUTHORIZED', proposal=ref(P/'proposal/PROPOSAL.json'),
        prerequisites='Analysis acceptance plus a fresh compute release and matching CONTROL/TASK_BOARD',
        native_runtime_validated=False, auto_run=False),
    actual_compute_release_claims=0, old_receipts_modified=False, holder_queried=False, holder_stopped=False,
    retained_evidence_file_count=len(paths), publication_is_authorization=False)
write(R/f'{TASK}_RESULT.json', result)
hpath = B/'nodes/A'/f'{TASK}_HEARTBEAT.json'
h = read(hpath); h.update(status='complete', updated_at_utc=now, progress='RESULT published; CPU only, V3 not authorized', result=str(R/f'{TASK}_RESULT.json'))
tmp = hpath.with_name(hpath.name + '.tmp'); tmp.write_text(json.dumps(h, indent=2) + '\n'); os.replace(tmp, hpath)
print(json.dumps(dict(result=ref(R/f'{TASK}_RESULT.json'), report=ref(report),
    artifact_refs=len(artifact_paths), retained_evidence_files=len(paths), CPU_READY=ref(P/'CPU_READY.json')), indent=2))
