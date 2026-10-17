# C_D24_PI05_SELECTED_H40_H50_V1

owner C，revision1。用户已授权把剩余任务自动串联，并再次强调先完成消融选配置，再跑正式实验。当前任务是既有11600范围的重分配，不新增训练/采集/科学矩阵。

完整安排：deadline_20260924/FULL_Q_AUTORUN_ASSIGNMENT_V2.md；授权：deadline_20260924/FULL_Q_AUTORUN_AUTHORIZATION_V2.json（SHA fb15e23ad4ed75eaa1b9490784d58dc9dc925e440194e99cab066ae11af6414f）。必须读取原FULL_Q_LOSS_SELECTION_PLAN_V1、并发24规则及OWNERSHIP_PLAN_V2。

现在私有CPU准备已授权π0.5所选Q H40、H50×Post/Velocity×原500=最多2000，由A原MAIN转移。保留唯一原X新Q选择等待器，不能重启该1000或插入另一份模型训练。A的完整开发选型锁到达后，原X P/V1000自动执行；其本机全族退出后，且TRANSFER_READY确切授予本节点未claim源，自动执行π0.5H40、H50两H。使用A所选π0.5 Q（fit9101），不要用本机XQ。π0.5保持A NVIDIA/30Hz/.015/raw50/NFE10与所有动作/种子；仅做必要适配、首计划episode验证，无新GPU预检。cap2200，累计16000。

目标每GPU3worker/共24；资源不足报告实际限制和可行最大并发。每阶段有限后台、唯一claim、结果先落盘、整族退出和恢复、完成/失败事件原会话自动处理。常规已授权下一项不用再问权限，不在LLM中长轮询。所有阶段受原截止和12小时有限范围约束，依赖未满足保持轻量等待和占卡恢复，不能提前正式评测。

交receipts/C/C_D24_PI05_SELECTED_H40_H50_V1_ACK.json、_RESULT_r*.json及results/C/C_D24_PI05_SELECTED_H40_H50_V1/QUEUE_READY.json、具体ORDERED_STAGES.json、STABLE_HANDOFF。只有真实部署后才能写已自动续跑；投递不代表ACK/launch。共享CONTROL/BOARD/总表仅分析写。
