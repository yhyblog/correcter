已消费自主恢复规则并部署独立 CPU 监督器，PID 2508712；READY、心跳和真实进程身份已核对。入口为本目录 START_CPU.sh，代码/接口见 CODE_MANIFEST.json 与 CONSUMER_INTERFACE.json。未修改 priority_authorization 或健康科学包，未发送科学停止信号，未改变 holder。

当前原科学链 ABLATION，快照 2026-09-22T17:52:08.377971+00:00 保存 24 个 MODEL_READY、24 个存活 worker。完整 DEV2400 已补齐；仅 Post DEV1200 选出 L01，部署 fit9101 固定，Velocity 权重为0且另文保留。TRANSFER_READY 已发布；原48fits/192000更新和此前有效DEV均保留。

监督器每15秒检查有限队列与依赖；工程故障自动通知固定原线程私有修复，通过 next_stage.consume 对准备好的隔离包做 unit/合法终局/终局日志/实际尝试预算/完整退出/选择门核对后进入原 lifecycle。同错最多两次有明确不同修复依据的接续；禁止盲目重启。科学问题写 nodes/A/issues，分析只投递一次；1800秒无可执行决定则 blocked_deferred，独立已授权就绪候选无需等满30分钟，无候选则记录 NO_RUNNABLE_TASKS 并继续有限依赖观察。

14项定向 CPU 检查通过，含真实小文件 collector、实际 next-stage validator、失败终局保留、partial job逐unit、固定期限、普通ACK无效、迟到决定安全边界、预算不重置及Post-only门。未注入真实故障，未做新的回调或GPU预检，不能把这些检查称为实测故障恢复。当前无issue/修复候选；新控制任务科学计算/claim均0，现有科学任务继续计其原账本。

独立 RESULT：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/A/A_D24_AUTORECOVERY_QUEUE_RULE_V1_RESULT.json。后台 READY/心跳、终局 outbox 与原线程已登记；本轮结束，不长等待，不重复启动。
