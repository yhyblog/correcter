from pathlib import Path
import json
import platform
import shutil
from campaign_io import BASE, WORK, RESULTS, atomic, preparation_gate, heartbeat, sha, now


def reference(path):
    path = Path(path)
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def main():
    control = preparation_gate()
    heartbeat('publishing final A10 CPU-preparation report and result; all experiment resources zero')
    if (BASE/'receipts/A/A10_RESULT.json').exists():
        raise RuntimeError('Published A10 result is immutable; use a revision receipt')
    validation = json.loads((WORK/'FINAL_CPU_VALIDATION.json').read_text())
    assert validation['status'] == 'passed'
    evidence = RESULTS/'evidence_v1'; evidence.mkdir(exist_ok=False)
    for name in ['FINAL_CPU_VALIDATION.json','CPU_VALIDATION_r1.json','CPU_RUNTIME_VALIDATION_r1.json',
                 'node_capacity.json','gpu_snapshot.json','occupancy_status.json']:
        shutil.copyfile(WORK/name, evidence/name)
    shutil.copyfile(BASE/'receipts/A/STORAGE_CANDIDATES.json', evidence/'STORAGE_CANDIDATES.json')
    capacity = json.loads((evidence/'node_capacity.json').read_text())
    capacity['cgroup_memory_missing_reason'] = 'Standard cgroup memory limit files were not exposed at checked paths; host MemAvailable is not a guaranteed job quota'
    atomic(evidence/'node_capacity.json', capacity)
    failures = [
        {'kind':'CPU_inventory_path_assumption','command':'build_data_index.py initial run','exit_code':1,
         'reason':'Expected separate episode_id.npy; actual arrays are members of arrays.npz',
         'recovery':'Read exact existing arrays.npz; next CPU run indexed 1300 real trajectories; no original files changed','formal_attempts':0},
        {'kind':'static_interpreter_mismatch','command':'final v2 audit ast.parse of all vendored code under Python3.11','exit_code':1,
         'reason':'Vendored lerobot streaming_dataset uses Python3.12 PEP695 class syntax',
         'recovery':'Used the pinned Python3.12 runtime for all 381 source AST checks; system CPU gate/tests and runtime CPU tests both pass','formal_attempts':0},
        {'kind':'receipt_read_before_writer_completion','command':'Read FINAL_CPU_VALIDATION.json before failed AST audit had published it','exit_code':1,
         'reason':'Receipt was not yet present','recovery':'Final audit writer completed and receipt verified; no restart or physical attempt','formal_attempts':0},
        {'kind':'source_path_discovery','command':'rg guessed runtime.py/rollout.py/duplicated lerobot path','exit_code':2,
         'reason':'Those guessed source paths do not exist','recovery':'rg --files located actual metaworld_runtime.py and collection backend; only needed code read','formal_attempts':0}]
    atomic(evidence/'FAILURES_AND_RECOVERIES.json', {'failures':failures,
        'expected_negative_checks':'P00 launch denial exits1 as intended before NVML/lifecycle/CUDA; it is a passed authorization test',
        'artifact_revisions':'code/preflight/commands v1,v2 retained unchanged; final v3 includes current device checks and external E3 summary semantics',
        'formal_retries':0, 'deleted_paths':[]})
    b_examples = next(x for x in validation['checks'] if x['name']=='B_published_examples_semantic_validation')
    compatibility = {'campaign_id':'corrector-sim-20260919','task_id':'A10','status':'CPU_compatible',
        'interface_version':'corrector-sim-interface/1','schema':reference(RESULTS/'interface_v1/interface.schema.json'),
        'A_examples':7,'B_examples':23,'B_evidence':b_examples,
        'analysis_integration_contract':reference(BASE/'contracts/INTERFACE_V1_INTEGRATION_NOTES.md'),
        'B_feedback':reference(BASE/'receipts/B/A10_INTERFACE_FEEDBACK.md'),
        'E3':'Complete decision/sampling event streams retain native frequency; single cut/entry summaries may be null+reason for external methods',
        'event_lifecycle_examples':reference(RESULTS/'accounting_examples_v1/SUMMARY.json'),
        'next_raw_pool':'Prefer prefix1 transitions or immutable per-step image index; never expand endpoint-only prefix into invented intermediate frames',
        'runtime_validation':'not yet performed; no shared raw pool or real adapter readiness claimed'}
    atomic(evidence/'INTERFACE_COMPATIBILITY.json', compatibility)
    atomic(BASE/'receipts/A/A10_INTERFACE_COMPATIBILITY.json', compatibility)
    report = BASE/'receipts/A/A10_REPORT.md'
    text = f'''# A10 r1：CPU 准备完成，未运行 GPU 预检

本机 A：{platform.node()}。CONTROL revision {control['revision']} / P00_PREP_V1；A00 已完成且结果 SHA 未变。
本次训练更新、模型采样、simulator attempts、完整 rollout、实验 GPU 秒全部 **0**。8 个 occupancy holder 继续运行，属于既有占卡政策。

| 交付 | 状态与边界 |
|---|---|
| 公共接口 v1 | 七类 schema＋7 样例不可变；B 的23条样例通过 A 语义校验 |
| 独立 Post/Velocity | 原自身半径/mask/raw恢复代码冻结；Post S²、Velocity 同噪声、自采 a0；CPU 回调入口 R/P/V 为1/1/2，真实梯度未预检 |
| H/C 队列 | H10/20/30/40/50；C10结束丢弃尾部并新采 nativeH；先终止再监测；最后合法 cut 为285/290/290/290/290 |
| 核心矩阵 | 严格16单元：各H N/P/V，只有H10加R；同源所有单元保留在显式指定主机 |
| 数据索引 | 700个train/development父源＋600条固定a0/repeat0后缀，1300条全部核验；359段有真实首次成功时间；不含历史held |
| 数据缺口 | 上述是限定覆盖索引；其他候选/重复未宣称全部索引。旧RGB/next及独立terminal标志仍缺失，不能充当完整新公共池 |
| 双账本与恢复 | entered仅计一次；成功/部分失败/缺末事件三个持久化样例；N shadow排除部署；完成复用校验SHA，不凭过期心跳重试 |
| CPU验收 | 系统Python3.11/NumPy1.26与实际Python3.12/NumPy2.2各42项通过；381文件在实际3.12下AST通过；shell通过；P00拒绝真实命令 |
| 实际预检命令 | 已准备，尚未执行。只检查原生底座加载/队列/渲染/单步数据，不声称P/V、MT50 corrector或正式评测已验证 |

当前正式交付使用 `results/A/A10/code_snapshot_v3/`、`preflight_v3/`、`commands_v3/`。v1/v2代码快照留作准备证据；公共 `interface_v1/` 从未原地修改。
代码manifest SHA：`{sha(RESULTS/'code_snapshot_v3/CODE_MANIFEST.json')}`。
预检proposal SHA：`{sha(RESULTS/'preflight_v3/PROPOSAL.json')}`。

## 可执行有限预检报价（需要新 release，本次不运行）

命令文件：`{RESULTS}/commands_v3/run_proposed_native_preflight.sh`，唯一参数为分析端新发布的绝对 release 路径。
工作目录：`{RESULTS}/code_snapshot_v3`。CPU复核命令为同目录旁 `commands_v3/cpu_checks.sh`。
配置与输入：`preflight_v3/PROPOSAL.json`、`source_manifest.json`、`RELEASE_TEMPLATE.json`（模板不是授权）。

| 数量 | 上限 |
|---|---:|
| 候选诊断初态 | 1：shelf-place-v3，env seed2026091900；development，不作为测试结论 |
| 模型初始化 / 环境初始化 / reset | 1 / 1 / 1 |
| simulator attempts / 物理状态恢复 / 完整rollout | 1 / 0 / 0 |
| 完整VLA采样 / 实际flow前向 | 5 / 50；同观测分别核验五种H，不由方法名补账 |
| 真实环境控制步 | 1；保存step0/1图像、proprio、raw动作、真实success/reward/native终止标志 |
| VLA反向 / Q前后向 / monitor / optimizer | 全部0 |
| 重试 / timeout | 0 / 1800秒，TERM后最多30秒强制退出 |

依赖：冻结4MB LeRobot源码、既有Python3.12/torch2.7.1环境、持久SFT030000完整7文件、固定tokenizer版本、EGL。运行前重新核验大权重SHA；A00/A10仅核验其尺寸和历史SHA，小文件及tokenizer已hash。
估计峰值（未实测）：单GPU显存40GiB、主存64GiB、新增磁盘2GiB；真正加载/渲染可用性仍待这次有限预检。
执行前校验本轮CONTROL、任务revision、proposal/code/input SHA、host和实际GPU UUID/driver；不读取旧READY或旧493余额。
这份命令只允许 **A-only wave**，整个命令经occupancy lifecycle包装，A全部holder停算至退出（含失败）；B不参加时维持自身占卡。联合A/B release被此启动器拒绝，后续联合生产launcher必须冻结双方compute-exited完成/失败屏障后再放行。
保留claim、逐调用事件、失败、账本、5个raw计划、前后观测和单步transition；失败不换源、不自动重试。

## 后续边界与证据

- A12仍需MT50 D/G0/Q绑定与适配；五任务旧A4000不能直接改名。真实Post/Velocity与D特征需另一个带数量的预检配置；当前最小原生命令不覆盖它们。
- 新公共池尚未采集。B要求逐步观测、policy预处理state、任务embedding及normalizer身份；以后按prefix1或逐步索引落盘，绝不由聚合终点补图。E1继续用现有train600，不补采600源。
- B13负责E1实际训练入口与共同初始化/更新预算；A交 `configs_v1/E1_training_shape.json`（4损失×3完整seed槽，12个完整ensemble fits，不能把成员当seed）。实际seed/更新数为null待发布。
- `configs_v1/core_eval_matrix.json` 给16单元的无失败独立整episode采样上界，合计261 calls/source/repeat；尚无测试源数量、真实Q/反向调用上限，因此不是正式评测预算或已发布评测launcher。
- `data_access_v1/DATA_ACCESS_READY.json`、`existing_trajectory_index.jsonl`、`parent_splits.json` 供分析端冻结共同访问身份；首次成功按动作后状态step+1，无成功前缀不冒充整episode失败。
- E3原生多次引导由完整事件流表达；单值cut/entry可null+原因。计划、完成及技术失败分母分开，最终恢复/统计规则待P20。

资源盘点单列：共享磁盘statvfs为池级容量（项目quota未知）；host RAM约2015GiB、available约1631GiB（容器额度未暴露）；8×H100每卡81559MiB，holder占1013MiB、49–50%，guard PID27508。详情 `evidence_v1/node_capacity.json`、`gpu_snapshot.json`、`occupancy_status.json`。
存储候选 `receipts/A/STORAGE_CANDIDATES.json`：4项明确keep，9个Smol旧中间checkpoint共14,494,556,639逻辑bytes标defer，尚未排除历史封存/B恢复依赖；删除0。分析端未发布精确删除清单前不执行清理。
CPU路径/解释器检查失败及恢复见 `evidence_v1/FAILURES_AND_RECOVERIES.json`；未触及旧封存、旧训练队列或另一节点文件。
'''
    report.write_text(text)
    current_folders = ['interface_v1','configs_v1','data_access_v1','accounting_examples_v1','code_snapshot_v3','preflight_v3','commands_v3','evidence_v1']
    entries = [reference(p) for name in current_folders for p in sorted((RESULTS/name).rglob('*')) if p.is_file()]
    atomic(RESULTS/'ARTIFACT_MANIFEST_r1.json', {'campaign_id':'corrector-sim-20260919','task_id':'A10','revision':1,
        'status':'complete_CPU_preparation_only','files':entries,'file_count':len(entries),
        'logical_bytes':sum(x['bytes'] for x in entries),'report':reference(report),
        'retained_superseded_preparation_artifacts':['code_snapshot_v1','code_snapshot_v2','preflight_v1','preflight_v2','commands_v1','commands_v2']})
    atomic(RESULTS/'CPU_READY_r1.json', {'status':'complete_CPU_preparation_only','campaign_id':'corrector-sim-20260919',
        'task_id':'A10','revision':1,'created_at_utc':now(),'publication_is_compute_authorization':False,
        'code_manifest':reference(RESULTS/'code_snapshot_v3/CODE_MANIFEST.json'),
        'artifact_manifest':reference(RESULTS/'ARTIFACT_MANIFEST_r1.json'),
        'interface_ready':reference(RESULTS/'interface_v1/INTERFACE_READY.json'),
        'finite_preflight_proposal':reference(RESULTS/'preflight_v3/PROPOSAL.json'),
        'actual_resource_counts':{'simulator_attempts':0,'completed_rollouts':0,'vla_sampling_calls':0,'optimizer_updates':0,'gpu_seconds':0}})
    findings = [
        'Public interface v1 remains immutable; A7 and B23 synthetic records pass; E3 multi-decision summaries are supported without changing native event frequency.',
        'Independent R/Post/Velocity CPU entry callbacks preserve own a0/noise/raw projection and 1/1/2 calls; real guided GPU numerics are not claimed validated.',
        'H/C clock tests cover H10..50, terminal-before-monitor, last legal cut285/290 and C10 tail discard/nativeH recovery; E4 matrix remains16 cells.',
        '700 historical train/development parents and600 fixed a0 repeat0 suffixes indexed:1300 trajectories,359 with observed success timing; no held or invented images.',
        'Durable entered/returned/failed accounting, three lifecycle examples, N shadow exclusion, explicit shards, SHA-verified reuse and no stale takeover prepared.',
        '42 CPU tests pass in both Python3.11/NumPy1.26 and real Python3.12/NumPy2.2;381 runtime-source AST files and shell syntax pass.',
        'Native finite preflight command/proposal ready but not run:1 simulator attempt,5 complete samples,50 actual flow forwards,1 env step,0 optimizers,0 retries.',
        'Published final code snapshot v3 and source/proposal identities; current P00 command denial verified before GPU/lifecycle entry.',
        'MT50 D/G0/Q adaptation, new complete raw pool, real P/V backend binding, joint-wave launcher and formal evaluation remain later-release dependencies.',
        '8 H100 holders healthy; disk pool/RAM/VRAM separated;4 keep+9 deferred Smol candidates,0 deletion; all actual experiment resources remain0.'
    ]
    ack = json.loads((BASE/'receipts/A/A10_ACK.json').read_text())
    result = {'campaign_id':'corrector-sim-20260919','task_id':'A10','revision':1,'role':'A','hostname':platform.node(),
        'session_id':'01a0b91f-7443-71b1-915d-6cdb6d6a1a13','status':'complete',
        'completion_scope':'authorized CPU preparation, not GPU runtime/scientific acceptance',
        'started_at_utc':ack['started_at_utc'],'finished_at_utc':now(),'control_revision':control['revision'],
        'release_id':'P00_PREP_V1','input_identity':{
            'protocol':[reference(BASE/p) for p in ['releases/P00_PREP_V1.json','contracts/P00_PREPARATION_CONTRACT_V1.md',
                'contracts/DATA_LOG_CONTRACT_V1.md','contracts/INVENTORY_DECISIONS_V1.md','contracts/INTERFACE_V1_INTEGRATION_NOTES.md','contracts/STORAGE_RETENTION_V1.md']],
            'code':reference(RESULTS/'code_snapshot_v3/CODE_MANIFEST.json'),
            'config':reference(RESULTS/'preflight_v3/PROPOSAL.json'),
            'data':reference(RESULTS/'data_access_v1/DATA_ACCESS_READY.json'),
            'model':{'path':'/mnt/bn/arnold-recommend/yaohaoyang/vla-corrector/outputs/metaworld_very_hard/sft_pi05_mt50/checkpoints/030000/pretrained_model/model.safetensors',
                'verified_payload_sha256':None,'historical_manifest_sha256':'dff338a91dbe534ca3c4525ba82df9324662e3c87131f42ed6e3d1b7bf0e94d4',
                'missing_reason':'A00/A10 checked bytes and historical identity, not a full9GB payload hash; proposed preflight requires full SHA before load'},
            'inventory':reference(BASE/'receipts/A/A00_RESULT.json')},
        'artifacts':[reference(p) for p in [report,RESULTS/'CPU_READY_r1.json',RESULTS/'ARTIFACT_MANIFEST_r1.json',
            RESULTS/'interface_v1/INTERFACE_READY.json',RESULTS/'data_access_v1/DATA_ACCESS_READY.json',
            RESULTS/'preflight_v3/PROPOSAL.json',RESULTS/'commands_v3/COMMANDS.json',
            evidence/'FINAL_CPU_VALIDATION.json',BASE/'receipts/A/A10_INTERFACE_COMPATIBILITY.json',BASE/'receipts/A/STORAGE_CANDIDATES.json']],
        'resource_counts':{'simulator_attempts':0,'completed_rollouts':0,'vla_sampling_calls':0,'optimizer_updates':0,'gpu_seconds':0},
        'resource_scope':'formal experiment only; pre-existing occupancy maintenance excluded; CPU synthetic counters are fixtures, not actual work',
        'failures_and_retries':failures,'findings':findings,'blockers':[
            {'scope':'future real Post/Velocity/core runtime','detail':'D/G0/Q and feature bindings need finite real numerical preflight; five-task assets do not establish MT50 adaptation','resolution':'P10 freezes exact input bindings and separate finite counts, A12 performs planned adaptation'},
            {'scope':'future common raw pool/B training','detail':'Historical per-step observation/next and separate terminal fields incomplete; new common pool has not been collected','resolution':'Analysis freezes access manifest; A11 records prefix1 or per-step sidecar once with explicit budget'},
            {'scope':'future joint compute wave','detail':'Published native diagnostic launcher is A-only and rejects joint release; no shared production barrier launched','resolution':'P10/A11 publishes specific multi-host compute-exited barrier retaining local lifecycle reservations'},
            {'scope':'future training/evaluation','detail':'Training init/update/seed counts and frozen test/model releases remain unspecified; formal drivers not published by A10','resolution':'B13/P10 and A12/P20 own these concrete task releases'}],
        'next_task_proposal':'Analysis reviews A10+B10, freezes common data access and a finite P10 release; execute no compute until exact new release. No historical stage restart.',
        'queue_delivery_receipt_expected':str(BASE/'receipts/A/A10_QUEUE_DELIVERY.json')}
    atomic(BASE/'receipts/A/A10_RESULT.json', result)
    heartbeat_path = BASE/'receipts/A/A10_HEARTBEAT.json'
    state = json.loads(heartbeat_path.read_text()); state.update(status='complete',updated_at_utc=now(),
        progress='A10 CPU package published; waiting for analysis/P10, no GPU work released',result_path=str(BASE/'receipts/A/A10_RESULT.json'))
    atomic(heartbeat_path,state)
    print(json.dumps({'result':str(BASE/'receipts/A/A10_RESULT.json'),'result_sha256':sha(BASE/'receipts/A/A10_RESULT.json'),
                       'report_lines':len(text.splitlines()),'artifact_files':len(entries),'current_code':'code_snapshot_v3'}))


if __name__ == '__main__':main()
