# C新任务发现修复：分析结论与部署状态

2026-09-22。用户要求优化C领取；本报告由分析端定向读取控制服务得出，不涉及模型代码或GPU。

## 原因

B每15秒通过dependency_snapshot/observe_dependencies读取任务板及stage_authorizations；新依赖生成dependency_changed并投递原线程。C每5秒只检查已注册job退出/结果与outbox，当前R私有包仍仅扩展任务白名单，没有task_available发现。两端心跳均活跃（B10:50:28、C10:50:34 UTC），因此问题是监听范围缺项，而不是C服务器慢或轮询周期大。原线程queue已有ACK；离线exec-resume未证实。

C本次R派单10:35:32发布，10:47:19 ACK，相差约11分47秒；B10:38:23 ACK。该单次时间仅作现象，不是领取延迟性能基准。

## 已落实的安排

- 新纯CPU伴随任务：tasks/C_TASK_DISCOVERY_SERVICE_V1.md。
- 授权：deadline_20260924/C_TASK_DISCOVERY_AUTHORIZATION_V1.json，用户已授权，无二次许可。
- CONTROL69、TASK_BOARD102、队列CONTROL37已登记；C当前科学R任务保持优先，已收到ACK的状态已纠正。
- nodes/C/NEXT_TASK.json及DISPATCH_C.json保留R主任务，新增control_plane_followups；不覆盖科学任务或claim。
- 要求C在独立控制包加入task_available类型：5秒元数据检查、按C/task/revision/授权SHA去重、已ACK/完成不重放、固定原线程通知、ACK与传输分列、无ACK显式告警、任务结束后继续监听。
- 只切换本机CPU通知服务，保留jobs/outbox/历史ACK；不得动R正式进程、占卡或A/B。无需新的GPU测试。

## 首次部署入口仍需C本机接收

分析端在A尝试本地codex queue向C固定thread投递，返回exit1：no rollout found for thread id 01a0c793-10d2-7791-a250-fd65d88e1ccb。这是本机线程存储不含C原会话，非自动审批拒绝，未开启远程服务或替代对话。旧C notifier仅支持终局提示，不能把派单伪装成terminal绕过。

将nodes/C/TASK_DISCOVERY_ACTIVATE.txt内容发到C原对话一次。此为部署启动，不是请求重复授权。完成后以receipts/C/C_TASK_DISCOVERY_SERVICE_V1_RESULT.json和新CPU服务心跳确认部署；实际下一任务ACK验证自动领取。当前只证明修复任务已发布，尚不称服务已部署。
