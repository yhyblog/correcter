# Native10 校准执行交接

原100个校准主槽全部完成，各任务20个真实不同初态；96个报警源、4个无报警共同结局（2成功、2失败），完整分母保留。A4000与post均在校准前固定。post 133/200=66.5%，仅重规划119/200=59.5%；额外+7.0pp，源级95% CI [3.0,12.0]，救回15/损害1，正/负/零源9/0/91。按冻结的mean(P−R)>0规则仅生成启用post提案，未封存部署选择，未初始化或运行held。校准幅度达到约5pp目标，但不是独立验证成功。

全轨迹、scene、原槽/替补、实际A4000、raw映射/同幅及13,872条后缀种子记录审计通过；6,356项文件入索引。没有技术缺失、重试、初始化替补或新增优化。五臂总率46/59.5/61/58/66.5%；七比较及逐任务/逐源在完整报告中。一条配对损害落在净零源，故源级负源0不等于配对损害0。

实际计费1156=100capture+96bank+960branch；全局46025/50000sim、51200/51200opt，技术储备0/1200。lifecycle墙钟580.12s，8卡holder恢复。新产物约103.20MB逻辑字节。命令XYZ/grip平均RMS .042460/.088905，三纠偏幅度匹配；无raw别名、clip碰撞或同幅失败，5个源grip零通道，未丢源。Q相关仅作描述，未增加门槛。

首个v12元数据freeze因两条历史from/to引用未带path被严格清单拒绝，发生在任何仿真前。分析端仅补path=to重发同v12；实际启动绑定修正版5cec3558…，163项授权引用的原件与快照全部进入新freeze。原失败证据保留；没有修改旧封存或重跑已完成波次。

完整报告：[calibration report](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_diagnostics/calibration_v1/report.md)；逐源：[per_source.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_diagnostics/calibration_v1/per_source.csv)。

审计：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_audits/calibration_v1`，seal `6e1568c11fc52d3f1cb1ce43e41f51be5b218faa8ddcab0fbc3183e090a70d25`。

诊断：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_diagnostics/calibration_v1`，seal `c5687a459aef2a9b6aef3028e208318052089fdd8f875fb3e963852fa4e546f3`。

独立重聚合：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_independent_audits/calibration_v1`，seal `1f5b59dabae1315019f0776ec0b9ecafa0f3e5ad21a90e6c979e96232e0acd98`。

本交接包summary.json含七比较、逐任务、提案与资源；parameters.json含原冻结科学参数；evidence.json列精确SHA。后续只等分析端对选择封存/held的阶段决定，不重新选模型或校准方法。

交接包：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/calibration_handoffs/calibration_v1`；seal `0d9140797c13d0f59eb02f067c8a94752c563959765dd9cccab02c0a3a972830`。
