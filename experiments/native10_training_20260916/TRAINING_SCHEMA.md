# Native10 训练参数与数据 schema 草稿

日期：2026-09-16。本文与同目录 `training_design.json` 是 P0 后提交分析端的实现材料，**训练尚未实现、尚未运行，当前训练更新数为 0**。批准训练设计不等于主采集/训练已经放行；当前 READY 只条件放行 P0。本文没有修改旧权重或任何封存产物，也不新增运行授权。

参数依据为 [主任务书](../../coordination/NATIVE10_TRAINING_TASK.md) 和 [已批准补充](../../coordination/NATIVE10_TRAINING_ADDENDUM.md)。原始命令表示还须满足 [raw 命令审查](../../coordination/NATIVE10_RAW_COMMAND_REVIEW.md)。文件 SHA 保存在 JSON 的 sources 中。补充协议明确取代旧审查草稿的 70/30：训练切点使用 **50% 首次合法报警、50% 预注册 scheduled**。以下将已批准参数与需要实现、审查的去重/mask细节分开。

## 1. Episode 分组、切点与标签规模

| split | 计划 episode | 每任务 | 用途 |
|---|---:|---:|---|
| train round1 | 300 | 60 | 原冻结 critic 生成候选；第一轮 A/B 拟合 |
| train round2 | 300 | 60 | 第一轮经开发选择后冻结的 critic 生成候选 |
| development | 100 | 20 | 固定候选银行选模型；两轮各一次真实五臂比较 |
| calibration | 50 | 10 | 已选模型/方法的接受规则；不更新 critic/PCA |
| heldout | 50 | 10 | 最终冻结后一次评价；前期禁止 capture 或读取结局 |
| P0，另计 | 20 | 4 | 技术诊断；与上述 800 个 episode 分离 |

分组键为 `(task, env_seed)`。同初始 episode 的所有策略噪声变体、切点、a0、候选、后缀和后来追加数据永远属于同一 split，不能通过改 case_id 拆开。P0 以及旧 99 primitive 源、45 flow 源默认不进入主训练。若以后使用旧数据，必须标记其历史、已曝光、native50 来源并记录开发决策，不能成为 native10 保留集。

每个训练 episode 仅一个主要 cut。每轮每任务 30 个首次合法报警、30 个 scheduled；scheduled 的 15/45/95 各 10 个，均为 native10 队列年龄 5 的时刻。没有报警、提前成功、未到达 cut 和技术失败均保留计划记录，不能为凑齐有用源而换种子。fallback 优先序必须在主采集前冻结；当前注册草稿为不回退、保留缺失原因，这仍须在 P0 后审查，不能以本文视为已正式冻结。

开发策略、校准、保留使用首次合法报警的一次干预；scheduled 训练样本不进入该策略成功率。无报警/报警前成功的 episode 在所有策略臂具有相同已观测结局，贡献零配对差值。技术失败没有已知结局，不能填成失败 0 或成功 1；需要重试审计或明确缺失，不能在缺数据时声称完整策略评价。

VLA 从 episode 初始按 native10 自然队列执行，预测长度仍为 50；合法干预须剩余至少 10 控制步。候选执行前 10 步，再按 native10 续跑至成功、终止或原总预算 300。

每个到达 cut 的训练源：**13 候选 × 4 配对后缀 = 52 个 critic 结局**，另有 **continue_native10 × 4 = 4 个正常控制结局**。后者不进入 critic 候选槽，不可填充旧队列冒充 a0。训练计划上限为 31,200 个 critic 标签 + 2,400 个正常标签；100 源开发银行为 5,200 + 400。未到达切点与合法物理复用会减少实际仿真，不增加独立 episode 数。

## 2. 十三个固定候选槽

