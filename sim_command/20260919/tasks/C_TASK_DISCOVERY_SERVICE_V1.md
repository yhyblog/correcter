# C 新任务自动发现与原会话通知

用户2026-09-22直接要求优化C领取机制。已授权C仅CPU实现、定向测试和部署，无需二次确认；这是当前R科学任务的控制面伴随项，不替换、不重启或阻塞R的5000回合。

## 已查明的问题

B的wakeup服务每15秒检查任务板/新stage_authorizations，生成dependency_changed。C存活的服务每5秒仅检查已注册job终局和outbox；当前私有R新版也仅增加任务白名单。C没有新派单发现，不能靠缩短终局轮询解决。当前queue原线程ACK有证据，离线exec-resume仍不能仅据queue成功宣称验证。

## 最小修改与部署

1. 在C私有控制包中为notifier增加独立task_available事件，复用当前可靠的原线程transport；不要把派单冒充科学terminal，也不另建第二个争抢原会话的通知器。保留旧jobs/outbox/delivery/handler_acks。部署只切换C自己的CPU控制服务，先确认原服务身份和退出，再启动唯一服务；不动科学worker、supervisor、formal.lock、holder或A/B。
2. CPU每5秒读取小元数据：nodes/C/NEXT_TASK.json、DISPATCH_C.json、TASK_BOARD.json、CONTROL.json及persistent_queue/CONTROL.json。只对C已发布且尚未领取的合法授权任务发通知；必要CPU伴随任务从control_plane_followups或任务板读取。读取瞬时缺失/半写入时保留旧状态、稍后再读；这不是撤销任务。
3. 科学派单需节点C、task_id/revision和引用authorization一致，授权在当前CONTROL登记且未停用，状态ready/running或明确已发布；旧关闭/取消/延后/已完成/已ACK或已有claim不重新执行。通知器不创建科学claim，不运行launcher，不因此扩预算。控制面伴随任务的计算权限严格为0。
4. 去重key=(C,task_id,revision,authorization SHA)。全局CONTROL版本改变、其他节点更新、心跳和统计变化不重复叫醒。同一任务内容若未经revision变化不得静默再执行。ACK/完成/撤销实时抑制未投递事件，恢复进程后沿用已持久化状态。
5. 专用task_available消息明确给出任务书、授权、当前科学任务与是否伴随CPU，要求执行端先写新ACK，再在既有授权范围完成；当前科学队列照常后台运行。新GPU任务只能在本节点现有正式队列退出后衔接，不能因此开第二个wave。
6. 当前对话忙时只queue一次；空闲时沿本机已支持的固定原线程原生resume路线，遵守会话锁，保留原权限/模型/配置，不用--last、不另建替代线程、不绕过锁。目标固定01a0c793-10d2-7791-a250-fd65d88e1ccb，host固定trial-303269581-trialrun-303269581-worker-0。终局旧消息缺ACK不能无限饿死合法新派单；优先核查已有原线程处理证据，保留uncertain标记，不伪造ACK或盲重发。
7. 记录detected_at/transport_entered/transport_accepted/handler_ACK；transport成功不等于领取。5分钟无ACK写DELIVERY_STALLED及心跳原因，禁止高频重发和长期LLM轮询；后台继续轻量检查，通知重试不会重复科学launch。
8. 保持daemon脱离终端，host+boot+PID start_ticks与单例锁。服务在科学任务结束后继续发现任务，至2026-09-23T15:30:00Z停止新派单监控；12:00Z后不得引入新的科学实验，已有任务/必要CPU收尾遵循各自授权。容器重启不得假称服务自动恢复。

## 验证与交付

仅做少量CPU/fake：新合法C任务触发一次；同任务重复扫描/重启去重；B更新无触发；旧/已ACK/已完成不重启；停用/错误授权拒绝；元数据临时缺失安全；忙会话只queue一次；专用dispatch提示不误报终局。无需Torch/GPU、全套历史检查或新增科学测试。

部署后两次轻量心跳证明服务存活；实际新派单的原线程ACK才可证明自动领取。可用本伴随任务的真实通知/ACK闭环，不新增递归唤醒自检，不延误R评测启动。已有C_D24_R_TRIGGER_MODES_V1_ACK必须作为去重正例，不能重新启动该科学任务。

交付receipts/C/C_TASK_DISCOVERY_SERVICE_V1_RESULT.json及短REPORT.md，列准确代码/服务入口、旧新服务身份、检测与去重检查、后台心跳、投递/真实ACK证据；若尚无真实新派单验证，明确“部署已完成，端到端下一派单待验证”。同步更新C自有控制README，分析端负责共享板。

科学模型/环境/GPU/holder调用、额外episode、训练/删除均0。本任务不修改任何冻结科学算法、随机表、源表或预算。
