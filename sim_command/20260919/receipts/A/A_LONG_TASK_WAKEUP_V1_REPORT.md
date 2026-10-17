# A_LONG_TASK_WAKEUP_V1 实际部署回执

状态：旁路已部署，原会话回调待验证。没有发布 WAKEUP_READY。

现有 D24 主链持续运行；保存进展确认 8 个已加载 worker 活跃，原先有效 episode 里程碑及本次心跳已归档。新 CPU observer PID 1362117、独立 session、PPID=1、stdin=/dev/null；启动命令已退出而后台仍有新心跳。STABLE_HANDOFF 已记录固定 A 原 thread、正式命令、授权、进程身份、trigger/outbox 和保存进展。本轮不重启或修改正式 launcher、不新增模型/硬件调用。

10 项定向 CPU fake 检查通过：实际 deliver 序列化、忙会话只排队一次、保留 native resume 机会、活跃 resume 不并发、三次总上限、错误持久化、ACK 身份/challenge、重启去重、失联不推断成功。旁路只拥有自己的 outbox；正式主链现有 notifier 继续独立拥有其终局通知，无重复转发。旁路补一条合并的 supervisor 消失/心跳异常通知，未知退出、发布和占卡状态均 null，不据此重跑。

实际 synthetic 自检额度已登记 2/2：第 1 个既有事件三次 queue 被接受但无 ACK；第 2 个事件延迟发送，先 queue 一次，若仍无 ACK则等原会话写锁释放，再在原 UUID 上有限尝试 native resume。Queued message 不算唤醒，旧 startup ACK 是活跃会话主动读取，不计离线验证。只有匹配 event_id/thread/challenge 的实际 handler ACK 才自动生成 nodes/A/wakeup_adapter_v1/WAKEUP_READY.json；该文件也明确物理窗口关闭测试未知、宿主重启未验证。

本机默认 app-server proxy socket 缺失，未创建替代 app-server，也未绕过单写锁。非交互续接能力依据[官方文档](https://learn.chatgpt.com/docs/non-interactive-mode#resume-a-non-interactive-session)及本机 help；这些不作为本机实测成功证据。当前原会话写锁仍忙，后台保留 pending。主机/容器重启后的自动拉起没有验证；恢复须先按持久身份/ACK 对账，绝不自动重跑实验。

接下来结束本轮等待。后台科学任务、超时/占卡监督和通知继续运行；后续真实事件由固定原会话检查最小终局/退出/发布/占卡结果，补回执；若 daemon 已续任务，不重复 launch。旧 475 源采集仍关闭。
