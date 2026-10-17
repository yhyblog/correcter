| 项目 | 实测结果 / 范围 |
|---|---|
| 一次真实执行 | rc=0，runtime/LAUNCH_RESULT均complete；仅本次静态graphics路径，待分析端验收关闭release |
| 目标身份 | EGL index0返回CUDA handle0→`0000:0f:00.0`→`GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe`，8候选PCI/内核UUID均核对；不是索引假定 |
| 库与renderer | 冻结535.161.08 CUDA路径与可见性一致；GL NVIDIA H100 80GB HBM3/PCIe/SSE2，4.6.0 NVIDIA535.161.08；EGL NVIDIA1.5 |
| RGB场景 | 已查看保存的64×64 uint8 RGB：红橙色有明暗球体、蓝灰色透视平面、黑色背景，与冻结XML相符；NPY/PPM/PNG查看副本像素相同 |
| 清理 / occupancy | cleanup无错误；context销毁、terminate、releaseThread、MjrContext free各1；全8holder在进程族退出后恢复，18:44:03 UTC再确认 |

| 资源 | planned | entered | returned | failed | incomplete |
|---|---:|---:|---:|---:|---:|
| attempt / 枚举 / cuInit（各） | 1 | 1 | 1 | 0 | 0 |
| 扩展 / 属性 / PCI（各） | 8 | 8 | 8 | 0 | 0 |
| getProcAddress / eglGetError | 5 / 35 | 5 / 35 | 5 / 35 | 0 | 0 |
| display初始化 / EGLcontext / render / RGB（各） | 1 | 1 | 1 | 0 | 0 |
| VLA / MetaWorld / reset / 物理推进 / 训练 / 重试（各） | 0 | 0 | 0 | 0 | 0 |

全项 entered/returned/failed/incomplete=105/105/0/0，所有caps满足；[完整计数](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_r1/COUNTS.tsv)包括库加载2、EGL/CUDA符号11/2、清理及其他辅助项。35次EGL错误查询均0x3000、cuInit/8PCI返回均0。模型静态data.time=0→0，不产生策略控制步或episode成功率。

墙钟：前置5.306s，预约/停全卡50.638s，wrapper0.004s，timed child10.003s，释放0.019s，恢复观察8.005s；launcher总73.975s（外层观察74.125s）。120+10s只约束子进程，未触发timeout。

RAM最大单个子进程RSS107.254MiB（不是并发总量）；timed child内18次完整NVML采样：GPU0峰值15MiB，其余各3MiB，利用率样本均0%。采样不等于精确GPU消耗；allocator peak和GPU-seconds仍null。run输出119250bytes，估计上限不冒充实测。

RGB NPY SHA `c54779ce229370a193da93de18b041c20fd234973543dca84f4ff8e27b0780db`；查看器不支持PPM，因此仅CPU无损编码PNG供目视，往返像素校验一致，无新增render/readback：[RGB](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_r1/RGB_VIEW.png)、[目视记录](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_r1/RGB_SCENE_INSPECTION.json)、[像素证据](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_r1/RGB_VIEW_PROVENANCE.json)。

证据：[LAUNCH_RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/EGL_graphics_runs/A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_r1_A_wave03/LAUNCH_RESULT.json)、[device mapping](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/EGL_graphics_runs/A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_r1_A_wave03/graphics/device_mapping.json)、[raw API](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/EGL_graphics_runs/A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_r1_A_wave03/graphics/api_results.jsonl)、[FINAL_AUDIT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_r1/FINAL_AUDIT.json)、[holder日志](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_r1/GUARD_LOG_WINDOW.txt)、[完整SHA清单](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_r1/FINAL_ARTIFACT_MANIFEST.json)。

ACK在先，真实命令仅1次，未另跑CPU checker。observer准备时一次路径文本断言在真实启动前修正，记录在RESULT与PRELAUNCH_PREPARATION_NOTE，不是graphics重试。冻结命令/库/设备/可见性未改，B未参与，无删除，native v5未运行。本release已消费，请分析端关闭；随后等待新任务。
