# 算法审核：critic 数据、结构、训练与选择事实

本笔记仅做只读事实核对，不运行模型、训练、PCA、测试或仿真。以下以最终实际封存的 `final_fit_protocols/final_fit_v1`、最终模型与实际训练实现为准。已核 `critic.py`、`training.py`、`dataset.py`、`candidates13.py`、`final_training_pipeline_v1.py` 当前 SHA 均与该 final freeze 一致。

## 1. 数据来源与训练边界

| 数据 | 独立 episode | 每任务 | 用途与实际有效行 |
|---|---:|---:|---|
| 第一轮 train | 300 | 60 | 原冻结 critic 1041–1044 生成局部候选；300 个有效 cut |
| 第二轮 train | 300 | 60 | 第一轮开发集选出的 B200 生成局部候选；300 个有效 cut |
| development | 100 | 20 | 原第一轮固定 13 候选 bank；95 个有效 cut，5 个共同结局；供两轮模型选择 |
| calibration | 100 | 20 | 最终固定 critic 的策略接受规则，不进入网络/PCA训练；每源2后缀 |
| heldout | 100 | 20 | 模型、方法与接受规则固定后一次评价；每源4后缀 |

训练与开发局部 bank 每源均为 13×4 个候选标签，另有 normal×4。全部600训练源实际有效，因此共有 **31,200 个候选二值标签，另2,400个 normal控制标签**；这些不是31,200个独立状态。五任务为 disassemble-v3、pick-place-wall-v3、shelf-place-v3、stick-pull-v3、stick-push-v3。

**两轮改变的是候选生成 critic，不是源轨迹行为策略。** source 始终由原 VLA 原生 raw 队列从初始状态按 native10 执行，`propose(seed)` 不带纠偏 objective；原冻结 D/G0 负责监测与选切点。B200 只在恢复 cut 后的 `make_bank` 生成/评分局部候选，真实标签来自各候选的环境续跑，不是把 B200 的 Q 当蒸馏标签。第一轮开发 bank 也保持原 teacher，不随最终 critic 重写。

每轮每任务训练 cut 预登记30个首次合法报警、30个 scheduled（15/45/95各10）；两轮合计50%/50%。源只取一个主要 cut。训练允许已预登记的早期 anchor fallback：15→5，45→15→5，95→45→15→5；报警组全程无合法报警时15→5。开发/校准/held不使用该训练 fallback。技术缺失、无报警和初态替补按原协议分别记录，不能按纠偏结果换源。

两轮以**原始 canonical 特征**合并，保留两份真实采集协议及两位生成 critic 身份；不能拼接两套 teacher 已投影的 PCA 坐标，也不伪造一个共同采集协议。每源等权，不因来自第二轮、Q较大或标签有信息而提高权重。旧99/45来源数据不追加到这600训练行；A继承旧训练信息的途径是旧权重与投影。

证据：[EVAL20最终划分](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/coordination/NATIVE10_EVAL20_AMENDMENT.md:7)、[当前schema](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/TRAINING_SCHEMA_MAIN_V2.md:7)、[源轨迹无纠偏执行](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:310)、[仅bank使用critic](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/engine.py:103)、[canonical合并契约](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/final_input_bundle_v1.py:118)、[最终实际coverage](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/models/final/final_fit_v1/result.json:41224)。

## 2. 13候选、标签与去重

| 槽 | 候选 | 含义 |
|---:|---|---|
| 0 | a0 | 同一cut重新采样的新计划；所有相对收益的固定锚点 |
| 1/2 | xyz_positive/negative | 最终matched-post实际delta的XYZ分量正/反向 |
| 3/4 | gripper_positive/negative | 同一post实际delta的夹爪分量正/反向 |
| 5/6 | random_half_positive/negative | 独立平滑联合随机方向的半幅正/反向 |
| 7/8 | random_full_positive/negative | 同一随机方向的全幅正/反向 |
| 9 | velocity | 原部署构造后的matched velocity |
| 10 | direct | 原部署构造后的matched direct |
| 11 | post | 原部署构造后的matched post |
| 12 | reverse_post | 最终post实际delta取反 |

XYZ/grip通道倍率按source预登记为0.5或1；对应post通道实际delta为零时，使用独立平滑随机fallback并保留标记。随机方向每动作维3个高斯时间节点、线性插值。formal V/D/P先按原五方向匹配得到，再用于训练bank；通道对和随机对单独保证对称可行性，**不把13候选一起做公共最小半径匹配**。训练槽12的 `reverse_post=-post_delta` 与部署bank的 `reverse_matched=-direct_delta` 不是同一方向。

