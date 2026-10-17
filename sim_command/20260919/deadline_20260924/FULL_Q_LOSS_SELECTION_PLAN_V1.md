# 完整Q损失消融、开发选型与正式配置验证

用户2026-09-22决定：取消Random-multi；先完成完整Q损失消融，再选择正式配置。随机单次触发结果保留。旧结果、旧失败和旧部分Q微调权重保留，不能改名为本实验。

## 立即取消与在途处理

Random-multi全部7500条撤销，未用额度不得转回随机实验。A旧E1 multi只排空已进入episode；调度最小单元若是已发出的5源chunk，可排空该最小chunk并报告。其余旧E1不再准入。B已启动的专属once恢复收尾；B/C未进入的旧Q Post/Velocity multi暂缓，已进入单元保留；Q无关的R可按原范围完成。若运行器没有协作准入边界，原执行端可取消本任务自有runner/进程组并保存已落盘终局；在途缺项标user_cancelled/unknown而非任务失败，不自动重试旧配置，不终止无关进程。只写共享决定不代表取消已经生效，须有各端ACK和处置。

## A：四损失完整训练与开发选择

新任务A_D24_FULL_Q_LOSS_SELECTION_V1。优先训练/开发，旧正式链退出后自动接续，不需再次许可。新任务评测优先每卡3worker共24，沿EVALUATION_CONCURRENCY_24_V1；本机资源不支持时报告可行并发和证据。

完整Q保持现有TenStepCritic结构，每成员7058参数。state/action/head/residual/advantage所有可学习参数重新初始化、全部训练；不能加载旧selected.pt网络参数再称从头训练。只允许从旧资产提取冻结的train-only PCA/norm等明确预处理字段。每个(fit seed,member)生成同一份未训练初始化供四loss共用，bootstrap/minibatch流也配对，派生键不含loss。训练结束记录实际可训练参数数、更新步数及各模块变化摘要即可，不做全模型哈希/完整一致性证明。

固定历史train600、同候选资格mask/去重/source加权和动作单位；不重新采训练数据。四loss为L00=BCE、L10=BCE+gain、L01=BCE+0.5pair、L11=BCE+gain+0.5pair。fit seeds9101/9102/9103，成员1041..1044；48fits，每份AdamW lr3e-4/wd0.01，batch32、clip1、固定4000末步，共192000更新。其他训练与现有完整Q路径对齐，不同时调整架构/引导强度/损失系数。底座、编码器、D/G0冻结。

开发100：results/A/A_D24_CORE_REMAINDER_V1/config/E6_SOURCES.json中development，五任务各20、env_seed2026111600..1699。与训练父源及E1 test进行普通身份交集检查；不能使用该文件test部分冒充dev。复用初态定义进行真实H10/C10 multi rollout，4loss×3fit×2分支×100=2400条。它是反复使用的开发集，不称全新盲测。开发与正式评测使用A主表现有NVIDIA EGL/30Hz/.015和pi05冻结动作桥；旧E1 Mesa结果只历史记录，不把renderer差异归于loss。首次已计划episode确认合法图像/动作即可。

开发选择一个共同loss用于Post/Velocity及跨底座。评分为五任务、三个fit、两个分支等权的成功率均值；完整开发单元可比较后取最大值。精确并列先辅助项更少，再按固定L00,L10,L01,L11顺序。不得按test改选loss、调阈值或挑fit；正式部署预先固定fit9101的四成员，不组成12成员ensemble。若有无法纠正的开发缺项，不以不等分母评出赢家；报告缺口并先完成其他独立阶段。一次明确技术纠正允许，合法终局不重放。

先发布results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json：各loss/seed/分支开发分数、选择规则、chosen_loss、固定fit9101、对应四权重及预处理、success/valid/技术缺项，锁定后才开始以下测试。该文件无需分析逐批许可即可供B/C消费；锁定后不得因任何test结果改变。

## A：选择后测试

1. 完整Q四loss补充消融：原work/B/B_D24_E1_EVAL_V1_r1/TEST_SOURCES.json完整rows50，4loss×3fit×2分支=1200。选择已锁定；此50源历史已揭晓，只能称复用测试源的补充消融，不称新独立盲测。共同源不能把三个fit当150独立初态。
2. 正式multi主表：所选loss、固定fit9101，Post/Velocity×H10/20/30/40/50×原500=5000。N、R、E6及外部方法原结果复用，不再执行；主表各H沿原source/env/policy/candidate随机流、D/G0/C10/阈值等，仅换Q。
3. 主设置次数对照：同一新Q的Post/Velocity once、H10各500，共1000；与新multi H10成对。旧五H once/multi保留为旧固定Q上的机制证据，不能和新Q混算纯次数收益。没有新增五H once大矩阵。

合计A首次评测9600（dev2400+消融1200+主表5000+H10 once1000），技术纠正余量500，stage cap10100。累计attempt cap27000，旧消耗不重置。新训练仅192000小Q更新，采集/SFT/D/G0更新0。已完成E6 multi100和CPU外部比较保留；换正式Q后再从保存结果CPU更新E3配对、E5调用/成本、表图。

## B/C：利用各自专属数据准备候选Q，然后按A开发选择执行

B新任务B_D24_FULL_Q_LOSS_REFRESH_V1（Smol），C新任务C_D24_FULL_Q_LOSS_REFRESH_V1（X）。各自沿已完成专属train数据和train-only PCA/norm，D/G0及底座不动、不重新采集。各4loss×4成员、固定fit9101，共16fits×4000=64000更新。全部Q7058参数从相同配对未训练初始化训练，目标/优化器与A一致，动作坐标按自身冻结桥。可以立即CPU准备及小Q训练；若使用GPU，须等本机原正式族退出，通过同一guard lifecycle，不能在别的正式wave旁插入。

各自独立完成全部候选，发表CANDIDATES_READY后结束LLM等待。SELECTION.json是必要科学配置依赖，不是跨节点进程退出屏障；轻量后台读取一次有效选择后，加载自身同chosen_loss固定fit9101四成员，Post/Velocity multi各原500，共1000。禁止加载π0.5 Q来代替自身头，禁止用本机test另选loss。R不依赖Q，可完成/复用旧multi500；B/C旧L11 multi已完成部分保留为历史，不用其作为新Q单元。若没有证明权重及运行配置相同，不冒充结果可复用；也不为复用展开严格全量审计。

各节点新增first test1000，stageattempt≤1100，B累计cap20000、C14000不变；各新Q更新≤64000。如果已获原授权的R需要接续，记原任务消耗，不藏进新Q1000。本轮不新增外部复现或LIBERO盲目采集。

## 发布和结束条件

全项目本次新Q更新上限320000（A192000+B64000+C64000），新first评测11600（A9600+B1000+C1000）；与取消随机7500的旧机会分别记账，不能直接抵消历史attempt。可并行训练/本机R及准备，选loss后各自自动评测，无用户逐批确认。

所有评测按EVALUATION_CONCURRENCY_24_V1争取24实际worker；普通容量检查、首计划episode检查、有限监测即可。无需GPU预检、MJB/全状态证明、百万账本或重新hash底座。正式wave全holder停算，整族退出后恢复；后台唯一claims/心跳/实际终局/原线程回调。稳定后STABLE_HANDOFF并结束LLM轮询。

科学准入9月23日20:00北京停止，表图23:00冻结；单阶段最长12小时或总截止较早者。元数据/报表错误不能丢掉科学终局；用户取消/技术异常都不填success=false。缺项如实保留，不能以已揭晓test选更好配置后假装独立确认。
