# ICLR标题与摘要素材：已封存实验事实复核

整理日期：2026-09-18。实验工作流：`native10_training_20260916`，最终结果于2026-09-17封存。

**用途：**给后续撰写论文标题、摘要的模型提供可以引用的实验事实与解释边界。本文件只汇总既有封存报告、独立统计及算法笔记；未新增实验、训练、模型调用或全量hash审计。它不判断论文录用概率，不代替相关工作的新颖性比较。

## 1. 可以直接使用的核心结论

在**五个固定MetaWorld v3任务、100个独立测试初态、每初态4个配对后缀重复**下，预先固定的 **Pi0.5＋冻结D/G0报警器＋A4000四成员critic＋matched-post** 将成功率从报警后仅重规划的 **53.50%提高到62.50%**：**增加9.00个百分点，任务分层源级95% bootstrap CI为[3.25,15.00]个百分点**。

这证明当前完整系统在所测设置中具有**超出普通重规划的额外纠偏收益**。点估计达到预登记+5pp目标，区间支持正收益；区间下界低于5pp，不能宣称真实增益已被证明至少5pp。Post在held结果打开前已经固定，未按held选择赢家。

证据：[最终分析结论](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/coordination/NATIVE10_HELDOUT_ANALYSIS.md)、[独立held统计复核](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/heldout_result_review.json)。

## 2. 测试对象和五个方法的准确含义

- 基础VLA为冻结Pi0.5（`sft_pi05_mt50/checkpoints/030000/pretrained_model`），本轮未更新基础VLA。每次生成50×4个raw命令，正常仅执行前10步后重新规划；总控制预算300步。
- 正常基线N=`continue_native10`：从episode开始即按10步周期规划，不响应额外报警中断；**并非整条episode永不重规划**。
- R=`alarm_replan10`：首次合法G0报警时丢弃旧队列剩余5步，以当前观测采样新的a0并执行10步，然后普通native10续跑。
- V/D/P分别为velocity、direct、post；与R共享指定a0及配对随机流，分别执行其matched候选前10步，然后普通native10续跑。
- 三种纠偏都只发生一次。主方法是**完整matched-post**；其共同可行半径仍依赖velocity/direct/post/反向direct/随机五个方向，后两者只生成保存，不作为额外物理测评臂。
- G0是旧协议下fresh−old终局收益回归头，两个成员平均值严格大于0.05且满足合法中断资格才触发；它不是失败概率，也不是D视觉预测误差阈值。当前10步纠偏Q与G0是不同模型。
- R−N同时包含中途动作替换、新10步承诺及后续规划相位变化；P−R等比较则固定这些因素，用于衡量纠偏增量。

证据：[完整中文算法文档](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/docs/NATIVE10_CORRECTOR_ALGORITHM_ZH.md)、[执行链审核笔记](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/algorithm_review_execution_notes.md)、[纠偏与匹配审核笔记](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/algorithm_review_correction_notes.md)。

## 3. 最终held：整体五臂结果

各臂为400个**逻辑计分结局**，独立统计单位是100个初态。

| 方法 | 成功数/400 | 成功率 | 相对R增益pp [95% CI] |
|---|---:|---:|---:|
| N：正常native10 | 168 | 42.00% | — |
| R：报警后仅重规划 | 214 | 53.50% | 基准 |
| velocity | 237 | 59.25% | +5.75 [0.75,11.00] |
| direct | 234 | 58.50% | +5.00 [−1.00,10.75] |
| **post：固定主方法** | **250** | **62.50%** | **+9.00 [3.25,15.00]** |

### 七个预登记配对比较

| 比较 | 增益pp [95% CI] | 配对救回/损害 | 正/负/零源 |
|---|---:|---:|---:|
| R−N | +11.50 [3.00,20.25] | 79/33 | 28/13/59 |
| V−R | +5.75 [0.75,11.00] | 32/9 | 13/5/82 |
| D−R | +5.00 [−1.00,10.75] | 36/16 | 15/7/78 |
| **P−R，唯一主比较** | **+9.00 [3.25,15.00]** | **46/10** | **18/6/76** |
| V−N | +17.25 [9.75,25.00] | 84/15 | 30/9/61 |
| D−N | +16.50 [9.25,24.50] | 82/16 | 28/9/63 |
| P−N | +20.50 [13.00,28.25] | 94/12 | 35/6/59 |

“救回/损害”按同源同repeat的0→1/1→0计数；“正/负/零源”按该源四后缀平均差值符号计数，不能互换。P−R净增36次成功，来自18个净收益源，也存在6个净损害源。

CI为任务内**整源**有放回bootstrap10000次，seed=`2026091622`，percentile95、linear分位数；源内四后缀与全部方法共同重采样。七项区间未作多比较校正，P−R预先固定为唯一主比较；没有另行进行P优于V/D的确认性比较。

