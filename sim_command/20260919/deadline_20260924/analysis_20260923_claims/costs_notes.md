# 新Q Post L01/fit9101：调用与参数证据

生成：2026-09-23T01:04:48.668258+00:00。只分析π0.5/MT50新Q Post；LIBERO与Velocity不进入本篇结论。只读现成CSV/摘要求和，未运行GPU、读取权重/大段代码或重算显著性。

## 完整策略调用：全部500有效episode

policy call指一次完整raw50采样，包含自然重规划和干预采样；NFE10，所以每次对应10次flow/action-expert前向。Post每次干预仅采样一次，之后另做Q纠偏。这里不是总pipeline FLOPs或端到端时间；编码、D/G0/Q及动作梯度仍有开销。分母含科学失败，不只挑成功episode。

| H | 新Post multi成功/500 | 完整calls总数 | calls/episode | 全调用/成功数 | 同H N成功/500；calls/episode | 同H R-multi成功/500；calls/episode |
|---:|---:|---:|---:|---:|---|---|
| 10 | 350/500 | 7037 | 14.074 | 20.106 | 308/500；15.130 | 343/500；14.452 |
| 20 | 334/500 | 4953 | 9.906 | 14.829 | 240/500；9.372 | 324/500；10.158 |
| 30 | 334/500 | 4231 | 8.462 | 12.668 | 205/500；6.964 | 330/500；8.650 |
| 40 | 324/500 | 3983 | 7.966 | 12.293 | 205/500；5.602 | 318/500；8.276 |
| 50 | 323/500 | 3639 | 7.278 | 11.266 | 196/500；4.312 | 321/500；7.584 |

所有新Post格各50任务×10源，完整calls均500/500有值；policy_calls=sampling_calls，flow_calls=10×sampling_calls。B H20只取原12条Post有效＋接续488条，不累计unstarted行；每格source_id唯一。新Q H20源自原r1与接续表合并，原失败记录保留。

## 可以使用的成本表述及边界

| H | 新Post相对N H10的完整调用变化 | 成功率点差 vs N H10 | 相对同H N调用变化 | 相对同H R-multi调用变化 |
|---:|---:|---:|---:|---:|
| 10 | -6.98% | +8.4pp | -6.98% | -2.62% |
| 20 | -34.53% | +5.2pp | +5.70% | -2.48% |
| 30 | -44.07% | +5.2pp | +21.51% | -2.17% |
| 40 | -47.35% | +3.2pp | +42.20% | -3.75% |
| 50 | -51.90% | +3.0pp | +68.78% | -4.03% |

可作描述性结论：长H的Post完整策略调用少于N_H10，同时在原500源上成功率点估更高；例如H50为64.6%与61.6%，7.278与15.130次/episode（少51.90%）。这比较不同正常执行间隔，不是单次推理提速。成功提前终止也会减少后续调用，不应把差异全归于更便宜的纠偏。

相同H下，Post较R-multi的调用点估均略少；较N仅H10更少，H20–50均更多。因此不能声称所有H相对各自N都省策略调用。H50全部调用/成功数为11.266，N_H50为11.000，不能把成功率提升写成该口径成本也全面下降。

## H10同新Q once / multi

once：341/500，6931次完整调用，13.862次/episode，全部调用/成功数20.326。multi：350/500，7037次，14.074次/episode，全部调用/成功数20.106。multi比once增加106次总调用＝0.212次/episode（+1.53%），成功率点估+1.8pp；不支持multi更省调用。

现成[A PAIRED.csv](../../results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/PAIRED.csv)报告同500源救回13/损害4，pointwise95%差值区间[0.4,3.4]pp，精确McNemar p=0.049041748046875；原口径为固定任务内source bootstrap，不含训练seed不确定性，此处未重算。该结果不是等效性试验，没有预定义等效/非劣界值；不能宣称“once/multi等效”或“相同效果”。

## 参数能怎么说

| 网络 | 成员数 | 每成员参数 | ensemble参数 |
|---|---:|---:|---:|
| D | 2 | 4474116 | 8948232 |
| G0 | 2 | 1468033 | 2936066 |
| Q | 4 | 7058 | 28232 |
| 合计 | 8 | — | 11912530 |

可称“D2/G02/Q4共约11.9M附加网络参数，其中Q4仅28232参数”；不可把Q4称完整系统，不能由网络参数小推断总计算小。π0.5共享已有冻结图像/语言backbone，新增encoder参数为0但编码计算非0。PCA/归一化buffer 2851264字节和共享固定投影2097152字节不是网络参数，也不是峰值显存。基础VLA唯一运行参数量未核定；序列化4143404816元素不能据此宣传整体参数缩小倍数。

新完整Q有独立TRAINING_COMPLETE/E5_PARAMETERS证据：每成员7058全参数从头训练、部署四成员28232；旧局部适配10116参数不是本轮训练范围。

Smol/X额外加载冻结π0.5作为外部特征提供者，整份加载记录为4143404816，包含不用的action参数，active visual submodule参数仍null。因此11.9M不是Smol/X完整附加pipeline；4.143B也不是每次视觉调用都激活的参数量。新X摘要保存编码/RPC/policy计时，但RPC与native推理可能重叠，不能直接相加为端到端成本；旧Smol once计时未冒用为新Q multi。

## 来源与未覆盖项

- `results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/FINAL_EPISODES.csv`
- `results/B/B_D24_PI05_SELECTED_H20_H30_V1/H20_r1/FINAL_EPISODES.csv`
- `results/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1/waves/H20_01/FINAL_EPISODES.csv`
- `results/B/B_D24_PI05_SELECTED_H20_H30_V1/H30_r1/FINAL_EPISODES.csv`
- `results/C/C_D24_PI05_SELECTED_H40_H50_V1/FINAL_EPISODES.csv`
- `deadline_20260924/MAIN_FINAL_CELLS_WITH_COSTS.csv`
- `deadline_20260924/analysis_20260922_current/trigger/TRIGGER_CELLS_AND_COSTS.csv`
- `results/A/A_D24_OURS_E5_REPORT_V1/FIELD_DEFINITIONS.json`
- `results/A/A_D24_OURS_E5_REPORT_V1/PARAMETER_COUNTS.json`
- `results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/E5_PARAMETERS.json`
- `results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/TRAINING_COMPLETE.json`
- `results/B/B_D24_SMOL_AUX_RETRAIN_V1/recovery_r3/RESOURCE_SUMMARY.json`
- `results/C/C_D24_XVLA_AUX_RETRAIN_V1/EXTERNAL_FEATURE_COSTS.json`
- `results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/FINAL_SUMMARY.json`

所有相对路径均相对`Corrector/sim_command/20260919/`。机器可读值、字段、口径与精确绝对来源见同目录`costs.json`。没有从旧Post Q成本推断新Post成本；N/R不依赖Q，直接复用其原500有效终局。N独立sampling_calls字段未记录，保留null；policy_calls的完整采样语义及0技术失败由已有FIELD_DEFINITIONS与原表说明支持。

这些调用总数排除历史技术尝试、加载、holder占用及发布失败研究费用；原记录继续保留。新Q真正端到端响应时间、GPU能耗、总FLOPs和总pipeline峰值显存未在此确认，不能据调用次数当作已证实。跨机器/并发episode时间求和也不等于部署延迟。调用差异只报点估计，本次未扩大bootstrap或显著性检验。
