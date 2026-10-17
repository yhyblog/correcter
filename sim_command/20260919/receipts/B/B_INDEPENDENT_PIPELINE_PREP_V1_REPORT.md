# B 独立流水线 CPU 准备回执

本次准备已交付；当前没有训练或正式评测授权，也没有执行模型计算。已有输入的 E1 提案先交阶段冻结：`proposals/B13_E1_FIT_TRAIN600_V1.json` 含 48 个真实入口 argv/cwd、配置与 SHA、输入、输出、资源、有限操作数和失败规则。机器可读总 DAG 在 `STAGE_DAG.json`，十个阶段独立阻塞，A 不等待 B。

| 阶段 | 本次交付与下一道门 |
|---|---|
| E1 历史 train600 四损失 | 输入就绪，真实 CPU fit 入口与 48 配置已交；待一次阶段冻结和公共队列接入 |
| E6 因果 D5→R | 元数据阈值校准入口已实现；缺真实开发预测/到达/action/reset 对齐轨迹及精确 D/G0 冻结身份 |
| E1/E6 H10 评测 | 缺新协议闭环驱动与 E5 阶段包装、P20_B_MECHANISM 源/seed/预算；argv=null，未伪造可运行命令 |
| GAF-v1 adapted | 3 个 critic 拟合入口/配置已交；缺与 A 相同的终版公共池、非空互斥开发集及 tensor 视图物化 |
| VLA-Corrector | 旧 h1/k10 权重和元数据存在；缺合法 normal-demo 的端点 token、有限抽取/训练配方及新队列训练入口 |
| E3 H10 比较 | 缺上述模型与新协议真实运行入口；绑定相同 A 公共池/评测身份，不依赖 A20 执行完成 |
| Smol50k | 精确保留 checkpoint 与任务序列已列；缺 Smol 专属 D/G0/Q 与 Post/Velocity 真实适配；不续 100k |
| X-VLA MT50 SFT | 既有初始化、数据、seed42/30000步/global batch64 配方及 B 私有输出 backend 已列；DDP 阶段入口、计数/取消/本机身份需完成，backend 不是队列入口 |
| X-VLA Corrector | 仅依赖自己的完成 checkpoint 与方法适配，不阻塞 Smol/LIBERO |
| π0.5-LIBERO | 官方权重和本地29999各自资产/规范已列；需独立冻结其一及对应归一化，缺 JAX Corrector 与方法数据/预算；旧 N 结果不作本轮完整方法结果 |

E1 输入实查了 train600 的 33,612,902B NPZ、rows、注册 manifest 和四个约 0.7MB 既有 critic checkpoint 的 SHA；只读二进制身份与数组头，不加载模型。600 个唯一 train parent，五任务各120，与95个有效 development cut 行互斥；原 planned development=100，95行不是 E6 全部开发轨迹，不能把缺少的5行删掉后冒充完整阈值校准集。固定 source/env seeds 全列于 `INPUT_AUDIT.json`，历史13候选×4真实结局保留，未换成新公共池的重复数。

E1 四损失 L00/L01/L10/L11 × 三个完整拟合 seed 9101/9102/9103 × 四成员1041–1044，共48个作业。每个4000步，AdamW lr1e-4、wd.01、batch16、gradclip1，7058参数，只训练 residual/advantage；冻结预处理与初始成员沿用 B10。总上限：192000 forward/backward/optimizer attempts/updates，48次初始化及小 checkpoint 读取，28800次已有特征投影；仿真/VLA/GPU inference=0。CPU device 保持冻结配方；8个 CPU 作业不冒充8卡真实 GPU 利用率。每作业1800s＋20s退出宽限，RAM3GiB的工程预约需实际准入，不是实测峰值。

E6 同两个 D 成员241/242的目录、小元数据已核对，权重只 stat，没有读取。完成身份仍须随真实开发 trace 冻结到具体 selected checkpoint、delta_scale、G0 规则和 R/Q 配置；不能以“目录存在”冒充该绑定已齐。`calibrate_e6.py` 要求真实 development-only、每 parent 一行、因果动作/reset 对齐声明和 SHA；阈值取最接近 G0 干预 episode 数、并列偏少再偏高，不读成功标签，最多一次干预，收益与异常均接 R。其 CPU metadata 命令真实存在，但缺输入时不会运行；实际 D 推理/轨迹生成没有授权。

