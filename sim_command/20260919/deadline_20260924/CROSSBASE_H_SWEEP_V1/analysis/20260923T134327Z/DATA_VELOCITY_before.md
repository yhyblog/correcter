# Velocity 实验数据表

更新：2026-09-23 12:57 UTC。保留本文件原有四组表格，已完成数据填入，本次H扫描的N基线已逐格填入，尚未完成的Velocity列保留空白。

仿真中的 Ours 均为 **Velocity＋G0-multi＋L11（BCE＋gain＋0.5pair）**，fit seed 9101、四成员1041–1044；SmolVLA / X-VLA使用各自训练的辅助网络。H表示正常执行队列长度，预测chunk保持π0.5/SmolVLA为50、X-VLA为30，干预承诺长度均为C10。不混入单次触发或历史L01结果。真实任务只按用户提供并确认的计数统计，未据仿真配置推断真机Q版本。

## 1. MT50

每个已完成仿真格原计划50任务×10个固定初态，共500次；具体有效样本差异在下文说明。表头中SR指成功率（success rate），Policy Calls指每个有效episode的平均完整策略采样次数，包含任务成功和任务失败的所有有效终局；Ours指L11 Velocity。ΔSR单位为百分点（pp），ΔCalls为平均调用次数的相对变化。↑/↓分别表示更高/更低为优，H为正常执行队列长度。

| Backbone | H | N SR (%) ↑ | N Policy Calls ↓ | Ours SR (%) ↑ | Ours Policy Calls ↓ | ΔSR (pp) ↑ | ΔCalls (%) ↓ | Mean Interventions | ΔCalls vs. N (H=10) (%) ↓ | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| π0.5 | 10 | 61.60 | 15.130 | 68.80 | 16.432 | +7.20 | +8.61% | 2.008 | +8.61% | Complete |
| π0.5 | 20 | 48.00 | 9.372 | 65.60 | 12.722 | +17.60 | +35.74% | 2.496 | -15.92% | Complete |
| π0.5 | 30 | 41.00 | 6.964 | 66.00 | 11.234 | +25.00 | +61.32% | 2.568 | -25.75% | Complete |
| π0.5 | 40 | 41.00 | 5.602 | 63.60 | 10.796 | +22.60 | +92.72% | 2.664 | -28.65% | Complete |
| π0.5 | 50 | 39.20 | 4.312 | 64.00 | 10.042 | +24.80 | +132.88% | 2.602 | -33.63% | Complete |
| SmolVLA | 10 | 47.18 | 19.532 | 49.40 | 23.394 | +2.22† | +19.77%† | 2.764 | +19.77% | Complete† |
| SmolVLA | 20 | 45.20 | 9.996 |  |  |  |  |  |  | Ours pending |
| SmolVLA | 30 | 41.00 | 7.036 |  |  |  |  |  |  | Ours pending |
| SmolVLA | 40 | 38.20 | 5.780 |  |  |  |  |  |  | Ours pending |
| SmolVLA | 50 | 33.80 | 4.576 |  |  |  |  |  |  | Ours pending |
| X-VLA | 10 | 80.60 | 12.264 | 81.40 | 16.630 | +0.80 | +35.60% | 3.002 | +35.60% | Complete |
| X-VLA | 20 | 77.60 | 6.612 |  |  |  |  |  |  | Ours pending |
| X-VLA | 30 | 77.00 | 4.572 |  |  |  |  |  |  | Ours pending |

“ΔCalls (%)”＝(Velocity平均采样/N同H平均采样−1)×100%；正号表示调用增加，负号表示调用减少。“ΔCalls vs. N (H=10) (%)”使用固定N(H10)作参照，属于**跨H工作点比较**，不能与同H变化混用。原模板的“采样率”在此明确为平均完整采样次数的相对变化，不是每秒采样频率。

† SmolVLA的N为496个有效源＋4个unknown，Velocity为500个有效源，主行差值使用各自分母，仅是描述性差值。共同496源上，N为234/496=47.18%，Velocity为246/496=49.60%，差值为+2.42pp（救回28、损害16）；对应完整采样为19.532与23.323次/episode。4个unknown不填成失败，也不为了此表补跑。

现有数据支持的补充信息：π0.5五个H下，Velocity相对同H N的成功率点差为+7.2～+25.0pp，但平均完整采样均增加。若比较不同运行点，Velocity H50为64.0%、10.042次采样，N H10为61.6%、15.130次采样，即成功率+2.4pp、完整采样−33.63%；这不等于相同H下更省，也不是端到端加速结论。

