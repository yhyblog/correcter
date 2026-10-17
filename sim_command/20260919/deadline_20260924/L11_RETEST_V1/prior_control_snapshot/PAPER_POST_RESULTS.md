# 本篇论文结果入口：N / R / Post

当前论文核心表格及正文／附录安排见[EXPERIMENT_FOR_PAPER.md](EXPERIMENT_FOR_PAPER.md)。该文档记录实际已运行的L01版本；L11切换讨论不改变旧结果身份。

**2026-09-23 CPU分析补充：**已按同500初态补齐当前Post的五H配对统计和完整策略调用；Post−N五H均有明确增益，Post−R五H区间均包含零。论文可宣称的优势、费用口径与组件边界见[当前Post论文主张](POST_PAPER_CLAIMS_20260923.md)。LIBERO本次暂不纳入，未新增科学实验或改选配置。

更新：2026-09-23 00:50 UTC。**本篇最终方法展示为Post。** 本文件直接转录已发布N/R与本轮完整Q Post终局，不把旧Post Q结果改名为新Q。本轮Velocity评测也已完成，继承Post选择，完整结果见[另文档案](VELOCITY_RESULTS_OTHER_WORK.md)，不进入本篇最终表图；全部历史数据仍见[实验总表](EXPERIMENT_RESULTS_MASTER.md)。

## 选择规则与当前状态

共同loss按四候选各自完整Post development100上的五任务×三fit（9101/9102/9103）等权成功率均值选择；Velocity权重0，不按test选loss、阈值或训练seed。精确并列先辅助项少，再L00/L10/L01/L11。正式部署固定fit9101四成员。Post开发缺项不能以不等分母评赢家。

完整Q候选80 fits/320000更新和原11600首次评测全部完成。A5600＝DEV2400＋test1200＋H10 multi P/V1000＋H10 once P/V1000，技术失败0；B/C各新Q3000完整，B另补原R24槽不混入11600。A原1546有效/854待续仅是排空时历史快照，DEV现已2400完整。共同选择已锁定L01（BCE＋0.5pair）、固定fit9101；Post DEV分数L00 202/300、L10 203/300、L01 207/300、L11 203/300。

## π0.5 / MT50：新完整Q Post主表

每格为同一原500初态（50任务×10源），跨H和方法重复使用相同初态身份；不能把各格分母累加当成独立初态。N与R不依赖新Q，直接复用可靠终局。新Q Post-multi保持原source、模型底座、动作桥、H/C10、D/G0与随机流，仅按锁定选择更换Q；新Q H10 once与同新Q multi配对。**旧Post-multi的355/339/341/328/328及旧Post-once成绩均属于旧Q，不改名为下面新Q结果。**

| H | N 成功/有效（%） | R-multi 成功/有效（%） | 新Q chosen_loss / fit | 新Q Post-multi成功/有效 | 新Q Post-once成功/有效 | 新Q Post−R配对及成本 |
|---:|---:|---:|---|---|---|---|
| 10 | 308/500（61.6） | 343/500（68.6） | L01 / 固定9101 | 350/500 | 341/500 | +1.4 pp；95% CI [−0.6,3.6]；14.074 calls/ep |
| 20 | 240/500（48.0） | 324/500（64.8） | L01 / 固定9101 | 334/500 | 不规划 | +2.0 pp；[−0.2,4.2]；9.906 calls/ep |
| 30 | 205/500（41.0） | 330/500（66.0） | L01 / 固定9101 | 334/500 | 不规划 | +0.8 pp；[−1.6,3.2]；8.462 calls/ep |
| 40 | 205/500（41.0） | 318/500（63.6） | L01 / 固定9101 | 324/500 | 不规划 | +1.2 pp；[−1.2,3.6]；7.966 calls/ep |
| 50 | 196/500（39.2） | 321/500（64.2） | L01 / 固定9101 | 323/500 | 不规划 | +0.4 pp；[−1.8,2.8]；7.278 calls/ep |

N/R数值逐项转录[总表第1节](EXPERIMENT_RESULTS_MASTER.md)，其终局来源为[原N主表](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/MAIN_20CELL_TABLE.csv)和[R multi回执](../sim_command/20260919/receipts/C/C_D24_R_TRIGGER_MODES_V1_RESULT.json)。本次CPU补充按共同500有效源计算配对差：固定任务内5000次bootstrap逐项区间、精确McNemar和每底座五H的Holm校正；见[统计与来源](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/main_pairs.json)。calls/ep是全部有效任务的完整策略采样均值，包含自然与干预采样，不能代替端到端时间；见[成本定义](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/costs_notes.md)。技术异常、用户取消和unknown不计任务失败。

