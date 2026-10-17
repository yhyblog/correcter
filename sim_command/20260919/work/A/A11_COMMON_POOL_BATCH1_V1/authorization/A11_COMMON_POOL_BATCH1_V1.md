# A11 Batch1：八个预定父源，并发2的正式采集

task_id=`A11_COMMON_POOL_BATCH1_V1`；revision=1；owner=A。唯一release=`releases/P11_A_COMMON_POOL_BATCH1_V1.json`。核对CONTROL46/TASK_BOARD53、host/release/任务SHA后写新ACK。先读 `manifests/A11_BATCH_SCALING_CPU_V1_ACCEPTANCE.json` 与 `contracts/BATCH1_RISK_AND_SCOPE_V1.md`。

## 固定范围

一次外层波次，固定8父源、并发2；每parent固定一个完整GPU UUID，内部最多15个顺序cold分支。完整source/env_seed/master_seed/GPU/path逐字使用proposal与release，不自行改PROPOSED/嵌套状态字段。8槽是disassemble、pick-place-wall、stick-pull、stick-push各train ordinal0/cut5，以及disassemble、pick-place-wall、shelf-place、stick-pull各ordinal1/cut55。已接受shelf0不重采，stick-push1留后续；其他45任务不运行，B不参与。

全波最多120attempt、3624sampling、36240flow、36000control、36120obs；116caps和调度aux均以release为准。pick-place-wall初始化forward与其他任务区别保留，整批初始化forward22080。Q/D/G0前向、梯度、训练、重试、安装和删除为0。

Q=C10、G0=C5后恢复H10，parent绝对s300或合法提前终局。完整状态/MJB资格在各源内检查，不扩写为普遍物理等价。普通有完整账本的parent技术失败只停止该parent后续branch；不换seed、不填补、不凑额度，其他已计划parent按冻结调度继续。身份/存储/cleanup/缺账本/未知同组进程/CONTROL停止等系统问题终止owned wave。技术/预算截尾保留null与mask，不写0结局。

## 唯一正式命令

工作目录：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_BATCH_SCALING_CPU_V1`。

```bash
bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_BATCH_SCALING_CPU_V1/commands/run_proposed_batch1.sh /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P11_A_COMMON_POOL_BATCH1_V1.json
```

仅执行一次冻结bash。分析端已执行纯JSON发布检查；不另跑checker或环境/GPU/并发probe。真实入口仍执行完整SHA、即时容量、设备身份检查。命令或claim前失败也不能自行重复命令机会；12旧计算release均关闭不复用。

## 容量、生命周期与回执

本批有限风险已独立接受，见 `contracts/BATCH1_RISK_AND_SCOPE_V1.md`：最低即时空间93,952,475,136B、564,096 inode；并发2规划RAM128GiB，容器/RSS/VRAM/共享IO与监测缺口仍未知。不得把statvfs当项目quota，I/O约1.148TB只称已知尺寸逻辑小计，4.82h只作算术情景。

全A8holder只由一次外层预约管理，空闲或提前结束的GPU不重启holder。不同worker不嵌套预约。branch及后代退出后才释放对应槽位；全部正式进程退出后完成数据/成本发布，reserved退出后统一恢复8holder。强制退出只处理即时核验归属的owned进程，不影响其他进程。

preparation900、handoff300、branch1800+30、parent27900、wave111900+30、publication300、restoration观察120秒各自分计；无锁等待/强制清理/端到端硬上界或精确GPU秒保证。不要为补缺失计数另做探针。

交独立RESULT/REPORT/LAUNCH_RESULT、逐parent与branch覆盖/终局/配对资格、全量实际116计数和调度aux、固定UUID/源身份、已存时序与进程组退出/8holder恢复、存储峰值和缺项；在不新增运行调用的前提下保留各worker启动/退出、模型载入与已有阶段耗时，以分析真实并发吞吐。公共记录/aggregate/private costs保持冻结接口；排除partial硬链接别名重复样本。

所有已启动源无论成功/失败均交，不按结局选择性发布；合格父源须再经分析纳入新索引，最多新增8不代表必然8个合格样本。当前已接受父源仍为1，不修改旧V4或训练索引。完成或失败后停止，等待分析验收关闭，不自动下一批/训练/评测/删除。
