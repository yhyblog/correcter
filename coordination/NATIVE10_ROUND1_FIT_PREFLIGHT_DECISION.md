# 第一轮训练前预检：权限与方法口径

2026-09-16，分析端决定。新增独立 `round1_fit_preflight` scope/stage，条件放行完整数据审计、B 的 train-only PCA、A/B 初始化与保存重载检查。**新增仿真 0，优化器更新 0；不放行正式训练。** 执行端负责实现与运行，不需再次请求用户许可。

## 1. 与正在运行的采集隔离

- `main_protocols/round1_v1` 的 config、freeze、代码和 READY v4 快照保持不变。继续现有采集权限、配对随机流和预算。
- 预检使用独立版本目录、配置、代码及 READY v5 快照，绑定原采集 config/freeze、注册表、输入数据 seal、审计代码与训练设计。不要在冻结主协议内追加 stage 或修改训练入口。
- 当前 `require_stage_budget` 只接受正数请求，不能拿它预留零预算阶段，也不能为通过该接口虚构 1 次训练更新。新入口独立核验 stage/scope、READY 与配置 SHA、预算严格为 0/0，并在执行前拒绝未授权阶段。
- 本 scope 不允许 optimizer.step、调度器推进、训练检查点选择、策略 rollout、新 capture/restore 或任何仿真尝试。PCA 拟合须单独记录，不能因优化器为零而声称“没有进行任何拟合”。正式 GPU 工作仍遵守 lifecycle 与 holder 规则，不干扰采集波次。

## 2. 数据就绪条件

- 首轮预登记的 300 train 和 100 development 槽位全部有终态，形成静态输入快照。仍在增长的 live bank 和三源 smoke seal 不可用作正式输入。
- 完整审计必须逐项检查注册 split/round、source/bank/branch seal、attempt 与配对后缀、raw 命令映射、alias、完整标签，以及 **scene_identity 和 replacement_chain**。这些必填检查缺失或失败均不能继续 PCA/初始化。
- 按原协议合法无 cut、无报警或提前终止的槽位保留原因及原计划分母；与文件缺失、未完成分支区分。不能按结果换源，不能静默丢弃缺失行，也不为凑足 300 个可训练 bank 改变预登记分母。train 实际有效源数和 dev 共同结局处理单列。
- 只读取第一轮 train/development；P0、第二轮、calibration、heldout 不进入此数据集。记录两用途的实际 ID、seal 和交集检查。Dev 标签可以审计完整性，不可用于选初始化、拟合投影或修改方法参数。

## 3. A/B 必须先共同通过，再允许任何优化

- A：加载既定旧四成员权重及原投影，核实冻结与可训练参数范围；不重新拟合 A 的 PCA。
- B：仅用第一轮唯一有效 train 源拟合视觉 16 / 语言 8 维 PCA。一个 source 只贡献一次特征，不能按候选、后缀或 bootstrap 重复加权；四成员共享这一 train-only 投影。
- 按既定种子生成 B 的四个初始成员，以及 A/B 各自按任务分层的 source bootstrap 清单；候选和四后缀随 source 整体抽样。不得根据 dev 表现挑初始化、重新抽种子或改投影。
- 记录真实 PCA 奇异值、尺度和数值截断；沿已登记的 canonical 预处理路径检查缓存、在线目标与保存重载的一致性。检查 A/B 全部成员的概率和动作梯度、输入表示、a0 锚定、冻结参数范围及 ensemble 汇总。容差在运行前固定，不依据结果放宽。
- 编排顺序是：数据审计通过 → PCA/两路初始化 → **A 和 B 全部通过概率/梯度重载审计** → 写出预检产物。任何一项失败即保持零优化更新，不能先训练 A 再验证 B。
- 正式训练必须加载预检通过的同一投影和成员初始权重，绑定同一输入与 bootstrap 清单。若确需重新生成，必须先验证生成结果与预检产物 SHA 一致；不允许审计一套初始化、训练另一套。

## 4. 输出和后续放行

独立报告至少包含：scope/stage 与 READY SHA，原采集 config/freeze SHA，train/dev 输入清单与 seal，全部必填数据检查，实际有效源数，PCA/初始模型/抽样清单 SHA，代码及运行配置 SHA，A/B 每成员重载检查、预登记容差、失败详情，以及 `simulator_calls=0`、`optimizer_updates=0` 的运行记录。

将上述报告和完整产物清单封存为一个可绑定的预检结果，使用 `passed` / `failed` 明确状态。条件通过只说明训练输入和初始化可信，不能解释为纠偏有效。

分析端复核通过后，另行发布正式 `training_round1` 授权，绑定该预检产物及其 SHA。A/B 损失、步数、开发选择和后续实际策略测评均沿原任务书与补充，不在本预检中改动。第二轮、校准和 heldout 继续锁定。
