B 当前后台入口：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_QUEUE_JOIN_V1_r2_occupancy_v1/b_join_waiter.py

状态（在 B 本机运行；需要真实 /proc，必要时走 GPU/host sandbox escalation）：
/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_QUEUE_JOIN_V1_r2_occupancy_v1/b_join_waiter.py status

正常会话退出后不用再启动。当前 waiter PID 431242、独立 session 431242，启动身份已验证。固定轮询间隔30秒，只读当前CONTROL授权和固定 package/READY.json；仅在包文件/协议/计划/科学基线/占卡覆盖SHA及CPU测试/本机门声明通过后执行固定 SHA 覆盖的 B installer 一次。没有包时保持后台等候且不占formal预约。

如机器/container重启后需要恢复，先核对 nodes/B 的已进入命令、公共service和进程身份：
/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_QUEUE_JOIN_V1_r2_occupancy_v1/b_join_waiter.py start

这不是开机自启配置。start 幂等；任何 A_PACKAGE_JOIN.ENTERED 无明确完成结果时，unknown execution阻止自动重跑，应先对账，不能仅删claim或凭PID不存在重复模型任务。

停止仅此join等待器的新接入：
/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_QUEUE_JOIN_V1_r2_occupancy_v1/b_join_waiter.py stop

stop不停止已接入公共服务/任何模型任务/guard/无关进程。安装已进入会等待安装退出；服务上线后用公共包公布的本机服务停止命令。仅在明确恢复这个自有stop后：
/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_QUEUE_JOIN_V1_r2_occupancy_v1/b_join_waiter.py resume

本入口是CPU接入等待器，不是完整实验daemon。DAEMON_READY只能由真实部署且身份可验证的公共服务给出。没有A就绪依赖；B等待包不阻塞A。B collection_source_limit=0；阶段训练/正式评测只由一次冻结授权驱动，不逐job聊天审批。

当前CONTROL r3占卡覆盖已纳入包门：指定GPU在模型加载前确认自有holder及后代退出，活跃正式GPU禁止holder；监督空闲卡补位需独立记账，并在最终交回原guard前退出。该waiter本身不启动/停止holder；当前原guard持续8卡占用。公共包必须提交相应交接/单预约/资源8并发/补位/容量/失败隔离控制面证据。
