import datetime
import hashlib
import json
import os
from pathlib import Path
import platform

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORK = Path(__file__).resolve().parent
OUT = BASE / 'results/A/A10_PREFLIGHT_REVISION_R2'
RECEIPTS = BASE / 'receipts/A'
TASK = 'A10_PREFLIGHT_REVISION_R2'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return {'path': str(path), 'sha256': sha(path)}


def publish(path, value, replace=False):
    assert replace or not path.exists(), str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.pending')
    temp.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temp, path)


control = json.loads((BASE / 'CONTROL.json').read_text())
assert TASK in control['allowed_task_ids'] and not control['stop_requested']
assert control['current_compute_limits'] == {'training_updates': 0, 'model_gpu_inference_calls': 0, 'simulator_attempts': 0}
ack = json.loads((RECEIPTS / f'{TASK}_ACK.json').read_text())
for source in (WORK / 'evidence').iterdir():
    if source.is_file():
        publish(OUT / 'evidence' / source.name, source.read_text())
runtime = json.loads((OUT / 'evidence/runtime_targeted_checks.json').read_text())
assert runtime['returncode'] == 0 and '32 passed' in runtime['stdout']
proposal = json.loads((OUT / 'preflight_v4/PROPOSAL.json').read_text())
report = f'''# A10 预检修正 R2（CPU）

| 项目 | 结果 |
|---|---|
| 新版本 | `{OUT}/CPU_READY_v4.json`；code_snapshot_v4 / preflight_v4 / commands_v4 |
| 实例 / reset | 2个物理环境 +1个Python包装器；50 task-set +1包装初始化 +1诊断 reset=52 |
| 初始化物理工作 | 每个native reset两次reset_model，共104次；5,200次内部do_simulation ×5子步=26,000初始化子步 |
| 科学诊断范围 | 仍为1诊断初态/1attempt、5native采样/50flow、1策略控制步（13物理子步）；0完整rollout/反向/monitor/更新/重试 |
| CPU 验证 | 真实运行环境32项定向测试通过；413发布代码文件SHA、9个变更Python AST、2个shell语法、2份P00纯CPU拒绝检查通过 |
| 当前实际用量 | GPU推理、环境实例、reset、仿真attempt、训练、删除均0；8张H100 holder正常，guard PID27508 |

v3 原报1环境/1reset不成立，新报价保留标准 MT1 初始化。`preflight_v4/INITIALIZATION_STATIC_AUDIT.json` 给调用链与来源；`external_source_manifest.json` 绑定实际安装的 MetaWorld全部Python源码及相关Gymnasium代码/metadata，共118个文件。共享环境未改写。模型/数据和诊断初态身份不变，旧600源不重采。

新增私有初始化账本在构造/reset/reset_model/do_simulation之前检查预算、落盘entered，结束写returned/failed；实际进入数、返回数、来源及缺末事件分别保留。总reset和分来源reset是同一工作的统计维度，不能相加成更多episode。初始化物理子步包括诊断reset内的settling，不记成策略控制步；mj_forward、构造、render等开销覆盖在诊断墙钟里。成功路径与预算不符即失败；部分失败不退回已进入费用，不重试、不换初态。未来资源回执模板的未测实际数为null，当前CPU任务用量为0。

1800秒TERM +30秒KILL宽限仅包围诊断子进程，覆盖其再次输入hash、导入、模型加载、全部初始化、采样/单步及诊断收尾。前置CPU完整hash/NVML检查、预约与holder释放、wrapper启动、预约释放和恢复观察均在其外；1830不是端到端严格上界。新LAUNCH_RESULT逐段记实际时间，缺marker为null；恢复只读观察最多120秒，不停止外部作业。仍为A-only wave，整个本机wave所有holder停算；失败释放预约后由guard恢复。B正常occupancy不参与本波次。

分析端新release必填：`status=released`、唯一release/task/revision/run/shard/wave、A主机/实际GPU UUID/index/model/driver/runtime、proposal及code_manifest SHA、external_source_manifest SHA、resource_caps、initialization_caps、max_retries=0、timeout_seconds=1800、kill_grace_seconds=30、timeout_scope、wave_participants=[A]。精确值见 `preflight_v4/RELEASE_TEMPLATE.json`；CONTROL须登记active_compute_release_id/allowed_task_ids/mode及PROPOSAL的全部control_minimum_limits；TASK_BOARD须登记同一任务版本、owner=A、release路径及ready/released/running状态。任一身份、源SHA或预算漂移即拒绝。

纯CPU授权命令（新release填实后亦只读验证，不查NVML、不进入lifecycle）：
```bash
{OUT}/commands_v4/check_authorization_cpu.sh /absolute/path/to/new-compute-release.json
```
当前两份P00都返回预期exit2。真实命令为同目录 `run_proposed_native_preflight.sh NEW_RELEASE`，未执行，也不用它作为dry-run。一次完整weight SHA在预约前，另一次在受timeout约束的诊断进程内；合计至少18,708,101,504个hash输入字节，另有模型加载I/O。原40GiB显存/64GiB RAM/2GiB新磁盘仍为未实测估计。

旧interface_v1和A10 r1/v3保持不变；本轮接口计费补充见 `receipts/A/A10_INTERFACE_SEMANTICS_r1.md`，已queue分析。真实环境可运行性、P/V数值、D/G0/Q绑定及正式MT50实验仍未验证/放行。存储依赖核查另交，不阻塞本次预检修正；无删除release。

验证范围记录：初次pytest的`-k revision`意外匹配父目录名，执行了71项CPU检查且全部通过；此后改用明确文件/node ID，仅跑修正相关32项，未再重复整套。完整命令与说明在evidence目录。只发生准备检查，无科学实验重试。
'''
report_path = RECEIPTS / f'{TASK}_REPORT.md'
publish(report_path, report)
files = sorted(p for p in OUT.rglob('*') if p.is_file())
manifest = OUT / 'ARTIFACT_MANIFEST.json'
publish(manifest, {'task_id': TASK, 'created_at_utc': now(), 'files': [
    {'path': str(p.relative_to(OUT)), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in files]})
old_identities = {
    'receipts/A/A00_RESULT.json': 'c8585594102c82f716bb70afbf7c4e1658fd60e56336b0ab43f6cdb52f5a7fda',
    'receipts/A/A10_RESULT.json': 'c2fe9e32551eedc24ba4b52f25513e977470856dabe4e84c850db7226e612b35',
    'results/A/A10/code_snapshot_v3/CODE_MANIFEST.json': '07f4b2eb87e93c563621bd346b1b75a2a2ddb82b97492dd4f5d1c52757941687',
}
for path, expected in old_identities.items():
    assert sha(BASE / path) == expected
result = {
    'campaign_id': control['campaign_id'], 'task_id': TASK, 'revision': 1, 'role': 'A',
    'hostname': platform.node(), 'session_id': control['roles']['A']['executor_session_id'],
    'status': 'complete', 'started_at_utc': ack['started_at_utc'], 'finished_at_utc': now(),
    'input_identity': {'protocol': ack['inputs_checked'], 'code': ref(OUT / 'code_snapshot_v4/CODE_MANIFEST.json'),
        'config': ref(OUT / 'preflight_v4/PROPOSAL.json'), 'data': ref(OUT / 'preflight_v4/source_manifest.json'),
        'external_source': ref(OUT / 'preflight_v4/external_source_manifest.json'),
        'model': {'path': str(Path(proposal['checkpoint']) / 'model.safetensors'), 'sha256': proposal['model_sha256'],
                  'verification': 'historical full SHA + inventory size; this CPU correction does not rehash9GB model; future load_authorization performs full checks'}},
    'artifacts': [ref(p) for p in (report_path, manifest, OUT / 'CPU_READY_v4.json',
        OUT / 'evidence/runtime_targeted_checks.json', OUT / 'evidence/PUBLISHED_CPU_VALIDATION.json')],
    'resource_counts': {'simulator_attempts': 0, 'completed_rollouts': 0, 'vla_sampling_calls': 0,
        'model_gpu_inference_calls': 0, 'environment_instances': 0, 'environment_reset_calls': 0,
        'initialization_physics_substeps': 0, 'env_steps': 0, 'optimizer_updates': 0, 'gpu_seconds': 0,
        'deleted_paths': 0, 'deleted_bytes': 0},
    'failures_and_retries': [
        {'kind': 'read_only_path_probe', 'command': 'rg --files .../code_snapshot_v3/tests', 'exit_code': 2,
         'recovery': 'Found test_cpu_contract.py at snapshot root; no runtime attempted'},
        {'kind': 'CPU_test_selection_broadened', 'exit_code': 0,
         'detail': '-k revision matched parent directory; 71 passed; final run selected explicit files/node IDs and 32 passed',
         'scientific_retries': 0},
        {'kind': 'expected_authorization_denials', 'exit_code': 2,
         'detail': 'Both P00 releases rejected by pure CPU entry, before NVML/lifecycle/heavy imports', 'retry': False},
    ],
    'findings': [
        'Standard initialization bound:2 native instances,51 initialization+1 diagnostic reset,104reset_model,26000 settling substeps; policy control has13substeps separately',
        'One diagnostic initial state/attempt,5native/50flow,1policy control,0rollouts/backward/monitor/updates/retries unchanged',
        'Durable private counters enforce entry caps and distinguish returned/failed/incomplete by source; public v1 unchanged',
        '118 installed source files bound by SHA; shared packages unmodified',
        '32 targeted CPU checks passed; final413 code hashes,9 AST files,2 shells and2 P00 denial paths passed',
        '1800+30 covers timed diagnostic child only; preparation/reservation/compute/release/restoration times recorded separately, no1830 end-to-end claim',
        'Independent A-only wave and all local holder lifecycle retained; guard27508 with8 H100 holders checked',
        'No GPU/reset/simulation/training/deletion executed; real environment executability remains unverified',
    ],
    'blockers': [{'task': 'future_A_native_GPU_preflight', 'gap': 'No active compute release; CONTROL prepare with zero budgets',
                  'resolution': 'Analysis reviews v4 then issues exact template/current CONTROL/TASK_BOARD authorization if desired'}],
    'next_task_proposal': 'Analysis review v4; storage dependency supplement may complete independently; do not execute v3 or GPU work under P00',
    'old_receipts_and_snapshot_manifest_unchanged': old_identities,
}
result_path = RECEIPTS / f'{TASK}_RESULT.json'
publish(RECEIPTS / f'{TASK}_HEARTBEAT.json', {'task_id': TASK, 'status': 'complete', 'updated_at_utc': now(),
        'actual_simulator_attempts': 0, 'actual_environment_reset_calls': 0, 'actual_GPU_inference_calls': 0}, replace=True)
publish(result_path, result)  # final task publication last
print(json.dumps({'result': str(result_path), 'sha256': sha(result_path), 'report': str(report_path), 'artifact_count': len(files)}))
