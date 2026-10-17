| 项目 | 可用 / 缺口 |
|---|---|
| CPU 修订 | complete；本任务实际 CUDA/EGL/dlopen/模型/仿真/训练均0，未执行提案 |
| 物理映射 | 单一路径 EGL_CUDA_DEVICE_NV → 原样 CUDA handle → PCI → 内核 UUID；与固定 NVML 目标核对，唯一匹配才进入context |
| CUDA 库 | 现有535.161.08，SHA `81b63dae639c3b1bc47692a63cab356419deaabda0fe0ce7f538c52351cc6084`；新隔离包绝对路径优先加载，排除550 compat；旧EGL/GLVND 8库内容相同 |
| 可见性 / ABI | 冻结8个完整UUID及PCI_BUS_ID顺序；EGLAttrib 8字节、CUdevice/CUresult 4字节，handle 0合法，不以任何API索引互猜 |
| raw / 错误 | NULL与空bytes分开，EGL属性/返回码/CUDA PCI buffer即时记录；EGL error按调用点预算查询，未查状态不推断 |
| 检查 / 未验证 | 31 CPU fake检查通过，3授权拒绝通过，7 AST/2 shell检查及33 bundle SHA通过；真实cuInit/映射/context/RGB尚未验证 |

新graphics任务建议ID：`A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1`。当前只有本CPU任务获准；下列预算和命令均为待新release提案。

| 下一次 graphics 显式调用 | 上限 |
|---|---:|
| attempt / EGL枚举 / cuInit（各） | 1 |
| 扩展字符串 / CUDA属性 / CUDA PCI（各） | 8 |
| eglGetProcAddress / 核心EGL符号 / CUDA符号 | 5 / 11 / 2 |
| eglGetError（含初始基线和清理） / 显式驱动库加载 | 35 / 2 |
| display初始化 / EGLcontext / 静态model+data / mj_forward / render+RGB（各） | 1 |
| EGL字符串 / GL字符串 / makeCurrent | 2 / 3 / 2 |
| context销毁 / terminate / releaseThread / MjrContext free（各） | 1 |
| CUDA context/kernel、DRM/binary/UUID额外查询、VLA/MetaWorld/reset/物理推进/训练/重试 | 0 |

`cuInit`单列计费；driver内部资源未知，不能由显式CUDA context调用0推断内部消耗0。VRAM1GiB/RAM2GiB/output32MiB仍是估计。子进程120s TERM+10s KILL覆盖hash/load/cuInit/映射/单帧/cleanup，前后准备、全A holder预约与恢复另计；A全8卡停到进程族退出含失败再恢复，B不参与。

真实命令（本轮未执行）：`bash /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CUDA_MAP_CPU_V1/commands/run_proposed_graphics_probe.sh /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/releases/P10_A_EGL_CUDA_MAP_GRAPHICS_PROBE_V1.json`。cwd=`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CUDA_MAP_CPU_V1`。

纯CPU授权命令与精确CONTROL/TASK_BOARD字段见 [COMMANDS](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CUDA_MAP_CPU_V1/proposal/COMMANDS.md)、[CONTROL_REQUIRED](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CUDA_MAP_CPU_V1/proposal/CONTROL_REQUIRED.json)；分析端生成独立新release后才可运行，不复用关闭的v1。所有候选的EGL属性/PCI/UUID必须可信，任何失败或重复映射即停，不尝试其他context、库、renderer或字节序。

设计和规范依据见 [MAPPING_DESIGN](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CUDA_MAP_CPU_V1/MAPPING_DESIGN.md)；ABI、库来源/顺序和完整caps均已冻结。[CPU证据](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_EGL_CUDA_MAP_CPU_V1_r1/CPU_FINAL_CHECKS.json)覆盖本次改动，未重跑旧CPU全套。原bundle、失败记录、native v4/v5均保持；本轮不要求平台补挂载或重建容器。

[PROPOSAL](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CUDA_MAP_CPU_V1/proposal/PROPOSAL.json) SHA `afb08b914bc746e8b570b670c90a40e681a98dc6528f6ec1cedba53468da3a7b`；[BUNDLE](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CUDA_MAP_CPU_V1/BUNDLE_MANIFEST.json) SHA `c60bdc602ea96962f794f1b21fce4d57a9d0f6c03b681bc8a78904af259f47fe`。当前guard自报8 holder，CPU任务未停卡；新增产物全部保留，无删除。