| 槽位 | 机器名 | 构造 |
|---:|---|---|
| 0 | a0 | 同状态指定的新重规划；对应策略臂 alarm_replan10 |
| 1 | xyz_positive | 最终 post delta 的 XYZ 分量，正向 |
| 2 | xyz_negative | 同一 XYZ delta 的反向 |
| 3 | gripper_positive | 最终 post delta 的 gripper 分量，正向 |
| 4 | gripper_negative | 同一 gripper delta 的反向 |
| 5 | random_half_positive | 独立平滑联合方向的 0.5 倍正向 |
| 6 | random_half_negative | 同一方向的 0.5 倍反向 |
| 7 | random_full_positive | 同一方向的 1 倍正向 |
| 8 | random_full_negative | 同一方向的 1 倍反向 |
| 9 | velocity | 实际 velocity 引导并经部署构造的候选 |
| 10 | direct | 实际 direct 引导并经部署构造的候选 |
| 11 | post | 实际最终 post delta |
| 12 | reverse_post | 最终 post delta 严格取反 |

明确的五个正反 pair 为 `(1,2)、(3,4)、(5,6)、(7,8)、(11,12)`。候选名称与本目录待实现的 13 候选生成器一致；策略评价仍使用 continue_native10、alarm_replan10、velocity、direct、post 五臂。

XYZ/gripper 通道倍率按预注册 source 身份均衡分配 0.5 或 1。全倍率取最终 post delta 对应分量，半倍率严格乘 0.5。零梯度使用预注册平滑随机回退并打标，不按结局替换。联合随机方向独立于 critic，以各维三个时间节点的高斯值线性插值产生，半/全倍率共用同一对称可行 delta。

初始上限：XYZ RMS .05、L∞ .15；gripper RMS .10、L∞ .40；边界余量 .05。三种实际纠偏保持登记的部署构造；通道和联合随机正反对各用其指定的对称可行空间。**禁止把 13 候选一起送入旧的全方向共同最小半径匹配器**，否则通道消融的零分量会压零其他候选。保存实际幅度，不能把名义半径或 alpha 当实际环境扰动。

设 raw 新计划为 r，critic 基准为 b=C(r)=clip(r,-1,1)。实际发送 r+delta，critic 读取 C(r+delta)。保存并审查 `C(r+delta)=C(r)+delta`、零 delta 原样保持 raw a0、正反对称、尾部不变以及真实执行 RMS/L∞。P0 必须验证控制限制与真实动力学的表示等价；没有该证据，不可只按 clipped 动作合并物理候选。

## 3. 建议的数据包与审计字段

以下是实现建议，尚未由训练代码执行。一个状态行对应一个已到达合法主 cut 的 episode；完整计划 manifest 另存，不能只保留这些状态行。

| 字段 | 建议形状/类型 | 含义 |
|---|---|---|
| history / history_mask | N×5×4096 / N×5 | 当时已观测视觉与 mask |
| proprio / proprio_mask | N×5×4 / N×5 | 当时本体历史 |
| past_actions / language / remaining | N×4×4 / N×2048 / N | 过去动作、语言、剩余预算 |
| raw_commands | N×13×10×4 float32 | 实际请求执行的 raw 前缀 |
| critic_commands | N×13×10×4 float32 | 与该 raw 前缀对应的 C 表示；槽 0 为指定 a0 |
| actual_delta | N×13×10×4 float32 | raw_commands − raw_a0 |
| candidate_group_id | N×13 int | 相同物理动作的 alias 分组 |
| candidate_outcomes | N×13×4 int8 | 0/1；未知用 -1，并提供 validity mask |
| candidate_outcome_valid | N×13×4 bool | 真实结局或经严格审计的 alias 结局 |
| normal_outcomes / normal_valid | N×4 / N×4 | 正常 continue_native10 控制，独立字段 |
| physical_attempt_ref | N×13×4，外加 normal refs | 指向真实账本或明确的复用引用，区分物理次数与逻辑槽位 |

每行元数据至少包含 episode_id/task/env_seed/split/round、注册与实际 cut_rule、cut_step、源 seal/hash、状态行索引、a0 seed/初噪声 hash、生成 critic 四权重 SHA、VLA/D/G0/实现身份、candidate bank seal、实际 mask/半径/范数/fallback、完整 paired_suffix_id 与各后缀 decision-index seeds。bootstrap 抽样清单、数据版本和模型输入归一化/PCA来源单独保存。

