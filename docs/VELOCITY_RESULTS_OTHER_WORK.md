# Velocity 结果归档：独立工作，排除本篇最终表图

最终 L11 汇总时间：2026-09-23 05:50:23 UTC。当前配置为 **L11＝BCE＋gain＋0.5pair / 固定 fit9101 / 四成员1041–1044**，Velocity 八个规划格均已完成。Velocity 继承 Post 的最终配置，仅供独立工作使用，不导出到本篇论文的最终表格或图中。以下保留原 L01、旧固定 Q、旧专属 Q 和迁移 Q 的全部数据，分版本归档，不改名移填。本次仅更新文档，不启动、取消或重启科学任务。

## 最终 L11 / fit9101：八格已完成结果与平均调用

当前选择依据为 [L11_SELECTION_OVERRIDE.json](../sim_command/20260919/deadline_20260924/L11_RETEST_V1/L11_SELECTION_OVERRIDE.json)：用户按 Post 完整三 fit 消融的均值和稳定性选定 L11，部署 fit9101 固定。Velocity 不参与 loss、fit 或阈值选型，亦不根据本表重新选型。已揭晓的 50 个消融源参与了这次修订选择，并与 π0.5 主表500源重叠，不能称为新的独立盲测；原 development-only L01 选择锁保留为历史。

下表直接取 [FINAL_ROLLUP.json](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json) 和 [FINAL_CELLS.csv](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_CELLS.csv) 的 Velocity 行。八格各500个有效终局，合计4000个科学单元，技术缺项均为0；总汇总的16格覆盖8000个唯一单元，missing=0、duplicate_unit_keys=0，且与预期 manifest 精确覆盖。模型、模式和 H 共同定义 cell，不将同源的不同协议评测当作新增独立初态。

| 模型 | 模式 | H | 成功/有效（%） | 平均采样调用 | 平均 flow 调用 | 平均干预次数 | 平均动作梯度调用 |
|---|---|---:|---:|---:|---:|---:|---:|
| π0.5 | G0-multi | 10 | 344/500（68.8） | 16.432 | 164.32 | 2.008 | — |
| π0.5 | G0-multi | 20 | 328/500（65.6） | 12.722 | 127.22 | 2.496 | 7.488 |
| π0.5 | G0-multi | 30 | 330/500（66.0） | 11.234 | 112.34 | 2.568 | 7.704 |
| π0.5 | G0-multi | 40 | 318/500（63.6） | 10.796 | 107.96 | 2.664 | 7.992 |
| π0.5 | G0-multi | 50 | 320/500（64.0） | 10.042 | 100.42 | 2.602 | 7.806 |
| π0.5 | G0-once | 10 | 334/500（66.8） | 14.934 | 149.34 | 0.782 | — |
| SmolVLA | G0-multi | 10 | 247/500（49.4） | 23.394 | 233.94 | 2.764 | — |
| X-VLA | G0-multi | 10 | 407/500（81.4） | 16.630 | 166.30 | 3.002 | — |

均值分母为每格500个有效终局；采样、flow和干预计数的已知覆盖均为500/500。动作梯度一列只转录 normalized rollup 已有的全样本均值：π0.5 H20–H50为500/500；Smol为389/500，X为398/500，按该汇总保留“—”，不推算其他缺键。

π0.5 H10 multi/once 的“—”仅表示逐 episode CSV 未导出动作梯度字段：A 的 [EPISODES.csv](../sim_command/20260919/results/A/A_D24_L11_RENDER_RECOVERY_V1/EPISODES.csv) 无该列，因此 normalized rollup 得到 known_count=0、mean=null，**不等于原计量未知**。A 的 [RESULT.json](../sim_command/20260919/results/A/A_D24_L11_RENDER_RECOVERY_V1/RESULT.json) 中 `compute_summary.cells` 已保存这两格各500个有效终局的 `action_gradients` 合计：**G0-multi H10 为3012，G0-once H10 为1173**。这些数值直接取原终局，不由干预次数推算；汇总中的 observed_sum=0 也不应解释为零调用。

旧尝试和无效尝试的成本保留在原账，本表仅描述选入的有效终局，不代表全部尝试成本或 GPU 内核耗时。

π0.5 H10 multi的500条中精确复用此前L11/fit9101消融50条；X-VLA Velocity的500条全部保留此前有效结果。各格其余合法接续与恢复结果沿用来源链去重，原无效尝试只排除出科学汇总、不删除。Smol/X继续使用各自专属的L11四成员及预处理，π0.5使用冻结的π0.5对应配置。

