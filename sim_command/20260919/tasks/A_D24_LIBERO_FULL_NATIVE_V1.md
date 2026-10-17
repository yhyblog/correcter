# A：LIBERO完整系统的必要原生适配

任务 A_D24_LIBERO_FULL_NATIVE_V1，revision1。用户明确要求本方法优先、空闲节点继续未完成任务。原计划LIBERO Full-Post/Full-Velocity尚未实现，B现有两组是无D/G0、BCE小头的算子迁移。直接按 IDLE_NODE_CONTINUATION_AUTHORIZATION_V1.json 推进，不需要CPU_READY或逐批批准。不要重启旧A主链/外部方法。B正在收尾的算子Velocity独立保留；本任务不是它的重跑。

## 固定输入与科学边界

复用 B 的 work/B/B_D24_LIBERO_POST_V1_r1 与 results/B/B_D24_EXTENSION_REMAINDER_V1/r1/D24_E8_LIBERO_POST_r1 中正式官方pi05、normalization、原400测试源、32开发父源/24train+8validation分割、160候选结局、原生7动作8状态及329维特征定义。B小头训练开发资产只读。native Velocity桥读取 work/B/B_D24_LIBERO_VELOCITY_V1_r1 已冻结实现，不等待其测试成功率，更不能据B已揭晓test选择参数。必要代码/环境复制仅A私有目录；不复制大权重。

首次窄查真实开发字段，目标是能否训练D/Q/G0，不是SHA/像素/MJB一致性审计。缺逐步特征不能用qpos/qvel或test补造。B160条是a0+扰动的开发候选，不能冒充old-vs-fresh收益监督。

## 本任务冻结的本地时距

保持N的正常执行K=5、raw horizon=10、NFE=10与官方动作坐标。监测采用D2：每个新native chunk启用前，预测该计划前2动作后的原生未来特征；执行2动作、取得真实观测后成熟。只在这个chunk内age=2处进行一次监测判断，此时正常队列还余3条。不存在合法cut或已终局直接跳过，不强行干预。

G0目标固定为“fresh普通计划执行3条后恢复native K5”减去“当前旧队列余3条后恢复native K5”的期末成功收益；以下简称 execute3_then_native5。这样old分支就是正常队列继续，不能将其改成在cut额外丢尾。G0输入仍是因果当前context、已知旧future-action block及D预测，原生维度/掩码明确记录；不把成熟残差事后拼成原G0未用过的输入。D2输入与目标单位按train-only归一化。监测2/参考承诺3是必要跨环境时距适配，不称原D5实验或完全相同超参。

真实部署G0>0.05时才干预，每episode最多一次；Post/Velocity纠偏承诺C=5，旋转不动、XYZ/夹爪沿B已冻结物理半径和独立自身半径定义，C5后丢弃未执行尾部并恢复native K5。Velocity末3步、梯度链/自身半径沿已冻结原生桥；无Q接受门、回滚或重试选优。未触发时保持原N轨迹规则；不改K来制造合法cut，不新增另一套N。

## 最多40次必要开发，设置累计不重置

该设置B已使用32父源/160物理开发attempt；原上限40父源/200attempt保留。本任务最多额外40attempt，优先复用既有父源，不新增父源。按已有development source/parent的固定词法序，每suite取train前4父源及validation前1父源，共20父源（16train/4validation，均来自原32，不取test）；每个父源独立cold old/fresh两支各一次，共40attempt。固定原env seed及成对prefix policy stream，首次合法age2为采集cut，整局真实终止口径沿LIBERO suite。fresh分支在cut普通新采样3动作，old支执行旧队列3动作，之后都正常K5至终局。没有合法cut或技术失败保留无效/缺失，不换源/补成功样本；40额度包含本阶段失败和任何允许纠正，不额外重试超过40。

在这些已计划轨迹中同时保存训练D2需要的真实逐步特征/已知动作/成熟目标，不再单开rollout。old/fresh得到真实终局y_fresh-y_old，只有一对观测而非双repeat成功概率，明确这个适配标签噪声。已有Q候选的a0/±和结局可供L11的BCE/gain/pair：仅按真实共同parent/cut及实际动作来组对；字段/标签不足则不能伪称已实现L11。不得用新测试结局完善训练或选阈值。

D/G0采用主方法对应双成员结构，必要输入/输出维度替换为原生特征与时距；固定seed241/242、341/342，每成员4000更新。Q原生四成员结构沿B，改回主方法L11组合及原冻结损失系数（从已验收E1 L11配置读取，不自选），固定seed9301..9304，每成员4000更新。合计最多32000小网更新，底座SFT=0。仅train拟合归一化/参数；固定末步checkpoint，validation描述性输出，不按test选择模型或强度。

若真正G0收益标签无变化/训练目标缺失、原生接口使上述age2/old3语义不可实现，停止该受影响Full单元并提交具体字段/标签/数学问题，勿把算子结果或全零触发拼成“Full已验证”。这属于科学适配缺口，无需扩大严格检查。只允许修复实现错误，不擅自扩开发额度、阈值sweep或改科学时距。

## 自动评测与期限

真实D/G0/Q训练目标成立且实现接通后，写一次小型METHOD_FROZEN.json，直接后台跑同原400 test的Full-Post，再Full-Velocity；不等待分析批准。源码、参数、源表和方法冻结先于test。两单元共800首次评测，单元独立输出；最多1000新物理attempt（其中development硬上限40），失败纠正沿一次规则、成功不重跑。正式目标8路有用worker，同卡原holder及后代退出后才启动，全波退出后恢复。CPU-only准备期间不停止占卡。稳定后结束LLM等待，阶段失败/终局通知A原线程并交共享回执。

首次字段/时距接通进展尽量30分钟内交短回执，但不要停下等新的CPU放行。最长本任务墙钟8小时或总deadline中更早者；无法完成时报告已完成/缺项，不能为了填图扩数据或改变测试。无需先跑独立GPU预检或全量测试。

交付 results/A/A_D24_LIBERO_FULL_NATIVE_V1/{METHOD_FROZEN,DATA_STATUS,FIT_SUMMARY,FINAL_SUMMARY,PER_EPISODE,RESOURCE_SUMMARY} 对应JSON/CSV与短REPORT；receipts/A/A_D24_LIBERO_FULL_NATIVE_V1_RESULT_r*.json。标为Full-Post/Velocity native-LIBERO（D2/G0-execute3/nativeK5/C5，旋转冻结），明确与主设置时距不同。若只接通部分组件，名称相应降级，不冒称Full。B原operator对照全部保留，A不等待B或C的整个任务。
