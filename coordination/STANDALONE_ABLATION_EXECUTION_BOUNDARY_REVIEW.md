# 独立纠偏消融：执行边界与完整审计链复核

日期：2026-09-18 UTC。

**结论：PASS，cpu_v2 对应实现未发现本次统计、权限或完整审计链的放行阻断项。** 此结论只覆盖已读取的代码与 CPU 证据；不宣称新 READY 已发布、实际 freeze 已通过或真实预检已通过。模型/仿真仍须由新 READY 绑定真实 pending/CPU/代码后，按同一冻结版本执行。

## 证据版本

- TASK：`coordination/STANDALONE_ABLATION_TASK_20260918.md`；SHA256 `363c50bedcb04d93a5904bf7ecf9873d691974e7e67d82f3a419af4c0065ff5e`。
- CPU：`outputs/standalone_ablation_20260918/preparation/cpu_v2`。
- CPU complete SHA256：`7438671e116cfe31eb3d13868c2b309ce6b0e109e48bf989372851810c35cb44`。
- CPU result SHA256：`b5e83f50c41565d539234953475b24ebec431e256e2f825ecc3a35746576cf05`。
- 已核 complete 的全部四个成员 SHA。JUnit：117 tests、0 failures、0 errors、0 skipped；receipt 为 passed/returncode 0，模型、仿真、优化均为 0。
- receipt 的 20 个代码/测试文件 `code_before == code_after == 当前 SHA`，与新工程全部 `.py/.sh` 文件集合完全一致。本次未重跑 CPU、导入模型或调用环境。

| 文件（`experiments/standalone_ablation_20260918/`） | 被审 SHA256 |
|---|---|
| protocol.py | `c20302fbe365914e76178443568dd99d77cb1daaead0aa9cbac76265c8cf4818` |
| prepare.py | `2f3a91f144c7e3d9fad1d2c7bc231ddf989de3fcbbb80b03277e9817a471daa8` |
| storage.py | `5734c2d738b60d6c728ecc04c49ec4c6a7185b4632d6a142a8b45da0a29f7295` |
| runner.py | `082d0ed21a769292c9b526662fb24ec497660ab914eb0a75e57658716350bd45` |
| collection.py | `6dbbdc164b48e4ae53e5db4c79f8ea859f08ee048193ff17ee8c0247e4b3cb4d` |
| audit.py | `5fee82e59935c8d0edbceb2ef3cf014cea3507f7f7dacfff37b587d908dc15ab` |
| statistics.py | `7422b3b3e70c89db35bdc7a0a67069fd094e6a95ebed29fab632017b8c382c2a` |

## 1. 权限、阶段及预算

- `protocol.py:34` 只接受新 standalone READY，核 TASK SHA、完整 release contract 及实际 preparation binding；旧 native10 READY 和 pending 配置不能运行。`prepare.py:123` 验 CPU before/after/current；`:136` 将实际 pending、CPU seal 和代码 SHA 交给 future-ready。
- `prepare.py:34` 从当前 TASK 读取预检计划 50，构造固定五源、原五臂 rep0 加三 solo rep0，每源另有原 fullbank 与独立 bundle 两次恢复：`5×(2+5+3)=50`。正式固定 100 源、三 solo、重复 0–3，98 个 cut 的 `98×(1+3×4)=1274`。
- 代码保留 30 次预检备选，但它由 TASK 表中的计划控制，并经完整配置及精确 READY 绑定。本次 TASK 为 50；最终 future-ready 应继续核实际计划为上述 50，不能误用 30 或仅凭统计文件通过启动。
- `protocol.py:118` 对每次预约核 scope、阶段 cap 和全局 cap；正式阶段额外调用 `require_preflight_pass`，检查实际 config、freeze SHA、版本、完整预检 seal、passed 状态及同计划 attempts。此门也保护低层模型/ledger 入口，不仅是 runner 的命令入口。
- `storage.py:85` 同时 SHA 绑定旧预算 snapshot 与原 live ledger，运行时检查二者文件身份。新 ledger 在独立锁内先追加预约，再恢复/执行；失败预约保留，重复身份拒绝。仅允许 `candidate_restore` 与 `branch_including_restore`，capture/替补/优化均拒绝。
- carry-in 为 48,183 simulator attempts、51,200 optimizer updates。新增阶段 cap 为 60/1400/40，合计 1500；计划 1324，累计计划 49,507、最大 49,683，不越 50,000；新增优化 0。repair 40 是否可用由新 READY scope 控制，初版应保持未释放。
- `collection.py:105` 显式拒绝 capture；所有 bank/branch 在 restore 前预约。输出限定新根目录，旧 source/bank/collection/ledger 仅作只读引用。runner 无自动重试，整波使用 lifecycle，`hold_idle=false`。

