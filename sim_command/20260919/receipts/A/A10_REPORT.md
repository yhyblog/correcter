# A10 r1：CPU 准备完成，未运行 GPU 预检

本机 A：trial-303224955-trialrun-303224955-worker-0。CONTROL revision 5 / P00_PREP_V1；A00 已完成且结果 SHA 未变。
本次训练更新、模型采样、simulator attempts、完整 rollout、实验 GPU 秒全部 **0**。8 个 occupancy holder 继续运行，属于既有占卡政策。

| 交付 | 状态与边界 |
|---|---|
| 公共接口 v1 | 七类 schema＋7 样例不可变；B 的23条样例通过 A 语义校验 |
| 独立 Post/Velocity | 原自身半径/mask/raw恢复代码冻结；Post S²、Velocity 同噪声、自采 a0；CPU 回调入口 R/P/V 为1/1/2，真实梯度未预检 |
| H/C 队列 | H10/20/30/40/50；C10结束丢弃尾部并新采 nativeH；先终止再监测；最后合法 cut 为285/290/290/290/290 |
| 核心矩阵 | 严格16单元：各H N/P/V，只有H10加R；同源所有单元保留在显式指定主机 |
| 数据索引 | 700个train/development父源＋600条固定a0/repeat0后缀，1300条全部核验；359段有真实首次成功时间；不含历史held |
| 数据缺口 | 上述是限定覆盖索引；其他候选/重复未宣称全部索引。旧RGB/next及独立terminal标志仍缺失，不能充当完整新公共池 |
| 双账本与恢复 | entered仅计一次；成功/部分失败/缺末事件三个持久化样例；N shadow排除部署；完成复用校验SHA，不凭过期心跳重试 |
| CPU验收 | 系统Python3.11/NumPy1.26与实际Python3.12/NumPy2.2各42项通过；381文件在实际3.12下AST通过；shell通过；P00拒绝真实命令 |
| 实际预检命令 | 已准备，尚未执行。只检查原生底座加载/队列/渲染/单步数据，不声称P/V、MT50 corrector或正式评测已验证 |

当前正式交付使用 `results/A/A10/code_snapshot_v3/`、`preflight_v3/`、`commands_v3/`。v1/v2代码快照留作准备证据；公共 `interface_v1/` 从未原地修改。
代码manifest SHA：`07f4b2eb87e93c563621bd346b1b75a2a2ddb82b97492dd4f5d1c52757941687`。
预检proposal SHA：`0501efafe971d92a5de21d462b590f5ffbd221aa1867f0e2b01ea2892f23d391`。

## 可执行有限预检报价（需要新 release，本次不运行）

命令文件：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10/commands_v3/run_proposed_native_preflight.sh`，唯一参数为分析端新发布的绝对 release 路径。
工作目录：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10/code_snapshot_v3`。CPU复核命令为同目录旁 `commands_v3/cpu_checks.sh`。
配置与输入：`preflight_v3/PROPOSAL.json`、`source_manifest.json`、`RELEASE_TEMPLATE.json`（模板不是授权）。

| 数量 | 上限 |
|---|---:|
| 候选诊断初态 | 1：shelf-place-v3，env seed2026091900；development，不作为测试结论 |
| 模型初始化 / 环境初始化 / reset | 1 / 1 / 1 |
| simulator attempts / 物理状态恢复 / 完整rollout | 1 / 0 / 0 |
| 完整VLA采样 / 实际flow前向 | 5 / 50；同观测分别核验五种H，不由方法名补账 |
| 真实环境控制步 | 1；保存step0/1图像、proprio、raw动作、真实success/reward/native终止标志 |
| VLA反向 / Q前后向 / monitor / optimizer | 全部0 |
| 重试 / timeout | 0 / 1800秒，TERM后最多30秒强制退出 |

依赖：冻结4MB LeRobot源码、既有Python3.12/torch2.7.1环境、持久SFT030000完整7文件、固定tokenizer版本、EGL。运行前重新核验大权重SHA；A00/A10仅核验其尺寸和历史SHA，小文件及tokenizer已hash。
估计峰值（未实测）：单GPU显存40GiB、主存64GiB、新增磁盘2GiB；真正加载/渲染可用性仍待这次有限预检。
执行前校验本轮CONTROL、任务revision、proposal/code/input SHA、host和实际GPU UUID/driver；不读取旧READY或旧493余额。
这份命令只允许 **A-only wave**，整个命令经occupancy lifecycle包装，A全部holder停算至退出（含失败）；B不参加时维持自身占卡。联合A/B release被此启动器拒绝，后续联合生产launcher必须冻结双方compute-exited完成/失败屏障后再放行。
保留claim、逐调用事件、失败、账本、5个raw计划、前后观测和单步transition；失败不换源、不自动重试。

## 后续边界与证据

- A12仍需MT50 D/G0/Q绑定与适配；五任务旧A4000不能直接改名。真实Post/Velocity与D特征需另一个带数量的预检配置；当前最小原生命令不覆盖它们。
- 新公共池尚未采集。B要求逐步观测、policy预处理state、任务embedding及normalizer身份；以后按prefix1或逐步索引落盘，绝不由聚合终点补图。E1继续用现有train600，不补采600源。
- B13负责E1实际训练入口与共同初始化/更新预算；A交 `configs_v1/E1_training_shape.json`（4损失×3完整seed槽，12个完整ensemble fits，不能把成员当seed）。实际seed/更新数为null待发布。
- `configs_v1/core_eval_matrix.json` 给16单元的无失败独立整episode采样上界，合计261 calls/source/repeat；尚无测试源数量、真实Q/反向调用上限，因此不是正式评测预算或已发布评测launcher。
- `data_access_v1/DATA_ACCESS_READY.json`、`existing_trajectory_index.jsonl`、`parent_splits.json` 供分析端冻结共同访问身份；首次成功按动作后状态step+1，无成功前缀不冒充整episode失败。
- E3原生多次引导由完整事件流表达；单值cut/entry可null+原因。计划、完成及技术失败分母分开，最终恢复/统计规则待P20。

资源盘点单列：共享磁盘statvfs为池级容量（项目quota未知）；host RAM约2015GiB、available约1631GiB（容器额度未暴露）；8×H100每卡81559MiB，holder占1013MiB、49–50%，guard PID27508。详情 `evidence_v1/node_capacity.json`、`gpu_snapshot.json`、`occupancy_status.json`。
存储候选 `receipts/A/STORAGE_CANDIDATES.json`：4项明确keep，9个Smol旧中间checkpoint共14,494,556,639逻辑bytes标defer，尚未排除历史封存/B恢复依赖；删除0。分析端未发布精确删除清单前不执行清理。
CPU路径/解释器检查失败及恢复见 `evidence_v1/FAILURES_AND_RECOVERIES.json`；未触及旧封存、旧训练队列或另一节点文件。
