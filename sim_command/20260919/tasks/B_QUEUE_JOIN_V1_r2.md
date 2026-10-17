# B_QUEUE_JOIN_V1 revision2：一次接入与八卡利用率目标

本r2替代`tasks/B_QUEUE_JOIN_V1.md`中的共同池采集任务、并发2上限和V1授权引用；其余一次接入、后台join-waiter、B11视图工作、节点身份和恢复规则继续。读取`persistent_queue/AUTHORIZATION_V2.json`、`GPU_UTILIZATION_POLICY_V2.md`及`INDEPENDENT_NODE_ASSIGNMENT_V2.md`。本轮475共同池源全部归A，B不领取其中任何源；V1的B250与首parent采集计划取消。

无需长期保持对话窗口：按当前总授权验证固定公共包、部署独立session/supervisor并完成CPU断会话测试。A包尚未发布时将受限join-waiter后台化，不能把它当DAEMON_READY。

B转为独立任务线：外部基线E3、五任务E1/E6消融、Smol/X-VLA＋MetaWorld及π0.5＋LIBERO适用性E8。先完成B11及`B_INDEPENDENT_PIPELINE_PREP_V1`的隔离CPU准备；当前没有训练/评测GPU额度，须在各自一次冻结的阶段方案发布后后台自动执行。届时根据真实资源以8卡并行已批准的种子/方法/评测分片为目标，不增加GPU诊断源。缺输入只阻塞对应B任务，执行本机其他已就绪任务；不得暂停或等待A为B提供人工ACK。

连续任务之间维持node预约，全卡holder停算；没有可执行任务且全部owned后代、发布和清理完成才恢复。保存每卡实际利用率和空闲时间，记录载入/CPU仿真瓶颈，不能在任务期间用holder填空。与A仅共享存储短时记账事务互斥、容量预约可并存，不参与当前A Batch3。

保留任何r1回执；新写`receipts/B/B_QUEUE_JOIN_V1_r2_ACK.json`和`_REPORT.md`、`_RESULT.json`。实际后台服务就绪后持续自动续批，不因交付回执而停止；训练/正式评测/删除仍未解锁。

已观察到B有V1 join-waiter，它固定读取V1授权，不能自行消费V2。此次已授权完成一次CPU迁移：先按host/boot/PID/start_ticks核对本任务自有waiter，仅停止该旧waiter，再部署V2或支持当前授权修订的入口并以独立session启动。保留旧日志/回执，不停止无关进程，不重启guard；不能因旧PID alive就宣称V2已就绪。CONTROL切换后旧waiter的gate_blocked不是A阻塞条件。没有GPU可执行任务时不持有正式预约。
