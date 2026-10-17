# H10 基线、算法一致性与 critic 数据审查

日期：2026-09-16。范围：只读现有代码、配置、封存轨迹与训练数组；本轮未新增仿真、训练或修改封存。当前小批量账本仍为 **653/700**。以下改进均为建议，未执行。

**接受用户最新定义：正常执行 horizon 应为 10。已完成的 `continue_old/native50` 仅作为历史对照存档；后续公平正常基线必须从 episode 初始按 native10 自然队列运行，忽略 G0。** 当前 `replan=55.00%` 也不是这一正常 native10 基线，它包含 native50 的报警前轨迹及报警处强制重规划。

## 1. 旧30源与新15源：同算法，但不是同源同随机流复跑

结论：四个共同臂的公式、权重、数值参数、十步执行和 fixed10 后缀保持一致；未发现算法迁移错误。真实改变包括源样本、四类随机流、执行对照和并发数。现有检查支持核心数值一致，**没有完成跨两套实现、同状态同随机流的完整 VLA→引导→仿真逐位对照**。

| 项目 | 旧30源 | 新15源 | 判断 |
|---|---|---|---|
| 正式源 | 2026104000–4029，五任务各6源 | 2026106000–6014，各3源 | 新样本，状态和难度可变 |
| 预检 | 2026103900–3904，每臂2次 | 2026105900–5904，每臂1次 | 不同预检样本与规模 |
| 正式后缀 | 每源每臂8次 | 相同 | 无变化 |
| 实际执行臂 | replan、三种matched、reverse、random、两种native | replan、三种matched、continue_old | 对照设计改变 |
| 生成候选 | 8种 | 仍生成原8种，另保存old队列 | 五方向共同半径依赖保留 |
| 并发 | 32 worker，4/GPU | 8 worker，1/GPU | 调度改变 |
| CPU线程 | worker 4、critic内部2 | 相同 | 未改成单线程 |
| 源捕获策略 | native50，首次G0报警 | 同样native50 | 两轮共同的目标基线偏差，不是两轮之间新变化 |
| α/引导时刻 | 10；τ=.3/.2/.1 | 相同 | 无强度参数变化 |
| 实际扰动限制 | XYZ RMS≤.05/L∞≤.15；grip RMS≤.10/L∞≤.40；边界余量.05 | 相同 | 无匹配参数变化 |
| 共同臂执行 | 十步前缀，清队列，fixed10，原总预算300 | 相同 | 共同臂延续语义一致 |

随机命名空间确实发生变化：candidate `ogg_flow_replan→corrector_small_replan`；suffix `ogg_flow_suffix→corrector_small_suffix`；random `ogg_flow_random→corrector_small_random`；branch order `ogg_flow_branch_order→corrector_small_branch_order`。源策略命名空间仍为 `ogg_source`。因此即使复用某个环境种子，候选 a0、后缀和随机方向也不能默认相同。random 虽未在新批次执行，仍参与共同可行半径的最小值计算，会影响最终 matched 幅度。

不变的具体数学路径：状态固定、槽0为指定且detach的a0、只对槽1候选求导；目标为四成员 sigmoid 成功概率差的均值；velocity 为 `v−ατg`，direct 为 `v−αg`；post 使用相同 float32 NumPy `S²∇aR`；真实反归一化/clamp导数和最终五方向共同mask/半径相同。VLA、D、G0仍由同一运行时加载，四个critic checkpoint及ranking完全相同。

代码AST核对显示 flow_update、FlowHook、critic_threads、construct、TenStepCritic等核心定义一致。提取测试覆盖真实权重加合成观测的critic特征/概率/梯度、合成采样状态上的单步flow更新，以及匹配算法。**“旧30源候选逐位重建”只读取旧保存的a0、native velocity/direct和post方向，再重做construct；没有重新生成旧源VLA或重算整条引导轨迹。** 新8-worker复现核验的是新实现自身的预检replan轨迹。两类证据不能扩大成完整跨实现逐位保证。

