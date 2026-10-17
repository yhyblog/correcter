# H10 推理效率表与辅助网络开销

2026-09-25 的 SmolVLA/X-VLA 小批量补测已完成。每底座覆盖预先固定的 20 个 MT50 任务，各采一个真实 cut5；每个切点对 N、R、Post 各预热一次、计时五次，每格 100 次，共 600 次有效查询和 120 次预热查询。40 个源全部完成，提前终止和技术失败均为零。设备为八张 H100 80GB，每卡一个查询流、batch size 1。两底座使用已训练的专属 D/G0 与 L11/fit9101 四成员 Q，无训练更新。

## 补全原效率表

| 底座 | 方法 | 完整策略调用/episode | 干预/episode | 单次查询均值（ms）↓ | 单次查询 P95（ms）↓ | 查询测速次数 |
|---|---|---:|---:|---:|---:|---:|
| π0.5 | N | 15.130 | 0 | 238.256 | 247.030 | 1,759 |
| π0.5 | R-multi | 14.452 | 2.034 | 236.563 | 245.881 | 310 |
| π0.5 | Post-multi | 14.248 | 2.050 | 246.648 | 255.061 | 253 |
| SmolVLA | N | 19.532† | 0 | 161.507 | 166.298 | 100 |
| SmolVLA | R-multi | 20.550 | 2.654 | 161.478 | 166.859 | 100 |
| SmolVLA | Post-multi | 20.382 | 2.700 | 172.679 | 177.459 | 100 |
| X-VLA | N | 12.264 | 0 | 95.540 | 98.161 | 100 |
| X-VLA | R-multi | 13.402 | 2.910 | 96.381 | 99.021 | 100 |
| X-VLA | Post-multi | 13.412 | 2.884 | 105.719 | 108.036 | 100 |

前两项 episode 指标复用原 H10 正式评测；除 † SmolVLA N 为 496 个有效 episode、另有 4 个未知外，其余各 500 个。测速次数是独立计时记录数，与 episode 指标的分母不同。SmolVLA/X-VLA 的 N 零干预来自原生控制器定义。

π0.5 的三个测速值来自此前独立的低并发机制实验：五任务、100 个测试父源，每卡一环境，排除每 episode 每类操作第一次出现；N 取 plan，R/Post 取 intervene。SmolVLA/X-VLA 是本次 20 任务真实切点上重复调用的查询级补测，测量时不推进环境，不依据 G0 是否超过阈值筛选切点。因此表中的 R-multi/Post-multi 表示对应部署方法的查询算子；本次计时不新增 multi 闭环成功率结果。三底座的时间来自不同采样批次。

单次查询覆盖完整原生策略采样和动作接口处理；Post 还包括 Q objective 构造、四成员动作梯度和自身半径投影。这里的 Post 查询不含前置特征编码与 D/G0 监测，其耗时在下表单列。GPU 在计时边界同步，Q 保持历史 CPU 实现。模型加载、环境步进、渲染、预热及本地 RPC 传输不计入本表。包含 RPC 的查询墙钟均值分别为 Smol N/R/Post 161.608/161.568/173.432 ms、X N/R/Post 95.632/96.467/106.409 ms。测速适配器省去旧 Velocity 调试桥的流状态复制与逐步检查，保留原生策略与 Post 数值路径。

## 辅助网络影响

以下都是每次对应操作的均值；每格 100 次，D/G0 为各自两个成员合计，Q 为四成员合计。

| 组件 | SmolVLA（ms） | X-VLA（ms） |
|---|---:|---:|
| 外部历史视觉编码，5 帧 | 51.152 | 49.252 |
| D 两成员 | 3.668 | 3.633 |
| G0 两成员 | 1.896 | 1.856 |
| 完整监测，包括编码、上下文与 D/G0 | 57.335 | 55.342 |
| Q objective 构造 | 5.790 | 5.586 |
| Q 动作梯度 | 3.512 | 3.488 |
| 动作投影 | 0.655 | 0.648 |
| 单次 Post 相对其自身原生采样新增部分 | 9.958 | 9.722 |

本批次 Q 纠偏新增约 10 ms，相对同一批 Post 调用内的原生采样部分约为 6.1%/10.1%。D/G0 本身合计约 5.56/5.49 ms，前置监测的大部分耗时来自外部视觉编码。完整监测一行已经包含上面的编码和 D/G0，不能重复累加；Post 查询表不含该监测开销。这些结果刻画现有小网络的查询成本；episode 总推理时间还取决于完整策略调用数和实际监测次数。

## 来源

本次 [协议](../experiments/inference_efficiency_20260925/PROTOCOL.md)、[资产与权重](../experiments/inference_efficiency_20260925/assets.json)、[完整报告与逐源链接](../experiments/inference_efficiency_20260925/REPORT.md)、[查询统计](../experiments/inference_efficiency_20260925/QUERY_LATENCY.csv)、[组件统计](../experiments/inference_efficiency_20260925/COMPONENT_LATENCY.csv)、[正式终局](../experiments/inference_efficiency_20260925/RESULT.json)。均值与 P95 使用预热以外的全部计时，P95 从逐查询总时间按 linear 分位数计算。

π0.5 原始 [E_LOCAL_LATENCY.csv](../sim_command/20260919/results/C/C_MECHANISM_20260924_V1/analysis/E_LOCAL_LATENCY.csv)；episode 指标见 [Post 正式结果](EXPERIMENT_FOR_POST.md)。Smol R 的 1,327 次干预来自 [500 源结果索引](../sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/SMOL_R_H10_CALLS.json)所指终局；X R 的 1,455 次干预来自 [逐 episode 结果](../sim_command/20260919/results/C/C_D24_CROSSBASE_H_SWEEP_V1/FINAL_EPISODES.csv)的 H10/R 子集。
