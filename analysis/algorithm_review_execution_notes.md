# Native10执行、G0报警与配对评估：算法审核笔记

日期：2026-09-17。只读核对正式native10协议、实现和旧G0训练定义；本次未调用模型、环境或仿真。本文件供中文算法全流程文档引用，不重复实验结果。

## 0. 冻结模型各司其职

| 模块 | 本次实际模型 | 作用 |
|---|---|---|
| VLA动作策略 | **Pi0.5 / `pi05`**，`sft_pi05_mt50/checkpoints/030000/pretrained_model`；配置PaliGemma为`gemma_2b`、action expert为`gemma_300m` | 根据当前图像、观测状态和语言指令采样动作；10次flow推理生成50×4命令，执行器采用native10 |
| D动作条件世界模型 | `future_aware.models.WorldModel`的`spatial_pair`两成员241/242；每个4,474,116参数，GRU宽256 | 根据因果历史和旧队列未来5动作，预测未来5×4096视觉特征及5×4 proprio；当前G0路径只使用视觉预测，忽略第二个proprio输出 |
| G0中断收益头 | `BenefitModel`两成员341/342；每个1,468,033参数，宽128 | 在生成fresh方案前，用旧5动作及D预测判断预计换计划收益；冻结不训练 |
| 纠偏Q | 当前四成员10步critic，最终A4000 | 对同一a0附近的10步候选进行概率估计和梯度引导；它与G0不是同一个模型 |

VLA checkpoint自身`chunk_size=50`、`n_action_steps=50`、`num_inference_steps=10`；当前执行器显式将实际策略队列容量改为10，再由独立raw队列执行前10条。因此只看checkpoint配置中的50，会误判本次正常执行周期。这里报告实际配置名称，不进一步推断checkpoint未记录的训练覆盖或泛化范围。

模型证据：[VLA冻结checkpoint配置](/mnt/bn/arnold-recommend/yaohaoyang/vla-corrector/outputs/metaworld_very_hard/sft_pi05_mt50/checkpoints/030000/pretrained_model/config.json:1)、[实际VLA/D/G0加载](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg/experiment.py:20)、[D封存模型身份](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_future_aware_20260914/models/spatial_pair_241/complete.json:3)、[G0封存参数及目标](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_future_aware_20260914/critics/gate_341/complete.json:422)。

## 1. 首先区分三个“步数”

1. **VLA一次生成50个四维raw命令**，每个命令为XYZ与夹爪；这里50是生成长度。
2. **正常执行horizon为10**：只把这50个命令的前10个放入本次执行队列；第10个执行完后，根据新观测重新生成，未使用的后40个不续执行。episode开始即如此，所以正常规划时刻是0、10、20……。
3. **每5个环境控制步监测一次**：监测频率5不等于正常规划周期5，也不等于纠偏执行窗口。当前主动干预的新动作窗口为10。

因此`continue_native10`应译为“正常native10执行，不响应额外报警中断”，不宜写成“完全不重新规划”。本轮已经采用从episode初始开始的native10，不是旧native50 source在中途临时截到10。[生成与清空内部策略队列](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/engine.py:42)；[独立raw队列语义](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/semantics.py:106)；[正式capture从reset开始使用10](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:299)。

代码定位：`engine.py:73–82`核50×4生成与10步执行；`semantics.py:17–18,138–177`控制自然耗尽、5步监测及报警资格；正式held配置`config.json:39037–39040`明确总预算300、门限0.05、至少剩10步、生成50。

## 2. G0到底判断什么

### 2.1 当前运行时输入

每次监测先构造当前的因果上下文：

- 最近至多5帧视觉特征，每帧4096维，历史不足时补零并带有效性mask；这些特征来自冻结VLA视觉编码及固定空间投影。
- 同期5帧四维proprio及mask、最近4个实际执行动作、2048维任务语言表示。
- 剩余控制预算比例`(300-t)/300`。
- **当前旧队列接下来5个尚未执行的命令**，不是fresh replan动作，也不是纠偏候选。

