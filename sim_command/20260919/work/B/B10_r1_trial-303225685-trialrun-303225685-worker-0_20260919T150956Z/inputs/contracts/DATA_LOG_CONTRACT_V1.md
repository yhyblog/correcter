# 公共数据与日志合同 v1

本文件规定字段语义；序列化格式由A10在无GPU准备阶段落实并用样例与B10对齐。字段缺失使用null和missing_reason，不能伪造0。存大对象可用不可变路径引用及SHA，不要求复制巨量图像。

## 1. 训练原始轨迹

必需身份：dataset_revision、split、task/instruction、parent_episode_id、source_id、branch_id、suffix_id、collection_policy/checkpoint、seed、step、H、generated_length、executed_prefix_length。

必需内容：observation/ref、proprioception、next_observation/ref、raw_action、normalized_action或可重建的normalizer版本、generated_chunk/ref、executed_actions/ref、reward序列、success序列、first_success_step、terminated、truncated、cut_reason。

终局候选bank补充：anchor_id/a0、candidate_family、raw_alias_group、suffix_seed、terminal_success。gain/pair通过真实源/候选/后缀关系构造，不跨不同源比较。

视图manifest：method/version、原始数据manifest SHA、selection_rule、parent/source/transition数量、目标/折扣/动作窗口、feature/normalizer版本、使用历史初始化及其数据沿革。各方法视图可不同，公共可访问数据池相同。

## 2. episode结果

campaign/task/run/node/host、method_version/checkpoint、env/version、task、initial_state_id、parent/source_id、train_seed、generation_seed、suffix_seed、H、C、split、success、first_success_step、termination_reason、technical_status、executed_steps、intervened、cut_step。

无报警源在分母中保留；技术失败按failure表保留，不写成成功/失败二值假标签。不同H的源轨迹/cut另记，同H比较保持对应身份。

## 3. 事件

episode_id、event_id、event_type、decision_index、sampling_index、environment_step、entered/returned/failed、wall_start/end、device_elapsed、timing_parent_id、is_deployment_required_for_methods、is_research_only、GPU/worker/concurrency/precision/batch/warmup。

event_type至少区分natural_plan、intervention_decision、anchor_sample、guided_sample、flow_forward、vla_backward、critic_forward/backward、monitor、action_transform、env_step、restore、audit_io；可合并高频记录为带时间范围的计数块，不能丢真实数量或服务方法归属。

chunk记录：chunk_id、计划H、实际执行长度、终止原因（自然耗尽/报警/成功/环境终止/预算）；尾部未执行动作不计控制步。

## 4. 双账本与复用

experiment_actual：本轮真正执行的采集/生成/恢复/优化及GPU资源，包括失败，不能因为结果复用又计一次执行。
deployment_reconstructed：每个方法每条episode应承担的prefix＋own entry＋own suffix；共享入口不除以后缀数，共享前缀不让其他方法承担。
同时记录prefix_id、entry_generation_id、suffix_run_id、reused_from及原成本事件引用。重建时间是估计；不和实验实际墙钟混为一个指标。

方法入口耗时可含子阶段，汇总时按区间/父子归属避免重算。N中的shadow监测是研究成本；R/P/V的在线监测属于部署成本，包括无报警episode。

## 5. 机器与结果身份

绑定code snapshot/commit、config SHA、data manifest SHA、model SHA、driver/runtime/GPU、hardware role、host shard、wave_id、正式release。
跨机分片不重复source；同源方法在同机执行。P95等延迟指标按约定计时子集计算，不混入其他GPU型或并发条件。
