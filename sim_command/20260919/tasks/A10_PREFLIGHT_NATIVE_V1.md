# A：π0.5／MetaWorld 有限原生链路预检

task_id=`A10_PREFLIGHT_NATIVE_V1`；task_revision=1；owner=A；只限主机 `trial-303224955-trialrun-303224955-worker-0`。

执行依据：`releases/P10_A_NATIVE_PREFLIGHT_V1.json`、当前 CONTROL/TASK_BOARD，以及已验收的 `results/A/A10_PREFLIGHT_REVISION_R2/CPU_READY_v4.json`。只运行 v4。原 interface_v1/A10/v3 保留，不重跑旧阶段。

## 要验证的内容

验证持久 SFT030000 在本机实际加载、标准 MetaWorld 初始化和渲染、同一诊断观测的五H原生采样/队列、1个真实策略步与 transition/日志落盘。唯一诊断源 shelf-place-v3，env seed2026091900，generation seed2026091901，suffix seed2026091902；development，不用于论文成功率或独立测试结论。

上限为1诊断初态/attempt、5完整VLA采样/50flow、1策略控制步（13物理子步），0完整rollout、VLA/Q反向、monitor、训练更新及重试。标准初始化另计：2物理环境＋1包装器、50 task-set＋1包装初始化＋1诊断reset＝52 native reset、104 reset_model、5200初始化do_simulation、26000初始化物理子步。总reset与分来源reset是同一工作的不同统计维度，不能相加成更多episode。

## 执行

写本任务 ACK，核对 release 与设备/输入身份后执行一次：

```bash
bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_PREFLIGHT_REVISION_R2/commands_v4/run_proposed_native_preflight.sh /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P10_A_NATIVE_PREFLIGHT_V1.json
```

工作目录为 `results/A/A10_PREFLIGHT_REVISION_R2/code_snapshot_v4`。此入口已经在 GPU 计算前执行 CPU 授权与完整输入 SHA 检查，并在生命周期预约后再次核验。无需额外先跑同一 CPU checker 来增加第三遍大权重hash；若因排障单独调用，记录其额外I/O和时间。严禁将实际 `.sh` 当 dry-run。

入口内部负责 `gpu_occupancy_lifecycle.sh run --`，不要额外重复包装。开始前按 AGENTS 核实本机 guard；全部 A holder 在整个 A-only wave 停算，退出含失败后恢复并回报。B不参加此 wave，其正常占卡不受影响。不能终止无关进程、不能启动空闲卡holder或改为联合波次。

诊断子进程1800秒TERM、30秒KILL宽限，覆盖全部初始化；前置校验、预约建立、释放和恢复观察在其外，逐段计实际时间。失败、身份漂移、预算超限或控制停止立即退出，不换源、不自动重试。失败的已进入费用保留；缺末事件与时间保持未知，不补零。

## 交付与停止

只写本角色新 run 产物。保留 claim、完整采样/flow和初始化事件、逐来源资源账本、五个raw计划、step0/1图像与本体观测、真实动作/reward/success/终止信息、队列检查、LAUNCH_RESULT、失败与occupancy恢复观察。不要复制底座权重，预计新增磁盘2GiB、显存40GiB、RAM64GiB是未实测估计；记录实测峰值及未知项。

先写 `receipts/A/A10_PREFLIGHT_NATIVE_V1_ACK.json`，运行时短心跳，最终交 `receipts/A/A10_PREFLIGHT_NATIVE_V1_REPORT.md`（建议不超过60行）和 `A10_PREFLIGHT_NATIVE_V1_RESULT.json`，引用实际run目录及SHA。报告计划/进入/返回/失败/未完成与各项实际用量；结果同样包括技术失败，不只交成功结果。

此release只有一次执行额度，已存在claim或完成记录不得重跑。结束后等待分析端下一任务；这次不执行 P/V、D/G0/Q、E1/GAF训练、公共池采集或完整MT50评测。存储候选仍无删除权限。
