# A：Velocity随机单次/收益多次，五H各500

task_id=`A_D24_VELOCITY_TRIGGER_MODES_V1`，revision1，owner A。用户新增实验授权：执行`deadline_20260924/TRIGGER_TIMING_AND_MULTIPLICITY_V1.md`及对应`TRIGGER_TIMING_MULTIPLICITY_AUTHORIZATION_V1.json`。

A独占Velocity的Random-once与G0-multi，H10/30/50/20/40、每格原500test源，共10格5000首次回合。源/模型/原生数值/环境沿A主表；multi只去次数帽，不改变C10锁或G0阈值，random用统一冻结表。旧20pilot不能作为新主表替代，也不能复制它的legacy随机流。

原论文CPU任务20格已完成并退出，不重做统计、不恢复LIBERO Full。必要私有改动后直接八卡后台运行，不等第二次放行。每节点本任务5500 attempt上限、A原累计18000上限仍生效，历史不重置，无训练。A不等待B/C；按原线程`01a0b91f-7443-71b1-915d-6cdb6d6a1a13`终局通知。
