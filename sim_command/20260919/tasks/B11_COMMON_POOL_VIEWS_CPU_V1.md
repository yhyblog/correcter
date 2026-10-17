# B11：共同池视图与sidecar CPU适配

task_id=`B11_COMMON_POOL_VIEWS_CPU_V1`；revision=1；owner=B。
release=`releases/P00_B_COMMON_POOL_VIEWS_CPU_V1.json`。核对当前CONTROL/TASK_BOARD、host、任务/release SHA后写新ACK。B10_PREFLIGHT_REVISION_R2及B存储专项已验收；不重投、不重跑旧任务。

以 `contracts/COMMON_POOL_PROTOCOL_DECISIONS_V2.md` 和 `results/A/A11_COMMON_POOL_REVISION_CPU_V2/FIELD_VIEW_MATRIX.md` 为冻结语义，在独立新目录实现**纯CPU元数据消费者与资格检查**。保留B10旧包、模型、损失和公共interface_v1不变，无真实数据提取/网络前向/优化器。

1. 各方法独立资格：正常示范LVM只需同episode连续t..t+10、真实两端token签名/形状、原action_t与normalizer身份；缺terminated/truncated不再由通用AND门整批拦截。其缺失仍null。D5需真实到达窗口/实际动作，GAF需真实10步动作窗口及其完整折扣目标；不足10步继续按B已冻结规则排除，不补动作，不继承LVM终局豁免。
2. G0 C5和Q C10严格分域，原parent绝对s300含末步；技术/额度/未知time-limit终局不能填0。gain/pair/G0仅full_state_verified+参与臂两个预定repeat共同完整，observable-only拒绝；单臂BCE资格不推导配对资格。raw-C10组去重，来源/role引用不增加物理样本数。特权恢复状态只用于审计，不能进入任何模型输入。
3. A为sidecar schema唯一发布者。检查 `results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/sidecar_v1/READY.json`；存在则核SHA并消费schema/例子，写不可变 `SIDECAR_COMPATIBILITY.json`，列通过与明确拒绝。未发布时先按既定字段语义实现内部adapter和synthetic fixtures，不自称接口已兼容，不另造竞争public schema；交付时明确pending，待同一任务的定向集成补充即可，无需停下所有独立工作。
4. CPU fixtures用少量形状描述/明确synthetic token与动作元数据，覆盖正常LVM缺终止可用、缺端点/错encoder/action表示拒绝、GAF短窗拒绝、跨parent/cut/repeat错配、别名、缺repeat、s300完成/技术截尾区分。列各视图train/dev父源继承和有效数量报告字段；不能将合成数量当真实有效样本。现有示范与新增共同池、旧训练初始化分别列沿革，不宣称相同全部历史数据。
5. 输出实际adapter代码快照、输入/检查manifest、DIFF、视图合同、compatibility或pending原因及短REPORT/RESULT。只测新增与真实消费者组合，不重跑旧9测试或新完整库存。A collector与B adapter可以并行，B不改A产物，也不领取A的真实source分片。

本任务不需要再做独立两forward GPU探针。旧B GPU提案继续封存未授权：其90秒handoff以及200 GPU秒/1600预约秒字段不能直接用于未来计算。记录此待处理项，等未来真实训练/适配运行包绑定300交接和各timeout作用域时一起闭合；本次不发新GPU提案。

GPU/驱动查询、Torch/MuJoCo/dlopen/NVML、模型/encoder/环境/采样/训练、holder查询停算、真实launcher/claim、真实seed/shard、安装/删除、大权重hash均0。允许标准库/NumPy小型CPU synthetic tests及必要静态读取。旧包、CONTROL/BOARD、共享guard不改。

B的27文件无依赖声明已验收，保持不打开这些候选的承诺；需要变化先报分析。清理由A按未来独立精确release执行，B不删除。交 `receipts/B/B11_COMMON_POOL_VIEWS_CPU_V1_RESULT.json` 与 `results/B/B11_COMMON_POOL_VIEWS_CPU_V1`，完成等待验收，不自动计算。