## 历史 L01 选择与执行口径（2026-09-23 00:50 UTC 快照）

本节及后续历史章节记录 L11 切换前的结果与规则；其中的 L01 `selected_locked` 和“新 Q”均为当时的配置身份，不代表当前最终选择。

当时以 [POST_LED_SELECTION_OVERRIDE_V1.json](../sim_command/20260919/deadline_20260924/POST_LED_SELECTION_OVERRIDE_V1.json) 为选择规则：四个候选损失 L00/L10/L01/L11 仅依据 **Post 的完整 development100，在五个 task、三个 fit seed（9101/9102/9103）上的等权宏平均成功率**选择共同 chosen_loss。每个 loss 的 Post 开发单元必须完整；部分开发领先不能产生有效赢家。精确并列先选辅助损失项更少者，再按 L00、L10、L01、L11 排序。

该历史规则中 Velocity 的选择权重为 0，开发和测试成绩均不参与选 loss、fit 或阈值。Velocity 完全继承 Post 当时所选 loss 和预先固定的部署 fit9101 四成员，不另选 Velocity 最佳配置。Smol/X 使用各自底座专属的对应四成员与预处理；π0.5 使用 A 的对应四成员与预处理。当时的 selected-Q 评测采用 Post-only 规则，旧 Post/Velocity 联合分数规则不提供准入依据；当前 L11 则按上节的显式用户选择执行。

历史 [SELECTION.json](../sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json) 保留 `selected_locked`：完整开发 2400 条已齐，其中用于选择的 Post 为 1200 条；chosen_loss=L01，fixed_fit_seed=9101，test_used=false。Velocity 当时继承这一选择；该历史锁不覆盖后来的显式 L11 选择，也不能用 Velocity 成绩反向改选。

依据 [FULL_Q_AUTORUN_ASSIGNMENT_V2.md](../sim_command/20260919/deadline_20260924/FULL_Q_AUTORUN_ASSIGNMENT_V2.md)，完整 Q 候选训练为 A 192000、B 64000、C 64000，共 **320000 次更新，已完成并复用**；没有因选择口径或报告范围改变而重训。本轮 ABC 原定 **11600 个首次评测单元全部完成**：A 5600、B 3000、C 3000。B 原 R 的 24 个缺项接续另列原任务，现 R 汇总为 245/500，不混入本轮 11600 或新 Q Velocity。B 回执的 3500 有效数含原 R 的完整 500 条汇总，不表示新增了 3500 个本轮单元。来源见下方 A/B/C 终局链接。

[AUTORUN_LIVE_CHAIN_COMPATIBILITY_V1.json](../sim_command/20260919/deadline_20260924/AUTORUN_LIVE_CHAIN_COMPATIBILITY_V1.json) 保存了 A 原开发阶段退出时的 1546 个有效开发单元（Post 775、Velocity 771），以及原范围内尚未进入的 854 个单元（Post 425、Velocity 429）。这些数目是该发布时的保存快照，不是完整开发终局或当前实时进度。保留有效单元，仅接续原未进入单元，不整批重放开发，也不以部分 job 的 RESULT 跳过尚未完成的 episode。此次变更新增独立科学单元为 0、新增训练更新为 0。

上述 1546/854 是历史交接快照，现已由完整开发 2400 的终局覆盖其进度状态；历史记录本身保留。以下新 Q 成功数与有效分母直接取真实终局。技术缺项、用户取消和未知分开保留，不记作 success=false；恢复后的完整覆盖也不抹去原中断、失败和取消记录。

## 历史 π0.5＋MT50：旧固定 Q 的五 H 结果

以下成功数、有效数及百分比直接转录自 [EXPERIMENT_RESULTS_MASTER.md](EXPERIMENT_RESULTS_MASTER.md) 原第 1 节及 F6/F7，没有重算统计。旧 once 百分比亦与 [Experiment_plam.md](Experiment_plam.md) 的历史 H 扫描记录一致。这里的旧 Q 是历史固定配置，不是本次完整四损失开发选出的新 Q。

