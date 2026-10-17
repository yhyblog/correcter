# 第一轮主采集执行交接

状态：collect-before准备完成，待分析端按阶段升级READY后冻结并启动。原P0封存不改；主采集、真实训练均0。

- 新目录主版本222项CPU检查＋36子检查全部通过，包含完整13候选、fallback、真实artifact loader到pipeline接口、EVAL20场景和替补、权限/预算门。日志和对应代码SHA：`outputs/native10_training_20260916/preparation/main_cpu_20260916_v1/`。仅posthoc concurrency auditor后写完成，不属于采集代码依赖；其独立审计2073项通过。
- P0共564/600，有20源五臂和32worker复现。32份候选/完整轨迹实际逐位一致，无OOM；8卡holder已恢复。审计路径`p0/concurrency32/audit.json`、`report.md`。主并发拟冻结4worker/GPU，共32。
- `preparation/main_registration_v2/`：主900＋原P020，原820逐项保留；新增cal/held各50。备用1800另列，不算已采或总体分母。每primary两条有序备用，只允许初次动作前重复初态或reset初始化失败；尝试保留且不因结局换源。三次同reset异常会阻断整波。
- `scene_identity.py`对真实qpos/qvel/act/mocap/goal/body-site-geom位姿按单位规范化，排除seed/RNG/time；原始状态和exact hash另存。跨主split同task查重；初态审计不作critic输入。held及其备用不会在本阶段初始化。
- 主参数：600train（300＋300）、100dev、100cal、100held，重复4/4/2/4，计划48800＋储备1200，总50000。第一轮银行只含300train round1＋100dev，13候选＋normal，各4重复；上限23200（含capture/bank独立恢复），额外初始化替补capture使用技术储备。

待放行scope：`round1_native10_local_labels`和`preregistered_initialization_replacements`。仅前者对应stage `round1_labels`、后者对应stage `technical_reserve`；训练/round2/cal/held仍未开放。可审查pending配置：`preparation/main_round1_pending.json`。freeze入口会重新检查READY、P0依赖、并发审计、代码/权重/种子，并复制独立coordination快照到`main_protocols/<version>/`。

已有training.py/dataset.py/artifact_loader.py/training_pipeline.py均仅合成测试。真实源收集后还须按输入seal/账本/scene/配对审计打包，并通过真实train-only PCA与模型重载概率/动作梯度审计，之后另等训练阶段READY。本次无需以不存在的真实数据审计拖延采集。

成本：短32worker探针加载后工作跨度22.946秒完成32 bank+branch对；含模型加载worker包络199.603秒。这只支持实现一致性与并发可运行，不是完整13候选稳态基准。600训练规模可行；新主阶段实际吞吐/磁盘在首批完成后更新。当前轻量磁盘估计8–15GiB，保留20–50GiB余量；8worker实测外推11–22h，32worker可望缩短但先不称实测提速。
