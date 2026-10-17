# C：R随机单次/收益多次，五H各500

task_id=`C_D24_R_TRIGGER_MODES_V1`，revision1，owner C。用户新增实验授权：执行`deadline_20260924/TRIGGER_TIMING_AND_MULTIPLICITY_V1.md`及对应`TRIGGER_TIMING_MULTIPLICITY_AUTHORIZATION_V1.json`。

C独占R的Random-once与G0-multi，H10/30/50/20/40、每格原500test源，共10格5000首次回合。沿C刚完成R40/50的NVIDIA EGL/30Hz/.015及A主表R协议；multi只去次数帽，random用统一冻结表。R无Q纠偏/动作梯度，不增加新算法。旧R40/50、Velocity、N补缺均不重跑。

必要私有改动后直接八卡后台运行，无A/B依赖或二次批准。本新任务5500 attempt上限，C累计上限按新用户范围从2400增至7900，已发生2013保留；新授权不是旧任务余额，不复用旧claim。无训练。稳定后结束LLM等待；终局通知原线程`01a0c793-10d2-7791-a250-fd65d88e1ccb`。