候选实际执行 raw 新计划前10步，然后以冻结VLA/native10续跑；总控制步预算仍300，可因成功或环境终止提前结束。令

\[
y_{ijr}=\mathbf 1\{\text{第 }i\text{ 源，候选 }j\text{，第 }r\text{ 条配对续跑在终局前出现success}\},\quad r=1,\ldots,4.
\]

因此标签是完整续跑的二值成功，不是“第10步是否成功”、即时奖励、D预测误差或teacher Q。四个后缀按 episode/cut/repeat/后缀决策index共用种子，不包含method编号；各臂状态和绝对采样时刻可以不同。

本次**实际主采集没有物理alias复用**：即便前10步raw命令完全相同，13×4和normal×4仍各自执行。alias用于一致性审计和训练去重。判等必须是同源/cut、完全相同raw命令、同冻结模型/协议及配对后缀；仅C(raw)相同不算物理等价。组内结局与suffix实现必须一致，不能挑一次更好的标签。

- 每个distinct候选组的BCE权重为1；保留alias槽时每槽权重1/组大小。
- 与a0相同的组只计一份BCE，不进入gain项。
- 正反pair为(1,2)、(3,4)、(5,6)、(7,8)、(11,12)；同组pair不计，重复无序组对只计一次。
- 非零对称性错误直接审计失败；不能用mask掩盖。
- 缺少四个完整标签不能填0；没有有效gain/pair时该项为0，但保留该源的外层权重及a0 BCE。
- normal继续旧队列的4标签独立保存，**不进critic损失、不作slot0、不用于本轮重训G0**。

证据：[候选顺序](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/candidates13.py:16)、[实际构造与alias](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/candidates13.py:179)、[本次不复用物理分支](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:11)、[真实标签/后缀](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/main_collection.py:490)、[数据完整与alias检查](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/dataset.py:373)、[损失去重](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/training.py:75)。

## 3. Critic实际输入与特征

| 单源字段 | 形状 | 用法 |
|---|---|---|
| history / history_mask | 5×4096 / 5 | 最多最近5个已观测视觉特征，右对齐；无历史补零并mask |
| proprio / proprio_mask | 5×4 / 5 | 同时刻本体历史；mask后展平20维 |
| past_actions | 4×4 | 最近4条已执行动作，补零后展平16维 |
| language | 2048 | 指令编码；无参数LayerNorm |
| remaining | 标量 | (300−cut_step)/300 |
| critic候选动作 | 13×10×4 | C(raw)=clip(raw,−1,1)，slot0指定a0 |

历史特征先用checkpoint保存的4096维mean/std标准化（std下界1e−6）并clip到[−8,8]。拼接“最新帧”与“mask加权历史均值”，得到8192维视觉向量，再做16维PCA；语言LayerNorm后做8维PCA。PCA各维除以保存的投影标准差并clip到[−8,8]。最后拼20维本体、16维历史动作、1维remaining，共 **16+8+37=61维**。history/proprio mask不另作为独立维度拼接。物理scene去重信息、环境真状态、目标success及未来观测不进入该critic。

视觉与语言大特征提取器冻结；canonical视觉先逐样本空间投影，再half→float量化存储。PCA前的观测数组在两轮间保持相同定义；在线及离线canonical推理使用同一逐源预处理。

证据：[数据形状](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/dataset.py:26)、[特征拼接/归一化](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/critic.py:19)、[原特征padding](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg/common.py:48)、[冻结空间特征](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/ogg_research/experiment.py:35)、[逐源canonical预处理](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/training.py:266)。

## 4. 网络与锚定公式

每成员均为5个小MLP；隐藏层激活SiLU，输出logit，不含BatchNorm/Dropout：

| 模块 | 维度 | 参数数（由Linear形状计算） |
|---|---|---:|
| state S | 61→32→16 | 2,512 |
| action E | 40→16→16 | 928 |
| residual R | 40→16→16 | 928 |
| baseline head H | 32→32→1 | 1,089 |
| advantage A | 48→32→1 | 1,601 |
| 合计 | 每成员 | **7,058** |

令fᵢ是61维特征；aᵢ₀与aᵢⱼ均为10×4 clipped critic命令；d=(.15,.15,.15,.40)按时间广播。d是残差输入尺度，不是最终动作RMS约束。定义

