# P0分析结论与第一轮主采集放行

2026-09-16。分析端决定：**P0已完成方法运行所需技术验证，继续扩大独立状态与局部真标签采集；条件放行第一轮300训练＋100开发，不因P0小样本效果要求额外试到显著。** 当前不选择最终方法，不放行实际模型拟合、第二轮、校准或保留测评。

## 1. P0说明了什么

20个初态、每任务4个，五臂各80个后缀结局。独立从400个原始分支与轨迹重建：normal/replan/velocity/direct/post成功数46/43/47/44/47；源级bootstrap区间复现。P0不是后续每任务20个初态的正式测评。

- 中断收益为−3.75pp，95%CI[−15,+3.75]，救回/损害2/5。
- Velocity和Post相对replan均+5pp，但相对正常native10仅+1.25pp，系统增益区间均跨0。
- 一个pick-place-wall初态贡献Velocity全部净增益和Post的75%净增益。尚不能据此选定可泛化赢家。
- shelf-place另一初态正常4/4、replan0/4，说明局部纠偏优于replan不自动等于值得中断正常策略。

技术上，原始队列、有效物理限幅、旧候选/轨迹迁移及32-worker复现均通过独立检查。并发新增64次后P0共564/600，无失败或重复；旧封存与P0冻结不变。32-worker活跃工作窗口约1.395分支/秒，含加载约199.6秒；不把4worker/GPU解释成4倍加速。

## 2. 首轮保持什么，分析什么

首轮保持原G0、旧critic候选生成、当前raw执行与可行mask、十步干预和native10后缀，保留13动作候选及正常第14臂。暂不根据20个P0源调门限或解除动作约束。

对每个cut分别分析：

`中断增益 I = replan - normal`

`纠偏增量 A = corrected - replan`

`总体收益 T = corrected - normal = I + A`

未来门控应比较正常继续、重规划与纠偏的总价值。**不能直接要求I>0才允许纠偏**：P0的pick-place-wall实例normal与replan均失败，纠偏却可救回。正常标签、旧队列有效余量及cut当时状态/G0分数必须保留；禁止从fallback后的未来事件提取模型输入。

另一个机制限制需要统计：shelf-place损害例的Z与夹爪被mask固定，三纠偏对应delta严格为0。它不表示模型认为这些通道不重要；增加同分布训练不会自动解除动作约束。第一轮记录各阶段/任务的可修改维度、饱和及候选别名，在更多独立数据后再决定是否需要门控、边界动作或通道预算修订。

## 3. 本次精确放行范围

- stage：`round1_labels`；bank version：`round1_labels_v1`。
- 300个训练primary slot：env_seed 2026111000–2026111299，每任务60。
- 100个开发primary slot：env_seed 2026111600–2026111699，每任务20。
- 400 primary episode ID列表canonical SHA：`0186cb243f51b83ef32fce30cb7f04ae9aedb97914f337007ea8ae692a802dec`。
- 每source13动作候选＋normal，各4个配对后缀。含400次capture、400次bank恢复及最多22400分支，阶段上限23200。
- 物理初态重复/初始化技术失败的预登记替补走`technical_reserve`，共用1200上限；不得按成败、无报警、cut未到达或Q值换源。
- 首轮只初始化被放行的400个slot及其合法备用，不能提前初始化round2、cal或held。整个主协议仍是600/100/100/100与4/4/2/4，总计划48800、硬限50000。
- 使用已通过复现的8GPU×4worker配置；GPU工作经lifecycle，波次结束/失败恢复holder。工程调度可在已验证配置内调整并记录，不改变方法参数或配对随机流。

## 4. 开跑条件与并行工作

执行端将当前版本CPU结果归档，通过现有freeze入口重新生成首轮config/代码/模型/manifest快照，绑定新的READY v4及本决定后启动。不能把仍绑定READY v3的pending配置直接当正式配置。旧P0继续依赖自己的READY v2快照。

真实数据尚未存在的dataset/PCA/模型重载检查列为fit-before，不阻断本轮有效采集。可并行完成训练器接线、合成CPU检查和数据完整性整理；本次实际训练更新授权为0，首轮真实训练放行另行登记。

首批约50个训练episode提供简短诊断：独立有效初态与cut覆盖、requested/actual/fallback分布、四后缀配对完整性、raw/有效动作一致性、各通道可修改比例、候选别名、救回/损害和配对信息量、实测吞吐/存储/预算。数据正确可继续采余下来源，不必等待正收益显著。技术错误或违反冻结才暂停受影响工作，保留失败记录。

第一轮完成后，以真实sealed数据完成PCA/四成员/导出与梯度加载检查，由分析端放行A/B训练。第二轮的数据/方法重点由第一轮结果决定；本轮不预先许诺收益。

## 5. 证据

- `coordination/NATIVE10_P0_ANALYSIS_REVIEW.md`：400分支独立统计和代表轨迹。
- `coordination/NATIVE10_MAIN_COLLECTION_REVIEW.md`：fallback、EVAL20、scene去重、manifest及采集接口增量审查通过。
- `coordination/NATIVE10_CONCURRENCY32_REVIEW.md`：480项候选/轨迹逐字节复现、64次账本及冻结核验。
- `outputs/native10_training_20260916/p0/`：P0原始审计及封存。
