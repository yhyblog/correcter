# Standalone失败路径修订交接

2026-09-18T16:15:16.939919+00:00。仅更新新隔离目录`engine.py`、`test_engine.py`，原冻结及此前证据保持只读。

1. collection当前两个导入均为`reference_generation`，其中`compare_archived_identity`显式alias为`audit_archived_identity`；已有实际采集器合成测试覆盖solo和reference路径，不存在早期导入缺口。
2. `GuidanceError`现在单次采样失败后立即清hook并抛出异常，不再调用额外无引导采样。保留失败那次policy call、部分forward/backward/times/noise、耗时与峰值；入口合计成功返回与失败调用。未知计数用null明确表示，不填0。外部stub若报告重试，证据如实记录true；入口不重试。
3. 成功`propose`除唯一异常handler外AST与旧方法严格一致；方向、梯度目标、raw/mask/半径、种子及成功路径1/2/2不变。NaN/Inf仅在错误证据中显式编码，不新增科学容差。

最终CPU **136 passed / 0 failed**，`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/cpu_v4`，seal `b014ced62ba7f2f086caa3db565140a47c6f449cd1668b72ef16f76b9a33855f`。包含真正提取production propose AST的fake-runtime/CUDA故障注入，证明一次native_action后停止；不是仅检查stub。22文件测试前后SHA一致，完整受测代码已归档到CPU目录tested_code。

- engine SHA `8787c21c13a5f61485f09685346f16242022d4640bd507592791a35276a3c9d6`。
- test_engine SHA `ca9c46c99725070ecb52bb428024c7fb5e0b2255a726a927559a27bf0249350e`。
- TASK `363c50bedcb04d93a5904bf7ecf9873d691974e7e67d82f3a419af4c0065ff5e`、原pending及科学release合同完全不变。
- 50预检+1274正式=1324，阶段60/1400/锁40、总1500/0优化、原50000上限不变。
- 新future READY字段：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/handoff_v2/future_ready_fields.json`，SHA `58561a03c7710ad04edc81ae917fa2d7e24b59af3a05d23ed4c8c8e84654be0a`。

并发发布的READY v1 SHA `1223e6b00f15e77b4714d13edfa37c5b2a547a4bc7fa71d0bf7a545882cfdb4e`绑定旧cpu_v3/旧engine/test。新freeze入口已真实元数据检查并拒绝此不匹配，未生成freeze、未启动模型/环境。请仅重绑新CPU和两文件SHA；无新方法/范围/预算或用户权限要求。旧v1交接保留历史，新handoff_v2用于正式入口。

实际新增model/sim/opt均0，全局仍48183/51200；八卡holder=True。8臂统计及三solo−R共同主比较保持原TASK。