| H | 旧 Q G0-once 成功/有效（%） | 旧 Q Random-once 成功/有效（%） | 旧 Q G0-multi 成功/有效（%） |
|---:|---:|---:|---:|
| 10 | 340/500（68.0） | 308/500（61.6） | 346/500（69.2） |
| 20 | 316/500（63.2） | 245/500（49.0） | 328/500（65.6） |
| 30 | 309/500（61.8） | 209/500（41.8） | 329/500（65.8） |
| 40 | 295/500（59.0） | 208/500（41.6） | 316/500（63.2） |
| 50 | 296/500（59.2） | 195/500（39.0） | 325/500（65.0） |

每格使用原 MT50 的 50 task×10 固定 test 源，有效分母均为 500；各 H、各模式共享原源身份，不能把重复评测当成新增独立初态。底座为冻结 π0.5 SFT030000，raw50/NFE10，纠偏承诺 C10；H 是执行/重规划间隔。G0-once 最多一次，G0-multi 只移除总次数帽，保持原阈值、监测、合法性、C10 锁和总控制预算。Random-once 与 G0-once 的实际触发次数未必相同，不能据本表声称严格等实际次数的纯时机因果效应。

总表保留的原始来源为 [r03 MAIN_20CELL_TABLE.csv](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/MAIN_20CELL_TABLE.csv)、[A Velocity 触发实验 r5 回执](../sim_command/20260919/receipts/A/A_D24_VELOCITY_TRIGGER_MODES_V1_RESULT_r5.json) 与 [TRIGGER_CELLS_AND_COSTS.csv](../sim_command/20260919/deadline_20260924/analysis_20260922_current/trigger/TRIGGER_CELLS_AND_COSTS.csv)。本次沿用总表的来源链，不重新计算配对区间、显著性或成本。修复后的有效覆盖不抹去历史技术失败；Random-multi 已取消，不在此新增待填实验。

## 历史 π0.5＋MT50：继承 Post 选择的 L01 Q 终局

下表为已完成的五 H multi 与 H10 once，均为 L01 / fit9101，使用 A 的所选 π0.5 四成员及冻结预处理，权重身份见 [SELECTION.json](../sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json)。H10 once/multi 仅在同一新 Q 下作次数比较，不与旧 Q 结果混算次数收益。

| H | 执行端 | chosen_loss / fit9101 四权重来源 | 新 Q Velocity-multi 成功/有效 | 新 Q Velocity-once 成功/有效 | 状态 |
|---:|---|---|---|---|---|
| 10 | A | A L01 / 9101 四成员 | 340/500 | 336/500 | 完成 |
| 20 | B | A L01 / 9101 四成员 | 324/500 | 不规划 | 完成；r2 合并原结果与合法接续 |
| 30 | B | A L01 / 9101 四成员 | 324/500 | 不规划 | 完成 |
| 40 | C | A L01 / 9101 四成员 | 314/500 | 不规划 | 完成 |
| 50 | C | A L01 / 9101 四成员 | 317/500 | 不规划 | 完成 |

来源：[A POST_LED RESULT 的 summary.cells](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json)、[B H20/H30 终局 r2](../sim_command/20260919/receipts/B/B_D24_PI05_SELECTED_H20_H30_V1_RESULT_r2.json)、[C H40/H50 FINAL_SUMMARY](../sim_command/20260919/results/C/C_D24_PI05_SELECTED_H40_H50_V1/FINAL_SUMMARY.json)。各规划格均有 500 个有效终局。B r2 保留 H20 原先 24 个有效单元，再合并 976 个有效接续单元（Post/Velocity 合计），没有覆盖原任务失败结果；H20/H30 四格 missing=0。执行和归属沿原交接，不另起重复评测。

## 历史完整 Q：Velocity 开发与四 loss 补充 test 归档

直接转录 [A POST_LED RESULT 的 summary.cells](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json)；各格 complete=true，technical_failures/unstarted/user_cancelled 均为 0。开发表仅作 Velocity 描述，不参与 Post-only 选择；补充 test 使用原已揭晓的 50 个源，不据此另选损失或 fit。下表不新增均值、区间或显著性计算。

| loss | Velocity dev fit9101 成功/有效 | dev fit9102 | dev fit9103 | Velocity 补充 test fit9101 成功/有效 | test fit9102 | test fit9103 |
|---|---:|---:|---:|---:|---:|---:|
| L00 | 66/100 | 68/100 | 64/100 | 32/50 | 32/50 | 34/50 |
| L10 | 68/100 | 66/100 | 67/100 | 32/50 | 34/50 | 34/50 |
| L01 | 71/100 | 69/100 | 69/100 | 35/50 | 35/50 | 39/50 |
| L11 | 68/100 | 68/100 | 70/100 | 37/50 | 36/50 | 34/50 |

