# A10 有限原生预检：技术失败，已停止

| 项目 | 实际结果 |
|---|---|
| 一次执行 | P10_A_NATIVE_PREFLIGHT_V1 / v4；exit1；无重试、换源或协议回退 |
| SFT底座 | 加载完成，日志明确All keys loaded successfully，无missing/unexpected keys |
| 环境初始化 | 2物理实例+1包装器；51初始化+1诊断native reset=52全部返回；104reset_model /5200do_simulation /26000初始化物理子步 |
| 诊断 attempt | 计划1、进入1、完成0、技术失败1；完整观测未返回，初态图像产物0 |
| 采样 / 策略步 | 计划5采样/50flow/1策略步；实际均0，尚未进入 |
| 其他 | 完整rollout、反向、monitor、训练更新、自动重试、删除均0；success=null，不制造任务失败标签 |
| 占卡 | 8张H100 holder全部恢复，guard27508；17:06:35 UTC再次只读核实 |

失败点为 backend.reset_episode → 观测格式化 → render → MuJoCo EGL GLContext：`Cannot initialize a EGL device display`。异常发生在native reset已返回后、第一张RGB图像生成前；两条公共操作事件为模型加载返回、restore失败。4条公共phase记录与10724条初始化phase记录一致，末事件无缺失，已进入成本不清零。

只读环境线索：NVIDIA_DRIVER_CAPABILITIES=`compute,utility`，`/usr/share/glvnd/egl_vendor.d`无vendor JSON，ldconfig缓存未列libEGL/libnvidia-egl；只见libGLdispatch。优先由分析安排容器graphics/EGL驱动暴露与库查找链核查。这些元数据尚不能断言宿主GPU或驱动不支持EGL。未安装库、未改环境、未切换renderer，也未再创建EGL context。

实测分段墙钟：准备42.65s，预约/释放holder 37.63s，诊断子进程215.43s，预约释放0.033s，恢复观察14.01s；launcher端到端309.75s。未触发1800+30超时。子进程族OS最大RSS约39.31GiB；受控子进程期间GPU0总显存采样峰值9,675MiB，GPU1–7采样显存均0。NVML峰值只是采样下界，CUDA allocator峰值及实际GPU计算秒数未知，不拿CPU/加载墙钟冒充。

命名审计：原runtime资源回执`diagnostic_initial_states_returned=1`来自native reset返回计数；完整backend观测返回实际为0。原回执保持原样，本次FINAL_AUDIT明确更正解释，建议下一代码版本改名为diagnostic_native_resets_returned，并单独统计完整观测成功返回。

诊断目录：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/P10_diagnostic_runs/38cde7a1357b92c1020f307cad6b912ea266bd15bc43fad077836ceff7a5fbe2`；launcher目录：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/P10_launcher_runs/A10_PREFLIGHT_NATIVE_V1_r1_A_v4_wave01`；执行/监控/静态EGL证据：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_PREFLIGHT_NATIVE_V1_r1`。所有实际文件SHA见本任务ARTIFACT_MANIFEST.json。没有生成raw5计划、step0/1图像、transition或queue_checks；原因是此前渲染失败，不补假数据。

请分析关闭此已消耗的一次release，决定EGL修复的具体CPU工程任务及任何后续独立有限release。原v1、旧A10/v3/v4及封存实验均未修改；不以剩余5采样/1策略步预算自行重跑。存储定向回执已另交，B依赖回执尚待，删除仍为0。
