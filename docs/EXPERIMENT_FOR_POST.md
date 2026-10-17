# Post 分支正式实验数据汇总

更新日期：2026-09-24。最终配置为 **Post-multi，L11＝BCE＋gain＋0.5pair，固定 fit9101，Q 四成员 1041–1044**。正式 Post 结果共 **14 格、7,000 条有效终局**：π0.5 五个 H 的 multi 与 H10 once，SmolVLA 五个 H 的 multi，X-VLA 三个 H 的 multi。最新补充为 SmolVLA H20/30/40/50 与 X-VLA H20/30，已全部纳入。

本文件集中管理当前 Post 配置及仍可复用的基线、完整 Q 消融、触发器对照；同类数据合表。附录另收录 LIBERO 已有算子适配数据，以及 MetaWorld 固定难度分组和逐任务明细；LIBERO 的旧 BCE 算子与当前 L11 完整方法分别标注。历史版本和失败尝试继续保存在 [实验总表](EXPERIMENT_RESULTS_MASTER.md)，论文布局参考 [论文数据文档](EXPERIMENT_FOR_PAPER.md)，算法对应 [Post 算法说明](ALGORITHM_POST_ZH.md)。本文没有新增评测。

数值导出：[完整 JSON](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/docs/data/EXPERIMENT_FOR_POST_VALUES_20260924.json)；[本次合并来源、CSV 与生成脚本](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924)。文中 **NR** 表示没有可用记录，**N/A** 表示指标不适用，均不等于零。

## 1. MT50 主结果、H 扫描与跨底座适配

表 1 同时覆盖原 E4/E9 主结果与 H 扫描、N→R→Post 组件比较，以及 SmolVLA/X-VLA 适配，避免拆成多张重复表。**Native（N）**为原策略按 H 正常执行；**Replan（R）**为 G0 触发后仅重规划；**Post**在相同触发机制下进一步纠偏。R 与 Post 在本表均为 multi，不限制全局触发总次数，其余合法时机、阈值与承诺规则保持固定。

每底座预定 MT50 全部 50 个任务、每任务 10 个固定源，共 500 条；同底座各 H 复用同一源集合。成功率为有效终局成功数/有效终局数。除 † 外均为 500 条；† SmolVLA H10 Native 只有 496 条有效、4 条未知，234 个成功，以 496 为分母；这 4 条没有补为失败。Policy Calls 与 Interventions 为**每个有效 episode 的平均值，包含任务成功和失败**，并非“只在成功任务中”的均值。

| Backbone | H | Native SR (%) | Native Policy Calls | Replan SR (%) | Replan Policy Calls | Post SR (%) | Post Policy Calls | Post Interventions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| π0.5 | 10 | 61.6 | 15.130 | 68.6 | 14.452 | 69.2 | 14.248 | 2.050 |
| π0.5 | 20 | 48.0 | 9.372 | 64.8 | 10.158 | 67.2 | 9.968 | 2.390 |
| π0.5 | 30 | 41.0 | 6.964 | 66.0 | 8.650 | 66.2 | 8.678 | 2.616 |
| π0.5 | 40 | 41.0 | 5.602 | 63.6 | 8.276 | 64.8 | 7.966 | 2.594 |
| π0.5 | 50 | 39.2 | 4.312 | 64.2 | 7.584 | 65.2 | 7.422 | 2.624 |
| SmolVLA | 10 | 47.2† | 19.532† | 49.0 | 20.550 | 50.0 | 20.382 | 2.700 |
| SmolVLA | 20 | 45.2 | 9.996 | 49.2 | 13.328 | 50.2 | 13.338 | 3.096 |
| SmolVLA | 30 | 41.0 | 7.036 | 46.8 | 11.212 | 47.6 | 11.098 | 3.194 |
| SmolVLA | 40 | 38.2 | 5.780 | 44.4 | 10.302 | 44.6 | 10.134 | 3.200 |
| SmolVLA | 50 | 33.8 | 4.576 | 45.2 | 9.462 | 45.6 | 9.280 | 3.172 |
| X-VLA | 10 | 80.6 | 12.264 | 82.4 | 13.402 | 82.2 | 13.412 | 2.884 |
| X-VLA | 20 | 77.6 | 6.612 | 78.6 | 10.524 | 79.6 | 10.352 | 3.396 |
| X-VLA | 30 | 77.0 | 4.572 | 78.8 | 9.584 | 77.0 | 9.898 | 3.848 |

**比较范围。** H 是正常执行队列长度，预测 chunk 不随 H 改变；π0.5/SmolVLA raw50，X-VLA raw30，干预承诺 C10，结束后丢弃未执行尾部并恢复正常 H。π0.5 使用 NVIDIA EGL、30Hz、动作尺度 .015；SmolVLA/X-VLA 使用其冻结 Mesa、80Hz、.01 协议。因此比较应在同底座内部进行，表中跨底座的原始成功率不是统一协议下的模型排名。SmolVLA H10 的 N 与 Post 不能用完整 500 对 496 直接构造配对检验。

**读数边界。** π0.5 Post 相对同 H Native 提高 7.6–26.0pp，但相对 Replan 的点差只有 0.2–2.4pp；相应配对统计见表 6。SmolVLA 五 H 的 Post 均高于其 Native 点估计；X-VLA H30 Post 与 Native 同为 77.0%，低于 Replan 的 78.8%。不将结果写成所有底座、所有 H 都有额外纠偏增益。π0.5 H10 Post 的调用数低于 Native；H>10 时 Post 的调用数高于同 H Native，不能概括为普遍减少策略调用。

来源：[原八格 L11 Post 终局](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json)、[新增六格 Post 与对应 N/R](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_CROSSBASE_H_SWEEP_DATA.json)、[Smol H10 R 调用](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/SMOL_R_H10_CALLS.json)、[跨底座 H10 N 有效源](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_D24_E8_POST_V1_r1/VALID_N_INDEX.json)。统一表格导出：[MAIN_H_SWEEP.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/MAIN_H_SWEEP.csv)。

## 2. 外部方法对比

表 2 使用相同 π0.5 SFT030000、H10、MT50 原 500 源；N/R/Post 三行复用表 1，**不是额外实验**。外部方法使用各自实际实现与训练资产，干预预算未完全一致，属于本地系统比较。GAF 标为 adapted，不能当成官方协议的原样复现。

| Method | Success Rate (%) | Policy Calls | Interventions |
| --- | --- | --- | --- |
| Native π0.5 | 61.6 | 15.130 | 0.000 |
| Replan-only (G0-multi) | 68.6 | 14.452 | 2.034 |
| Post L11 (G0-multi) | 69.2 | 14.248 | 2.050 |
| VLA-Corrector | 63.8 | 19.961† | 3.199† |
| GAF-v1 adapted | 63.0 | 14.864 | N/A |

† VLA-Corrector 成功率覆盖全部 500 源，其中 8 条由已保存终局日志恢复并独立标记；精确调用与干预费用只覆盖 492 条，8 条费用保持未知。GAF 为连续 flow 引导，离散干预次数不适用。GAF 使用 15 个训练父源、2 个内部 holdout、三个 critic 各 10,000 更新；这些训练数据与 Post 不完全相同。

当前 L11 Post 相对 VLA-Corrector/GAF 的点差为 +5.4/+6.2pp，对应救回/损害为 62/35 与 62/31，统计见表 6。没有统一记录条件下的端到端速度排名；也不由本表宣称同数据预算、公平训练成本或通用 SOTA。

来源：[VLA-Corrector 合并终局](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_E3_UNSTARTED_CONTINUATION_V1/COMBINED_EPISODES.json)、[GAF 终局](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/FINAL_SUMMARY.json)；费用与未知源保存于 [本次数值导出](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/docs/data/EXPERIMENT_FOR_POST_VALUES_20260924.json)。

## 3. 完整 Q 损失消融与最终选型

表 3 合并开发评估与补充选型结果，全部为 π0.5、Post-multi、H10。**四种损失均实际重新训练 Q 的全部参数**，每种损失 3 个 fit、每 fit 四成员、每成员 4,000 更新；没有把只改推理损失或历史局部参数微调当作完整消融。

开发集为五任务各 20 源，共 100；选型集为五任务各 10 源，共 50。三 fit 顺序均为 9101/9102/9103；每 fit 复用相同源，不能将三次评测合称 150 个独立选型初态。± 为三 fit 成功率的**样本标准差**，不是二项误差或均值置信区间。Policy Calls 按各集合全部有效 episode 汇总。

| Loss ID | Objective | Dev SR by Fit (%) | Dev SR, Mean ± SD (%) | Dev Policy Calls | Selection SR by Fit (%) | Selection SR, Mean ± SD (%) | Selection Policy Calls |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L00 | BCE | 65.0 / 68.0 / 69.0 | 67.33 ± 2.08 | 16.297 | 76.0 / 70.0 / 70.0 | 72.00 ± 3.46 | 15.813 |
| L10 | BCE + gain | 68.0 / 67.0 / 68.0 | 67.67 ± 0.58 | 16.310 | 70.0 / 70.0 / 68.0 | 69.33 ± 1.15 | 16.253 |
| L01 | BCE + 0.5pair | 70.0 / 68.0 / 69.0 | 69.00 ± 1.00 | 16.043 | 70.0 / 70.0 / 66.0 | 68.67 ± 2.31 | 16.260 |
| L11 (Selected) | BCE + gain + 0.5pair | 69.0 / 67.0 / 67.0 | 67.67 ± 1.15 | 16.277 | 74.0 / 72.0 / 70.0 | 72.00 ± 2.00 | 15.513 |

当前选择依据是**已揭晓选型集上三 fit 均值优先、并列时观察到的 SD 较小**：L11 与 L00 都为 72.00%，L11 的 SD 为 2.00、L00 为 3.46，因此采用 L11；部署固定 fit9101，不再次按评测表现挑 fit。L10 的 SD 更小但均值更低，L01 在开发集上更高。数据不支持“L11 在所有集合最优”“L11 的总体方差最小”或“每个损失项单独加入都有效”。

**选型集已揭晓，且其 50 源包含在主表 π0.5 的 500 源中；H10 L11 multi 复用了这 50 条有效结果。** 因此主表不能表述为完全未触及的盲测。历史开发集选择 L01 的决定仍留在总表，当前表不混用旧 L01 的最终成绩。

π0.5 共训练 48 个 Q 成员、192,000 更新；固定 train600、train-only PCA/归一化、AdamW lr3e−4、weight decay0.01、batch32、clip1；同(fit,member)的不同 loss 使用配对初始化及采样流。底座、D/G0 与编码器冻结。本表没有进行数据效率实验。

来源：[完整 Q 训练终局](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json)、[既有逐 episode 数据](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/TECHNICAL_EPISODES_ALL_METHODS.csv)。逐 fit 成功数、调用、flow、干预和梯度保存在 [LOSS_ABLATION_PER_FIT.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/LOSS_ABLATION_PER_FIT.csv)。

## 4. 触发机制与单次／多次：统一对照表

表 4 汇总原本分散的次数、随机时机和异常触发对照，按 Source Set 区分。MT50 行使用主表 500 源；E6 使用五任务各 10 个 ordinal10–19 的独立源，共 50，与主表 ordinal0–9 不重叠。E6 的四行复用同一 50 源，不能与 MT50 行横向当成相同难度比较。

