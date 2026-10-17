# 本轮运行发布单

当前有P00_PREP_V1：允许完成本机盘点后的A10/B10 CPU接口准备，GPU训练/推理/仿真上限均为0；不等于正式GPU计算放行。

发布单由分析端创建，必须含本轮campaign/task/revision、protocol/data/code/model身份、owner hostname、shard、明确资源上限及停止条件。执行端不自行制造release，不使用Corrector/coordination中的历史READY。

准备任务不需要模型GPU计算；正式预检也必须列入发布单的数量和资源。分析端据盘点和可审查命令签发，避免空配置或无限额启动。
