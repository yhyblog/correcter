# 快速多次干预测试：只用旧20个初态

task_id=`A_D24_MULTI_INTERVENTION_PILOT_V1`，revision=2，owner=A。用户最新明确：只复用旧20个初态，不再新增30个初态。本版本立即覆盖revision1的50源安排；未启动的新源全部取消，不重新执行已经完成的相同有效样本。

- 任务仍为 `disassemble-v3`，全部旧20个env seed固定repeat0，名单见 `MULTI_INTERVENTION_COHORT_V2.json`。不新增初态，不增加repeat来凑50。
- 首要四组各20条：R_once、R_multi、Post_once、Post_multi。旧单次结果可对应时直接复用，实际只需新增R_multi20＋Post_multi20，共40条rollout；否则在同一轻量runner补必要单次对照，四组共80条。
- Velocity入口已就绪时可补once/multi各20条，首张R/Post表先交。总计划最多120条新rollout；含明确错误修复后一次重试上限160，不重复已成功样本。
- 只解除multi组的总干预次数上限，G0阈值0.05、监测间隔、历史成熟、合法cut、H10/C10、承诺执行锁、300控制步及终止规则均不变。不增加冷却、不强制触发、不改纠偏强度、不加Q接受门。每次用当前历史/队列重算，完成承诺后回到原监测规则；不在同一控制时刻零步反复触发。
- 模型/配置仍用旧standalone独立Post/Velocity及A4000；无需训练，无严格一致性检查、全树hash或独立预检。旧单次结果只做必要元数据对应，禁止把不同协议汇总当成同一20条结果。
- 继续最高优先级插队；N基线、已运行任务和B任务继续。常驻worker分卡执行，后台完成通知原执行会话。
- 立刻交20条的成功数/成功率、multi−once增量、Post_multi−R_multi、救回/损害，以及0/1/2/3+次干预分布、调用和耗时。每条成功相当于5个百分点；明确这是旧已揭晓20初态的开发小测试，不作全MT50结论。没有实际第二次干预时如实说明。

输出仍在 `results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/`，ACK/REPORT/RESULT写明revision2、n=20。若已按旧revision启动，停止接纳被取消的新增30源，保存实际已发生情况；不要为版本更新重跑有效旧20源。
