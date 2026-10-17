# A：一次占卡 guard 文件安装（纯 CPU、无计算）

task_id=`A10_GUARD_HANDOFF_INSTALL_V1`；revision=1；owner=A；唯一A主机 `trial-303224955-trialrun-303224955-worker-0`。授权 `releases/P00_A_GUARD_HANDOFF_INSTALL_V1.json`。分析已审阅准备包和精确patch；当前只安装，不验证实际交接或启动V3。

## 前置与唯一命令

读取当前CONTROL/TASK_BOARD、新release及本任务；确认CONTROL为prepare、全部计算关闭，active_guard_installation_release精确指向本release，任务板为ready。写本任务ACK。旧七份计算release保持关闭，V3真实计算release尚未发布。

核验release及以下冻结安装器/源文件SHA，确认本release没有关闭或已有执行记录。使用原安装器一次：

```bash
/usr/bin/python3 -I -S -B /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_PV_HANDOFF_CPU_REPAIR_V1/commands/transition_guard_file_cpu.py --release /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P00_A_GUARD_HANDOFF_INSTALL_V1.json --operation install
```

cwd=`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_PV_HANDOFF_CPU_REPAIR_V1`。安装器SHA `a19f376f2acb1dfeb47c6028bf0460ce71668153579eb554bdc8476b4ffbeafe`。不调用安装器作dry-run或重复运行；真实入口任何阶段失败都提交原状证据，由分析决定后续。

## 精确授权范围

唯一共享替换路径：`/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.py`。

- 安装前SHA：`d499982dff72c3b74ddab0e13e359edccb5f282900c534030b3816b58495fcaf`。
- 安装后SHA：`7910c567a47ddf68294d92fc9698cc780aeb130ddefde0337414bfcd88cb85a4`。
- 原字节：准备包 `guard_patch/gpu_occupancy_guard.original.py`；新字节：`guard_patch/gpu_occupancy_guard.patched.py`。

沿用安装器私有暂存/原字节备份、mode/uid/gid保持、替换前inode与SHA复核、单次原子替换和替换后SHA校验。其独占暂存目录按release ID创建并保留；不得覆盖已有暂存、清理失败证据或覆盖未知漂移。仅此一处共享文件写入，其他准备包/旧回执/CONTROL/任务板不改。

默认等待仍90秒；新V3未来显式300秒。安装不会改变正在运行daemon已加载逻辑，无需重启；本任务不运行新的run客户端，也不证明实际handoff成功。保留原停止/锁/信号/进程组机制。

安装失败时报告失败阶段和目标当前SHA；若已经替换，应据实报告，不能当成未安装自行重跑。回退源保留，但回退需要分析另发具体操作；本任务不自动回退。A为本次唯一安装执行者，B不参与安装或计算。

## 回执与零调用边界

交本任务ACK、短REPORT/RESULT、安装器原始stdout/退出码/耗时及其产生的transition记录、安装前后目标身份/SHA/mode/uid/gid、备份与manifest。应保留原始失败输出；若安装器未产生结果，由执行端给明确标注的外层回执，不伪装内部结果。

声明真实入口次数、共享替换次数及未进入阶段。无需重跑CPU fake/AST/完整manifest或大模型hash，只核对本任务小文件身份。安装后不 import/compile 执行guard，不运行status/start/NVML/holder检查，不写formal.lock，不做真实进程信号、不重启daemon、不停止holder、不运行GPU/模型/环境/训练，不删除任何数据/证据。共享文件替换不作为数据清理授权。

本次完成只交分析端验收并关闭安装release。即使安装成功，也不能运行V3、运行handoff-only探针或复用旧预检；下一次计算必须独立release。
