# C_D24_QUOTA_INDEPENDENT_QUEUE_V1 revision1

用户额度即将耗尽：最高优先级完成本机**普通程序自动队列**部署，让既有所有剩余阶段在无Codex额度/离线情况下继续，不为任务发布打断健康计算。

读 `deadline_20260924/QUOTA_INDEPENDENT_AUTORUN_V1.md` 与 `deadline_20260924/QUOTA_INDEPENDENT_AUTORUN_AUTHORIZATION_V1.json`。沿本机当前科学任务及自主恢复规则，在已有队列上补必要缺口，禁止重建重复队列。先给ACK，完成后只交一次简短RESULT和 `results/C/C_D24_QUOTA_INDEPENDENT_QUEUE_V1/QUOTA_INDEPENDENT_READY.json`。记录实际本地后台PID、stage清单、无需LLM的自动衔接、纯CPU选择/依赖读取、回调失败不阻塞、有限重试/1800秒跳过和持久结果。不能仅做通知daemon便声称科学链已自动化。

本任务CPU控制面部署，新增科学单元/训练/预检0；科学计算沿各自现有授权/预算/去重。整波holder全停，Post-only选择先于所选配置test；V继续但另篇归档。先部署、少写长报告、结束LLM等待。不用等本控制任务分析验收再继续已授权科学工作。

## 本节点已发现的待闭合缺口

优先消除已知真实阻塞：NATIVE_FUTURE_ENTRY_GUARD.json记录原native旧waiter joint-score validator可能拒绝Post-only锁。不要只修未来manager却留旧waiter永远拒绝。使用实际Post-only CPU fixture修正私有接续验证器；确认旧CPU waiter未进入formal后可安全移交唯一waiter，保留原scientific claim/训练/去重/预算，不复跑任何fit或健康GPU任务。并把service异常后未完成unit接续、1800秒跳过独立stage写入普通后台程序；当前automatic_scientific_retries=0/已claim不能简单新launch的问题也需在无LLM情况下处理。

这是当前用户授权内的必要工程适配，请立即处理，不等分析再次确认；完成的项目直接引用既有证据。后台只能自动处理已编码故障；未知且无法程序解决的错误留存并跳到独立可执行任务，不将唤醒投递成功冒充自动恢复。
