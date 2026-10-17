# Native10 P0：32-worker 并发独立复核

复核快照：2026-09-16 16:50:44 UTC。结束时账本仍为 564 条，全部属于 p0，training_updates=0，未出现主采集阶段登记。

## 结论

**PASS。当前 8 GPU、每 GPU 4 worker 的配置通过本次并发复现检查，可用于同一冻结实现下的后续主采集。** 本检查没有启动仿真或训练，没有改动运行代码、封存结果或预算账本。

这项结论针对并发条件下的候选与轨迹复现性。它不等价于证明 32 worker 的吞吐最优，也不替代主采集阶段自身的协议、预算和数据完整性检查。

## 检查范围和结果

- 注册为 32 worker，使用 P0 manifest 的前 8 个 source，各复现 4 次，没有按成功结局筛选。
- 注册指定的 24 个参考 seal（每源 source、candidate、alarm_replan10/repeat_0 各一个）及其封存文件均通过 SHA256 核验。
- 32/32 worker 均有 ready、result、complete 记录，rank 唯一，结果为 passed，errors 为空。
- 每个 worker 的 6 个完整候选计划数组均与其指定参考逐字节一致：alarm_replan10、velocity、direct、post、reverse_matched、random_matched。
- 每个 worker 的 9 类完整轨迹数组均与参考逐字节一致：actions、physics_states、rewards、success_flags、done_flags、generated_plans、generated_steps、actual_sampling_seeds、actual_sampling_steps。
- 共 **480 项数组比较通过**，dtype、shape、原始字节均相同；32 对 plans.npz 和 32 对 trajectory.npz 的整个文件 SHA256 也分别一致。
- physics_states 最大绝对误差为 **0**，严于注册的 atol=1e-10、rtol=0。
- generation.json 中共有的候选、预测、匹配、噪声与梯度语义字段一致。差异仅为运行耗时、部分内存统计；原参考另有 restore、预算、preview13 与队列检查等封装字段。因此这里的“逐字节一致”严格指上述候选/轨迹数组及 NPZ 文件，不指带运行计时的整份 generation.json。
- 本次实际复现的环境分支为 alarm_replan10/repeat_0；6 种候选命令均重建，但没有新增执行其他纠偏臂，也没有复核整个主阶段的 13 候选采集过程。

## 预算和冻结完整性

- 原 P0 审计记录的 **500 条账本字节前缀完全未变**，其 SHA256 与原 audit_native20.json 一致。
- 新增编号恰为 **501–564**，无缺号或重号：32 次 concurrency_candidate_restore，加 32 次 concurrency_branch_including_restore。
- 每个 worker 的 bank_attempt.json、branch_attempt.json 均与账本对应行完整一致，result 中的 attempt 引用也相同；64 次登记全部一一对应已封存产物。
- 无新增失败、重试、漏计或多余尝试。P0 当前为 **564/600**，剩余 36 次。
- 注册引用的原 P0 audit SHA256 一致；原 freeze.json 与 config.json SHA256 均未改变。
- freeze.json 中登记的 **713 个文件哈希全部一致**；本次 probe 的 2 个注册实现文件哈希也一致。
- 此次没有重算大型模型权重的全量 SHA256；并发前依赖验证沿用原 P0 审计。本项不影响已核实的冻结记录和 713 个登记文件内容一致性结论。

关键哈希：

| 文件 | SHA256 |
|---|---|
| p0/freeze.json | `1c06d15e6b95eff1e4d9667e5a2899682b8e6991cb1caaf10972b7ddeeb78d1d` |
| p0/concurrency32/registration.json | `d78840933e9737d34bfba14cda08d38ad134c74c8faf559e1c6c9402464dea5c` |
| budget/attempts.jsonl（564条） | `223d7d9ceba81ecb8aec9594347834bd668caa38e568e7e2e360c601127ff600` |

## 吞吐证据与解释范围

| 测量项 | 本次结果 |
|---|---:|
| 最早开始工作至最晚完成 | 22.9455 s |
| 32 个 worker 同时处于工作区间的重叠 | 7.6822 s |
| 候选重建及分支共同工作窗口内完成分支数 | 32 |
| 上述工作窗口吞吐 | 1.3946 分支/s |
| 分支内 policy 调用总数 | 556 |
| policy 调用数 / 上述共同工作窗口 | 24.2313 次/s |
| 单 worker 模型加载时间范围 | 167.818–176.651 s |
| 从最早 worker 启动推算至最后完成，含加载 | 199.6033 s |
| 单分支平均 wall time，32-worker probe | 11.0580 s |
| 相同参考分支历史平均 wall time | 6.2969 s |
| 平均每次分支 policy 调用，32-worker probe | 0.5479 s |
| 相同参考分支历史平均每次 policy 调用 | 0.2850 s |

22.95 秒工作窗口包括候选重建、状态回放和完整分支执行；policy 调用统计只计分支调用，不包括候选构造额外的策略调用。含启动时间由 worker 自报 wall time 与完成时间推算，不包括外层调度器的全部开销。

这些数值证明 32 worker 曾实际重叠运行并保持复现；并发也使单分支和单次调用变慢。缺少同一任务集、相同启动条件的 8-worker 对照波次，**不能由此声称整体加速 4 倍，也不能精确给出相对 8 worker 的端到端加速比**。长采集若持续复用已加载 worker，可摊薄约 3 分钟的加载成本，但正式数据吞吐仍应从主采集实际累计完成量与经过时间计算。

## 原始证据

- 注册：[registration.json](../outputs/native10_training_20260916/p0/concurrency32/registration.json)
- worker 原始产物：[concurrency32](../outputs/native10_training_20260916/p0/concurrency32/)
- 原 P0 审计：[audit_native20.json](../outputs/native10_training_20260916/p0/audit_native20.json)
- 原冻结：[freeze.json](../outputs/native10_training_20260916/p0/freeze.json)
- 累计账本：[attempts.jsonl](../outputs/native10_training_20260916/budget/attempts.jsonl)
