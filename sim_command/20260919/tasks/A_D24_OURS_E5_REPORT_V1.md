# A：本方法E5已有结果整理，立即执行

任务 A_D24_OURS_E5_REPORT_V1，revision1，owner A。根据用户2026-09-22最新“先本方法、后外部复现”要求直接开展CPU结果整理；不增加科学评测、训练或GPU推理，不等待B/C，不需要CPU_READY再批准。授权及调度覆盖见 deadline_20260924/OURS_FIRST_PRIORITY_V1.json。既有E6/E3/GAF已结案，勿重投或重跑。

## 具体交付

1. 复用 deadline_20260924/MAIN_FINAL_CELLS_WITH_COSTS.csv、MAIN_FINAL_STATISTICS.json、MAIN_FINAL_PAIRED_COMPARISONS.csv 与已保存主链逐episode标量，整理本方法N/R/Post/Velocity的E5论文表。已有汇总不是需要重做的实验；只补目前缺的口径和字段。先交π0.5 MT50完整16格，不等B/C终局。
2. 每格列有效episode/成功数/技术失败、policy_calls及其实际定义、完整采样数及flow（缺失保留null）、全体尝试均值、成功条件均值、摊销调用 Σcalls/Σsuccess，成功率并列。成功条件均值不能冒充摊销成本。均衡MT50用任务等权；缺失不填0，不借用别的方法补未知字段。
3. 推理计时沿保存范围：主链inference_seconds仅生成/纠偏，D/G0/context主要进入episode墙钟。分别给已有可用计时/可观测分母；可以计算相同范围的描述比率，但不能用episode减几个时间字段猜监测/纠偏净耗时，也不宣称整个系统加速。原主链尾部辅助holder与并发环境影响保持脚注。Σepisode time不是整波墙钟或GPU秒。入口P95/分阶段额外耗时未记录则明确缺项，不再跑计时实验。
4. 先复用 Corrector/docs/PARAMETER_EFFICIENT_CORRECTOR_PLAN_20260919.md 的已有参数口径与依据，不重新盘点全部权重。统计部署新增模块参数量：D、G0、Q每个成员及总ensemble、总新增唯一参数，并区分共享既有编码器/投影、基础VLA和新增训练参数。优先配置/已有shape/摘要；必要时只在CPU一次读取小模块state_dict计数，无模型实例/前向、无新大权重hash。共享参数不重复计数，不能把4成员当单成员。Smol/X底座规模已有可信配置可引用；不为补完整参数表加载几GB底座。缺项与计数范围写清，不预写“参数更少且最优”的结论。
5. 复用已保存配对救回/损害及区间，不重跑已有bootstrap；如补摊销比率区间，可对已有逐源标量一次固定seed CPU bootstrap，任务内同源配对。小表足够，不重建百万事件账本、训练日志或库存。E1/E6已有最终表直接引用，结果不支持的优势照实写。
6. 输出 results/A/A_D24_OURS_E5_REPORT_V1/ 中 PAPER_COST_TABLE.csv、PARAMETER_COUNTS.json、REPORT.md、RESULT.json；回执 receipts/A/A_D24_OURS_E5_REPORT_V1_RESULT.json。报告用中文给可用于论文的描述与不能声称的范围。只输出本方法，暂不做新的外部复现/外部计时排名。

本任务CPU；模型/环境/硬件探针/新rollout/optimizer/GPU推理/删除均0，不停止占卡。可写CPU分析脚本、读取必要小权重与已有实验标量；不要大量阅读实现或重做严格一致性检查。输出可立即交分析端，无须等B/C。若需要长CPU工作，沿现有后台/完成通知即可，不新建通用调度认证工程。不得改共享冻结包或B/C输出。
