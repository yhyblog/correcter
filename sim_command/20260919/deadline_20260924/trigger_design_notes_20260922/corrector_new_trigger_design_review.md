# MT50 random-once / G0-multi：现有controller窄审查

主入口：`Corrector/sim_command/20260919/results/A/A_D24_MAIN_ONCE_V1/code/controller.py`（46行）；数值/种子：同目录`numeric_engine.py`；旧multi仅参考`results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/code/controller.py`（62行）。本轮只读这些窄函数及纯整数300步调度推导，无模型/环境/硬件。

## 必须沿用的精确合法性

时间t为执行下一个动作前、已有t个控制步，0..299。每轮先取得当前真实frame/proprio；队列耗尽则先native采样，age=0、active_horizon=H。

主controller行20监测门：`t >= locked_until and t % 5 == 0 and min(active_horizon-age, 300-t) >= 5`。

行23–25合法及G0触发：`len(frames)==5 and len(actions)>=4 and age>0 and t+10<=300`，且`mean(G0_members) > 0.05`。注意：`age>0`禁止在刚自然重规划的边界立即再次重规划；自然重规划发生在监测之前，不能用重置前age误判。history仅含截至当前观测和过去4动作；G0输入是当前context和仍已知的下5动作。现行实现没有新增D误差门，不能为multi额外增加。

介入后：生成raw50，设置age=0、active_horizon=10、`locked_until=t+10`；执行C10，锁内不监测/不中断；C10结束丢弃40尾部并native重采恢复H。恢复边界age0仍不能立刻再次介入，下一个绝对5步tick才可能合法。不可把修复后H长期改10。

任何动作返回success或done就结束，包括C10内部提前成功；第300动作结束。技术异常/外部timeout不当任务失败0；不能补动作到C10以凑满预算。

## G0-multi的最小变化

把主controller `count<1`变为`limit is None or count<limit`，multi limit=None；其他合法性、阈值、C10锁/早停全保留。不是每5步无条件重复介入，也不是去掉承诺锁。

必须同时改`first_cut`赋值：现主入口行31每次介入都`first_cut=t`，在once合法，multi会变成最后一次时间；应仅`if first_cut is None`时赋值，另记录每次cut/index（必要last_cut）。旧pilot行44已经示范此写法。

删除人为总次数帽后，仍有物理上限：最早首次t5；此后相邻cut至少15步（10步承诺+恢复native后至少5步）。在300步且t+10<=300条件下最多20次，极端cut为5,20,...,290，各H都一样。这个20由现协议推导，仅用于资源报价/日志断言，**不能另加一个改变行为的人为cap20**。实际成功早停和G0不报警会使次数更少。

## Random-once候选时间与因果性

若采用“回合开始前均匀选一个合法时刻”，在首次介入前固定native H，因此候选集合可仅用H/300步/5tick决定：

`S_H={t : 5<=t<=290, t%5=0, 0<t%H<=H-5}`。

| H | 合法预定cut数 | 最后合法cut |
|---|---:|---:|
|10|29|285|
|20|44|290|
|30|49|290|
|40|51|290|
|50|53|290|

不要从“该轨迹最终实际存活的cut”里后验挑一个，那会使用未来episode长度/成功信息。若在预抽时刻前合法终局，则记录未到cut/0干预，不能重抽/重跑，也不能删掉此源。必须报告实际干预率，这种once是最多一次，不保证每源一次；不宜事后按G0报警源筛选来强行相同次数。random是否需要成本相等的shadow G0由分析冻结，不影响随机cut抽样且不要把shadow算成必要部署成本。

随机控制器应该仅替换“是否在本合法t触发”的决定：随机预定t到达且legal即触发，不能依赖G0>.05，否则不是随机时机对照。保存G0门值可作shadow诊断但不参与触发。真实事件标`trigger_rule=random_schedule`，`true_G0_trigger`若另有测量则保持原实测值，不能因为random介入就伪称G0报警；`forced_engineering_intervention`也不能混写为旧工程强制预检。

## RNG隔离与配对

沿主入口的500源/策略种子，所有H/方法复用相同test identities，不换回旧pilot20。自然采样保持`start_natural_stream(policy_seed)`的独立CUDA Generator；`propose_natural()`只由自然采样消耗。Random cut用独立本地CPU RNG或hash，命名空间冻结、按source_id/policy_seed/H派生；不得调用global torch/NumPy/python RNG去干扰模型噪声流。R/Post/Velocity同source同H共享同一random cut，不以method派生不同cut。

所有修复candidate仍使用主入口的`seed_for('D24_designated_a0', source_id, policy_seed, t, namespace=engine.namespace)`。不把mode/random/G0/方法名/第几次干预加入candidate域；同source同t应同a0噪声。自然流与candidate始终分离：Velocity第2采样不能推进自然Generator，random抽cut也不能消耗自然噪声。多次介入后自然decision次数可能不同，这是路径变化，不能宣称同绝对时间强制噪声相等。

旧pilot的source_seed/suffix_seed基于first_cut是历史协议，**不要直接复制旧pilot controller来跑当前MT50**；应基于主入口增加mode分支，保留N/once当前流。只补少量CPU控制边界用例即可：t0/自然boundary拒绝、C10内拒绝、commit末尾恢复H、t290允许/t295拒绝、提前success、first_cut不覆盖、R/P/V共randomcut且独立seed。无需GPU预检/完整一致性审计。