证据：[held完整报告](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_diagnostics/heldout_v1/report.md)、[独立重聚合说明](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/heldout_result_review.md)。

## 4. 最终held：五任务全数

每任务20个不同物理初态×4后缀＝每臂80个计分结局。下表为“成功数/80（成功率）”。

| 任务 | N | R | V | D | P | P−R pp |
|---|---:|---:|---:|---:|---:|---:|
| disassemble-v3 | 52（65.00%） | 49（61.25%） | 59（73.75%） | 64（80.00%） | 60（75.00%） | +13.75 |
| pick-place-wall-v3 | 30（37.50%） | 58（72.50%） | 58（72.50%） | 60（75.00%） | 66（82.50%） | +10.00 |
| shelf-place-v3 | 16（20.00%） | 14（17.50%） | 18（22.50%） | 17（21.25%） | 22（27.50%） | +10.00 |
| stick-pull-v3 | 7（8.75%） | 17（21.25%） | 22（27.50%） | 21（26.25%） | 22（27.50%） | +6.25 |
| stick-push-v3 | 63（78.75%） | 76（95.00%） | 80（100.00%） | 72（90.00%） | 80（100.00%） | +5.00 |

五任务P−R点估计都为正，净增量为11/8/8/5/4次成功；**不表示各任务分别统计显著**。shelf与stick-pull最终P仅27.5%，仍有明显剩余失败。

### 为什么20个初态会出现61.25%等小数

同一初态的4次重复共享cut、a0及候选动作bank，只改变后缀策略采样的随机流；五臂在相同repeat及后缀决策序号上配对。某初态可以成功0/1/2/3/4次。先求每源四次均值，再对20源平均，等价于总成功数除以80。例如disassemble的R=49/80=61.25%，P=60/80=75%。这不是80个独立初态。

held有98个报警源和2个无报警源。两个无报警源都在pick-place-wall，一成功、一失败：真实共同结局分别在每臂逻辑计4成功和4失败，保留100源分母，不新增候选仿真。物理分支数为98×5×4=1960；逻辑结局总数为100×5×4=2000。技术缺失为0，不能把技术缺失当成无报警共同结局。

证据：[逐源CSV，100行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_diagnostics/heldout_v1/per_source.csv)、[独立统计JSON](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/heldout_result_review.json)。

## 5. 数据规模、分割与训练监督

| Split | 主episode数 | 每任务 | 用途 |
|---|---:|---:|---|
| 第一轮训练 | 300 | 60 | 旧critic生成局部候选，首轮训练A/B |
| 第二轮训练 | 300 | 60 | 首轮B200生成新候选，扩展监督 |
| 开发 | 100 | 20 | 固定旧13候选库选critic；真实五臂执行选择主方法 |
| 校准 | 100 | 20 | 固定Post后，仅决定全局启用/回R |
| Held | 100 | 20 | 最终预先固定策略的独立测试 |
| **主episode合计** | **900** | — | 600训练＋100开发＋100校准＋100held |

另有20个P0技术诊断episode，不计入900主源。初始化按物理scene身份查重；两份独立scene不是仅仅不同seed。只允许第一次动作前初始化失败/重复状态启用预登记有序替补，不按成功、报警、Q或纠偏效果筛源。

600训练源都达到一个有效主cut：每源13候选×4后缀，共**31,200个候选二值标签**；另normal×4，共2,400个控制标签，物理训练分支合计33,600。normal不属于critic的13候选，不进入Q损失或G0训练。候选或repeat不是独立source，不能把31,200写成31,200个独立训练状态。

每轮预登记150个first_alarm**请求**、scheduled15/45/95各50个。仅训练允许按既定优先级回退到已到达合法anchor；dev/cal/held没有scheduled或训练fallback。实际alarm/scheduled/fallback为第一轮142/129/29，第二轮146/130/24，合并288/259/53。两轮源前缀都由冻结原VLA正常执行，B200只改变cut候选生成器，标签仍来自真实环境续跑，不是teacher Q蒸馏标签。

### 训练诊断提供了什么证据

| 指标 | 第一轮300 | 第二轮300 | 合并600 |
|---|---:|---:|---:|
| 存在非alias候选均值差的源 | 109（36.33%） | 96（32.00%） | 205（34.17%） |
| 存在有益/有害候选的源 | 56/66 | 54/56 | 110/122 |
| 非a0 raw组正/负/零gain | 172/274/3108 | 232/199/3145 | 404/473/6253 |
| V/D/P相对a0训练标签增益pp | +0.92/+0.58/+1.42 | +2.50/+4.00/+3.58 | +1.71/+2.29/+2.50 |

