# Post 分支正式实验数据汇总

更新日期：2026-09-24。最终配置为 **Post-multi，L11＝BCE＋gain＋0.5pair，固定 fit9101，Q 四成员 1041–1044**。正式 Post 结果共 **14 格、7,000 条有效终局**：π0.5 五个 H 的 multi 与 H10 once，SmolVLA 五个 H 的 multi，X-VLA 三个 H 的 multi。最新补充为 SmolVLA H20/30/40/50 与 X-VLA H20/30，已全部纳入。

本文件集中管理当前 Post 配置及仍可复用的基线、完整 Q 消融、触发器对照；同类数据合表。历史版本和失败尝试继续保存在 [实验总表](EXPERIMENT_RESULTS_MASTER.md)，论文布局参考 [论文数据文档](EXPERIMENT_FOR_PAPER.md)，算法对应 [Post 算法说明](ALGORITHM_POST_ZH.md)。本文没有新增评测。

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

π0.5 各 H 的 50 任务 N/R/Post 成功数保存在 [逐任务 CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_L11_POST_PER_TASK.csv)；新跨底座 H 的有效 episode 及来源索引保存在 [跨底座逐 episode CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_CROSSBASE_H_SWEEP_VALID_EPISODES.csv)。这些细粒度数据通过链接集中管理，避免在本文复制超宽逐任务表。

| Item | Current Evidence | Treatment in This Document |
| --- | --- | --- |
| L11 Post Random-once | 当前没有同版本正式结果；已有 Post 随机对照绑定旧 Q | 不填成 L11；保留 R 随机对照作为明确标注的辅助证据 |
| L11 Post once at H20/30/40/50 | 当前没有同版本正式结果 | H 扫描只报告已完成 multi，不移用旧 once |
| Real-world results | 已有用户提供的三任务计数，每任务 60 次；Post 分支、Q 版本和触发配置尚未绑定 | 数值仍在总表，正式 Post 结果待身份确认后再加入 |
| LIBERO full method | 完整 D/G0/L11 系统缺结果；已有 operator-only 不等价 | 暂不列正式 Post 成功率 |
| QGF / QPILOTS | 文献资料可用，未找到本地同协议实际终局 | 不将论文数值冒充复现实验 |
| Historical L01 / old Q / demo videos | 历史数据及选择性展示保留 | 不混入当前正式主表；演示视频不计总体成功率 |

本次核对以终局结果、有效源索引和小型汇总为准；较晚回执中的演示录像与缺口审计未产生新的正式成绩。最新来源与纳入决定见 [Post 来源审计](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/POST_DATA_CONSOLIDATION_20260924/POST_LATEST_SOURCE_AUDIT.json)。原始数据、现有总表与其他分支文档均保留。
