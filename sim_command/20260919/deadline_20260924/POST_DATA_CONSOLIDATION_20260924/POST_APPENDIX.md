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

