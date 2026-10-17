# Corrector 两服务器仿真指挥入口

**当前最高优先级：[9月24日截稿冲刺](deadline_20260924/PLAN.md)。必要算法适配和清单内计算已一次授权；取消严格一致性审计/全量475源采集/通用队列READY前置。CONTROL52 / BOARD67 / queue CONTROL7；23日20:00北京时间冻结数据、23:00交表图。下方旧采集与审批条款受此覆盖。**

最新占卡覆盖（2026-09-21）：用户明确允许formal wave期间给空闲卡补holder，以维持8卡利用率；正式任务优先且同卡加载/运行前先让出。见[有效补充](persistent_queue/OCCUPANCY_OVERRIDE_V1.md)。此补充覆盖下文及旧合同的全卡停holder表述；科学配置与A/B独立分工不变。

2026-09-21更新：[独立后台队列V2](persistent_queue/README.md)。A负责全部475待采源和本方法主结果，B负责外部对比/消融/适用性；A不等待B。正常批次自动检查接续，目标8卡真实任务、按资源准入；正式任务优先，同卡 holder 先退出再加载；其他空闲卡按最新用户覆盖保机。Batch3 已验收关闭，下一批八路准备已领取。V2授权与实际后台服务状态分开，后者只认各node READY/heartbeat。

Campaign：corrector-sim-20260919，revision 1。分析端负责方法、任务发布与结果分析；两执行端负责工程、运行、审计。真机由用户自行完成，不在本目录派单。

先读[实验清单和分工](MASTER_PLAN.md)，再读[控制状态](CONTROL.json)、[任务板](TASK_BOARD.json)及自己节点的入口：

- [服务器A启动任务](START_SERVER_A.md)：本机既有执行对话。
- [服务器B启动任务](START_SERVER_B.md)：另一服务器，通过共享存储交接。
- [另一服务器启动命令](LAUNCH_COMMANDS.md)：已有Codex窗口和新开终端两种方式，任选一种。
- [回执合同](contracts/REPORT_CONTRACT.md)：执行端用短报告交接，不将大量代码或完整日志灌入分析端。
- [存储清理与保留规则](contracts/STORAGE_RETENTION_V1.md)：用户已授权清理确认无用的 VLA 数据/权重，历史共享资产由 A 统一清理，其他项目不动。
- [方法与实验设计](../../docs/Experiment_plam.md)。

共同池已验收 23 个四目标完整 train 父源，另 1 个部分有效源，dev=0；25 个计划源已处理，475 个待执行。详见[Batch3分析](manifests/A11_BATCH3_ANALYSIS.md)及[严格索引V4](manifests/COMMON_POOL_ACCEPTED_PARENTS_V4.json)。CONTROL51 / TASK_BOARD66 已关闭本批；八路首次计算仍待资源与入口验收及独立release，此后正常批次按后台队列自动接续。队列实施、部署与CPU准备已授权；训练/正式评测及删除未新增授权。

用户已要求两机协作准备实验。两机盘点与CPU接口准备已验收；B10 R2和B存储专项也已验收。按当前独立队列合同推进；正常已授权批次自动继续，未冻结的科学阶段等待一次配置发布，不补跑历史实验。

## 目录与写入权限

- 分析端单写：MASTER_PLAN、CONTROL、TASK_BOARD、tasks、contracts、manifests、releases。
- A单写：nodes/A、receipts/A、results/A、work/A。
- B单写：nodes/B、receipts/B、results/B、work/B。
- 公共原始训练数据清单由A在results/A发布，分析端在manifests/冻结其引用和SHA；之后只读。本轮共同池由A单写；B只读快照并写自己的视图/模型/评测结果。
- 不修改原standalone、原VLA-Corrector复现、旧训练库与封存；新输出始终有campaign/task/revision/host身份。

当前文件是任务安排，不是实验结果。完成以相应回执和产物核验为准。
