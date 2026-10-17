# 执行端回执合同

分析端只读本合同约定的摘要和表格；不要求回传实现正文。

## 任务领取与身份

ACK JSON字段：campaign_id、task_id、task_revision、node_role、hostname、executor_session_id、started_at_utc、control_revision、allowed_scope、inputs_checked。

identity.json字段：role、hostname、session_id、workspace_path、shared_mount_check、GPU型号/数量、环境摘要、机器本地checkpoint缺口、occupancy状态来源。不要记录密钥、令牌或整份环境变量。

## 最终回执

RESULT JSON字段：

- campaign_id/task_id/revision/role/hostname/session_id；
- status：complete、blocked、failed；ACK或running另用单独状态文件；
- started_at_utc/finished_at_utc；
- input_identity：protocol/code/config/data/model的path与已核验SHA；未知写null并解释；
- artifacts：短报告、表格、日志、checkpoint及完整manifest路径；
- resource_counts：simulator_attempts、completed_rollouts、vla_sampling_calls、optimizer_updates、gpu_seconds；审查任务填0，未知正式用量不填0伪装；
- failures_and_retries：包含失败命令/退出码及恢复；无失败为空；
- findings：最多10条关键结论；
- blockers：具体缺口、影响任务、建议解法；
- next_task_proposal：仅建议，不能自行改任务板。

报告MD先给可用/缺口表，再说明工程建议、数量与证据路径。不要复制整文件代码、历史聊天或冗长日志。可引用少量相关行号。

## 发布规则

每个task/revision/run使用独立文件名。先写完整临时文件再在同一共享目录原子替换；完成产物后最后写RESULT。仅写本节点目录。最终结果后追加修订回执，不悄悄覆盖旧结论。

运行中每个子批次或约60秒更新本节点心跳（实际执行器适合时），附当前任务、PID及启动时间、进度计数。心跳过期不表示允许他机抢占。

B没有对A会话的直连能力，文件即正式回报。A可按当前启动任务书通过本机queue发送回执路径；queue成功不等于分析验收，也不等于正式GPU任务放行。
