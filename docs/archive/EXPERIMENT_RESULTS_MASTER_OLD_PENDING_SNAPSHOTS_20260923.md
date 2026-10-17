# 历史待续快照：不代表当前实验状态

原文摘自总表，2026-09-23归档。其中“待填/尚未选择/运行中”等均为当时状态；当前终局请回到[实验数据总表](../EXPERIMENT_RESULTS_MASTER.md)。历史数值保留，禁止据此重启旧任务。

## 历史快照：Post-only覆盖前的总表状态

以下原文原样保留，不作为当前选型或运行状态依据；训练已完成与自动分工以本文顶部为准。

更新：2026-09-22，**取消Random-multi；先完成完整Q四损失训练/开发选型，再验证统一正式配置。** G0-multi仍为主线；现有L11 multi主表保留为历史/当前参考，所选Q尚未确定，不能将旧分数改名为新结果。已完成N、R、Random-once、E6和外部方法可复用。新科学任务已计划发布，本文不声称已经训练/启动。依据：[完整Q选型计划](../../sim_command/20260919/deadline_20260924/FULL_Q_LOSS_SELECTION_PLAN_V1.md)。

| 新阶段 | 节点 | 新首次评测 | 新Q更新 / 状态 |
|---|---|---:|---|
| 完整Q四损失开发选型 | A | 2400 | 48 fits×4000＝192000；尚待训练/开发真实回执，F9 |
| 锁定后四损失补充test消融 | A | 1200 | 原50已揭晓源；F9空表 |
| 所选Q五H Post/Velocity multi | A | 5000 | 固定fit9101；第1节新表待填 |
| 所选Q H10 Post/Velocity once | A | 1000 | 与同新Q multi配对；第1节新表待填 |
| Smol专属四损失候选及所选Q P/V multi | B | 1000 | 16 fits/64000更新；F8待候选与A选择 |
| X专属四损失候选及所选Q P/V multi | C | 1000 | 独立16 fits/64000更新；F8待候选与A选择 |

合计**11600新首次评测、320000新Q更新**；A9600/192000、B/C各1000/64000。A新阶段attempt≤10100，B/C各≤1100；累计cap A27000/B20000/C14000不重置，取消随机7500不抵消历史消耗。E6 multi100已完成（G0→R 26/50、D5→R 31/50，技术失败0），E3/E5已有CPU汇总保留，待新Q终局后更新配对与成本。LIBERO Full监督缺口、真机待用户交付均不混入新Q额度。

旧任务处置：A旧链已取消，[RESULT](../../sim_command/20260919/results/A/A_D24_MULTI_PRIMARY_VALIDATION_V1/RESULT.json)于15:52 UTC确认all_owned_descendants_exited=true；旧微调E1保留420/1200有效、未发780撤销，E6保留100有效，Random-multi进入0/取消7500。B旧专属once恢复收尾，C旧专属once1500已完成。B/C未进入的旧Q Post/Velocity multi暂缓，已进入单元保留；Q无关R可继续。B/C真实停止ACK尚未确认，不由A退出推断；取消/技术缺项记user_cancelled/unknown，不记success=false。

后续评测按[24 worker规则](../../sim_command/20260919/deadline_20260924/EVALUATION_CONCURRENCY_24_V1.md)优先每卡3 worker、八卡共24。容量不足须报告具体显存/RAM/CPU限制、每worker估计和实际可行最大并发；不无证据退回8。运行中队列不热改worker身份，原执行端排空自有族后切换。正式wave包含加载、间隙和尾部，全holder停算，整族退出后恢复。新准入9月23日20:00北京停止、表图23:00冻结；正常后台接续无需逐批许可，STABLE_HANDOFF后结束LLM等待。



## 历史快照：2026-09-22 16:48 UTC自动接续发布

以下旧待续状态原文保留；本轮终局以顶部2026-09-23记录为准。

更新：2026-09-22 16:48 UTC。**本篇最终表图只展示Post方法；Velocity实验继续做、原始数据完整保留，但不进入本篇导出。** 本篇入口：[PAPER_POST_RESULTS](../PAPER_POST_RESULTS.md)；另文入口：[VELOCITY_RESULTS_OTHER_WORK](../VELOCITY_RESULTS_OTHER_WORK.md)。本总表包含历史与另文数据，不能整表直接当作本篇最终稿。

