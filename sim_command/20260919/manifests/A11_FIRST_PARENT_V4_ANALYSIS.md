# 首个共同池父源验收与后续安排

日期：2026-09-20。A11_COMMON_POOL_FIRST_PARENT_V4 已验收并关闭；[权威回执](A11_COMMON_POOL_FIRST_PARENT_V4_ACCEPTANCE.json)，[训练父源索引](COMMON_POOL_ACCEPTED_PARENTS_V1.json)。

有效独立父源为1：shelf-place/train ordinal0/cut5。15条完整终局、7组双repeat构成相关监督，不是15个独立父源。12条到s300；3条成功提前终局。14份cut状态按冻结closure的225字段/9组及MJB一致，physical_equality_proven=null不变。Q均值a0/plus/minus=0/0/0.5，gain+=0、gain−=0.5、pair=−0.5；G0 old/fresh0/fresh1/fresh2=0/0/0.5/0.5，目标1/3。局部±是随机数据探针，不是Post/Velocity输出；这些值不证明纠偏性能或在线G0触发有效性。

实际384采样/3840flow/3804控制/3819观测。46私有作用域147971对事件，全部116caps内；整组退出后8holder恢复。保存内容按唯一inode计3,208,698,132B（约2.99GiB），不是硬链接路径合计的双份。存储监测863次无异常，原quota/缓存/超调/RSS未知保留。

父源耗时4337.169秒≈72.29分钟。只作为同速情景，500父源单串行流约25.10天、两机各一条串行流约12.55天；不能直接除以16，也不代表其余任务/cut55吞吐。提前终止child仍244–249秒，300步child288–293秒，冷初始化明显影响吞吐。下一项以多GPU处理不同完整父源为目标；不立即改变已经验证的branch冷回放语义或引入模型常驻。

当前进度1/500规划父源，后续499个槽位不保证全部产生合法配对样本。训练与正式评测尚未开始。下一A CPU任务准备有限多GPU波次，优先利用原五机制任务和cut5/55，保留500覆盖规划；B在现有CPU任务内用本真实父源验证视图索引。normal不是示范且缺LVM端点token，只能作为LVM正确拒绝案例。
