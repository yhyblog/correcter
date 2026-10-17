# A：一次接入已验证 EGL 路径的原生 V3 预检

task_id=`A10_PREFLIGHT_NATIVE_V3`；revision=1；owner=A；仅主机 `trial-303224955-trialrun-303224955-worker-0`。本任务书本身不构成计算放行，须当前 CONTROL/TASK_BOARD 与 `releases/P10_A_NATIVE_PREFLIGHT_V3.json` 一致。旧native V1/V2及两份graphics release保持关闭。

目标：在固定π0.5 MT50 030000底座上，验证私有EGL适配后的真实MetaWorld观测、五个H的原生采样/队列及一条实际transition。这是工程预检；不验证D/G0/Q、Post/Velocity数值、完整episode或MT50性能。

本次在V2基础上只修正Torch UUID表示合同及证据：支持exact str或真实 `torch._C._CUuuid` 类token身份，可信非字符串只转换一次，严格完整UUID匹配。`policy_device_type.json`须在转换前保存原类型，`policy_device.json`须在接受/拒绝前保存转换、格式和目标结论；不增加properties或设备查询。V2原对象的具体类型仍未知，不反填。

## 唯一命令

读取release、核对当前状态及独占claim不存在，先写本任务ACK，再执行一次：

```bash
bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1/commands/run_proposed_native_preflight.sh /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P10_A_NATIVE_PREFLIGHT_V3.json
```

cwd=`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_TORCH_UUID_ABI_CPU_REPAIR_V1`。真实入口已有完整身份/SHA校验，不另跑独立CPU checker，不将实际入口当dry-run。已有本release的claim或结案记录时只报告，不重复执行；任何阶段失败均耗尽本次机会。

## 本次运行上限

- 只用冻结development诊断源 `A10-native-queue-diagnostic-shelf-place-v3-2026091900`；环境/generation/suffix seed分别为2026091900/1901/1902。不按结果替换初态。
- 1模型初始化、1诊断attempt。H=10/20/30/40/50各1次完整native采样，共5次采样、50次flow forward；只执行1个真实策略控制步/13物理子步。完整rollout、monitor、critic、反向、optimizer、训练和重试均0。
- 初始化2个原生环境+1包装器；50任务生成reset+1包装初始化reset+1诊断reset，共52 native reset、104 reset_model、5200 settling do_simulation、26000初始化物理子步。总物理子步26013只是两项之和的别名，不与分项重复计费。
- 固定GPU UUID `GPU-17198167-95ac-ca23-d6a3-58bb5568a8fe`、PCI `0000:0f:00.0`、driver `535.161.08`。八设备EGL CUDA handle→PCI/内核UUID完整核对后，按冻结UUID可见性选择策略逻辑设备并用Torch文本UUID复核；不以EGL/CUDA/NVML序号等价替代身份验证。
- 1个EGL context与1个MjrContext复用；初态和控制步后各1张corner2 480×480 RGB，共2次render/readPixels。后者内部填充depth不另作独立观测。最多2份可用观测NPZ；同源PPM/无损PNG查看副本不增加render/readback。
- graphics适配的完整显式caps见release（成功目标108项）；模型/初始化/graphics三套账本各保留边界。显式cuInit=1并不限制或宣称Torch/MuJoCo/驱动内部cuInit总数；底层CUDA context/kernel未逐项计量，由本次单模型、5/50采样范围约束。不能沿用旧graphics任务的全进程CUDA kernel=0表述。
- `diagnostic_native_resets_returned`、初态完整观测、步后完整观测、可用观测产物分别报告；native reset返回不代表RGB可用。entered计一次，终态不额外加费；库调用returned也不等于语义验证成功。

## 波次与时间

使用冻结入口内部既有lifecycle，不重复包装。A全8卡holder在整个进程组退出前停算，成功、异常或超时后均先确认进程组退出，再释放预约并恢复全部holder；不在空闲子集启动holder，不终止无关进程。B不参与本次wave。

1800秒TERM＋30秒KILL仅覆盖诊断子进程，含其校验、初始化、加载、采样、渲染和清理。前置hash、预约、进程组退出、释放与恢复另计；端到端严格上界未知。41GiB VRAM/64GiB RAM/2GiB输出是工程估计，实际资源按观测口径回报，未知值保留null。

## 回执与验收

交 `receipts/A/A10_PREFLIGHT_NATIVE_V3_ACK.json`、运行心跳及同名前缀REPORT.md/RESULT.json；保留LAUNCH_RESULT、claim、全部阶段/初始化/graphics账本、5个raw计划、H队列检查、当前/next观测及真实transition、policy UUID原类型/转换/判定、mapping/loader/renderer、cleanup和进程组退出/holder恢复证据。

成功须检查两张保存RGB是否符合shelf-place场景、观测与transition身份一致、5组计划/队列均符合冻结协议。可仅CPU将已保存像素无损编码PNG供分析查看，附像素相等及来源SHA，不增加渲染。失败报告具体阶段、已入账资源和未到达产物原因，不把技术失败计为任务成功率样本。

无论成功失败，本次release均消耗，未进入额度作废；交分析端验收关闭，不能自行追加或换库/renderer/设备/seed重试。删除0，旧封存与共享环境不动；不自动进入P/V、公共池采集、训练或完整评测。
