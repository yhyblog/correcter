# 新 Post L01 / fit9101：组件主张与证据边界

范围：只审当前 Post 论文口径；不纳入 LIBERO、Velocity。读取既有小统计/终局摘要，未启动实验、未读科学实现、未修改执行侧记录。结论可带限定条件引用，不能将组合系统的收益分摊为每个组件的独立贡献。结构化数值见 [components.json](components.json)。

**最稳的论文优势是：在冻结的 π0.5–MT50 协议下，包含选择性重规划与 Post 修正的完整系统，相对同 H 的原始策略显著提高成功率。** 单独的收益触发器、差分损失、Q 修正各有更窄边界：G0 优于指定随机 R 策略，但没有胜过 D5 异常触发；L01 是开发集合法选出的配置，但测试消融不支持它独占最优；Post 相对匹配 R 的额外增益均小且不确定。

## 1. 全 Q 损失消融：选择合法，独立优越性不成立

当前 Q 每个成员全部 7058 参数从零训练，4,000 更新，三组 fit seed 9101/9102/9103；历史网络权重没有加载。当前选择由 Post-only 覆盖规则确定：五任务、三 fit 等权开发均值，部署 fit9101 预先固定，test 不能改 loss/fit/阈值。早期 METHOD_FROZEN 中仍有双分支选择文字，当前选择权威是 [PAPER_SCOPE_POLICY](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/PAPER_SCOPE_POLICY.json)；训练设置见 [METHOD_FROZEN](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/METHOD_FROZEN.json)。

| 损失 | Post 开发集 | 测试 fit9101/9102/9103 成功数 | 测试三 fit 描述均值 |
|---|---:|---:|---:|
| L00 (BCE) | 202/300 = 67.33% | 38/35/35（各50） | 108/150 = 72.00% |
| L10 (BCE+gain) | 203/300 = 67.67% | 35/35/34（各50） | 104/150 = 69.33% |
| L01 (BCE+0.5pair) | 207/300 = 69.00% | 35/35/33（各50） | 103/150 = 68.67% |
| L11 (BCE+gain+0.5pair) | 203/300 = 67.67% | 37/36/35（各50） | 108/150 = 72.00% |

来源：[DEVELOPMENT_SELECTION](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/DEVELOPMENT_SELECTION.csv)、[ABLATION_CELLS](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/ABLATION_CELLS.csv)。开发 300 次评估复用 100 个 source，测试 150 次评估复用 50 个 source；三 fit 不是额外独立环境初态。

可宣称：L01（BCE+0.5pair）开发均值 69.0%，在四个候选中最高，并被依协议冻结。不可宣称：pair/full loss 必然改善测试、L01 最优、gain/pair 都不可缺。测试描述均值 L01 68.67%，L00/L11 各72.0%，L01 相对纯 BCE 为 −3.33pp；部署 fit9101 也为 L01 35/50，L00 38/50，L11 37/50。现成配对只给 L11−其余损失，所有 CI 包含或触及0，McNemar p≥0.5，不能拿它们充作 L01−L00 的配对 CI。[既有配对统计](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/PAIRED.csv)

差分/排序监督仍可作为方法设计描述，但这些标签由既有 outcome 构造，不能声称新增独立监督数据；减去与动作无关的 baseline 本身不改变动作梯度，也没有证明学到了真实成功率梯度。尤其当前部署 L01 不含 gain，不能把 L11 的“全损失”写成最终方法的必要组成。

## 2. 收益触发与异常触发 E6：不能写前者更好

当前 E6 H10/C10、相同下游 R、允许多次干预，共同有效50：G0 为26/50=52%，D5 为31/50=62%。G0−D5 **−10pp，95% CI [−22,0]，McNemar p=0.1796875**；G0独赢2、D5独赢7。点估计偏向 D5，证据不足以支持 G0 优势，也不足以声称等价。[E6 multi 配对](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_PRIMARY_VALIDATION_V1/PAIRED.json)

G0 平均干预4.8次，D5 7.6次，但 sampling calls 分别1,072与1,001；不能由“干预更少”推出全系统更省。监测/采样/flow/墙钟应各自报告。[G0 multi RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/A/A_D24_MULTI_PRIMARY_VALIDATION_V1_E6_G0_MULTI_H10_RESULT.json)、[D5 multi RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/A/A_D24_MULTI_PRIMARY_VALIDATION_V1_E6_D5_MULTI_H10_RESULT.json)

早期 once 是另一套机制证据：G0 26/50、D5 30/50，p=0.21875；D5 阈值在 dev100 上按报警量匹配，不用成功标签；test 上没有强制相同报警数。这50源为五任务 ordinals10–19，不能冒充完整MT50，不能外推到 Post 或其他 H。[E6 once summary](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_CORE_REMAINDER_V1/E6_FINAL_SUMMARY.json)、[范围说明](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/E6_COMPLETED_ANALYSIS_20260922.md)

