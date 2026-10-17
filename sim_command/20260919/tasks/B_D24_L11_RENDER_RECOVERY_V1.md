# B_D24_L11_RENDER_RECOVERY_V1 revision1

用户已授权必要工程修复和未完成实验自动接续。此次分析处置详见deadline_20260924/L11_RECOVERY_V1/REPORT.md、ASSIGNMENT.md及AUTHORIZATION.json，不再等待逐批确认。

本机B唯一恢复清单：deadline_20260924/L11_RECOVERY_V1/RECOVERY_UNITS_B.jsonl，共1000原科学单元；追加attempt预算1100。固定L11/fit9101，不调loss/fit/阈值。A/C保存本次具体修复、观测/帧归属与干预前合法性证据后开始原缺项恢复；B用已成功π0.5独立环境进程/RPC路径直接接手原A H30，不等待其他节点。禁止在已知坏渲染路径上盲重跑。B只读提供现成可复用实现给A/C，不改原包、不停止他机。

保留所有旧raw结果与失败；先用已有日志补可恢复终局，已经有效的科学单元不得重跑。恢复不改变source/seed/candidate stream/单位/触发条件。新task/run/claim/output隔离。按清单owner而非旧owner执行，旧A H30原族已退出，正式归B；A不再恢复H30。三机无联合屏障。

24活动分支/GPU×8目标，合法观测优先；模型共享但环境渲染/队列/历史/随机流必须独立。首批计划恢复episode就是验证，不增加额外实验；保存少量实际RGB归属和错误日志，不做旧严格一致性流程。正式全波holder停算，整族退出后恢复。独立有限队列自动接续，故障私有修复；30分钟无科学决定继续独立任务。原截止时间有效。

先写receipts/B/B_D24_L11_RENDER_RECOVERY_V1_ACK.json，私有结果results/B/B_D24_L11_RENDER_RECOVERY_V1/；交修复记录、同一科学key原始尝试链、逐episode唯一可用结果与缺项、各cell汇总、真实并发/调用成本、终局退出恢复。完成事件绑定原thread 01a0b9c5-1e4b-7b73-9336-229e6df349a2。ready/实际进展后写STABLE_HANDOFF并结束LLM等待，后台继续。实际新完整结果未产生前不报科学完成。
