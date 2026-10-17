# A10 EGL CPU 修复准备 V1

| 项目 | 交付 / 缺口 |
|---|---|
| 实际加载路径 | conda有GLVND1.7.0的libEGL；Python/_ctypes的RPATH可找到私有库。系统ldconfig缺项不能推出没有EGL |
| 根因证据 | 实际查找目录缺NVIDIA EGL vendor/core/glsi和vendor JSON；启动能力为compute,utility。此证据支持vendor栈缺失，未执行EGL，尚未排除设备/扩展等第二问题 |
| 隔离修复 | 复制4个既有GLVND库；从NVIDIA官方下载3个535.161.08拆分包共21,961,782字节，仓库SHA全部匹配；4个NVIDIA库加4个GLVND库共88,876,552字节。无系统安装 |
| 静态依赖 | 18个ELF对象的DT_NEEDED候选均可解析；额外补齐动态引用的同版本shader库。未使用dlopen/ldd验证，不把静态通过写成运行通过 |
| 设备挂载 | 沙箱外nvidia0/ctl/uvm存在；dri/modeset不存在。sysfs card1/renderD128均指向目标PCI0f:00.0。当前不能断言这些缺项对headless EGL必然致命 |
| CPU验证 | 16项定向合成测试、9个相关Python AST、2条shell语法、3次纯CPU拒绝路径、438项发布文件SHA通过 |
| 当前资源 | 模型GPU、graphics、EGL枚举/初始化/context、渲染、仿真/reset、训练、删除全部0；只读guard状态显示8holder存活 |

发布入口：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CPU_REPAIR_V1`。`proposal/PROPOSAL.json` SHA=`f5ea6f220c760465ab4ee93e459bb3e63f508d2d51a22e5e477ea375446f319b`；`BUNDLE_MANIFEST.json` SHA=`40040cd0e6134d715ffc025156b0e7118a9f35e7d01bf6e7a36700b1a1ee6639`。共享系统/conda及旧v1/v3/v4/失败回执均未改。

隔离vendor JSON固定指向本任务NVIDIA535.161.08库，子进程使用明确库路径、不继承CUDA550compat优先项；保持NVIDIA/EGL，无软件renderer回退。实际安装的MuJoCo3.6.0、PyOpenGL3.1.10及绑定文件共3006项外部源身份冻结；没有导入这些图形包作探针。

原MuJoCo在未设置MUJOCO_EGL_DEVICE_ID时可遍历EGL设备并尝试初始化；该ID也不等于CUDA序号。新独立探针只枚举一次，借EGL DRM路径→sysfs PCI→内核GPU UUID选择唯一目标GPU-17198167…/PCI0000:0f:00.0。映射缺失/歧义即失败，不逐卡试context。最多16槽、48次设备字符串查询，精确计数上限见proposal。

未来探针限1进程、1attempt、1display初始化、1EGL context、1个64×64静态MuJoCo场景、1次显式mj_forward（data.time不推进）、1render/1RGB readback；MetaWorld/策略模型/采样/reset/物理步/训练全0，重试0。成功只证明这次EGL RGB读回，不证明MetaWorld完整链路或P/V。

预估显存1GiB、进程RAM2GiB、运行新输出32MiB，均未实测。120秒TERM+10秒KILL仅限graphics子进程，含其hash/import/初始化/清理；前置检查、全A预约与holder释放、恢复观察另计，端到端严格上界null。复用已有全A holder生命周期，B不参与。

纯CPU授权检查：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CPU_REPAIR_V1/commands/check_authorization_cpu.sh NEW_RELEASE`。本次对两份P00及已关闭旧P10均按预期exit2，未用实际启动脚本作dry-run。未来唯一启动命令：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_EGL_CPU_REPAIR_V1/commands/run_proposed_graphics_probe.sh NEW_RELEASE`，本次未执行；分析还须独立发布graphics任务/CONTROL预算及RELEASE_TEMPLATE实值。

新`native_code_snapshot_v5`仅改原生预检计数：`diagnostic_native_resets_returned`、`diagnostic_observations_returned`、`usable_observation_artifacts`分开，观测返回后及有效文件写完后分别持久化标记。旧失败对应1/0/0，而总native reset是52；三个合成例子位于work同名JSON。v5只是代码修正，没有新的native预检授权。

平台当前无已证实必须操作：可先审核本隔离依赖与一次有限探针提案；若探针暴露设备/接口缺项，再按`work/A/A10_EGL_CPU_REPAIR_V1_r1/PLATFORM_FALLBACK.md`配置启动时graphics暴露。仅在现容器export能力变量不会补齐启动挂载。依据：[NVIDIA能力文档](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)、[官方拆分包仓库](https://developer.download.nvidia.com/compute/cuda/repos/debian11/x86_64/)、[EGL DRM映射规范](https://registry.khronos.org/EGL/extensions/EXT/EGL_EXT_device_drm.txt)。

工程检查失败记录：初次unittest命令遗漏CPU_TEST_ARTIFACT_ROOT，16项均在setUp报错、用例未执行；补齐命令环境后在实际Python3.12环境16项全过，未扩展旧验收。官方535.161.08 README网页不可访问，改以实际固定库、官方包索引及源码取证。所有下载、解包、测试临时证据保留并入manifest，删除0。
