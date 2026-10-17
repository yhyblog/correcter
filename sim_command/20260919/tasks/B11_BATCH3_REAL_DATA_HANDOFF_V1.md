# Batch3 已验收数据的 CPU 交接补充

日期：2026-09-21。接入现有 B11 / B_INDEPENDENT_PIPELINE_PREP_V1，不新增计算任务、GPU release 或重复采集。A 无需等待 B 消费此快照。

读取分析发布的 `manifests/COMMON_POOL_ACCEPTED_PARENTS_V4.json`、`COMMON_POOL_PARTIAL_TARGET_PARENTS_V1.json`、`COMMON_POOL_SOURCE_DISPOSITIONS_V3.json` 和 `A11_BATCH3_VIEW_ACCEPTANCE_V1.json`，核对其引用。旧索引/原始回执保持不变。

- 严格四目标索引为 23 个 train 父源，dev=0；部分目标索引另列 door-close 一个父源。G0 可用父源并集为 24，不把部分有效源重复计入严格索引。
- door-close 的 gain_local_plus、gain_local_minus、pair 保持 mask=false / target=null，禁止用 0 填补。G0=0、mask=true、两 repeat 有效。
- door-close 的绝对成功监督按既有协议在父源内以实际 raw C10 去重。预定锚点 Q_a0 为 canonical：r0/r1 均 success=1，分别于绝对 s42/s41 终局。一组相同行为、两个 repeat；六个物理 Q 分支不产生六份独立监督。具体终局/sidecar/SHA 在视图决定及科学审阅中。
- D5/GAF 仅有可供核对的原始字段；完整窗口和训练视图仍须各自 CPU 验收。LVM 正例/示范资格未授予。任何方法都不能把 normal 成功轨迹直接改标为专家示范。
- source/parent split、public v1、sidecar 与 supplement_v2 不变；partial 硬链接不计新样本。25 源已处理，475 源仍按既定计划，不为 raw alias 或提前成功补源。

在原 CPU 任务的后续回执中列明视图接收/拒绝原因及样本数即可，无需重跑旧测试或扫描全数据树。本文是只读交接，不要求 B 等待 A 完成整个池，也不授予训练/评测计算。
