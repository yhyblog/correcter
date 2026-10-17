# A_D24_VELOCITY_TRIGGER_MODES_V1 recovery r2 终局回执 r3

已接收真实事件 `D24_A_velocity_trigger_modes_recovery_r2_chain_terminal_v1`。科学链再次部分失败，raw lifecycle exit=3；compute_complete=false，publication_completed=true。外层fatal=null仅表示监督器没有额外异常；真正故障见MANAGER_EXIT.fatal。

- H10 Random-once完整：308/500成功。
- H10 G0-multi完整：346/500成功；原8中断均完成单次纠正，旧失败费用保留。
- H30 Random-once：224次进入，216完整终局/111成功，8中断success=null，276未进入；该格尚未完成，不按216子集代替500源结论。
- 其余7格3500单元未进入；合计3776未进入、8尚未解决中断。

合并旧包及recovery：1232物理attempt=1216完整+16历史中断；1224唯一已进入单元，其中1216有效。原518消耗全部保留，本recovery新增714attempt/706有效/8中断，A历史9360+1232=10592。原8中断和新8中断分列，没有抹除历史失败、没有重放完整结果。

Manager在publication_data.py:75抛EvidenceConflict: result without same source attempt claim。停止后定向复核1232 claims与1232 RESULT逐attempt精确一一对应，缺失0，终局CPU导出第1次即成功。静态调用顺序是先快照claim路径、再逐个读job/枚举新增RESULT，支持并发读取快照竞态解释；原错误未记录具体unit key或初始snapshot，不能指认确切触发单元。此为监督/汇总故障证据，不当作模型方法失败。

管理器清理使8个当时在途H30回合中断，原错误为episode stop/deadline，实际已执行4..259步，均未完整终局。已保存正式组排空、8worker退出码3、数据发布后释放同锁及11:50:59 UTC八holder恢复证据。

本回调仅读取/核对和写ACK/回执，scientific_compute=0；没有新launch、修复运行、配置或holder变更。保留全部已完成单元和当前未完成清单、原截止与stage5500/A18000上限。

合并表：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_VELOCITY_TRIGGER_MODES_V1_RECOVERY_r2/FINAL_CELLS.csv
独立样本：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_VELOCITY_TRIGGER_MODES_V1_RECOVERY_r2/FINAL_EPISODES.csv
全部物理尝试：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_VELOCITY_TRIGGER_MODES_V1_RECOVERY_r2/ALL_ATTEMPTS.csv
核对明细：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_VELOCITY_TRIGGER_MODES_V1_RECOVERY_r2/notifications/chain_terminal/CPU_TERMINAL_RECONCILIATION.json