证据：[旧配置](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/results/reference_flow_20260916/config.json)、[新配置](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/metaworld_small_20260916/config.json)、[提取测试](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/tests/test_extraction.py:54)、[30源银行重建范围](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/metaworld_small/common.py:89)、[新采集器](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/metaworld_small/collection.py:38)。27项外部冻结依赖核验见新批次 `audits/development.json`。

### 结果变化与实际扰动

| 方法 | 旧30源成功率；相对replan | 新15源成功率；相对replan |
|---|---:|---:|
| replan | 69.58%；0 | 55.00%；0 |
| velocity matched | 75.42%；+5.83 pp | 53.33%；−1.67 pp |
| direct matched | 75.42%；+5.83 pp | 55.83%；+0.83 pp |
| post matched | 78.75%；+9.17 pp | 55.00%；0 pp |

旧30源/新15源的实际XYZ平均RMS分别为 .044342/.042972，夹爪为 .081043/.084676；XYZ共同半径收缩23/30与10/15，夹爪零组3/30与2/15。新XYZ平均约低3.1%，夹爪反而较高，不能只凭本批失效归因为“强度被改弱”。

任务分布虽同名均衡，具体难度不同：replan在pick-place-wall由100%变33.33%，stick-pull由50%变8.33%，disassemble反而由37.5%变100%。旧post主要净收益来自shelf-place和stick-pull；新批次的纠偏配对变化仅发生在两个stick-pull源。新旧平均Q预测增益仍都约+10 pp。结论是**旧开发集收益幅度未在新源、新随机流中复现**；不能把不同源上的差值解释为某一项实现变化的因果效应，也不能宣布已确定梯度方向错误。

结果证据：[旧evaluation](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/results/reference_flow_20260916/evaluation.json)、[新evaluation](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/metaworld_small_20260916/evaluation.json)。

## 2. 正常native10的公平基线必须从初始建立

当前捕获明确 `runtime.reset(case,50)`，并使用手工ActionQueue每50步换计划。每5步检查G0；先在队列耗尽时更新计划，再要求 `queue.age>0` 才能报警。故改成native10会改变观测历史、过去动作、即将执行动作、报警值、报警时刻及报警资格。D预测残差是记录项；实际切点由G0收益预测阈值.05触发。

“VLA生成50步”不等于“执行50步”：PI0.5的正常队列可以只收生成计划的前 `n_action_steps=10`，自然耗尽后再生成。因此后续应保留50步生成长度，但按用户指定的10步正常执行周期采集。

| 分支 | 从episode初始到cut | cut处与后续行为 |
|---|---|---|
| 正常native10 | native10自然队列；G0仅旁路记录 | 忽略G0，完成原队列合法余量，自然耗尽后再native10 |
| 仅中断重规划 | 与正常分支同一native10前缀 | cut清旧队列，生成指定a0，执行10步，之后native10 |
| 中断＋纠偏 | 同一native10前缀、同一cut | 同a0和采样噪声，仅改候选；十步窗口与后缀和replan一致 |

例如cut=5：正常分支只应继续初始计划 `[5:10]` 的五步，在t=10自然采样；不能执行原50步计划的 `[5:15]`，也不能到t=15再强制清正常队列。重规划/纠偏分支在t=5介入、t=15再次采样，其相位变化属于中断效果。

分别报告：中断收益=`replan−正常native10`；纠偏额外收益=`纠偏−replan`；总体收益=`纠偏−正常native10`。同源同分母下第三项等于前两项之和。critic槽0仍为指定的新a0，不应把不足十步的旧队列填充后冒充a0。

