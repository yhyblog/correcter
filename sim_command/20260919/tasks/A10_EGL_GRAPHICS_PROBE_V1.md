# A：一次 EGL 单帧 graphics 预检

task_id=`A10_EGL_GRAPHICS_PROBE_V1`；task_revision=1；owner=A；仅主机 `trial-303224955-trialrun-303224955-worker-0`。授权见 `releases/P10_A_EGL_GRAPHICS_PROBE_V1.json`，旧native预检继续关闭。

目标是验证已隔离的535.161.08 NVIDIA用户态graphics库能否在指定物理GPU上建立EGL context并完成一次静态RGB读回。CPU静态依赖通过并不等于运行已通过；本次成功也不等于MetaWorld、VLA或P/V已验证。

## 唯一命令

先写本任务ACK，核对当前CONTROL/TASK_BOARD/release与claim状态，然后执行一次：

```bash
bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CPU_REPAIR_V1/commands/run_proposed_graphics_probe.sh /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P10_A_EGL_GRAPHICS_PROBE_V1.json
```

工作目录为 `results/A/A10_EGL_CPU_REPAIR_V1`。真实入口已执行CPU授权、文件身份与设备检查，不必额外重复独立CPU checker；若为排障调用，单独记I/O/时间且不视为新graphics额度。禁止将真实入口当dry-run。

## 边界

- 1个进程、1个graphics attempt、1次EGL设备枚举；最多16设备槽、48次设备字符串查询。只在DRM路径→sysfs PCI→内核UUID唯一匹配目标 `GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe` / `0000:0f:00.0` 后初始化display，不按CUDA序号猜，不轮流尝试其他卡。
- 1次display初始化、1个EGL context、1个64×64静态场景与data、最多1次显式mj_forward、1次render和1次RGB读回。mjrContext仅为渲染资源对象；资源创建/释放和查询调用均按release完整caps，不另加隐式探针。
- 策略模型加载/推理/采样、MetaWorld实例/reset、物理推进/控制步、rollout及训练全部0。mj_forward不作为推进时间的策略步。自动重试0，失败不换库/设备/renderer接着试。
- 子进程120秒TERM＋10秒KILL，覆盖该进程的hash/import/EGL/静态场景/清理；前置检查、预约建立、释放与恢复观察另计，不能称端到端130秒。显存1GiB、RAM2GiB、输出32MiB均为待实测估计。
- 入口内部使用既有lifecycle；A全8卡holder在整个波次及进程族退出前停算，退出包括失败后恢复。B不参与，不终止无关进程。不要额外重复lifecycle包装。

## 回执与下一步

保存设备映射证据、实际GL vendor/renderer/version、RGB及shape/dtype/hash、阶段事件、计数、cleanup、RESULT与LAUNCH_RESULT。输出只写本角色新run目录；实际失败同样保留，未知值不补0，不把技术失败记为任务失败率。

交 `receipts/A/A10_EGL_GRAPHICS_PROBE_V1_ACK.json`、运行心跳和最终 `A10_EGL_GRAPHICS_PROBE_V1_REPORT.md` / `A10_EGL_GRAPHICS_PROBE_V1_RESULT.json`。最终报告注明planned/entered/returned/failed/incomplete、墙钟各段、实测内存及其观测口径、holder恢复情况。

无论成功失败，一次release结束即消耗；请分析端关闭，不能用未进入的剩余额度自行重跑。成功后等待新的原生链路任务；失败则报告具体库/设备/接口阶段证据与可行修复，不自行改共享环境或要求未经证实的平台重建。当前无任何删除授权。
