# 首个共同池采集器：分析修订决定

2026-09-20。适用A的最小CPU修订与B现有CPU视图消费。共同池V2科学协议不变；本文件修工程合同，不增加实验、方法或训练主张。

## 1. 保持已正确的部分

shelf-place H10/cut5首计划parent，normal+14独立cold policy replay；Q a0/±各2；G0 old+3fresh各2；绝对s300与缺失mask；不复用normal；完整字段比较在干预前；同一A-only wave全8holder直到整组退出才恢复。15attempt/453sample/4530flow/4500control/4515obs是原无早停预算，不授权真实运行。

## 2. 状态元数据和公开记录

- 合法Box low/high可含±inf，它是空间定义元数据，不是非有限物理状态。仅在明确类型/字段允许这些IEEE值，并保留dtype/shape/原字节；NaN、非有限物理状态和未知对象继续拒绝。不放宽完整状态比较精度，不新增真实环境探针。
- 保留source_id与parent_source_id的不同含义，用单一episode_id规则贯穿private recorder、public episode、sidecar及引用。干预分支身份仍不进入物理状态相等条件。
- 现有private_causal_event_v1的局部整数事件和numeric/init/graphics私有账本不能当公共UUID事件。当前collector的public `cost_event_refs=[]`，并在missing_reasons说明“公共部署费用视图未交付，实际采集成本见私有审计索引”。另产不可变路径/SHA/format索引，退出阶段完成RESOURCE_LEDGER后再登记。无须追加公共event转换层；真实资源账本完整，E5公共部署费用视图尚未交付，两者分开。
- 实际public publisher对每个声明为null的字段补契约要求的原因；用真实publisher输出作CPU语义检查，不能只依赖schema结构通过。
- 逻辑配对aggregate的physical_alias_of始终null。沿用现有comparison_arms非空、repeat_id=null识别逻辑聚合，另以版本化、绑定SHA的小型aggregate索引说明record_ref的PAIRED_LABELS目标、label_key及成员sidecar引用。整体资格由所有paired_members证明，不用首成员复制摘要冒充所有臂结果。
- 已发布sidecar_v1的READY/schema/README/例子/validator字节不动。以上修producer与新增独立解释索引；若执行端发现确需新增schema字段，先报告具体原因，不覆盖v1。B既有B11任务可按该补充实现CPU消费，不宣称实际样本已兼容。

## 3. 首parent资源准入

移除新增的RLIMIT_AS128GiB。虚拟地址限制不等于resident RAM限制，不使用一次正式采集测试这个自设限制。继承平台约束不改；RAM/VRAM估计、已实现的进程组RSS观测及未覆盖峰值如实分开，不把未实现RSS/cgroup硬限写成已实现。

首parent与整批2.08TiB规划分离。不要求为了约8.8125GiB的单parent先证明整批quota或平台独占预留，也不做大文件预分配/挂载/cgroup安装。下一版可提出 `bounded_first_parent` 准入：有限源身份、实际受控writer/log/小元数据额度、当前容量证据、第三方temp/cache路径及估算预算、写失败/空间不足拒绝、监测覆盖和超调限制一并供分析审核。project_quota_known可为false，exclusive_reservation=false；不能填写虚假reserved_bytes。

受控writer的硬字节限与第三方写入监测分列。列本次固定加载链中实际已知写点，说明HF共享cache的读取/可能写入、TMPDIR、Python字节码、CUDA缓存等具体设置；offline或目录权限不能证明所有native库零写入。只增加必要的私有目录及有限临时预算，不改共享cache权限/安装。无法严格控制部分保留unknown和预期超调；监测不是原子硬配额。是否接受这一有限风险由后续具体release决定，本CPU合同不放行计算。

command/claim两份gate前JSON也要限制字段和序列化大小，计入固定metadata预算；保留命令一次进入与失败不复用语义。metadata拒绝和私有空间检查不得启动holder/NVML/模型。预算如因索引/temp增加，单独给delta，不随意扩采样/物理配额。

完整MJB调用及跨child字节稳定性、真实full_state资格仍放在原计划parent中检验；不增加独立短GPU探针，不在看到差异/结局后屏蔽字段或改容差。其他49任务继续拒绝。
