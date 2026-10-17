# A_QUEUE_BOOTSTRAP_V1 revision2：后台队列及八卡真实任务目标

先读原`tasks/A_QUEUE_BOOTSTRAP_V1.md`了解实施任务，再读`persistent_queue/GPU_UTILIZATION_POLICY_V2.md`、`INDEPENDENT_NODE_ASSIGNMENT_V2.md`与当前`persistent_queue/AUTHORIZATION_V2.json`。本r2取代r1中的并发2上限、A/B共同采集分工和V1授权引用。A独立拥有全部475待采集源，主方法数据视图/训练/主结果不能依赖B。不要执行已被新queue CONTROL替代的V1安装/派批入口。

当前Batch3完整保留原并发2和冻结流程；新queue-aware入口目标8张卡各1父源、最多8并行，按实际RAM/cgroup/VRAM/CPU/IO准入自动升并发，资源够时可直接8。不追加GPU试验，不逐级申请授权；只用原计划父源。B不再采集本轮共同池，改为外部方法/消融/适用性任务线。

保持单node预约贯穿可执行任务链，退出即补位，跨批不启动holder。有正式任务时所有holder停算；真正无可执行任务且owned后代/发布清理完成后才恢复。给出每卡利用率、空闲时间、CPU仿真/载入瓶颈的保存指标，不能用显存占用替代。

并发8的RAM/temp/CPU线程和共享容量准入需在实现中闭合；操作总预算/500源身份seed/15cold及所有科学规则不变，未开始源的owner统一A按SOURCES_V2。A不等待B部署或CPU兼容反馈，自己的D/G0/Q训练视图在A侧完成；完成采集后待一次冻结的A训练/评测配置，不建立B前置依赖。不修改正在运行的共享guard/旧launcher，不直接套旧launcher造成嵌套锁。

若r1 ACK/证据已存在保留，r2写`receipts/A/A_QUEUE_BOOTSTRAP_V1_r2_ACK.json`和`_REPORT.md`、`_RESULT.json`，避免覆盖。部署和控制面验收通过后daemon自动继续，不只交CPU_READY等待。实际READY/heartbeat记录当前V2总授权SHA。
