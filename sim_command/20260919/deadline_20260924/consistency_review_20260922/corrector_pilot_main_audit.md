# Pilot 80% 与 MT50 Post 69% 的定向核查

结论：不能把这两个数字解释为相同实验从80%跌至69%。旧pilot是一个子任务disassemble的20个已揭晓开发初态；当前主表是50个任务各10个独立新test初态，共500。当前主表中同一个disassemble任务的Post是10/10=100%，并非69%。但10个新源与旧20个源不重合，所以100%也不能据此宣称对旧80%提高20pp。

| 数据范围（H10） | N | R | Post | Velocity |
|---|---:|---:|---:|---:|
| 旧20 disassemble pilot，once | 本pilot未测N | 13/20=65% | 16/20=80% | 15/20=75% |
| 旧20同初态pilot，multi | 本pilot未测N | 13/20=65% | 16/20=80% | 15/20=75% |
| 当前MT50主表，仅disassemble | 10/10=100% | 9/10=90% | 10/10=100% | 10/10=100% |
| 当前MT50主表，历史五任务名称子集 | 28/50=56% | 32/50=64% | 36/50=72% | 33/50=66% |
| 当前MT50全50任务 | 308/500=61.6% | 336/500=67.2% | 345/500=69% | 340/500=68% |

## 当前五任务明细

| 任务 | N/10 | R/10 | Post/10 | Velocity/10 |
|---|---:|---:|---:|---:|
| disassemble | 10 | 9 | 10 | 10 |
| pick-place-wall | 7 | 7 | 7 | 7 |
| shelf-place | 3 | 2 | 2 | 1 |
| stick-pull | 3 | 4 | 7 | 5 |
| stick-push | 5 | 10 | 10 | 10 |

旧20 once/multi三种方法的逐源最终成败均一样；R/Post/Velocity分别有6/4/6个multi源真正触发至少两次，故不是多次路径没运行，但当前80%也不是放开多次使结果由较低数值升至80%。同一pilot的Post_once本身也是80%。

## 已核对的一致项与差异

- Pilot与主表均使用声明SHA相同的pi05_MT50_SFT030000；选定Q的元数据、guidance、独立自身半径solo_rule一致。没有重新hash大权重，不能把这一点称为本轮独立数值复现。
- 两个新实验均NVIDIA EGL；H10/C10、最多300真实控制步、30Hz控制/400Hz物理、0.015动作scale、corner2 480×480、raw50/NFE10相同。G0阈值0.05、每5步、历史成熟/承诺锁不变，once最多一次。
- 实际语言也一致：pilot `chain/workers/0/MODEL_READY.json`记录`Pick a nut out of a peg`，主表冻结source instruction也相同。pilot BASE继承的`Disassemble a nut from a peg.`只是模板残留，实际由TASK_DESCRIPTIONS覆盖，不能据模板宣称语言更改。
- 当前pilot120个回合复用了旧20初态的已保存小数组检查，仍不是完整隐藏状态证明。主表为50任务各10个全新test源。CPU核对pilot20环境seed与主表500环境seed交集为0。
- 随机策略流也不是同一批：pilot沿旧source_seed/suffix_seed/candidate_seed；主表自然采样使用与N一致的episode CUDA generator，纠偏候选用D24_designated_a0按source/policy_seed/cut固定。不能将旧20与新10做逐源配对差值，也不能把差值完全归因为某一个因素。
- 定向读取两份controller和runtime终止/成功字段：均来自`info.success`，遇成功即结束，或done/截断/300步结束；技术异常success=null。因此没有发现这两组采用“末帧成功”与“任意帧成功”导致的成功定义差别（因首次成功立即停止，两者在保存结局等价）。

## 保存结果内部核对

读取主表5500行标量CSV，11格每格500、全部complete、步数1..300，成功数重新求和与FINAL_CELLS/MAIN_FINAL_TASKS一致；11格source/env_seed/policy_seed/task/ordinal身份逐源一致，0不匹配。Pilot PER_SOURCE_RESULTS20条×6方法重新求和得到13/16/15，once/multi逐源成败一致。未发现漏分母、重复源把69%压低、或把技术失败计0的迹象。这一结论只覆盖保存结果和上述窄语义，不等于全面证明实现无错。

## 论文建议

主表69%是MT50整体成绩；80%只放在标注“disassemble / 已揭晓开发20初态”的小实验中，不写成MT50整体。新增R的H20/30/40/50必须严格复用当前500个主test源及当前N/P/V同一评估条件，才可补齐H扫描。无需为了让历史百分比相同重跑成功样本。

## 定向来源

- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/MAIN_FINAL_TASKS.csv`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MAIN_ONCE_V1/FINAL_EPISODES.csv`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MAIN_ONCE_V1/FINAL_SUMMARY.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MAIN_ONCE_V1/config/CONFIG.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MAIN_ONCE_V1/config/TEST_SOURCES_V1.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/FINAL_SUMMARY.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/PER_SOURCE_RESULTS.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/COMPLETION_CHECK.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/config/CONFIG.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/config/SOURCES.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/NUMERICAL_BINDING.md`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/chain/workers/0/MODEL_READY.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/evidence/ONCE_REUSE_DECISION.json`
