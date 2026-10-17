C X-VLA G0-multi V1

/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_XVLA_MULTI_EVAL_V1

已授权R/Post/Velocity各500；固定上一轮D2/G02/Q4。新训练、采集、N运行均为0。保留旧1000Velocity、5N补跑、5未知源，不重放。

单一service.py start创建独占claim，CLAIM存在时不重启。原formal.lock只继承不嵌套；整族退出后恢复原guard。STOP.json停止新准入；终止已有任务保留claim并等原线程审计，未知不得当作未开始。

source错误最多一次明确修正，自动重试关闭；仅重启通知不重启科学。到期2026-09-23T03:13:38.951469Z或全局撤销立即停止。

终局通知由C_TASK_DISCOVERY_SERVICE_V1_r1/wakeup.py固定原线程派送。后续回调核对小结果与全部后代、逐源claim，再ACK；无递归唤醒。

首个8模型与8外部encoder ready且真实episode终局后由服务写STABLE_HANDOFF，LLM结束等待。
