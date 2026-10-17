# Standalone 有界运维修复交接

2026-09-18T16:46:22.151750+00:00。原失败 standalone_v1 完整保留、不可运行。新工程准备通过，当前真实模型/仿真/优化均0。

一次全量继承审计覆盖 **1702文件及1个9,354,050,752字节权重**，只有外部 gpu_occupancy_lifecycle.sh / gpu_occupancy_guard.py 变化。科学实现和权重保持原SHA。两脚本旧正文从旧heldout真实tar提取并核原SHA；当前正文单独保存，真实diff只增加holder占用参数 .50/.20。当前新增完整运维闭包还绑定 gpu_hold.py、原wave脚本及 /usr/bin/true；不为旧快照缺失的holder编造历史SHA。旧全局文件与旧freeze不改。

新protocol仅在显式白名单内替换这两个运行SHA；旧freeze、旧正文与历史位置另行保留。缺少原依赖、科学漂移、大权重不符或未列明runtime修改均拒绝。新READY枚举旧/新证据真实文件引用，future字段51个唯一引用的原件及副本SHA均已核。

预检八设备槽：0–4仍各一个原supervisor与源；5–7仅`/usr/bin/true`，无模型、环境、源或attempt。仍5源50次。正式八卡四worker共32不变；严格审计全部job命令、rank、源与空槽零工作契约。真实旧wave工具在mock子进程CPU例中已接受八槽spec，不改全局wave。整波仍一次lifecycle；退出释放后holder为guard异步恢复，实际结束后需核8holder，不能仅凭命令退出声称恢复完成。

**本次必要CPU：86 passed / 0 failed**，仅4个受影响测试模块；此前cpu_v5的145项科学/日志测试证据沿用，未重复运行。24份当前代码/测试/脚本前后SHA一致。只改5个prepare/runner/audit工程及对应测试文件，新增operations与测试；engine/candidates/collection/reference/statistics/protocol/storage身份不变。

- 新pending：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/pending/operational_v1`，seal `de1ac02e0374b52899a4d38f76cb2750189ff6dedec740edd44fb4e97d6bac93`。与原pending仅增加operational_runtime字段。
- 运维来源包：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/operational_repair_v1`，seal `2ced1eecc5139d3a02a2e1fcff1140a600d28e17ad652619d15d65cb6b91da4a`。
- CPU：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/cpu_v6`，seal `5d53cb699f6b1b142a366168d25679bd44ea359b8d3f73a2401869715877bd1f`。
- 新完整future字段：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/handoff_v4/future_ready_fields.json`，SHA `46f9ee7da5b431bf9e10eabe2d55d6c48d20091c98a2f0fede5837edec1128fc`。
- 机器交接：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/preparation/handoff_v4/handoff.json`。

原科学契约逐项不变，仅增加独立operational_runtime引用；计划50+1274=1324、新cap1500、repair锁、全局50000不变。live v3不匹配本次新工程，尚未尝试新freeze或wave。分析端精确重绑后使用新version目录，不能覆盖失败standalone_v1。当前全局48183sim/51200opt，8holder保持。