## 3. G0-once 与 Random-once：R 证据可复用，Post 不可偷换

下表全部 Q-independent R，同一冻结策略、源、候选 RNG、C10 与后续规则；每 H 共同有效500。原统计方向是 Random−G0，这里反向展示 G0−Random（区间同时反向）。

| H | G0-once 成功 | Random-once 成功 | G0−Random (pp) | 点态95% CI (pp) |
|---:|---:|---:|---:|---:|
| 10 | 336/500 | 307/500 | +5.8 | [2.6, 9.0] |
| 20 | 312/500 | 242/500 | +14.0 | [11.0, 17.2] |
| 30 | 307/500 | 210/500 | +19.4 | [16.4, 22.6] |
| 40 | 290/500 | 211/500 | +15.8 | [12.4, 19.4] |
| 50 | 297/500 | 196/500 | +20.2 | [16.6, 23.6] |

来源：[FINAL_PAIRED](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_R_TRIGGER_MODES_V1/FINAL_PAIRED.json)，固定任务内 source bootstrap 2,000 次、seed20260921；未做多重比较校正，不包含训练种子不确定性。可写“在指定 R 协议下，G0-once 在五个 H 的成功率均高于预先冻结的随机单次策略”。

Random 在运行前均匀抽合法绝对槽位，早终止不强制补干预，实际触发分别250/309/341/337/345（各500），所以这并不是相同实际干预次数/预算下纯 timing 效应。Random 保留 D/G0 shadow 计算，运行开销也不能当成理想零监测随机策略。[冻结方法](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_R_TRIGGER_MODES_V1/METHOD_FROZEN.json)、[触发与调用统计](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_R_TRIGGER_MODES_V1/FINAL_CELLS.csv)

R 不依赖 Q，既有 R 比较可以继续使用。**当前未有“新 L01 Q 的 Post Random-once”对照**；旧 Q 的 Post Random-once 不能改标为新 Q，也不能据 R 推出 Post 的同等结论。更不能把“胜随机”改写为“胜异常 D5”“最优中断时机”或“已校准收益”。

## 4. Post 约束动作修正：系统收益强，Q 的独立增益弱

当前五 H 完整系统对 N 的配对增益为 +8.4/+18.8/+25.8/+23.8/+25.4pp；同一家族五比较经 Holm 校正仍成立。更能隔离动作修正的 Post−R 为：

| H | 新 Post multi | 匹配 R multi | Post−R (pp) | 点态95% CI (pp) | 五比较 Holm p |
|---:|---:|---:|---:|---:|---:|
| 10 | 350/500 | 343/500 | +1.4 | [-0.6, 3.6] | 1.000 |
| 20 | 334/500 | 324/500 | +2.0 | [-0.2, 4.2] | 0.662 |
| 30 | 334/500 | 330/500 | +0.8 | [-1.6, 3.2] | 1.000 |
| 40 | 324/500 | 318/500 | +1.2 | [-1.2, 3.6] | 1.000 |
| 50 | 323/500 | 321/500 | +0.4 | [-1.8, 2.8] | 1.000 |

来源：[本轮现成 main_pairs](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/analysis_20260923_claims/main_pairs.json)，固定任务内配对重采样5,000次、seed20260923；exact McNemar，Post−R 五比较为独立校正家族。它记录完整原始来源。所有 Post−R 区间跨0，不能宣称 Q 修正有明确独立优势，不能把 Post−N 大差异全归给动作梯度。R−N 本身同时改变重规划、C10 commitment 与队列时序，不能进一步拆成纯触发或纯时序因果效应。

同一新 Q 的 H10 multi 350/500 对 once341/500，为 +1.8pp，点态CI [0.4,3.4]，p=0.0490（未校正）；它是有限的同版本重复干预证据。旧 Q once 对新 Q multi 同时改变模型与次数，不能替代这个对照。[同新 Q multi/once 配对](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/PAIRED.csv)

可宣称受约束 Post 与选择性重规划组合在固定主协议下有效；不能宣称每个 trust region、PCA、anchor、动作尺度或步长选择都已单独验证必要性。现有数据也不支持“安全保证”或对底座/未知任务普遍成立。

## 5. Smol / X native：只支持经过适配的可运行性

| 底座 | 当前新 Post | 对照 | 共同源配对差异 |
|---|---:|---:|---|
| Smol | 245/500=49.0% | R 245/500=49.0% | 总成功率相同；本次小摘要没有现成 P−R 配对区间，不能称等价 |
| Smol（N可用源） | 244/496=49.19% | N 234/496=47.18% | +2.02pp，CI [−0.40,4.44]；共同有效496 |
| X | 409/500=81.8% | N 403/500=80.6% | +1.2pp，CI [−1.6,4.0] |
| X | 409/500=81.8% | R 412/500=82.4% | −0.6pp，CI [−2.0,0.8] |