两个冻结世界模型D（成员241/242）分别根据上述上下文和旧5步动作，预测随后1至5步的视觉特征。配套两个G0头（341/342）各读取上下文、旧5步动作及对应的预测视觉效应，再将两个实数输出求平均。G0模型里五步预测效应相对当前特征做归一化，并在时间维平均；它不读取真实未来。当前加载的是`BenefitModel`，不是另一个会显式编码完整剩余队列的`ControllerBenefitModel`。旧队列年龄用于外部报警资格判断，不作为该G0头的显式输入。

证据：[模型加载关系](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg/experiment.py:24)、[实际monitor](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/engine.py:89)、[上下文形状及padding](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg/common.py:48)、[空间特征编码](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg_research/experiment.py:35)、[D的五步动作条件预测](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/models.py:35)、[G0/OutcomeModel前向与BenefitModel定义](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/models.py:84)。

### 2.2 G0的训练标签与execute5含义

旧G0标签是一个**固定执行协议的长期成功率差**：

\[
y_G(s)=\frac{1}{3}\sum_{j=1}^{3}\hat p(\text{fresh}_j\text{前5步，然后fixed10})
-\hat p(\text{old队列接下来5步，然后fixed10}).
\]

同一旧源状态生成三份fresh计划，加上old作为四个候选。四候选各先真正执行5步，然后都清空队列，以正常固定10步的策略续跑直到成功、环境终止或总步数300。标签中的成功率来自配对后缀真实仿真终局，不是“接下来的5步是否成功”、视觉预测误差或短期reward。G0只用old候选这一列的输入预测“平均fresh−old”标签，以SmoothL1回归训练；输出不经过sigmoid，因此**不是失败概率，也不是安全概率**。

旧训练时的source规划horizon混有20/50，且标签fresh只承诺5步；当前source始终native10、干预承诺10步。两者具有明确协议差异，不能把G0直接解释为“当前N与R差值的已校准估计”。本轮600源训练更新的是新的10步纠偏critic，G0及D仍冻结。

**G0网络和旧标签规模（少量封存metadata已核）：**历史编码器宽128，以5帧视觉/proprio/过去动作/语言经GRU得到128维；旧5×4动作展平20维后投影到128维；D的五步视觉效应平均后投影到128维；再拼remaining一维，共385维，经`Linear(385,128)→SiLU→Dropout(0.1)→Linear(128,1)`得到回归输出。推理为eval，dropout关闭。训练loss是`SmoothL1(beta=0.1)`，只监督每组old输入那一列的上述fresh均值减old目标；AdamW学习率1e-4、weight_decay1e-3，batch为16个cut组，最多1600更新，按验证MAE选checkpoint。实际341选step1000，342选step1200。

旧训练原计划50个source，其中40个source提供80个可达cut，另外20个cut记录not_reached；**G0训练监督是80个cut级收益标签**。每cut有4候选、每候选2后缀，共640个候选终局结局，不应写成640个独立G0训练状态。旧验证20个source提供39个cut、1个not_reached，共312个候选终局结局。该数量从[旧训练branches目录](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_future_aware_20260914/branches/train)及[旧验证branches目录](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_future_aware_20260914/branches/validation)的`local_effects.json/repeat_count`与not_reached元数据计数；与G0封存crossfit的21/19个source两折一致。这里只核数量和目标定义，没有重新审计这些旧轨迹。训练G0用按source分折的D预测，避免同源不同cut/候选跨折；验证使用冻结D预测。[G0网络形状](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/models.py:84)、[crossfit按source与训练设置](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/critic.py:46)、[G0损失和选模](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/critic.py:127)、[crossfit封存记录](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_future_aware_20260914/critics/gate_341/complete.json:406)。

证据：[四候选old/fresh构造](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/idea3/local_collection.py:191)、[execute5之后fixed10](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/idea3/local_collection.py:225)、[future-aware采集复用此执行器](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/collect.py:59)、[训练标签和loss](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/critic.py:130)、[旧source horizon注册](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/common.py:39)。实际G0封存元数据的目标字符串在[gate341 complete](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_future_aware_20260914/critics/gate_341/complete.json:423)与[gate342 complete](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_future_aware_20260914/critics/gate_342/complete.json:423)均为`mean_fresh_minus_old_execute5_then_fixed10`。

### 2.3 门限0.05的正确解释

触发数值条件是两个G0成员平均值 **严格大于0.05**，相等不报警。按其训练标签单位，可理解为预测旧execute5协议下平均换计划收益超过5个百分点；这不是“错误概率超过5%”，也不是当前纠偏Q提高5个百分点。

