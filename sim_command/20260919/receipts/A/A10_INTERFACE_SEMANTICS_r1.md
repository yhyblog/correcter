# A10 interface_v1 集成计费说明

| 项目 | 结论 |
|---|---|
| 公共 v1 | READY 与 README/schema/examples 三文件 SHA 均与分析登记相同；不改 schema，不发 v2 |
| CPU 定向检查 | 10 项通过；三类既有样例、重复引用、重复 entered、跨 run ID 冲突、终态身份/计费漂移、E3 多次事件 |
| B 消费 | B 已在 `receipts/B/A10_INTERFACE_FEEDBACK.md` 确认相同计费规则及 v1 兼容；原等待状态已解除 |
| 实际计算 | GPU推理/训练/仿真/reset均0；下表仅合成计数 |

## 生命周期与唯一身份

`resource_units` 是一次操作的固定计费向量。`entered` 引入该向量的一次增量；`returned` 或 `failed` 原样重述它，新增费用为0。它不是 run 累计值，也不是每条 phase 再加一遍；`count` 不再乘上该向量。完整调用、失败调用和缺末事件调用均按唯一 entered 计一次。

`event_id` 是实际操作身份，必须在会被合并的实际账本（本轮跨 task/run/node/episode 的账本）中唯一，不能每个 episode 从0重新编号。A 的 EventJournal 使用 UUID4；同一次操作的 entered 与唯一末事件复用同一 ID，并保留相同 `identity`、`episode_id`、硬件/时钟、父事件和资源向量。当前 reconcile 以 event_id 为键，并核对终态身份；它没有实现“相同 event_id 加 run_id 后自动分桶”。跨 run 的 ID 冲突、重复 entered 或重复末事件直接拒绝，不能当作同一操作合并。独立合成示例不冒充真实合并账本。

复用的轨迹/方法视图只引用原操作的 `cost_event_refs`；相同引用用集合去重，不复制 entered。父容器的资源向量必须为0；采样事件计1次采样，子 flow 逐次计其实际进入次数，不能在采样父事件再预填50个 flow。时间按同一时钟的区间并集计算；设备父子覆盖不重复相加。跨时钟不能相减。N 的研究 shadow 成本不归入 N 部署成本。

## 三个合成例子

| 样例 | phase 记录 | 采样/flow entered计费 | returned/failed/缺末事件 |
|---|---|---:|---:|
| successful_return | 采样 entered → flow entered → flow returned → 采样 returned | 1 / 1 | 2 / 0 / 0 |
| partial_failure | 采样 entered → flow entered → flow failed → 采样 failed | 1 / 1 | 0 / 2 / 0 |
| missing_terminal | 采样 entered → flow entered，随后无末事件 | 1 / 1 | 0 / 0 / 2 |

原始 JSONL 与逐例摘要：`results/A/A10/accounting_examples_v1/`；本次按其原 SHA 复核，未改写。部分失败的1个 flow 是进入费用，不声称该 kernel 已完成；未进入的后续 flow 不预计。

entered 在调用前落盘并 fsync，是调用尝试/预算扣账边界。若崩溃发生在落盘后、实际函数执行前，仍保留该尝试费用；不能据 entered 独自证明 kernel 完成。缺末事件保留 incomplete ID，不退费、不补造 returned/failed、不自动重试。无法观测的后续工作不填0；未知结果保持 null+原因。missing_terminal 的 wall_union={} 表示没有完整可测区间，绝不是总墙钟0秒；设备耗时也未知。计划/完成/技术失败/未完成的数量分别保留，不能丢掉 null 后声称完整配对结果；恢复规则与最终分母由 P20 冻结。

## E3 与 E8

E3 的单值 `cut_step/entry_generation_id` 仅为适用时的摘要。多次原生决策时可 null+原因；真实调用次数由冻结方法与完整事件流的 decision_index/sampling_index 决定，不受 Core 一次干预上限约束。本次合成例子验证空单值摘要与3个原生采样事件并存。E8 沿用独立 H/C、动作维度与自己的 release；不套用 Core 50/C10。

证据：`results/A/A10/interface_semantics_r1/CPU_CHECK.json`；执行脚本：`work/A/A10_PREFLIGHT_REVISION_R2_r1/check_interface_semantics.py`。不修改旧 A10 RESULT 或 code_snapshot_v3。
