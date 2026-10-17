# A：EGL 失败定向 CPU 诊断与隔离修复准备

task_id=`A10_EGL_CPU_REPAIR_V1`；task_revision=1；owner=A。执行依据 `releases/P00_EGL_CPU_REPAIR_V1.json`。前次 `P10_A_NATIVE_PREFLIGHT_V1` 已消耗并关闭；本任务不复用其剩余额度。

已知事实：π0.5完整加载成功，52 native reset返回；首次RGB渲染无法初始化EGL display，可用观测0。容器元数据 `NVIDIA_DRIVER_CAPABILITIES=compute,utility`、系统vendor目录/ldconfig缓存缺少相关条目只是线索，不能据此断言宿主不支持EGL，也不能排除私有环境里存在库。

## 当前允许的工作

1. 定向读取本次实际Python环境的MuJoCo/PyOpenGL版本、EGL加载源文件、GLVND配置、相关动态库实际路径和ELF依赖、驱动组件挂载，以及必要的白名单环境变量（MUJOCO_GL、PYOPENGL_PLATFORM、LD_LIBRARY_PATH、NVIDIA_DRIVER_CAPABILITIES、NVIDIA_VISIBLE_DEVICES、CUDA_VISIBLE_DEVICES等）。不要输出整份环境或凭据，不做全工作区扫描。
2. 区分系统`ldconfig`、conda/venv私有库和冻结launcher实际查找路径。使用文件/链接/ELF/包元数据检查；不调用EGL枚举、eglInitialize、创建context、渲染或其他graphics探针，不导入会立即触发这些操作的模块。NVML只读身份查询可按既有规则使用。
3. 若匹配本机驱动的完整用户态graphics依赖已可见，在`work/A`新隔离目录准备明确的库查找环境、vendor配置及启动脚本，版本与SHA冻结；只作用于未来任务进程。允许将必要的小型用户态依赖从可信源放入该隔离目录并静态验依赖，不安装/替换宿主驱动、不改共享系统/conda库、不重启容器，不大规模下载。
4. 若缺少必须由容器运行时注入的库或设备挂载，交精确缺项、来源证据和可执行的容器启动配置建议。容器内单纯export能力变量不等于补齐启动时挂载。先完成可自主完成的定位/修复准备，再说明是否需要平台介入。
5. 保持EGL/NVIDIA渲染路线，不静默切OSMesa/软件渲染来绕过问题。若只能换renderer，另报对图像/协议的影响供分析决定。
6. 在新版本里拆分`diagnostic_native_resets_returned`与`diagnostic_observations_returned/usable_observation_artifacts`，不改旧失败回执或封存。只复查有关命名/计数检查，不重跑整套CPU验收。

技术依据：NVIDIA说明驱动能力配置决定容器暴露的组件，`graphics`用于OpenGL等图形接口；这支持排查方向，不证明本次唯一根因。[NVIDIA官方文档](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)。MuJoCo的`MUJOCO_EGL_DEVICE_ID`对应EGL枚举列表，不能静默等同CUDA可见序号；以本机冻结版本源码为准，并参考[MuJoCo官方EGL实现](https://github.com/google-deepmind/mujoco/blob/main/python/mujoco/egl/__init__.py)。

## 下一步探针：只准备，不执行

提交独立、一次性的graphics-only探针提案及命令：一个进程、一个固定GPU物理身份、一个EGL context、一个小型静态MuJoCo场景、一次RGB readback。策略加载/采样、MetaWorld实例/reset、物理推进和训练均0；若绘制前需要`mj_forward`，显式至多1次，区分其与物理时间推进。建议子进程timeout120秒＋10秒宽限、0重试；精确EGL枚举/display/context/readback调用上限、初始化与失败计数由提案冻结。

EGL设备身份核查纳入同一次graphics探针：记录枚举索引与目标GPU UUID的关联证据，不把CUDA序号自动当EGL序号；无法确认时明确失败/未知，不循环换设备。此任务中只做静态映射方案，实际枚举也等单独GPU release。

输出图像、shape/dtype、GL vendor/renderer、设备映射及失败阶段；成功只证明EGL/读回可用，不代表MetaWorld完整链路/P/V通过。探针仍采用A-only波次、全A holder停算到进程族退出、失败恢复，不联合B。预计显存/RAM/磁盘给工程估计，不编造实测。

## 交付

ACK、短REPORT、RESULT写`receipts/A/A10_EGL_CPU_REPAIR_V1_*`；代码/配置/依赖清单/命令/有限proposal在本角色新work/results目录。报告先给根因证据、已准备修复、剩余缺口、下一命令/上限和是否需平台动作。资源账本：模型GPU/graphics/EGL枚举或初始化/仿真/reset/训练全部0，删除0。不把本CPU任务当graphics探针放行。
