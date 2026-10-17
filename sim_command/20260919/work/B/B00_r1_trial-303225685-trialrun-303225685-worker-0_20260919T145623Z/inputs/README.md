# Corrector 两服务器仿真指挥入口

Campaign：corrector-sim-20260919，revision 1。分析端负责方法、任务发布与结果分析；两执行端负责工程、运行、审计。真机由用户自行完成，不在本目录派单。

先读[实验清单和分工](MASTER_PLAN.md)，再读[控制状态](CONTROL.json)、[任务板](TASK_BOARD.json)及自己节点的入口：

- [服务器A启动任务](START_SERVER_A.md)：本机既有执行对话。
- [服务器B启动任务](START_SERVER_B.md)：另一服务器，通过共享存储交接。
- [另一服务器启动命令](LAUNCH_COMMANDS.md)：已有Codex窗口和新开终端两种方式，任选一种。
- [回执合同](contracts/REPORT_CONTRACT.md)：执行端用短报告交接，不将大量代码或完整日志灌入分析端。
- [方法与实验设计](../../docs/Experiment_plam.md)。

当前仅A00/B00已分配，可做资产、环境及代码入口盘点；当前GPU训练/推理/仿真额度为0。后续正式任务由分析端在本目录发布新版本协议和release，使用本次新任务身份，不读取旧coordination/下READY当作启动命令。

这不是重新请求用户授权：用户已要求两机协作准备实验。当前尚缺另一台机器能力、输入资产和实际资源需求，先将它们变成具体回执，分析端再冻结同一协议。执行端完成当前可执行任务后，如无新任务，报告待命，不擅自补跑历史实验。

## 目录与写入权限

- 分析端单写：MASTER_PLAN、CONTROL、TASK_BOARD、tasks、contracts、manifests、releases。
- A单写：nodes/A、receipts/A、results/A、work/A。
- B单写：nodes/B、receipts/B、results/B、work/B。
- 公共原始训练数据清单由A在results/A发布，分析端在manifests/冻结其引用和SHA；之后只读。并行采集必须先分配互不重叠的源分片，B只写自己的分片。
- 不修改原standalone、原VLA-Corrector复现、旧训练库与封存；新输出始终有campaign/task/revision/host身份。

当前文件是任务安排，不是实验结果。完成以相应回执和产物核验为准。