现有native50数据可以回答“这些指定报警状态上纠偏相对强制重规划”的局部问题，**不能代替正常native10策略的整体对照**。仅把old后缀50改10仍不够：报警前轨迹和切点没有改变。新15源切点为5步11源、10步3源、40步1源；旧30源有18个cut=5。若初始动作/噪声完全一致，cut=5的物理状态可能共享，不能说所有旧源都已改变；但应逐一验证。对于t=10边界，native10可能已新采样而队列年龄为0，报警资格就可能不同；t=40更不能默认同分布。

现有 `continue_old=25.83%` 只是native50对照；`replan−continue_old=+29.17 pp` 同时包含周期和命令处理等差异，不能当作正常native10上的中断收益。未来正常分支应保持其原始raw命令语义；监测和候选生成不能偷偷清空它的队列。`restore()`目前只恢复物理轨迹，`propose()`会清policy队列，即使环境fingerprint不变也不代表原队列被保留。正常队列需要独立恢复/准确续接，且不能把已反归一化环境命令直接塞进内部归一化动作队列。

证据：[capture及报警](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg/experiment.py:86)、[restore](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg/experiment.py:142)、[runtime队列周期](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/idea3/metaworld_runtime.py:24)、[PI0.5队列截取](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/projects/vla-corrector/src/lerobot/policies/pi05/modeling_pi05.py:1223)。

## 3. 当前四成员critic究竟训练了什么

### 数据采集与精确规模

四成员为1041/1042/1043/1044，每个7058参数；Corrector复制权重与原v3 refit权重逐字节一致。训练源都是**native50源轨迹上的首次G0报警状态**，不是native10在策略运行中到达的状态，也不是跟随flow纠偏得到的状态。

| 数据部分 | 源种子 | 计划源/有报警源 | 当前权重使用的h10结局 |
|---|---|---:|---:|
| pilot | 2026103000–3049 | 50/50 | 50×9×8=3600 |
| train_extra | 2026103050–3099 | 50/49 | 49×9×8=3528 |
| 当前refit合计 | 上述两组 | 100/99 | **7128个二值结局、891个候选均值、99个独立源** |
| calibration | 2026103100–3149 | 50/49 | 不进入权重/PCA；1024条实际去重分支用于策略校准 |
| validation | 2026103150–3199 | 50/50 | 不进入权重/PCA；1088条实际去重分支用于旧离散策略评价 |

train_extra缺失的报警源是 `pick-place-wall-v3__2026103086`，其无报警且source成功；它保留在计划分母，没有伪造候选标签。pilot还采过h5的3600条结局，但**当前四成员只读取h10数组**。缺失校准源为 `shelf-place-v3__2026103107`，同样在报警前成功。calibration/validation执行replan、固定raw winner、backoff三个请求臂，相同候选复用封存轨迹，因此其数组槽位数不等于实际物理分支数。

训练NPZ实测形状：pilot actions `(50,9,10,4)`、outcomes `(50,9,8)`；extra分别为`(49,9,10,4)`、`(49,9,8)`。99源中91源至少一个候选均值与a0不同，40源有更好候选、69源有更差候选，两者可以重叠。这不等于91源都有可救回动作。

每个报警状态只采样一个指定a0，再构造以下九候选；候选前缀十步，之后清队列，冻结fixed10到成功/终止或原总控制预算300。每候选八个后缀重复；同源/重复号/后缀决策序号使用配对随机流，候选前缀是同一个确定计划，不是每次repeat重新采a0。

| 候选 | 十步内的构造 |
|---|---|
| replan | 指定a0 |
| xyz_plus / xyz_minus | 同一个随机三维方向，按最大分量归一到.15；整个十步加/减常量向量，再clip |
| gripper_plus / gripper_minus | 同一个随机符号的线性ramp，幅度从.08到.40，加/减后clip |
| settle_close | 前3步XYZ=0、夹爪+1，后7步从a0开头续接 |
| delayed_close | 前5步夹爪−1、后5步+1，XYZ保持a0 |
| lift_return_regrasp | 3步向上.4并打开、3步向下−.4并打开、4步XYZ=0并闭合 |
| backoff_reapproach | 依观测位移（退化时依a0平均平移）先反向.3三步、再正向.3三步、最后4步续接a0；方向退化时保留a0 |

