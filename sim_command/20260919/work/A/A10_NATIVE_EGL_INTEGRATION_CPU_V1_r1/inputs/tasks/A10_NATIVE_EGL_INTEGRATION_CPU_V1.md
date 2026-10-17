# A：已验证 EGL 路径接入原生预检的 CPU 准备

task_id=`A10_NATIVE_EGL_INTEGRATION_CPU_V1`；revision=1；owner=A。CPU准备授权为 `releases/P00_NATIVE_EGL_INTEGRATION_CPU_V1.json`。本任务不运行GPU、CUDA/EGL、模型、MetaWorld、reset或仿真，也不删除文件。

## 输入与目标

分析端已查看保存RGB并验收 `A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1`；结论仅为A固定GPU、隔离535库栈、一次静态图像路径通过。对应计算release已消费关闭，不能继续使用。

复用以下已发布材料，不重做库存或重投已验收任务：

- `manifests/A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1_FINAL_ACCEPTANCE.json`、本次RESULT/映射/loader/renderer证据。
- `results/A/A10_EGL_CUDA_MAP_CPU_V1` 的隔离库、可见性与显式CUDA handle→PCI/UUID映射。
- 原A10 v4预检和 `results/A/A10_EGL_CPU_REPAIR_V1` 的native v5修订；v5拆分reset返回、完整观测返回、可用观测产物计数，但没有获准实跑。

目标：在新的不可变版本中将已验证的库加载和物理映射接入真实MetaWorld原生观测链，交付一份可审阅、可执行的**单次native V2提案**。这是原生链路修复准备；不扩成Post/Velocity数值验证、训练或正式评测。

## 具体工作

1. 定向静态确认原生后端的GLContext创建、GPU选择和camera/RGB路径。说明已验证的映射结果如何传递到实际MuJoCo上下文，如何避免原生包再次用CUDA/NVML序号猜EGL设备。使用私有适配或独立快照，不原地修改共享MuJoCo/conda/系统库。旧v4/v5、graphics包和回执不变。
2. 冻结535库来源/SHA、加载顺序和实际CUDA可见性。如π0.5设备配置与graphics可见性需要衔接，明确物理UUID绑定及导入顺序；不能将本次恰好handle/index0写成通用等价关系。复用已经验证的单一映射，不加入DRM/binary UUID/renderer备选路径。
3. 保留原有H/C、raw动作、双账本及interface_v1语义。下一次native提案仍以1诊断初态/1attempt、5次完整native采样（H=10/20/30/40/50，各10 flow）、1个真实策略控制步为目标；完整rollout/monitor/反向/更新/重试为0。不额外重复静态球体探针或加载第二份模型。
4. 报价必须覆盖真实初始化与观测路径：原v4的2物理环境+1包装器、52 native reset、104 reset_model、5200 settling do_simulation/26000初始化物理子步及1策略步/13子步为既有依据。若集成改变任何调用数，逐项解释后在新提案中冻结，不直接沿用不适用上限。列清完整观测和策略步后观测的camera、context、render/readback、mapping及cleanup调用边界；不要把静态单帧的1context/1frame预算直接移植到原生链路，也不要将库内部未知调用伪装为逐项已计量。
5. 新计数继续区分 `diagnostic_native_resets_returned`、`diagnostic_observations_returned`、`usable_observation_artifacts`，初始化物理子步与策略控制步分别计量。为真实前后RGB/动作/transition及5个H队列检查准备产物；未到达的阶段保留缺失原因，不把reset返回当作RGB就绪。
6. 只跑与改动相关的CPU fake/static检查：物理映射传递、导入/可见性约束、失败清理、观测计数和新release拒绝路径。fake检查禁止实际ctypes库加载/符号查询、CUDA/EGL调用及MuJoCo环境实例化。不重跑旧全套测试，不重复hash大模型来替代CPU检查；执行前的权重身份核验仍由新实际入口负责。
7. 发布独立新代码/config/manifests、PROPOSAL、RELEASE_TEMPLATE、CONTROL_REQUIRED及唯一真实命令和纯CPU授权入口。建议未来任务ID=`A10_PREFLIGHT_NATIVE_V2`；模板status仍为未授权。新真实入口沿用A-only、全8卡holder生命周期、claim一次性、当前release/host/UUID/driver/SHA守门；子进程1800+30秒可复用但前置准备/预约/恢复另计，不承诺端到端1830秒。

## 交付与限制

先写 `receipts/A/A10_NATIVE_EGL_INTEGRATION_CPU_V1_ACK.json`；最终交同名前缀REPORT.md/RESULT.json及新的CPU_READY、manifest和有限native提案。短报告聚焦接入方式、相对v5差异、检查结果、资源增量和未验证部分，避免大段实现代码。复用既有资产清单；全部新证据保留。

本次实际GPU库dlopen/CUDA/EGL/模型采样/环境初始化/reset/物理推进/训练/删除均0；无额外GPU/NVML探测，不调用真实launcher作dry-run。已有occupancy按用户要求继续运行，CPU准备不停止holder。不要自行运行native v5或新native V2；分析端审阅新提案后另发计算release。