GAF 每成员9201/9202/9203各10000步、batch256、lr1e-4、wd1e-4，每1000步只按开发 MSE选模；3成员组成一个 ensemble，不能宣称三套独立方法 seed。三成员共30000训练 forward/backward/optimizer步，最多1200开发 forward；train cap1000000、dev cap10240，超限拒绝，不截数据。state4、实际已执行10×4动作、language2048；γ=.99按实际控制步，成功时间是动作后状态。B11 当前17处理父源中的16 paired只用于接口，0 development，不可直接启动该训练。tensor物化工程仍列为缺口。

LVM 使用256×2048 float32端点，每个独特帧2,097,152B，按实际需要的唯一帧计存储和抽取；没有 latent cache。原 h1/k10、delta_z、展平cosine、按parent split保留，不能把 controller 切片当normal demonstration，也不重播旧随机frame-pair拆分。正式 E3 使用同 π0.5 checkpoint/normalizer、H10/总时域/环境资产/预定初始源；LVM原有重复安全触发/cooldown10与GAF逻辑分别披露，不改为统一G0一次。

E8 各底座/环境独立冻结。Smol固定50000不续100000；X原始MT50初始化尚非训练完成checkpoint，H30/K10、物理action4与内部20维区分，30000步和8 rank计数仅是候选SFT预算，172800s是工程超时提案并非实测耗时，80GiB存储需根据实际优化器/shard/保留规则再冻结。LIBERO本地29999是推理资产、optimizer不在；官方与本地归一化不能交叉。LIBERO state8/action7/双图/H10/K5，legacy套件上限220/280/300/520和10步settle单列，不移植MW的4维/300步假设。缺少评测 episode 数/源身份时保留 null 和 released=0，不编造科学预算。

每项真实命令、代码/配置/输入引用、资源与输出目录、并发上限及成功/partial/异常规则均在 DAG/提案中。E1/GAF 的 `stage_gate.py` 在导入框架前校验当前CONTROL、一次阶段注册、代码/配置/输入 SHA、操作上限、当前占卡覆盖和唯一继承预约；ENTERED排他登记后未知执行不自动重跑。新的 `CONTROL.stage_authorizations` 是提交分析与公共程序对接的明确接口提案，尚未由B写入公共CONTROL。预览命令不导入框架，`--execute` 在当前授权下必拒绝。

队列目标是真实独立种子/方法/分片资源准入后最多8并发，阻塞阶段不挡其他本机阶段。`resource_admission.py` 是纯控制面选取函数，公共daemon仍需提供当前CPU、host MemAvailable、cgroup余量、VRAM、tmp和共享ledger，unknown不当无限；保留A下一8源93,952,475,136B，已有A预约不重复扣。仅短时存储记账锁，B失败不写A/global stop。真实GPU指标每15秒、每卡滚动利用率/空闲、队列长度和加载/仿真/推理阶段另计，日志上限32MiB；这些是提交给公共daemon的要求，不能据此声称daemon已实现或已经8卡实验。

交付期间CONTROL revision3新增SHA绑定 `OCCUPANCY_OVERRIDE_V1`：原guard预约仍保持单锁，模型进入前指定卡的自有holder及后代须已退出，活跃正式卡不得加holder；监督空闲卡补位只按当前覆盖执行，辅助GPU活动独立记账。最终监督holder退出后再交回原guard。当前只做CPU准备、原8卡guard保持运行，科学GPU调用0不代表机器GPU活动0。混合占卡和不同host条件的原始E5时延不直接作算法效率排名。

10项新增CPU接口检查通过：当前阶段拒绝/host/撤销/SHA/占卡覆盖绑定、资源8并发与补位、cgroup和未知容量、A空间底线、独立阶段阻塞隔离、E6输入拒绝、失败状态落盘和完整seed矩阵。没有重复B10旧全集、没有模型导入/初始化/训练/评测/特征抽取/GPU探针/大权重hash，也没有修改共享源码、环境、CONTROL、任务板或A输出。