证据：[训练输入装载](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg_research_v3/learning.py:34)、[训练候选构造](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg_research_v3/candidates.py:7)、[v3采集配置](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_ogg_research_v3_20260916/config.json)、[pilot h10清单](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_ogg_research_v3_20260916/data/pilot/h10/rows.json)、[extra h10清单](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_ogg_research_v3_20260916/data/train_extra/h10/rows.json)。

### 标签、损失、split与训练

标签 `y[s,j,r]` 为真实配对后缀的最终成功0/1，不是世界模型预测误差、未来视觉误差，也不是第十步末是否成功。令 `q[s,j]=mean_r y[s,j,r]`，`p[s,j]=sigmoid(logit[s,j])`，损失为：

**BCEWithLogits(logit,q) + 1.0 × MSE(p[j]−p[0], mean_r(y[j,r]−y[0,r]))**。

BCE覆盖九候选，relative MSE只覆盖八个非a0候选；没有TD、自举未来价值或动作梯度真值监督。输入是当前可观测视觉/本体历史、过去动作、语言、剩余预算和完整10×4候选/a0；四成员本体不输入D预测的未来或真实未来状态。D/G0的报警作用与该critic最终成功监督需分开。

- 按完整源、分任务拆分：inner train计划80且实际80（pilot42+extra38）；inner validation计划20、实际19（pilot8+extra11，3086原在held中）。没有把同源候选/repeat随机拆到两侧。
- 仅用inner训练80源拟合PCA；视觉16维、语言8维，加其余37维组成61维状态输入。旧视觉归一化继承冻结spatial_pair_241统计。选步后在全部99源重新拟合PCA并refit，校准/验证特征不进入拟合。
- 四成员共享同一源集合，参数初始化和minibatch随机种子不同，没有对source做bagging。每批16个源；有任一经验候选均值不同于a0的源采样权重4，其余1；refit为91个信息源，inner train为73个。
- AdamW，lr=3e−4，weight_decay=.01，梯度clip=1。inner最多4000步，检查100/200/400/800/1600/3200/4000；依据四成员平均预测在19个实际held源上的相对概率增益MSE选步，最早并列优先。选中**800步**，四成员随后对99源refit800步。
- `refit/details.json` 的 `held_sources` 列出全部99训练源，属于训练内预测记录，不能误认成另一套保留验证集。
- 当前a0锚定结构强制同动作相对增益为0。历史PCA单源数值路径与CPU两线程修正有单独amendment，均发生在这两轮flow实验之前，不是30→15迁移时新增的算法改变。
- 后续calibration只拟合离散赢家接受策略：scale=.155180427、kappa=1、margin=0。flow两轮均直接使用四成员原始平均概率差，没有套用这套离散winner接受规则。旧30源和新15源结局均未进入当前四成员权重或PCA。

先前离散候选策略的50源保留验证中，replan为60%，校准选择策略为54%，救回16、损害40（−6 pp，95%CI [−13.75,+1.25]）。这也未更新当前权重，说明不能把这组critic视为已证明可泛化的动作评分器；它与本轮15源结果是不同实验，不能混合计数。证据：[原离散策略最终评价](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_ogg_research_v3_20260916/learning/final_evaluation.json)。

证据：[训练配置/split](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/assets/critic/config.json)、[refit详情](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_ogg_research_v3_20260916/learning/models/refit/member_1041/details.json)、[损失](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg_research_v2/training.py:35)、[选步](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/assets/critic/stopping.json)、[PCA](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg_research_v3/capacity.py:95)、[训练/推理数值修正](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_ogg_research_v3_20260916/learning/inference_implementation_amendment.json)、[flow原始目标](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:109)。

### 与flow局部扰动的分布差异