第二轮增加了96个有可分辨监督的source，覆盖总量扩大，但信息源密度没有上升。合并395/600源候选四后缀均值相同；四次二值后缀分辨率有限，相同均值不证明真实收益或梯度为零。候选组相关，收益/损害源可以重叠。

这些是**训练采集器的标签诊断**，不是最终A4000部署效果。两轮source、cut和生成critic同时变化，不能据此推出teacher提升或数据量增加的因果收益。报警与scheduled分层也不是随机化的门控对照。

证据：[600训练监督审查](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/train600_method_review.md)、[正式600源方向诊断](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/coordination/NATIVE10_TRAIN600_DIRECTION_DIAGNOSTICS.md)、[训练算法笔记](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/algorithm_review_training_notes.md)。

## 6. 开发、校准、held结果分别回答什么问题

### 6.1 实际新生成动作的五臂结果

| 阶段 | Critic | 独立源×后缀/每臂分母 | N/R/V/D/P成功数 | P−R pp [95% CI] | P救/害 |
|---|---|---|---|---:|---:|
| 第一轮真实开发 | B200 | 100×4/400 | 221/257/265/268/267 | +2.50 [−1.25,6.50] | 20/10 |
| 第二轮真实开发 | A4000 | 同100源×4/400 | 221/257/270/268/274 | +4.25 [0.25,8.75] | 25/8 |
| 校准 | A4000 | 新100源×2/200 | 92/119/122/116/133 | +7.00 [3.00,12.00] | 15/1 |
| 最终held | A4000 | 新100源×4/400 | 168/214/237/234/250 | +9.00 [3.25,15.00] | 46/10 |

开发固定100源中95报警、5无报警（4成功1失败），两轮均保留400逻辑分母。校准96报警、4共同源（2成功2失败），保留200。held98报警、2共同源（1成功1失败），保留400。

### 6.2 选择顺序与可比性边界

1. 在固定**旧13候选开发库**上按预登记规则选critic：最大完整分母候选收益 → 最少损害 → 最低gain MSE → 更早step → B。四成员必须同一checkpoint，不按结局挑成员。
2. 首轮选B200，最终选A4000。最终旧库预测选择成功数275/400，相对a0 257/400为+4.5pp、救23害5；首轮B200旧库代理也是275/400，但救24害6。**旧库代理+4.5不是新生成Post的真实增益。**
3. A4000新生成五臂开发测评后，Post以净收益和损害的开发表现被固定为主方法；未因held较高才选择Post。
4. 校准只有两个全局选项：完整100源等权mean(P−R)>0则启用Post，否则统一R。规则不使用CI、Q、逐任务门或V/D重新择优；+7pp使Post全局启用，选择在held前封存。
5. 第一轮与第二轮开发使用同100来源，P点估计提高1.75pp；这只作描述。本轮独立报告没有做完整跨轮配对状态/随机流审计及跨轮差值CI，不能把点差写成训练因果效应。
6. 开发已被反复用于选模型和方法，不能当独立验证。校准用于启用开关，也不能替代held。A4000在开发、校准、held之间没有继续训练；**+4.25→+7→+9不是学习曲线**，这些数据集和重复数不同。三者不合并放大显著性。

证据：[首轮五臂开发](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/round1_policy_result_independent_review.md)、[最终五臂开发](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/round2_policy_result_review.md)、[最终critic选模](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/final_training_selection_review.md)、[校准独立复核](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/calibration_result_review.md)。

## 7. 资源与成本：必须同时交代测量范围

### 7.1 已用资源

- 全工作流累计**48,183次simulator attempt**，硬上限50,000；该计数含源capture、独立bank restore、分支（含恢复）及先前诊断，不是48,183个独立episode，也不是环境控制step数。
- 实际优化更新**51,200**：首轮A/B各4成员×2400，共19,200；最终A/B各4成员×4000，共32,000。它不是训练epoch数；基础VLA/D/G0没有更新。
- 最终held新增**2,158 attempts＝100 capture＋98 bank＋1,960物理分支**。校准新增1,156＝100 capture＋96 bank＋960分支。
- 最终held无缺失、替补、技术故障或重试；资源、初态、真实模型、动作语义、随机流与冻结审计已通过。此处沿用既有审计结论，没有再执行全量审计。

### 7.2 本轮并发配置下的实测耗时

8 GPU、每卡4 worker；以下均为对应事件的平均记录时间，不是通用硬件上的保证延迟。

