# 共同池设计修订决定 v2（不是计算授权）

2026-09-20。V1五项CPU设计交付验收，具体审阅见 `manifests/COMMON_POOL_DESIGN_CPU_V1_REVIEW.json`。本文件覆盖V1中未冻结的候选/标签/分片问题，原报告与方案仍封存。没有真实seed、shard、计算release、项目空间预留或采集授权。

## 1. 本轮固定的设计规模与范围

首个覆盖批次按50任务每任务8 train＋2 development，总500父源、每源1个预定cut设计。每个task/split内按事先序号交替cut5/55；无合法cut不改cut、不补源/seed，完整保留无cut原因和实际成本。这是覆盖起始批，不保证学习充分性或统计功效，不等于500个有效配对训练源。H10/生成50、Q承诺10后native10、G0承诺5后native10保持。E1旧train600不补采，E8/真机不扩入本任务。

数量用于修订报价，真实父源/seed/owner清单、资源上限和实施包仍需分析另行发布。没有当前G0报警也要保留全50任务预定覆盖。

## 2. Q必须真正具有正反监督

权威算法§5.1的L_pair是同锚点正反组对；不能临时将a0和独立native计划当成该pair，也不能让Full静默退化成BCE＋gain。新Q结构只取三个逻辑候选：a0、local_plus、local_minus，每个2个suffix repeats。去掉独立native的Q后缀槽，不新增Post/Velocity候选或参数扫描。

局部方向独立于当前Q，沿用算法§3.4已文档化的平滑随机探针：每动作维在时间0、4.5、9抽3个独立标准高斯节点，对10步线性插值。12个原节点、插值10×4方向、RNG实现/版本与预定流身份在未来新manifest中绑定并保存，不因全零、边界或结果重抽。

以同一个a0有界前10步b，按现有mask M=(1-|b|≥0.05)、XYZ/gripper RMS目标0.05/0.10、逐坐标上限0.15/0.40、margin1−1e−6，沿这一个随机方向求自己的对称可行半径；产生±δ这一对。不是跨Post/Velocity方向取共同半径。非活跃位和raw尾保持a0位语义。数学上正反对称，float32实际写回/执行delta分别保存，不伪造严格位级反对称。零组不重抽，两个候选如同a0或互为raw别名则按冻结规则屏蔽相应gain/pair，父源仍保留。

训练别名依据同源同协议的前C10 raw命令字节；仅clamp后相同不算raw alias。raw50/噪声完整身份也保留，但不同未执行尾巴不能制造额外C10监督。逻辑候选、唯一动作组、物理attempt与标签引用分开，按源内去重再源间平均。pair明确为(local_plus,local_minus)，不改损失权重或公式。局部采集是训练手段，不作为论文独立创新。

## 3. G0保持三fresh经验估计器

每合法cut生成3份独立普通fresh计划，fresh0就是Q锚点a0；fresh1/2仅供G0的C5臂，不再为Q额外执行。G0包括old和3个fresh，均各2个suffix repeats；每臂先执行5步再清尾采native10，直到同一绝对目标时域。目标保持mean_3fresh(mean_2repeat success) − mean_2repeat old success。

Q的a0 C10与G0的fresh0 C5可共享已生成raw计划，不能共享物理后缀结局。候选生成RNG与source continuation严格隔离；同目标协议、parent/cut/repeat/后缀决策编号共享预定义噪声身份，不含候选家族/host；Q-C10与G0-C5的流命名空间明确分开。2 repeats不是2个父源或2份fresh，3×2两层均需独立ID。

允许设计一个有条件的真实复用：事先将normal的cut后续流定义为G0_old5 repeat0。由于H10在cut时age5，normal接下来的5步旧队列＋native10可与这一臂是同一次真实执行。仅在计划年龄、目标时域、全部动作/状态/噪声/策略身份和完整结局条件一致时引用同一物理结果，保留正常角色与G0标签角色两个逻辑视图；不能事后因结果相同才别名，也不能当第二个repeat。实施未证明前主预算按不复用报价，另列可抵扣情形。

## 4. 有限终局和配对资格

目标是从原parent开始至第300个真实控制步产生的状态（s300，包含该步）内曾出现success。成功提前终止可形成完整成功标签；完整观察至s300且从未成功才给0。已冻结语义下的真实吸收终止可给0；私有配额不足、超时、未知TimeLimit、缺帧或其他提前截断仍null，不以预算停止伪装完整失败。每记录写parent绝对时刻、cut、剩余目标时域、outcome_complete和具体原因。