成本口径：π0.5 N沿原policy_calls、Smol/X N沿原queries计完整策略采样；Velocity用保存的sampling_calls。一次完整采样含10个flow/NFE步骤，不能把这10步算成10次完整策略调用。辅助网络、额外编码器和动作梯度的计算不包含在完整策略调用数中。

比较边界：π0.5采用NVIDIA EGL/30Hz/.015动作缩放，Smol/X采用原Mesa/80Hz/.01协议；本表支持各底座内部比较，不支持直接按不同底座原始成功率排名。当前π0.5 H10复用的50个已揭晓消融源与主500源重叠，不能称全新盲测。新增H按方法逐格更新：已取得500条完整终局的N填入，Velocity未完成列留空；不以运行中不完整分片的成功率冒充完整500条结果。

来源：[L11最终汇总](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json)；[N/R既有成本](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/costs.json)；[Smol N源索引](../sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/D24_N_CONTROL_REPAIR_r2/N_INCREMENTAL_SUMMARY.json)；[X N汇总](../sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/D24_XVLA_N_r1/N_COMPLETE_SUMMARY.json)；[新增H扫描任务](../sim_command/20260919/deadline_20260924/CROSSBASE_H_SWEEP_V1/ASSIGNMENT.md)；[A新增H逐源结果](../sim_command/20260919/results/A/A_D24_CROSSBASE_H_SWEEP_V1/FINAL_EPISODES.csv)（只提取N完整500源格，整队仍未结束）。

新增H的N基线补录：A已发布Smol H20/H30完整逐源表；B的Smol H40/H50、C的X H20/H30各读取已结束阶段的500份有效终局，仅CPU汇总成功数与counters.policy_queries，均500唯一源、采样字段覆盖500/500。每个完整N格可单独填表，不表示整个包含Post/R/Velocity的队列已完成。B来源：[SOURCE_INDEX](../sim_command/20260919/results/B/B_D24_CROSSBASE_H_SWEEP_V1/SOURCE_INDEX.json)；C来源：[N阶段退出结果](../sim_command/20260919/results/C/C_D24_CROSSBASE_H_SWEEP_V1/chains/evaluate/stages/00_X-VLA_N_H20_30/RESULT.json)及其对应evaluation目录。精确目录和汇总数值保存在本文数值JSON中。

## 2. 消融

固定π0.5、同一MT50原500源。N不干预，R为同收益触发器下的无引导重规划，Ours为L11 Velocity；R和Ours都不限制总干预次数，C10及其余合法触发条件保持冻结协议。此表是方法组件对照，不是Q训练损失消融。

| H | N SR (%) ↑ | R SR (%) ↑ | Ours SR (%) ↑ | R − N (pp) | Ours − R (pp) | Ours − N (pp) | R Policy Calls ↓ | Ours Policy Calls ↓ | ΔCalls vs. R (%) ↓ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 61.6 | 68.6 | 68.8 | +7.0 | +0.2 | +7.2 | 14.452 | 16.432 | +13.70% |
| 20 | 48.0 | 64.8 | 65.6 | +16.8 | +0.8 | +17.6 | 10.158 | 12.722 | +25.24% |
| 30 | 41.0 | 66.0 | 66.0 | +25.0 | 0.0 | +25.0 | 8.650 | 11.234 | +29.87% |
| 40 | 41.0 | 63.6 | 63.6 | +22.6 | 0.0 | +22.6 | 8.276 | 10.796 | +30.45% |
| 50 | 39.2 | 64.2 | 64.0 | +25.0 | -0.2 | +24.8 | 7.584 | 10.042 | +32.41% |

R与Ours各500/500有效终局的采样计量完整。现有五H中Ours−R为+0.2、+0.8、0、0、−0.2pp，不能将Ours−N的全部增益归因于Q引导，也不能由这些点差宣称Q有显著独立增益。

来源：[L11最终逐格CSV](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_CELLS.csv)；[R-multi原始汇总](../sim_command/20260919/deadline_20260924/analysis_20260922_current/trigger/TRIGGER_CELLS_AND_COSTS.csv)；[N原始汇总](../sim_command/20260919/deadline_20260924/MAIN_FINAL_CELLS_WITH_COSTS.csv)。

## 3. 不同方法之间的对比

固定π0.5 SFT030000、MT50原500源、正常执行H10。保留各外部方法已经实际运行的机制；本表不是所有方法同训练数据、同干预预算的比较。

| Method | SR (%) ↑ | Ours − Method (pp) | Policy Calls ↓ |
| --- | ---: | ---: | ---: |
| N | 61.6 | +7.2 | 15.130 |
| Velocity (L11, multi) | 68.8 | 0.0 | 16.432 |
| VLA-Corrector | 63.8 | +5.0 | 19.961 |
| GAF-v1 adapted | 63.0 | +5.8 | 14.864 |

