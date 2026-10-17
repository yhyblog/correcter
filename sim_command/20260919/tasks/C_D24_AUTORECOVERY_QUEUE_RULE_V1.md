# C_D24_AUTORECOVERY_QUEUE_RULE_V1 revision 1

C 发现器字段兼容补充：本任务实际绑定 `deadline_20260924/AUTONOMOUS_RECOVERY_AND_SKIP_AUTHORIZATION_V2.json`（SHA `0e0c6a309bf90c1d79d75d34a7d96470704c60e084c9b05b76621115341f82f7`）。V2 仅补充 nodes.C / thread_id / new_GPU_claims 元数据，下面 V1 的用户规则与范围完全不变；同一任务只部署一次。A/B 的 V1 绑定不变。

用户最新要求：故障时执行端自行修复并接续；需分析决定则报告，30 分钟无可执行反馈保留问题并继续不依赖它的授权任务。有独立任务可立即执行，不等满30分钟。

读取 `deadline_20260924/AUTONOMOUS_RECOVERY_AND_SKIP_V1.md`、`deadline_20260924/AUTONOMOUS_RECOVERY_AND_SKIP_AUTHORIZATION_V1.json`、`deadline_20260924/POST_LED_SELECTION_OVERRIDE_V1.json` 和 `deadline_20260924/AUTORUN_LIVE_CHAIN_COMPATIBILITY_V1.json`。这是伴随 CPU 控制任务，不替换本机原科学任务、授权、claim 或优先级；健康任务继续。

- 绑定本机 C / trial-303269581-trialrun-303269581-worker-0 / 原线程 01a0c793-10d2-7791-a250-fd65d88e1ccb。
- 私有实现/接入已有有限队列：故障分类、保留有效终局、按 unit 去重接续、有限有修复重试、issue 上报+1800秒计时、依赖无关任务跳过、完成/失败原线程事件。不另造科学试验或 GPU 预检。
- 规则必须实际可被本机下一阶段管理器消费，只有文档 ACK 不代表部署完毕；无需中断健康进程使其重载。
- Post完整开发集选损失，Velocity直接继承，固定fit9101；当前论文最终表图只用Post。无选模证据时不得跑所选配置test。
- A只接续原854未入DEV，不重跑1546或192k训练；B/C保留原native等待器与已完成64k训练，新π0.5任务接精确TRANSFER_READY所有权。以最新合法结果去重，854是派单时快照。
- 任务内CPU准备不消耗新增科学额度。必要技术接续计入已有科学stage/node预算；老的逐次等待批准流程由本次明确用户规则覆盖。超预算/科学决定等保留issue后继续独立项，不盲目死循环。
- 稳定执行后写STABLE_HANDOFF并结束LLM轮次，后台定时/回调继续；整波holder全停、整族退出再恢复。

写 `receipts/C/C_D24_AUTORECOVERY_QUEUE_RULE_V1_ACK.json`，交 `receipts/C/C_D24_AUTORECOVERY_QUEUE_RULE_V1_RESULT.json` 及短报告，列部署入口、issue目录、后台timer/event路径、实际已消费的Post选择规则和compat引用、当时就绪/等待队列。不把fake检查当真实恢复测试，不补跑测试来证明回调。