\[
u_i=[S(f_i),E(\operatorname{vec}a_{i0})],\qquad
v_{ij}=R\!\left(\operatorname{vec}\frac{a_{ij}-a_{i0}}{d}\right),
\]
\[
z_{ij}=H(u_i)+A([u_i,v_{ij}])-A([u_i,R(0)]),\qquad p_{ij}=\sigma(z_{ij}).
\]

所以这是**给定状态及固定a0锚点的十步动作成功概率模型**；不是不依赖a0的通用最优Q函数。零delta时两个advantage项在数学上相消，zᵢ₀=H(uᵢ)。实现按H+actual−zero进行float32运算，勿把该代数性质扩写成旧/新checkpoint的a0绝对概率必然逐位相等；严格检查的锚定是同一模型同一a0的相对gain为0。它由有限时域rollout成功监督，不做Bellman backup、TD损失或在线强化学习。

四成员在线纠偏目标是

\[
\mathcal J_i(a)=\frac14\sum_{m=1}^4\left[p_m(f_i,a;a_{i0})-p_m(f_i,a_{i0};a_{i0})\right].
\]

a0和观测特征均detach固定，只对候选动作求导；**不是移动a0一起优化**。成员离散度不等于统计置信区间。

证据：[网络/forward全定义](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/critic.py:31)、[残差尺度与7058断言](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/training.py:216)、[固定a0在线目标](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/guidance.py:109)。

## 5. 训练目标（不是排名hinge损失）

令qᵢⱼ=¼∑ᵣyᵢⱼᵣ；Gᵢ为distinct候选组，Gᵢ⁺为去掉a0组的候选组，Pᵢ为去重后的有效正反组对。单源损失为

\[
L_i=\frac1{|G_i|}\sum_{j\in G_i}\operatorname{BCEWithLogits}(z_{ij},q_{ij})
+\frac1{|G_i^+|}\sum_{j\in G_i^+}\left[(p_{ij}-p_{i0})-(q_{ij}-q_{i0})\right]^2
+\frac{0.5}{|P_i|}\sum_{(j,k)\in P_i}\left[(p_{ij}-p_{ik})-(q_{ij}-q_{ik})\right]^2.
\]

空gain/pair集合对应项定义为0；总损失是minibatch完整source的Lᵢ均值。alias槽用前述逆重数权重实现同一组级平均。权重固定 **1 / 1 / 0.5**。pair项只是配对二值成功差的回归，不是真梯度标签、不除以半径、不另加排序hinge或跨半径第四损失；四重复使经验成功率粒度为0.25。

证据：[完整loss实现](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/training.py:126)。

## 6. A/B路径、PCA、bootstrap与优化

| 项目 | A：旧critic残差适配 | B：全小critic重训 |
|---|---|---|
| 每阶段初态 | 原旧1041–1044四成员重新warm start | 四个全新MLP初始化 |
| 可训练 | residual、advantage；8参数张量/2,529参数 | state/action/head/residual/advantage全部；20张量/7,058参数 |
| 冻结 | state/action/head；全部9个预处理buffer | 全部9个预处理buffer |
| PCA | 每成员原旧投影不变 | 当前阶段全部唯一有效train源拟合，视觉16/语言8；四成员共享 |
| 学习率 | 1e−4 | 3e−4 |

**最终A不是接着round1 A训练；最终B不是接着B200训练。** final预检重新从原旧成员构造A；B在合并600源上重新拟PCA并fresh初始化。随后真实fit严格复用该封存预检的8初态、投影、trainable mask、bootstrap和minibatch计划，不再拟PCA或随机初始化。B200仅作为第二轮候选生成器保留作用。

A有一个结构性限制：state/action/head和PCA全冻结，且advantage在a0数学上相消，因此**a0基线分支没有学习新数据的自由度**；除浮点运算舍入差异外，其绝对基线仍由旧模型固定部分决定。新数据训练只改变相对动作修正部分。B可以同时适配state/action/head及相对部分，但最终开发规则选中A。

B的PCA：在bootstrap前对唯一训练源各使用一次；视觉8192维、语言2048维分别中心化SVD，取前16/8轴，投影标准差使用population std，floor=1e−3。沿用原视觉归一化mean/std，不用dev/cal/held估计任何统计。最终实际fit_source_count=600，语言8轴中4轴触及scale floor，视觉0轴触及；这不等于8个有效语义方向。训练/推理保留相同预处理数值规则。

