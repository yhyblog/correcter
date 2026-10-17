# SmolVLA / X-VLA 专属辅助网络重训与适用性验证 V1

2026-09-22用户修正：每个底座必须使用自己策略采集的数据重新训练辅助网络。既有Smol/X结果保留，名称改为“冻结π0.5辅助网络直接迁移”；不能据此判断专属适配后效果，也不能预先承诺重训一定提高成功率。本任务是我们方法的优先适用性实验，不是外部方法复现。

## 所有权与自动执行

| 节点 | 任务 | 完整独立链 |
|---|---|---|
| B | B_D24_SMOL_AUX_RETRAIN_V1 | Smol50k采集→D/G0/Q训练→R/Post/Velocity评测 |
| C | C_D24_XVLA_AUX_RETRAIN_V1 | X30k采集→D/G0/Q训练→R/Post/Velocity评测 |

现在可做必要CPU准备；各节点当前触发模式正式wave及全部后代退出后，自动接续本机新链，无跨节点屏障、二次审批或单独GPU预检。不终止/重跑正在执行的Random-once/G0-multi。目标8个常驻模型worker，父源/分支重置不重新加载大模型；训练阶段可按8个小网络分卡。全正式wave停止所有holder，整组退出后恢复，沿用本机guard/lifecycle。

内部截止不变：9月23日20:00北京停止新科学准入，23:00完成表格；队列为采集/训练/1500评测预留时间，预测赶不上时在完整父源边界交真实部分完成情况，不做无界扩采。单节点本任务最长12小时或总截止更早者；不因另一节点进度阻塞。

## 底座、观测与单位固定

- Smol保持050000，raw H=50、实际执行K=10；X保持030000，raw H=30、实际执行K=10。两者NFE=10，终局最多300控制步。不得把raw H当实际重规划间隔。
- 冻结旧扩展实际环境：MetaWorld MT50、Mesa llvmpipe、80Hz控制/400Hz物理、frame_skip5、action_scale=.01、corner2 480×480；以B/C终局证据为准，旧ENGINE_CONFIG/brief的30Hz/.015文本已过时。不要同时切换到π0.5主实验的NVIDIA/30Hz/.015。
- 原底座和原生flow/动作坐标桥保持；新测试仍用 work/B/B_D24_E8_POST_V1_r1/POST_SOURCES.json 的500个D24_MW_tXX_eYY。不是A主表的D24_NEW_TEST。资产入口deadline_20260924/C_ASSET_INDEX_V1.json。
- 为减少不必要实现，继续采用冻结π0.5外部视觉/语言特征提取及既定固定投影；**D、G0、Q全部为本底座新数据重训，数据统计PCA/norm仅train拟合**。不把Smol/X内部embedding硬塞旧π0.5映射，不称原生Smol/X特征提取；外部编码器的参数、显存、调用成本单列，不能只报11.9M附加总成本。
- Q动作监督统一为真实环境有界4维命令。Post尺度与Velocity原生内部坐标的Jacobian沿已完成桥接，不把不同底座内部坐标直接相等。保持独立自身半径、raw尾部/零增量约束与无Q接受门。

## 专属开发数据：250父源/底座，上限2000分支

每个MT50任务预先固定4 train +1 development，共200 train/50 dev父源。train四源切点依次5/15/35/55；dev切点从同列表按ASCII任务序号mod4选择。覆盖早中期合法cut，同时接受晚cut可能已提前成功造成标签缺失；不靠旧G0报警、测试结果或候选结局挑选cut，不后移/回退补造。

生成独立 PER_BASE_AUX_V1/{base}/{task}/{split}/{ordinal} 源/环境/策略/后缀seed命名空间，在首采集前封存小型SOURCE_MANIFEST与METHOD_FROZEN；检查实际初始化输入元组不与已登记测试/held源冲突，冲突用预定盐递增、仍在采集前固定。不能只换source_id继续用同一测试环境seed，也不使用原500测试或现已揭晓的原20pilot训练。不同父源split隔离，候选和后缀不跨split。

每个有效cut只生成**1个普通无引导fresh a0**，最多四种计划×两个配对后缀repeat：

1. old：真实旧队列/native K10继续到终局，不能在cut强制丢尾或当作fresh。
2. a0：fresh普通计划执行C10，丢尾恢复native K10，至终局。
3. local_plus与local_minus：在该a0前C10施加相反平滑随机可行扰动，后续规则与a0一致。三高斯时间节点0/4.5/9插值；沿原随机探针的XYZ/夹爪rho=.05/.10、单坐标cap=.15/.40、mask与对称边界；随机流由父源/cut固定，无旧Q/测试梯度挑方向。只用本候选自身可行半径，不恢复共同五方向半径。

两repeat共用同一cut/a0/正反方向、prefix种子，使用各自预登记且跨候选配对的suffix策略seed。第一old分支可同时生成该父源公共cut/bank，剩余支复用小引用；已知提前终局到不了cut时记录normal-only并跳过后续无意义分支，不补父源、不把缺标签填0。新接口无需MJB/full-state逐字段证明；可用现成可靠恢复，或同seed重置回放至cut并核基本动作/状态/合法观测。必要检查失配即标技术问题，不能硬当同状态配对。