gain/pair/G0只准入`full_state_verified`：任务/目标、决定转移的完整物理/模型可变状态、RNG、wrapper控制/物理相位和终止、policy队列/history/噪声身份均在结果产生前完成核验。snapshot或确定性回放皆可作为实现路径，但仅RGB/proprio/context相等的`independent_replay_observable_match`不准入这些同状态反事实标签。特权状态仅作恢复/核验，不进模型输入。

本轮CPU修订须给出可实施的字段清单、所依据版本接口/源文件身份、逐位或容差规则草案及未覆盖项；未有依据的容差不能编造，未知项继续阻止该任务的配对准入。不能先看差异或结果再降标准。真实验证可嵌入首个计划collector/完整parent，不要求先另开全50恢复实验。

记录`valid_pair_repeat_ids`及planned/entered/completed/missing。本首批的配对标签要求两个预定repeat均在参与比较的所有臂中完整且身份对齐：gain为a0与该候选，pair为正负臂，G0为old＋3fresh的共同交集。任一repeat缺失则对应配对目标mask=false，保留交集但不把单repeat均值冒充原2repeat配置。单分支BCE可按自身完整结局准入并显式记有效重复数；具体训练权重/初始化另由A12/B12训练合同固定，不悄悄修改本方法源级损失。

## 5. 各方法视图与主机分片

VLA-Corrector正常动态视图单独验资格：同normal示范原episode、连续t..t+10、真实两端token与原action_t表示、正常器/encoder身份明确即可，不因缺终局terminated/truncated而整批拒绝。缺字段原样null并保留原因；D5需真实连续到达窗口/实际执行动作，GAF需其完整目标时域、实际动作窗口和终局资格，两者不得随LVM放宽。B需在未来视图适配确认该分流规则及sidecar消费。

共享池意味着共同可访问原始池，不等于全部历史初始化/训练数据相同。2500示范底座已见、旧五任务D/G0/Q和旧LVM split沿革均披露，训练配方待后续单独冻结。

train按(task,split,cut)分层分配A/B，每任务每台各2个cut5及2个cut55；可用parent ordinal的floor(i/2)模2分owner，与cut=i模2分离。dev每task仅2源，owner按(task ordinal+cut ordinal)模2交错，跨50任务两机各类cut等额。parent的全部候选/repeat/特征随owner，不按方法分机器；真实显式列表日后冻结。

联合wave节点compute-exited只报告本机计算已退出，不能立即释放本地预约或恢复holder；所有参与节点退出的全局屏障成立后才各自释放，失败也遵守。单机wave按本机退出处理。数据完整发布屏障与occupancy释放屏障是两件事，不互相冒充。

## 6. 修订报价与实施边界

冻结π0.5采样路径每完整sample为3次视觉编码（1实图＋2填充）及1次语言编码，不能把填充图像计算免费省略。显式特征提取、预处理函数调用/图像数量、视觉forward分别报价，别名不相加；未改/未证入口不能按1视觉/sample估算。

供算术交叉核验，不是release：在500源全部合法、2 repeats且全部至300、冷policy回放不复用时，Q6＋G0_8=14个branch/源，加normal共7500attempt、2250000controls、226500完整sample/2265000flow、2257500实际observation。若normal确为G0_old repeat0同一执行，则为7000attempt、2100000controls、211500samples。初始化、显式特征、验证、异常及重试另列，不能以这串数代替完整预算。

空间需重算新结构。优先流式不可变存储、无损RGB编码及按真实内容SHA引用；不改像素/dtype或丢掉方法所需字段。未验证的压缩/去重不抵扣硬上限，实测小样本均值只能作规划估计。demo token暂保留已报价float32，不静默换fp16。项目quota未知须定向查证/报告，不能把共享盘空闲或18GB清理候选当作已解决TiB级存储问题；当前无删除授权。

可分别报价保守冷回放与经验证后每worker持续加载/记录动作回放的节省路径；不假装后者已实现/获验收。有限collector验证须覆盖新a0/正负计划身份、C5三fresh引用、重复/alias/masks和恢复字段；纯CPU fixture与后续首个计划parent验证可组合，避免为每问题新建GPU实验。短验证不能证明终局或全MT50。

本任务只修订设计与必要静态证据/报价，不实现collector/logger、不构造环境/模型、不发真实seed/shard/release、不运行计算。Velocity风险及未授权可选日志保持原决定，既定方法/阈值/α不改。
