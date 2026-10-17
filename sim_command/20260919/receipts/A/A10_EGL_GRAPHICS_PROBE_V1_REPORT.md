| 项目 | 可用 / 缺口 |
|---|---|
| 一次真实执行 | 已完成，技术失败，rc=1；release 已消耗，待分析端关闭 |
| 固定物理设备 | GPU 0 / `GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe` / PCI `0000:0f:00.0` / driver 535.161.08，入口核对一致 |
| EGL 映射 | 1 次枚举返回 8 设备；8 次扩展 + 16 次 DRM 查询未建立任何物理映射，拒绝进入 display |
| context / RGB | 均未进入；vendor/renderer/version、RGB shape/dtype/hash 为 null，有缺失原因 |
| cleanup / occupancy | releaseThread 1 次成功、cleanup 无错误；进程退出后全 A 8 holder 恢复，18:02:41 UTC 再确认 |

实际命令按任务书执行一次，ACK 在先，入口自带完整身份校验；没有独立 CPU checker、重试、换设备/库/renderer或 B 参与。失败不是 episode 任务失败率。

| 资源 | planned cap | entered | returned | failed | incomplete |
|---|---:|---:|---:|---:|---:|
| graphics attempt | 1 | 1 | 0 | 1 | 0 |
| EGL enumeration | 1 | 1 | 1 | 0 | 0 |
| device string query | 48 | 24 | 24 | 0 | 0 |
| explicit getProcAddress | 4 | 3 | 3 | 0 | 0 |
| releaseThread | 1 | 1 | 1 | 0 | 0 |
| display / initialize / EGL context / render / RGB（各） | 1 | 0 | 0 | 0 | 0 |
| VLA / MetaWorld / reset / 物理推进 / rollout / 更新（各） | 0 | 0 | 0 | 0 | 0 |

总事件 entered=30、returned=29、failed=1、incomplete=0；terminal 不重复计费，全部 caps 满足。完整查询、清理与零项逐行见 [COUNTS.tsv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_GRAPHICS_PROBE_V1_r1/COUNTS.tsv)。没有 native reset 返回或完整观测返回。

墙钟：准备 5.410 s；预约/停止 holders 66.293 s；wrapper 0.005 s；定时子进程 5.841 s；释放 0.018 s；恢复观察 21.007 s；launcher 端到端 98.574 s（外层观察 98.667 s）。未触发 timeout；120+10 s 仅约束子进程，前置与恢复另计。

实测 RAM 最大单个子进程 RSS 47.523 MiB（含 observer 子命令，不是并发 RAM 总和）。定时区间 14 次完整 NVML 采样，8 卡 sampled memory peak 均 0 MiB、utilization 均 0%；采样可能漏短时分配，allocator peak 与 GPU-seconds 未知，写 null。run 产物 28815 bytes；估计上限不冒充实测。

容器 `/dev/dri` 缺失，而 sysfs card1/renderD128→PCI→内核 UUID 与目标一致。当前 DRM 返回的 NULL/空串没有分开记录；只断言“无可用路径”，不推断 context 不可运行。建议分析端先决定 CPU 审查已宣告的 persistent-device UUID 映射路线；或核对主机节点后决定精确挂载。依据、限制及另一方案见 [REPAIR_OPTIONS.md](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_GRAPHICS_PROBE_V1_r1/REPAIR_OPTIONS.md)，本轮不实施。

证据：[runtime RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/EGL_graphics_runs/A10_EGL_GRAPHICS_PROBE_V1_r1_A_wave02/graphics/RESULT.json)、[device_mapping](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/EGL_graphics_runs/A10_EGL_GRAPHICS_PROBE_V1_r1_A_wave02/graphics/device_mapping.json)、[LAUNCH_RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/EGL_graphics_runs/A10_EGL_GRAPHICS_PROBE_V1_r1_A_wave02/LAUNCH_RESULT.json)、[FINAL_AUDIT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_GRAPHICS_PROBE_V1_r1/FINAL_AUDIT.json)、[holder 恢复](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_GRAPHICS_PROBE_V1_r1/OCCUPANCY_AFTER.json)；完整 SHA 见 [manifest](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_GRAPHICS_PROBE_V1_r1/FINAL_ARTIFACT_MANIFEST.json)。

请分析端关闭 `P10_A_EGL_GRAPHICS_PROBE_V1`，剩余未进入额度不复用。旧 native release 保持关闭，v5 未执行。全部新产物保留，无删除、共享库修改或容器重启；等待下一任务。
