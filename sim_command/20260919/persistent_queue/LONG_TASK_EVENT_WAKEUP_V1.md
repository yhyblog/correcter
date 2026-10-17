# 长任务稳定后退出对话等待，终局事件唤醒原执行会话

用户于2026-09-21新增规则，适用于A/B所有后续长任务，也适用于可不改动冻结入口而挂接的当前任务。此规则减少对话中的重复等待和日志检查；不停止后台进程管理、超时、GPU占卡交接、资源监测、结果写入或异常处理。

## 稳定后立即结束当前轮次

执行端先确认任务由脱离终端的进程/session或现有daemon承载，身份/command/claim与输出日志齐全，并已有有效执行进展。可用首次有效里程碑或两次正常心跳间计数推进来确认，不只看PID存在，也不用等完整parent结束。后台完成触发器必须已安装并登记该job。

满足后写STABLE_HANDOFF，记录node/host/boot、进程身份、job/run/attempt、授权SHA、固定原会话ID、trigger/outbox路径及最近进展，然后结束当前对话轮次。不得靠长工具wait、反复sleep→tail或“仍在运行”的模型回复维持任务。若有其他已授权独立工作则去做，不为了等任务而消耗对话轮次。

## 完成与异常均产生持久事件

优先由后台runner的终局/finally处理器在已知退出、必要清理及最小结果落盘后原子写终局事件；已有冻结任务只加独立旁路observer，不能热改launcher、重启正式命令。observer优先消费现有终局文件/进程事件；必要时用低频OS轮询，不能让LLM轮询。

成功、合法partial、技术失败、启动失败、超时或异常阻塞都要通知。进程消失/心跳断联不是成功证据：写execution_unknown或blocked事件，保留无法证明退出/清理的字段，不重新执行原命令。OOM/监督器重启后从持久日志和进程身份对账补发缺失通知，不凭lease超时重跑。

终局event至少包含：schema、event_id、node/hostname、executor_thread_id、task/revision/run/attempt/claim身份、授权/代码引用、outcome、exit_code（未知null）、进程族退出/发布/占卡交接状态、结果和错误摘要路径、创建时间。没有人工审计报告时先引用launcher最小结果与日志，唤醒后由执行端完成审计，不让“必须先有人工REPORT”变成唤醒前置条件。

默认按整批/wave终局合并通知，不为每个step、heartbeat、15个child或8个parent各唤醒一次。紧急异常单独通知；普通进度只落后台日志。通知器本身、Codex回调完成或事件ACK不得再次触发同类完成事件，避免自唤醒循环。

## 固定原会话与实际唤醒

| 节点 | hostname | 唯一执行会话UUID |
|---|---|---|
| A | trial-303224955-trialrun-303224955-worker-0 | 01a0b91f-7443-71b1-915d-6cdb6d6a1a13 |
| B | trial-303225685-trialrun-303225685-worker-0 | 01a0b9c5-1e4b-7b73-9336-229e6df349a2 |

每台服务器只在本机向自己的原执行会话提交；B不通过A宿主的会话服务调用。禁止`--last`、新建替代对话、fork、模糊会话名、发给分析会话。保留原模型与权限配置，不加入跳过审批/沙箱的参数。

本机已确认存在`codex queue --thread UUID --message TEXT`与`codex exec resume SESSION_ID PROMPT`。前者只凭CLI返回不能证明关闭窗口后可唤醒；执行端应验证本机session服务的真实行为。对话已加载/忙时可通过原服务排队；未加载时使用本机已验证的原会话resume+新turn接口，或非交互`codex exec resume <固定UUID>`。argv/cwd/env和日志用结构化参数构造，不从实验日志拼shell，不输出认证信息。

同一thread最多一个写入者。检测当前会话/turn占用并尊重现有服务锁；已有写入者则将事件保持pending，不能强杀或并行启动另一个headless writer，也不能绕过锁。仅queue本身不支持离线唤醒时，须实现可工作的本机续接路径，不能只交“投递成功”。具体命令以各节点本地help和实测为准，不假定另一机器相同。

官方能力依据：OpenAI Docs [非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode#resume-a-non-interactive-session)说明可按指定session ID续接；本地help已确认queue和exec resume入口。具体app-server/session占用、关闭窗口后的唤醒链路仍需节点自检，本文不将文档能力冒充本机已部署。

## 投递去重与故障恢复

事件先持久化到host/node范围的outbox，再调用Codex。保存pending、transport_accepted、handler_acknowledged、handled/blocked等不同状态；`Queued message`、子进程启动、文件存在都不等于handler已处理。只有原执行对话写入绑定event_id的ACK才确认到达。

event_id稳定并绑定同一终局；重复投递允许，重复实验不允许。handler先原子领取处理权并查看既有handled记录、command/claim、当前授权/stop和queue已运行状态。网络超时或进程重启产生不确定投递时先对账；不得并发queue与resume去“碰碰运气”。通知层可有限退避重投，默认每事件至多3次传输尝试（30/120/600s间隔可配置）；无ACK且状态不明保留blocked/pending及原因，异常汇总落盘，不无限开启模型轮次。有新连接/明确服务恢复事件才重试该事件；不得因此重跑计算。

## 原会话醒来后检查并推进

回调只带event ID、job身份、简短outcome和少量结果路径，避免灌入完整日志/数组。原执行端核查：冻结身份与预算、终局/合法partial、真实退出及清理/发布/占卡交接、失败或缺字段，然后完成原任务REPORT/RESULT/审计、写handler ACK与处理结论。

若daemon已机器核验并开始下一批，对话仅复核和记录，不重复launch，不暂停其正常推进。若后续已授权任务需要执行端衔接，则启动一次、确认稳定、登记新的触发器后再次结束对话。正常同阶段daemon自动续批不新增“等对话ACK”的屏障；首次QUEUE8独立release与未授权训练/评测仍遵守已有门。执行未知/资源或协议失败走原异常规则，B失败不阻塞A。

## 一次接入与验收

将上述功能作为现有A bootstrap/B join的附加实施任务，已授权CPU实现、定向fake检查、后台安装及每节点最多2次短的真实Codex回调自检，不需要额外人工安装许可。自检只验证控制面：固定原UUID、对话当前轮次结束后能自动续接写ACK、断开交互窗口的路径、终局去重、忙会话单写、失败通知、通知器重启恢复；不得启动模型/仿真/正式job、重hash大权重或新建试验源。fake检查可合并覆盖，无须为每个case调用一次Codex。

真实回调自检消息明确synthetic=true，只允许原对话写回小ACK并结束，不运行实验；同一节点至多2个自检事件。自身当前turn运行时先登记好事件、交接并结束该turn，不用本对话原地等待自己被唤醒。实施完成交WAKEUP_READY及一次实测event→transport→handler ACK证据；仅CPU fake/帮助文档/消息ID不足以标READY。

无法安装或唤醒时报告具体服务/权限/锁/认证阻塞，保留后台任务和outbox，不恢复成小时级对话轮询；不把未实现规则说成服务已上线。窗口关闭与宿主/容器掉线区分；整机停机期间不能保证触发，恢复后对账未ACK事件。