Smol 来源：[Post summary](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/evaluation_r1/FINAL_SUMMARY.json)、[R完成合并 summary](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_PI05_SELECTED_H20_H30_V1/R_cancelled_r3/FINAL_SUMMARY.json)、[N共同496配对](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/evaluation_r1/PAIRED.json)。N 缺失4不能填成失败，也不能把 Post全500的245与N496的234直接构成500配对。Smol CI 为固定任务内共同源bootstrap2,000次、seed20260922，一组独立fit，标注descriptive。X 来源：[summary](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/FINAL_SUMMARY.json)、[配对](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/POST_PAPER_PAIRED.json)；X CI 为任务cluster bootstrap2,000次、seed20260922，与 Smol 的区间法不同。

两者只在各自冻结 native 协议内比较。Smol rawH50/nativeK10，X rawH30/nativeK10，均 Mesa80Hz/.01、NFE10/C10；π0.5主线 NVIDIA EGL30Hz/.015，不能跨协议横排原始成功率再宣称底座迁移提升。[Smol冻结协议](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SMOL_MULTI_EVAL_V1/METHOD_FROZEN.json)、[X冻结协议](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/METHOD_FROZEN.json)

这些路径使用各底座自己的辅助头/训练数据适配，并保留外部 π0.5 encoder 特征；新 Q 从各自既有数据全参数重训、共享A开发选择，不是无需训练即插即用，也不是纯 native encoder 独立方案。当前 Post−N 小幅正、Post−R 平或负，区间包含0，无法支持“稳定跨底座性能增益”。

## 6. 外部 VLA-C / GAF：可写限定系统比较，不能写同预算算法胜出

H10同一 π0.5 SFT030000、同500测试源：当前新 Post 350/500=70.0%；VLA-C 319/500=63.8%；adapted GAF-v1 315/500=63.0%。Post−VLA-C **+6.2pp，CI [3.0,9.4]，p=0.0015165**（rescued61/harmed30）；Post−GAF **+7.0pp，CI [4.0,10.0]，p=0.00022369**（rescued61/harmed26）。来源：[当前 E3_CELLS](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/E3_COMPARISON.csv)、[当前 E3_PAIRED](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/E3_PAIRED.csv)；固定任务内source bootstrap2,000次、seed20260921，点态区间，不含训练种子不确定性。不要套用旧Post结果上的p值或旧Holm数值。

可以写“在这套冻结任务和实现下，当前 Post 系统成功率高于所比较的 VLA-C 与 adapted GAF 基线”。限定必须保留：

- 使用现有各自训练资产，未完成相同训练数据/同干预预算匹配。VLA-C 保留自身在线检测与重复干预；GAF 是每个flow步骤引导，不走G0/once门控。结果不识别纯算法差异，也不证明通用SOTA。[外部比较范围说明](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/E3_H10_EXTERNAL_FINAL_20260922.md)
- VLA-C 500终局含8条 accepted log-derived outcome；8条精确calls/time缺失。终局有效不抹去历史故障，也不能据此宣称完整精确成本优势。[VLA-C lineage](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/E3_VLA_CORRECTOR_COMPARISON_20260922.md)
- GAF 为适配版，训练15个parent、内部固定holdout2个parent；不是官方完整MT50同数据复现。3个critic各10,000更新，用holdout MSE分别选9,000/2,000/10,000步，组成一个ensemble，不是3次独立系统实验。重叠窗口不等于独立样本。[GAF summary](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/FINAL_SUMMARY.json)、[GAF numerical lineage](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/NUMERICAL_LINEAGE.md)

## 三项创新的写作优先级

| 论文创新 | 当前支持强度 | 建议措辞 | 应删去的强化主张 |
|---|---|---|---|
| 预期收益驱动的选择性干预 | 相对指定随机R较强；相对异常触发不支持 | 提出收益触发策略；冻结R对照中优于预设随机触发 | 优于异常检测、最优/已校准触发、天然稀疏或总成本更低 |
| 锚定差分/排序监督 | 独立测试增益弱 | 全Q可训练，L01按开发数据选择；如实呈现混合消融结果 | 差分/排序/full loss不可缺、test独占优势、真实成功梯度 |
| 受约束的Post动作修正与重规划组合 | 整体对N强；独立Q增益未定 | 整套方法在固定π0.5主线上有效，外部实现比较正向 | 主要收益由Q修正带来、匹配R显著提升、每项约束已验证、跨底座普遍提升 |

发布边界：本组件检查通过，适合带以上限定条件分享。未处理的统计边界是训练种子/未知任务外推、组件独立效应与外部预算公平性；这些是结论范围，不应被“全部计算已完成”替代。
