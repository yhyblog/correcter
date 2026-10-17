B 本机完成事件观察器，固定原会话 01a0b9c5-1e4b-7b73-9336-229e6df349a2。

启动/状态/停止：
/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py start
/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py status
/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py stop

start 幂等，后台独立session和本机 /tmp 单实例锁。stop只停止通知器，不停止guard、实验或任何会话writer。若STOP.json存在，先对账再人工/已授权执行端明确恢复，不盲删claim。主机/container重启需要重新start并对账outbox；未安装OS自启。

固定状态目录：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/persistent_queue/nodes/B/wakeup
正常周期15秒，仅轻量元数据；不会为空心跳唤醒LLM。只监测明确登记的整批终局和package/已放行B任务/阶段依赖的实际变化，不监测回调自身的结束。原join-waiter继续独立运行。

未来B runner启动并确认真实进展后，提交一次不可变注册JSON：
{"job_id":"B_unique_job", "task_id":"B_task", "revision":1, "run_id":"unique_admitted_run", "attempt":1, "claim_identity":{"path":"B_owned_claim","sha256":"..."}, "process_identity":{"hostname":"trial-303225685-trialrun-303225685-worker-0","boot_id":"...","pid":123,"start_ticks":123}, "result_path":"B_owned_terminal_result_path", "error_summary_path":"B_owned_log_or_error_path"}
/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py register --manifest ABSOLUTE_B_OWNED_MANIFEST
登记要求本机实际PID/boot/start身份存活；终局结果若可用需包含status、exit_code、all_owned_descendants_exited、publication_completed、occupancy_handoff_complete。进程消失且无终局不推定成功，写execution_unknown。每run/attempt至多一个终局event，后续审计改变结果字节不反复通知。

outbox先持久化，再dispatch。当前turn inProgress时保留pending；idle原TUI持有writer锁时只向固定UUID codex queue；writer锁正常释放时才codex exec resume固定UUID。没有--last、fork、替代会话、model/permission override或绕过规则参数。CLI自身writer锁是最终竞争保护，通知器不杀writer。原模型、工作区和权限元数据漂移会阻止通知准入。

每个通知事件有durable enter/owned process/exit和独立handler_ACK；消息ID、CLI exit0或投递accepted都不是唤醒成功。当前实现对可能已进入的投递不自动重发，保存delivery_unknown/transport_failed等待明确对账，最多3次的授权不代表必须重试。两次真实selftest各最多1次传输：001在本轮结束后用当前可用路径；002只在原writer自然退出后测试headless原UUID恢复。不会为测试关闭用户窗口或强杀TUI。

回调只包含event_id、task/run/outcome和路径。synthetic事件只允许原线程写小ACK并结束。ack入口检查CODEX_THREAD_ID、不同于arming turn的新active turn，以及该event_id确实出现在原turn用户输入；去重claim/ACK/handled。真实事件还必须提供B自有审计路径。示例：
/usr/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py ack --event-id EVENT --outcome selftest_ack_only
真实任务审计后使用audited_complete / audited_partial / blocked / execution_unknown，并传--audit B_OWNED_PATH。

WAKEUP_STATUS.json持续真实记状态；只有实际固定UUID headless恢复并收到原线程ACK后才生成WAKEUP_READY.json。TUI路径ACK单独记为已验证，headless还没发生时不宣称断窗口链路已验收。receipts/B/B_LONG_TASK_WAKEUP_V1_RESULT.json由观察器在证明状态变化时更新；消息投递本身不会标complete。DAEMON_READY与实验授权完全独立。
