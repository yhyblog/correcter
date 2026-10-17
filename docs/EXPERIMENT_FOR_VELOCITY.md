# EXPERIMENTS_FOR_VELOCITY：Velocity 实验数据汇总

整理时间：2026-09-23T08:41:36.119815+00:00。用途：ICASSP论文写作资料；用户给定稿件形式为IEEE双栏、4页正文、无附录。

**本文件只整理、迁移已有Velocity数据，由用户自行筛选。** 不推荐正文取表、不划分正文/附录、不按成绩选择版本或删除结果，也不启动实验。当前L11、历史L01、旧固定Q、旧残差微调、旧共同半径、算子适配及工程诊断分开保存。N/R、Post、Direct和外部方法仅在原比较所需处保留为参照。

数值迁移自[实验总表](EXPERIMENT_RESULTS_MASTER.md)、[旧Velocity档案](VELOCITY_RESULTS_OTHER_WORK.md)及各表链接的保存终局。旧文件和原数据保留；本文件集中保存汇总表及原始逐episode数据入口，不将数万条逐episode记录或运行日志逐行嵌入Markdown。四页限制属于最终稿件，不限制这份资料集的完整度。

数据目录：

- [1. 数据版本与字段说明](#velocity-data-01)
- [2. 当前 L11 / fit9101 的八格结果](#velocity-data-02)
- [3. 当前 L11 的保存成本原值与覆盖](#velocity-data-03)
- [4. 当前 L11：H10 once/multi 已保存配对](#velocity-data-04)
- [5. 既有 N/R 五H参考数据](#velocity-data-05)
- [6. H10外部方法参考数据](#velocity-data-06)
- [7. Smol/X既有参考基线](#velocity-data-07)
- [8. 当前结果的原始来源及版本隔离](#velocity-data-08)
- [9. 完整Q四损失：Velocity开发结果与补充multi结果](#velocity-data-09)
- [10. 历史残差Q损失消融：once完整与multi部分完成](#velocity-data-10)
- [11. 历史完整Q L01 / fit9101：MT50及跨底座结果](#velocity-data-11)
- [12. 历史旧固定Q：MT50 once与multi H扫描](#velocity-data-12)
- [13. 历史旧固定Q：Random-once和不限次数G0-multi补充](#velocity-data-13)
- [14. 历史Smol/X：直接迁移、专属训练与各版本](#velocity-data-14)
- [15. 历史外部比较及已保存配对](#velocity-data-15)
- [16. 共用触发器E6数据：下游仅R，不是Velocity评测](#velocity-data-16)
- [17. 历史LIBERO记录：算子完成，Full未测试](#velocity-data-17)
- [18. 历史旧Q成本与计时（按原测量范围）](#velocity-data-18)
- [19. 共用参数规模及缓冲区记录](#velocity-data-19)
- [20. 历史20初态pilot](#velocity-data-20)
- [21. 历史standalone：共同半径与独立Velocity](#velocity-data-21)
- [22. A10有限工程数值记录（不是任务成功率）](#velocity-data-22)
- [23. L11首次无效尝试及恢复关系（原状态保留）](#velocity-data-23)
- [24. 无结果和未生成统计字段登记](#velocity-data-24)
- [25. 原始数据入口与更新口径](#velocity-data-25)

<a id="velocity-data-01"></a>
## 1. 数据版本与字段说明

| 记录版本 | 数据身份 | 本文件处理 |
|---|---|---|
| 完整Q L11 / fit9101 | 最后实际执行配置；π0.5、Smol、X共8格Velocity结果 | 保存终局和成本，不重新选loss或fit |
| 完整Q L01 / fit9101 | 此前Post开发选型后实际执行的版本 | 单独保存，不改名为L11 |
| 完整Q四损失消融 | Q全部参数从配对未训练初始化训练；三fit | 保存全部候选，Velocity没有参与原共同选型 |
| 旧残差Q消融 | 共同旧critic初始化，仅residual/advantage更新 | 与完整Q区分；包含未跑完即取消的multi记录 |
| 旧固定Q D24 | 原once、Random-once、multi及外部比较 | 保存全部原模式与配对统计 |
| 专属Smol/X与frozen-head transfer | 专属数据训练和直接迁移是不同阶段 | 分表保留 |
| 历史standalone | held100×4后缀，含共同半径/独立半径 | 与MT50的500源分开 |
| LIBERO算子/Full | 已完成固定时刻算子；Full测试未进入 | 原结果与未完成状态均保留，无新运行 |
| 工程预检及无效尝试 | 数值诊断、强制干预、渲染异常和恢复记录 | 保留原状态，不当任务成功率样本 |

- 成功/有效按实际合法终局计，技术失败或未知不自动记任务失败。`NR`表示未记录/未生成；空白未测值不填0。
- H是正常执行/重规划间隔；C是干预动作承诺长度。raw计划长度与H不同。once最多一次；multi仅移除总干预次数帽，保留原合法性及触发条件。
- 一次完整VLA采样计一次policy调用；Velocity一次纠偏有base与guided两次采样，flow步不是完整采样。成本的有效episode口径、成功条件口径和全尝试摊销口径分开。
- 三fit复用同一批初态，ensemble成员不是独立实验；不同H也复用初态。配对方向、区间方法和校正家族沿原统计，不换成新的定义。
- L11为用户在已揭晓消融之后指定、固定fit9101的实际版本。Velocity继承Post配置，不把L11写成由Velocity独立选出的最佳损失。H10复用的50源参与过选择。

<a id="velocity-data-02"></a>
## 2. 当前 L11 / fit9101 的八格结果

本节只搬运现有终局，不筛选论文展示内容、不新增统计、不启动实验。L11=BCE＋gain＋0.5pair，fit9101，四成员1041–1044；Velocity继承Post所选配置。π0.5 H10 multi 的50条消融源已经揭晓、参与最终L11选择，并与主500源重叠；该格复用这50条并接续其余450条，不能改称新盲测。Smol/X使用各自底座专属L11四成员及预处理。

[旧Velocity档案](VELOCITY_RESULTS_OTHER_WORK.md)顶部的八格成功数、有效数、采样／flow／干预均值与[FINAL_ROLLUP.json](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json)一致：每格500，合计4,000个Velocity科学单元，技术缺项0。模型／模式／H区分cell，重复协议的同一source不是新的独立初态。

| 底座 | 模式 | H/K | 成功/有效 | 成功率% | 完整采样/episode | flow/episode | 干预/episode |
|---|---|---:|---:|---:|---:|---:|---:|
| π0.5 | G0-multi | 10 | 344/500 | 68.8 | 16.432 | 164.32 | 2.008 |
| π0.5 | G0-multi | 20 | 328/500 | 65.6 | 12.722 | 127.22 | 2.496 |
| π0.5 | G0-multi | 30 | 330/500 | 66.0 | 11.234 | 112.34 | 2.568 |
| π0.5 | G0-multi | 40 | 318/500 | 63.6 | 10.796 | 107.96 | 2.664 |
| π0.5 | G0-multi | 50 | 320/500 | 64.0 | 10.042 | 100.42 | 2.602 |
| π0.5 | G0-once | 10 | 334/500 | 66.8 | 14.934 | 149.34 | 0.782 |
| SmolVLA050000 | G0-multi | 10 | 247/500 | 49.4 | 23.394 | 233.94 | 2.764 |
| X-VLA030000 | G0-multi | 10 | 407/500 | 81.4 | 16.630 | 166.30 | 3.002 |

π0.5为冻结SFT030000、raw50/NFE10、C10；五H使用相同50任务×10固定源。Smol为raw50/nativeK10；X为raw30/nativeK10。Smol/X原管线为Mesa80Hz/.01，π0.5主线为NVIDIA EGL30Hz/.015；不同底座的数值不要解释为统一仿真协议下的底座排名。

<a id="velocity-data-03"></a>
## 3. 当前 L11 的保存成本原值与覆盖

| 底座 | 模式 | H/K | 采样合计 | flow合计 | 干预合计 | 原已记录动作梯度合计／覆盖 | 原汇总elapsed秒/episode |
|---|---|---:|---:|---:|---:|---|---:|
| π0.5 | G0-multi | 10 | 8,216 | 82,160 | 1,004 | 3,012／完整500源cell合计† | 119.57885875343531 |
| π0.5 | G0-multi | 20 | 6,361 | 63,610 | 1,248 | 3,744／500/500 | 88.3090119650578 |
| π0.5 | G0-multi | 30 | 5,617 | 56,170 | 1,284 | 3,852／500/500 | 87.47900174256368 |
| π0.5 | G0-multi | 40 | 5,398 | 53,980 | 1,332 | 3,996／500/500 | 99.63611731375381 |
| π0.5 | G0-multi | 50 | 5,021 | 50,210 | 1,301 | 3,903／500/500 | 102.83912261132151 |
| π0.5 | G0-once | 10 | 7,467 | 74,670 | 391 | 1,173／完整500源cell合计† | 100.34235096081719 |
| SmolVLA050000 | G0-multi | 10 | 11,697 | 116,970 | 1,382 | 4,146／389/500 | 130.21085957650607 |
| X-VLA030000 | G0-multi | 10 | 8,315 | 83,150 | 1,501 | 4,503／398/500 | 144.4439818657674 |

来源为[最终逐格CSV](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_CELLS.csv)及[汇总JSON](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json)的Velocity行。采样、flow、干预、elapsed均覆盖各500/500。每episode均值包含所有有效任务成功和任务失败终局，不按成功条件过滤；终局之外的原技术尝试成本、模型载入与占卡成本不在此有效episode表中。

† A的[EPISODES.csv](../sim_command/20260919/results/A/A_D24_L11_RENDER_RECOVERY_V1/EPISODES.csv)未导出动作梯度列，所以normalized rollup的H10梯度known_count=0、observed_sum=0、mean=null。**这里的observed_sum=0不能解释成真实零梯度。** [A RESULT.json的compute_summary.cells](../sim_command/20260919/results/A/A_D24_L11_RENDER_RECOVERY_V1/RESULT.json)直接保存 `L11_Velocity_G0-multi_H10.action_gradients=3012` 和 `L11_Velocity_G0-once_H10.action_gradients=1173`，均为完整500源cell合计；本表搬运原计量，不用干预数乘3补造。逐episode梯度仍缺字段。

Smol389/500、X398/500是normalized CSV有明确动作梯度字段的episode覆盖；这里仅搬运已记录合计，不把未导出字段填0，不从干预数推算余下episode。π0.5 H20–H50原已发布梯度均值依次7.488、7.704、7.992、7.806，覆盖均为500/500。

elapsed是执行端原保存的episode时长；节点、恢复批次及并发条件不同，不能作为统一纯推理延迟、GPU kernel耗时、wave墙钟或速度排名。独立辅助网络、编码和动作梯度不包含在完整策略调用数中。

<a id="velocity-data-04"></a>
## 4. 当前 L11：H10 once/multi 已保存配对

| 分支 | 配对源 | once成功 | multi成功 | multi救回 | multi损害 | 原已发布点差pp |
|---|---:|---:|---:|---:|---:|---:|
| Velocity L11 / fit9101 | 500 | 334 | 344 | 14 | 4 | +2.0 |

直接转录[FINAL_ROLLUP.json 的 H10_multi_once_paired.Velocity](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json)。不新增CI、p值或显著性判断，不混用旧Q/L01的配对统计。

<a id="velocity-data-05"></a>
## 5. 既有 N/R 五H参考数据

以下是不依赖Q的既有基线，沿原版本复用；没有为了当前Velocity重跑基线。此表只搬运基线，不进行新的差值或配对计算。

| H | N成功/有效 | N成功率% | N完整调用/episode | R-multi成功/有效 | R成功率% | R完整调用/episode |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 308/500 | 61.6 | 15.130 | 343/500 | 68.6 | 14.452 |
| 20 | 240/500 | 48.0 | 9.372 | 324/500 | 64.8 | 10.158 |
| 30 | 205/500 | 41.0 | 6.964 | 330/500 | 66.0 | 8.650 |
| 40 | 205/500 | 41.0 | 5.602 | 318/500 | 63.6 | 8.276 |
| 50 | 196/500 | 39.2 | 4.312 | 321/500 | 64.2 | 7.584 |

基线来源：[N/R来源索引](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/main_pairs.json)、[调用既有汇总的N_reused_cells/R_multi_reused_cells](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/costs.json)。这两份旧文件同时包含L01 Post分析；此处只搬运N/R字段。

N调用原独立 `sampling_calls_total` 字段未记录，为null；表中“完整调用”沿其 `policy_calls` 定义，不能把缺独立字段说成零调用。原N policy总数依次7565/4686/3482/2801/2156，flow总数75650/46860/34820/28010/21560。R-multi policy总数依次7226/5079/4325/4138/3792。

<a id="velocity-data-06"></a>
## 6. H10外部方法参考数据

| 方法／版本 | 成功/有效 | 成功率% | 原计量或实现备注 |
|---|---:|---:|---|
| N | 308/500 | 61.6 | 原生H10 |
| R-multi | 343/500 | 68.6 | 仅收益触发重规划 |
| L11 Velocity-multi | 344/500 | 68.8 | 当前Velocity，引用上表 |
| VLA-Corrector本地实现 | 319/500 | 63.8 | 8条终局由原日志恢复，精确成本仅492/500 |
| GAF-v1 adapted | 315/500 | 63.0 | 15train/2内部holdout，3成员各10,000更新 |

引用：[原E3_COMPARISON.csv](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/E3_COMPARISON.csv)、[各外部方法实现口径](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/component_notes.md)、当前L11终局。比较使用同π0.5 SFT030000、MT50原500源，但外部方法各自的训练资产、机制和干预预算没有完全匹配；这里只原样归档这些参考结果，不产生统一算法排名。

<a id="velocity-data-07"></a>
## 7. Smol/X既有参考基线

| 底座 | 原N成功/有效 | 原N成功率% | 专属R-multi成功/有效 | R成功率% | 当前L11 Velocity-multi成功/有效 | Velocity成功率% |
|---|---:|---:|---:|---:|---:|---:|
| SmolVLA050000 | 234/496 | 47.18 | 245/500 | 49.0 | 247/500 | 49.4 |
| X-VLA030000 | 403/500 | 80.6 | 412/500 | 82.4 | 407/500 | 81.4 |

来源：[总表F8](EXPERIMENT_RESULTS_MASTER.md#current-f8)。Smol原N另4条unknown，不能算科学失败或将全500的Velocity成功数当成共同496的成功数；这里只并列原计数，没有计算新的配对统计。专属数据计划各200train＋50dev父源，Smol有效cut188/47，X有效cut191/49；D/G0/Q首轮各32,000更新，完整Q四loss四成员刷新各64,000更新。均非直接迁移π0.5辅助权重；Smol/X仍使用额外冻结π0.5特征提供者。

<a id="velocity-data-08"></a>
## 8. 当前结果的原始来源及版本隔离

| 当前Velocity cell | 原结果入口 | 迁移／复用关系 |
|---|---|---|
| π0.5 H10 multi/once | [A恢复EPISODES.csv](../sim_command/20260919/results/A/A_D24_L11_RENDER_RECOVERY_V1/EPISODES.csv)；[RESULT](../sim_command/20260919/results/A/A_D24_L11_RENDER_RECOVERY_V1/RESULT.json) | multi复用原50＋恢复450；once500；旧无效尝试保留 |
| π0.5 H20、SmolH10 multi | [B原有效合并CSV](../sim_command/20260919/results/B/B_D24_L11_RETEST_V1/recovery_queue/merged/EPISODES.csv) | 原B有效终局，含预episode构造失败后仅未进入单元接续 |
| π0.5 H30 multi | [B恢复CSV](../sim_command/20260919/results/B/B_D24_L11_RENDER_RECOVERY_V1/FINAL_EPISODES.csv) | 接手A旧不合格H30结果后独立恢复 |
| π0.5 H40/H50、XH10 multi | [C有效保留与恢复CSV](../sim_command/20260919/results/C/C_D24_L11_RENDER_RECOVERY_V1/EPISODES.csv) | π0.5修复；X Velocity原500有效全保留 |
| 汇总后的全部Velocity逐episode | [总汇总FINAL_EPISODES.csv，method=Velocity](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_EPISODES.csv) | 8格×500；保留source_table和result_path |

A初次共享EGL路径偏差的旧2900原始结果与C旧π0.5/X失败等都保留原账；当前有效结果不覆盖或洗白旧尝试。旧Velocity档案后续的L01、旧固定Q、旧专属Q、迁移Q与完整Q消融为不同版本，不能合并或改名为L11。

<a id="velocity-data-09"></a>
## 9. 完整Q四损失：Velocity开发结果与补充multi结果

π0.5四loss×三个fit×四成员＝48份完整Q成员训练，每份4000更新、共192000更新。全部Q参数参与训练；底座、D/G0、编码、train-only PCA/归一化冻结。AdamW lr3e−4、weight decay0.01、batch32、clip1。同(fit,member)跨loss初始化/bootstrap/minibatch流配对。开发为五任务各20个源；补充评测为五任务各10个已揭晓源。

### 完整Q开发集（全部Velocity候选）

| loss | 分支 | fit9101 | fit9102 | fit9103 | 合计成功/评测 | 三fit平均成功率 | 选择权重 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L00 | Velocity | 66/100 | 68/100 | 64/100 | 198/300 | 66.00% | 0；仅另文保留 |
| L10 | Velocity | 68/100 | 66/100 | 67/100 | 201/300 | 67.00% | 0；仅另文保留 |
| L01 | Velocity | 71/100 | 69/100 | 69/100 | 209/300 | 69.67% | 0；仅另文保留 |
| L11 | Velocity | 68/100 | 68/100 | 70/100 | 206/300 | 68.67% | 0；仅另文保留 |

每fit共100源，三fit复用原100源；300是评测条数。原Post-only开发选择产生L01，随后用户依据已揭晓Post补充消融指定L11；两段选择历史保留，Velocity选择权重均为0。

### 完整Q补充multi评测（全部Velocity候选）

| 损失 | 分支 | seed9101 成功/有效 | seed9102 成功/有效 | seed9103 成功/有效 | multi成功率均值±SD（%） |
| --- | --- | --- | --- | --- | --- |
| L00 | Velocity | 32/50 | 32/50 | 34/50 | 65.33±2.31 |
| L10 | Velocity | 32/50 | 34/50 | 34/50 | 66.67±2.31 |
| L01 | Velocity | 35/50 | 35/50 | 39/50 | 72.67±4.62 |
| L11 | Velocity | 37/50 | 36/50 | 34/50 | 71.33±3.06 |

每fit50源；均值±SD沿原三fit成功率的样本SD（ddof=1），不是置信区间。三fit150条不是150独立初态。来源：[完整Q训练/开发/补充评测终局](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json)、[全部分支逐episode（筛method=Velocity）](../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/TECHNICAL_EPISODES_ALL_METHODS.csv)。

<a id="velocity-data-10"></a>
## 10. 历史残差Q损失消融：once完整与multi部分完成

该阶段共同旧critic初始化，只更新residual和advantage，状态/锚点编码与基线头等其余Q参数冻结。四loss×三个fit×四成员均实际训练4000更新，48成员共192000更新。这组与后来完整Q训练不同，不互相替代。

### once：每格50源，12个Velocity单元均完成

| 损失 | 分支 | seed 9101 成功/50 | seed 9102 成功/50 | seed 9103 成功/50 | 成功率均值±SD（%） |
| --- | --- | ---: | ---: | ---: | ---: |
| L00：BCE | Velocity | 32/50 | 32/50 | 30/50 | 62.67±2.31 |
| L10：BCE＋gain | Velocity | 34/50 | 33/50 | 32/50 | 66.00±2.00 |
| L01：BCE＋pair | Velocity | 32/50 | 30/50 | 33/50 | 63.33±3.06 |
| L11：BCE＋gain＋pair（Full） | Velocity | 33/50 | 32/50 | 33/50 | 65.33±1.15 |

原双分支24格1200有效。旧1120条无效渲染保留，最终表由保留80＋修正1120组成；这1200和1120是双分支总量。来源：[E1最终格表](../sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/D24_E1_RENDER_REPAIR_r3/E1_COMPLETE_CELLS.csv)、[E1记录说明](../sim_command/20260919/deadline_20260924/E1_COMPLETED_ANALYSIS_20260922.md)。

### multi：用户取消前已完成的Velocity记录

| loss | fit | 成功/有效 | 计划数 | 未启动后取消 | 平均干预次数（原存值） |
| --- | --- | --- | --- | --- | --- |
| L00 | 9101 | 17/20 | 50 | 30 | 2.05 |
| L00 | 9102 | 17/20 | 50 | 30 | 1.35 |
| L00 | 9103 | 16/20 | 50 | 30 | 1.45 |
| L10 | 9101 | 15/15 | 50 | 35 | 1.3333333333333333 |
| L10 | 9102 | 14/15 | 50 | 35 | 1.3333333333333333 |
| L10 | 9103 | 15/15 | 50 | 35 | 1.2666666666666666 |
| L01 | 9101 | 17/20 | 50 | 30 | 1.4 |
| L01 | 9102 | 16/20 | 50 | 30 | 1.9 |
| L01 | 9103 | 17/20 | 50 | 30 | 1.6 |
| L11 | 9101 | 14/15 | 50 | 35 | 1.5333333333333334 |
| L11 | 9102 | 14/15 | 50 | 35 | 1.7333333333333334 |
| L11 | 9103 | 15/15 | 50 | 35 | 1.2 |

Velocity共210有效、390未启动取消；含Post的原E1共420有效、780取消。不同loss当前分母20或15，不把这些部分结果补成50。该波为Mesa路径、旧残差微调权重。来源：[原summary.cells](../sim_command/20260919/results/A/A_D24_MULTI_PRIMARY_VALIDATION_V1/RESULT.json)、[取消及保留记录](../sim_command/20260919/receipts/A/A_D24_MULTI_PRIMARY_VALIDATION_V1_Q_LOSS_OVERRIDE_RESULT_r2.json)。

<a id="velocity-data-11"></a>
## 11. 历史完整Q L01 / fit9101：MT50及跨底座结果

这是完整Q训练后、原Post开发选定L01的实际已完成版本。保持原权重身份和结果，不用L11改名。

### π0.5五H及H10 once

| H | chosen_loss / 权重来源 | 新Q Velocity-multi成功/有效 | 新Q Velocity-once成功/有效 |
| --- | --- | --- | --- |
| 10 | L01 / A fit9101四成员 | 340/500 | 336/500 |
| 20 | L01 / A fit9101四成员，B执行 | 324/500 | 不规划 |
| 30 | L01 / A fit9101四成员，B执行 | 324/500 | 不规划 |
| 40 | L01 / A fit9101四成员，C执行 | 314/500 | 不规划 |
| 50 | L01 / A fit9101四成员，C执行 | 317/500 | 不规划 |

| 分支 | multi / once成功 | 有效对数 | 差值pp | 95%区间pp | 救回/损害 | 精确p |
| --- | --- | --- | --- | --- | --- | --- |
| Velocity（另文） | 340/500 / 336/500 | 500 | +0.8（描述差值） | NR：本次未生成配对区间 | NR | NR |

### Smol/X专属L01

| 底座 / 节点 | N复用成功/有效（%） | 专属R-multi成功/有效 | 所选新Q Velocity-multi成功/有效 | 状态 |
| --- | ---: | ---: | ---: | --- |
| SmolVLA050000 / B | 234/496（47.18%） | 245/500 | 240/500 | L01/fit9101终局；N四unknown保留 |
| X-VLA030000 / C | 403/500（80.60%） | 412/500 | 412/500 | L01/fit9101终局；旧Q另表保留 |

### 专属L01已保存配对

| 底座 | 对比 | 共同有效源 | 方法/参照成功数 | 救回/损害 | 差值pp | 逐项95%区间pp |
| --- | --- | --- | --- | --- | --- | --- |
| SmolVLA | Velocity−N（另文） | 496 | 239 / 234 | 24 / 19 | +1.01 | [−1.41,3.43] |
| X-VLA | Velocity−N（另文） | 500 | 412 / 403 | 21 / 12 | +1.8 | [−1.2,4.8] |
| X-VLA | Velocity−R（另文） | 500 | 412 / 412 | 7 / 7 | 0.0 | [−1.0,1.0] |

Smol配对仅共同496源，239成功不替代全500源240成功。Smol区间：固定任务内bootstrap2000次；X区间：任务cluster bootstrap2000次；均seed20260922。来源：[Smol L01配对](../sim_command/20260919/results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/evaluation_r1/PAIRED.json)、[X L01配对](../sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/PAIRED.json)。H20/H30来源：[B L01终局](../sim_command/20260919/receipts/B/B_D24_PI05_SELECTED_H20_H30_V1_RESULT_r2.json)；H40/H50：[C L01终局](../sim_command/20260919/results/C/C_D24_PI05_SELECTED_H40_H50_V1/FINAL_SUMMARY.json)。

### L01五H multi与H10 once调用

| H | 分支 | 模式 | 成功/有效 | 完整policy调用总数 | 调用/episode | flow总数 | 干预总数 / 均值 | 次数0/1/≥2 | 全调用/成功数 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | Velocity（另文） | G0-multi | 340/500 | 8326 | 16.652 | 83260 | 1052 / 2.104 | 109/157/234 | 24.488 |
| 20 | Velocity（另文） | G0-multi | 324/500 | 6254 | 12.508 | 62540 | 1177 / 2.354 | 93/142/265 | 19.302 |
| 30 | Velocity（另文） | G0-multi | 324/500 | 5637 | 11.274 | 56370 | 1281 / 2.562 | 85/142/273 | 17.398 |
| 40 | Velocity（另文） | G0-multi | 314/500 | 5355 | 10.710 | 53550 | 1305 / 2.610 | 85/142/273 | 17.054 |
| 50 | Velocity（另文） | G0-multi | 317/500 | 5077 | 10.154 | 50770 | 1314 / 2.628 | 92/129/279 | 16.016 |
| 10 | Velocity（另文） | G0-once | 336/500 | 7415 | 14.830 | 74150 | 391 / 0.782 | 109/391/0 | 22.068 |

各格500有效，含成功与任务失败。策略调用总数不含额外D/G0/Q/编码与动作梯度计算。来源：[保存Velocity成本补录](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/master_costs_e6_addendum.json)。

<a id="velocity-data-12"></a>
## 12. 历史旧固定Q：MT50 once与multi H扫描

π0.5 SFT030000，raw50/NFE10、C10，50任务×10源。D/G0/Q为历史五任务资产；G0>0.05、每5步监测、合法队列与C10期间禁止重入。multi去除总次数帽，最大300控制步与成功提前终止不变。各模式、五H共用原500源。

### G0-once

| H | N 成功/500（%） | R 成功/500（%） | Velocity 成功/500（%） | Velocity−N（pp） |
| --- | ---: | ---: | ---: | ---: |
| 10 | 308/500（61.6） | 336/500（67.2） | 340/500（68.0） | +6.4 |
| 20 | 240/500（48.0） | 312/500（62.4） | 316/500（63.2） | +15.2 |
| 30 | 205/500（41.0） | 307/500（61.4） | 309/500（61.8） | +20.8 |
| 40 | 205/500（41.0） | 290/500（58.0） | 295/500（59.0） | +18.0 |
| 50 | 196/500（39.2） | 297/500（59.4） | 296/500（59.2） | +20.0 |

### G0-multi

| H | N 成功/500（%） | R-multi 成功/500（%） | Velocity-multi 成功/500（%） | Velocity−R（pp） |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 308/500（61.6） | 343/500（68.6） | 346/500（69.2） | +0.6 |
| 20 | 240/500（48.0） | 324/500（64.8） | 328/500（65.6） | +0.8 |
| 30 | 205/500（41.0） | 330/500（66.0） | 329/500（65.8） | -0.2 |
| 40 | 205/500（41.0） | 318/500（63.6） | 316/500（63.2） | -0.4 |
| 50 | 196/500（39.2） | 321/500（64.2） | 325/500（65.0） | +0.8 |

來源：[原20格once结果](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/MAIN_20CELL_TABLE.csv)、[旧multi有效episode成功及成本](../sim_command/20260919/deadline_20260924/analysis_20260922_current/trigger/TRIGGER_CELLS_AND_COSTS.csv)。

### 旧once相对R的原配对

| H | 对比 | 有效对数 | 差值pp | 95%区间pp | 救回/损害 | 精确McNemar p |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 10 | Velocity - R | 500 | +0.80 | [-1.40, 3.00] | 20/16 | 0.6177 |
| 20 | Velocity - R | 500 | +0.80 | [-1.00, 2.80] | 16/12 | 0.5716 |
| 30 | Velocity - R | 500 | +0.40 | [-1.60, 2.40] | 15/13 | 0.8506 |
| 40 | Velocity - R | 500 | +1.00 | [-0.80, 3.00] | 17/12 | 0.4583 |
| 50 | Velocity - R | 500 | -0.20 | [-2.00, 1.60] | 11/12 | 1.0000 |

区间为固定50任务内10源共同draw、2000次bootstrap、seed20260921；逐项95%，原p未做全论文校正。来源：[MAIN_FULL_MINUS_R_PAIRED.csv](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/MAIN_FULL_MINUS_R_PAIRED.csv)。

### 旧once保存的其余Velocity相关配对（保留原方向）

| 原比较 | 类别 | 对数 | 差值pp | 原95%区间pp | 救回/损害 | 共同成功/共同失败 | 正/负/零任务 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Velocity_H10-N_H10 | within_H | 500 | 6.4 | [3.0, 9.605] | 62/30 | 278/130 | 19/8/23 |
| Post_H10-Velocity_H10 | within_H | 500 | 1.0 | [-1.0, 2.8] | 16/11 | 329/144 | 8/5/37 |
| Velocity_H20-N_H20 | within_H | 500 | 15.2 | [11.995, 18.6] | 90/14 | 226/170 | 27/1/22 |
| Post_H20-Velocity_H20 | within_H | 500 | 1.2 | [-0.4, 2.6] | 11/5 | 311/173 | 6/3/41 |
| Velocity_H30-N_H30 | within_H | 500 | 20.8 | [17.595, 24.0] | 118/14 | 191/177 | 30/2/18 |
| Post_H30-Velocity_H30 | within_H | 500 | 1.4 | [-0.2, 3.0] | 13/6 | 303/178 | 9/4/37 |
| Velocity_H40-N_H40 | within_H | 500 | 18.0 | [15.0, 21.2] | 111/21 | 184/184 | 24/6/20 |
| Post_H40-Velocity_H40 | within_H | 500 | 1.0 | [-0.6, 2.6] | 12/7 | 288/193 | 8/6/36 |
| Velocity_H50-N_H50 | within_H | 500 | 20.0 | [16.6, 23.2] | 110/10 | 186/194 | 26/2/22 |
| Post_H50-Velocity_H50 | within_H | 500 | 0.8 | [-0.8, 2.4] | 11/7 | 289/193 | 6/5/39 |
| Velocity_H10-R_H10 | H10_R_reference | 500 | 0.8 | [-1.4, 3.0] | 20/16 | 320/144 | 10/9/31 |
| Velocity_H20-N_H10 | cross_H_descriptive | 500 | 1.6 | [-2.2, 5.2] | 59/51 | 257/133 | 13/13/24 |
| Velocity_H30-N_H10 | cross_H_descriptive | 500 | 0.2 | [-3.6, 3.6] | 53/52 | 256/139 | 12/16/22 |
| Velocity_H40-N_H10 | cross_H_descriptive | 500 | -2.6 | [-6.4, 0.8] | 51/64 | 244/141 | 13/17/20 |
| Velocity_H50-N_H10 | cross_H_descriptive | 500 | -2.4 | [-6.2, 1.2] | 50/62 | 246/142 | 11/18/21 |

上表包含Post−Velocity及跨H比较，方向沿原文件，没有反转救回/损害。区间原精度保留；它们均属于旧once，不能移填L11。来源：[MAIN_FINAL_PAIRED_COMPARISONS.csv](../sim_command/20260919/deadline_20260924/MAIN_FINAL_PAIRED_COMPARISONS.csv)。

<a id="velocity-data-13"></a>
## 13. 历史旧固定Q：Random-once和不限次数G0-multi补充

原500源已揭晓后提出的补充评测；模式/随机时刻表在补充运行前固定。Random-once只替换选时机条件，其他合法性/C10不变；若预定时刻前终局或时刻不合法，不强制触发、不重抽。实际触发率与G0-once可以不同。

### Random-once与旧G0-once

| H | 分支 | 执行端 | 有效回合 | G0-once成功/500（%） | Random-once成功/有效 | 相对G0-once差值pp | 95%区间pp | 救回/损害 | 新模式触发0/1/≥2 | 已记录调用/有效源† | 已记录调用/成功数† |
| ---: | --- | --- | ---: | ---: | --- | ---: | --- | --- | --- | ---: | ---: |
| 10 | Velocity | A | 500 | 340/500（68.0） | 308/500（61.6%） | -6.40 | [-9.80, -3.20] | 31/63 | 250/250/0 | 16.138 | 26.198 |
| 20 | Velocity | A | 500 | 316/500（63.2） | 245/500（49.0%） | -14.20 | [-17.60, -11.00] | 17/88 | 191/309/0 | 10.724 | 21.886 |
| 30 | Velocity | A | 500 | 309/500（61.8） | 209/500（41.8%） | -20.00 | [-23.21, -16.80] | 13/113 | 159/341/0 | 8.710 | 20.837 |
| 40 | Velocity | A | 500 | 295/500（59.0） | 208/500（41.6%） | -17.40 | [-20.80, -14.20] | 21/108 | 163/337/0 | 7.022 | 16.880 |
| 50 | Velocity | A | 500 | 296/500（59.2） | 195/500（39.0%） | -20.20 | [-23.60, -16.80] | 10/111 | 155/345/0 | 6.196 | 15.887 |

### G0-multi与旧G0-once

| H | 分支 | 执行端 | 有效回合 | G0-once成功/500（%） | G0-multi成功/有效 | 相对G0-once差值pp | 95%区间pp | 救回/损害 | 新模式触发0/1/≥2 | 已记录调用/有效源† | 已记录调用/成功数† |
| ---: | --- | --- | ---: | ---: | --- | ---: | --- | --- | --- | ---: | ---: |
| 10 | Velocity | A | 500 | 340/500（68.0） | 346/500（69.2%） | +1.20 | [-0.40, 2.80] | 12/6 | 109/156/235 | 16.512 | 23.861 |
| 20 | Velocity | A | 500 | 316/500（63.2） | 328/500（65.6%） | +2.40 | [0.40, 4.40] | 21/9 | 93/139/268 | 12.386 | 18.881 |
| 30 | Velocity | A | 500 | 309/500（61.8） | 329/500（65.8%） | +4.00 | [2.20, 6.00] | 27/7 | 85/133/282 | 11.226 | 17.061 |
| 40 | Velocity | A | 500 | 295/500（59.0） | 316/500（63.2%） | +4.20 | [2.20, 6.40] | 29/8 | 85/135/280 | 10.718 | 16.959 |
| 50 | Velocity | A | 500 | 296/500（59.2） | 325/500（65.0%） | +5.80 | [3.80, 8.00] | 35/6 | 92/127/281 | 10.048 | 15.458 |

† 上面“已记录调用”沿原尝试总账范围；旧multi H10为16.512/有效源，包含已记录技术尝试费用。只取最终有效episode的同版本H10为16.364，见后续成本表。这是计量范围差别。其余缺失失败阶段成本不补造；Random shadow D/G0费用沿原记录。原三分支两模式总计15000有效，历史技术失败A16/B9/C0保留；这些是全波记录，不混作当前L11数据。

### 保存的精确检验与Holm校正（只迁移Velocity行）

| 比较 | H | 左/右成功 | 对数 | 救回/损害 | 精确McNemar p | 原15比较Holm p |
| --- | --- | --- | --- | --- | --- | --- |
| Random-once - G0-once | 10 | 308/340 | 500 | 31/63 | 0.0012613865981312992 | 0.0025227731962625985 |
| Random-once - G0-once | 20 | 245/316 | 500 | 17/88 | 9.952845271763166e-13 | 3.981138108705266e-12 |
| Random-once - G0-once | 30 | 209/309 | 500 | 13/113 | 4.524471384904378e-21 | 4.9769185233948155e-20 |
| Random-once - G0-once | 40 | 208/295 | 500 | 21/108 | 2.667293660294376e-15 | 2.1338349282355006e-14 |
| Random-once - G0-once | 50 | 195/296 | 500 | 10/111 | 1.044129126315013e-22 | 1.357367864209517e-21 |
| G0-multi - G0-once | 10 | 346/340 | 500 | 12/6 | 0.237884521484375 | 0.237884521484375 |
| G0-multi - G0-once | 20 | 328/316 | 500 | 21/9 | 0.04277394525706768 | 0.17109578102827072 |
| G0-multi - G0-once | 30 | 329/309 | 500 | 27/7 | 0.0008213953115046024 | 0.006023176480084658 |
| G0-multi - G0-once | 40 | 316/295 | 500 | 29/8 | 0.0007528970600105822 | 0.006023176480084658 |
| G0-multi - G0-once | 50 | 325/296 | 500 | 35/6 | 4.873598300036974e-06 | 6.823037620051764e-05 |

原Holm家族分别为Random−once、multi−once，各包含三分支×五H共15项；迁移Velocity行后不重算成5项家族。原CI为任务内bootstrap2000/seed20260921的pointwise95%。来源：[保存的校正表](../sim_command/20260919/deadline_20260924/analysis_20260922_current/trigger/PAIRED_TIMING_MULTIPLICITY_WITH_HOLM.csv)、[Velocity触发模式终局](../sim_command/20260919/receipts/A/A_D24_VELOCITY_TRIGGER_MODES_V1_RESULT_r5.json)、[原随机时刻表](../sim_command/20260919/deadline_20260924/RANDOM_ONCE_SCHEDULE_V1.json)。Random-multi已取消，实际结果不存在。

<a id="velocity-data-14"></a>
## 14. 历史Smol/X：直接迁移、专属训练与各版本

### 冻结π0.5辅助网络直接迁移（once）

| 底座 | N 成功/有效（%） | +Velocity 成功/有效（%） | 状态 |
| --- | ---: | ---: | --- |
| π0.5 SFT030000，H10 | 308/500（61.60%） | 340/500（68.00%） | A主表复用，不与B/C逐源混配 |
| SmolVLA 050000 | 234/496（47.18%） | 247/500（49.40%） | frozen-head transfer；N有4未知 |
| X-VLA 030000 | 403/500（80.60%） | 403/500（80.60%） | frozen-head transfer；各500完成 |

Smol raw50/K10、X raw30/K10；辅助网络直接用冻结π0.5五任务资产，此阶段专属小网训练0。X底座原训练记录49个唯一任务标签。N缺项与协议按原结果保留。

### 专属网络旧Q once

| 底座 / 节点 | N复用成功/有效（%） | 专属R-once成功/有效（%） | 专属Velocity-once成功/有效（%） |
| --- | ---: | ---: | ---: |
| SmolVLA050000 / B | 234/496（47.18%） | 242/500 | 247/500 |
| X-VLA030000 / C | 403/500（80.60%） | 410/500 | 407/500 |

### 专属网络旧Q multi（完整终局状态）

| 底座 | 旧专属Q Velocity-multi | 状态/来源 |
| --- | --- | --- |
| SmolVLA | 未取得完整终局 | 该旧Q格没有完整结果；不以L01的240/500或L11的247/500替代 |
| X-VLA | 408/500 | [原专属multi终局](../sim_command/20260919/results/C/C_D24_XVLA_MULTI_EVAL_V1/FINAL_SUMMARY.json) |

Smol once：[FINAL_SUMMARY.json](../sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/recovery_r3/FINAL_SUMMARY.json)；X once：[FINAL_SUMMARY.json](../sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1/FINAL_SUMMARY.json)。两底座旧专属Q的once与完整刷新后L01/L11 multi同时改变Q版本和次数协议。

### 专属数据采集与训练数量

| 底座 | 计划train/dev父源 | 实际有效train/dev cut | 实际采集终局/技术缺失 | G0有效配对及非零收益数 | Q有效a0/±组及pair数 | D/G0/Q实际更新 | 开发指标/冻结模型 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SmolVLA | 200/50，共250 | 188/47 | 1895完整；15 normal-only父源，技术缺项另账 | 188 train；非零25 | 188绝对父源；gain364，pair182 | 32000，8成员各4000 | 固定4000末步；dev仅描述 |
| X-VLA | 200/50，共250 | 191/49 | 1930完整；10 normal-only父源，技术缺项另账 | 191 train；非零25 | 191绝对父源；gain372，pair186 | 32000，8成员各4000 | 固定4000末步；dev仅描述 |

MT50每任务4train＋1dev，训练cut固定5/15/35/55，dev按任务序号分配。同cut old/fresh a0/local±各2后缀重复；晚cut之前成功不换源，不把缺repeat造标签。首轮D双成员/G0双成员/Q四成员各4000更新共32000；Q每成员7058参数，L11。随后每底座四loss×四成员完整Q刷新另64000更新。外部冻结π0.5特征提供者仍存在。

来源：[Smol DATA](../sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/DATA_SUMMARY.json)、[Smol FIT](../sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/FIT_SUMMARY.json)、[X DATA](../sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1/DATA_SUMMARY.json)、[X FIT](../sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1/FIT_SUMMARY.json)。

### 直接迁移阶段保存的Velocity配对

| 设置 | 对比 | 有效对数 | 对比方法成功 / 参照成功 | 救回 / 损害 | 差值 pp | 95%描述性区间 pp |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| SmolVLA 050000 / MT50 | Velocity - N | 496 | 246 / 234 | 35 / 23 | +2.42 | [-0.40, +5.05] |
| SmolVLA 050000 / MT50 | Velocity - Post | 500 | 247 / 240 | 11 / 4 | +1.40 | [+0.00, +3.00] |
| X-VLA 030000 / MT50 | Velocity - N | 500 | 403 / 403 | 25 / 25 | +0.00 | [-4.60, +4.00] |
| X-VLA 030000 / MT50 | Velocity - Post | 500 | 403 / 407 | 7 / 11 | -0.80 | [-2.20, +0.40] |

这些是旧frozen-head transfer的配对，不是专属L01/L11的配对。Smol用共同496源，246成功不替代全500源247成功。MW Velocity区间沿C的任务cluster bootstrap2000/seed20260922。来源：[E8_PAIRED.csv](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E8_PAIRED.csv)。

<a id="velocity-data-15"></a>
## 15. 历史外部比较及已保存配对

当前L11及不依赖Q的外部基线已在前部列明；下面保存旧版本参照数值和既有配对，不计算新L11差值。

| π0.5 H10版本/方法 | 成功/有效 | 原成功率 |
| --- | --- | --- |
| 旧固定Q Velocity-once | 340/500 | 68.0% |
| 旧固定Q Velocity-multi | 346/500 | 69.2% |
| 完整Q L01 Velocity-multi | 340/500 | 68.0% |
| VLA-Corrector本地实现 | 319/500 | 63.8% |
| GAF-v1 adapted | 315/500 | 63.0% |

同π0.5 SFT030000/MT50原500源；外部各自训练资产和干预机制不同。VLA-Corrector8条终局为log-derived，精确费用492/500；GAF三成员共30000更新，15train/2internal holdout。

### 旧once Velocity与VLA-Corrector

| 左侧方法 − VLA-Corrector | 对数 | 差值pp | 95%区间pp | 救回/损害 | 精确McNemar p | 四比较Holm p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Velocity | 500 | +4.20 | [0.60, 7.60] | 60/39 | 0.0439 | 0.1316 |

### 旧once GAF与Velocity（原方向GAF−Velocity）

| GAF − 参照方法 | 对数 | 差值pp | 95%区间pp | 救回/损害 | 精确McNemar p | 四比较Holm p |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GAF - Velocity | 500 | -5.00 | [-8.40, -1.80] | 36/61 | 0.01439 | 0.04317 |

Holm各沿原四比较家族；只迁移一行不重新校正。CI为原固定任务内配对bootstrap。来源：[E3_VLA_CORRECTOR_PAIRED_ANALYSIS.csv](../sim_command/20260919/deadline_20260924/E3_VLA_CORRECTOR_PAIRED_ANALYSIS.csv)、[E3_GAF_PAIRED.csv](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E3_GAF_PAIRED.csv)。

### 旧multi外部点差登记（其余统计未生成）

| 新配对 | 计划共同源 | 差值pp | 95%区间 | 救回/损害 | 精确p/校正p |
| --- | ---: | ---: | --- | --- | --- |
| Velocity-multi − VLA-Corrector | 500 | +5.4 | NR | NR | NR |
| Velocity-multi − GAF | 500 | +6.2 | NR | NR | NR |

该处空白转为NR仅表示原统计字段未生成；原500条评测已完成。L01和L11 Velocity外部配对的未生成CI/p不由上述旧once统计填充。

<a id="velocity-data-16"></a>
## 16. 共用触发器E6数据：下游仅R，不是Velocity评测

保留与Velocity使用的触发器相关的共用记录；这里下游R，不把结果改名为Velocity。测试五任务ordinal10–19，与MT50主表ordinal0–9不同。D5阈值0.2521600950570383在旧100dev上匹配95/100报警，不读test成功选择阈值。

### once

| 指标 | 收益 G0→R | 因果异常 D5→R |
| --- | ---: | ---: |
| 成功/有效 | 26/50 | 30/50 |
| 成功率 | 52.0% | 60.0% |
| 实际触发episode | 46/50 | 45/50 |
| 策略采样调用总数 | 973 | 884 |

| 任务（每臂10条） | G0 成功/10 | D5 成功/10 |
| --- | ---: | ---: |
| disassemble-v3 | 7/10 | 9/10 |
| pick-place-wall-v3 | 7/10 | 8/10 |
| shelf-place-v3 | 1/10 | 2/10 |
| stick-pull-v3 | 1/10 | 1/10 |
| stick-push-v3 | 10/10 | 10/10 |

原once配对共同成功25、共同失败19；D5救回5/损害1，D5−G0 +8pp，精确双侧p=0.21875。来源：[E6_COMPLETED_ANALYSIS_20260922.md](../sim_command/20260919/deadline_20260924/E6_COMPLETED_ANALYSIS_20260922.md)、[E6_PER_TASK_CELLS.csv](../sim_command/20260919/results/A/A_D24_CORE_REMAINDER_V1/E6_PER_TASK_CELLS.csv)。

### multi

| 触发器 | 成功/有效 | 成功率% | 触发0/1/≥2 | 干预总数 / 均值 | 完整policy调用总数 / 均值 | 相对另一臂：差值/区间/救回损害 |
| --- | --- | --- | --- | --- | --- | --- |
| G0→R-multi | 26/50 | 52.0 | 4/11/35 | 240 / 4.80 | 1072 / 21.44 | −10 pp；[−22,0]；2/7 |
| D5→R-multi | 31/50 | 62.0 | 5/2/43 | 380 / 7.60 | 1001 / 20.02 | +10 pp；[0,22]；7/2 |

原G0−D5 p=0.1796875；任务内bootstrap2000/seed20260921的逐项95%区间。来源：[PAIRED.json](../sim_command/20260919/results/A/A_D24_MULTI_PRIMARY_VALIDATION_V1/PAIRED.json)、[master_costs_e6_addendum.json](../sim_command/20260919/deadline_20260924/analysis_20260923_claims/master_costs_e6_addendum.json)。

<a id="velocity-data-17"></a>
## 17. 历史LIBERO记录：算子完成，Full未测试

本节仅迁移已保存记录；用户此前暂缓LIBERO的运行安排没有改变。

### 固定时刻算子适配（没有D/G0）

| suite | N 成功/有效（%） | +Velocity算子 成功/有效（%） |
| --- | ---: | ---: |
| libero_spatial | 98/100（98.00%） | 99/100（99.00%） |
| libero_object | 100/100（100.00%） | 99/100（99.00%） |
| libero_goal | 98/99（98.99%） | 99/100（99.00%） |
| libero_10 | 91/100（91.00%） | 90/100（90.00%） |
| all_four_suites | 387/399（96.99%） | 387/400（96.75%） |

官方π0.5权重/normalizer，H10/K5/NFE10、command20固定干预。原随机reset/policy seed，不是官方固定初态排行榜协议。算子小头120训练候选（24父源、5负例）、40描述性验证候选（8父源、全部成功）。

### 算子版Velocity配对

| 设置 | 对比 | 有效对数 | 对比方法成功 / 参照成功 | 救回 / 损害 | 差值 pp | 95%描述性区间 pp |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| pi05 official / all_four_suites | Velocity - N | 399 | 386 / 387 | 5 / 6 | -0.25 | [-1.88, +1.38] |
| pi05 official / all_four_suites | Velocity - Post | 400 | 387 / 387 | 4 / 4 | +0.00 | [-1.39, +1.39] |

Velocity−N共同399源中为386/387成功，方法全400源为387成功；Velocity−Post 400对、4救回/4损害。原LIBERO对N采用已发布配对正态描述区间，区间原样保留。来源：[E8_TABLE.csv](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E8_TABLE.csv)、[E8_PAIRED.csv](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E8_PAIRED.csv)、[COMBINED_N_INDEX.json](../sim_command/20260919/results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1/COMBINED_N_INDEX.json)。

### LIBERO Full-Velocity状态

| 字段 | 保存状态 |
| --- | --- |
| 计划测试 | 400 |
| 实际Full-Velocity测试 | 0；无成功率，不填0% |
| 开发采集 | 40 attempts；30有效且成功、10技术失败 |
| G0收益配对 | 7train＋4validation，收益全部0 |
| 训练更新 | 0 |
| 配对成功/调用/时间 | NR：Full评测未进入 |
| 原生方案 | D2/age2/G0 old3–fresh3后native5、C5/nativeK5、once阈值0.05、旋转不纠偏 |

来源：[A_D24_LIBERO_FULL_NATIVE_V1_RESULT_r13.json](../sim_command/20260919/receipts/A/A_D24_LIBERO_FULL_NATIVE_V1_RESULT_r13.json)。算子版与Full是两个不同设置。Smol基线4未知、LIBERO基线1未知保留；LIBERO已合法恢复5个槽、5/5成功，N由394有效变为399有效。

<a id="velocity-data-18"></a>
## 18. 历史旧Q成本与计时（按原测量范围）

### 旧multi最终有效episode成本

| H | 方法 | 成功/500 | 策略调用/有效episode | 全有效调用/成功数 | 平均干预次数 | 次数0/1/≥2 |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 10 | N | 308/500 | 15.130 | 24.562 | 0 | 500/0/0 |
| 10 | R-multi | 343/500 | 14.452 | 21.067 | 2.034 | 109/155/236 |
| 10 | Velocity-multi | 346/500 | 16.364 | 23.647 | 2.070 | 109/156/235 |
| 20 | N | 240/500 | 9.372 | 19.525 | 0 | 500/0/0 |
| 20 | R-multi | 324/500 | 10.158 | 15.676 | 2.412 | 93/141/266 |
| 20 | Velocity-multi | 328/500 | 12.386 | 18.881 | 2.330 | 93/139/268 |
| 30 | N | 205/500 | 6.964 | 16.985 | 0 | 500/0/0 |
| 30 | R-multi | 330/500 | 8.650 | 13.106 | 2.568 | 85/131/284 |
| 30 | Velocity-multi | 329/500 | 11.226 | 17.061 | 2.566 | 85/133/282 |
| 40 | N | 205/500 | 5.602 | 13.663 | 0 | 500/0/0 |
| 40 | R-multi | 318/500 | 8.276 | 13.013 | 2.734 | 85/135/280 |
| 40 | Velocity-multi | 316/500 | 10.718 | 16.959 | 2.612 | 85/135/280 |
| 50 | N | 196/500 | 4.312 | 11.000 | 0 | 500/0/0 |
| 50 | R-multi | 321/500 | 7.584 | 11.813 | 2.676 | 92/127/281 |
| 50 | Velocity-multi | 325/500 | 10.048 | 15.458 | 2.614 | 92/127/281 |

该表仅最终有效500episode，含科学任务失败，旧技术尝试费用另账。调用/episode＝全有效调用÷500；全有效调用/成功数为摊销，不是仅成功episode均值。Velocity H10 16.364与前部总尝试16.512分开。来源：[TRIGGER_CELLS_AND_COSTS.csv](../sim_command/20260919/deadline_20260924/analysis_20260922_current/trigger/TRIGGER_CELLS_AND_COSTS.csv)。

### 旧once完整调用、成功条件与摊销成本

| 设置 | 成功/有效 | 调用/episode | 仅成功episode的平均调用 | 全部调用/成功数（摊销） | 摊销95%CI |
| --- | ---: | ---: | ---: | ---: | ---: |
| N_H10 | 308/500 | 15.130 | 5.860 | 24.562 | [22.469, 27.021] |
| R_H10 | 336/500 | 14.156 | 6.009 | 21.065 | [19.263, 23.125] |
| Velocity_H10 | 340/500 | 14.794 | 6.844 | 21.756 | [19.929, 24.025] |
| N_H20 | 240/500 | 9.372 | 3.275 | 19.525 | [17.968, 21.317] |
| R_H20 | 312/500 | 8.742 | 4.038 | 14.010 | NR（未估计） |
| Velocity_H20 | 316/500 | 9.484 | 4.896 | 15.006 | [13.843, 16.328] |
| N_H30 | 205/500 | 6.964 | 2.595 | 16.985 | [15.500, 18.675] |
| R_H30 | 307/500 | 6.690 | 3.550 | 10.896 | NR（未估计） |
| Velocity_H30 | 309/500 | 7.482 | 4.346 | 12.107 | [11.256, 13.150] |
| N_H40 | 205/500 | 5.602 | 2.151 | 13.663 | [12.512, 14.953] |
| R_H40 | 290/500 | 5.872 | 3.210 | 10.124 | NR（未估计） |
| Velocity_H40 | 295/500 | 6.636 | 4.031 | 11.247 | [10.430, 12.170] |
| N_H50 | 196/500 | 4.312 | 1.694 | 11.000 | [9.995, 12.172] |
| R_H50 | 297/500 | 4.844 | 2.926 | 8.155 | NR（未估计） |
| Velocity_H50 | 296/500 | 5.646 | 3.682 | 9.537 | [8.884, 10.283] |

调用/episode、仅成功episode条件均值、全调用/成功数是三个不同指标。原区间为固定任务内配对bootstrap，沿原记录；未估计项保留NR。

### 旧once各H计时

| 设置 | episode墙钟/episode(s) | 生成/纠偏时间/episode(s) | 生成/纠偏时间/成功条件(s) | 生成/纠偏时间/成功摊销(s) |
| --- | ---: | ---: | ---: | ---: |
| N_H10 | 4.278 | 3.240 | 1.266 | 5.260 |
| R_H10 | 6.866 | 3.279 | 1.399 | 4.879 |
| Velocity_H10 | 6.952 | 3.430 | 1.596 | 5.044 |
| N_H20 | 3.278 | 2.027 | 0.712 | 4.223 |
| R_H20 | 5.906 | 2.028 | 0.943 | 3.250 |
| Velocity_H20 | 6.089 | 2.236 | 1.164 | 3.539 |
| N_H30 | 2.850 | 1.490 | 0.555 | 3.633 |
| R_H30 | 5.542 | 1.544 | 0.818 | 2.515 |
| Velocity_H30 | 5.767 | 1.766 | 1.042 | 2.857 |
| N_H40 | 2.596 | 1.218 | 0.471 | 2.972 |
| R_H40 | 5.635 | 1.372 | 0.757 | 2.365 |
| Velocity_H40 | 5.764 | 1.572 | 0.964 | 2.665 |
| N_H50 | 2.325 | 0.934 | 0.367 | 2.382 |
| R_H50 | 5.266 | 1.123 | 0.677 | 1.891 |
| Velocity_H50 | 5.467 | 1.333 | 0.877 | 2.252 |

各格覆盖500/500。N生成计时含预处理/raw50生成/解码；主链生成/纠偏含Q/投影，monitor/context多数在episode墙钟范围。episode时间不含常驻加载/job环境创建；不是GPU秒。

### 旧once干预入口时间

| 干预入口 | 保存/实际入口 | 入口均值(s) | 中位数(s) | P95(s) | 最小–最大(s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| R_H10 | 391/391 | 0.232 | 0.230 | 0.241 | 0.223–0.277 |
| Velocity_H10 | 391/391 | 0.490 | 0.489 | 0.513 | 0.476–0.557 |
| Velocity_H20 | 407/407 | 0.496 | 0.500 | 0.508 | 0.476–0.525 |
| Velocity_H30 | 415/415 | 0.496 | 0.499 | 0.515 | 0.477–0.599 |
| Velocity_H40 | 415/415 | 0.496 | 0.498 | 0.511 | 0.476–0.544 |
| Velocity_H50 | 408/408 | 0.493 | 0.493 | 0.508 | 0.478–0.555 |

R_H20/30/40/50入口数407/415/415/408；原r03未提取其逐入口时间，均值/P95/范围NR。Velocity入口含base/guided采样、Q、动作梯度、投影、局部产物保存，不含入口前monitor/context；嵌套时间不重复相加。净D/G0/context、净反向、净纠偏增量、GPU kernel秒和能耗NR。旧主链末段32个辅助holder会话、累计263.297管理进程区间秒保留，不解释为kernel时长。

来源：[旧调用](../sim_command/20260919/results/A/A_D24_OURS_E5_REPORT_V1/PAPER_COST_TABLE.csv)、[旧计时](../sim_command/20260919/results/A/A_D24_OURS_E5_REPORT_V1/TIMING_TABLE.csv)、[旧入口](../sim_command/20260919/results/A/A_D24_OURS_E5_REPORT_V1/ENTRY_TIMING_TABLE.csv)、[扩展R成本](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E5_AMORTIZED_COST_TABLE.csv)、[扩展R时间](../sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E5_TIMING_RANGES.csv)。

<a id="velocity-data-19"></a>
## 19. 共用参数规模及缓冲区记录

| 新增组件 | 成员数 | 每成员网络参数 | 全ensemble网络参数 |
| --- | ---: | ---: | ---: |
| D | 2 | 4,474,116 | 8,948,232 |
| G0 | 2 | 1,468,033 | 2,936,066 |
| Q | 4 | 7,058 | 28,232 |
| D＋G0＋Q | 8 | — | **11,912,530** |

网络参数按成员计，不包含非训练PCA/归一化buffer；buffer按保存加载副本2,851,264字节，另有共享固定投影2,097,152数据字节。π0.5共享编码器新增参数0，但计算并非免费。基础VLA唯一运行参数量NR；序列化权重元素数4,143,404,816不等于已核定运行参数量，不能据此算缩小倍数。Q的28,232不是完整系统新增参数。历史一次A4000拟合仅更新10,116参数，不是全部历史训练/部署规模。

来源：[PARAMETER_COUNTS.json](../sim_command/20260919/results/A/A_D24_OURS_E5_REPORT_V1/PARAMETER_COUNTS.json)。

<a id="velocity-data-20"></a>
## 20. 历史20初态pilot

disassemble-v3旧20个已揭晓初态，repeat0；once/multi仅改变总次数帽。保留原比较方法数值，所有六格合计120有效、技术失败0。

| 方法 | once 成功/20（%） | multi 成功/20（%） | multi−once（pp） | multi 中≥2次干预的初态数 | multi救回/损害 |
| --- | ---: | ---: | ---: | ---: | ---: |
| R | 13/20（65.0） | 13/20（65.0） | 0.0 | 6/20 | 0/0 |
| Post | 16/20（80.0） | 16/20（80.0） | 0.0 | 4/20 | 0/0 |
| Velocity | 15/20（75.0） | 15/20（75.0） | 0.0 | 6/20 | 0/0 |

Velocity两组逐源成败完全相同；multi有6个源干预≥2次。这里不是MT50，也不是L11完整Q重测。来源：[PILOT_FINAL_RESULTS.csv](../sim_command/20260919/deadline_20260924/PILOT_FINAL_RESULTS.csv)、[PILOT_FINAL_ANALYSIS.md](../sim_command/20260919/deadline_20260924/PILOT_FINAL_ANALYSIS.md)。

<a id="velocity-data-21"></a>
## 21. 历史standalone：共同半径与独立Velocity

held100＝五任务各20初态，每源4个配对后缀种子；每方法400结局、每任务80，独立初态数100。98合法报警源运行独立分支，2无报警源沿用共同结局。N/R及共同半径版本来自封存对照。该实验已完成，未因本文迁移重跑。

### 原共同半径与独立分支总体记录

| 方法/版本 | 成功/400 | 原成功率 | 原相对R pp |
| --- | --- | --- | --- |
| 原N | 168/400 | 42.00% | — |
| 原R | 214/400 | 53.50% | 0 |
| 共同半径Velocity | 237/400 | 59.25% | +5.75 |
| 独立Velocity | 240/400 | 60.00% | +6.50 |
| 共同半径Post（参照） | 250/400 | 62.50% | +9.00 |
| 独立Post（参照） | 252/400 | 63.00% | +9.50 |
| 共同半径Direct（参照） | 234/400 | 58.50% | +5.00 |
| 独立Direct（参照） | 237/400 | 59.25% | +5.75 |

### 独立Velocity配对与幅度

| 原比较 | 差值pp | 95%区间pp | Bonferroni98.3333%区间pp | 救回/损害 | 正/负/零源 |
| --- | --- | --- | --- | --- | --- |
| solo_velocity−R | +6.50 | [2.50, 11.25] | [1.50, 12.25] | 30/4 | 13/4/83 |
| solo_velocity−原共同半径Velocity | +0.75 | [−1.50, 3.00] | 原次要比较未给 | 6/3 | 3/1/96 |

| 分支 | XYZ幅度增大源/98 | 夹爪幅度增大源/98 | XYZ平均RMS旧→新 | 夹爪平均RMS旧→新 |
| --- | --- | --- | --- | --- |
| Velocity | 38/98 | 20/98 | 0.042949→0.045949 | 0.087509→0.089554 |

XYZ零组0，夹爪零组9源均mask全关；非零组内方向夹角最大不到0.00005度。原配对采用任务内整源bootstrap10000次、seed2026091801；Bonferroni家族含三个独立分支对R。正/负/零源按每源4次平均差分类。

### 逐任务（N/R与Velocity）

| 任务（每方法80结局） | N | R | 独立Velocity |
| --- | ---: | ---: | ---: |
| disassemble-v3 | 65.00% | 61.25% | 76.25% |
| pick-place-wall-v3 | 37.50% | 72.50% | 73.75% |
| shelf-place-v3 | 20.00% | 17.50% | 22.50% |
| stick-pull-v3 | 8.75% | 21.25% | 27.50% |
| stick-push-v3 | 78.75% | 95.00% | 100.00% |

### 历史独立入口计时

| 历史独立入口 | 每次干预VLA采样数 | 入口均值(s) | 中位数(s) | P95(s) |
| --- | ---: | ---: | ---: | ---: |
| Velocity | 2 | 0.904 | 0.887 | 1.152 |

98报警入口计时包含自身a0、纠偏、诊断评分/检查，不含加载、恢复、后缀仿真；8GPU×4worker，原固定调用顺序存在冷入口影响。来源：[standalone原报告](STANDALONE_CORRECTOR_ABLATION_20260918.md)，各数字的记录版本不变。

<a id="velocity-data-22"></a>
## 22. A10有限工程数值记录（不是任务成功率）

历史五任务Q、step0和cut5是两个保存诊断状态，不是受控消融；cut5 G0均值−0.0577081237未触发，执行的是强制工程干预。没有接受门或数值下降重试。

| 状态 | 分支 | g·实际delta | cosine | 最终J=ΔQ | 成员升/降 | XYZ实际RMS |
| --- | --- | --- | --- | --- | --- | --- |
| step0 | Velocity | +0.067283644 | +0.684355 | +0.061526142 | 3/1 | ≈0.050000 |
| cut5 | Velocity | −0.068514917 | −0.348346 | −0.156066865 | 0/4 | ≈0.044475 |

| cut5处理阶段 | 与该状态锚点g点积 |
| --- | --- |
| guided raw差 | −0.118639497 |
| clamp后 | −0.115827395 |
| mask后 | −0.116817487 |
| 独立半径及float32写回后 | −0.068514917 |

| 状态 | τ | 原保存一阶预测 | 保存局部ΔJ | clip |
| --- | --- | --- | --- | --- |
| step0 | 0.3 | +0.847350 | −0.268069 | 25.0% |
| step0 | 0.2 | +0.148198 | −0.246999 | 27.5% |
| step0 | 0.1 | +0.025773 | +0.013966 | 35.0% |
| cut5 | 0.3 | +2.038450 | −0.151515 | 25.0% |
| cut5 | 0.2 | +0.492224 | −0.342613 | 25.0% |
| cut5 | 0.1 | +1.041704 | −0.121940 | 27.5% |

保存末τ local-after不是独立最终guided Q；后者为null。完整逐τ向量/成员概率缺失，首次反向τ与根因未知。原理想一阶关系、有限步实际值和负结果并存；没有据此改α、符号或加Q门。本次仅迁移这些已保存数值。来源：[REPORT.md](../sim_command/20260919/results/A/A10_PV_DIRECTION_CPU_ANALYSIS_V1/REPORT.md)、[REPORT.md](../sim_command/20260919/results/A/A10_CAUSAL_C10_PREFLIGHT_V2/REPORT.md)。

<a id="velocity-data-23"></a>
## 23. L11首次无效尝试及恢复关系（原状态保留）

以下是已归档的原执行汇总，不是有效L11终局。旧A/C存在Q介入前路径分歧及渲染错误证据，独立修复后只恢复原非有效单元。当前有效结果与旧尝试各有来源，不覆盖原记录。

| 原执行节点 | 模式/H | Velocity原汇总成功/记录 | 分析处置 |
| --- | --- | --- | --- |
| A | G0-multi/H10 | 81/500 | 新执行部分暂缓采信；H10multi原复用各50有效 |
| A | G0-multi/H30 | 65/500 | 本格500条质量hold；随后由B恢复原非有效单元 |
| A | G0-once/H10 | 56/500 | 本格500条质量hold；随后由A恢复原非有效单元 |
| C | G0-multi/H40 | 40/500 | Velocity本格500条质量hold；原1000条为Post与Velocity合计 |
| C | G0-multi/H50 | 38/500 | 500条执行质量hold |

当前Velocity恢复关系：A H10 multi450恢复＋50原有效复用，once500；B接手H30 500；C恢复H40/H50各500；B H20与Smol旧有效各500、C X旧有效500保留。第一次A2900和C1500质量隔离是原双/多分支范围，不能都算成Velocity数。

原A：[RESULT.json](../sim_command/20260919/results/A/A_D24_L11_RETEST_V1/RESULT.json)；原C尝试：[ATTEMPTS_ALL.csv](../sim_command/20260919/results/C/C_D24_L11_RETEST_V1/task_summary/ATTEMPTS_ALL.csv)；恢复终局：[FINAL_ACCEPTANCE.json](../sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ACCEPTANCE.json)。旧有效/未知/渲染hold保持原状态，未用成功率高低直接改写标签。

<a id="velocity-data-24"></a>
## 24. 无结果和未生成统计字段登记

| 项目 | 保存状态 | 数值处理 |
|---|---|---|
| Random-multi | 用户取消，未运行 | 不填成功率，不转为待自动运行 |
| LIBERO Full-Velocity | 开发监督缺口后停止，测试0 | 成功率/配对/成本NR |
| 旧Smol专属Q multi完整格 | 无完整终局 | 不用后续L01/L11代填 |
| Smol N四源、LIBERO N一源 | unknown | 不计科学失败，分母496/399保留 |
| L11新配对CI/p、逐任务派生表 | 除已有H10救回/损害外，本汇总未生成 | 不复制其他Q版本统计 |
| L01 Velocity H10 multi−once配对区间 | 原总表NR | 边际成功340/336与已有点差保留 |
| 时间/能耗/逐episode梯度缺字段 | 以对应成本表覆盖为准 | 缺失不填0，不以墙钟替代GPU秒 |
| 用户真实场景 | 尚无指定为Velocity分支的终局记录 | 不将原未指定分支的计划自动归入Velocity |

此表记录数据状态，没有新增任务或实验安排。

<a id="velocity-data-25"></a>
## 25. 原始数据入口与更新口径

- 当前L11：前部四份来源表合并入口及 `FINAL_EPISODES.csv` 的 `method=Velocity` 共4000条；来自A/B/C三个节点，包含源ID、方法、H、成功、计量与原RESULT路径。
- 完整Q开发/补充test：`TECHNICAL_EPISODES_ALL_METHODS.csv` 按Velocity、loss、fit、split读取；旧残差组使用自己的E1终局，不能混合。
- 原MT50 once：`MAIN_20CELL_TABLE.csv` 与 `MAIN_FINAL_PAIRED_COMPARISONS.csv`；原随机/多次：`TRIGGER_CELLS_AND_COSTS.csv` 和 `PAIRED_TIMING_MULTIPLICITY_WITH_HOLM.csv`。
- 专属/迁移Smol/X、LIBERO、standalone、pilot和工程诊断：各节直接链接其原表与回执；重复引用不代表新实验。

后续补数据时应带上底座、Q训练范围/loss/fit、once/multi、H/C/raw、源/seed、renderer/控制协议、分母、技术状态、指标范围和直接来源。表内旧精确p/CI保留原比较方向及校正家族，不随文章取表数量自动改写。本次只做数据迁移与一致的排列表达，筛选和稿件取舍由用户决定。


## 26. 新增X-VLA多次H扫描（L11 / fit9101）

H20/H30均复用原MT50的500个固定测试源，不新增初态，normal H与C10分离，raw chunk30，NFE10。每格500唯一源完整终局，technical/unknown均0；费用为全部有效episode均值。

| H | N SR (%) | R-multi SR (%) | Velocity SR (%) | Policy Calls | Flow Calls | Interventions | Action Gradients |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 77.6 | 78.6 | 79.8 | 13.586 | 135.86 | 3.346 | 10.038 |
| 30 | 77.0 | 78.8 | 77.6 | 13.654 | 136.54 | 3.822 | 11.466 |

这是X-VLA本身固定Mesa协议内比较；不是跨底座统一协议的排名，亦不宣称同H采样或完整时延更低。来源：[C终局逐源CSV](../sim_command/20260919/results/C/C_D24_CROSSBASE_H_SWEEP_V1/FINAL_EPISODES.csv)、[成本覆盖](../sim_command/20260919/results/C/C_D24_CROSSBASE_H_SWEEP_V1/COSTS.json)。SmolVLA H20已完成并见下一节；H30/H40/H50尚未完整，不以部分样本代填。


## 27. 新增SmolVLA多次H扫描：H20（L11 / fit9101）

同一原MT50测试源，每格500合法终局。Velocity保留34条原合法结果，修复后只续跑466条缺项；500唯一源、模型/Q/seed身份均核对。技术失败尝试另账。

| H | N SR (%) | R-multi SR (%) | Velocity SR (%) | Policy Calls | Flow Calls | Interventions | Action Gradients |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 45.2 | 49.2 | 49.0 | 16.680 | 166.80 | 3.142 | 9.426 |

所有均值只来自500个合法终局；不能用包含190次技术失败尝试的8837次总采样除500，正确合法采样总数为8340。原失败证据保留，不作任务失败样本。来源：[有效逐源合并表](../sim_command/20260919/results/A/A_D24_CROSSBASE_H_SWEEP_V1_RECOVERY_r2/COMBINED_VALID_EPISODES.csv)、[分析费用重算](../sim_command/20260919/deadline_20260924/CROSSBASE_H_SWEEP_V1/analysis/20260923T134924Z/A_VALID_ONLY_VELOCITY_COSTS.json)。
