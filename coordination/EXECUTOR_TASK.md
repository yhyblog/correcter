# 执行端任务：当前 MetaWorld 三种纠偏的小批量比较

任务 ID：`corrector-small-20260916`。用户已授权本轮小采样及双 Codex 协作。

## 分工及状态传递

- 分析端对话：`01a0a551-9ed3-7f53-9f39-b60d8674819d`。负责独立核心、历史结果归档、协议/代码复核及结论。
- 执行端对话：`01a09fc3-ff82-72e3-87ef-9e9f63a792ce`（设计VLA中断纠偏方案）。负责运行前审查、环境检查、GPU 小批量执行、原始产物及执行报告。
- 两端通过本目录文件交接，并可使用 `codex queue --thread <对方 UUID> --message <简短消息>` 通知。
- 执行端先写 `EXECUTOR_STATUS.json`，至少含 task_id、state、updated_at、message、output_path。阶段建议 accepted / preflight / sampling / completed / failed。
- 分析端完成核心数值核验、脚本复核后生成 `ANALYSIS_READY.json`（含文件 SHA256）。这是代码就绪条件，不是再次向用户申请许可。就绪前执行端可检查环境和协议；不得启动这批正式仿真。

## 文件所有权

- 分析端当前正在编写 `src/corrector/`、`tests/`、`experiments/metaworld_small/`、`configs/` 和 `scripts/run_metaworld_small.sh`；归档到 `assets/`、`provenance/`、`results/reference_flow_20260916/`、`docs/reference/`。
- 执行端只写 `coordination/EXECUTOR*`、运行产物目录 `outputs/metaworld_small_20260916/` 和最终 `docs/SMALL_BATCH_EXECUTION_20260916.md`。代码有问题先通知分析端修复，避免同时编辑。
- 原 ACT-RECAP 的代码、配置、模型和封存结果只读。

## 固定实验范围

1. 当前相同 MetaWorld、冻结 VLA / G0 / v3 critic，不训练、不调 alpha、不根据结果追加样本。
2. 原有五个任务，每任务三个新源，共十五。正式种子 `2026106000`–`2026106014`；预检 `2026105900`–`2026105904`；运行前检查未与旧产物冲突。保留原验证的 5000 系列不动。
3. 每源八次配对续跑。实际执行 `continue_old`、`replan`、`velocity_matched`、`direct_matched`、`post_matched` 五臂，共 600 正式分支。用户新增的 `continue_old` 是不在报警时中断/重新规划：继续原 50 步队列剩余动作，自然耗尽后再按原正常 50 步策略生成，至 300 步；不得在第 10 步主动清队列。它和 fixed10 的 replan 比较包含策略周期变化，不能解释为仅报警这一瞬间重规划的净效应。正常队列耗尽后的策略调用仍存在，“不重规划”不代表永远复用一个动作。
4. 三种方式分别是 flow velocity 注入、QGF 式 direct 注入、采样后的 endpoint/post 梯度修正。第三种不在 flow 积分内部注入，报告名称要准确。
5. 保留上一轮 shared mask/shared radius 算法：仍生成 velocity、direct、post、reverse、random 五个方向来决定共同幅度；reverse/random 本轮不做物理 rollout。不得改成每方法单独裁剪/缩放。
6. alpha=10，tau=[0.3,0.2,0.1]，true clamp；XYZ RMS=.05 / Linf=.15，夹爪 RMS=.10 / Linf=.40，边界余量=.05。post 采用 S²∇aR。
7. 所有臂相同 source 状态、首次 G0 alarm。replan 和三种纠偏共用 a0、初始 flow noise、suffix seeds；十步前缀后清空队列，冻结 fixed10 后缀，到原总控制预算 300。continue_old 用同源/rep/自然策略决策序号种子配对，但调用时间和频率不同，须单独记录。无 alarm 的计划源不能丢弃。
8. 5 预检源各 1 replicate × 5 臂=25；源捕获 20；并发 a0 复现最多 8。计划计数 653，硬上限 700（包括失败/重复，余额只用于技术故障）。不得启动旧 100 源验证。
9. CPU 核心检查、alpha=0 基线等价、梯度符号、状态还原、配对 noise 和并发 a0 复现通过后才能正式采样。协议及代码 hash 在正式源捕获前冻结。
10. 以完整 source 为统计单位，任务分层 bootstrap；报告五臂绝对成功率、replan 相对 continue_old、三臂相对 a0，以及三种纠偏两两比较、rescues/harms、逐任务/逐源差异、zero group/fallback。15 源只做方法筛选，不因 120 条续跑而声称 120 个独立样本。
11. 计时区分原生候选生成、post 梯度、完整 matched candidate bank。post 共享幅度依赖其他方向，本批不能以一次 post 梯度耗时冒充完整部署时延。

## 执行步骤

1. 收到消息后先确认接单，检查共享路径和当前 GPU 状态；等待就绪文件期间审查协议，不另起重复小测。
2. 遵守父目录 AGENTS.md：检查/启动 occupancy guard；所有正式 GPU 工作由 `gpu_occupancy_lifecycle.sh run -- ...` 包裹。整个 wave 禁止 holder 运算；退出或失败后恢复，不能终止无关进程。
3. 就绪后按 `scripts/run_metaworld_small.sh` 的帮助和 `experiments/metaworld_small/PROTOCOL.md` 执行；若发现技术错误，保留失败计数并通知分析端，不能悄悄放宽审计。
4. 结束交付完整分支产物、冻结协议/代码、预算账本、审计、evaluation、逐源 CSV 与执行报告；检查占卡恢复，再通知分析端独立复核。

本任务是用户要求的当前环境小批量筛选，不是更广泛的独立验证。