当前monitor显式记录`frozen G0 mean benefit; no D-error trigger`。D在这里提供预测特征，不用D预测残差与实测残差的差值触发报警。因此“偏差判定”若用作概括名词，正文需要说明它实际是**预测换计划收益门**，不能画成视觉误差超过阈值的检测器。[monitor定义](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/engine.py:94)、[严格大于门限](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:326)。

## 3. 监测、报警资格与一次中断

循环顺序为：取得当前观测 → 若自然队列耗尽则生成新计划 → 每5步计算G0 → 检查中断资格 → 如不选cut则执行下一条命令。自然规划边界先换计划，所以0、10、20……即使G0超过门限，此时队列age=0，仍不允许额外中断。

合法主动cut要求：尚未成功或终止；处于监测点；队列age>0；当前队列还有至少5步可预测；episode预算还容得下完整10步干预。正常native10情况下合法cut是5、15、25……285。290虽然剩10步，但刚自然重规划、age=0；295仍可记录一次五步监测，但总预算只剩5步，因此不能主动中断。**最后可中断285和最后可监测295是不同概念。**

dev/cal/held只在**首次合法报警**截取源状态；本次测评是每episode最多一次干预。干预或normal前缀执行后均进入普通fixed10后缀；后缀循环不再调用G0，也不再重复纠偏。它不是持续闭环多次报警系统。

证据：[监测及资格](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/semantics.py:164)、[capture顺序和首次报警](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:316)、[后缀无再报警](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:494)。

## 4. 源capture与恢复不是再次挑选成功样本

源episode从预登记初态开始，正常native10执行。初始化后、首次动作前，做物理scene fingerprint查重；只有初始化失败或初态重复可使用预登记有序替补，不得根据后续成功率、G0或Q换源。

cut保存发生在即将执行该时刻动作之前。保存内容包括因果上下文、完整50×4 raw计划、计划起点/age/剩余队列、当前图像hash、物理/RNG/时钟fingerprint、此前真实执行轨迹与随机seed记录。capture至cut停止，不提前执行任何候选。

每次建bank及每个分支都恢复同一个cut：reset原episode，逐步重放已保存的前缀raw命令；逐步核物理状态，核reward与成功/终止，并在cut核图像及fingerprint。恢复过程中不调用模型重新生成前缀；它重放已记录动作，而不是让VLA重新走一遍再假设回到了同一状态。所有分支共享cut前的因果历史。

**在线输入与实验特权状态的界线：**上述物理状态、完整MuJoCo信息、RNG/时钟fingerprint和scene身份用于初态去重、恢复及一致性审计，不输入G0或Q。G0、D和Q使用保存的图像特征、由运行时观测提取的proprio、过去动作、语言、remaining及候选动作；世界模型的“未来”是预测，分支真实未来只在执行后形成监督和评价。代码中Q的`STATE_KEYS`仅有history/history_mask/proprio/proprio_mask/past_actions/language/remaining，建bank明确按这一白名单取context，未把物理state或fingerprint拼入critic。proprio在仿真中由`state_from_observation`得到，不能扩大表述为“模型完全不读取状态”；准确说法是“使用规定的观测状态，不使用完整MuJoCo恢复状态或真实未来”。[critic输入白名单](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/critic.py:19)、[bank只传白名单context](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:408)、[运行时观测与physics/fingerprint分别暴露](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/idea3/metaworld_runtime.py:41)。

证据：[首次动作前初态审查](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:287)、[cut保存字段](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:338)、[恢复和一致性检查](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/adapter.py:124)、[bank先于所有结局封存](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:396)。

## 5. 五臂的具体执行差别

设cut=25，原计划从20开始，前5条已经执行，剩余5条尚未执行：

| 臂 | cut处第一段执行 | 第一次后缀采样时刻 | 后续 |
|---|---|---:|---|
| N：continue_native10 | 原raw队列第25至29步，保持旧命令 | 30 | 普通10步周期 |
| R：alarm_replan10 | cut处新采样a0的前10步，第25至34步 | 35 | 普通10步周期 |
| V：velocity | 同a0噪声得到的velocity引导、最终matched候选前10步 | 35 | 普通10步周期 |
| D：direct | 同a0噪声得到的direct引导、最终matched候选前10步 | 35 | 普通10步周期 |
| P：post | 对a0后处理、最终matched候选前10步 | 35 | 普通10步周期 |

