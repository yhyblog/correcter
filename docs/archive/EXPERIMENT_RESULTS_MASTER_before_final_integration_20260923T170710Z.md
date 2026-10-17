# Corrector 实验结果总表（含另文Velocity原始结果）

**总表定位：完整保存实验过程中产生的全部数据、版本、原始失败与成本缺项。** 论文只取已筛选的最终有效数据，见[EXPERIMENT_FOR_PAPER.md](EXPERIMENT_FOR_PAPER.md)；[长期整理规则](PAPER_DATA_CURATION_POLICY.md)。执行安排不放入论文结果文档。

**当前更新（2026-09-23T05:58:12.435100+00:00）：最终L11/fit9101重测及恢复全部完成。16格、8000个有效科学单元＝7900个本轮新单元＋100个原消融精确复用，缺项0、重复科学键0。** A恢复1900、B接手H30恢复1000、C恢复1764，合计4664；此前有效3236和复用100均保留。三机最后正式进程族均已退出并交回占卡管理，状态依据各自终局回执，不是本轮跨机硬件探测。旧A/C渲染异常记录仍保留为质量隔离历史，未将旧失败/未知改写为有效结果。此次仅CPU汇总与完成登记，不新增实验派单或计算。

<a id="current-l11-retest"></a>
## 当前L11最终结果（完整16格）

| 模型 | 模式 | H/K | Post成功/有效 | Velocity成功/有效 | 状态 |
|---|---|---:|---|---|---|
| π0.5 | G0-multi | 10 | 346/500（69.2%） | 344/500（68.8%） | 已完成并纳入汇总 |
| π0.5 | G0-multi | 20 | 336/500（67.2%） | 328/500（65.6%） | 已完成并纳入汇总 |
| π0.5 | G0-multi | 30 | 331/500（66.2%） | 330/500（66.0%） | 已完成并纳入汇总 |
| π0.5 | G0-multi | 40 | 324/500（64.8%） | 318/500（63.6%） | 已完成并纳入汇总 |
| π0.5 | G0-multi | 50 | 326/500（65.2%） | 320/500（64.0%） | 已完成并纳入汇总 |
| π0.5 | G0-once | 10 | 343/500（68.6%） | 334/500（66.8%） | 已完成并纳入汇总 |
| SmolVLA | G0-multi | 10 | 250/500（50.0%） | 247/500（49.4%） | 已完成并纳入汇总 |
| X-VLA | G0-multi | 10 | 411/500（82.2%） | 407/500（81.4%） | 已完成并纳入汇总 |

H10 multi各50个复用源已参与配置选择，与该格500源重叠；必须披露，不能称为新盲测。π0.5各H/模式共用500初态，不能把8000条评测记录当成8000独立初态。L11的训练候选来自完整Q训练；旧L01及旧残差训练实验分别保留。N/R、外部基线及Q无关E6复用原真实结果。LIBERO暂不推进，Velocity仅供另一篇工作。

| 最后恢复节点 | 本次恢复有效单元 | 最终汇总范围 | 终局 |
|---|---:|---|---|
| A | 1900 | H10 Post/Velocity multi和once共2000，含100复用 | 全部完成，进程族退出 |
| B | 1000 | H30 P/V1000；另此前自身2500有效保持 | 全部完成，进程族退出 |
| C | 1764 | H40 P/V、H50 V与X P/V共2500，含736此前有效 | 全部完成，进程族退出 |

并发目标为24路/卡×8卡＝192路，实际为共享模型、batch1的逻辑分支调度，不声称每时刻192活跃。A本次P/V峰值均175；B H30峰值144/155。资源与吞吐不因目标数字而推断。

### L11成本：所有有效episode上的平均调用与干预

| 底座 | 分支/模式 | H/K | 平均完整策略采样 | 平均flow调用 | 平均干预 |
|---|---|---:|---:|---:|---:|
| π0.5 | Post/G0-multi | 10 | 14.248 | 142.480 | 2.050 |
| π0.5 | Velocity/G0-multi | 10 | 16.432 | 164.320 | 2.008 |
| π0.5 | Post/G0-multi | 20 | 9.968 | 99.680 | 2.390 |
| π0.5 | Velocity/G0-multi | 20 | 12.722 | 127.220 | 2.496 |
| π0.5 | Post/G0-multi | 30 | 8.678 | 86.780 | 2.616 |
| π0.5 | Velocity/G0-multi | 30 | 11.234 | 112.340 | 2.568 |
| π0.5 | Post/G0-multi | 40 | 7.966 | 79.660 | 2.594 |
| π0.5 | Velocity/G0-multi | 40 | 10.796 | 107.960 | 2.664 |
| π0.5 | Post/G0-multi | 50 | 7.422 | 74.220 | 2.624 |
| π0.5 | Velocity/G0-multi | 50 | 10.042 | 100.420 | 2.602 |
| π0.5 | Post/G0-once | 10 | 13.840 | 138.400 | 0.782 |
| π0.5 | Velocity/G0-once | 10 | 14.934 | 149.340 | 0.782 |
| SmolVLA | Post/G0-multi | 10 | 20.382 | 203.820 | 2.700 |
| SmolVLA | Velocity/G0-multi | 10 | 23.394 | 233.940 | 2.764 |
| X-VLA | Post/G0-multi | 10 | 13.412 | 134.120 | 2.884 |
| X-VLA | Velocity/G0-multi | 10 | 16.630 | 166.300 | 3.002 |

这些成本已包含本轮不限总干预次数的multi结果；每格成本覆盖500/500，只统计有效科学episode，旧技术尝试成本另存原账。平均调用不是“完成一个成功任务的成本”；并发下episode墙钟不直接解释为单次推理耗时，也不与旧低并发时延作加速比较。逐episode动作梯度字段存在不同导出完整度，未获得字段不自动补0；调用/flow/干预三项均完整。

同L11、同500源的H10次数比较：Post once343→multi346（+0.6pp，救回10/损害7）；Velocity once334→multi344（+2.0pp，救回14/损害4）。未据此声明显著优于或全任务一致受益。

终局来源：[全16格及覆盖检查](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json)、[8000行有效结果](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_EPISODES.csv)、[成功率/成本CSV](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_CELLS.csv)。执行端：[A最终](../sim_command/20260919/results/A/A_D24_L11_RENDER_RECOVERY_V1/FINAL_SUMMARY.json)、[B原2500](../sim_command/20260919/results/B/B_D24_L11_RETEST_V1/FINAL_RECOVERED_SUMMARY_r2.json)、[B H30](../sim_command/20260919/results/B/B_D24_L11_RENDER_RECOVERY_V1/FINAL_SUMMARY.json)、[C审阅终局](../sim_command/20260919/results/C/C_D24_L11_RENDER_RECOVERY_V1/AUDITED_SUMMARY.json)。[完成情况与剩余清单](EXPERIMENT_STATUS_AND_REMAINING_20260923.md)。

---

### L11首次执行原始结果与质量处置（历史保留，不进入论文有效表）

以下为恢复前快照。缺项现已由独立恢复完成；旧质量隔离记录仍无效，不覆盖、不删除、不重计。

A旧同源三例在首噪声、step0 G0、前5动作/reward一致时，Q介入前step5 G0已不同；共享EGL渲染存在OpenGL0x506日志。C亦有同样pre-Q分歧，并主动标记1500条质量hold。以下数值保留为原始诊断，不认作L11效果。后续已通过私有环境进程隔离及渲染上下文修复恢复原非有效单元；不是仅凭低成功率否定结果。

| 原执行节点 | 模式/H | Post原汇总成功/记录 | Velocity原汇总成功/记录 | 分析处置 |
|---|---|---|---|---|
| A | G0-multi/H10 | 81/500 | 81/500 | 新执行部分暂缓采信；H10multi原复用各50有效 |
| A | G0-multi/H30 | 61/500 | 65/500 | 新执行部分暂缓采信；H10multi原复用各50有效 |
| A | G0-once/H10 | 49/500 | 56/500 | 新执行部分暂缓采信；H10multi原复用各50有效 |
| C | G0-multi/H40 | 49/500 | 40/500 | 1000条执行质量hold |
| C | G0-multi/H50 | 不归C | 38/500 | 500条执行质量hold |

C X Post完整500源处置：236有效（198成功、38科学失败），211技术缺项、31已进入但未知、22渲染hold；四类合计500。技术/未知/hold均不计科学失败，198/236不能代替完整500成功率。C X Velocity500有效、407成功。

B初始π0.5构造器故障发生在episode前，科学结果null；其Smol1000继续完成，私有修复后补齐原未进入π0.5 1500，最终有效2500、缺项0，原故障和原1000部分汇总保留。当前B以FINAL_RECOVERED_SUMMARY_r2为准。

原始结果/逐episode/成本：[A终局及全部计量](../sim_command/20260919/results/A/A_D24_L11_RETEST_V1/RESULT.json)、[B最终合并结果](../sim_command/20260919/results/B/B_D24_L11_RETEST_V1/FINAL_RECOVERED_SUMMARY_r2.json)、[C全任务质量分类与成本](../sim_command/20260919/results/C/C_D24_L11_RETEST_V1/task_summary/SUMMARY.json)、[C全部原始尝试](../sim_command/20260919/results/C/C_D24_L11_RETEST_V1/task_summary/ATTEMPTS_ALL.csv)。旧原始结果不覆盖；恢复产生独立尝试链，最终每科学key只计一个可用结果。


## 2026-09-23 L01终局与此前实验历史（原数值保留）


