# Native10 第一轮运行交接

2026-09-16。执行端已按分析端 READY v4 启动第一轮真实采集；真实训练更新为 0。运行状态以 `NATIVE10_EXECUTOR_STATUS.json` 为准，本文记录固定入口与权限边界，不取代实时计数。

## 隔离与放行

- 新实现：`experiments/native10_training_20260916/`；新产物：`outputs/native10_training_20260916/`。ACT-RECAP、上一批 653 次封存和本轮 P0 均只读。
- 主冻结：`outputs/native10_training_20260916/main_protocols/round1_v1/`。config SHA `f68b59f279ae4d03094ebe70f0185e29d7a65a8ce20903aed92ac4392f1e4fd2`；freeze SHA `f46dda706607bf8ed52281d33a203471c2854b6c09f83e6d26d3b216a509d893`。已封存代码包与 READY v4、任务书和 manifest 快照。
- 当前仅 `round1_labels` / `round1_labels_v1`：300 训练主槽＋100 开发主槽；32 workers（8 卡×4），上限 23200 次。预登记初始化替补使用独立技术储备，最多 1200 次；总体硬上限 50000。
- 全计划 600 独立训练 episode，分两轮 300；开发/校准/保留各 100。训练至多 31200 个候选标签及 2400 个正常控制标签，标签相关，不等于同等数量独立 episode。
- 训练、第二轮、校准和保留尚未放行。分析端 READY v5 已条件放行首轮完整数据后的 CPU fit-before 阶段，使用独立 `round1_fit_preflight` scope/stage，严格 0 次仿真、0 次优化；采集仍沿独立 READY v4 快照。实际优化接口暂建议 `round1_critic_training`，尚须分析端另行采用并放行。

## 运行与监控

主 wave 为 `round1_v1_01`，launch PID `2506458`，进程 start_ticks `1587265491`；已由主入口内部 lifecycle 包装。不要重复启动同一 wave。

- worker 日志和状态：`outputs/native10_training_20260916/main_execution/round1_labels/round1_labels_v1/round1_v1_01/`。
- 全局账本：`outputs/native10_training_20260916/budget/attempts.jsonl`；失败与独立恢复计数不退款。
- CPU 只读 watcher PID `2681069`，每 30 秒更新共享状态。注册、日志、最新进度与通知记录位于 `outputs/native10_training_20260916/progress/watcher/round1_v1_01/`。单实例锁防止重复监控。
- 固定前 50 个预登记训练主槽**全部**封存后，调用 `main_progress_audit.py`，生成 `outputs/native10_training_20260916/progress_audits/watcher_round1_v1_01_first50.json`。未达到门槛仅看运行进度，不按完成快慢挑样本。
- watcher 对运行错误、元数据不一致、重复接受初态、超预算或意外训练更新立即通知分析/执行线程。整波退出后记录 lifecycle 返回与 holder 恢复；不会自动重跑、训练或启动下一阶段。
- 分析线程：`01a0a551-9ed3-7f53-9f39-b60d8674819d`；执行线程：`01a09fc3-ff82-72e3-87ef-9e9f63a792ce`。已授权共享文件和队列协同；队列可能延迟，以状态文件为准。

## 当前证据与待办

主采集前 222 项 CPU 检查及 36 子检查通过；P0 564 次与 32-worker 实现一致性审计通过。首 3 个完整训练源的 738 文件、174 次尝试及完整 raw 动作/状态/初态/配对证据已审计通过；这里只是数据管道检查，不是效果结论。证据在 `preparation/main_cpu_20260916_v1/`、`p0/concurrency32/`、`preparation/smoke_dataset_audit.json`。

后续先完成首固定 50 槽诊断，分别报告 replan−normal、中断后纠偏−replan、纠偏−normal 的真实救回/损害，以及 cut 覆盖、mask、别名、成本和预算。训练时的 scheduled/fallback 诊断不等于部署 first-alarm 策略测评，不选开发赢家作为独立成功。

整轮结束后，用 `artifact_loader.py` 审计和封存完整 train/dev 数据，保留无报警/无合法 cut 的已知共同结局与计划分母。技术未知不能当失败或静默筛掉。训练入口正在单独补齐：强制 scene/replacement 审计；A/B 全部初始化、train-only PCA 和概率/动作梯度重载检查必须先于任何优化更新。相关新入口与测试不属于当前采集冻结依赖，不影响运行中的参数。

P0 外推的轻量磁盘为 8–15 GiB，建议保留 20–50 GiB；32-worker 全计划耗时粗估 6–14 小时，尚不能称主采集实测吞吐。首固定 50 槽完成后以实际全 13 候选负载更新估算。当前共享文件系统空间充足；该检查不代表用户配额保证。
