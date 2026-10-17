# Corrector 两服务器仿真指挥入口

Campaign：corrector-sim-20260919，revision 1。分析端负责方法、任务发布与结果分析；两执行端负责工程、运行、审计。真机由用户自行完成，不在本目录派单。

先读[实验清单和分工](MASTER_PLAN.md)，再读[控制状态](CONTROL.json)、[任务板](TASK_BOARD.json)及自己节点的入口：

- [服务器A启动任务](START_SERVER_A.md)：本机既有执行对话。
- [服务器B启动任务](START_SERVER_B.md)：另一服务器，通过共享存储交接。
- [另一服务器启动命令](LAUNCH_COMMANDS.md)：已有Codex窗口和新开终端两种方式，任选一种。
- [回执合同](contracts/REPORT_CONTRACT.md)：执行端用短报告交接，不将大量代码或完整日志灌入分析端。
- [存储清理与保留规则](contracts/STORAGE_RETENTION_V1.md)：用户已授权清理确认无用的 VLA 数据/权重，历史共享资产由 A 统一清理，其他项目不动。
- [方法与实验设计](../../docs/Experiment_plam.md)。

首个共同池父源V4已验收并关闭：1/500规划父源（train1/dev0）、15完整终局、7组双repeat，资格限冻结状态closure，physical_equality_proven=null。实际384采样/3804控制、72.29分钟，结果不是方法成功率。CONTROL45/TASK_BOARD52计算全0，A准备[下一8父源的参数化与多GPU调度](tasks/A11_BATCH_SCALING_CPU_V1.md)，B按[真实父源交接](tasks/B11_FIRST_PARENT_REAL_DATA_HANDOFF_V1.md)继续CPU视图适配。12份计算release关闭；整批采集、训练/评测、安装/删除未授权。

用户已要求两机协作准备实验。两机盘点与CPU接口准备已验收；B10 R2和B存储专项也已验收。当前两端并行CPU实现与消费共同池接口；完成当前任务后等待分析，不擅自补跑历史实验。

## 目录与写入权限

- 分析端单写：MASTER_PLAN、CONTROL、TASK_BOARD、tasks、contracts、manifests、releases。
- A单写：nodes/A、receipts/A、results/A、work/A。
- B单写：nodes/B、receipts/B、results/B、work/B。
- 公共原始训练数据清单由A在results/A发布，分析端在manifests/冻结其引用和SHA；之后只读。并行采集必须先分配互不重叠的源分片，B只写自己的分片。
- 不修改原standalone、原VLA-Corrector复现、旧训练库与封存；新输出始终有campaign/task/revision/host身份。

当前文件是任务安排，不是实验结果。完成以相应回执和产物核验为准。