Velocity相对本地VLA-Corrector为+5.0pp、相对GAF-v1 adapted为+5.8pp。按共同500源重新计数，前者救回58/损害33，后者救回56/损害27；这里只补充配对计数，不套用旧Post或旧Q版本的置信区间、p值或显著性结论。

VLA-Corrector成功率覆盖500条（含8条已接受的log-derived终局），平均采样19.961只来自492条已知成本记录（9821/492），不是9821/500；另外8条仍为未知。GAF为15个train父源＋2个内部holdout、三成员各10,000更新后选定的适配版，不写成官方同数据完整复现。不同执行批次/并发下的elapsed不支持统一时延排名，本表不将其作为推理加速优势。

参数规模补充：π0.5路径新增D＋G0＋Q小网络共11,912,530个参数（约11.91M），其中四成员Q共28,232；不能用28,232代替完整方法新增参数。该计数不包含固定投影/归一化缓冲区，不代表整个VLA系统参数；外部方法暂无同口径核定值，因此不补造参数缩小倍数。Smol/X还使用额外冻结π0.5特征提供者，不能照搬“只增加11.91M”的全系统口径。

来源：[VLA-Corrector逐源合并结果](../sim_command/20260919/results/A/A_D24_E3_UNSTARTED_CONTINUATION_V1/COMBINED_EPISODES.json)；[GAF最终汇总](../sim_command/20260919/results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/FINAL_SUMMARY.json)；[新增网络参数计数](../sim_command/20260919/results/A/A_D24_OURS_E5_REPORT_V1/PARAMETER_COUNTS.json)；[L11逐源结果](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_EPISODES.csv)。

### π0.5＋LIBERO：已完成算子适配版（无 D/G0）

| suite | N 成功/有效（%） | +Velocity算子 成功/有效（%） |
|---|---:|---:|---:|
| libero_spatial | 98/100（98.00%） | 99/100（99.00%） |
| libero_object | 100/100（100.00%） | 99/100（99.00%） |
| libero_goal | 98/99（98.99%） | 99/100（99.00%） |
| libero_10 | 91/100（91.00%） | 90/100（90.00%） |
| all_four_suites | 387/399（96.99%） | 387/400（96.75%） |

## 4. 真实任务效果对比

平台：AgileX PiPER。用户已确认每个任务共60次，每种方法合计180次。按原表顺序将计数对应到Pick-place、Alignment、Disturbance：baseline为41/60、29/60、26/60，Ours为49/60、40/60、39/60。

表中成功率单位为%，统一写为 **成功率 ± 95%置信区间半宽**。单任务采用二项比例的Wald正态近似区间：$\hat p\pm1.96\sqrt{\hat p(1-\hat p)/60}$，以百分数展示；这里的±不是标准差。为统一对称格式，此处已将先前的Wilson区间改为Wald近似，并非将Wilson区间直接改写为对称形式。Avg为三任务等权平均。

| Method | Pick-place ↑ | Alignment ↑ | Disturbance ↑ | Avg. ↑ |
| --- | ---: | ---: | ---: | ---: |
| π0.5 baseline | 68.3 ± 11.8 | 48.3 ± 12.6 | 43.3 ± 12.5 | 53.3 ± 7.1 |
| Ours | 81.7 ± 9.8 | 66.7 ± 11.9 | 65.0 ± 12.1 | 71.1 ± 6.5 |
| Ours − Baseline (pp) | +13.3 | +18.3 | +21.7 | +17.8 |

Avg的95%区间单独按各任务的二项方差传播计算：$\bar p=\frac{1}{3}\sum_{i=1}^{3}p_i$，半宽为$1.96\sqrt{\sum_{i=1}^{3}p_i(1-p_i)/60}/3$。因此baseline为53.3±7.1，Ours为71.1±6.5；这是分任务独立Bernoulli近似下的均值区间，不是跨训练seed的标准差，也不把三个不同任务视为同一个同质二项总体。若试验存在组内相关性，该近似需原始记录进一步调整。

真实实验计数来源：用户提供的本文件原始表述及2026-09-23对“每任务60次”的明确确认。Ours三任务分别增加8、11、13次成功，总计增加32/180，即+17.8pp。未提供逐次配对日志，故不计算差值置信区间或显著性，也不从汇总计数推断Q版本、触发次数或推理费用。

本次补全的可复算数值与来源索引：[DATA_VELOCITY_VALUES_20260923.json](data/DATA_VELOCITY_VALUES_20260923.json)。其他历史版本继续保存在[完整Velocity档案](EXPERIMENT_FOR_VELOCITY.md)和[实验数据总表](EXPERIMENT_RESULTS_MASTER.md)，不以当前表覆盖旧版本。