每路径4成员分别按任务做完整episode有放回bootstrap。最终每任务120个有效源，从该任务抽120次，总600条bootstrap索引；所有候选与后缀随source同行。每更新从本成员bootstrap清单均匀有放回抽32个source，无成功/Q/轮次权重。初始化、bootstrap、minibatch使用独立phase/path/member随机域并保存真实采样索引。

优化器AdamW，weight_decay=.01，gradient clip norm=1，CPU float32、2线程、固定学习率；代码未指定betas/eps，使用实际封存PyTorch的AdamW默认值。round1每成员2400更新，final每成员4000更新。保存检查点200/400/800/1600/2400/3200/4000，round1只到2400。实际两条路径均训练到上限：round1 8×2400=19,200，final 8×4000=32,000，共51,200优化更新。这里是更新数，不是episode数或epoch数。

证据：[A/B初始化与冻结](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/training.py:229)、[PCA定义](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/training.py:170)、[source bootstrap](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/training.py:277)、[优化循环](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/training.py:342)、[最终预检构造8初态](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/final_training_pipeline_v1.py:334)、[真实fit复用与检查](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/final_training_pipeline_v1.py:525)、[实际PCA600](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/fit_preflight/final/final_preflight_v1/pca_fit_audit.json:604)。

## 7. 模型选择与最终A4000

同一checkpoint步数的4成员构成一个ensemble；比较所有A/B ensemble checkpoints，不跨成员挑不同步数。每个开发源用四成员平均概率从原13候选bank选一个候选；精确并列优先a0，再按槽序。开发选择把成员float32概率转float64平均；在线目标使用float32并单独校验部署一致性。

固定排序规则：①完整100计划源的真实配对净收益最大；②救害配对中的harms最少；③相对a0的概率gain MSE最小；④更早step；⑤仍并列优先B。gain MSE按95有效source、去重非a0候选计算；无有效gain组贡献0。5个无cut共同结局不伪造critic输入，但保留100源策略分母和零配对差值。

第一轮胜出 **B200**；最终胜出 **A4000**，即四成员均取A路径第4000步。最终离线bank选择收益+4.5pp、救23害5、gain MSE=0.0566079674；这是候选选择代理结果，不能当作实际连续梯度纠偏效果。每轮仅该选中critic做一次五臂真实开发rollout。后续确定post主方法、校准统一启用、最终held均是另外的策略评价/选择层，不更改网络训练损失。

证据：[候选/检查点排序实现](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/training.py:425)、[无cut开发分母](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/training_pipeline.py:335)、[第一轮实际选择](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/models/round1/round1_fit_v1/result.json:68)、[最终实际选择](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/models/final/final_fit_v1/result.json:84551)、[最终模型独立审计](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/final_trained_model_review.json)。

## 8. 防泄漏、数值保证与文档优先级

- split按episode分组；同源候选、cut、重复、alias不跨split。独立物理scene检查用于去重审计，不作critic特征。最终train600、dev100、cal100、held100不同；dev两轮复用属于开发数据曝光，不叫新的独立验证。
- train-only PCA及bootstrap只接触训练行；dev只做预检推理/重载检查、离线checkpoint选择和已规定实际策略比较，不能参与权重loss/PCA。cal/held不参与网络更新。
- 最终训练前已审8初态，canonical同shape的13候选概率、槽0/11动作梯度及a0锚定导出重载严格一致；训练后selected在dev95重载再次通过。**不是“所有13槽梯度都审过”**，也不是“任意batch shape逐位一致”。dense与singleton存在已报告浮点差异；保持canonical严格，dense仅诊断，不改算法或伪造容差。
- `TRAINING_SCHEMA.md`的50/50 cal/held、早期无fallback、held8次，以及部分文件开头“尚未训练/0更新”是历史草稿文字。实际采用EVAL20、ANALYSIS_LEAD、最终封存配置及完成产物。最终design参数来源仍绑定 `fit_protocols/round1_preflight_v1/training_design.json` SHA `3b9bbf7a67fc15123ac761c13358c0bfd8492ea9aea3c25649cefb02c66ef0cf`；其中旧status/precedence是参数来源历史，不覆盖final阶段的真实授权/执行事实。

证据：[训练/开发隔离](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/training_pipeline.py:214)、[最终数值预检独立审查](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/final_prefit_independent_review.json)、[最终训练后重载调用](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/final_training_pipeline_v1.py:587)。