| 项目 | 每报警源均值 | 范围 |
|---|---:|---|
| 无引导a0采样 | 0.361368 s | 基础采样子步骤 |
| velocity采样 | 0.484856 s | 引导采样子步骤 |
| direct采样 | 0.458213 s | 引导采样子步骤 |
| post梯度 | 0.003564 s | 仅额外梯度子步骤 |
| **完整候选bank** | **1.334741 s** | 排除source状态恢复；包括完整匹配所需方向生成 |
| source恢复 | 1.063736 s | 实验回放恢复 |
| generation wall | 2.436013 s | 包含恢复及生成相关开销 |

另有source capture wall平均4.346944 s（100源，reset至报警cut或无报警终局）；整波controller墙钟931.92 s（含lifecycle），worker初始化均值175.187 s。初始化包含绑定检查、CUDA和模型加载，不能当纯加载时间；worker累计秒不能当整波墙钟。

**3.564毫秒不能被写成完整部署时延。** 当前Post幅度仍依赖V/D/reverse/random生成；删掉这些依赖后的单独Post效率与收益没有在本轮被验证。bank也不是完整在线episode耗时：它不涵盖完整source监测过程、物理控制与后缀执行。没有因此得到实时部署保证或公平串行加速比。

证据：[held成本与诊断原报告](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_diagnostics/heldout_v1/report.md)、[最终资源/初态复核](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/heldout_completion_review.json)。

## 8. 标题与摘要禁止越过的证据边界

1. **不能宣称SOTA、首个方法或已优于GAF/QGF/QPILOTS。** 当前封存实验没有这些外部方法的公平对照；相关工作支持哪些新颖性需另行论证。
2. **不能把平均+9pp写成每次纠偏有效、无伤害或安全保证。** P−R存在10个受害后缀、6个净损害源。
3. **不能宣称概率已校准或Q能识别全部伤害。** 98报警源中97源Post预测收益为正，6个净损害源的Q均为正；预测与实际源收益Pearson约0.223、Spearman约0.192。当前没有逐源Q接受门。
4. **不能宣称五任务各自显著、真实提升至少5pp，或Post被统计证明优于V/D。** 只有固定总体P−R主比较；逐任务全正只是点估计。
5. **不能把完整P−N的+20.5pp全部归功于纠偏。** R−N已有+11.5pp，纠偏增量是P−R的+9pp；旧native50基线25.83%也不能替代本次native10的42%。
6. **不能单独归因于更多训练数据、pair loss、梯度方向、残差适配或matcher。** 本轮是组合系统验证，尚缺分离这些因素的消融，以及同预算best-of-K/同幅随机扰动等强对照。
7. **不能声称跨任务、跨VLA、跨环境泛化或真实机器人验证。** held是五个既定任务的新初态；没有新的任务集合、另一个VLA/环境或真机结果。
8. **不能称持续闭环多次纠偏已经验证。** 每episode最多一次首次合法报警干预，之后普通native10；也不能将G0称为视觉预测误差检测器或当前10步收益的已校准门。
9. **不能称无需训练、零环境交互、毫秒级完整纠偏或无额外推理。** 本轮有新critic训练与真实仿真候选标签；完整matched-post仍需全bank生成。
10. **不能合并train/dev/cal/held，或把后缀、候选、attempt数当独立初态数。** 无报警共同结局保留分母，技术缺失不能填0；开发/校准收益不是独立held收益。

上述限制不否定已成立的主结果：**对预先固定系统，在所测五任务的新初态上，独立held支持纠偏相对普通重规划的正增益。**

## 9. 最短证据入口

| 内容 | 文件 |
|---|---|
| 最终方法和算法参数 | [中文算法文档](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/docs/NATIVE10_CORRECTOR_ALGORITHM_ZH.md) |
| 最终held主结论 | [NATIVE10_HELDOUT_ANALYSIS.md](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/coordination/NATIVE10_HELDOUT_ANALYSIS.md) |
| 五臂、七比较、逐任务独立统计 | [heldout_result_review.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/heldout_result_review.json) |
| 原始逐源计数、成本、Q诊断 | [heldout_diagnostics/heldout_v1/report.md](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_diagnostics/heldout_v1/report.md)及[per_source.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_diagnostics/heldout_v1/per_source.csv) |
| 开发阶段真实生成动作 | [首轮](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/round1_policy_result_independent_review.md)、[最终](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/round2_policy_result_review.md) |
| 校准全局开关 | [calibration_result_review.md](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/calibration_result_review.md) |
| 600训练源诊断 | [train600_method_review.md](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/train600_method_review.md) |

关键封存身份（沿已有记录引用，本次未重跑全量hash）：held主审计complete `d776f54ceb94879bc1945a6e5e02736d04ba9d7e4652e02e06280be3a85a833e`；held正式config `d86dc14afddf81a37587ff020cd36cc07e85869bf315502dc1778a97bda8f795`；最终选择complete `2afa80bc07c9cf3f87c5bb8a21bcc8b36baf2a129d25e86b37731de386c7144e`。