## 历史 Smol/X：旧 Velocity 与 L01 Q 边界

以下是总表原第 5 节已经发布的 **冻结 π0.5 辅助网络迁移（frozen-head transfer）**结果；不是底座专属辅助网络重训结果，也不是所选新 Q 结果。

| 底座 | 历史 N 成功/有效（%） | 旧迁移 Q Velocity-once 成功/有效（%） | 结果身份 |
|---|---:|---:|---|
| SmolVLA 050000 | 234/496（47.18） | 247/500（49.40） | frozen-head transfer；N 另有 4 unknown |
| X-VLA 030000 | 403/500（80.60） | 403/500（80.60） | frozen-head transfer；各 500 有效 |

数值直接取自 [EXPERIMENT_RESULTS_MASTER.md](EXPERIMENT_RESULTS_MASTER.md) 的“MetaWorld MT50：历史 once 结果”表。Smol raw50/K10、X raw30/K10，正常实际执行间隔均为 10；B/C 原协议为 80Hz/.01，与 A 的 π0.5 主表不同，不跨设置逐源配对或合并统计。Smol 的未知 N 源不计失败，也不能以 Velocity 全部 500 条的成功数充当共同有效 N 配对成功数。

### 旧专属 Q 的已核对终局

以下计数转录自分析端已读取的对应真实小终局，属于各底座旧专属 Q；与上表 frozen-head transfer 分开保留，不能移填所选新 Q 结果。

| 底座 / 节点 | 旧专属 Q Velocity-once 成功/有效 | 旧专属 Q Velocity-multi 成功/有效 | 来源与状态 |
|---|---:|---:|---|
| SmolVLA 050000 / B | 247/500 | 不作当前结果：旧Q无完整终局 | [once recovery_r3 FINAL_SUMMARY](../sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/recovery_r3/FINAL_SUMMARY.json)；该旧Q单元不属于当前选定配置，不以新Q240/500回填，亦不作为待补实验 |
| X-VLA 030000 / C | 407/500 | 408/500 | [once FINAL_SUMMARY](../sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1/FINAL_SUMMARY.json)、[multi FINAL_SUMMARY](../sim_command/20260919/results/C/C_D24_XVLA_MULTI_EVAL_V1/FINAL_SUMMARY.json) |

### 历史继承 Post 选择的 L01 Q 终局

| 底座 / 节点 | 继承 Post 的 chosen_loss / 自身 fit9101 四权重来源 | 新 Q Velocity-multi 成功/有效 | 状态 |
|---|---|---|---|
| SmolVLA 050000 / B | 自身 L01 / 9101 四成员 | 240/500 | 完成 |
| X-VLA 030000 / C | 自身 L01 / 9101 四成员 | 412/500 | 完成 |

Smol 来源：[B QUOTA_INDEPENDENT_QUEUE 终局 r2 的 native / Velocity](../sim_command/20260919/receipts/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1_RESULT_r2.json)，全部依赖阶段 remaining_units=0、summary.missing=0。X 来源：[C FULL_Q_LOSS_REFRESH FINAL_SUMMARY 的 groups / Velocity](../sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/FINAL_SUMMARY.json)，technical/unknown/unstarted 均为 0；其选定自身权重与预处理引用为 [SELECTION_CONSUMED.json](../sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/SELECTION_CONSUMED.json)。两底座均为各自专属数据训练的完整 Q，不使用 A 的 π0.5 权重代替。新 Q multi 与旧 Q once 同时改变 Q 和次数协议，不能解释为纯次数收益。

## 历史 L01 成本与配对统计的发布状态

历史L01 π0.5 Velocity五H multi及H10 once调用已录入[总表第6节](EXPERIMENT_RESULTS_MASTER.md)，Smol/X的已保存配对已录入总表F8，均保持新旧Q分开；[历史F8结果入口](EXPERIMENT_RESULTS_MASTER.md#current-f8)两底座已完整。尚未生成的其他统计不从成功总数推断，不使用旧Q/旧once代替。X 的历史成本摘要保存在上述 FINAL_SUMMARY 的 Velocity `per_valid_episode` / `all_valid_cost_per_success` 字段，配对来源由该文件指向 `PAIRED.json`；这些L01成本不移填顶部L11表。历史技术尝试成本仍保留在原账，occupancy 成本与科学成本分列。