如成功或环境done，立即结束，不强行补满动作窗口。每臂共用从episode开始计算的300步总预算，而非在cut后重新获得300步。

N在cut处不生成新动作；R等新候选bank也不能覆写N保存的旧队列。R执行原生raw a0，不额外只对R裁剪。纠偏在可行mask下给raw a0加matched delta；末尾未执行的40步及mask禁止维度保持。三种纠偏只作用于这一次10步前缀，后缀不再引导。

由此，R−N检验的是“在此中点抛弃剩余5步、承诺新10步，并把后续规划相位平移5步”的整体改变；它不能被描述为只有动作替换、时序完全不变。P−R等比较才固定了新计划噪声、10步承诺和后缀相位，以隔离纠偏的增量。

证据：[normal保留队列而主动臂执行10步](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/semantics.py:226)、[分支执行和后缀](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:465)、[raw a0保留](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/engine.py:128)。V/D/P注入的具体微分公式及共同幅度约束由纠偏模块章节另述。

## 6. “配对随机量”精确定义

- 源采样seed由episode身份与自然规划**序号**确定，正常source域独立于candidate和suffix域。
- 一个cut只生成一个指定a0 bank；候选seed由episode/cut/candidate_index确定，不含method或repeat。R、V、D共享相同初始flow噪声，并保存noise hash核对；P直接从该a0计算，无另一次随机起点。
- 同一源的4个后缀repeat复用这个已经封存的bank，不是每个repeat再抽一份a0。重复测的是固定候选动作下不同随机后缀的结局。
- suffix seed由episode/cut/repeat/**suffix决策序号**确定，不含method。每臂第j次后缀采样使用相同seed；不同repeat使用不同流。
- 相同seed不意味着动作相同：各臂物理状态已因前缀不同而分叉。N与其他臂首后缀时刻还相差5步；上例N在30和R在35共享suffix序号0的随机流，并非在相同绝对时刻获得相同状态/动作。
- N的cut后suffix使用分支后缀域，而非接着source自然seed域执行；它评估相同正常native10策略的随机延续，不要求等于某一条原source继续跑的逐位轨迹。

证据：[三种seed域与配对定义](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/protocol.py:116)、[候选同noise核验](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/engine.py:103)、[后缀seed按决策序号及记录解释](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:494)。

## 7. 训练切点与实际评估切点不同

当前主episode注册为 **600训练+100开发+100校准+100held=900**；另有20个P0诊断episode，不属于上述900。不是1000个主episode。五任务均衡：训练每任务120，其他三split每任务20。600训练分两轮300，每轮每任务60。

每轮300训练的requested切点分配为：150个first_alarm，另150个scheduled（15、45、95各50）。即每任务30 first_alarm，scheduled三个时刻各10；“50/50”指报警请求与定时请求各一半，不是固定执行horizon50。

| 注册切点 | 当前训练选择规则 |
|---|---|
| first_alarm | 选首次合法报警；若整条正常source无报警，则按15→5选已到达、尚未终止的合法anchor |
| scheduled15 | 优先15；未到达则按5回退 |
| scheduled45 | 按45→15→5选首个可用anchor |
| scheduled95 | 按95→45→15→5选首个可用anchor |

scheduled source即使在目标前触发G0，也不因此改成报警cut；它按注册定时规则继续。每source最多选一个主cut，其他早期anchor只为既定可达性回退保存，不作为额外独立episode。回退只依赖已到达的合法anchor及固定优先级，不按候选成功率或Q挑最好cut；但可达性与轨迹终止有关，所以其分布仍与部署首次报警不同。

dev/cal/held没有上述训练fallback，也没有scheduled来源：只取首次合法G0报警。如果一路未报警，就正常执行到终局，得到五臂共同结局，不造一个纠偏cut。这也说明训练scheduled/fallback上的平均收益不能直接报告为部署成功率。

注意原manifest保存了旧的请求字段字符串，实际fallback已由批准的`analysis_lead_v1`实现与独立selection audit明确覆盖；解释最终行为应看`select_cut`，不能只读早期请求里的`none_pending_analysis_review`。

证据：[原训练50/50注册](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/prepare.py:27)、[最终cal/held各扩至100并保留旧身份](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/register_main_v2.py:12)、[实际fallback算法](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:56)、[两轮切点比例强校验](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/round2_prepare_v1.py:31)、[完整注册产物](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/main_registration_v2/primary_manifest.json)。

## 8. G0与当前成功概率Q必须分开命名

| 项目 | G0报警头 | 当前10步纠偏Q |
|---|---|---|
| 作用 | 是否值得在旧队列中途额外重规划 | 给固定a0附近候选动作提供纠偏目标 |
| 输出 | 旧协议fresh−old收益回归实数 | sigmoid后的终局成功概率估计 |
| 动作窗口 | 旧队列接下来5步 | 指定候选接下来10步，相对同一a0 |
| 未来信息 | D预测的五步视觉效应 | 当前实现输入保存的观测上下文、a0与候选delta；不读取真实未来，也不把D未来作为此Q的显式输入 |
| 本轮是否训练 | 不更新 | 600新源候选结局监督更新，最终冻结A4000四成员 |

纠偏实际最大化四成员平均`Q_i(s,a;a0)−Q_i(s,a0;a0)`。这里Q是模型概率预测，不是已验证的真实成功率；G0的0.05门限也不应用到Q上。最终Post由开发选择和校准全局规则固定，不在每个held源上以Q阈值决定是否接受；G0负责首次合法报警，之后按冻结主策略执行一次Post。

证据：[当前critic的10步结构与固定a0](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/critic.py:31)、[四成员概率差目标](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:51)、[实际sigmoid及平均](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:109)。normal控制不是critic候选；因此本轮候选critic训练不会自动学会“保留旧队列vs主动中断”的选择。

## 9. 配对成功率与源级统计如何形成

每条分支成功指标为在总300步内是否出现环境success；成功、done或预算耗尽后终止。对于方法m及源s，先把该源K个配对后缀的0/1成功值平均，得到源成功率。方法总体成功率是全N个源等权平均，不能把K次重复当K个独立初态。

比较m与b时，每源差值`d_s=mean_r(Y_smr−Y_sbr)`，总增益为`mean_s d_s`。配对救回是同源同repeat下m=1,b=0；损害反之。正/负/零源按源平均差值符号统计，和救/害的计数单位不同。

无报警源没有实际候选分支，它的真实正常episode结局按各臂各repeat逻辑广播，因此所有差值0，但必须保留在全N分母。技术失败或缺失不能作为这种共同结局，也不能填0。校准K=2；训练、开发和held的分支K=4。训练采13候选加normal控制；最终方法评估五臂N/R/V/D/P，不应将训练候选数与五臂数混写。

最终held使用固定100源、每任务20；任务内整源有放回bootstrap10000次，seed2026091622，95%线性percentile区间。每次抽源保留该源所有方法和后缀配对关系。P−R为唯一主比较，R−N及三T/其余A共六项次要；点估计是否达到+5pp和区间是否支持正收益分开报告。开发、校准、held不合并，也不在held后改主方法。

证据：[success与终止定义](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/idea3/local_collection.py:53)、[各split重复次数和训练候选集合](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:34)、[无cut真实共同结局](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:578)、[技术完整性/共同结局校验](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/heldout_statistics_v1.py:85)、[配对、源均值和bootstrap](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/heldout_statistics_v1.py:163)。

## 10. 必须保留的解释边界

- **已核事实**：5/10/50三个窗口、门限和中断资格、G0旧execute5目标、一次干预、正常队列保留、配对随机域、训练fallback、完整源分母均有上述实现依据。
- **尚不能由此证明**：G0在当前native10/10步承诺下是否校准良好；G0是否找到了最优中断时刻；候选Q概率是否逐源可靠。目标协议差异是事实，其导致多少性能损失需要另外的实验，本文不从代码推导因果大小。
- 每个“步”是环境控制step。本文没有重新核验底层frame_skip、仿真时间步或真实机器人采样频率，不能直接把5/10步写成固定多少毫秒。
- 这套封存评估支持“固定五任务、一次首次合法报警干预”的结论；未检验持续多次纠偏、全新任务分布或真实机器人部署。