## 2. 配对与完整结局来源

- `audit.py:233` 先要求整波退出成功、全部固定 worker seal、完整 slot 分配及同一已加载模型身份，之后才读取新结局。缺 worker、缺 source、失败、替补或模型不一致均不能产生正式完整结果。
- `audit.py:301` 将 source/cut/scene/native10/300 步与原 seal 绑定；旧 collection 必须原五臂、四 repeats。`audit.py:331` 核原每个 cut 的 20 个 method/repeat 参考分支，旧 success 来自受原 seal 约束的 summary，并核原来源与 suffix 身份。
- `audit.py:354` 核新 bank 的旧 a0、noise、mask、观测上下文、调用数和动作来源。预检重建 fullbank，与原四条 raw plan、完整 formal 数组逐位对照；V/D 原生方向使用新捕获但已复现原 full 实现的诊断数据，不伪称历史归档保存过这些原生方向。
- `audit.py:171` 对原五臂预检重放检查终局、动作、计划、seed、图像、队列和离散数组；物理状态绝对容差 `1e-10`、reward `1e-8`，不夸称物理浮点逐位一致。
- `audit.py:387` 逐项匹配新 expected method/repeat 组合；将新分支交给原 `artifact_loader.py:327` 核 trajectory：success 必须等于实际 `success_flags.any()`，源前缀动作/状态/reward/flags、干预 raw prefix 和原 suffix 调度必须一致。新 success 不由 Q 或旧标签代填。
- 全部有 cut 源读取旧五臂与新三臂四 repeats；无 cut 源仅允许指定两个原 ID，须核原 source 已有完整 episode 终局、原 collection 无物理分支且共同布尔结局一致，然后给八臂各保留四个相同逻辑位置。无 cut 不建 bank、不新增 rollout。
- `audit.py:192` 将每个新 bank/branch 的 attempt 与 ledger 一一闭合；漏记、重复、额外失败记录、越 cap 或被删记录均不能通过完整审计。预检仅保存技术证明，不汇总 solo 成功率，也不并入正式统计。

## 3. 统计边界

- `statistics.py:32` 要求完整原 100 ID、每任务 20 不同 scene fingerprint、指定 98 cut + 2 common、八方法各四个布尔结局及已通过配对审计；缺失不填 0、不删源。
- 三项共同主要比较为 solo Post/Direct/Velocity 相对原 replan；solo−同方法 full 是关键次要结构诊断。原 N/R/full V/D/P 与新增 solo 分别标为复用封存/新增实测。
- `statistics.py:102` 固定任务内整源 bootstrap 10,000 次、seed 2026091801；每源先平均四 repeats，八方法共用同一抽样矩阵。总体每臂 400 个逻辑结局，五任务各 80；不存在把 400 或 80 当独立初态抽样的实现。
- 所有预登记总体差值给 95% percentile/linear CI；三个主要比较另给分位点 `0.05/6` 与 `1−0.05/6` 的 Bonferroni 98.333333% 区间，并注明近似家族控制。无事后赢家选择、接受门或非劣效宣称。

## 审查界限

本次完成的是已测实现的静态审查及 CPU 证据核验。未来 READY/pending/freeze 的实际绑定仍由既定发布步骤负责；真实恢复、旧轨迹重现、实际单分支调用与最终 100 源完整性必须由同一代码版本的预检和正式审计实测证明。旧 held 已揭晓，追加试验始终属于同队列结构消融，不增加独立 held 证据。

## 补充：cpu_v3 报告与绑定差分

