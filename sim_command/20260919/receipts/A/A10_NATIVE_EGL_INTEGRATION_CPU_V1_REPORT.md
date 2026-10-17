| 项目 | 结果 / 缺口 |
|---|---|
| 本任务 | CPU准备完成；新 native V2 未授权、未执行 |
| 私有 EGL 集成 | 已冻结535库、8卡可见性、CUDA handle→PCI/内核UUID映射；GLContext接收实际handle；Torch文本UUID独立核对 |
| 原生观测链 | 当前 Gymnasium OffScreenViewer；1个EGL context、1个MjrContext复用，初态/步后各1张corner2 480×480 RGB |
| 有限提案 | 1诊断attempt，5 native/50 flow，1控制步/13物理子步；0 rollout/monitor/反向/更新/重试 |
| 初始化报价 | 不变：2原生环境+1wrapper，52reset/104reset_model/5200do_simulation/26000初始化子步 |
| CPU验证 | 18项定向fake通过（22次执行，含改动相关复查）；3授权拒绝；11改动源码AST、2shell语法通过 |
| 实际计算/删除 | GPU/CUDA/EGL/NVML/dlopen/模型/环境/reset/物理推进/训练/删除均0；holder未查询、未停止 |
| 待验证 | 真实模型+535库兼容、两张原生RGB和5次采样尚未实测，须分析另发native V2 release |

新包：`results/A/A10_NATIVE_EGL_INTEGRATION_CPU_V1/CPU_READY.json`。419文件CODE_MANIFEST、22引用INTEGRATION_MANIFEST及3133项继承/定向补充的外部源码身份已发布；本轮未重扫库存、未重hash大权重、未改旧v4/v5或共享包。

完整调用依据见 `STATIC_CALL_AUDIT.json`；相对v5的主要变化是私有映射/上下文接入、策略UUID绑定、前后观测分列计数及RGB产物、release独占claim、进程组退出后才释放全8卡预约。`diagnostic_native_resets_returned` 与完整RGB返回、可用NPZ分开；后观测另列。失败保留已入账/未完成事件、阶段与缺产物原因，cleanup不重试。

唯一真实命令（仅提案）：`commands/run_proposed_native_preflight.sh NEW_RELEASE_JSON`。纯CPU入口：`commands/check_authorization_cpu.sh NEW_RELEASE_JSON`。真实入口自带完整SHA/设备检查，不额外先跑checker；所有旧compute release仍不可用。

显式graphics成功目标108个操作：1枚举/1显式cuInit，扩展/属性/PCI各≤8，1context、2render/readPixels；辅助查询及清理精确caps见 `proposal/PROPOSAL.json` / `CAPS_AND_CONTROL.md`。Torch/MuJoCo/驱动内部API不逐项计量，不将显式cuInit上限解释成全进程调用总数。readPixels内部也填depth，保存的NPZ/PPM为同一次RGB观测，未来仍需视觉核对原生场景。

1800+30秒只包诊断子进程；前置SHA、预约、进程组清理、释放与恢复另计。预估41GiB VRAM/64GiB RAM/2GiB输出，非测量。当前CONTROL15/TASK_BOARD22计算全0；无技术阻塞，不申请复用旧额度。所有新增代码、fake产物和报告保留。