每父源最多8个真实rollout，合计2000是上限而非保证有效数。local raw别名/零方向/缺repeat明确mask，Q的绝对结局与可识别gain/pair资格分开。正常分支继续后的全部真实终局用于标签；技术失败/未到cut/预算截尾不能标任务失败。

同时保存真实逐步编码观测、本体、动作、mask和未来5步目标供D训练。尽量单次编码复用，不重复逐帧存RGB、完整物理state或百万事件/巨量文件；保留少量已有帧用于必要观测检查。不得用qpos/qvel假造policy-observed状态。各split继承父源身份。

## G0目标与真实部署对齐

新目标是：
`mean(success(fresh a0 execute C10 then native K10), repeat0/1) - mean(success(old native continuation), repeat0/1)`。

a0的两个真实结局同时用于Q和G0，不新增采样；这是**一个fresh计划的两个后缀重复**，不是两个独立fresh计划或三计划期望。这次execute10目标明确替代旧π0.5 execute5标签，属于新适配定义。old在cut剩5动作时先执行完旧5，随后自然重规划，不能为了对齐10步强行丢弃新的尾部。

D仍预测未来5步，沿成熟历史/已知旧5步动作/G0因果输入；G0仍回归收益，不是失败概率。部署每5步检查、严格G0>.05、合法cut、最多一次、C10承诺后恢复native K10。新R是用本底座新G0触发、仅普通重规划；新Post/Velocity使用同一新D/G0加新Q。不要夹入随机触发或多次干预设置。

## 从头训练全部8个小网络

底座/外部大编码器训练0；D双成员、G0双成员、Q四成员各4000更新，合计最多32000更新/底座。两底座训练、PCA/norm和checkpoint目录完全独立。

- D/G0按已有结构/优化器做必要本域适配，新初始化，不续训π0.5旧权重。D只使用成熟真实5步窗口；G0只能使用有资格的old/fresh对。
- Q走既有“B全小critic重训”路线：四成员全部7058参数从头训练，包括E_s/E_a/H/E_delta/Fadv；不能仅训练A4000动作差/优势残差后称全网适配。L11保持BCE + gain MSE +0.5 pair MSE，损失单位/权重与既有E1 L11配置一致。
- Smol D seed1241/1242，G0 1341/1342，Q19301..19304；X D2241/2242，G0 2341/2342，Q29301..29304。固定4000末步模型，dev只做误差/校准/监督覆盖描述；不看test选择checkpoint、阈值、引导强度。
- PCA/norm等仅train拟合。D可用已计划轨迹所有合法窗口，不额外采集；Q/G0独立状态数必须按父源/cut报，不能把后缀repeat当独立初态。
- 数据采集结束先报告真实有效parent、各cut分布、成功/失败类、非零gain/可识别pair数量。若G0训练目标全部常数或Q缺少必要候选监督，保留科学缺口并停止受影响Full单元，不用常数输出或强迫触发假装完成；不按测试结果扩采/换seed。有效但样本不足/误差高如实报告，不承诺提高。

## 正式测试与结果解释

原各底座500个test源/策略seed/实际环境冻结，**新R、Full-Post、Full-Velocity各500**，每底座1500新首次评测。旧N不重跑：Smol234/496且4unknown，X403/500；与N做双方有效配对，缺失不填失败。旧冻结辅助网Post/Velocity保留，可与新专属适配对照，前提是实际底座/输入协议相同。

新表列N、专属R、专属Post、专属Velocity；另表保留旧frozen-head-transfer。报告success/valid/technical、配对救回损害和差值区间、真实触发0/1比例、policy/encoder/Q/梯度调用、可测时长及外部特征成本。模型训练和G0目标同时更新，结果解释为“底座专属完整适配包”，不单独归因于某个头。这里复用了已揭晓的500源，是补充适配评测，不称新的未揭晓验证。

每机新阶段：最多2000采集+1500test首次任务=3500，额外500仅用于明确技术故障的一次修正，**总attempt硬上限4000**；不给追加有利数据/重复成功样本额度。模型前启动故障另列。小网更新32000硬上限，基础SFT0。B累计attempt由16000增至20000；C7900增至11900；旧已执行、失败和claim全部保留，原触发实验stagecap5500不变。

部署实际有效8worker后记录STABLE_HANDOFF并结束LLM等待。数据/训练/评测由有界队列自动串联，阶段完成或失败通知原线程；无需逐阶段报告后等待分析放行。必要存储/RAM检查一次即可，不做全量hash、严格一致性审计、冷启动吞吐研究或附加GPU探针。

交付各节点results/{node}/{task}/的SOURCE_MANIFEST、METHOD_FROZEN、DATA_SUMMARY、FIT_SUMMARY、FINAL_EPISODES、FINAL_SUMMARY、PAIRED_COMPARISONS及短报告。回执写receipts/{node}/{task}_RESULT_r*.json。一次训练种子组是8成员ensemble，不当多独立fit-seed实验。
