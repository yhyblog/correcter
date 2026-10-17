A10_PV_OFFLINE_PREFLIGHT_V2 / revision1 已执行唯一冻结命令，结果为 occupancy 交接技术失败；无重试。本次命令1、claim1（已消费）、诊断attempt0。release SHA256：`b7baf846254e9c63dca4efef354e56f56c0afcb69bfee88754e8eddc20db8522`。CONTROL25/TASK_BOARD32、固定主机/设备、输入及冻结包均未改。

guard 在清空等待约 90.808 秒后抛出 `GPUs still occupied; formal command was not launched`，早于 reserved.py/诊断子进程创建。源码的等待上限为90秒，holder按卡串行退出，每卡TERM等待最多15秒后KILL再等5秒；波次日志中GPU6/7到21:57:24/21:57:39才yield，晚于21:57:22.687的失败返回。现有证据支持串行holder交接超过固定等待上限；未保存超时瞬间NVML逐进程行，不追加探针还原，也不修改共享guard。

父层私有账本只有1个完整entered/returned事件：NVML身份核验1/1；子层账本未创建，全部计数0。66项资源汇总与冻结LAUNCH_RESULT逐项一致，无超额：模型初始化/载入、encoder/Q、guided/flow、Post/Velocity梯度、噪声重建、环境/reset/render/物理/训练全部0。父层完整SHA校验已返回（大权重1遍）；子层第二遍未进入，无额外checker/大权重hash。两账本未拼接成公共UUID事件流。

数值、mask/features、raw锚点、loader/策略UUID、噪声SHA、P/V约束、冻结参数产物均未产生，具体缺阶段见 STAGE_DISPOSITION.json；未生成替代数据。固定物理GPU的父层NVML证据保存在 pre_reservation_device.json。1800+30诊断timeout未启动，不把它解释成本次90秒guard等待。

冻结launcher返回3（内部lifecycle返回1），外层实测 134.431 秒；已reap，外层和lifecycle会话均无残留成员。内部process_family_cleanup=null是因为reserved wrapper未启动，另交只读/proc退出审计。8holder于21:57:44重新启动，21:57:56.699被入口确认恢复；manager PID270938–270945，现有guard缓存及/proc复核通过。父层准备 9.238 秒，恢复观察 34.012 秒。GPU利用时间、模型VRAM峰值未测，留null。

LAUNCH_RESULT：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/P10_PV_V2_launcher_runs/A10_PV_OFFLINE_PREFLIGHT_V2_r1_A_wave07/LAUNCH_RESULT.json`。
外层回执、私有账本汇总、阶段缺失、失败源码/日志、进程退出和holder恢复审计位于 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_PV_OFFLINE_PREFLIGHT_V2` 与 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_PV_OFFLINE_PREFLIGHT_V2_r1`；完整manifest随RESULT交付。

本次不提供数值成功、部署成本或任务成功率结论。诊断实际Post0/Velocity0采样；原部署Post1/Velocity2口径未变。旧六份release不复用，B未参与，删除0；本次剩余额度不可复用，请分析关闭P10_A_PV_OFFLINE_PREFLIGHT_V2，之后等待新任务。
