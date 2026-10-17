# Standalone 采样失败活动记录补充交接

2026-09-18T16:28:44.985996+00:00。最新窄日志缺口已修复；最终 CPU **145 passed / 0 failed**（含既有成本、预算、配对和统计检查）。真实模型/仿真/优化调用均为0。

每次 propose 开始建立新活动记录，在底层 native_action 进入前追加调用，返回或异常时保存状态、耗时和当前 hook 证据。采样前失败为0次，采样内异常和采样后 shape/schedule/first-action 校验失败均为1次。generate_solo 同时汇总已返回和失败 proposal；不把未知外部 stub 调用数填0，不沿用上一调用的活动。KeyboardInterrupt 保留原异常类型。

旧 fallback 两次采样都抛异常的合成 CPU 例证明可恢复2次实际进入；生产路径沿上一修订遇 GuidanceError 立即停止，无 fallback。成功路径梯度与采样运算 AST 在仅归一化已知日志包装/局部代理及既有 GuidanceError 处理后与旧实现完全一致；原 runtime 对象不替换。未增加 Q 门、采样重试或其他算法改动。

仅 engine.py 和 test_engine.py 更新，其余20代码文件、TASK/pending/科学合同、50预检+1274正式/1500新增cap/50000全局上限全部不变。旧封存和历史 CPU/交接保留。

- CPU：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/cpu_v5`；seal `0244e95c3c564678f407666f27f751ddb6c8b846d621745be475bfbdb286c18e`，包含22份受测源码和前后SHA。
- 新字段：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/handoff_v3/future_ready_fields.json`；SHA `eb1bb5737499de4ed4a8543a4c1b402e25a34b0b2595639978aeeca23f71ff51`。
- 修订细节与故障例：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/handoff_v3/revision.json`。
- 机器交接：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/handoff_v3/handoff.json`。
- TASK SHA `363c50bedcb04d93a5904bf7ecf9873d691974e7e67d82f3a419af4c0065ff5e`。
- engine.py SHA `73b2a0758cf5e281ff5ec5288ae747abf6bd6c3181aa011e00a22307bd18adaf`；test_engine.py SHA `e4883fc6d765e674e1965e38ceddbaf5628b89b67f738184e6eea7d65568a8cb`。

现有 READY v2 SHA `b023993688040473e3a8778dc2989c7d6c0041f4b3ee5fc2fca1639d83a2900c` 精确绑定历史 CPUv4。真实 metadata freeze 已正确拒绝用它运行本次修订，未创建freeze或计费；需将新CPU/代码字段精确绑定，既有科学范围与权限不变，无需用户重复许可。新未来字段中的36项实际授权引用已核SHA。

全局仍48183sim/51200opt，新增0，八卡holder保持。本报告不声称真实预检或跨实现数值配对已通过。