共同loss只由四loss各自**完整Post development100上五任务×三fit等权成功率均值**选定，Velocity权重0并继承结果；精确并列先辅助项少，再L00/L10/L01/L11。固定部署fit9101四成员，不按dev/test挑fit，不按test调整loss或阈值。Post DEV未完整不能定赢家；授权Velocity DEV仍须执行，但不参与评分。依据：[Post-only覆盖](../../sim_command/20260919/deadline_20260924/POST_LED_SELECTION_OVERRIDE_V1.json)、[自动接续V2](../../sim_command/20260919/deadline_20260924/FULL_Q_AUTORUN_ASSIGNMENT_V2.md)、[活链兼容修正](../../sim_command/20260919/deadline_20260924/AUTORUN_LIVE_CHAIN_COMPATIBILITY_V1.json)；后两者中的旧共同评分或运行快照以最新覆盖决定为准。

| 节点 | 实际完成状态 | 已发布后续自动分工；尚不声称启动 |
|---|---|---|
| A | 48 fits、192000更新完成；DEV1546有效（Post775/V771），技术失败0 | 仅续DEV854（Post425/V429）→ Post-only选择锁 → test消融1200 → H10 multi P/V1000 → H10 once P/V1000 → CPU表图 |
| B | 16 fits、64000更新完成；旧once R/Post/V各500完整；R multi476有效、24用户取消 | Smol新Q P/V1000 → 原R最多24槽合法接续 → π0.5 H20/30 multi P/V2000 |
| C | 16 fits、64000更新完成；旧once与旧multi R/Post/V各500完整 | X新Q P/V1000 → π0.5 H40/50 multi P/V2000 |

完整Q **80 fits/320000更新已完成，全部候选复用、不重训**。A因授权切换正常排空，原`partial_or_failed`状态保留，技术失败0，不把它解释成模型失败；只续未进入源，不重放有效DEV。训练来源：[A TRAINING_COMPLETE](../../sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/TRAINING_COMPLETE.json)、[B FIT_RESULT](../../sim_command/20260919/receipts/B/B_D24_FULL_Q_LOSS_REFRESH_V1_FIT_RESULT_r1.json)、[C候选终局](../../sim_command/20260919/receipts/C/C_D24_FULL_Q_LOSS_REFRESH_V1_RESULT_r1.json)。

原首次范围仍**11600**：A5600（含DEV2400），B3000，C3000；不新增科学单元。A continuation剩余first≤4054、attempt≤4500；B/C native各1000/cap1100，转移π0.5各≤2000减A已进入项/cap2200。累计cap A27000/B22000/C16000，历史消耗不清零。B R取消槽先日志恢复，确无可靠终局才至多一次原协议接续，另记原R任务；不是新增初态，也不混入新Q1000。

新正式test须等采用当前Post-only规则的`SELECTION.json`/锁；B/C π0.5须再等A的[TRANSFER_READY](../../sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_HANDOFF_V2/TRANSFER_READY.json)精确未claim单元归属（当前为预定交接路径，未由文档确认已生成）。保留各自native唯一等待器，不因发布新分工重复launch。本次只更新分工和结果口径，未声称新continuation或转移任务已启动。π0.5用A对应Q，Smol/X用自身对应Q；底座、D/G0、动作/观测/随机流冻结。

已完成N、π0.5 R、Random-once、E6及外部结果复用。旧微调E1 420有效/780取消、Random-multi进入0/取消7500、原技术失败及旧Q结果全部保留。新Q空格不能移填旧Post/Velocity分数。LIBERO Full监督缺口、用户真机待交付仍未解决。

有限后台阶段自动接续并通知原线程；正常排空整个自有族后进入下一阶段，保持唯一claim，旧12小时等待期限仍生效。每卡3worker/八卡24是目标，实际不足据实记录；正式wave包括加载、间隙和尾部全holder停算、整族退出恢复。不增GPU预检或严格一致性审计。9月23日20:00北京停止新episode准入、23:00表图冻结。