paired_suffix_id 绑定 episode、cut、repeat、冻结的后缀协议与命名空间，不含 method。normal 与介入臂后缀按相同 decision index 配对，但采样绝对时间可能分别为 10/20/... 和 15/25/...，不宣称同状态或同绝对步噪声。source 自然决策流与 branch 后缀流使用不同域；所有纠偏共享同一 a0 draw seed，candidate_index 不是方法编号。

主策略评价可另用 `policy_outcomes[N,5,R]`，R 在开发/校准为4、保留为8，保留所有计划 episode。它与十三候选局部银行分开，避免把训练候选选择收益冒充实际引导策略收益。

## 4. 已批准损失与建议去重/mask

令 zᵢⱼ 为 logit，pᵢⱼ=sigmoid(zᵢⱼ)，qᵢⱼ 为四次完整配对成功的均值。标签是前缀之后续跑的最终二值成功，不是第十步结束是否成功，也不是 D 的预测误差。

批准的唯一主损失为：

`L = mean_source[BCEᵢ + 1.0 × GainMSEᵢ + 0.5 × PairDiffMSEᵢ]`。

- BCEᵢ：该源所有有效 distinct 候选组的 BCEWithLogits(z,q) 均值，包含 a0 一次。
- GainMSEᵢ：有效非 a0 distinct 组的 `[(pⱼ−p₀)−mean_r(yⱼᵣ−y₀ᵣ)]²` 均值。
- PairDiffMSEᵢ：有效 distinct 正反组对的 `[(p₊−p₋)−mean_r(y₊ᵣ−y₋ᵣ)]²` 均值。

每项先在源内平均，再在采样的完整 source 上平均，不直接展平所有候选后平均。正反项只是已有成功标签的定向加权，不是新梯度真值；四重复的 .25 粒度和 discordant/rescue/harm 数均保存。**不除以小半径**；不搜索1/1/.5权重。半/全半径曲线及同向差值保留为诊断，不擅加第四项排序损失或其他未批准权重。

推荐的 mask/去重规则，须由实现及分析审查确认：

1. 一个 distinct 组仅有一份候选损失权重；若张量保留 alias 槽，每槽权重为1/组大小。按同源状态、raw 十步命令、后缀协议/种子和冻结 VLA 判定可复用，不能只比较 clipped 数组。数值“接近”不自动等同完全相同命令。
2. 与 a0 完全相同的候选合并进 baseline 组，不重复计 BCE，不进入 gain 分母。它们的零相对收益由锚定结构保证。
3. 正反 pair 只有两个组均有效且不同才参与。正反 alias 或 delta=0 时 pair mask=0；多个 pair 指向同一无序候选组对时只计一次，避免重复加权。
4. 非零 pair 的对称性失效是数据构造错误，需要阻断审计，不能偷偷用 mask 藏掉。四个后缀不完整时，结局未知；不得填0凑齐训练标签。严格 alias 扩展可复用对应已审计结局。
5. 一个源没有有效非baseline gain 或有效 pair 时，该项取0；仍保留 source 外层权重及 a0 BCE，不仅保留“有信息”源。真正无合法 cut 的 planned episode 没有伪造的 critic 输入，保留在 coverage/策略分母。

正常控制标签只用于 `mean(y_a0−y_normal)` 的 native10 中断目标和独立策略评价，不进入以上十三槽 BCE 或 a0 锚点。若要据此训练 G0，另等目标/输入审查和 READY，不暗中增加第三训练路径。

## 5. 两条必须实施的训练路径

| 参数 | A：残差适配参照 | B：完整小 critic 重训 |
|---|---|---|
| 起点 | 只读旧四成员权重 | 四成员新初始化 |
| 更新模块 | residual、advantage | state、action、head、residual、advantage 全部 MLP |
| 冻结小网络部分 | state、action、baseline head 及所有归一化/PCA buffer | 训练拟合后固定的预处理 buffer |
| PCA | 原冻结投影 | 当前训练 split 重拟合，视觉16/语言8 |
| 学习率 | 1e-4 | 3e-4 |
| 优化器 | AdamW | AdamW |
| weight decay / clip norm | .01 / 1 | .01 / 1 |
| batch | 32 完整 source | 32 完整 source |
| 第一轮最大更新/成员 | 2400 | 2400 |
| 最终最大更新/成员 | 4000 | 4000 |

