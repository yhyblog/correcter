# B_LONG_TASK_WAKEUP_V1（revision1）

读取`persistent_queue/LONG_TASK_EVENT_WAKEUP_V1.md`及同名JSON授权。将完成事件与原执行会话唤醒纳入现有B_QUEUE_JOIN_V1 r2；本机可独立实现轻量触发器，不需等待A公共采集包。原join-waiter继续工作，收到包或对应依赖状态变化时可合并发一次本机事件，不以空轮询周期唤醒模型。

目标线程固定`01a0b9c5-1e4b-7b73-9336-229e6df349a2`，必须由B本机调用。不要在A侧连接B线程；不假定A的queue行为已证明B可用。验证本机固定UUID非交互resume/原session服务，同线程单写、持久outbox与handler ACK。

已授权CPU实现、定向fake检查、后台安装及最多2次短的原对话回调自检；不需另等安装批准。稳定交接后结束当前对话轮次，不长时间wait/tail。完成/失败/真实依赖变更事件唤醒原对话处理，之后继续已有授权的B11/独立CPU准备或已发布阶段。A475源与主线任务仍不属于B；不新增任何GPU训练/评测权限。

输出`receipts/B/B_LONG_TASK_WAKEUP_V1_ACK.json`、`_REPORT.md`、`_RESULT.json`，在node/B下保存wake机制READY/注册表/outbox引用和实际handler ACK。公共包未到不会阻止本任务独立准备和安装；若本机原会话服务有具体阻塞如实报告，不把queue消息ID称为唤醒成功，不用长期对话轮询替代。