| Source Set | Method | Trigger / Count | H | Success Rate (%) | Policy Calls | Interventions |
| --- | --- | --- | --- | --- | --- | --- |
| MT50 | Post L11 | G0-once | 10 | 68.6 | 13.840 | 0.782 |
| MT50 | Post L11 | G0-multi | 10 | 69.2 | 14.248 | 2.050 |
| MT50 | Replan-only | G0-once | 10 | 67.2 | 14.156 | 0.782 |
| MT50 | Replan-only | Random-once | 10 | 61.4 | 15.632 | 0.500 |
| MT50 | Replan-only | G0-multi | 10 | 68.6 | 14.452 | 2.034 |
| MT50 | Replan-only | G0-once | 20 | 62.4 | 8.742 | 0.814 |
| MT50 | Replan-only | Random-once | 20 | 48.4 | 10.144 | 0.618 |
| MT50 | Replan-only | G0-multi | 20 | 64.8 | 10.158 | 2.412 |
| MT50 | Replan-only | G0-once | 30 | 61.4 | 6.690 | 0.830 |
| MT50 | Replan-only | Random-once | 30 | 42.0 | 7.944 | 0.682 |
| MT50 | Replan-only | G0-multi | 30 | 66.0 | 8.650 | 2.568 |
| MT50 | Replan-only | G0-once | 40 | 58.0 | 5.872 | 0.830 |
| MT50 | Replan-only | Random-once | 40 | 42.2 | 6.326 | 0.674 |
| MT50 | Replan-only | G0-multi | 40 | 63.6 | 8.276 | 2.734 |
| MT50 | Replan-only | G0-once | 50 | 59.4 | 4.844 | 0.816 |
| MT50 | Replan-only | Random-once | 50 | 39.2 | 5.508 | 0.690 |
| MT50 | Replan-only | G0-multi | 50 | 64.2 | 7.584 | 2.676 |
| E6 | Replan-only | G0-once | 10 | 52.0 | 19.460 | 0.920 |
| E6 | Replan-only | G0-multi | 10 | 52.0 | 21.440 | 4.800 |
| E6 | Replan-only | D5-once | 10 | 60.0 | 17.680 | 0.900 |
| E6 | Replan-only | D5-multi | 10 | 62.0 | 20.020 | 7.600 |

当前同权重 L11 Post 的 once/multi 直接对照只覆盖 H10：68.6%→69.2%，救回 10、损害 7；配对区间包含零，不能写成多次显著优于单次。其余 H 的正式 Post 主表均为 multi。旧 Post 随机单次结果使用旧 Q，本文件不将其重标为 L11；**随机时机证据来自不依赖 Q 的 Replan-only 对照**。

R 的 Random-once 在运行前固定随机时机；任务在该时机前终止或时机不合法时不会强制补干预，因此 G0-once 与 Random-once 实际干预率不同。这是两种时机机制的总体效果比较，不是严格等实际干预次数的纯时机效应。Random-multi 已取消，没有结果可填。

E6 的 D5 阈值 0.2521600950570383 在旧开发 100 源上按 95/100 报警率匹配，不按测试成功率选择；G0 阈值 0.05。E6 once/multi 中 G0 成功率都没有高于 D5。multi 的 G0 平均干预较少（4.8 vs 7.6），但策略调用更多（21.44 vs 20.02），不能据此宣称整体更省。报警匹配也不等于 multi 下实际干预预算相同。

来源与逐行计数：[消融和触发结果合并 JSON](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/POST_ABLATION_TRIGGER_TABLES.json)、[TRIGGER_MODES.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/TRIGGER_MODES.csv)。

## 5. 正式 Post 运行成本与计量覆盖

表 5 集中保存 14 格 Post 的总量与时间；表 1、表 4 中正式 Post 行的平均调用值来自这些总量。每格 500 个有效 episode；计量包含合法任务失败，排除历史技术无效尝试。一次 Policy Call 是完整 VLA 计划采样，NFE=10，因此本组 Flow Steps=10×Policy Calls。Post 每次纠偏使用一次动作梯度，不更新策略或 critic 参数。

