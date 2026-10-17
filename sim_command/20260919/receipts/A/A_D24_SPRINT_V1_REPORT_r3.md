A_D24_SPRINT_V1 / N2500：八卡持久后台评测已实际运行。

本会话明确用户批准已保存。实际supervisor PID1270859，父PID1；8个worker均已完成严格SFT030000加载，8个不同物理UUID核对通过，并持续自动取下一task/H job。当前只执行N，固定50任务×10个新test初态×H10/30/50/20/40，上限2500episode；不含训练、P/V/R、删除或475源采集。

截至2026-09-21T16:10:00.053674+00:00：已保存273个episode终局（273正常终局、0技术异常），仍有8个worker运行。此为进行中快照，不是完整矩阵结果，不提前计算论文排名。一次实时利用率快照各卡[43.0, 49.0, 46.0, 54.0, 61.0, 62.0, 46.0, 62.0]%，均值52.875%；该值不是时间平均，也不保证持续下界。

全8holder已在正式进程创建前停算；同一formal.lock预约由原guard授予，supervisor保留同一FD副本，无嵌套二次加锁。整个可执行任务链内持续预约，所有后代退出和结果发布后才统一恢复holder。CPU控制service独立存活；B脚本由B自行执行，A未部署B。

原自动审批拒绝及随后一次前端元数据失败均保留：拒绝命令未执行；元数据失败没有daemon/claim/计算。用户明确批准与baseline_N继续字段修正后，唯一实际formal chain已启动。旧关闭release未复用。

查看 deadline_20260924/A/HEARTBEAT.json、SUMMARY.json、runs/*/RESULT.json。后台继续衔接，不等待分析逐批release或聊天。结束/失败通过固定原会话outbox通知；控制面自检已transport accepted，handler ACK与物理关窗口唤醒尚未观测，不能冒充完整唤醒验收。
