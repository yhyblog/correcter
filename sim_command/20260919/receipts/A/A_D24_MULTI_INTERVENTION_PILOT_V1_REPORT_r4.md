旧20初态开发测试：R/Post四组已完整完成；每组20，repeat0，技术失败0。

| 方法 | 成功 | 成功率 | 干预0/1/2/3+ | 采样调用 | 逐episode耗时之和(s) |
|---|---:|---:|---|---:|---:|
| R_once | 13/20 | 65% | 0/20/0/0 | 379 | 211.80 |
| R_multi | 13/20 | 65% | 0/14/4/2 | 381 | 196.75 |
| Post_once | 16/20 | 80% | 0/20/0/0 | 297 | 157.55 |
| Post_multi | 16/20 | 80% | 0/16/3/1 | 301 | 158.17 |

R多次−单次=0pp，Post多次−单次=0pp；两者均救回0/损害0。R多次有6条、Post多次有4条真正发生第二次或更多干预；结果相同不是“没有第二次干预”。

Post_multi−R_multi=+15pp（多成功3条），救回5、损害2；具体源见 PRIMARY_RESULT.json。不能据旧已揭晓20初态推断全MT50排名。每条成功对应5个百分点，未新增seed/repeat或挑选赢家。

采样包含正常H10重规划和实际干预，Post每次干预1采样、Velocity为2。耗时列为逐episode累加，非并发墙钟，不包含各worker一次性的模型加载。控制、预测、参数与初态检查见隔离包；旧Mesa单次仅独立历史参考。

Velocity入口已实际开始执行，不等待本报告或新授权。整波holder保持全停，Velocity及全部后代退出/发布后统一恢复。

/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/PRIMARY_RESULT.json