论文取表与正文／附录安排见[EXPERIMENT_FOR_PAPER.md](EXPERIMENT_FOR_PAPER.md)。 L11正式切换后的完整结果和执行状态见本表最前部；以下为L01历史快照。总表恢复为主结果→外部比较→损失消融→触发机制→适配→成本的顺序；[multi损失消融](#current-multi-loss)与[F8](#current-f8)保留直接跳转。

**2026-09-23分析补充：**按用户要求暂不讨论LIBERO，当前Post可宣称的优势、五H配对统计及调用成本见[优势与证据边界](POST_PAPER_CLAIMS_20260923.md)。该历史快照采用L01/fit9101；当前新任务已另行授权L11，不覆盖该历史数据。

表格更新：2026-09-23T01:27:03.348026+00:00；科学终局快照仍为2026-09-23 00:50 UTC。**本轮完整Q选型与正式评测全部完成：80 fits/320000更新，原11600条首次评测全部有效。** A5600＝DEV2400＋四loss补充test1200＋H10 multi P/V1000＋H10 once P/V1000；B3000＝Smol P/V1000＋π0.5 H20/30 P/V2000；C3000＝X P/V1000＋π0.5 H40/50 P/V2000。B另补原R的24个缺槽，形成R500有效，不混入11600。

**共同选择已锁定L01（BCE＋0.5pair），部署固定fit9101四成员。** Post完整DEV的五任务×三fit等权分数：L00为202/300（0.6733333333）、L10为203/300（0.6766666667）、L01为207/300（0.69）、L11为203/300（0.6766666667）。Post与Velocity各1200 DEV均完整；Velocity选择权重0，仅继承Post配置，不按test改loss/fit/阈值。本篇最终展示Post，Velocity原始结果与授权实验完整保留，仅供另文。

| 节点 | 本轮已完成范围 | 终局与保留事项 |
|---|---|---|
| A | 48 fits/192000更新；5600有效 | 技术失败0；旧DEV1546待续是排空时历史快照，剩余原源现已补齐，无重训 |
| B | 16 fits/64000更新；新Q3000有效；另原R500有效 | H20/H30四格missing0；初次发布失败及原中间结果保留，r2恢复发布不抹去故障历史 |
| C | 16 fits/64000更新；新Q3000有效 | X P/V1000及H40/H50 P/V2000均完整，技术缺项0 |

新Q π0.5 Post multi H10/20/30/40/50为350/334/334/324/323（各500）；H10 Post once341/500。Smol新Q Post245/500、原R修复后245/500；X新Q Post409/500、原R412/500。新Q与旧Q分表，旧Post分数、失败及成本证据不改名为本轮结果。

**“本轮11600完成”不等于所有论文事项完成。** LIBERO Full仍有开发监督科学缺口，未完成Full测试；真机仍待用户交付；旧N未知5槽（Smol4、LIBERO1）保留。当前新Q Post主配对/E3、P/V调用、完整Q分fit及均值SD、E6 multi详情和跨底座现成配对已录入本表。尚无可靠记录的计时/能耗继续NR；本次仅CPU转录与算术汇总，不新增实验。已完成单元不得重跑。

终局来源：[A完整5600](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json)、[Post-only选择锁](../sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json)、[B H20/H30恢复发布r2](../sim_command/20260919/receipts/B/B_D24_PI05_SELECTED_H20_H30_V1_RESULT_r2.json)、[B native及原R终局r2](../sim_command/20260919/receipts/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1_RESULT_r2.json)、[C H40/H50](../sim_command/20260919/results/C/C_D24_PI05_SELECTED_H40_H50_V1/FINAL_SUMMARY.json)、[C native X](../sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/FINAL_SUMMARY.json)。

本篇结果见[PAPER_POST_RESULTS](PAPER_POST_RESULTS.md)，Velocity见[另文档案](VELOCITY_RESULTS_OTHER_WORK.md)。总表保留Velocity所有原始数据，但不整表导出到本篇最终稿。

- **空白数值格**：该计划实验/更新尚未完成，等待终局填入；不是0，也不是失败。
- **NR / 未记录**：实验已完成，但该字段未测得或不能可靠恢复；不靠新增无关实验补造。
- **未规划 / 不适用**：本轮不做该单元，如未纳入本轮的其他配置；不要当成后续待填实验。
- 成功率为成功数÷有效episode；技术失败/未知单列，不自动计作任务失败。计划数量不充当实际分母。pp为百分点。
- 不同初态、seed、renderer、训练来源、动作时距的结果各表保留，不跨表混合平均。不因结果不显著追加样本或回调参数。

| 实验块 | 已完成规模 | 当前状态 | 本文位置 |
|---|---|---|---|
| π0.5-MT50 multi及H扫描 | 旧N五格＋multi十五格=10000有效，共享500初态 | 新所选L01 P/V5000已完成；旧Q仅历史参考 | 第1节、F7 |
| E1损失消融 | 旧微调once1200有效；旧multi420有效/780取消 | 新完整Q48 fits、DEV2400、test1200均完成；Post-only选定L01 | 第3节F9 |
| E6触发对照 | 100开发＋once100＋multi100 | 两种次数协议均完成；multi次数/调用/配对已补齐 | 第4节F10 |
| VLA-Corrector/GAF外部对比 | 两方法各500 | 完成，现有结果复用 | 第2节 |
| Smol/X冻结π0.5辅助网络迁移 | 4单元各500；基线有4未知 | frozen-head transfer完成，非专属重训 | 第5节 |
| Smol/X专属辅助网络 | 两底座各250父源及旧32000更新完成 | 各新Q16 fits/64000更新、新P/V各1000均完成；Smol原R24缺槽补齐 | 第5节F8 |
| LIBERO算子版Post/Velocity | 两方法各400；更新后N有效399/400 | 完成；无D/G0，不是Full | 第5节 |
| LIBERO完整D/G0＋Post/Velocity | 40开发attempt、30有效；Full测试0 | 本批终止：G0的11个收益标签全0，Full未完成 | F1、F3 |
| 旧N缺项恢复/合法接续 | 5个LIBERO槽恢复有效且成功；仍5未知 | 当前补缺任务完成，未知保留 | F2 |
| E5参数/调用/时间 | N＋multi20格调用已更新 | 新Q P/V五H及H10 once调用已补录；未确认的新计时仍NR | 第6节 |
| once/multi开发pilot | 六臂×20=120 | 完成，不混主表 | 第7节 |
| Random-once随机时机 | 15格×500=7500有效 | 完成；终局及配对已填 | F6 |
| G0-multi不限总次数 | 旧Q15格×500=7500有效 | 历史结果完整；新正式Q L01五H P/V也已完成 | 第1节、F7 |
| Random-multi不限次数随机对照 | 原7500计划取消 | 不再实验；Random-once保留 | F11 |
| standalone历史结构消融 | held100、每源4后缀种子 | 完成并封存 | 第8节 |
| 用户真实场景一组 | 数量/设置待用户确定 | 留空；无外部方法真机矩阵 | F4 |

QGF、QPILOTS目前仅是文献参考，不新增“必做复现”空表。被删除的数据效率、容量非劣、大方向矩阵，以及475源大采集不在本结果清单里恢复。

## 1. MT50主结果与H扫描（E4/E9）

### 新所选Q L01正式结果（本轮完整终局）

N/R沿上表复用，仍为相同500个原始初态；新Q固定fit9101四成员，Post/Velocity各五H×500。Post进入本篇，Velocity仅另文。chosen_loss已锁定L01；以下数值来自本轮真实终局，旧L11成绩不得移填。新H10 once各500仅与同一新Q multi作次数对照，不与旧Q混算纯次数收益。

| H | chosen_loss / 权重来源 | 新Q Post-multi成功/有效 | 新Q Velocity-multi成功/有效 | 新Q Post-once成功/有效 | 新Q Velocity-once成功/有效 |
|---|---|---|---|---|---|
| 10 | L01 / A fit9101四成员 | 350/500 | 340/500 | 341/500 | 336/500 |
| 20 | L01 / A fit9101四成员，B执行 | 334/500 | 324/500 | 不规划 | 不规划 |
| 30 | L01 / A fit9101四成员，B执行 | 334/500 | 324/500 | 不规划 | 不规划 |
| 40 | L01 / A fit9101四成员，C执行 | 324/500 | 314/500 | 不规划 | 不规划 |
| 50 | L01 / A fit9101四成员，C执行 | 323/500 | 317/500 | 不规划 | 不规划 |

终局来源：[A完整5600](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json)、[Post-only选择锁](../sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json)、[B H20/H30恢复发布r2](../sim_command/20260919/receipts/B/B_D24_PI05_SELECTED_H20_H30_V1_RESULT_r2.json)、[B native及原R终局r2](../sim_command/20260919/receipts/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1_RESULT_r2.json)、[C H40/H50](../sim_command/20260919/results/C/C_D24_PI05_SELECTED_H40_H50_V1/FINAL_SUMMARY.json)、[C native X](../sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/FINAL_SUMMARY.json)。 当前Post新Q配对与两分支调用成本已补录到下表和第6节；Velocity列只作另文原始记录。


### 新Q补录：Post五H同初态配对

| H | 对比 | 共同有效 | 左/右成功数 | 差值pp | 逐项95%区间pp | 救回/损害 | 精确McNemar p | 各五H Holm p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | Post−N | 500 | 350/308 | +8.4 | [5.4, 11.4] | 63/21 | 4.96802e-06 | 4.96802e-06 |
| 10 | Post−R | 500 | 350/343 | +1.4 | [-0.6, 3.6] | 20/13 | 0.296206 | 1 |
| 20 | Post−N | 500 | 334/240 | +18.8 | [15.8, 22.0] | 103/9 | 2.31451e-21 | 4.62902e-21 |
| 20 | Post−R | 500 | 334/324 | +2.0 | [-0.2, 4.2] | 23/13 | 0.132498 | 0.662491 |
| 30 | Post−N | 500 | 334/205 | +25.8 | [22.4, 29.2] | 141/12 | 4.2189e-29 | 1.68756e-28 |
| 30 | Post−R | 500 | 334/330 | +0.8 | [-1.6, 3.2] | 22/18 | 0.635828 | 1 |
| 40 | Post−N | 500 | 324/205 | +23.8 | [20.6, 27.0] | 130/11 | 5.75468e-27 | 1.7264e-26 |
| 40 | Post−R | 500 | 324/318 | +1.2 | [-1.2, 3.6] | 24/18 | 0.440799 | 1 |
| 50 | Post−N | 500 | 323/196 | +25.4 | [22.0, 28.6] | 134/7 | 1.42935e-31 | 7.14674e-31 |
| 50 | Post−R | 500 | 323/321 | +0.4 | [-1.8, 2.8] | 20/18 | 0.871415 | 1 |

区间为固定50任务内、每任务10源的配对bootstrap5000次，seed20260923；Holm分别覆盖五个Post−N和五个Post−R，不是全论文校正。区间不包含训练seed或未见任务不确定性。五H共享500初态，不当作2500个独立源。Post−R五组区间均含0，不把Post−N大收益全部归因于Q纠偏。来源：[配对CSV](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/main_pairs.csv)、[统计方法与逐文件来源](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/main_pairs.json)。

### 新Q补录：H10同版本multi−once

| 分支 | multi / once成功 | 有效对数 | 差值pp | 95%区间pp | 救回/损害 | 精确p |
| --- | --- | --- | --- | --- | --- | --- |
| Post | 350/500 / 341/500 | 500 | +1.8 | [0.4, 3.4] | 13/4 | 0.0490417 |
| Velocity（另文） | 340/500 / 336/500 | 500 | +0.8（描述差值） | NR：本次未生成配对区间 | NR | NR |

Post配对直接转录[A已发布PAIRED.csv](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/PAIRED.csv)，固定任务内bootstrap2000次/seed20260921，单项未校正。Velocity两格终局完整，但不从边际成功数推断救回/损害。两分支once/multi调用均已补到第6节；不使用旧Q once作为新Q次数对照。

### 旧固定Q参考表：N与G0-multi（已完成，保留历史分数）

每格50任务×10源=500。H是原生执行/重规划间隔，raw50/NFE10，C10后丢尾恢复该H；D/G0/Q保持原五任务训练覆盖。G0严格>0.05、5步监测、因果历史和合法队列不变，只取消总次数帽。C10期间不能重入，不强迫触发，300控制步和提前成功规则不变。

| H | N 成功/500（%） | R-multi 成功/500（%） | Post-multi 成功/500（%） | Velocity-multi 成功/500（%） | Post−R（pp） | Velocity−R（pp） |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 308/500（61.6） | 343/500（68.6） | 355/500（71.0） | 346/500（69.2） | +2.4 | +0.6 |
| 20 | 240/500（48.0） | 324/500（64.8） | 339/500（67.8） | 328/500（65.6） | +3.0 | +0.8 |
| 30 | 205/500（41.0） | 330/500（66.0） | 341/500（68.2） | 329/500（65.8） | +2.2 | -0.2 |
| 40 | 205/500（41.0） | 318/500（63.6） | 328/500（65.6） | 316/500（63.2） | +2.0 | -0.4 |
| 50 | 196/500（39.2） | 321/500（64.2） | 328/500（65.6） | 325/500（65.0） | +1.4 | +0.8 |

来源为本文F7及[有效episode调用/成功表](../sim_command/20260919/deadline_20260924/analysis_20260922_current/trigger/TRIGGER_CELLS_AND_COSTS.csv)。N复用旧五格；15格multi有效7500，旧技术中断和纠正记录保留。上表点差不冒充显著性，不能把R带来的收益全部归因于纠偏。multi与once的已发布配对和次数分布保留在F7。

### 历史次数预算消融：G0-once（原主表，保留）

每格50任务×10个固定test源，分母500；20格均已完成，共10000个有效episode，技术失败0。共享500个初态身份，不能将10000个episode当成10000个独立初态。冻结π0.5 SFT030000，D/G0/Q仍为历史五任务训练后迁移；once≤1，C10；H是执行/重规划间隔，raw plan固定50。N=原底座，R=收益触发后仅重规划，Post/Velocity=收益触发加对应纠偏。

| H | N 成功/500（%） | R 成功/500（%） | Post 成功/500（%） | Velocity 成功/500（%） | Post−N（pp） | Velocity−N（pp） |
|---|---:|---:|---:|---:|---:|---:|
| 10 | 308/500（61.6） | 336/500（67.2） | 345/500（69.0） | 340/500（68.0） | +7.4 | +6.4 |
| 20 | 240/500（48.0） | 312/500（62.4） | 322/500（64.4） | 316/500（63.2） | +16.4 | +15.2 |
| 30 | 205/500（41.0） | 307/500（61.4） | 316/500（63.2） | 309/500（61.8） | +22.2 | +20.8 |
| 40 | 205/500（41.0） | 290/500（58.0） | 300/500（60.0） | 295/500（59.0） | +19.0 | +18.0 |
| 50 | 196/500（39.2） | 297/500（59.4） | 300/500（60.0） | 296/500（59.2） | +20.8 | +20.0 |

H20–50的R已完成：312/307/290/297成功。各H的Full−R已可直接报告，不能把Full−N全部归于额外纠偏。Post−R为+0.6至+2.0pp，Velocity−R为−0.2至+1.0pp；多数配对区间包含0，详见下表。P/V五个同H直接比较的既有区间均跨0，不宣称Post稳定优于Velocity。

来源：[r03完整20格CSV](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/MAIN_20CELL_TABLE.csv)、[r03汇总说明](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/MASTER_DOCUMENT_UPDATE.md)；[原16格H扫描](../sim_command/20260919/deadline_20260924/H_SWEEP_RESULTS.md)作为历史来源保留。

### 历史G0-once的已保存配对差值

| 对比 | 有效对数 | 差值pp | 95%区间pp | 救回/损害 |
|---|---:|---:|---:|---:|
| Post_H10 − N_H10 | 500 | +7.40 | [4.40, 10.40] | 64/27 |
| Velocity_H10 − N_H10 | 500 | +6.40 | [3.00, 9.61] | 62/30 |
| Post_H10 − Velocity_H10 | 500 | +1.00 | [-1.00, 2.80] | 16/11 |
| Post_H20 − N_H20 | 500 | +16.40 | [13.00, 19.60] | 95/13 |
| Velocity_H20 − N_H20 | 500 | +15.20 | [11.99, 18.60] | 90/14 |
| Post_H30 − N_H30 | 500 | +22.20 | [18.80, 25.40] | 122/11 |
| Velocity_H30 − N_H30 | 500 | +20.80 | [17.59, 24.00] | 118/14 |
| Post_H40 − N_H40 | 500 | +19.00 | [15.80, 22.20] | 114/19 |
| Velocity_H40 − N_H40 | 500 | +18.00 | [15.00, 21.20] | 111/21 |
| Post_H50 − N_H50 | 500 | +20.80 | [17.40, 24.00] | 114/10 |
| Velocity_H50 − N_H50 | 500 | +20.00 | [16.60, 23.20] | 110/10 |
| R_H10 − N_H10 | 500 | +5.60 | [2.60, 8.60] | 54/26 |
| Post_H10 − R_H10 | 500 | +1.80 | [-0.20, 3.80] | 22/13 |
| Velocity_H10 − R_H10 | 500 | +0.80 | [-1.40, 3.00] | 20/16 |
| R_H20 − N_H20 | 500 | +14.40 | [11.20, 17.40] | 84/12 |
| R_H30 − N_H30 | 500 | +20.40 | [17.40, 23.80] | 114/12 |
| R_H40 − N_H40 | 500 | +17.00 | [13.80, 20.20] | 105/20 |
| R_H50 − N_H50 | 500 | +20.20 | [16.80, 23.60] | 112/11 |

区间直接取既有固定任务内同源配对bootstrap，数值四舍五入；不覆盖训练seed或新任务总体不确定性。差值方向均为左侧方法减右侧方法。来源：[原主表配对CSV](../sim_command/20260919/deadline_20260924/MAIN_FINAL_PAIRED_COMPARISONS.csv)、[B新增R配对](../sim_command/20260919/results/B/B_D24_R_H20_H30_V1/FINAL_PAIRED.csv)、[C新增R配对](../sim_command/20260919/results/C/C_D24_R_H40_H50_V1/r2/PAIRED_COMPARISONS.csv)。

### 历史G0-once相对R（已完成）

| H | 对比 | 有效对数 | 差值pp | 95%区间pp | 救回/损害 | 精确McNemar p |
|---:|---|---:|---:|---:|---:|---:|
| 10 | Post - R | 500 | +1.80 | [-0.20, 3.80] | 22/13 | 0.1755 |
| 10 | Velocity - R | 500 | +0.80 | [-1.40, 3.00] | 20/16 | 0.6177 |
| 20 | Post - R | 500 | +2.00 | [0.40, 3.60] | 16/6 | 0.0525 |
| 20 | Velocity - R | 500 | +0.80 | [-1.00, 2.80] | 16/12 | 0.5716 |
| 30 | Post - R | 500 | +1.80 | [-0.20, 3.80] | 19/10 | 0.1360 |
| 30 | Velocity - R | 500 | +0.40 | [-1.60, 2.40] | 15/13 | 0.8506 |
| 40 | Post - R | 500 | +2.00 | [0.20, 3.80] | 18/8 | 0.0755 |
| 40 | Velocity - R | 500 | +1.00 | [-0.80, 3.00] | 17/12 | 0.4583 |
| 50 | Post - R | 500 | +0.60 | [-1.00, 2.20] | 10/7 | 0.6291 |
| 50 | Velocity - R | 500 | -0.20 | [-2.00, 1.60] | 11/12 | 1.0000 |

这里Full指MT50的Post/Velocity完整机制，不是LIBERO Full。区间沿固定50任务内10源共同draw、2000次bootstrap、seed20260921，为逐项描述性区间；未做全论文多重比较校正。Post的H20/H40区间未含0，但对应精确McNemar p分别为0.0525/0.0755，不能把不同统计方法混称一致的显著结论。B/C补充R跨主机执行，不据耗时断言严格速度优劣。来源：[MAIN_FULL_MINUS_R_PAIRED.csv](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/MAIN_FULL_MINUS_R_PAIRED.csv)。

## 2. 外部方法对比（E3）

### 当前L01新Q：H10与既有外部方法

| 方法 | 成功/有效 | 成功率 | 范围 |
| --- | --- | --- | --- |
| N | 308/500 | 61.6% | 原N复用 |
| R-multi | 343/500 | 68.6% | 原R复用 |
| Post-multi L01/fit9101 | 350/500 | 70.0% | 本篇当前配置 |
| Velocity-multi L01/fit9101 | 340/500 | 68.0% | 另文记录 |
| VLA-Corrector | 319/500 | 63.8% | 本地实现；8条log-derived |
| GAF-v1 adapted | 315/500 | 63.0% | 适配版；原结果复用 |

| 当前配对 | 共同有效 | 差值pp | 逐项95%区间pp | 救回/损害 | 精确p（未校正） |
| --- | --- | --- | --- | --- | --- |
| Post−VLA-Corrector | 500 | +6.2 | [3.0, 9.4] | 61/30 | 0.0015165 |
| Post−GAF-v1 adapted | 500 | +7.0 | [4.0, 10.0] | 61/26 | 0.0002237 |

来源：[E3当前表](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/E3_COMPARISON.csv)、[新Q E3配对](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/E3_PAIRED.csv)。固定任务内source bootstrap2000次/seed20260921，不含训练seed不确定性；未挪用旧Q的p值或校正值。各方法训练资产/干预预算未完全匹配，只作本地实现系统比较。VLA-Corrector精确费用覆盖492/500，8条缺项仍null。

### 历史旧Q：multi与既有外部方法（原数值保留）

同π0.5/MT50/H10的原500源。本文改用已完成G0-multi；外部方法保留其原生重复干预/每次引导，不改成本文触发器，也不重跑已完成源。训练数据/覆盖不同，仍不能称严格同数据的净算法排名。

| 方法 | 成功/有效 | 成功率（%） | 来源 |
|---|---:|---:|---|
| N | 308/500 | 61.6 | 旧N复用 |
| R-multi | 343/500 | 68.6 | 已完成multi复用 |
| Post-multi | 355/500 | 71.0 | 已完成multi复用 |
| Velocity-multi | 346/500 | 69.2 | 已完成multi复用 |
| VLA-Corrector | 319/500 | 63.8 | 旧500复用，8条log-derived及费用缺项保留 |
| GAF-v1 adapted | 315/500 | 63.0 | 旧500复用，适配版/独立训练来源保留 |

| 新配对 | 计划共同源 | 差值pp | 95%区间 | 救回/损害 | 精确p/校正p |
|---|---:|---:|---|---|---|
| Post-multi − VLA-Corrector | 500 | +7.2 |  |  |  |
| Velocity-multi − VLA-Corrector | 500 | +5.4 |  |  |  |
| Post-multi − GAF | 500 | +8.0 |  |  |  |
| Velocity-multi − GAF | 500 | +6.2 |  |  |  |

这些空格仅属于历史旧Q未转录的统计；不视作尚未执行的实验。当前新Q的Post配对已列在本节首表，不搬用下方once区间与p值。

### 历史once外部对比（原结果保留）

π0.5 SFT030000＋MT50，H10，同A主表500源。VLA-Corrector保留其逐步检测与重复干预；GAF-v1 adapted每flow步引导；本文R/Post/Velocity为冻结G0、最多一次干预。各方法的既有训练数据/覆盖不同，**不是统一最终数据池训练的净算法比较**。

| 方法 | 成功/有效 | 成功率(%) | 版本及计量说明 |
|---|---:|---:|---|
| 原策略N | 308/500 | 61.60 | 主表复用 |
| 仅重规划R | 336/500 | 67.20 | 主表复用 |
| Post | 345/500 | 69.00 | 主表复用 |
| Velocity | 340/500 | 68.00 | 主表复用 |
| VLA-Corrector | 319/500 | 63.80 | 已选epoch30；8条结局由终局日志恢复，精确费用覆盖492/500 |
| GAF-v1 adapted | 315/500 | 63.00 | 15训练父源/2内部holdout，3成员共30000更新；非官方协议完整复现 |

VLA-Corrector旧8次publication failure保留，不冒称全过程零技术失败；可唯一恢复的成功结局参与500分母，缺失的调用/时间继续null。GAF最终500条无技术失败，三成员是一个ensemble，不是三次独立数据实验。

### 与VLA-Corrector的已发布配对统计

| 左侧方法 − VLA-Corrector | 对数 | 差值pp | 95%区间pp | 救回/损害 | 精确McNemar p | 四比较Holm p |
|---|---:|---:|---:|---:|---:|---:|
| N | 500 | -2.20 | [-4.20, 0.00] | 11/22 | 0.0801 | 0.1603 |
| R | 500 | +3.40 | [0.00, 6.60] | 54/37 | 0.0929 | 0.1603 |
| Post | 500 | +5.20 | [1.80, 8.20] | 62/36 | 0.0112 | 0.0447 |
| Velocity | 500 | +4.20 | [0.60, 7.60] | 60/39 | 0.0439 | 0.1316 |

区间沿原固定任务内配对bootstrap；Holm只覆盖本表四项比较，不是全论文校正。来源：[E3终局汇总](../sim_command/20260919/deadline_20260924/E3_H10_EXTERNAL_FINAL_20260922.md)、[VLA-Corrector配对CSV](../sim_command/20260919/deadline_20260924/E3_VLA_CORRECTOR_PAIRED_ANALYSIS.csv)。

### 与GAF的已发布配对统计

| GAF − 参照方法 | 对数 | 差值pp | 95%区间pp | 救回/损害 | 精确McNemar p | 四比较Holm p |
|---|---:|---:|---:|---:|---:|---:|
| GAF - N | 500 | +1.40 | [-0.20, 3.20] | 14/7 | 0.18925 | 0.18925 |
| GAF - R | 500 | -4.20 | [-7.40, -1.00] | 33/54 | 0.03142 | 0.06284 |
| GAF - Post | 500 | -6.00 | [-9.00, -2.80] | 33/63 | 0.00288 | 0.01151 |
| GAF - Velocity | 500 | -5.00 | [-8.40, -1.80] | 36/61 | 0.01439 | 0.04317 |

方向为GAF减参照，救回/损害也按GAF相对参照定义。区间为固定50任务内同源bootstrap的pointwise95%，Holm仅校正本表四个精确检验，区间本身未做同时校正；不外推为统一训练数据下的净算法优势。来源：[E3_GAF_PAIRED.csv](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E3_GAF_PAIRED.csv)。

## 3. 监督损失消融（E1）

**当前F9是完整Q从头训练后的multi消融，全部模块参与训练，1200条补充test已经完成。旧微调配置单独保留在本节末尾，不与当前表混用。**

### F9：完整Q训练、Post-only开发选型及补充test全部完成

训练已由A TRAINING_COMPLETE确认48 fits/192000更新，不重训；DEV2400有效完整，Post-only选择锁L01，test1200有效完整、技术失败0；早期DEV1546是历史快照。新TenStepCritic每成员7058参数，全部模块从配对未训练初始化训练；只复用train-only PCA/norm，固定train600、同候选资格mask/去重/source权重。四loss×fit9101/9102/9103×四成员＝48 fits，各固定4000末步，共192000更新；同(fit,member)四loss初始化/bootstrap/minibatch流配对。底座/编码器/D/G0冻结；不是旧微调权重的续训或改名。AdamW lr3e-4/wd0.01、batch32、clip1。

开发2400＝4 loss×3 fit×2分支×100：使用`E6_SOURCES.json`的development（五任务各20，env_seed2026111600..1699），与train父源/test查身份交集。H10/C10 multi沿A主表NVIDIA EGL/30Hz/.015/冻结动作桥；旧Mesa E1不混为loss效果。只按完整Post开发结果的五任务、三fit等权均值选一个共同loss，Velocity选择权重为0并继承Post选择；精确并列先辅助项少，再L00/L10/L01/L11。Post缺项不以不等分母决胜。锁定`SELECTION.json`后统一供P/V及跨底座，正式预先固定fit9101四成员；不看test选loss、阈值或fit。

| loss | Post dev成功/有效及技术缺项 | Post五任务/三fit等权成功率（V权重0） | 选择状态 |
|---|---|---|---|
| L00：BCE | 202/300；技术缺项0 | 0.6733333333333333 | 未选定 |
| L10：BCE＋gain | 203/300；技术缺项0 | 0.6766666666666666 | 未选定 |
| L01：BCE＋0.5pair | 207/300；技术缺项0 | 0.69 | 已选定，固定fit9101 |
| L11：BCE＋gain＋0.5pair | 203/300；技术缺项0 | 0.6766666666666666 | 未选定 |


### 新Q补录：完整DEV分fit结果（两分支原始记录）

| loss | 分支 | fit9101 | fit9102 | fit9103 | 合计成功/评测 | 三fit平均成功率 | 选择权重 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L00 | Post | 65/100 | 68/100 | 69/100 | 202/300 | 67.33% | 1；仅Post选型 |
| L00 | Velocity | 66/100 | 68/100 | 64/100 | 198/300 | 66.00% | 0；仅另文保留 |
| L10 | Post | 68/100 | 67/100 | 68/100 | 203/300 | 67.67% | 1；仅Post选型 |
| L10 | Velocity | 68/100 | 66/100 | 67/100 | 201/300 | 67.00% | 0；仅另文保留 |
| L01 | Post | 70/100 | 68/100 | 69/100 | 207/300 | 69.00% | 1；仅Post选型 |
| L01 | Velocity | 71/100 | 69/100 | 69/100 | 209/300 | 69.67% | 0；仅另文保留 |
| L11 | Post | 69/100 | 67/100 | 67/100 | 203/300 | 67.67% | 1；仅Post选型 |
| L11 | Velocity | 68/100 | 68/100 | 70/100 | 206/300 | 68.67% | 0；仅另文保留 |

每fit重复使用相同100个开发初态；300不是300个独立初态。Velocity不参与选型。来源为[A完整RESULT的compute_summary.cells](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json)。下方test均值±SD按三个fit的成功率计算样本标准差（ddof=1），不是置信区间；三fit共用50个test初态。

下表仅填新完整Q的1200条补充test（4 loss×3 fit×2分支×原50源），不能移填旧once或旧微调multi。开发是重复使用的开发集，原50 test已揭晓，不称新独立盲测；三fit不当成150独立初态。旧E1 multi420有效保留、未发780已取消，A自有后代退出已确认；这些结果仍属于旧微调权重。

<a id="current-multi-loss"></a>

| 损失 | 分支 | seed9101 成功/有效 | seed9102 成功/有效 | seed9103 成功/有效 | multi成功率均值±SD（%） |
|---|---|---|---|---|---|
| L00 | Post | 38/50 | 35/50 | 35/50 | 72.00±3.46 |
| L00 | Velocity | 32/50 | 32/50 | 34/50 | 65.33±2.31 |
| L10 | Post | 35/50 | 35/50 | 34/50 | 69.33±1.15 |
| L10 | Velocity | 32/50 | 34/50 | 34/50 | 66.67±2.31 |
| L01 | Post | 35/50 | 35/50 | 33/50 | 68.67±2.31 |
| L01 | Velocity | 35/50 | 35/50 | 39/50 | 72.67±4.62 |
| L11 | Post | 37/50 | 36/50 | 35/50 | 72.00±2.00 |
| L11 | Velocity | 37/50 | 36/50 | 34/50 | 71.33±3.06 |

### 历史once损失消融（完整保留）

**训练范围澄清（2026-09-22）：以下历史once组是“共同旧critic初始化、固定预处理下的四种损失微调消融”。四损失各3个fit seed×4成员，48份权重均实际执行4000次更新，共192000次；各自使用对应loss，并非只改验证配置。实际仅更新`residual`与`advantage`，其余Q参数冻结。因此它检验的是既有Q上不同微调目标的增量，不能作为整个Q从头训练的损失消融，也不能证明去掉某项损失已消除旧初始化中该项训练的影响。历史once和旧420条multi均受此限制，当前完整Q的F9不受此旧初始化限制。** 依据：[实际训练及参数范围](../sim_command/20260919/work/B/B_D24_SPRINT_V1_r1/e1_worker.py:63)、[48次训练完成记录](../sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/E1_COMPLETE_SUMMARY.json)。

三次完整拟合seed=9101/9102/9103，每次4成员ensemble，每格50个固定五任务test源。48次成员拟合、24格×50=1,200个有效episode。均值±样本SD单位为%，不是CI；三seed共用50个初态。

| 损失 | 分支 | seed 9101 成功/50 | seed 9102 成功/50 | seed 9103 成功/50 | 成功率均值±SD（%） |
|---|---|---:|---:|---:|---:|
| L00：BCE | Post | 34/50 | 34/50 | 36/50 | 69.33±2.31 |
| L00：BCE | Velocity | 32/50 | 32/50 | 30/50 | 62.67±2.31 |
| L10：BCE＋gain | Post | 36/50 | 36/50 | 35/50 | 71.33±1.15 |
| L10：BCE＋gain | Velocity | 34/50 | 33/50 | 32/50 | 66.00±2.00 |
| L01：BCE＋pair | Post | 35/50 | 36/50 | 35/50 | 70.67±1.15 |
| L01：BCE＋pair | Velocity | 32/50 | 30/50 | 33/50 | 63.33±3.06 |
| L11：BCE＋gain＋pair（Full） | Post | 36/50 | 33/50 | 34/50 | 68.67±3.06 |
| L11：BCE＋gain＋pair（Full） | Velocity | 33/50 | 32/50 | 33/50 | 65.33±1.15 |

当前Full并未在两分支上一致占优。旧1120条无效渲染结果排除并留存，最终有效表由保留80条加修正1120条组成；不与A主表跨renderer直接配对。

来源：[E1_COMPLETE_CELLS.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/D24_E1_RENDER_REPAIR_r3/E1_COMPLETE_CELLS.csv)；[E1分析](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/E1_COMPLETED_ANALYSIS_20260922.md)。

## 4. 收益/异常触发对照（E6）

### F10：multi收益/异常触发（100条及详细统计已补录）

复用dev冻结的D5阈值0.2521600950570383与原五任务ordinal10–19测试源；两臂均取消总次数帽，保留阈值/合法性/C10。旧95/100的episode报警率不等于multi机会预算匹配。

| 触发器 | 成功/有效 | 成功率% | 触发0/1/≥2 | 干预总数 / 均值 | 完整policy调用总数 / 均值 | 相对另一臂：差值/区间/救回损害 |
| --- | --- | --- | --- | --- | --- | --- |
| G0→R-multi | 26/50 | 52.0 | 4/11/35 | 240 / 4.80 | 1072 / 21.44 | −10 pp；[−22,0]；2/7 |
| D5→R-multi | 31/50 | 62.0 | 5/2/43 | 380 / 7.60 | 1001 / 20.02 | +10 pp；[0,22]；7/2 |

技术缺项0。G0−D5精确McNemar p=0.1796875，固定任务内bootstrap2000次/seed20260921，区间为逐项95%；不支持G0优势。原once D5=30/50不代填本表multi的31/50。来源：[终局逐episode与成本补录](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/master_costs_e6_addendum.json)、[既有E6配对](../sim_command/20260919/results/A/A_D24_MULTI_PRIMARY_VALIDATION_V1/PAIRED.json)。

### 历史once收益/异常触发（完整保留）

H10/C10，下游仅R，once≤1；100个固定dev用于匹配假想报警率，测试是独立五任务每任务10源（ordinal10–19），两臂各50，技术失败0。

| 指标 | 收益 G0→R | 因果异常 D5→R |
|---|---:|---:|
| 成功/有效 | 26/50 | 30/50 |
| 成功率 | 52.0% | 60.0% |
| 实际触发episode | 46/50 | 45/50 |
| 策略采样调用总数 | 973 | 884 |

| 任务（每臂10条） | G0 成功/10 | D5 成功/10 |
|---|---:|---:|
| disassemble-v3 | 7/10 | 9/10 |
| pick-place-wall-v3 | 7/10 | 8/10 |
| shelf-place-v3 | 1/10 | 2/10 |
| stick-pull-v3 | 1/10 | 1/10 |
| stick-push-v3 | 10/10 | 10/10 |

配对共同成功25、共同失败19、仅D5成功5、仅G0成功1；D5−G0=+8pp，精确双侧McNemar p=0.21875。不能声称G0优势，也不构成等效性证明。D5阈值0.2521600950570383，仅dev匹配95/100报警，未用test选阈值。

来源：[E6分析](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/E6_COMPLETED_ANALYSIS_20260922.md)；[逐任务CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_CORE_REMAINDER_V1/E6_PER_TASK_CELLS.csv)。

## 5. 跨底座与跨环境适用性（E8，含待填表）

证据快照：A论文汇总r03，2026-09-22T10:15:06.485917+00:00；已纳入C恢复的5条LIBERO N有效终局。以下成功率和配对均采用更新后的共同有效源；完整LIBERO仍以SCIENTIFIC_GAP留空。

### F8：Smol/X专属数据复用、完整Q刷新及所选Q评测

旧采集与32000更新结果保留。新完整Q两底座各16 fits/64000更新均完成；按A完整Post DEV选定L01、固定fit9101，使用自身对应四成员和预处理，Smol/X新Q P/V各1000均已完成。底座/D/G0未更新，无新增采集；Velocity只供另文。Smol原R先前243/476与24用户取消是历史中间状态，原24缺槽现已补齐，终局245/500；该补齐不计入新Q11600。X原R412/500复用。

<a id="current-f8"></a>

**F8-multi：L01/fit9101新Q P/V各500/底座全部完成，R沿原范围补齐/复用。**

| 底座 / 节点 | N复用成功/有效（%） | 专属R-multi成功/有效 | 所选新Q Post-multi成功/有效 | 所选新Q Velocity-multi成功/有效 | 状态 |
|---|---:|---:|---:|---:|---|
| SmolVLA050000 / B | 234/496（47.18%） | 245/500 | 245/500 | 240/500 | L01/fit9101终局；N四unknown保留 |
| X-VLA030000 / C | 403/500（80.60%） | 412/500 | 409/500 | 412/500 | L01/fit9101终局；旧Q另表保留 |

**F8-once：两底座专属网络旧次数协议均完成，保留历史；新Q once未在跨底座范围中另增。**

| 底座 / 节点 | N复用成功/有效（%） | 专属R-once成功/有效（%） | 专属Post-once成功/有效（%） | 专属Velocity-once成功/有效（%） |
|---|---:|---:|---:|---:|
| SmolVLA050000 / B | 234/496（47.18%） | 242/500 | 246/500 | 247/500 |
| X-VLA030000 / C | 403/500（80.60%） | 410/500 | 408/500 | 407/500 |

Smol once数值直接转录[recovery_r3终局](../sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/recovery_r3/FINAL_SUMMARY.json)，历史R multi中间状态243/476见[原续跑回执](../sim_command/20260919/receipts/B/B_D24_SMOL_MULTI_EVAL_V1_R_UNSTARTED_RESULT_r2.json)，当前245/500采用[B完整终局r2](../sim_command/20260919/receipts/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1_RESULT_r2.json)；未重算配对或统计，Smol N四个unknown保留。 X专属once直接转录[原once终局](../sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1/FINAL_SUMMARY.json)，R multi转录[原multi终局](../sim_command/20260919/results/C/C_D24_XVLA_MULTI_EVAL_V1/FINAL_SUMMARY.json)；该旧Q multi的Post404/500、Velocity408/500仅保留为历史，不填新Q格。

| 底座 | 计划train/dev父源 | 实际有效train/dev cut | 实际采集终局/技术缺失 | G0有效配对及非零收益数 | Q有效a0/±组及pair数 | D/G0/Q实际更新 | 开发指标/冻结模型 |
|---|---|---|---|---|---|---|---|
| SmolVLA | 200/50，共250 | 188/47 | 1895完整；15 normal-only父源，技术缺项另账 | 188 train；非零25 | 188绝对父源；gain364，pair182 | 32000，8成员各4000 | 固定4000末步；dev仅描述 |
| X-VLA | 200/50，共250 | 191/49 | 1930完整；10 normal-only父源，技术缺项另账 | 191 train；非零25 | 191绝对父源；gain372，pair186 | 32000，8成员各4000 | 固定4000末步；dev仅描述 |

每底座MT50每任务4 train＋1 dev；4个训练cut固定5/15/35/55，dev cut按ASCII任务序号模4选同四值。每cut比较old正常延续、fresh a0+C10、local+、local−，各2后缀重复，最多2000采集rollout；每底座采集＋1500测试共3500首次任务，另500技术失败纠正硬余量。晚cut前成功/终止不换源、不回填，无合法cut/缺repeat不造标签，因此250是计划源数，不是有效训练量。D窗口复用这些真实轨迹。

以下描述历史首轮专属D/G0/Q训练，当前F8使用随后完整Q刷新选定的L01。历史G0标签是fresh C10后native K10与old真实正常延续的终局收益差；每cut是一份fresh计划的两次后缀重复，不是旧三fresh均值。D双成员/G0双成员/Q四成员各4000更新，合计32000；Q全部7058参数/成员从头训练，L11=BCE＋gain＋0.5pair；train-only norm/PCA。外部π0.5编码器仍冻结，必须披露其成本，不能称原生Smol/X特征或只报11.9M完整附加参数。阈值0.05、D5、每5步监测、C10、300步及原动作桥保持；原已启动测试once≤1，新multi只去次数帽。沿原B/C真实80Hz/.01/renderer，不与A主表换协议混比。

#### 当前新Q：跨底座已发布配对补录

| 底座 | 对比 | 共同有效源 | 方法/参照成功数 | 救回/损害 | 差值pp | 逐项95%区间pp |
| --- | --- | --- | --- | --- | --- | --- |
| SmolVLA | Post−N | 496 | 244 / 234 | 26 / 16 | +2.02 | [−0.40,4.44] |
| SmolVLA | Velocity−N（另文） | 496 | 239 / 234 | 24 / 19 | +1.01 | [−1.41,3.43] |
| X-VLA | Post−N | 500 | 409 / 403 | 24 / 18 | +1.2 | [−1.6,4.0] |
| X-VLA | Post−R | 500 | 409 / 412 | 8 / 11 | −0.6 | [−2.0,0.8] |
| X-VLA | Velocity−N（另文） | 500 | 412 / 403 | 21 / 12 | +1.8 | [−1.2,4.8] |
| X-VLA | Velocity−R（另文） | 500 | 412 / 412 | 7 / 7 | 0.0 | [−1.0,1.0] |

来源：[Smol新Q配对](../sim_command/20260919/results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/evaluation_r1/PAIRED.json)、[X新Q配对](../sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/PAIRED.json)。Smol为固定任务内共同源bootstrap2000次，X为任务cluster bootstrap2000次，均seed20260922；方法不同不混称同一区间程序。Smol配对的244/239是共同496源内成功数，不替换全500评测的245/240；N四个unknown保留。Smol对补齐后R500以及R−N本次未新增配对统计，成功数已完整录入，不视为未完成评测。上述区间均含0，不宣称稳定跨底座增益。

原500测试源已经揭晓，本轮属于固定专属重训后的补充适配验证，不称新增盲测；所有训练/开发源与test隔离，不据test调阈值或选模型。若G0收益全零、可区分局部标签不足或实际数据缺项，报告科学缺口，不强迫触发、不以旧迁移数值填新格。新数据覆盖及新收益均不能预先保证；每节点当前波退出后独立接续，9月23日20:00北京时间停止新准入、23:00交表。详情见[专属辅助网络重训协议](../sim_command/20260919/deadline_20260924/PER_BASE_AUXILIARY_RETRAINING_V1.md)。

专属训练来源：[Smol DATA_SUMMARY](../sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/DATA_SUMMARY.json)、[Smol FIT_SUMMARY](../sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/FIT_SUMMARY.json)、[X DATA_SUMMARY](../sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1/DATA_SUMMARY.json)、[X FIT_SUMMARY](../sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1/FIT_SUMMARY.json)。训练完成不代表测试增益已成立。

### MetaWorld MT50：历史once结果（Smol/X为冻结π0.5辅助网络迁移）

| 底座 | N 成功/有效（%） | +Post 成功/有效（%） | +Velocity 成功/有效（%） | 状态 |
|---|---:|---:|---:|---|
| π0.5 SFT030000，H10 | 308/500（61.60%） | 345/500（69.00%） | 340/500（68.00%） | A主表复用，不与B/C逐源混配 |
| SmolVLA 050000 | 234/496（47.18%） | 240/500（48.00%） | 247/500（49.40%） | frozen-head transfer；N有4未知 |
| X-VLA 030000 | 403/500（80.60%） | 407/500（81.40%） | 403/500（80.60%） | frozen-head transfer；各500完成 |

SmolVLA使用50k底座、raw50/K10；X-VLA使用30k底座、raw30/K10，正常实际执行间隔均为10，不能把raw长度当作重规划间隔。上述两者接入冻结π0.5五任务特征/D/G0/Q，统一标为 **frozen-head transfer**，专属小网训练为0；旧小增益不等于已证明方法本身跨底座适用性差。X-VLA原训练记录为49个唯一任务标签。各底座均使用自身原冻结源与seed，实际B/C协议80Hz/.01与A主表不同，不跨设置逐源配对或合并统计。

### π0.5＋LIBERO：已完成算子适配版（无 D/G0）

| suite | N 成功/有效（%） | +Post算子 成功/有效（%） | +Velocity算子 成功/有效（%） |
|---|---:|---:|---:|
| libero_spatial | 98/100（98.00%） | 96/100（96.00%） | 99/100（99.00%） |
| libero_object | 100/100（100.00%） | 100/100（100.00%） | 99/100（99.00%） |
| libero_goal | 98/99（98.99%） | 100/100（100.00%） | 99/100（99.00%） |
| libero_10 | 91/100（91.00%） | 91/100（91.00%） | 90/100（90.00%） |
| all_four_suites | 387/399（96.99%） | 387/400（96.75%） | 387/400（96.75%） |

这是官方 π0.5 权重及其 normalizer、H10/K5/NFE10、command20 固定干预的算子适配结果，不是包含 D/G0 的 Full。沿用原随机 reset 与 policy seed，不能作为官方固定初态 LIBERO 榜单成绩。原生小头仅120训练候选（24父源、5负例）及40描述性验证候选（8父源、全部成功）。

### 配对比较（已发布统计直接引用）

| 设置 | 对比 | 有效对数 | 对比方法成功 / 参照成功 | 救回 / 损害 | 差值 pp | 95%描述性区间 pp |
|---|---|---:|---:|---:|---:|---:|
| SmolVLA 050000 / MT50 | Post - N | 496 | 239 / 234 | 33 / 28 | +1.01 | [-2.08, +4.10] |
| SmolVLA 050000 / MT50 | Velocity - N | 496 | 246 / 234 | 35 / 23 | +2.42 | [-0.40, +5.05] |
| SmolVLA 050000 / MT50 | Velocity - Post | 500 | 247 / 240 | 11 / 4 | +1.40 | [+0.00, +3.00] |
| X-VLA 030000 / MT50 | Post - N | 500 | 407 / 403 | 28 / 24 | +0.80 | [-2.03, +3.63] |
| X-VLA 030000 / MT50 | Velocity - N | 500 | 403 / 403 | 25 / 25 | +0.00 | [-4.60, +4.00] |
| X-VLA 030000 / MT50 | Velocity - Post | 500 | 403 / 407 | 7 / 11 | -0.80 | [-2.20, +0.40] |
| pi05 official / all_four_suites | Post - N | 399 | 386 / 387 | 5 / 6 | -0.25 | [-1.88, +1.38] |
| pi05 official / all_four_suites | Velocity - N | 399 | 386 / 387 | 5 / 6 | -0.25 | [-1.88, +1.38] |
| pi05 official / all_four_suites | Velocity - Post | 400 | 387 / 387 | 4 / 4 | +0.00 | [-1.39, +1.39] |

Post−N的 MW 比较、LIBERO 比较沿用 B 已发布的配对正态区间；MW Velocity 比较沿用 C 的任务聚类 bootstrap（2000次、seed20260922）。区间方法不同且均未做多重比较校正，不能混称同一推断方法；现有区间均含或接触0，不支持“各底座、各环境普遍改善”的结论。LIBERO 两算子总成功数相同，但逐源仍有4救回/4损害。更新后的Post/Velocity−N均为399对、386对387成功、5救回/6损害，不能将方法全400条的387成功直接填到399对的候选成功列。各suite更新后的配对和来源见[r03 E8配对CSV](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E8_PAIRED.csv)；[0,0]的无不一致配对区间不构成等效性证明。

### F1 待填：π0.5＋LIBERO 完整系统

| 方法 | Spatial 成功/有效 | Object 成功/有效 | Goal 成功/有效 | Long 成功/有效 | 总成功率 | 计划测试数 | 当前状态 |
|---|---|---|---|---|---|---:|---|
| Full-Post（D/G0＋Post） |  |  |  |  |  | 400 | A：r13 SCIENTIFIC_GAP，Full测试未进入 |
| Full-Velocity（D/G0＋Velocity） |  |  |  |  |  | 400 | A：r13 SCIENTIFIC_GAP，Full测试未进入 |

A原生方案为 D2/age2/G0 old3–fresh3后native5、C5/nativeK5、once阈值0.05、旋转不纠偏。2026-09-22 r13已结束：新增40开发attempt中30有效且成功、10技术失败；可用G0配对7train＋4validation收益均0，按预先规定停止。训练更新0、Full两分支测试0；不训练常数G0，不把30/30开发成功当测试100%，不把未测试填0%。算子结果不能代填此表。

### F2 已更新：基线缺项处理终局（未知继续保留）

| 待补项目 | 原有有效 | 已新增有效 | 剩余未有有效结果 | 后续新成功 / 新有效 | 更新后总成功 / 总有效 |
|---|---:|---:|---:|---|---|
| SmolVLA N | 496/500 | 0 | 4未知 | 0/0（无新有效，不算成功率） | 234/496 |
| LIBERO N | 394/400 | 5 | 1未知 | 5/5 | 387/399 |

C终局r1已完成5个合法LIBERO槽，5/5成功，N更新为387/399；另4个Smol和1个LIBERO槽保持未知。本节成功率和配对已按r03同步更新；394条旧快照保留在原始来源，不与新分母混用。补缺没有重跑已完成源，未知不记失败。

来源（本次仅引用保存表，没有新增统计计算或模型调用）：
- [r03 E8完整成功率表](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E8_TABLE.csv)
- [r03 E8更新配对表](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E8_PAIRED.csv)
- [E8_TABLE.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1/E8_TABLE.csv)
- [E8_PAIRED.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1/E8_PAIRED.csv)
- [COMBINED_N_INDEX.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1/COMBINED_N_INDEX.json)
- [TABLE_BUILD.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1/TABLE_BUILD.json)
- [E8_REPORT.md](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1/E8_REPORT.md)
- [B_D24_EXTENSION_REMAINDER_V1_RESULT.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/B/B_D24_EXTENSION_REMAINDER_V1_RESULT.json)
- [C_D24_MW_VELOCITY_V1_RESULT_r3.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/C/C_D24_MW_VELOCITY_V1_RESULT_r3.json)
- [A_D24_LIBERO_FULL_NATIVE_V1_RESULT_r13.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/A/A_D24_LIBERO_FULL_NATIVE_V1_RESULT_r13.json)

## 6. 参数量、调用和计时（E5）

### 当前L01/fit9101：五H multi与H10 once真实调用

| H | 分支 | 模式 | 成功/有效 | 完整policy调用总数 | 调用/episode | flow总数 | 干预总数 / 均值 | 次数0/1/≥2 | 全调用/成功数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | Post | G0-multi | 350/500 | 7037 | 14.074 | 70370 | 1011 / 2.022 | 109/164/227 | 20.106 |
| 10 | Velocity（另文） | G0-multi | 340/500 | 8326 | 16.652 | 83260 | 1052 / 2.104 | 109/157/234 | 24.488 |
| 20 | Post | G0-multi | 334/500 | 4953 | 9.906 | 49530 | 1166 / 2.332 | 93/145/262 | 14.829 |
| 20 | Velocity（另文） | G0-multi | 324/500 | 6254 | 12.508 | 62540 | 1177 / 2.354 | 93/142/265 | 19.302 |
| 30 | Post | G0-multi | 334/500 | 4231 | 8.462 | 42310 | 1251 / 2.502 | 85/142/273 | 12.668 |
| 30 | Velocity（另文） | G0-multi | 324/500 | 5637 | 11.274 | 56370 | 1281 / 2.562 | 85/142/273 | 17.398 |
| 40 | Post | G0-multi | 324/500 | 3983 | 7.966 | 39830 | 1293 / 2.586 | 85/136/279 | 12.293 |
| 40 | Velocity（另文） | G0-multi | 314/500 | 5355 | 10.710 | 53550 | 1305 / 2.610 | 85/142/273 | 17.054 |
| 50 | Post | G0-multi | 323/500 | 3639 | 7.278 | 36390 | 1275 / 2.550 | 92/130/278 | 11.266 |
| 50 | Velocity（另文） | G0-multi | 317/500 | 5077 | 10.154 | 50770 | 1314 / 2.628 | 92/129/279 | 16.016 |
| 10 | Post | G0-once | 341/500 | 6931 | 13.862 | 69310 | 391 / 0.782 | 109/391/0 | 20.326 |
| 10 | Velocity（另文） | G0-once | 336/500 | 7415 | 14.830 | 74150 | 391 / 0.782 | 109/391/0 | 22.068 |

每格500个有效episode，包含任务失败；policy_calls=sampling_calls，flow_calls=10×sampling_calls。每次Post干预采样1份新计划，Velocity干预base+guided计2次；动作梯度、D/G0/Q与编码开销另计，不能把调用减少当端到端加速。B H20按各分支原有效12＋接续488合并，排除unstarted占位。

Post H10 multi相对once：成功350对341、平均调用14.074对13.862；新增0.212次/episode，不写成multi更省调用。Post H30相对N H10：66.8%对61.6%、8.462对15.130次，调用点估少44.07%；这是跨H观测权衡，不是非劣性或低延迟保证。当前新Q计时/能耗未在此确认，不挪用下方旧Q计时。

来源：[Post逐源汇总](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/costs.json)、[Velocity及E6成本补录](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/master_costs_e6_addendum.json)。以下旧Q表及旧once成本继续留作历史。

### 历史旧Q：N与G0-multi的平均调用（新Q成本不据此推断）

以下每格仅计最终500个有效episode，包含任务失败episode，剔除历史技术中断尝试；那些技术成本仍在旧尝试账中保留。**调用/episode是全部有效episode的调用数÷500，不是只统计成功任务；全部调用/成功数是摊销成本。** 一次完整sample_actions记一次，Velocity每次干预的base＋guided记两次，不能把多个flow步当多个完整策略调用。

| H | 方法 | 成功/500 | 策略调用/有效episode | 全有效调用/成功数 | 平均干预次数 | 次数0/1/≥2 |
|---:|---|---:|---:|---:|---:|---|
| 10 | N | 308/500 | 15.130 | 24.562 | 0 | 500/0/0 |
| 10 | R-multi | 343/500 | 14.452 | 21.067 | 2.034 | 109/155/236 |
| 10 | Post-multi | 355/500 | 13.780 | 19.408 | 1.912 | 109/158/233 |
| 10 | Velocity-multi | 346/500 | 16.364 | 23.647 | 2.070 | 109/156/235 |
| 20 | N | 240/500 | 9.372 | 19.525 | 0 | 500/0/0 |
| 20 | R-multi | 324/500 | 10.158 | 15.676 | 2.412 | 93/141/266 |
| 20 | Post-multi | 339/500 | 9.798 | 14.451 | 2.340 | 93/138/269 |
| 20 | Velocity-multi | 328/500 | 12.386 | 18.881 | 2.330 | 93/139/268 |
| 30 | N | 205/500 | 6.964 | 16.985 | 0 | 500/0/0 |
| 30 | R-multi | 330/500 | 8.650 | 13.106 | 2.568 | 85/131/284 |
| 30 | Post-multi | 341/500 | 8.448 | 12.387 | 2.516 | 85/133/282 |
| 30 | Velocity-multi | 329/500 | 11.226 | 17.061 | 2.566 | 85/133/282 |
| 40 | N | 205/500 | 5.602 | 13.663 | 0 | 500/0/0 |
| 40 | R-multi | 318/500 | 8.276 | 13.013 | 2.734 | 85/135/280 |
| 40 | Post-multi | 328/500 | 7.990 | 12.180 | 2.614 | 85/134/281 |
| 40 | Velocity-multi | 316/500 | 10.718 | 16.959 | 2.612 | 85/135/280 |
| 50 | N | 196/500 | 4.312 | 11.000 | 0 | 500/0/0 |
| 50 | R-multi | 321/500 | 7.584 | 11.813 | 2.676 | 92/127/281 |
| 50 | Post-multi | 328/500 | 7.384 | 11.256 | 2.598 | 92/130/278 |
| 50 | Velocity-multi | 325/500 | 10.048 | 15.458 | 2.614 | 92/127/281 |

例如Post H10 once13.732→multi13.780次/episode；H50 once4.802→multi7.384。Velocity H10有效episode口径为16.364，F7旧尝试账的16.512含技术中断费用，不能混用。multi时间及区间未在本表转录，等待保存日志的CPU汇总，不拿旧once墙钟代替。所有调用减少的表述仍须披露D/G0/Q/外部编码器额外成本，不能等同于端到端同比加速。

来源：[multi最终有效episode成本表](../sim_command/20260919/deadline_20260924/analysis_20260922_current/trigger/TRIGGER_CELLS_AND_COSTS.csv)；N转录下方旧N行，未重新执行。

### 不随次数变化的网络参数

| 新增组件 | 成员数 | 每成员网络参数 | 全ensemble网络参数 |
|---|---:|---:|---:|
| D | 2 | 4,474,116 | 8,948,232 |
| G0 | 2 | 1,468,033 | 2,936,066 |
| Q | 4 | 7,058 | 28,232 |
| D＋G0＋Q | 8 | — | **11,912,530** |

网络参数按成员计，不包含非训练PCA/归一化buffer；buffer按保存加载副本2,851,264字节，另有共享固定投影2,097,152数据字节。π0.5共享编码器新增参数0，但计算并非免费。基础VLA唯一运行参数量NR；序列化权重元素数4,143,404,816不等于已核定运行参数量，不能据此算缩小倍数。Q的28,232不是完整系统新增参数。历史一次A4000拟合仅更新10,116参数，不是全部历史训练/部署规模。

### 历史G0-once调用与成本（保留原数值）

| 设置 | 成功/有效 | 调用/episode | 仅成功episode的平均调用 | 全部调用/成功数（摊销） | 摊销95%CI |
|---|---:|---:|---:|---:|---:|
| N_H10 | 308/500 | 15.130 | 5.860 | 24.562 | [22.469, 27.021] |
| R_H10 | 336/500 | 14.156 | 6.009 | 21.065 | [19.263, 23.125] |
| Post_H10 | 345/500 | 13.732 | 6.046 | 19.901 | [18.227, 21.915] |
| Velocity_H10 | 340/500 | 14.794 | 6.844 | 21.756 | [19.929, 24.025] |
| N_H20 | 240/500 | 9.372 | 3.275 | 19.525 | [17.968, 21.317] |
| R_H20 | 312/500 | 8.742 | 4.038 | 14.010 | NR（未估计） |
| Post_H20 | 322/500 | 8.530 | 4.112 | 13.245 | [12.193, 14.443] |
| Velocity_H20 | 316/500 | 9.484 | 4.896 | 15.006 | [13.843, 16.328] |
| N_H30 | 205/500 | 6.964 | 2.595 | 16.985 | [15.500, 18.675] |
| R_H30 | 307/500 | 6.690 | 3.550 | 10.896 | NR（未估计） |
| Post_H30 | 316/500 | 6.568 | 3.598 | 10.392 | [9.601, 11.339] |
| Velocity_H30 | 309/500 | 7.482 | 4.346 | 12.107 | [11.256, 13.150] |
| N_H40 | 205/500 | 5.602 | 2.151 | 13.663 | [12.512, 14.953] |
| R_H40 | 290/500 | 5.872 | 3.210 | 10.124 | NR（未估计） |
| Post_H40 | 300/500 | 5.758 | 3.243 | 9.597 | [8.876, 10.406] |
| Velocity_H40 | 295/500 | 6.636 | 4.031 | 11.247 | [10.430, 12.170] |
| N_H50 | 196/500 | 4.312 | 1.694 | 11.000 | [9.995, 12.172] |
| R_H50 | 297/500 | 4.844 | 2.926 | 8.155 | NR（未估计） |
| Post_H50 | 300/500 | 4.802 | 2.907 | 8.003 | [7.451, 8.677] |
| Velocity_H50 | 296/500 | 5.646 | 3.682 | 9.537 | [8.884, 10.283] |

调用/episode=全体调用÷500；成功条件均值只含该方法成功子集；摊销=全部调用（含失败）÷成功数。后两者不是同一指标。所有采样生成raw50；主链Velocity干预base+guided计2次，Post/R计1次。N的policy_calls按已进入且本批全部完成的sample_actions计数；N独立sampling_calls未记录，仍为NR，不伪填。95%区间直接复用已发布固定任务内配对bootstrap，不包含训练/新任务总体不确定性。

### 历史G0-once各H计时（秒；不是multi时间）

| 设置 | episode墙钟/episode(s) | 生成/纠偏时间/episode(s) | 生成/纠偏时间/成功条件(s) | 生成/纠偏时间/成功摊销(s) |
|---|---:|---:|---:|---:|
| N_H10 | 4.278 | 3.240 | 1.266 | 5.260 |
| R_H10 | 6.866 | 3.279 | 1.399 | 4.879 |
| Post_H10 | 6.624 | 3.177 | 1.406 | 4.604 |
| Velocity_H10 | 6.952 | 3.430 | 1.596 | 5.044 |
| N_H20 | 3.278 | 2.027 | 0.712 | 4.223 |
| R_H20 | 5.906 | 2.028 | 0.943 | 3.250 |
| Post_H20 | 5.785 | 2.006 | 0.972 | 3.115 |
| Velocity_H20 | 6.089 | 2.236 | 1.164 | 3.539 |
| N_H30 | 2.850 | 1.490 | 0.555 | 3.633 |
| R_H30 | 5.542 | 1.544 | 0.818 | 2.515 |
| Post_H30 | 5.449 | 1.533 | 0.849 | 2.425 |
| Velocity_H30 | 5.767 | 1.766 | 1.042 | 2.857 |
| N_H40 | 2.596 | 1.218 | 0.471 | 2.972 |
| R_H40 | 5.635 | 1.372 | 0.757 | 2.365 |
| Post_H40 | 5.501 | 1.362 | 0.778 | 2.270 |
| Velocity_H40 | 5.764 | 1.572 | 0.964 | 2.665 |
| N_H50 | 2.325 | 0.934 | 0.367 | 2.382 |
| R_H50 | 5.266 | 1.123 | 0.677 | 1.891 |
| Post_H50 | 5.221 | 1.129 | 0.689 | 1.882 |
| Velocity_H50 | 5.467 | 1.333 | 0.877 | 2.252 |

每格计时覆盖500/500。N生成计时含预处理/raw50生成/解码；主链生成/纠偏计时含其中Q/投影，大部分context/D/G0位于episode墙钟。episode计时不含常驻加载与job环境创建。两实现scope不同，不能相减当作净模块额外时间，也不是GPU秒。

| 干预入口 | 保存/实际入口 | 入口均值(s) | 中位数(s) | P95(s) | 最小–最大(s) |
|---|---:|---:|---:|---:|---:|
| R_H10 | 391/391 | 0.232 | 0.230 | 0.241 | 0.223–0.277 |
| Post_H10 | 391/391 | 0.246 | 0.245 | 0.255 | 0.239–0.291 |
| Velocity_H10 | 391/391 | 0.490 | 0.489 | 0.513 | 0.476–0.557 |
| Post_H20 | 407/407 | 0.248 | 0.250 | 0.256 | 0.238–0.283 |
| Velocity_H20 | 407/407 | 0.496 | 0.500 | 0.508 | 0.476–0.525 |
| Post_H30 | 415/415 | 0.247 | 0.245 | 0.258 | 0.238–0.286 |
| Velocity_H30 | 415/415 | 0.496 | 0.499 | 0.515 | 0.477–0.599 |
| Post_H40 | 415/415 | 0.250 | 0.251 | 0.257 | 0.239–0.275 |
| Velocity_H40 | 415/415 | 0.496 | 0.498 | 0.511 | 0.476–0.544 |
| Post_H50 | 408/408 | 0.248 | 0.249 | 0.255 | 0.239–0.292 |
| Velocity_H50 | 408/408 | 0.493 | 0.493 | 0.508 | 0.478–0.555 |

N没有干预入口，本表不列N。新增R_H20/30/40/50的实际干预数为407/415/415/408，但r03未重新提取逐入口时延，入口均值/P95/范围保留NR；其每episode成本和时间已加入上表。R入口为一次propose范围；P/V含base/guided采样、Q、动作梯度、投影和局部产物保存，不含入口前monitor/context。嵌套计时已包含，不能再相加。实际分母为每格真实触发入口数（H10为391），而非500请求；并发经验P95不是单机器人速度保证。净D/G0/context、净动作反向、净纠偏增量、GPU kernel秒和能耗均NR。历史主链末段有32次辅助占卡，共263.297管理进程区间秒，保留计时限制，不据墙钟作严格吞吐比较。

新增R成本与时间来源：[r03调用表](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E5_AMORTIZED_COST_TABLE.csv)、[r03计时范围](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E5_TIMING_RANGES.csv)；其摊销调用CI未估计，保留NR。B/C跨主机计时不能与A旧主链解释为受控速度比较。

来源：[E5报告](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_OURS_E5_REPORT_V1/REPORT.md)、[调用CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_OURS_E5_REPORT_V1/PAPER_COST_TABLE.csv)、[参数JSON](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_OURS_E5_REPORT_V1/PARAMETER_COUNTS.json)、[时间CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_OURS_E5_REPORT_V1/TIMING_TABLE.csv)、[入口时间CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_OURS_E5_REPORT_V1/ENTRY_TIMING_TABLE.csv)。

## 7. 一次/多次干预开发测试（历史pilot）

旧disassemble已揭晓20初态、repeat0，新once/multi各20；没有新初态，120条有效结局，技术失败0。除取消总次数帽外，触发条件与算法不变。

| 方法 | once 成功/20（%） | multi 成功/20（%） | multi−once（pp） | multi 中≥2次干预的初态数 | multi救回/损害 |
|---|---:|---:|---:|---:|---:|
| R | 13/20（65.0） | 13/20（65.0） | 0.0 | 6/20 | 0/0 |
| Post | 16/20（80.0） | 16/20（80.0） | 0.0 | 4/20 | 0/0 |
| Velocity | 15/20（75.0） | 15/20（75.0） | 0.0 | 6/20 | 0/0 |

全部配对最终成败相同；不证明其他任务重复干预无效或两模式等效。新授权全MT50五H的G0-multi结果另填F7，不能用本pilot的零差值代填。Post_multi相对R_multi为+15pp、救回5/损害2，仅作本开发集描述，不混入MT50主表。

来源：[pilot终局分析](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/PILOT_FINAL_ANALYSIS.md)；[六组CSV](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/PILOT_FINAL_RESULTS.csv)。

## 8. 历史standalone结构消融（独立口径）

历史已揭晓held100：五任务各20独立初态，每初态4配对后缀种子，因此每方法400结局但只有100个初态。98合法报警源新跑3分支共1,176物理分支，2无报警源共用原结局；N/R使用封存对照。与当前D24新test MT50表不能合并，也不能当新增独立测试。C10/nativeH10，保留各自独立半径且不调用其他分支。

| 方法 | 成功/400 | 成功率 | 相对R（pp） | 相对R三比较Bonferroni区间（98.3333%，pp） |
|---|---:|---:|---:|---:|
| 原封存 N | 168/400 | 42.00% | — | — |
| 原封存 R | 214/400 | 53.50% | 0.00 | — |
| 独立 Post | 252/400 | 63.00% | +9.50 | [2.50, 17.25] |
| 独立 Velocity | 240/400 | 60.00% | +6.50 | [1.50, 12.25] |
| 独立 Direct（历史分支） | 237/400 | 59.25% | +5.75 | [−1.25, 13.00] |

| 任务（每方法80结局） | N | R | 独立Post | 独立Velocity | 独立Direct |
|---|---:|---:|---:|---:|---:|
| disassemble-v3 | 65.00% | 61.25% | 75.00% | 76.25% | 81.25% |
| pick-place-wall-v3 | 37.50% | 72.50% | 82.50% | 73.75% | 77.50% |
| shelf-place-v3 | 20.00% | 17.50% | 28.75% | 22.50% | 21.25% |
| stick-pull-v3 | 8.75% | 21.25% | 28.75% | 27.50% | 26.25% |
| stick-push-v3 | 78.75% | 95.00% | 100.00% | 100.00% | 90.00% |

| 历史独立入口 | 每次干预VLA采样数 | 入口均值(s) | 中位数(s) | P95(s) |
|---|---:|---:|---:|---:|
| Post | 1 | 0.637 | 0.484 | 1.229 |
| Velocity | 2 | 0.904 | 0.887 | 1.152 |
| Direct | 2 | 0.920 | 0.919 | 1.199 |

98报警源入口计时含各自a0、纠偏、诊断评分/检查，不含加载/恢复/后缀仿真；8GPU×4worker并发且Post调用顺序固定较早，有冷入口影响，不是等条件预热测速。当前D24入口计时另表保留，不能直接混合平均。部署分支独立不等于训练候选数据也完全独立；Direct仅历史补充，无需再补D24实验。

来源：[standalone报告](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/docs/STANDALONE_CORRECTOR_ABLATION_20260918.md)。

## 9. 剩余结果的补充空表

F1（完整LIBERO成功率）与F2（已更新的基线缺项）位于第5节。F3/F4保留科学缺口与用户真实场景，F5记录已完成的R扩展，F6/F7记录已完成的触发实验，F8（第5节）记录专属辅助网络重训；只填实际终局数据，不使用算子版或旧pilot数值顶替。

### F3 待填：完整LIBERO的配对效果与过程成本

| 方法 | N配对有效数 | 方法/N配对成功 | 救回/损害 | 差值pp | 95%区间pp | 真正G0触发数 | policy调用/episode | 全部policy调用/成功数 | 已记录推理时间范围及值 |
|---|---:|---|---|---:|---|---:|---:|---:|---|
| Full-Post，原生D2/G0/C5 |  |  |  |  |  |  |  |  |  |
| Full-Velocity，原生D2/G0/C5 |  |  |  |  |  |  |  |  |  |

| 原生完整系统模块 | 成员数 | 网络参数总数 | 实际更新数 | train/validation父源数 | 数据/模型选择说明 |
|---|---:|---:|---:|---|---|
| LIBERO D2 |  |  |  |  |  |
| LIBERO G0（old3/fresh3目标） |  |  |  |  |  |
| LIBERO Q（L11真实目标） |  |  |  |  |  |
| 完整新增模块合计 |  |  |  |  |  |

若监督不足/没有合法触发，记录“未完成/适配受限”，不能用已完成的BCE算子头冒充L11完整系统；也不能把工程启动失败填成0%任务成功率。只有A原生分支确实完成后，才更新第5节F1和本节F3。

### F4 待填：用户负责的一组真实场景验证

| 场景 | 底座/版本 | 实际部署分支 | 有效任务数 | 成功数 | 成功率 | 调用/episode | 已记录推理时间及范围 | 采集日期/备注 |
|---|---|---|---:|---:|---:|---:|---|---|
| 用户计划的一组真实场景 |  |  |  |  |  |  |  |  |

本表不预设试验数量，不要求真实场景的其他方法对比；由用户提供实际记录后填充。

### F5 已完成：新增R H扫描

B完成H20/30，C完成H40/50；四格各500，共2000条有效终局，技术失败/未知均0。新增独立初态为0；模型、原500源和种子、NVIDIA EGL及30Hz/400Hz/.015协议沿A主表，未使用历史Mesa路线。

| H | 执行端 | 有效回合 | 成功/有效 | 技术失败/未知 | R−N（pp） | Post−R（pp） | Velocity−R（pp） | 实际调用/episode | 逐入口耗时范围 |
|---:|---|---:|---|---|---:|---:|---:|---:|---|
| 20 | B | 500 | 312/500 | 0/0 | +14.4 | +2.0 | +0.8 | 8.742 | NR（r03未提取） |
| 30 | B | 500 | 307/500 | 0/0 | +20.4 | +1.8 | +0.4 | 6.690 | NR（r03未提取） |
| 40 | C | 500 | 290/500 | 0/0 | +17.0 | +2.0 | +1.0 | 5.872 | NR（r03未提取） |
| 50 | C | 500 | 297/500 | 0/0 | +20.2 | +0.6 | -0.2 | 4.844 | NR（r03未提取） |

第1节已同步成功率和配对区间，第6节已同步成本及已有时间。来源：[MAIN_20CELL_TABLE.csv](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/MAIN_20CELL_TABLE.csv)、[MAIN_FULL_MINUS_R_PAIRED.csv](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/MAIN_FULL_MINUS_R_PAIRED.csv)、[E5_AMORTIZED_COST_TABLE.csv](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E5_AMORTIZED_COST_TABLE.csv)。跨主机耗时单列，不声称严格速度优劣。

### F6 已完成：随机时机Random-once（15格）

F6/F7是查看原主表后提出、复用已揭晓500源的补充评测；新增模式和随机表在本次评测前固定，不称新的独立未揭晓测试集或预注册验证。

五H×R/Post/Velocity×原500源，共7500有效终局。原50任务各10源、ordinal0..9全部保留，不选G0触发子集；独立初态仍为500。R归C、Post归B、Velocity归A，每格500。既有G0-once对照复用第1节，新成功、配对与已保存调用成本转录自各节点终局。

每个(source,H)运行前从预定潜在合法槽均匀抽取一次时点，三分支共用冻结随机表，独立于轨迹、G0、成功与自然策略RNG。t表示已执行的控制步数；只替换G0>0.05这一选时机条件，其余合法性、C10和恢复同H规则不变。若提前成功/终止或到时不合法，不强制干预、不顺延、不补抽，记录原因并保留全500计划源；技术失败/未知单列，不能填成任务失败。

| H | 分支 | 执行端 | 有效回合 | G0-once成功/500（%） | Random-once成功/有效 | 相对G0-once差值pp | 95%区间pp | 救回/损害 | 新模式触发0/1/≥2 | 已记录调用/有效源† | 已记录调用/成功数† |
|---:|---|---|---:|---:|---|---:|---|---|---|---:|---:|
| 10 | R | C | 500 | 336/500（67.2） | 307/500（61.4%） | -5.80 | [-9.00, -2.60] | 28/57 | 250/250/0 | 15.632 | 25.459 |
| 10 | Post | B | 500 | 345/500（69.0） | 311/500（62.2%） | -6.80 | [-10.00, -3.60] | 31/65 | 250/250/0 | 15.638 | 25.141 |
| 10 | Velocity | A | 500 | 340/500（68.0） | 308/500（61.6%） | -6.40 | [-9.80, -3.20] | 31/63 | 250/250/0 | 16.138 | 26.198 |
| 20 | R | C | 500 | 312/500（62.4） | 242/500（48.4%） | -14.00 | [-17.20, -11.00] | 13/83 | 191/309/0 | 10.144 | 20.959 |
| 20 | Post | B | 500 | 322/500（64.4） | 248/500（49.6%） | -14.80 | [-18.00, -11.60] | 16/90 | 191/309/0 | 10.054 | 20.270 |
| 20 | Velocity | A | 500 | 316/500（63.2） | 245/500（49.0%） | -14.20 | [-17.60, -11.00] | 17/88 | 191/309/0 | 10.724 | 21.886 |
| 30 | R | C | 500 | 307/500（61.4） | 210/500（42.0%） | -19.40 | [-22.60, -16.40] | 12/109 | 159/341/0 | 7.944 | 18.914 |
| 30 | Post | B | 500 | 316/500（63.2） | 210/500（42.0%） | -21.20 | [-24.40, -18.00] | 12/118 | 159/341/0 | 7.934 | 18.890 |
| 30 | Velocity | A | 500 | 309/500（61.8） | 209/500（41.8%） | -20.00 | [-23.21, -16.80] | 13/113 | 159/341/0 | 8.710 | 20.837 |
| 40 | R | C | 500 | 290/500（58.0） | 211/500（42.2%） | -15.80 | [-19.40, -12.40] | 23/102 | 163/337/0 | 6.326 | 14.991 |
| 40 | Post | B | 500 | 300/500（60.0） | 208/500（41.6%） | -18.40 | [-22.00, -15.00] | 22/114 | 163/337/0 | 6.332 | 15.221 |
| 40 | Velocity | A | 500 | 295/500（59.0） | 208/500（41.6%） | -17.40 | [-20.80, -14.20] | 21/108 | 163/337/0 | 7.022 | 16.880 |
| 50 | R | C | 500 | 297/500（59.4） | 196/500（39.2%） | -20.20 | [-23.60, -16.60] | 12/113 | 155/345/0 | 5.508 | 14.051 |
| 50 | Post | B | 500 | 300/500（60.0） | 196/500（39.2%） | -20.80 | [-24.20, -17.40] | 10/114 | 155/345/0 | 5.488 | 14.000 |
| 50 | Velocity | A | 500 | 296/500（59.2） | 195/500（39.0%） | -20.20 | [-23.60, -16.80] | 10/111 | 155/345/0 | 6.196 | 15.887 |

Random-once与G0-once只共享“最多一次”上限，实际触发率可能不同；主比较是完整在线触发策略的效果，不是严格等实际次数下的纯timing因果效应。共同实际触发子集只能另作描述，不能替代全源主结果。

统一配对检验已汇总到[触发比较统计表](../sim_command/20260919/deadline_20260924/analysis_20260922_current/trigger/PAIRED_TIMING_MULTIPLICITY_WITH_HOLM.csv)：本次以保存的救回/损害数计算双侧精确McNemar，并分别对Random−once和multi−once的15项比较做Holm校正。Random的15项均支持G0-once；multi的10项通过（H30/40/50三分支，以及Post H20）。下列/上列表中的95%区间仍是原pointwise区间，未改称同时置信区间；不把是否通过校正与效果等效混淆。统一500有效episode的调用口径另见[费用表](../sim_command/20260919/deadline_20260924/analysis_20260922_current/trigger/TRIGGER_CELLS_AND_COSTS.csv)，它与包含历史失败费用的执行端总账分列。

### F7 已完成：收益G0-multi（15格）

五H×R/Post/Velocity×原500源，共7500有效终局；源、分工和对照与F6相同。仅删除总次数条件`intervention_count < 1`，不加新次数帽、冷却、强制报警或不同阈值。每5步检查、严格G0>0.05、历史与队列合法性、C10期间不重入、丢尾后恢复该H、300步预算和提前终止均保持不变。保存first_cut、last_cut及完整cut序列，不能把multi压成一次。旧20源pilot不是本表结果。

| H | 分支 | 执行端 | 有效回合 | G0-once成功/500（%） | G0-multi成功/有效 | 相对G0-once差值pp | 95%区间pp | 救回/损害 | 新模式触发0/1/≥2 | 已记录调用/有效源† | 已记录调用/成功数† |
|---:|---|---|---:|---:|---|---:|---|---|---|---:|---:|
| 10 | R | C | 500 | 336/500（67.2） | 343/500（68.6%） | +1.40 | [0.20, 2.80] | 10/3 | 109/155/236 | 14.452 | 21.067 |
| 10 | Post | B | 500 | 345/500（69.0） | 355/500（71.0%） | +2.00 | [0.60, 3.60] | 13/3 | 109/158/233 | 13.780 | 19.408 |
| 10 | Velocity | A | 500 | 340/500（68.0） | 346/500（69.2%） | +1.20 | [-0.40, 2.80] | 12/6 | 109/156/235 | 16.512 | 23.861 |
| 20 | R | C | 500 | 312/500（62.4） | 324/500（64.8%） | +2.40 | [0.40, 4.40] | 21/9 | 93/141/266 | 10.158 | 15.676 |
| 20 | Post | B | 500 | 322/500（64.4） | 339/500（67.8%） | +3.40 | [1.60, 5.40] | 24/7 | 93/138/269 | 9.798 | 14.451 |
| 20 | Velocity | A | 500 | 316/500（63.2） | 328/500（65.6%） | +2.40 | [0.40, 4.40] | 21/9 | 93/139/268 | 12.386 | 18.881 |
| 30 | R | C | 500 | 307/500（61.4） | 330/500（66.0%） | +4.60 | [2.60, 6.60] | 27/4 | 85/131/284 | 8.650 | 13.106 |
| 30 | Post | B | 500 | 316/500（63.2） | 341/500（68.2%） | +5.00 | [2.80, 7.20] | 32/7 | 85/133/282 | 8.448 | 12.387 |
| 30 | Velocity | A | 500 | 309/500（61.8） | 329/500（65.8%） | +4.00 | [2.20, 6.00] | 27/7 | 85/133/282 | 11.226 | 17.061 |
| 40 | R | C | 500 | 290/500（58.0） | 318/500（63.6%） | +5.60 | [3.40, 7.80] | 34/6 | 85/135/280 | 8.276 | 13.013 |
| 40 | Post | B | 500 | 300/500（60.0） | 328/500（65.6%） | +5.60 | [3.60, 7.80] | 33/5 | 85/134/281 | 7.990 | 12.180 |
| 40 | Velocity | A | 500 | 295/500（59.0） | 316/500（63.2%） | +4.20 | [2.20, 6.40] | 29/8 | 85/135/280 | 10.718 | 16.959 |
| 50 | R | C | 500 | 297/500（59.4） | 321/500（64.2%） | +4.80 | [2.60, 7.00] | 32/8 | 92/127/281 | 7.584 | 11.813 |
| 50 | Post | B | 500 | 300/500（60.0） | 328/500（65.6%） | +5.60 | [3.40, 7.80] | 35/7 | 92/130/278 | 7.384 | 11.256 |
| 50 | Velocity | A | 500 | 296/500（59.2） | 325/500（65.0%） | +5.80 | [3.80, 8.00] | 35/6 | 92/127/281 | 10.048 | 15.458 |

F6/F7合计30格、15000有效回合；加上原20格，已完成50格、25000个有效回合，仍仅500个共享初态。A/B/C各5000有效终局，未解决缺项均0；历史技术失败A16、B9、C0保留，不把修复后的全覆盖写成全过程无技术失败。上述已完成波没有Random-multi；原新增7500计划已取消，见F11。旧波固定H顺序和两模式顺序保持，未按成绩调整。

† 两列调用按各节点已发布episode计数转录：已记录调用÷500有效源、已记录调用÷成功数。A/B保留已记录失败/纠正尝试费用，因此它们不是只保留最终成功运行的理想部署成本；未记录的失败阶段费用不补造。完整资源、尝试范围、触发次数分布与时间范围见各终局包。Random的shadow D/G0费用保留，不作为随机策略最小部署成本；并发时长及跨主机墙钟不据此作严格速度比较。G0-multi每episode平均触发次数R 2.034–2.734、Post 1.912–2.614、Velocity 2.070–2.614；multi收益与新增调用同时解释，不能称免费改善。

主要比较分别为Random-once−G0-once和G0-multi−G0-once，每组15个预定对比；使用全部共同有效源，不排除无触发/早终止。沿固定50任务内同源bootstrap 2000次、seed20260921给pointwise95%区间；若报告显著性，精确McNemar分别在两组各15比较内做Holm，不称全论文已校正。同模式Post−R/Velocity−R直接复用这些结果，不增加episode。

来源与冻结协议：[触发时机及次数安排](../sim_command/20260919/deadline_20260924/TRIGGER_TIMING_AND_MULTIPLICITY_V1.md)、[授权](../sim_command/20260919/deadline_20260924/TRIGGER_TIMING_MULTIPLICITY_AUTHORIZATION_V1.json)、[显式500源表](../sim_command/20260919/deadline_20260924/TRIGGER_MODE_SOURCES_V1.json)、[预抽随机时刻表](../sim_command/20260919/deadline_20260924/RANDOM_ONCE_SCHEDULE_V1.json)。底座/normalizer/D/G0/Q、raw50、NFE10、C10、300步、NVIDIA EGL及物理协议保持冻结，无新增训练/开发采集。终局来源：[A Velocity r5回执](../sim_command/20260919/receipts/A/A_D24_VELOCITY_TRIGGER_MODES_V1_RESULT_r5.json)、[B Post终局回执](../sim_command/20260919/receipts/B/B_D24_POST_TRIGGER_MODES_V1_RESULT.json)、[C R终局回执](../sim_command/20260919/receipts/C/C_D24_R_TRIGGER_MODES_V1_RESULT.json)。表中点估计和pointwise区间直接转录，各15项比较的统一检验由分析汇总，不能凭逐项区间预写整体显著性。旧20格和其他实验原始证据均不覆盖。

### F11 已取消：Random-multi（不再实验）

用户2026-09-22取消原五H×R/Post/Velocity×500＝7500计划，不再保留待填科学数值表，不将未用额度转回随机实验。已完成Random-once的F6及旧Q G0-multi的F7全部保留；A旧链已实际退出、Random-multi进入0/取消7500，真实处置见顶部回执。

## 10. 更新规则与责任

| 待填表 | 负责方 | 允许填充的证据 | 同时需要更新 |
|---|---|---|---|
| F1/F3 完整LIBERO | A执行端，分析端汇总 | 新Full分支终局、真实D/G0/L11配置与原生时距、逐源结果及缺失原因 | 状态索引、成功/有效数、配对、调用和计时范围 |
| F2 基线缺项 | C执行端，分析端汇总 | 缺项处置及可恢复终局/合法接续结果、COMBINED_N_INDEX | E8 N分母及所有受影响配对比较，旧原始记录保留 |
| F5 R_H20/30/40/50 | B/C已完成，分析端汇总 | r03完整终局及原500源配对CSV | 主表/Full−R/成本已更新；缺失逐入口计时仍NR |
| F6 Random-once（完成） | A Velocity / B Post / C R，分析端汇总 | 每格完整500源覆盖、随机表引用、终局及配对/成本CSV | 状态索引、新成功/有效、早终止/不合法原因、差值区间与调用 |
| F7 G0-multi（完成） | A Velocity / B Post / C R，分析端汇总 | 每格终局、完整cut列表及真实次数/调用，非旧pilot | 状态索引、相对once配对、触发分布及新增成本 |
| F8 专属完整Q刷新 | B Smol / C X，分析端汇总 | 各16 fits/64000更新候选、A选择及新P/V各500终局；R沿旧任务 | 新旧Q分开、共同有效N/R配对、触发/成本；旧once/迁移保留 |
| F9 完整Q开发/损失消融 | A | 新48 fits、dev2400、锁定SELECTION及test1200真实终局 | chosen_loss、固定fit9101、新三fit表；不覆盖旧微调结果 |
| F10 multi触发对照 | A | 原阈值/原两臂50源的新multi终局 | 触发次数、终局和成本 |
| F11 Random-multi（取消） | 分析记录 | 用户取消决定及各端实际ACK | 不再收集新科学终局；保留Random-once |
| F4 真机 | 用户，分析端整理 | 实际场景、部署配置和逐次成败/成本记录 | 有效分母、日期、失败原因及适用范围 |

1. 每次先核对新的终局回执属于哪个source/method单元；仅排队、模型ready或运行快照不能填最终成功率。正常缺项处理不重新启动完成实验。
2. 只替换本文对应表的空格或已明确更新的数据行；记录更新时间与来源。不得按计划数量填实际n，不对unknown填失败或0成本。
3. 配对结果始终使用共同有效源；某个N缺项补齐后，同时更新配对n、救回/损害和区间。无新统计时保留旧统计并明确旧子集，不能只换分母。
4. 原始回执/旧有效表/技术失败保留不覆盖。本文件只是论文汇总，不替代原始记录或扩大实验授权。
5. F6/F7只用原ordinal0..9全500计划源；不按G0是否触发或Random是否到达抽签时刻筛选，不强迫早终止episode干预。multi仅去次数帽，旧once对照直接复用；触发率/次数不同须与成功和成本并列解释。
6. 每个新cell以(mode,branch,H,source)区分，原50任务内整源配对；跨模式及节点的相同初态不是新增独立样本。逐格终局更新，不用部分成功率填完整格，不因通知重发重跑。
7. 现有数据不支持“所有消融项必然更差”“收益触发稳定优于异常”“跨底座/环境普遍改善”或“整体比VLA微调更高效”，不要在填写表格时预写这些结论。

源表与待填项索引见 [EXPERIMENT_RESULTS_MASTER_INDEX.json](../sim_command/20260919/deadline_20260924/EXPERIMENT_RESULTS_MASTER_INDEX.json)。

## 11. 本次更新记录

- 2026-09-23T01:54:01.371871+00:00：按论文逻辑恢复总表排序，移除临时置顶重复表；新增EXPERIMENT_FOR_PAPER.md，将正文、附录及证据限制分开。L11切换仅处于用户讨论中，当前已运行结果仍为L01，未重标数据或启动实验。
- 2026-09-23T01:33:09.431132+00:00：将已填齐的当前multi损失消融与F8置顶，并添加稳定跳转；旧待续快照移入历史档案，明确区分旧微调与当前完整Q。没有新增科学计算或改动原终局。
- 2026-09-23T01:27:03.348026+00:00：补录新Q Post五H配对、H10同版本次数配对、当前E3；补齐P/V DEV分fit、test均值±样本SD、Smol/X现成配对、E6 multi次数/成本和P/V新Q十二格调用。科学终局数未变，未新增训练/评测；LIBERO本次不处理，所有原始记录与旧Q表保留。
- 2026-09-23 00:50 UTC：直接回填本轮11600有效终局与L01/fit9101选择、五H主表、H10 once、完整Q test1200及Smol/X新Q。B原R24槽另账补齐；B初次发布失败保留。未新算paired/区间/成本；LIBERO Full、真机和旧N五未知未冒称完成。

- 2026-09-22 16:48 UTC：落实Post-only开发择loss、固定fit9101，Velocity继续执行但另文；确认80 fits/320000更新完成，A DEV1546有效/854待续及技术失败0；登记A/B/C自动分工，11600范围不变。新增Post论文与Velocity另文入口，保留历史统计。

- 2026-09-22最新修订：取消Random-multi；新完整Q开发统一选loss，合计11600首次评测/320000更新。旧L11主表改历史/当前参考，新Q数值留空；24 worker为目标并发，容量限制须实报。仅更新计划/表格，未声称新训练启动；A旧链退出已有回执，B/C停止ACK仍待确认。

| 日期 | 更新内容 |
|---|---|
| 2026-09-22 | 首次汇总主表、E1/E6、E3、E8算子/跨底座、E5、pilot及standalone；完整LIBERO、基线缺项新终局、真机均预留空表。没有新增科学运行。 |
| 2026-09-22（新增R） | 用户要求补齐四个H的R，已分配B20/30、C40/50；新增F5空表，原16格保留。 |
| 2026-09-22（r03终局） | 合并20格/10000有效结果，R四格312/307/290/297；补Full−R、GAF配对、R成本及LIBERO N387/399和新共同子集配对。仅转录已发布表。 |
| 2026-09-22（新触发实验） | 新增F6 Random-once与F7 G0-multi各15格空表，A Velocity/B Post/C R各5000，合计15000计划回合；只填旧G0-once对照，新科学数值留空。 |
| 2026-09-22（专属辅助网络重训） | 用户要求Smol/X分别采集策略数据并重训D/G0/Q；旧结果标为frozen-head transfer，新增F8训练覆盖及R/Post/Velocity空表，N复用。B Smol/C X各250父源、最多2000采集＋1500新测试；未产生新科学结果。 |
| 2026-09-22（触发30格终局） | 转录A r5/B/C终局，F6/F7全部填齐；共50格25000有效回合，保留A16/B9历史技术失败及调用计量限制。B Smol/C X专属采集均8 worker已启动，新训练效果待填。 |

## 12. 历史数字与主表的口径提醒

| 数字 | 实际范围 | 不能作的比较 |
|---|---|---|
| 旧N 42.0%（168/400） | 五任务100初态×4配对后缀，Mesa旧协议 | 不能当成全MT50主表基线 |
| 当前N 56.0%（28/50） | 当前主表抽回相同五个任务名，新初态/随机流/NVIDIA | 与旧42%的差异仍有多项因素，不能只归因任务数 |
| 当前N 61.6%（308/500） | 全MT50，50任务各10源，执行H10 | 不与旧42%作配对增益 |
| pilot Post80.0%（16/20） | 仅disassemble旧20源；once与multi均80% | 不是MT50成绩，也不是取消一次帽新增的收益 |
| 当前Post69.0%（345/500） | 全MT50；其中disassemble为10/10 | 不解释成同一实验从80%下降 |
| 文献π0.5 H10基线64.50% | VLA-Corrector Table4 | 48.70/48.72%不是它的H10数值；协议仍非完全对齐 |

完整50任务名单、相同/不同协议与原文出处见[历史口径核查](RESULT_PROTOCOL_CONSISTENCY_20260922.md)。目前保存结果的算术与分母可相互核对，但不据此宣称实现绝无问题。

当前本轮11600首次评测与320000完整Q训练更新均已完成；所选L01/fit9101新Q与旧Q分开保存。LIBERO Full仍有监督缺口，真机仍待用户记录，旧N五未知保留；当前已保存配对及调用详见第1/3/4/5/6节；缺失计时等仍NR，不能标为所有论文事项完成。


## 历史进度档案

两份旧“待续/待填”执行快照已移到[历史进度档案](archive/EXPERIMENT_RESULTS_MASTER_OLD_PENDING_SNAPSHOTS_20260923.md)。它们不代表当前状态；当前multi损失消融与F8均在本文顶部和各自正式章节完整列出。


<a id="crossbase-h-sweep-20260923"></a>
## 新增：SmolVLA / X-VLA 多次触发H扫描（2026-09-23）

本次核对时间 13:49 UTC；只新增H，L11/fit9101、各底座专属D/G0/Q、原500测试源、C10与合法触发条件冻结。每格计划50任务×10源；H10全部复用，不混入以下新增24格计数。已完整格每格500有效终局，未完整格成功率留空。

| Node | Backbone | H | N SR (%) | R-multi SR (%) | Post-multi SR (%) | Velocity-multi SR (%) | Status |
|---|---|---:|---:|---:|---:|---:|---|
| A | SmolVLA | 20 | 45.2 | 49.2 | 50.2 | 49.0 | 完整 |
| A | SmolVLA | 30 | 41.0 | 46.8 | 47.6 |  | Velocity未完整 |
| B | SmolVLA | 40 | 38.2 | 44.4 | 44.6 |  | Velocity未完整 |
| B | SmolVLA | 50 | 33.8 | 45.2 | 45.6 |  | Velocity未完整 |
| C | X-VLA | 20 | 77.6 | 78.6 | 79.6 | 79.8 | 完整 |
| C | X-VLA | 30 | 77.0 | 78.8 | 77.0 | 77.6 | 完整 |

A首轮保留381次技术失败，Post未进入、Velocity部分单位失败；同一既定范围的私有修复恢复了Post并继续Velocity，已有效终局不重跑。B首轮保留384次技术失败及55个Velocity有效终局，其成本总账含技术尝试，不能直接除以有效数当正式平均采样；后续修复仅接续未完成单位。C八格全部完成、4000个新有效单元、技术缺项0，正式进程族退出后恢复8卡holder。不得将早终止而较易完成的Velocity分片高成功率当完整格结果。

来源：[A有效合并表](../sim_command/20260919/results/A/A_D24_CROSSBASE_H_SWEEP_V1_RECOVERY_r2/COMBINED_CELLS.csv)、[B首轮格表](../sim_command/20260919/results/B/B_D24_CROSSBASE_H_SWEEP_V1/FINAL_CELLS.csv)、[C终局格表](../sim_command/20260919/results/C/C_D24_CROSSBASE_H_SWEEP_V1/FINAL_CELLS.csv)。本轮完整快照和历史失败/缺项另见[核查快照](../sim_command/20260919/deadline_20260924/CROSSBASE_H_SWEEP_V1/analysis/20260923T134924Z/SCIENTIFIC_STATUS.json)。后续快照以新增或显式更新方式记录，不覆盖原执行回执。
