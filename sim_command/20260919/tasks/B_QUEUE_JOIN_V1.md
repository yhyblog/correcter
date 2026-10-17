# B：一次接入持久队列，后续无需保持对话窗口

task_id=`B_QUEUE_JOIN_V1`，revision1，owner=B；依据用户2026-09-21指令与`persistent_queue/AUTHORIZATION_V1.json`。本任务优先处理接入，并继续已发布的`B11_COMMON_POOL_VIEWS_CPU_V1`及真实数据handoff；不是等待A每一批发消息。

只读`persistent_queue/README.md`、`QUEUE_CONTRACT_V1.md`及plan。核B本机host；A正在运行的Batch3仅属A，B不参与、不重跑、不使用其设备/claim。旧B11仍按原公共interface/sidecar/supplement与现16个接受父源做视图适配，原ACK缺失不得假称已完成。

公共程序将由A发布到`persistent_queue/package/READY.json`。如果尚未存在，设置仅监听这个固定、受总授权约束入口的后台join-waiter：独立session/断开stdin/文件日志/单例和有限频率轮询；READY通过身份/SHA/协议/测试证据检查后自动安装并进入本机控制面检查，不必保持当前会话等待。等待期间若无可执行任务，允许占卡。禁止泛执行共享目录中的任意新脚本。

绑定本机设备、环境、boot身份；本机科学模块、模型输入SHA和环境协议须匹配，差异导致B阻塞而非套A UUID或静默换版本。按合同完成纯CPU后台断会话/幂等/故障恢复测试，实际启动B服务并写`nodes/B/JOIN_ACK.json`、`DAEMON_READY.json`、heartbeat。总授权已包含这次安装和符合门限后的采集，不再申请逐批release。

B首次采集用自己固定顺序的第一个原计划父源、并发1通过现有加载/闭包/双repeat/退出/发布检查后，自动继续并发2、每批≤8；无额外短GPU探针。B最多250个pending源，按冻结顺序，不替换seed/源；每源15cold，Q-C10/G0-C5和s300不改。未来训练/正式评测未解锁。

本机有执行中或可衔接的已批准任务，全8holder持续停算；跨批维持一个reservation，不嵌套lifecycle，不在空闲GPU子集上占卡。没有可执行任务且所有owned后代/发布/清理结束后才恢复。不得终止无关进程；A与B使用独立node wave及退出屏障，共享存储预约互斥。

交`receipts/B/B_QUEUE_JOIN_V1_ACK.json`、`_REPORT.md`、`_RESULT.json`及B11实际兼容回执；明确daemon正在后台或join-waiter正在等待，不把等待文件当服务READY。提供一次启动/停止/状态命令及机器重启恢复限制。交付后后台队列继续，不自动停止。状态/结果持续写共享存储，后续无需聊天窗口保持打开。