终局来源：[A完整5600](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json)、[Post-only选择锁](../sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json)、[B H20/H30恢复发布r2](../sim_command/20260919/receipts/B/B_D24_PI05_SELECTED_H20_H30_V1_RESULT_r2.json)、[B native及原R终局r2](../sim_command/20260919/receipts/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1_RESULT_r2.json)、[C H40/H50](../sim_command/20260919/results/C/C_D24_PI05_SELECTED_H40_H50_V1/FINAL_SUMMARY.json)、[C native X](../sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/FINAL_SUMMARY.json)。 B首次发布失败和中间结果保留；恢复发布不等于原全过程零故障。

## 可复用的历史N / R-once对照

以下同为原500源的已完成记录。R-once与R-multi明确区分；跨模式比较不能把换Q与次数收益混为一项。

| H | N成功/500（%） | R-once成功/500（%） |
|---:|---:|---:|
| 10 | 308/500（61.6） | 336/500（67.2） |
| 20 | 240/500（48.0） | 312/500（62.4） |
| 30 | 205/500（41.0） | 307/500（61.4） |
| 40 | 205/500（41.0） | 290/500（58.0） |
| 50 | 196/500（39.2） | 297/500（59.4） |

直接转录[原20格表](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/MAIN_20CELL_TABLE.csv)。这些已完成单元不重跑。

## 新完整Q Post损失消融与跨底座终局

| loss | 完整Post dev五任务/三fit均值 | Post test seed9101成功/有效 | seed9102成功/有效 | seed9103成功/有效 | 选择状态 |
|---|---|---|---|---|---|
| L00 | 202/300；0.6733333333333333 | 38/50 | 35/50 | 35/50 | 未选定 |
| L10 | 203/300；0.6766666666666666 | 35/50 | 35/50 | 34/50 | 未选定 |
| L01 | 207/300；0.69 | 35/50 | 35/50 | 33/50 | 已选L01，固定fit9101 |
| L11 | 203/300；0.6766666666666666 | 37/50 | 36/50 | 35/50 | 未选定 |

Post补充test为四loss×三fit×原50源，共600条，属于原双分支1200范围；选择先锁定，test不能反改选择。原50 test已揭晓，仅作复用测试源的补充消融，三个fit不当成150个独立初态。旧微调E1不得代填全参数从头训练结果。

| 底座 | 原N成功/有效 | 专属R-multi成功/有效 | 所选本底座新Q Post-multi成功/有效 | 限定 |
|---|---:|---|---|---|
| SmolVLA050000 | 234/496 | 245/500 | 245/500 | L01/fit9101；R原24缺槽已补齐，N四unknown保留 |
| X-VLA030000 | 403/500 | 412/500 | 409/500 | L01/fit9101；旧Q Post不替代新Q |

Smol R与新Q Post直接转录[B终局r2](../sim_command/20260919/receipts/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1_RESULT_r2.json)；N沿[总表F8](EXPERIMENT_RESULTS_MASTER.md)保留。X R直接转录[原multi终局](../sim_command/20260919/results/C/C_D24_XVLA_MULTI_EVAL_V1/FINAL_SUMMARY.json)。Smol/X沿各自原冻结500源及动作/环境协议，不能与π0.5跨协议逐源混配。

## 自动接续与导出范围

A/B/C已在有效Post-only SELECTION及明确transfer归属下完成上述本轮范围：A5600、B3000、C3000，总11600。B原R24缺槽额外补齐仅属于原R任务。全部80 fits/320000训练更新完成；本次只转录终局，无新训练、评测或统计计算。

本篇导出N/R/Post、新Q Post学习消融、Post跨底座/环境以及其触发、外部对比和真实成本。已有外部方法/E6原始终局在总表保留复用；当前π0.5新Q五H配对、区间和调用成本已补齐，外部配对与组件边界统一见[主张文档](POST_PAPER_CLAIMS_20260923.md)。未复制旧Post统计作为新Q结论。Velocity相关列、图和结论统一留在另文；不因分开展示重算或删除已发布统计。LIBERO Full监督缺口、真机待用户记录仍留空，旧N五未知（Smol4、LIBERO1）保留，不能称所有论文事项完成。
