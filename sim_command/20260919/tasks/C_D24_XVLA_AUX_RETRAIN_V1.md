# C独立任务：X-VLA专属辅助网络重新采集/训练/验证

任务`C_D24_XVLA_AUX_RETRAIN_V1` revision1，完整授权见`deadline_20260924/PER_BASE_AUXILIARY_TRAINING_AUTHORIZATION_V1.json`。用户最新修正已直接授权必要新数据和D/G0/Q训练，无二次审批。

科学协议逐项执行`deadline_20260924/PER_BASE_AUXILIARY_RETRAINING_V1.md`。你只负责X-VLA整条链，不等待其他节点。现在允许CPU准备；正式GPU开始必须在自身`C_D24_R_TRIGGER_MODES_V1`所有正式后代退出之后，不能抢停、重复当前wave或科学claim。

固定50任务×4train+1dev=250父源，cut5/15/35/55；old/a0/±各2，共最多2000采集。独立D2/G02/Q4全小网络从头各4000更新；不能只微调旧Q残差。底座/外部编码器冻结且成本单列。新R/Post/Velocity各500，旧N不重跑，实际旧Mesa80Hz/.01、nativeK10保持。新G0监督为freshC10后nativeK10减真实old延续。

首批准入前固定新train/dev源与方法；只查必要的非test分割、输入/单位和真实标签，不做全状态证明或GPU预检。正常阶段自动接续，无需分析逐次放行；固定截止及监督缺口停止规则见总协议。目标8常驻worker，长任务稳定后结束LLM等待。

新阶段attempt≤4000/updates≤32000，累计attempt从7900增至11900，旧计算不重置。旧5000触发任务cap与claim保持。新结果写results/C/C_D24_XVLA_AUX_RETRAIN_V1/，ACK和回执写receipts/C/C_D24_XVLA_AUX_RETRAIN_V1_ACK.json及_RESULT_r*.json。新表留空到实际完成，不保证提升。