| Backbone | H | Count Mode | Total Policy Calls | Total Flow Steps | Total Interventions | Observed Action Gradients | Gradient Coverage | Mean Episode Time (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| π0.5 | 10 | multi | 7,124 | 71,240 | 1,025 | 1,025 | Cell total | 107.769 |
| π0.5 | 10 | once | 6,920 | 69,200 | 391 | 391 | Cell total | 94.630 |
| π0.5 | 20 | multi | 4,984 | 49,840 | 1,195 | 1,195 | 500/500 | 104.260 |
| π0.5 | 30 | multi | 4,339 | 43,390 | 1,308 | 1,308 | 500/500 | 73.721 |
| π0.5 | 40 | multi | 3,983 | 39,830 | 1,297 | 1,297 | 500/500 | 70.522 |
| π0.5 | 50 | multi | 3,711 | 37,110 | 1,312 | 1,312 | 500/500 | 73.532 |
| SmolVLA | 10 | multi | 10,191 | 101,910 | 1,350 | 1,350 | 389/500 | 121.964 |
| SmolVLA | 20 | multi | 6,669 | 66,690 | 1,548 | 1,548 | 500/500 | 114.695 |
| SmolVLA | 30 | multi | 5,549 | 55,490 | 1,597 | 1,597 | 500/500 | 113.247 |
| SmolVLA | 40 | multi | 5,067 | 50,670 | 1,600 | 1,600 | 500/500 | 108.318 |
| SmolVLA | 50 | multi | 4,640 | 46,400 | 1,586 | 1,586 | 500/500 | 104.607 |
| X-VLA | 10 | multi | 6,706 | 67,060 | 1,442 | 1,442 | 398/500 | 101.051 |
| X-VLA | 20 | multi | 5,176 | 51,760 | 1,698 | 1,698 | 500/500 | 154.210 |
| X-VLA | 30 | multi | 4,949 | 49,490 | 1,924 | 1,924 | 500/500 | 155.504 |

**覆盖说明。** π0.5 H10 的梯度总数由原单元 RESULT 明确记录，但统一逐 episode 导出没有该字段，故写 Cell total，不伪造逐源覆盖。Smol/X H10 的梯度字段显式覆盖 389/500、398/500，表中为已知记录之和，缺项不补零；不由这些稀疏行计算完整总体梯度均值。新增 H 的完整覆盖包括有明确证据的结构性零，细分保存在原汇总中。

Mean Episode Time 为保存的 episode elapsed_seconds 描述性均值，受节点、并发、模拟器、记录开销影响；不是纯推理延迟、GPU 秒、能耗或跨方法速度结论。历史技术失败、恢复尝试和占卡费用另存总表，未隐藏为成功样本成本。表 1 的 Policy Calls 不包含 D/G0、编码器与 Q 前向，不能等同全部计算量。

来源：[原 L11 计量](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json)、[π0.5 H10 原单元梯度总数](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_L11_RENDER_RECOVERY_V1/RESULT.json)、[新增 H 原始计量及覆盖](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_CROSSBASE_H_SWEEP_DATA.json)、[新增 H 保存计时](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_CROSSBASE_POST_ELAPSED.json)。导出：[FORMAL_POST_COSTS.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/FORMAL_POST_COSTS.csv)。

## 6. 逐源配对差异：集中统计表

表 6 合并既有 Post、时机及 E6 配对结果。**救回/损害始终按 Comparison 左侧相对右侧定义**。MT50 各行共同有效源为 500，E6 为 50。Paired normal 为固定任务、任务内配对差的方差及逐项 95% 正态近似；Paired bootstrap 为原已发布的任务内配对源 bootstrap（2,000 次、seed20260921）。这里只迁移已完成统计，没有新跑 bootstrap。

| Source Set | Comparison (Left − Right) | Rescued | Harmed | ΔSR (pp) | 95% CI (pp) | CI Method | McNemar p | Holm p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MT50 | π0.5 H10 Post–N | 62 | 24 | +7.6 | [4.38, 10.82] | Paired normal | <0.001 | <0.001 |
| MT50 | π0.5 H10 Post–R | 17 | 14 | +0.6 | [-1.59, 2.79] | Paired normal | 0.720 | 1.000 |
| MT50 | π0.5 H20 Post–N | 105 | 9 | +19.2 | [15.90, 22.50] | Paired normal | <0.001 | <0.001 |
| MT50 | π0.5 H20 Post–R | 26 | 14 | +2.4 | [-0.06, 4.86] | Paired normal | 0.081 | 0.403 |
| MT50 | π0.5 H30 Post–N | 139 | 13 | +25.2 | [21.55, 28.85] | Paired normal | <0.001 | <0.001 |
| MT50 | π0.5 H30 Post–R | 22 | 21 | +0.2 | [-2.36, 2.76] | Paired normal | 1.000 | 1.000 |
| MT50 | π0.5 H40 Post–N | 130 | 11 | +23.8 | [20.34, 27.26] | Paired normal | <0.001 | <0.001 |
| MT50 | π0.5 H40 Post–R | 22 | 16 | +1.2 | [-1.22, 3.62] | Paired normal | 0.418 | 1.000 |
| MT50 | π0.5 H50 Post–N | 137 | 7 | +26.0 | [22.45, 29.55] | Paired normal | <0.001 | <0.001 |
| MT50 | π0.5 H50 Post–R | 21 | 16 | +1.0 | [-1.40, 3.40] | Paired normal | 0.511 | 1.000 |
| MT50 | π0.5 H10 Post multi–once | 10 | 7 | +0.6 | [-0.99, 2.19] | Paired normal | 0.629 | — |
| MT50 | π0.5 H10 Post–VLA-Corrector | 62 | 35 | +5.4 | [1.84, 8.96] | Paired normal | 0.008 | — |
| MT50 | π0.5 H10 Post–GAF | 62 | 31 | +6.2 | [2.77, 9.63] | Paired normal | 0.002 | — |
| MT50 | SmolVLA H20 Post–N | 47 | 22 | +5.0 | [1.85, 8.15] | Paired normal | 0.004 | — |
| MT50 | SmolVLA H20 Post–R | 16 | 11 | +1.0 | [-1.04, 3.04] | Paired normal | 0.442 | — |
| MT50 | SmolVLA H30 Post–N | 56 | 23 | +6.6 | [3.24, 9.96] | Paired normal | <0.001 | — |
| MT50 | SmolVLA H30 Post–R | 12 | 8 | +0.8 | [-0.97, 2.57] | Paired normal | 0.503 | — |
| MT50 | SmolVLA H40 Post–N | 58 | 26 | +6.4 | [2.93, 9.87] | Paired normal | <0.001 | — |
| MT50 | SmolVLA H40 Post–R | 12 | 11 | +0.2 | [-1.67, 2.07] | Paired normal | 1.000 | — |
| MT50 | SmolVLA H50 Post–N | 82 | 23 | +11.8 | [8.15, 15.45] | Paired normal | <0.001 | — |
| MT50 | SmolVLA H50 Post–R | 12 | 10 | +0.4 | [-1.40, 2.20] | Paired normal | 0.832 | — |
| MT50 | X-VLA H20 Post–N | 36 | 26 | +2.0 | [-0.92, 4.92] | Paired normal | 0.253 | — |
| MT50 | X-VLA H20 Post–R | 15 | 10 | +1.0 | [-0.99, 2.99] | Paired normal | 0.424 | — |
| MT50 | X-VLA H30 Post–N | 33 | 33 | +0.0 | [-2.84, 2.84] | Paired normal | 1.000 | — |
| MT50 | X-VLA H30 Post–R | 12 | 21 | -1.8 | [-3.97, 0.37] | Paired normal | 0.163 | — |
| MT50 | π0.5 H10 R G0-multi - G0-once | 10 | 3 | +1.4 | [0.20, 2.80] | Paired bootstrap | NR | — |
| MT50 | π0.5 H10 R Random-once - G0-once | 28 | 57 | -5.8 | [-9.00, -2.60] | Paired bootstrap | NR | — |
| MT50 | π0.5 H20 R G0-multi - G0-once | 21 | 9 | +2.4 | [0.40, 4.40] | Paired bootstrap | NR | — |
| MT50 | π0.5 H20 R Random-once - G0-once | 13 | 83 | -14.0 | [-17.20, -11.00] | Paired bootstrap | NR | — |
| MT50 | π0.5 H30 R G0-multi - G0-once | 27 | 4 | +4.6 | [2.60, 6.60] | Paired bootstrap | NR | — |
| MT50 | π0.5 H30 R Random-once - G0-once | 12 | 109 | -19.4 | [-22.60, -16.40] | Paired bootstrap | NR | — |
| MT50 | π0.5 H40 R G0-multi - G0-once | 34 | 6 | +5.6 | [3.40, 7.80] | Paired bootstrap | NR | — |
| MT50 | π0.5 H40 R Random-once - G0-once | 23 | 102 | -15.8 | [-19.40, -12.40] | Paired bootstrap | NR | — |
| MT50 | π0.5 H50 R G0-multi - G0-once | 32 | 8 | +4.8 | [2.60, 7.00] | Paired bootstrap | NR | — |
| MT50 | π0.5 H50 R Random-once - G0-once | 12 | 113 | -20.2 | [-23.60, -16.60] | Paired bootstrap | NR | — |
| E6 | R D5-once − G0-once | 5 | 1 | +8.0 | NR | NR | 0.219 | — |
| E6 | R G0-multi − D5-multi | 2 | 7 | -10.0 | [-22.00, 0.00] | Paired bootstrap | 0.180 | — |

所有区间是逐项区间；π0.5 五 H 的 Post−N、Post−R 分别作五次 Holm 校正，其他行无该校正，故 Holm p 为“—”。NR 表示原结果没有对应检验/区间，非 p=1 或无差异。上述统计不覆盖训练 seed、新任务及协议变化的不确定性，也不能消除选型初态重叠。当前统一统计包未生成最终 L11 的 Smol/X H10 配对区间，因此不拿旧 Q 区间代替；其成功率和调用结果已完整列于表 1。

来源：[π0.5／外部／次数配对](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_L11_POST_PAIRED_STATS.json)、[新增跨底座 H 配对](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_CROSSBASE_POST_PAIRED_STATS.json)、[R 时机及次数配对](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_R_TRIGGER_MODES_V1/FINAL_PAIRED.json)、[E6 multi 配对](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_PRIMARY_VALIDATION_V1/PAIRED.json)。全部精确 p 值与区间（未四舍五入）见 [PAIRED_COMPARISONS.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/PAIRED_COMPARISONS.csv)。

## 7. 训练覆盖、参数与方法描述所需数据

| Backbone | Base Checkpoint | Predicted Chunk | Evaluated H | Auxiliary Data / Training |
| --- | --- | --- | --- | --- |
| π0.5 | MT50 SFT030000 | 50 | 10 / 20 / 30 / 40 / 50 | 历史五任务 train600；完整 Q 四 loss×三 fit×四成员，各 4,000 更新；最终 L11/fit9101 |
| SmolVLA | MT50 SFT050000 | 50 | 10 / 20 / 30 / 40 / 50 | 专属 200 train＋50 dev 计划父源，有效 cut 188/47；首轮 D/G0/Q 合计 32,000 更新；完整 Q 四 loss×四成员另 64,000 更新；使用本底座 L11 |
| X-VLA | MT50 SFT030000 | 30 | 10 / 20 / 30 | 专属 200 train＋50 dev 计划父源，有效 cut 191/49；首轮 D/G0/Q 合计 32,000 更新；完整 Q 四 loss×四成员另 64,000 更新；使用本底座 L11 |

Smol/X 首轮的 32,000 为 D 双成员、G0 双成员、Q 四成员各 4,000 的**合计**，不是每类网络各 32,000。它们重新采集本底座数据并训练辅助网络，未直接沿用 π0.5 Q 权重；但仍使用额外冻结 π0.5 特征提供者，其成本须另计。

| Component | Members | Parameters per Member | Total Parameters |
| --- | --- | --- | --- |
| D | 2 | 4,474,116 | 8,948,232 |
| G0 | 2 | 1,468,033 | 2,936,066 |
| Q | 4 | 7,058 | 28,232 |
| Total | 8 | — | 11,912,530 |

11.91M 是附加 D/G0/Q 网络规模，28K 只是 Q，均不包含底座。π0.5 复用冻结编码器，新增编码器参数为零不等于新增编码计算为零；PCA/归一化 buffer 不计入网络参数。Smol/X 的额外冻结特征模型更不能省略。可以描述小规模附加网络，不能据此推出比 VLA 微调更高效。

π0.5 主表评测 MT50 全 50 任务，但 D/G0/Q 的训练覆盖仍是五任务。历史 G0 的收益监督为 5 步承诺、native10 后缀；Q 的终局标签为候选执行 10 步后 native10 续跑。部署使用 C10、不同 H 和 multi，不能直接宣称这些分数是当前部署下已校准的最终成功概率。局部配对采集本身不作为创新或数据效率优势。

来源：[总表 F8 专属训练记录](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/docs/EXPERIMENT_RESULTS_MASTER.md)、[完整 Q 训练设置（其中旧成绩不复用）](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/analysis_20260923_claims/component_notes.md)、[参数与计量定义](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/analysis_20260923_claims/costs_notes.md)。

## 8. 细粒度数据入口与尚不能归入正式 Post 的项目

π0.5 各 H 的 50 任务 N/R/Post 成功数保存在 [逐任务 CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_L11_POST_PER_TASK.csv)；新跨底座 H 的有效 episode 及来源索引保存在 [跨底座逐 episode CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_CROSSBASE_H_SWEEP_VALID_EPISODES.csv)。本次已将三底座完整逐任务成功率与固定难度统计加入附录B/C，并保留包含分母和调用数的CSV。

| Item | Current Evidence | Treatment in This Document |
| --- | --- | --- |
| L11 Post Random-once | 当前没有同版本正式结果；已有 Post 随机对照绑定旧 Q | 不填成 L11；保留 R 随机对照作为明确标注的辅助证据 |
| L11 Post once at H20/30/40/50 | 当前没有同版本正式结果 | H 扫描只报告已完成 multi，不移用旧 once |
| Real-world results | 已有用户提供的三任务计数，每任务 60 次；Post 分支、Q 版本和触发配置尚未绑定 | 数值仍在总表，正式 Post 结果待身份确认后再加入 |
| LIBERO full method | 完整 D/G0/L11 系统缺结果；已有 operator-only 不等价 | 附录A列已有Native/算子结果与40任务明细；Full仍标NR |
| QGF / QPILOTS | 文献资料可用，未找到本地同协议实际终局 | 不将论文数值冒充复现实验 |
| Historical L01 / old Q / demo videos | 历史数据及选择性展示保留 | 不混入当前正式主表；演示视频不计总体成功率 |

本次核对以终局结果、有效源索引和小型汇总为准；较晚回执中的演示录像与缺口审计未产生新的正式成绩。最新来源与纳入决定见 [Post 来源审计](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/POST_LATEST_SOURCE_AUDIT.json)。原始数据、现有总表与其他分支文档均保留。

## Appendix A. LIBERO：已有算子适配结果与完整方法状态

本附录补入已经执行的 LIBERO 数据，并保持配置身份独立。**现有 Post 是算子适配，不是主表的 L11＋D/G0＋multi 完整方法**：使用官方 π0.5 LIBERO 权重及 normalizer，预测 chunk=10、正常执行 K=5、NFE=10；执行20个命令后的自然重规划点固定一次纠偏，只修改5步 XYZ/夹爪，旋转与未用尾部不改，随后恢复 native K5。没有 D/G0 触发；critic 为 BCE 原生 LIBERO 头，四成员 seed9301–9304，各训练4,000步。

训练用120候选/24父源，仅5个负例；描述性验证40候选/8父源全部成功。因此不能由该验证集声称已学会可靠故障区分。测试使用保存的随机 reset/policy seeds，而非官方固定初态榜单。四个套件各10任务、每任务每方法计划10条：Native 399条有效、Post 400条有效；Goal/task0 的 Native 源 D24_LIBERO_libero_goal_t00_e08 未知，未填成失败。各自有效分母上的成功率和平均调用如下；此处不是三底座主表新增的正式 L11 格。

### A1. Suite-level results

| Suite | Native SR (%) | Post Operator SR (%) | Native Policy Calls | Post Operator Policy Calls | Post Interventions | Full L11 Post SR (%) |
| --- | --- | --- | --- | --- | --- | --- |
| Spatial | 98.00 | 96.00 | 21.990 | 22.130 | 0.380 | NR |
| Object | 100.00 | 100.00 | 28.590 | 28.280 | 0.870 | NR |
| Goal | 98.99† | 100.00 | 22.768† | 22.680 | 0.580 | NR |
| Long (LIBERO-10) | 91.00 | 91.00 | 55.320 | 55.200 | 0.640 | NR |
| Overall | 96.99† | 96.75 | 32.190† | 32.072 | 0.618 | NR |

† Goal Native 为98/99，Overall Native 为387/399；Post 分别为100/100与387/400。Full L11 Post 实际测试0条，NR表示**未评测**，不是0%：现有收益监督仅7组train、4组validation且全零，尚未训练/评测完整 D/G0/L11 系统。新增开发40次中30有效、10技术失败是开发数据，不填入本表测试成功率。

### A2. Paired outcomes and calls

以下仅在共同有效源上比较 Post Operator−Native：Spatial/Object/Long各100对，Goal99对，合计399对。整体 Post 成功386、Native成功387，5救回/6损害。各自400/399分母的率差不能代替共同399对差值。区间沿用原已发布的逐episode配对正态近似及精确McNemar，未作多重校正；Object的[0,0]不证明等效。

| Suite | Rescued | Harmed | Paired ΔSR (pp) | 95% CI (pp) | McNemar p | Native Paired Policy Calls | Post Paired Policy Calls |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Spatial | 0 | 2 | -2.00 | [-4.76, 0.76] | 0.500 | 21.990 | 22.130 |
| Object | 0 | 0 | +0.00 | [0.00, 0.00] | 1.000 | 28.590 | 28.280 |
| Goal | 1 | 0 | +1.01 | [-0.97, 2.99] | 1.000 | 22.768 | 22.667 |
| Long (LIBERO-10) | 4 | 4 | +0.00 | [-5.57, 5.57] | 1.000 | 55.320 | 55.200 |
| Overall | 5 | 6 | -0.25 | [-1.88, 1.38] | 1.000 | 32.190 | 32.093 |

算子共实际纠偏247次，均为最多一次的固定时刻干预；平均调用32.0725来自完整400条Post，配对调用32.0927来自共同399条，两者口径不同。保存时间字段的范围不同，不据此比较推理速度。以上结果可以作为算子跨环境适配的附录记录，不能当成完整 L11 系统提升成功率的证据。

### A3. Per-task results

每任务通常各10条；†仅Goal/task0 Native为9条，其余字段按各自有效分母计算。救回/损害用该任务共同有效对，任务ID沿各套件的0–9编号。

| Suite | Task ID | Task | Native SR (%) | Post Operator SR (%) | Native Policy Calls | Post Operator Policy Calls | Rescued / Harmed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Spatial | 0 | pick up the black bowl between the plate and the ramekin and place it on the plate | 90.0 | 90.0 | 21.700 | 19.900 | 0 / 0 |
| Spatial | 1 | pick up the black bowl next to the ramekin and place it on the plate | 100.0 | 100.0 | 22.100 | 22.200 | 0 / 0 |
| Spatial | 2 | pick up the black bowl from table center and place it on the plate | 100.0 | 100.0 | 19.500 | 19.300 | 0 / 0 |
| Spatial | 3 | pick up the black bowl on the cookie box and place it on the plate | 100.0 | 100.0 | 17.200 | 17.300 | 0 / 0 |
| Spatial | 4 | pick up the black bowl in the top drawer of the wooden cabinet and place it on the plate | 100.0 | 100.0 | 25.300 | 25.400 | 0 / 0 |
| Spatial | 5 | pick up the black bowl on the ramekin and place it on the plate | 100.0 | 90.0 | 20.700 | 22.600 | 0 / 1 |
| Spatial | 6 | pick up the black bowl next to the cookie box and place it on the plate | 100.0 | 100.0 | 21.500 | 21.400 | 0 / 0 |
| Spatial | 7 | pick up the black bowl on the stove and place it on the plate | 100.0 | 100.0 | 24.500 | 24.100 | 0 / 0 |
| Spatial | 8 | pick up the black bowl next to the plate and place it on the plate | 100.0 | 100.0 | 20.600 | 20.700 | 0 / 0 |
| Spatial | 9 | pick up the black bowl on the wooden cabinet and place it on the plate | 90.0 | 80.0 | 26.800 | 28.400 | 0 / 1 |
| Object | 0 | pick up the alphabet soup and place it in the basket | 100.0 | 100.0 | 30.600 | 30.900 | 0 / 0 |
| Object | 1 | pick up the cream cheese and place it in the basket | 100.0 | 100.0 | 29.300 | 27.200 | 0 / 0 |
| Object | 2 | pick up the salad dressing and place it in the basket | 100.0 | 100.0 | 25.500 | 24.900 | 0 / 0 |
| Object | 3 | pick up the bbq sauce and place it in the basket | 100.0 | 100.0 | 26.900 | 26.100 | 0 / 0 |
| Object | 4 | pick up the ketchup and place it in the basket | 100.0 | 100.0 | 29.300 | 29.000 | 0 / 0 |
| Object | 5 | pick up the tomato sauce and place it in the basket | 100.0 | 100.0 | 29.400 | 27.500 | 0 / 0 |
| Object | 6 | pick up the butter and place it in the basket | 100.0 | 100.0 | 31.200 | 31.800 | 0 / 0 |
| Object | 7 | pick up the milk and place it in the basket | 100.0 | 100.0 | 26.200 | 27.400 | 0 / 0 |
| Object | 8 | pick up the chocolate pudding and place it in the basket | 100.0 | 100.0 | 31.600 | 32.700 | 0 / 0 |
| Object | 9 | pick up the orange juice and place it in the basket | 100.0 | 100.0 | 25.900 | 25.300 | 0 / 0 |
| Goal | 0 | open the middle drawer of the cabinet | 100.0† | 100.0 | 24.444† | 25.500 | 0 / 0 |
| Goal | 1 | put the bowl on the stove | 90.0 | 100.0 | 21.400 | 17.300 | 1 / 0 |
| Goal | 2 | put the wine bottle on top of the cabinet | 100.0 | 100.0 | 18.000 | 18.200 | 0 / 0 |
| Goal | 3 | open the top drawer and put the bowl inside | 100.0 | 100.0 | 38.800 | 39.500 | 0 / 0 |
| Goal | 4 | put the bowl on top of the cabinet | 100.0 | 100.0 | 18.300 | 17.900 | 0 / 0 |
| Goal | 5 | push the plate to the front of the stove | 100.0 | 100.0 | 30.400 | 32.500 | 0 / 0 |
| Goal | 6 | put the cream cheese in the bowl | 100.0 | 100.0 | 18.700 | 18.600 | 0 / 0 |
| Goal | 7 | turn on the stove | 100.0 | 100.0 | 15.400 | 15.100 | 0 / 0 |
| Goal | 8 | put the bowl on the plate | 100.0 | 100.0 | 15.300 | 15.100 | 0 / 0 |
| Goal | 9 | put the wine bottle on the rack | 100.0 | 100.0 | 27.100 | 27.100 | 0 / 0 |
| Long (LIBERO-10) | 0 | put both the alphabet soup and the tomato sauce in the basket | 100.0 | 90.0 | 53.800 | 57.900 | 0 / 1 |
| Long (LIBERO-10) | 1 | put both the cream cheese box and the butter in the basket | 100.0 | 100.0 | 50.900 | 50.400 | 0 / 0 |
| Long (LIBERO-10) | 2 | turn on the stove and put the moka pot on it | 90.0 | 90.0 | 56.900 | 57.500 | 1 / 1 |
| Long (LIBERO-10) | 3 | put the black bowl in the bottom drawer of the cabinet and close it | 90.0 | 100.0 | 50.600 | 45.100 | 1 / 0 |
| Long (LIBERO-10) | 4 | put the white mug on the left plate and put the yellow and white mug on the right plate | 90.0 | 100.0 | 52.100 | 46.200 | 1 / 0 |
| Long (LIBERO-10) | 5 | pick up the book and place it in the back compartment of the caddy | 100.0 | 100.0 | 36.000 | 38.600 | 0 / 0 |
| Long (LIBERO-10) | 6 | put the white mug on the plate and put the chocolate pudding to the right of the plate | 90.0 | 90.0 | 50.800 | 50.500 | 0 / 0 |
| Long (LIBERO-10) | 7 | put both the alphabet soup and the cream cheese box in the basket | 100.0 | 100.0 | 54.600 | 56.000 | 0 / 0 |
| Long (LIBERO-10) | 8 | put both moka pots on the stove | 50.0 | 40.0 | 93.300 | 95.700 | 1 / 2 |
| Long (LIBERO-10) | 9 | put the yellow and white mug in the microwave and close it | 100.0 | 100.0 | 54.200 | 54.100 | 0 / 0 |

来源：[Post 算子终局](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/D24_E8_LIBERO_POST_r1/N_POST_SUMMARY.json)、[修复后 Native 有效索引](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1/COMBINED_N_INDEX.json)、[已发布配对数据](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E8_PAIRED.csv)、[Full 方法缺口终局](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/A/A_D24_LIBERO_FULL_NATIVE_V1_RESULT_r13.json)。完整配置、逐任务分母与来源：[LIBERO JSON](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/appendix_data/POST_LIBERO_APPENDIX_DATA.json)；可编辑导出：[套件 CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/appendix_data/LIBERO_SUITE_METRICS.csv)、[40任务 CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/appendix_data/LIBERO_TASK_METRICS.csv)。

## Appendix B. MetaWorld：按固定难度分组统计

### B1. Difficulty definition and aggregation

采用本地固定 **VLA-Corrector 仓库任务难度映射**（commit 9d23a0ba6fad562d3ed1a68fc52c8a12459abb41，配置项 DIFFICULTY_TO_TASKS）：**Easy 28、Medium 11、Hard 6、Very Hard 5**。这不是本文根据成功率新划分的等级，也不标作 MetaWorld 官方难度标准。原配置精确覆盖当前50个 -v3 任务，无需改名；所有 H、三种底座统一使用同一任务映射，不根据 Post 效果更换分组。

下表每格为**组内任务等权平均成功率与任务等权平均 Policy Calls**：先按每个任务的有效episode求均值，再对组内任务平均。数据完整时，每任务10条，与episode加权均值相同。任务组数量不相等，重建MT50总均值须按28/11/6/5加权，不能把四档均值直接平均。R/Post都是multi、Post为最终L11/fit9101，协议与正文表1相同；跨底座仍保留各自模拟器/控制协议。

† SmolVLA H10 Native 的四个未知源保留：Easy 为 277/280 有效；Medium 为 109/110 有效，Hard/Very Hard完整；缺项分别位于drawer-open、handle-press-side、handle-press和hammer。该格完整50任务macro成功率为47.3556%，而正文按496个有效episode合并为47.1774%；分母权重差异已在导出中同时保存macro与micro，不是数据矛盾。

**选型重叠须随表保留：π0.5 的 Very Hard 五任务恰为本次完整 Q 的五个选型任务。H10 Post 的50个源与 L11/fit9101 选型50逐源完全相同，37/50＝74.0%、平均调用15.020就是正文消融中已复用的结果；不能将其称为新的独立困难任务泛化测试。H20–50虽重新执行了不同H，仍沿用这50个已揭晓初态。** 对应源和结果路径核对见 [Very Hard 与选型源重叠记录](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/appendix_data/POST_VERY_HARD_SELECTION_OVERLAP.json)。

### B2. Difficulty-level success and policy calls

| Backbone | H | Difficulty | Tasks | Native SR (%) | Replan SR (%) | Post SR (%) | Native Policy Calls | Replan Policy Calls | Post Policy Calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| π0.5 | 10 | Easy | 28 | 81.07 | 83.57 | 82.86 | 9.975 | 10.189 | 10.254 |
| π0.5 | 10 | Medium | 11 | 31.82 | 46.36 | 47.27 | 22.782 | 20.491 | 20.318 |
| π0.5 | 10 | Hard | 6 | 30.00 | 41.67 | 41.67 | 22.900 | 21.283 | 21.117 |
| π0.5 | 10 | Very Hard | 5 | 56.00 | 66.00 | 74.00 | 17.840 | 16.840 | 15.020 |
| π0.5 | 20 | Easy | 28 | 68.57 | 77.86 | 78.93 | 6.911 | 7.532 | 7.582 |
| π0.5 | 20 | Medium | 11 | 21.82 | 44.55 | 48.18 | 12.518 | 13.800 | 13.464 |
| π0.5 | 20 | Hard | 6 | 8.33 | 40.00 | 41.67 | 13.967 | 14.300 | 14.500 |
| π0.5 | 20 | Very Hard | 5 | 38.00 | 66.00 | 74.00 | 10.720 | 11.880 | 10.200 |
| π0.5 | 30 | Easy | 28 | 55.71 | 77.86 | 78.21 | 5.839 | 6.436 | 6.475 |
| π0.5 | 30 | Medium | 11 | 20.00 | 43.64 | 44.55 | 8.564 | 12.127 | 12.091 |
| π0.5 | 30 | Hard | 6 | 11.67 | 43.33 | 41.67 | 9.067 | 12.600 | 12.733 |
| π0.5 | 30 | Very Hard | 5 | 40.00 | 76.00 | 76.00 | 7.220 | 8.660 | 8.640 |
| π0.5 | 40 | Easy | 28 | 56.79 | 75.71 | 75.36 | 4.657 | 6.125 | 6.075 |
| π0.5 | 40 | Medium | 11 | 17.27 | 42.73 | 46.36 | 7.036 | 11.609 | 10.645 |
| π0.5 | 40 | Hard | 6 | 10.00 | 36.67 | 36.67 | 7.383 | 12.267 | 12.467 |
| π0.5 | 40 | Very Hard | 5 | 42.00 | 74.00 | 80.00 | 5.600 | 8.200 | 7.260 |
| π0.5 | 50 | Easy | 28 | 56.79 | 76.43 | 76.43 | 3.518 | 5.354 | 5.346 |
| π0.5 | 50 | Medium | 11 | 12.73 | 43.64 | 43.64 | 5.500 | 10.982 | 10.527 |
| π0.5 | 50 | Hard | 6 | 8.33 | 38.33 | 40.00 | 5.633 | 11.350 | 11.833 |
| π0.5 | 50 | Very Hard | 5 | 36.00 | 72.00 | 80.00 | 4.560 | 8.080 | 6.920 |
| SmolVLA | 10 | Easy | 28 | 69.01† | 71.43 | 72.50 | 14.470† | 14.771 | 14.604 |
| SmolVLA | 10 | Medium | 11 | 25.05† | 25.45 | 25.45 | 24.858† | 27.582 | 27.564 |
| SmolVLA | 10 | Hard | 6 | 10.00 | 8.33 | 8.33 | 27.817 | 29.700 | 29.650 |
| SmolVLA | 10 | Very Hard | 5 | 20.00 | 24.00 | 28.00 | 25.740 | 26.460 | 25.820 |
| SmolVLA | 20 | Easy | 28 | 64.29 | 68.21 | 67.86 | 7.782 | 10.393 | 10.471 |
| SmolVLA | 20 | Medium | 11 | 25.45 | 28.18 | 30.00 | 12.327 | 18.345 | 18.591 |
| SmolVLA | 20 | Hard | 6 | 15.00 | 15.00 | 18.33 | 13.317 | 16.333 | 16.033 |
| SmolVLA | 20 | Very Hard | 5 | 18.00 | 30.00 | 34.00 | 13.280 | 15.120 | 14.600 |
| SmolVLA | 30 | Easy | 28 | 58.21 | 65.71 | 66.43 | 5.718 | 8.750 | 8.700 |
| SmolVLA | 30 | Medium | 11 | 21.82 | 26.36 | 27.27 | 8.509 | 16.018 | 15.882 |
| SmolVLA | 30 | Hard | 6 | 10.00 | 13.33 | 11.67 | 9.267 | 12.600 | 12.600 |
| SmolVLA | 30 | Very Hard | 5 | 24.00 | 26.00 | 30.00 | 8.500 | 12.760 | 12.200 |
| SmolVLA | 40 | Easy | 28 | 55.00 | 62.86 | 62.50 | 4.725 | 8.107 | 8.107 |
| SmolVLA | 40 | Medium | 11 | 22.73 | 24.55 | 27.27 | 6.773 | 15.464 | 14.827 |
| SmolVLA | 40 | Hard | 6 | 5.00 | 10.00 | 6.67 | 7.817 | 10.833 | 11.050 |
| SmolVLA | 40 | Very Hard | 5 | 18.00 | 26.00 | 28.00 | 7.060 | 10.600 | 10.060 |
| SmolVLA | 50 | Easy | 28 | 50.36 | 63.57 | 63.21 | 3.839 | 7.436 | 7.382 |
| SmolVLA | 50 | Medium | 11 | 19.09 | 24.55 | 28.18 | 5.245 | 14.764 | 13.945 |
| SmolVLA | 50 | Hard | 6 | 5.00 | 15.00 | 10.00 | 5.867 | 9.250 | 9.850 |
| SmolVLA | 50 | Very Hard | 5 | 8.00 | 24.00 | 28.00 | 5.680 | 9.400 | 8.960 |
| X-VLA | 10 | Easy | 28 | 86.79 | 89.29 | 88.57 | 10.471 | 11.296 | 11.321 |
| X-VLA | 10 | Medium | 11 | 73.64 | 72.73 | 72.73 | 14.700 | 17.045 | 16.964 |
| X-VLA | 10 | Hard | 6 | 68.33 | 73.33 | 73.33 | 14.550 | 14.550 | 14.967 |
| X-VLA | 10 | Very Hard | 5 | 76.00 | 76.00 | 78.00 | 14.200 | 15.800 | 15.440 |
| X-VLA | 20 | Easy | 28 | 79.64 | 83.93 | 84.29 | 6.064 | 9.007 | 9.182 |
| X-VLA | 20 | Medium | 11 | 77.27 | 73.64 | 75.45 | 7.091 | 13.573 | 12.664 |
| X-VLA | 20 | Hard | 6 | 78.33 | 73.33 | 75.00 | 6.683 | 9.317 | 9.067 |
| X-VLA | 20 | Very Hard | 5 | 66.00 | 66.00 | 68.00 | 8.540 | 13.760 | 13.360 |
| X-VLA | 30 | Easy | 28 | 79.29 | 83.21 | 84.29 | 4.207 | 8.421 | 8.389 |
| X-VLA | 30 | Medium | 11 | 76.36 | 73.64 | 69.09 | 4.873 | 12.618 | 12.909 |
| X-VLA | 30 | Hard | 6 | 78.33 | 73.33 | 66.67 | 4.617 | 8.250 | 9.967 |
| X-VLA | 30 | Very Hard | 5 | 64.00 | 72.00 | 66.00 | 5.900 | 11.020 | 11.640 |

这些是固定任务集合上的描述性分层，不据单个小组点差宣布显著性，也不将已有难度标签等同于每个底座上实际成功率排序。逐任务仅约10条，尤其Hard/Very Hard组较小；本次没有增加采样或新做分组统计检验。

分组来源：[冻结任务映射配置](/mnt/bn/arnold-recommend/yaohaoyang/vla-corrector/src/lerobot/envs/metaworld_config.json)；本次保存副本和来源身份：[50任务难度映射 JSON](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/appendix_data/POST_MW_TASK_DIFFICULTY.json)。全部52个model×H×difficulty格的分母、成功数、macro/micro与调用：[难度汇总 CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/appendix_data/METAWORLD_DIFFICULTY_METRICS.csv)。

### B3. External comparisons by difficulty

π0.5 H10 原500源的外部比较也使用同一四档映射。表中成功率与调用均按任务等权平均；† VLA-Corrector费用为每任务已知episode均值再平均，Easy缺6条、Medium缺2条费用，不能当成完整总体调用估计。8条log-derived终局仍计入成功率。GAF为本地adapted版本，训练资产不同，比较范围与正文表2相同。

| Difficulty | Tasks | Native SR (%) | Replan SR (%) | VLA-Corrector SR (%) | GAF SR (%) | Post SR (%) | VLA-Corrector Policy Calls | GAF Policy Calls | Post Policy Calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Easy | 28 | 81.07 | 83.57 | 82.14 | 82.14 | 82.86 | 12.924† | 9.929 | 10.254 |
| Medium | 11 | 31.82 | 46.36 | 37.27 | 34.55 | 47.27 | 28.870† | 22.173 | 20.318 |
| Hard | 6 | 30.00 | 41.67 | 31.67 | 31.67 | 41.67 | 31.067 | 22.567 | 21.117 |
| Very Hard | 5 | 56.00 | 66.00 | 58.00 | 56.00 | 74.00 | 25.360 | 17.180 | 15.020 |

VLA-Corrector任务等权的全MT50已知费用均值为19.8527，而正文逐已知episode加权为19.9614；差异来自8条费用未知后两种权重不同。完整覆盖的GAF/Post两种权重一致。组内费用覆盖和逐源缺项保存在 [外部方法细粒度 JSON](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/appendix_data/POST_EXTERNAL_FINE_DATA.json)。

## Appendix C. MetaWorld：50任务逐项结果与完整 H 扫描

### C1. Native / Replan / Post across all H

每个单元格依次为 **Native / Replan / Post 的成功率（%）**。三底座各列50任务，任务按固定难度及名称排序；每任务每方法每H通常10条，†标出SmolVLA H10 Native的9条有效分母，未补造未知结果。X-VLA预测raw30，H40/H50不在本轮范围，故N/A。本表只汇总已完成multi；正文H10 once对照仍独立保留。

| Backbone | Difficulty | Task | H10 SR (%) | H20 SR (%) | H30 SR (%) | H40 SR (%) | H50 SR (%) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| π0.5 | Easy | button-press-topdown-v3 | 90.0 / 90.0 / 90.0 | 60.0 / 90.0 / 90.0 | 70.0 / 90.0 / 90.0 | 70.0 / 90.0 / 90.0 | 60.0 / 90.0 / 90.0 |
| π0.5 | Easy | button-press-topdown-wall-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 |
| π0.5 | Easy | button-press-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 |
| π0.5 | Easy | button-press-wall-v3 | 100.0 / 100.0 / 100.0 | 80.0 / 100.0 / 100.0 | 0.0 / 100.0 / 100.0 | 0.0 / 100.0 / 100.0 | 0.0 / 100.0 / 100.0 |
| π0.5 | Easy | coffee-button-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 |
| π0.5 | Easy | dial-turn-v3 | 30.0 / 30.0 / 30.0 | 20.0 / 20.0 / 20.0 | 20.0 / 20.0 / 20.0 | 10.0 / 10.0 / 10.0 | 20.0 / 20.0 / 20.0 |
| π0.5 | Easy | door-close-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 80.0 / 80.0 | 90.0 / 90.0 / 90.0 | 100.0 / 90.0 / 90.0 | 50.0 / 90.0 / 90.0 |
| π0.5 | Easy | door-lock-v3 | 40.0 / 100.0 / 80.0 | 40.0 / 70.0 / 70.0 | 20.0 / 70.0 / 40.0 | 30.0 / 80.0 / 40.0 | 30.0 / 80.0 / 50.0 |
| π0.5 | Easy | door-open-v3 | 90.0 / 90.0 / 90.0 | 50.0 / 40.0 / 50.0 | 80.0 / 80.0 / 80.0 | 20.0 / 40.0 / 40.0 | 60.0 / 60.0 / 60.0 |
| π0.5 | Easy | door-unlock-v3 | 60.0 / 80.0 / 70.0 | 80.0 / 80.0 / 80.0 | 70.0 / 80.0 / 80.0 | 80.0 / 90.0 / 90.0 | 70.0 / 80.0 / 80.0 |
| π0.5 | Easy | drawer-close-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 |
| π0.5 | Easy | drawer-open-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 80.0 / 100.0 / 100.0 | 80.0 / 100.0 / 100.0 |
| π0.5 | Easy | faucet-close-v3 | 100.0 / 100.0 / 100.0 | 80.0 / 100.0 / 100.0 | 30.0 / 90.0 / 90.0 | 20.0 / 100.0 / 100.0 | 60.0 / 100.0 / 100.0 |
| π0.5 | Easy | faucet-open-v3 | 100.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 10.0 / 100.0 / 100.0 | 10.0 / 100.0 / 100.0 | 40.0 / 100.0 / 100.0 |
| π0.5 | Easy | handle-press-side-v3 | 100.0 / 100.0 / 100.0 | 80.0 / 90.0 / 90.0 | 90.0 / 90.0 / 90.0 | 70.0 / 70.0 / 70.0 | 80.0 / 80.0 / 80.0 |
| π0.5 | Easy | handle-press-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 90.0 / 90.0 / 90.0 |
| π0.5 | Easy | handle-pull-side-v3 | 20.0 / 0.0 / 10.0 | 0.0 / 0.0 / 20.0 | 0.0 / 0.0 / 40.0 | 0.0 / 0.0 / 10.0 | 0.0 / 0.0 / 10.0 |
| π0.5 | Easy | handle-pull-v3 | 70.0 / 70.0 / 70.0 | 50.0 / 70.0 / 60.0 | 60.0 / 50.0 / 50.0 | 70.0 / 70.0 / 70.0 | 60.0 / 60.0 / 60.0 |
| π0.5 | Easy | lever-pull-v3 | 20.0 / 20.0 / 20.0 | 0.0 / 0.0 / 0.0 | 10.0 / 0.0 / 0.0 | 10.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| π0.5 | Easy | peg-unplug-side-v3 | 60.0 / 60.0 / 60.0 | 0.0 / 40.0 / 50.0 | 10.0 / 50.0 / 50.0 | 0.0 / 40.0 / 40.0 | 10.0 / 40.0 / 40.0 |
| π0.5 | Easy | plate-slide-back-side-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 |
| π0.5 | Easy | plate-slide-back-v3 | 100.0 / 100.0 / 90.0 | 100.0 / 100.0 / 100.0 | 50.0 / 70.0 / 70.0 | 80.0 / 60.0 / 70.0 | 60.0 / 60.0 / 70.0 |
| π0.5 | Easy | plate-slide-side-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 |
| π0.5 | Easy | plate-slide-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 |
| π0.5 | Easy | reach-v3 | 10.0 / 40.0 / 40.0 | 0.0 / 50.0 / 50.0 | 0.0 / 50.0 / 50.0 | 0.0 / 50.0 / 50.0 | 0.0 / 50.0 / 50.0 |
| π0.5 | Easy | reach-wall-v3 | 80.0 / 80.0 / 90.0 | 50.0 / 80.0 / 80.0 | 50.0 / 80.0 / 80.0 | 50.0 / 80.0 / 70.0 | 40.0 / 80.0 / 80.0 |
| π0.5 | Easy | window-close-v3 | 100.0 / 100.0 / 100.0 | 80.0 / 100.0 / 100.0 | 0.0 / 100.0 / 90.0 | 60.0 / 80.0 / 100.0 | 60.0 / 90.0 / 100.0 |
| π0.5 | Easy | window-open-v3 | 100.0 / 80.0 / 80.0 | 60.0 / 70.0 / 70.0 | 20.0 / 70.0 / 80.0 | 30.0 / 70.0 / 70.0 | 20.0 / 70.0 / 70.0 |
| π0.5 | Medium | basketball-v3 | 0.0 / 10.0 / 10.0 | 10.0 / 10.0 / 0.0 | 0.0 / 10.0 / 10.0 | 0.0 / 10.0 / 20.0 | 0.0 / 20.0 / 10.0 |
| π0.5 | Medium | bin-picking-v3 | 30.0 / 50.0 / 50.0 | 0.0 / 20.0 / 60.0 | 0.0 / 0.0 / 20.0 | 0.0 / 0.0 / 0.0 | 0.0 / 10.0 / 10.0 |
| π0.5 | Medium | box-close-v3 | 50.0 / 70.0 / 80.0 | 20.0 / 60.0 / 70.0 | 10.0 / 60.0 / 60.0 | 0.0 / 60.0 / 70.0 | 0.0 / 60.0 / 60.0 |
| π0.5 | Medium | coffee-pull-v3 | 70.0 / 80.0 / 80.0 | 60.0 / 80.0 / 80.0 | 40.0 / 80.0 / 80.0 | 60.0 / 80.0 / 80.0 | 30.0 / 80.0 / 80.0 |
| π0.5 | Medium | coffee-push-v3 | 60.0 / 10.0 / 0.0 | 0.0 / 10.0 / 0.0 | 0.0 / 10.0 / 0.0 | 0.0 / 10.0 / 20.0 | 0.0 / 10.0 / 10.0 |
| π0.5 | Medium | hammer-v3 | 40.0 / 50.0 / 50.0 | 50.0 / 90.0 / 100.0 | 80.0 / 100.0 / 100.0 | 40.0 / 90.0 / 90.0 | 20.0 / 90.0 / 90.0 |
| π0.5 | Medium | peg-insert-side-v3 | 20.0 / 30.0 / 30.0 | 10.0 / 20.0 / 10.0 | 10.0 / 20.0 / 10.0 | 10.0 / 20.0 / 20.0 | 10.0 / 10.0 / 10.0 |
| π0.5 | Medium | push-wall-v3 | 50.0 / 80.0 / 80.0 | 60.0 / 80.0 / 80.0 | 50.0 / 80.0 / 80.0 | 50.0 / 80.0 / 80.0 | 50.0 / 80.0 / 80.0 |
| π0.5 | Medium | soccer-v3 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| π0.5 | Medium | sweep-into-v3 | 0.0 / 50.0 / 50.0 | 0.0 / 40.0 / 40.0 | 0.0 / 40.0 / 40.0 | 0.0 / 40.0 / 40.0 | 0.0 / 40.0 / 40.0 |
| π0.5 | Medium | sweep-v3 | 30.0 / 80.0 / 90.0 | 30.0 / 80.0 / 90.0 | 30.0 / 80.0 / 90.0 | 30.0 / 80.0 / 90.0 | 30.0 / 80.0 / 90.0 |
| π0.5 | Hard | assembly-v3 | 0.0 / 20.0 / 0.0 | 0.0 / 20.0 / 0.0 | 0.0 / 20.0 / 0.0 | 0.0 / 20.0 / 0.0 | 0.0 / 20.0 / 0.0 |
| π0.5 | Hard | hand-insert-v3 | 20.0 / 60.0 / 70.0 | 30.0 / 60.0 / 70.0 | 20.0 / 60.0 / 70.0 | 40.0 / 60.0 / 70.0 | 20.0 / 60.0 / 70.0 |
| π0.5 | Hard | pick-out-of-hole-v3 | 30.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| π0.5 | Hard | pick-place-v3 | 30.0 / 50.0 / 60.0 | 20.0 / 50.0 / 60.0 | 20.0 / 50.0 / 60.0 | 10.0 / 40.0 / 50.0 | 20.0 / 40.0 / 60.0 |
| π0.5 | Hard | push-back-v3 | 40.0 / 60.0 / 50.0 | 0.0 / 40.0 / 50.0 | 0.0 / 60.0 / 50.0 | 10.0 / 30.0 / 30.0 | 0.0 / 40.0 / 40.0 |
| π0.5 | Hard | push-v3 | 60.0 / 60.0 / 70.0 | 0.0 / 70.0 / 70.0 | 30.0 / 70.0 / 70.0 | 0.0 / 70.0 / 70.0 | 10.0 / 70.0 / 70.0 |
| π0.5 | Very Hard | disassemble-v3 | 100.0 / 90.0 / 100.0 | 0.0 / 100.0 / 100.0 | 0.0 / 100.0 / 100.0 | 0.0 / 100.0 / 100.0 | 0.0 / 100.0 / 100.0 |
| π0.5 | Very Hard | pick-place-wall-v3 | 70.0 / 70.0 / 70.0 | 80.0 / 80.0 / 80.0 | 70.0 / 90.0 / 80.0 | 80.0 / 80.0 / 80.0 | 60.0 / 80.0 / 80.0 |
| π0.5 | Very Hard | shelf-place-v3 | 30.0 / 20.0 / 20.0 | 10.0 / 10.0 / 20.0 | 20.0 / 50.0 / 40.0 | 20.0 / 50.0 / 60.0 | 10.0 / 40.0 / 50.0 |
| π0.5 | Very Hard | stick-pull-v3 | 30.0 / 50.0 / 80.0 | 0.0 / 40.0 / 70.0 | 10.0 / 40.0 / 60.0 | 10.0 / 40.0 / 60.0 | 10.0 / 40.0 / 70.0 |
| π0.5 | Very Hard | stick-push-v3 | 50.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 |
| SmolVLA | Easy | button-press-topdown-v3 | 100.0 / 100.0 / 100.0 | 80.0 / 90.0 / 90.0 | 80.0 / 90.0 / 90.0 | 70.0 / 90.0 / 90.0 | 70.0 / 90.0 / 90.0 |
| SmolVLA | Easy | button-press-topdown-wall-v3 | 70.0 / 90.0 / 90.0 | 80.0 / 80.0 / 80.0 | 50.0 / 80.0 / 80.0 | 50.0 / 80.0 / 80.0 | 60.0 / 80.0 / 80.0 |
| SmolVLA | Easy | button-press-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 |
| SmolVLA | Easy | button-press-wall-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 90.0 / 90.0 / 90.0 | 100.0 / 100.0 / 100.0 | 90.0 / 90.0 / 90.0 |
| SmolVLA | Easy | coffee-button-v3 | 90.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 |
| SmolVLA | Easy | dial-turn-v3 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| SmolVLA | Easy | door-close-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 |
| SmolVLA | Easy | door-lock-v3 | 50.0 / 50.0 / 50.0 | 20.0 / 40.0 / 50.0 | 20.0 / 40.0 / 40.0 | 30.0 / 30.0 / 20.0 | 10.0 / 50.0 / 30.0 |
| SmolVLA | Easy | door-open-v3 | 90.0 / 100.0 / 100.0 | 80.0 / 80.0 / 80.0 | 80.0 / 80.0 / 80.0 | 80.0 / 80.0 / 80.0 | 90.0 / 80.0 / 80.0 |
| SmolVLA | Easy | door-unlock-v3 | 80.0 / 80.0 / 80.0 | 50.0 / 50.0 / 50.0 | 30.0 / 30.0 / 30.0 | 30.0 / 20.0 / 30.0 | 30.0 / 20.0 / 30.0 |
| SmolVLA | Easy | drawer-close-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 |
| SmolVLA | Easy | drawer-open-v3 | 44.4† / 40.0 / 40.0 | 50.0 / 50.0 / 50.0 | 50.0 / 50.0 / 50.0 | 50.0 / 50.0 / 50.0 | 50.0 / 50.0 / 50.0 |
| SmolVLA | Easy | faucet-close-v3 | 80.0 / 90.0 / 90.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 10.0 / 100.0 / 100.0 |
| SmolVLA | Easy | faucet-open-v3 | 90.0 / 90.0 / 90.0 | 80.0 / 90.0 / 90.0 | 80.0 / 80.0 / 80.0 | 90.0 / 80.0 / 80.0 | 70.0 / 80.0 / 80.0 |
| SmolVLA | Easy | handle-press-side-v3 | 77.8† / 90.0 / 90.0 | 90.0 / 100.0 / 100.0 | 70.0 / 90.0 / 90.0 | 90.0 / 100.0 / 100.0 | 80.0 / 90.0 / 90.0 |
| SmolVLA | Easy | handle-press-v3 | 100.0† / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 |
| SmolVLA | Easy | handle-pull-side-v3 | 10.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| SmolVLA | Easy | handle-pull-v3 | 10.0 / 10.0 / 0.0 | 0.0 / 20.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| SmolVLA | Easy | lever-pull-v3 | 10.0 / 50.0 / 70.0 | 10.0 / 30.0 / 50.0 | 0.0 / 30.0 / 50.0 | 0.0 / 30.0 / 30.0 | 10.0 / 40.0 / 30.0 |
| SmolVLA | Easy | peg-unplug-side-v3 | 40.0 / 10.0 / 30.0 | 40.0 / 20.0 / 20.0 | 10.0 / 20.0 / 20.0 | 10.0 / 20.0 / 20.0 | 20.0 / 10.0 / 10.0 |
| SmolVLA | Easy | plate-slide-back-side-v3 | 100.0 / 100.0 / 100.0 | 70.0 / 50.0 / 40.0 | 70.0 / 50.0 / 50.0 | 30.0 / 50.0 / 50.0 | 20.0 / 50.0 / 50.0 |
| SmolVLA | Easy | plate-slide-back-v3 | 90.0 / 80.0 / 80.0 | 80.0 / 100.0 / 90.0 | 30.0 / 100.0 / 100.0 | 0.0 / 70.0 / 60.0 | 10.0 / 80.0 / 90.0 |
| SmolVLA | Easy | plate-slide-side-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 |
| SmolVLA | Easy | plate-slide-v3 | 90.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 80.0 / 100.0 / 100.0 | 80.0 / 100.0 / 100.0 |
| SmolVLA | Easy | reach-v3 | 20.0 / 20.0 / 20.0 | 20.0 / 20.0 / 20.0 | 30.0 / 30.0 / 30.0 | 30.0 / 30.0 / 30.0 | 30.0 / 30.0 / 30.0 |
| SmolVLA | Easy | reach-wall-v3 | 30.0 / 30.0 / 30.0 | 40.0 / 30.0 / 30.0 | 30.0 / 30.0 / 30.0 | 60.0 / 30.0 / 30.0 | 50.0 / 30.0 / 30.0 |
| SmolVLA | Easy | window-close-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 50.0 / 50.0 / 50.0 | 60.0 / 60.0 / 60.0 |
| SmolVLA | Easy | window-open-v3 | 60.0 / 70.0 / 70.0 | 40.0 / 60.0 / 60.0 | 40.0 / 50.0 / 50.0 | 10.0 / 50.0 / 50.0 | 10.0 / 50.0 / 50.0 |
| SmolVLA | Medium | basketball-v3 | 10.0 / 10.0 / 10.0 | 0.0 / 0.0 / 10.0 | 0.0 / 10.0 / 10.0 | 0.0 / 10.0 / 10.0 | 0.0 / 0.0 / 10.0 |
| SmolVLA | Medium | bin-picking-v3 | 0.0 / 0.0 / 10.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| SmolVLA | Medium | box-close-v3 | 50.0 / 50.0 / 40.0 | 20.0 / 40.0 / 60.0 | 40.0 / 40.0 / 40.0 | 40.0 / 40.0 / 40.0 | 30.0 / 50.0 / 50.0 |
| SmolVLA | Medium | coffee-pull-v3 | 30.0 / 30.0 / 20.0 | 30.0 / 30.0 / 30.0 | 10.0 / 40.0 / 40.0 | 50.0 / 30.0 / 30.0 | 30.0 / 30.0 / 30.0 |
| SmolVLA | Medium | coffee-push-v3 | 20.0 / 30.0 / 20.0 | 70.0 / 60.0 / 50.0 | 50.0 / 40.0 / 50.0 | 60.0 / 40.0 / 50.0 | 50.0 / 40.0 / 50.0 |
| SmolVLA | Medium | hammer-v3 | 55.6† / 50.0 / 50.0 | 10.0 / 30.0 / 30.0 | 20.0 / 40.0 / 40.0 | 10.0 / 40.0 / 40.0 | 10.0 / 40.0 / 40.0 |
| SmolVLA | Medium | peg-insert-side-v3 | 20.0 / 20.0 / 20.0 | 40.0 / 30.0 / 40.0 | 20.0 / 30.0 / 30.0 | 20.0 / 20.0 / 40.0 | 10.0 / 20.0 / 40.0 |
| SmolVLA | Medium | push-wall-v3 | 20.0 / 30.0 / 40.0 | 30.0 / 40.0 / 40.0 | 20.0 / 20.0 / 20.0 | 20.0 / 20.0 / 20.0 | 20.0 / 20.0 / 20.0 |
| SmolVLA | Medium | soccer-v3 | 10.0 / 10.0 / 20.0 | 30.0 / 20.0 / 20.0 | 20.0 / 10.0 / 20.0 | 10.0 / 10.0 / 20.0 | 10.0 / 10.0 / 20.0 |
| SmolVLA | Medium | sweep-into-v3 | 20.0 / 10.0 / 10.0 | 20.0 / 10.0 / 10.0 | 20.0 / 10.0 / 10.0 | 10.0 / 10.0 / 10.0 | 20.0 / 10.0 / 10.0 |
| SmolVLA | Medium | sweep-v3 | 40.0 / 40.0 / 40.0 | 30.0 / 50.0 / 40.0 | 40.0 / 50.0 / 40.0 | 30.0 / 50.0 / 40.0 | 30.0 / 50.0 / 40.0 |
| SmolVLA | Hard | assembly-v3 | 10.0 / 10.0 / 10.0 | 10.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 10.0 / 10.0 |
| SmolVLA | Hard | hand-insert-v3 | 0.0 / 0.0 / 0.0 | 10.0 / 0.0 / 0.0 | 0.0 / 0.0 / 10.0 | 0.0 / 0.0 / 10.0 | 0.0 / 0.0 / 10.0 |
| SmolVLA | Hard | pick-out-of-hole-v3 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| SmolVLA | Hard | pick-place-v3 | 10.0 / 10.0 / 10.0 | 30.0 / 40.0 / 40.0 | 20.0 / 20.0 / 20.0 | 0.0 / 10.0 / 10.0 | 0.0 / 20.0 / 10.0 |
| SmolVLA | Hard | push-back-v3 | 20.0 / 20.0 / 20.0 | 20.0 / 20.0 / 40.0 | 20.0 / 40.0 / 20.0 | 30.0 / 40.0 / 10.0 | 20.0 / 40.0 / 10.0 |
| SmolVLA | Hard | push-v3 | 20.0 / 10.0 / 10.0 | 20.0 / 30.0 / 30.0 | 20.0 / 20.0 / 20.0 | 0.0 / 10.0 / 10.0 | 10.0 / 20.0 / 20.0 |
| SmolVLA | Very Hard | disassemble-v3 | 30.0 / 30.0 / 60.0 | 30.0 / 40.0 / 60.0 | 60.0 / 30.0 / 50.0 | 40.0 / 30.0 / 50.0 | 0.0 / 30.0 / 50.0 |
| SmolVLA | Very Hard | pick-place-wall-v3 | 20.0 / 20.0 / 10.0 | 20.0 / 20.0 / 20.0 | 20.0 / 20.0 / 20.0 | 20.0 / 20.0 / 20.0 | 20.0 / 20.0 / 20.0 |
| SmolVLA | Very Hard | shelf-place-v3 | 0.0 / 0.0 / 0.0 | 10.0 / 10.0 / 10.0 | 10.0 / 10.0 / 10.0 | 0.0 / 0.0 / 0.0 | 0.0 / 0.0 / 0.0 |
| SmolVLA | Very Hard | stick-pull-v3 | 0.0 / 20.0 / 20.0 | 10.0 / 30.0 / 30.0 | 10.0 / 20.0 / 20.0 | 10.0 / 30.0 / 20.0 | 0.0 / 20.0 / 20.0 |
| SmolVLA | Very Hard | stick-push-v3 | 50.0 / 50.0 / 50.0 | 20.0 / 50.0 / 50.0 | 20.0 / 50.0 / 50.0 | 20.0 / 50.0 / 50.0 | 20.0 / 50.0 / 50.0 |
| X-VLA | Easy | button-press-topdown-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | button-press-topdown-wall-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | button-press-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | button-press-wall-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | coffee-button-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | dial-turn-v3 | 10.0 / 20.0 / 20.0 | 10.0 / 10.0 / 20.0 | 0.0 / 0.0 / 0.0 | N/A | N/A |
| X-VLA | Easy | door-close-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | door-lock-v3 | 60.0 / 80.0 / 80.0 | 40.0 / 60.0 / 60.0 | 60.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | door-open-v3 | 100.0 / 100.0 / 100.0 | 90.0 / 100.0 / 100.0 | 100.0 / 100.0 / 90.0 | N/A | N/A |
| X-VLA | Easy | door-unlock-v3 | 100.0 / 90.0 / 90.0 | 80.0 / 80.0 / 80.0 | 90.0 / 80.0 / 80.0 | N/A | N/A |
| X-VLA | Easy | drawer-close-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | drawer-open-v3 | 100.0 / 100.0 / 100.0 | 90.0 / 90.0 / 90.0 | 80.0 / 80.0 / 80.0 | N/A | N/A |
| X-VLA | Easy | faucet-close-v3 | 100.0 / 100.0 / 90.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 90.0 | N/A | N/A |
| X-VLA | Easy | faucet-open-v3 | 100.0 / 100.0 / 100.0 | 90.0 / 90.0 / 90.0 | 90.0 / 90.0 / 90.0 | N/A | N/A |
| X-VLA | Easy | handle-press-side-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | handle-press-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | handle-pull-side-v3 | 20.0 / 10.0 / 10.0 | 40.0 / 10.0 / 10.0 | 0.0 / 10.0 / 10.0 | N/A | N/A |
| X-VLA | Easy | handle-pull-v3 | 60.0 / 80.0 / 60.0 | 40.0 / 40.0 / 50.0 | 60.0 / 40.0 / 50.0 | N/A | N/A |
| X-VLA | Easy | lever-pull-v3 | 50.0 / 80.0 / 100.0 | 20.0 / 90.0 / 90.0 | 10.0 / 80.0 / 80.0 | N/A | N/A |
| X-VLA | Easy | peg-unplug-side-v3 | 100.0 / 100.0 / 100.0 | 80.0 / 70.0 / 80.0 | 90.0 / 60.0 / 70.0 | N/A | N/A |
| X-VLA | Easy | plate-slide-back-side-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | plate-slide-back-v3 | 90.0 / 90.0 / 80.0 | 90.0 / 100.0 / 80.0 | 70.0 / 80.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | plate-slide-side-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | plate-slide-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | reach-v3 | 40.0 / 50.0 / 50.0 | 30.0 / 50.0 / 50.0 | 30.0 / 50.0 / 60.0 | N/A | N/A |
| X-VLA | Easy | reach-wall-v3 | 100.0 / 100.0 / 100.0 | 60.0 / 80.0 / 80.0 | 80.0 / 90.0 / 90.0 | N/A | N/A |
| X-VLA | Easy | window-close-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Easy | window-open-v3 | 100.0 / 100.0 / 100.0 | 70.0 / 80.0 / 80.0 | 60.0 / 70.0 / 70.0 | N/A | N/A |
| X-VLA | Medium | basketball-v3 | 60.0 / 70.0 / 70.0 | 70.0 / 70.0 / 70.0 | 60.0 / 70.0 / 70.0 | N/A | N/A |
| X-VLA | Medium | bin-picking-v3 | 70.0 / 60.0 / 60.0 | 70.0 / 70.0 / 70.0 | 70.0 / 90.0 / 60.0 | N/A | N/A |
| X-VLA | Medium | box-close-v3 | 100.0 / 90.0 / 100.0 | 100.0 / 80.0 / 90.0 | 90.0 / 100.0 / 80.0 | N/A | N/A |
| X-VLA | Medium | coffee-pull-v3 | 40.0 / 40.0 / 40.0 | 60.0 / 50.0 / 50.0 | 30.0 / 30.0 / 30.0 | N/A | N/A |
| X-VLA | Medium | coffee-push-v3 | 90.0 / 70.0 / 50.0 | 100.0 / 70.0 / 50.0 | 100.0 / 70.0 / 50.0 | N/A | N/A |
| X-VLA | Medium | hammer-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Medium | peg-insert-side-v3 | 80.0 / 70.0 / 60.0 | 70.0 / 90.0 / 90.0 | 90.0 / 60.0 / 70.0 | N/A | N/A |
| X-VLA | Medium | push-wall-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Medium | soccer-v3 | 30.0 / 30.0 / 40.0 | 20.0 / 20.0 / 30.0 | 10.0 / 20.0 / 30.0 | N/A | N/A |
| X-VLA | Medium | sweep-into-v3 | 40.0 / 70.0 / 80.0 | 60.0 / 60.0 / 80.0 | 90.0 / 80.0 / 80.0 | N/A | N/A |
| X-VLA | Medium | sweep-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 90.0 / 90.0 | N/A | N/A |
| X-VLA | Hard | assembly-v3 | 90.0 / 90.0 / 90.0 | 80.0 / 80.0 / 80.0 | 70.0 / 70.0 / 70.0 | N/A | N/A |
| X-VLA | Hard | hand-insert-v3 | 100.0 / 100.0 / 100.0 | 90.0 / 90.0 / 90.0 | 70.0 / 70.0 / 70.0 | N/A | N/A |
| X-VLA | Hard | pick-out-of-hole-v3 | 0.0 / 20.0 / 20.0 | 60.0 / 30.0 / 40.0 | 80.0 / 50.0 / 10.0 | N/A | N/A |
| X-VLA | Hard | pick-place-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Hard | push-back-v3 | 30.0 / 40.0 / 40.0 | 40.0 / 40.0 / 40.0 | 50.0 / 50.0 / 50.0 | N/A | N/A |
| X-VLA | Hard | push-v3 | 90.0 / 90.0 / 90.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |
| X-VLA | Very Hard | disassemble-v3 | 80.0 / 90.0 / 90.0 | 90.0 / 70.0 / 80.0 | 80.0 / 90.0 / 60.0 | N/A | N/A |
| X-VLA | Very Hard | pick-place-wall-v3 | 70.0 / 70.0 / 70.0 | 60.0 / 60.0 / 60.0 | 50.0 / 60.0 / 60.0 | N/A | N/A |
| X-VLA | Very Hard | shelf-place-v3 | 90.0 / 90.0 / 90.0 | 50.0 / 50.0 / 50.0 | 50.0 / 60.0 / 60.0 | N/A | N/A |
| X-VLA | Very Hard | stick-pull-v3 | 40.0 / 30.0 / 40.0 | 30.0 / 50.0 / 50.0 | 40.0 / 50.0 / 50.0 | N/A | N/A |
| X-VLA | Very Hard | stick-push-v3 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | 100.0 / 100.0 / 100.0 | N/A | N/A |

每任务的成功数、有效数、未知数、Policy Calls总量与均值、干预次数已同时保存到 [650个model×H×task格 CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/appendix_data/METAWORLD_TASK_METRICS.csv)；原始轻量索引为 [19,496条有效 N/R/Post episode CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/appendix_data/METAWORLD_VALID_EPISODES.csv)，包含每条记录的来源路径。三底座合计150个task行与主表13格N/R/Post逐项回加一致；该19,496是多方法、多H的评估记录数，不是独立初态数。

### C2. External methods: per-task success and policy calls

同一π0.5 H10设置，每任务10条有效成功率记录。† VLA-Corrector相应任务有一条费用未知，该均值仅来自其余9条；成功率仍含已验收的日志恢复终局。GAF/Post费用各任务完整。

| Difficulty | Task | VLA-Corrector SR (%) | GAF SR (%) | Post SR (%) | VLA-Corrector Policy Calls | GAF Policy Calls | Post Policy Calls |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Easy | button-press-topdown-v3 | 90.0 | 90.0 | 90.0 | 9.000† | 7.800 | 7.700 |
| Easy | button-press-topdown-wall-v3 | 100.0 | 100.0 | 100.0 | 5.111† | 4.600 | 5.200 |
| Easy | button-press-v3 | 100.0 | 100.0 | 100.0 | 4.222† | 4.000 | 4.200 |
| Easy | button-press-wall-v3 | 100.0 | 100.0 | 100.0 | 4.667† | 4.700 | 5.500 |
| Easy | coffee-button-v3 | 100.0 | 100.0 | 100.0 | 3.000† | 3.000 | 3.700 |
| Easy | dial-turn-v3 | 50.0 | 40.0 | 30.0 | 26.667† | 20.000 | 22.800 |
| Easy | door-close-v3 | 100.0 | 100.0 | 100.0 | 4.800 | 4.800 | 5.800 |
| Easy | door-lock-v3 | 50.0 | 50.0 | 80.0 | 33.400 | 19.800 | 18.000 |
| Easy | door-open-v3 | 80.0 | 90.0 | 90.0 | 13.300 | 9.800 | 10.800 |
| Easy | door-unlock-v3 | 90.0 | 70.0 | 70.0 | 15.000 | 11.800 | 13.900 |
| Easy | drawer-close-v3 | 100.0 | 100.0 | 100.0 | 6.200 | 6.000 | 6.000 |
| Easy | drawer-open-v3 | 100.0 | 100.0 | 100.0 | 10.900 | 7.900 | 8.000 |
| Easy | faucet-close-v3 | 100.0 | 100.0 | 100.0 | 10.000 | 6.000 | 6.500 |
| Easy | faucet-open-v3 | 100.0 | 100.0 | 100.0 | 4.900 | 4.900 | 5.700 |
| Easy | handle-press-side-v3 | 100.0 | 100.0 | 100.0 | 3.000 | 3.000 | 3.000 |
| Easy | handle-press-v3 | 100.0 | 100.0 | 100.0 | 2.800 | 2.700 | 2.700 |
| Easy | handle-pull-side-v3 | 30.0 | 20.0 | 10.0 | 34.600 | 24.900 | 29.200 |
| Easy | handle-pull-v3 | 60.0 | 80.0 | 70.0 | 26.600 | 17.300 | 16.600 |
| Easy | lever-pull-v3 | 10.0 | 10.0 | 20.0 | 33.600 | 27.600 | 25.800 |
| Easy | peg-unplug-side-v3 | 50.0 | 50.0 | 60.0 | 28.700 | 23.000 | 16.900 |
| Easy | plate-slide-back-side-v3 | 100.0 | 100.0 | 100.0 | 4.500 | 4.000 | 4.100 |
| Easy | plate-slide-back-v3 | 100.0 | 100.0 | 90.0 | 8.700 | 4.900 | 9.800 |
| Easy | plate-slide-side-v3 | 100.0 | 100.0 | 100.0 | 4.000 | 4.000 | 4.000 |
| Easy | plate-slide-v3 | 100.0 | 100.0 | 100.0 | 5.000 | 4.000 | 5.000 |
| Easy | reach-v3 | 10.0 | 20.0 | 40.0 | 31.700 | 24.800 | 20.200 |
| Easy | reach-wall-v3 | 80.0 | 80.0 | 90.0 | 11.500 | 9.400 | 7.200 |
| Easy | window-close-v3 | 100.0 | 100.0 | 100.0 | 6.400 | 6.100 | 6.700 |
| Easy | window-open-v3 | 100.0 | 100.0 | 80.0 | 9.600 | 7.200 | 12.100 |
| Medium | basketball-v3 | 0.0 | 0.0 | 10.0 | 43.800 | 30.000 | 31.100 |
| Medium | bin-picking-v3 | 40.0 | 30.0 | 50.0 | 35.444† | 24.000 | 21.600 |
| Medium | box-close-v3 | 70.0 | 50.0 | 80.0 | 29.600 | 21.300 | 12.900 |
| Medium | coffee-pull-v3 | 80.0 | 80.0 | 80.0 | 17.222† | 10.400 | 11.300 |
| Medium | coffee-push-v3 | 60.0 | 60.0 | 0.0 | 19.300 | 14.400 | 31.400 |
| Medium | hammer-v3 | 50.0 | 50.0 | 50.0 | 21.100 | 17.500 | 18.800 |
| Medium | peg-insert-side-v3 | 30.0 | 30.0 | 30.0 | 31.200 | 25.200 | 23.700 |
| Medium | push-wall-v3 | 50.0 | 50.0 | 80.0 | 22.400 | 18.300 | 12.600 |
| Medium | soccer-v3 | 0.0 | 0.0 | 0.0 | 34.200 | 30.000 | 31.600 |
| Medium | sweep-into-v3 | 0.0 | 0.0 | 50.0 | 36.700 | 30.000 | 19.200 |
| Medium | sweep-v3 | 30.0 | 30.0 | 90.0 | 26.600 | 22.800 | 9.300 |
| Hard | assembly-v3 | 0.0 | 0.0 | 0.0 | 48.100 | 30.000 | 35.200 |
| Hard | hand-insert-v3 | 20.0 | 20.0 | 70.0 | 28.800 | 24.900 | 12.900 |
| Hard | pick-out-of-hole-v3 | 40.0 | 40.0 | 0.0 | 34.800 | 23.200 | 31.000 |
| Hard | pick-place-v3 | 30.0 | 30.0 | 60.0 | 30.100 | 22.300 | 15.200 |
| Hard | push-back-v3 | 40.0 | 40.0 | 50.0 | 28.000 | 20.400 | 18.500 |
| Hard | push-v3 | 60.0 | 60.0 | 70.0 | 16.600 | 14.600 | 13.900 |
| Very Hard | disassemble-v3 | 90.0 | 90.0 | 100.0 | 14.000 | 9.800 | 10.800 |
| Very Hard | pick-place-wall-v3 | 60.0 | 70.0 | 70.0 | 25.400 | 13.600 | 14.400 |
| Very Hard | shelf-place-v3 | 30.0 | 30.0 | 20.0 | 41.600 | 24.300 | 30.500 |
| Very Hard | stick-pull-v3 | 50.0 | 30.0 | 80.0 | 27.300 | 23.200 | 13.400 |
| Very Hard | stick-push-v3 | 60.0 | 60.0 | 100.0 | 18.500 | 15.000 | 6.000 |

导出：[外部逐任务 CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/appendix_data/POST_EXTERNAL_FINE_TASKS.csv)、[外部难度 CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/appendix_data/POST_EXTERNAL_FINE_GROUPS.csv)。所有上述附录只汇总既有数据，不改变正式源、权重、原终局或原总表。

