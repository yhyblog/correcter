# A：一次 CUDA handle 映射与静态 EGL 图像预检

task_id=`A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1`；task_revision=1；owner=A；仅主机 `trial-303224955-trialrun-303224955-worker-0`。本任务书本身不构成计算放行；以当前 CONTROL、TASK_BOARD 和独立 `releases/P10_A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1.json` 一致为准。两份旧计算 release 保持关闭。

目标是实际验证已完成 CPU 审阅的单一映射链：EGL_CUDA_DEVICE_NV 返回的 handle 原样传给 cuDeviceGetPCIBusId，再通过内核 PCI/UUID 与固定 NVML 目标核对；唯一匹配后建立一个 EGL context 并读回一帧静态图像。此次不验证 MetaWorld、VLA、Post/Velocity 或任务成功率。

## 唯一命令

先写本任务 ACK，核对当前 CONTROL/TASK_BOARD/release 与 claim 状态，然后执行一次：

```bash
bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CUDA_MAP_CPU_V1/commands/run_proposed_graphics_probe.sh /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P10_A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1.json
```

cwd=`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CUDA_MAP_CPU_V1`。真实入口已含 CPU 授权与输入身份核验，不另跑独立 CPU checker，不当作 dry-run。已存在本 release 的 claim 或结案记录时只回报，不重复执行。

## 固定边界

- A-only，1个graphics进程、1个attempt、1次枚举、1次cuInit。扩展字符串、CUDA属性及PCI查询各最多8次；getProcAddress最多5次、eglGetError最多35次、核心EGL/CUDA符号查找11/2次、显式驱动库加载2次。完整逐项caps以冻结proposal及release为准。
- 目标为 `GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe`、PCI `0000:0f:00.0`、driver `535.161.08`。冻结8卡完整UUID可见性、PCI_BUS_ID顺序及隔离库SHA；不把EGL/CUDA/NVML索引等同。所有映射可信且唯一后才进入display/context；属性handle 0合法。
- 至多1次display初始化、1个EGL context、1个64×64静态model/data、1次显式mj_forward、1次render及1次RGB读回。库内部行为不伪装为逐项可观测调用；cuInit内部资源未知，不由显式CUDA context/kernel调用0推断资源消耗0。
- VLA加载/采样、MetaWorld实例/reset、物理时间推进、策略控制步、rollout、训练及删除均为0。自动重试0；不替换库、设备、renderer或可见性，不追加DRM/binary UUID路径。
- timed child为120秒TERM＋10秒KILL，含其hash/import/load/cuInit/映射/render/cleanup；前置准备、预约、释放与恢复观察另计，端到端严格上界未知。VRAM1GiB、RAM2GiB、输出32MiB仅工程估计，回执以实测口径为准。
- 入口内部使用既有lifecycle，不重复包装。A全8卡holder在整个波次及进程族退出前停算，成功或失败后恢复；B不参与，不终止无关进程，不启动闲置子集holder。

## 回执

交 `receipts/A/A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_ACK.json`、运行心跳和同名前缀的 REPORT.md / RESULT.json。保留原始API结果、NULL/空串区别、调用点错误状态、loader与device mapping证据、实际renderer身份、RGB及shape/dtype/hash、阶段事件、cleanup、LAUNCH_RESULT和manifest。提前失败时未到达产物明确记缺失原因。

报告planned/entered/returned/failed/incomplete、阶段墙钟、内存/利用率采样方式及holder恢复证据；GPU计算秒未知保留null，不以零采样推断精确零消耗。技术失败不进入任务成功率分母。

若报告成功，分析端还将查看已保存RGB是否呈现冻结的静态场景；仅有非空、非恒定缓冲或status=complete不足以验收实际读回。不为此额外调用render/readback。

成功或失败均消耗本次release，未进入额度作废，交分析端关闭后等待后续任务。成功仅支持本静态图形路径；native v5仍须另行任务与release。失败保留具体调用点证据，不自行追加探针或改共享驱动/容器。