训练局部候选只覆盖“恒定XYZ偏移”或“单独夹爪ramp”，另四类是较大的阶段化动作；flow是由critic自适应生成、随时间变化且可能联合改变XYZ和夹爪的方向。离散九点上的成功率拟合并不唯一约束点间和未覆盖方向上的动作导数。flow还会在 `T(xτ−τv)` 的中间干净动作估计上查询梯度：最终命令的匹配半径并不限制所有中间查询也在该半径内。post是在a0处取梯度，但a0点值被监督也不等于其40维导数被监督。

直接读取99源训练动作得到：XYZ±平均XYZ RMS约.09528/.09541，夹爪±平均grip RMS约.22752/.23476；新flow matched分别约.04297/.08468，且采用共享边界mask和各方向共同可行半径。恢复候选的RMS更大，且会重排/覆盖动作。训练也没有同状态、同方向的多半径局部曲线或flow方向正反有限差分监督。**动作范数落在训练最大幅度以内，不等于联合时序方向处于训练支持范围。** 另外，从native50源转到正常native10还会带来状态、动作历史和报警选择分布的变化。

## 4. 最小微调与重采重训优先级（仅建议）

| 优先级 | 建议 | 解决的问题与限制 |
|---|---|---|
| P0 | 先明确并实现从初始native10的源、自然队列基线及三类比较；固定VLA/D/G0/critic做基本队列审查 | 修正公平比较口径；不能靠改旧产物标签解决 |
| P1 | 新native10源上小规模采集真实配对数据，保留未报警/提前成功源；固定源级train/calibration/held划分 | 先量化中断收益与纠偏额外收益，避免直接扩大100源或盲目重训 |
| P2a | 若中断本身无收益或损害大，优先重定义并适配G0的收益标签 | 当前G0目标是fresh−old执行5步后fixed10，并非正常native10继续与立即重规划10步的差值 |
| P2b | 若中断有效而纠偏无效，优先补当前部署分布的局部候选标签，再微调小critic | 对齐动作方向与native10状态；先不动大VLA/D |
| P3 | 小幅微调不足时，用新native10数据及合适的旧数据重新训练同等容量critic；只在可观测特征偏移证据充分时重拟合PCA/状态编码 | 独立源划分、重新校准和保留验证仍必需 |
| P4 | 最后考虑D/G0更广泛重训或VLA微调 | 执行周期变化不自动证明D失效；当前没有证据要求先改大VLA |

最小critic微调可以先冻结视觉/语言投影、state/base-action编码和baseline head，只更新残差与advantage分支，保留a0恒等锚定和绝对成功率＋配对增益损失；小学习率和停止规则需在下一协议预先固定。新增数据应覆盖a0、实际velocity/direct/post、同幅反向与平滑随机方向，并在训练子集采少量同方向多半径点，监督局部收益曲线，特别保留“a0成功但纠偏损害”的配对。是否采用配对排序/有限差分辅助损失属于后续方法选择，本轮不变更。

如果仅做最低成本的离线机制诊断，可利用已有旧30源8臂×8与新15源四个fixed10臂×8，合计**45个源、300个候选组、2400个二值标签**；排除新批次native50 `continue_old` 的不匹配标签。它有真实flow/反向/随机监督，但仍来自native50状态，且已被查看用于开发，只能作训练/开发诊断，不能解决native10分布问题或再称独立验证。原99源primitive数据可作为防遗忘辅助，权重应在新开发集确定，不能淹没新的局部标签。

正的标量校准可以缩放预测，不能单独证明或修正梯度方向；对单纯post方向归一化而言，非零正比例缩放还会被RMS归一化抵消。因此优先级应是**正确native10数据与真实局部标签，其次小critic适配；不是先加alpha、扩大网络或直接宣布重训VLA**。

G0目标证据：[future_aware/critic.py](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/critic.py:135)。当前预算剩余47次保留不动；任何后续采集/训练均需另立协议，由分析端判断重大方法变更。本轮未重跑冻结实验，未启动100源。