2026-09-18 后续窄审：**PASS**。本节保留上文 cpu_v2 的事实，不将 v2 回执改写成覆盖后续变更。

- `preparation/cpu_v3/complete.json` SHA256：`ebcc3904757af5406be29543fa5d221fac5c71a986e48aad3d25247dcf53aa8a`；result SHA256：`b1e0248ff786bbe694a8dd70a826ffa4665fe4affd7d460fd037372e34356822`。125 项测试通过，无失败、错误或跳过，模型/仿真/优化为 0；该次读取时 22 文件 before/after/current 完全一致。
- `audit.py` 只在完整正式审计及统计之后增加两行 diagnostics 调用；移除这两行后 SHA 精确恢复为上文 v2 值。v3 SHA 为 `8b20aaeb59631dc15e680783987e3845dc064b09231e61735c7314ce0852221c`。
- `prepare.py` 只增加 method/input reviews 的 future-ready 引用绑定；移除此项后 SHA 精确恢复为 v2 值。v3 SHA 为 `cfb9cd989da3b235a79ea10d0e6d9c9ac9d7e36ba292a519cbefe3de51ce8311`。
- 新 `diagnostics.py` SHA 为 `e5805ee2f95cdef5e5346093725673b1e5d23116fcaece00afb8b525d70728da`。它要求完整正式审计、100 源/98 cut/2 common/400 分母，仅读取已审 SHA 覆盖的数据；报告扰动、Q 和包含独立 a0 的生成成本，不改变 gate、方法、统计或效应读取时机。
- 已检查实际 `pending/task_document_v1/ready_contract.json` 与 handoff_v1 的 future 字段相等；预检固定五旧臂 rep0 + 三 solo rep0、50 attempts，正式 1274。旧 30 次消息不构成本次实际配置。
- 本补充不覆盖 engine 异常调用日志的另行修订；该窄修和其后 CPU 由单独审查绑定。后续版本若改变本节代码，不能使用旧 CPU SHA 静默替换。

## 补充：cpu_v6 有界运维修复

2026-09-18 启动前运维修复窄审：**PASS，无新阻断**。未运行任何测试、模型或环境。

- `preparation/cpu_v6` seal SHA：`5d53cb699f6b1b142a366168d25679bd44ea359b8d3f73a2401869715877bd1f`；86 项针对性测试通过，无失败、错误或跳过，before/after/current 相同。其引用的 cpu_v5 seal 为 `0244e95c3c564678f407666f27f751ddb6c8b846d621745be475bfbdb286c18e`，145 项通过；engine/candidates/collection/protocol/statistics/storage 的 SHA 与 v5 不变。
- `operations.py` SHA：`584aa39b6dbca39c564e1058f3c94f29600b2681b00a86dd05138bfae3065e88`。依赖适配只允许 `gpu_occupancy_lifecycle.sh` 与 `gpu_occupancy_guard.py` 两个授权旧→新 SHA，保留历史快照并绑定运维修复决定；原 1702 文件的其余 1700 在封存依赖审计中均 matched，large 资产保持原 SHA。`gpu_hold.py`、旧八卡 scheduler 与 `/usr/bin/true` 作为实际运行依赖明确绑定，未把未知历史 gpu_hold 身份冒称原封存身份。
- prepare 的新 freeze/verify 调用该精确映射后仍核全部 SHA；没有全局跳过旧依赖检查。失败 `protocols/standalone_v1` 保持只读，修复必须创建新 freeze 版本。
- 预检仍为五个真实 supervisor，补三个精确 `/usr/bin/true` 空槽，空槽不含 worker/source/model/environment/attempt；新增 audit 严格检查空槽字典。cpu_v6 中真实导入旧八卡 scheduler、仅 mock 子进程的测试覆盖 5-worker 与 32-worker 两种 spec，均通过。
- 实际 `pending/operational_v1` 保留预检 50／正式 1274。预检通过门、三主比较、100/98+2/四 repeat、旧新 ledger 上限未变化。完整 READY/pending/CPU/代码/运维绑定仍须由最终 future 字段及新版本 freeze 接线，不得绕过 SHA 拒绝。
