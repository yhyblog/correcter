# A_D24_VELOCITY_TRIGGER_MODES_V1 终局回执 r2

已处理真实终局事件 `D24_A_velocity_trigger_modes_chain_terminal_v1`。本链因 CPU 发布异常退出，raw exit=1，原始 RESULT 的 publication_completed=false；并非5000条完成。

- H10 Random-once：500/500完整终局，308成功（61.6%），0技术失败；250条发生一次干预，250条未干预。
- H10 G0-multi：18次进入，10完整终局/10成功，8条被管理器退出中断、success=null；不足500条，不作为整格成功率。
- 合计518次真实attempt、510有效终局、8技术中断；4482个计划单元未进入。A历史9360保持，累计9878。

失败位于 code/report.py:85：父episode字段与monitor事件同时展开mode，抛出 TypeError: dict() got multiple values for keyword argument 'mode'；同处planned_random_cut也是重复键。首格发布错误引发manager终止其他worker，后续terminal发布再次失败。8条episode原始失败信息为episode stop/deadline，其不足8秒的实际时长与manager异常/停止路径相符，不冒称模型本身失败或实际1800秒超时。

518个独立unit claim与518个episode RESULT一一对应，保留所有完整和失败结果。实际 episode sampling=8210、flow=82100、Q ensemble=2248、动作梯度=843；训练0。完整资源明细见CPU_TERMINAL_RECONCILIATION；没有重算模型/环境。

原始整组清理证据确认全部自有正式后代退出；11:11:31 UTC保存的guard状态显示8/8 holder恢复。MANAGER_EXIT与BEFORE_RESERVATION_RELEASE未生成，采用已保存的SUPERVISOR_FAILURE/CHAIN_RESULT/RESTORATION说明退出。HEARTBEAT中的“publication”字样不能替代实际发布完成证据。

本回调仅CPU读取/统计并写去重ACK，scientific_compute=0；没有重复已完成episode，没有启动修复run或新增配置，没有变更holder。原claim、原结果、代码和失败日志不改。

核对明细：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_VELOCITY_TRIGGER_MODES_V1/notifications/chain_terminal/CPU_TERMINAL_RECONCILIATION.json
逐源索引：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_VELOCITY_TRIGGER_MODES_V1/notifications/chain_terminal/SAVED_EPISODE_INDEX.csv
