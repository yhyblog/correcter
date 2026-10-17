A_D24_CORE_REMAINDER_V1 滚动回执（2026-09-22T04:33:59.441226+00:00）。E6完成；E3部分执行后记录失败；GAF输入缺项。原8000主链及120pilot均未重跑，未恢复475采集。

| E6单元 | 实际episode | 成功 | 报警/干预episode | sampling / flow | episode耗时合计 |
|---|---:|---:|---:|---:|---:|
| 既有100dev N旁路 | 100 | 52（未用于定阈值） | 干预0 | 1814 / 18140 | 941.674秒 |
| G0→R test | 50 | 26（52%） | 46 | 973 / 9730 | 485.104秒 |
| D5→R test | 50 | 30（60%） | 45 | 884 / 8840 | 440.741秒 |

100个旧dev身份均纳入，异常阈值0.2521600950570383，严格大于，匹配95/100个G0报警episode；定阈值未读success。测试为五任务ordinal10..19，同50源双臂；D5单独成功5，G0单独成功1，共同成功25、共同失败19。技术失败0、更新0。仅此五任务小样本证据。完整逐源记录、阈值及逐task表在 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_CORE_REMAINDER_V1`。`E6_PER_TASK_CELLS.csv`是正确逐task聚合；原`SUMMARY.json.tasks`仅保留末分片，不用作task总数。

E3现成epoch30 VLA-Corrector使用原生逐步safety/动态阈值、cooldown10及重复干预，没有套G0 once；旧训练覆盖单独披露。第一次启动在模型前因库路径绑定错误停止（0模型ready/0episode）。一次纠正重试r2真实8模型ready，共进入47个固定源：39个结构化RESULT（成功12）；另外8个在终局摘要写JSON时抛NaN错误，全部worker退出3，不能将原汇总technical_failures=0解释为整波无技术失败。原生未定义恢复统计NaN与严格记录器不兼容，未见模型/动作NaN。8条已有终局进度的成功布尔可由原代码累计成功率公式唯一推导为true，已单列`E3_RECOVERED_TERMINAL_PROGRESS_V1.json`供分析接受；不偷偷并入39行，不重跑，不补造缺失采样/flow/耗时。

CPU最小补丁将合法未定义统计写null+原因，先保存核心终局，再保存可选摘要；原生真实摘要函数定向6检查PASS，未知NaN/infinity仍拒绝。补丁与453个尚未进入源表位于`repairs/native_summary_json_v1/`，未安装/未创建第三次launcher。当前已用一次job修正重试，r2 retry_remaining=0；已向分析交付明确边界，未自行第三次正式启动或改种子。

GAF未fit、未eval、更新0。现有公共池视图只有train；旧dev完整suffix有actions/success/physics_states，但缺连续窗口的实际policy_state4/观测引用及绑定变换。真实physics_state函数保存qpos/qvel/act/ctrl/warmstart/mocap/userdata/time，不是观察到的策略4维状态。`GAF_INPUT_STATUS_r2.json`给出窄证据链；不声称全树穷尽，也不以test、伪造观测或新采集填缺项。

本次物理attempt累计247（E6 200+E3 47），接续上限3000未重置；D24 A已知累计8367（原8120+247），上限18000。正式三波的holder退出ACK均早于首正式worker，期间全部8卡holder停算、辅助holder0；三波整组及后代均退出，分别恢复8holder，末次恢复04:25:27.861 UTC。无训练/删除/无关进程终止。当前没有稳定在跑的科学链，不写虚假的STABLE_HANDOFF；后台通知器空闲，终局ACK按event_id去重。