检查点为 200/400/800/1600/2400/3200/4000，第一轮截止2400。每条路径均四成员，两阶段总更新上限 `2×4×(2400+4000)=51200`，这只是拟议登记的上限，不是已执行更新数。允许按开发结果选更早 checkpoint；不能沿用旧800步结果作为新数据停止依据。

最终 A/B 均基于两轮全部新训练数据重新拟合：A 重新从原旧四成员 warm start；B 重新初始化并在600计划训练源的实际有效训练行上重新拟合 PCA，不把第一轮权重直接接到不兼容的新 PCA。B 必须完成，不能以 A 替代。VLA、D、视觉/语言特征提取器保持冻结；没有授权据本文微调大模型。

四成员按任务对完整训练 episode 做 bootstrap，有放回抽样并保存每成员的列表、重复次数、随机种子。候选与四后缀随 episode 整体进入成员数据。minibatch 均匀抽取 bootstrap 清单，重复 multiplicity 来自 bagging，**没有按成功、有益性或“信息源”再加4倍权重**。集成方差不是严格置信区间。

实现建议是 B 的 PCA 使用当前训练阶段全部唯一有效 source，在 bootstrap 重复前拟合，四成员共享这套 train-only 投影；这个具体共享方式须审查。不能使用 development/calibration/heldout 的观测拟合。延续 CPU float32、2线程和单源预处理路径作为初始工程方案，实际实现须检查新 PCA 单源/批量/线程数一致性；这些是待验证配置，不是已完成数值测试。

随机初始化、bootstrap、minibatch 使用冻结命名空间下不同 phase/path/member 域，并保存实际seed、bootstrap索引、checkpoint和优化器配置。A 的初始化是对应旧成员，不应写成随机初始化；B 才是新初始化。训练输出只能写新工作流的版本目录，旧 assets 与 ACT 路径仅只读导入，四个旧 SHA 已记录在 JSON。

## 6. 开发选择、校准和最终评价

每轮 A/B 所有集成 checkpoint 使用同一开发候选银行。每个源以四成员平均成功概率选候选，a0 在并列时优先；建议剩余候选并列按固定槽序，数值比较规则在读结局前固定。模型选择顺序严格为：

1. 全100个计划开发 episode 上，所选候选相对 a0 的真实配对净增益最大。
2. 净增益并列时，paired harms 更少。
3. 再并列取相对概率增益 MSE 更低。
4. 再并列取更早更新步数。
5. 最后优先 B。

无报警等已知共同结局源贡献零差值并留在总体分母；条件指标另列。技术缺失不能被无声删除。固定候选银行的最优 checkpoint 只是连续梯度部署的代理；每轮只对选出的一个 critic 跑一次100×5×4实际策略比较，两轮最多4000分支，不能把A/B各跑一套翻倍。

第一轮选定的 critic 在第二轮开始前冻结，并用于第二轮全部候选生成，不边采边更新。最终在开发集选择一个主注入方法/策略，再用50校准 episode 确定接受规则；模型、PCA不吃校准标签。拒绝纠偏回到同一a0。最后冻结模型、主方法、阈值及主比较后才打开50保留episode，其他两种注入作为预登记次要比较，不能从保留集挑最好者替换主结果。

## 7. 当前未完成事项与放行边界

本记录只转写批准设计并提出具体 schema：**模型训练代码、dataset loader、损失/alias实现、bagging、checkpoint选择均尚未实现或验证；没有训练产物。** 13候选与数据收集实现完成后仍须做实际动作、mask、对称、去重和配对审计。本文不能让 pending 配置运行。

P0 后提交：技术结果、raw命令物理表示检查、800个 episode 注册、fallback优先序、13候选与损失CPU审计、确定性训练配置/数据版本，以及实测 wall-time/GPU-hour/磁盘/attempt预测。分析端升级 READY 后才放行主采集与训练；校准/保留另按阶段冻结。现有50,000仿真硬限不变，candidate-only restore 等实际额外attempt必须在预算内显式分配，不能把逻辑复用当作未记账仿真。
