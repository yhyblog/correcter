# A11：首个 shelf-place 共同池采集器 CPU 实现

task_id=`A11_COMMON_POOL_COLLECTOR_CPU_V1`；revision=1；owner=A。
release=`releases/P00_A_COMMON_POOL_COLLECTOR_CPU_V1.json`。核对当前CONTROL/TASK_BOARD、host、任务/release SHA后写本任务ACK。旧V2协议已验收，不重做盘点/旧测试，不重投旧回执。

## 目标与范围

实现可审阅的H10共同池最小采集器，为未来**首个计划shelf-place train父源、cut5**准备有限提案。使用既定π0.5 SFT、独立535 EGL栈、UUID和strict loader、真实recorder与已修复handoff；旧包不改。只写新私有代码/配置及CPU检查，本任务不运行真实入口、模型、环境或硬件。

读 `manifests/COMMON_POOL_REVISION_CPU_V2_ACCEPTANCE.json`、`contracts/COMMON_POOL_PROTOCOL_DECISIONS_V2.md` 及V2的协议、字段合同、报价；数值方法与实验矩阵不改。500父源是规划，本任务不实现或放行整批MT50。

## 选定实现路径

1. **先实现保守cold policy replay＋完整字段比较**，一个normal源及14个Q/G0分支，各独立新子进程，单机同一formal预约顺序运行。normal无复用，snapshot恢复、persistent worker、动作回放省采样、去重省计算均不在首版；用支持矩阵明确未实现/未验证。首个源未来可成为已规划500源之一，不另增“诊断父源”；真实ID/seed只在未授权提案中建议，不创建活跃数据shard/claim。
2. normal在真实cut观测/history更新后保存参考字段，隔离生成fresh0/1/2和局部±bank；不能推进normal/prefix/suffix随机流。Q a0/±各2，G0 old和三fresh各2；按协议分流C10/C5，完整目标到parent s300。源未到合法cut则如实结束，无换seed补源。cut后成功按真实完整结局处理；技术失败或状态资格不通过停止最小wave扩展、保留已进入成本，不重试。
3. 每个重放分支在干预前比较与参考一致的完整字段；先核source/prefix/raw计划/历史，再应用预定repeat流。物理状态与故意不同的run/branch ID分开。unknown不得通过；schema版本、每字段captured/recomputed/immutable/irrelevant/unknown及依据机器可读。先闭合shelf的integration、可变model、task Python、RNG、wrapper绝对时钟、队列和历史；未知插件/回调/模型修改必须拒绝。固定环境类allowlist，其他49任务默认拒绝，不能把shelf证明推广到MT50。
4. 不调用额外_get_obs核验，不悄悄改变_prev_obs；cold replay不执行mj_setState。静态闭合mj_getState/mj_stateSize与model/task字段读取/序列化方案及完整计数。若采用MJB只作model字段身份序列化，说明哪些运行时修改被覆盖，不能据header声明已真实证明。原数组逐位核验、浮点精度/字节序明确；不得看真实差异后放松容差。
5. CPU实现并用**小型明确synthetic数组/假对象**测试平滑高斯节点插值、各组自身对称半径、raw C10别名、raw50尾/零坐标保位、双repeat缺失mask、s300含末步/早成功/技术截尾，候选RNG隔离。允许标准库/NumPy CPU fixture，不导入Torch/MuJoCo/GL/NVML、不读真实轨迹做新投影。合成RNG/投影测试单列为CPU测试，不冒充真实采集操作全0。源级损失不改，partial BCE训练权重以后冻结。

## 数据与B交接

公共interface_v1保持原SHA。恢复/资格/repeat/target_namespace扩展放独立版本化sidecar；A为schema发布者，**尽早**在本任务结果目录 `sidecar_v1/READY.json` 发布schema/README/显式synthetic例子和SHA，发布后不覆盖。至少含原record/parent/attempt身份引用、schema/输入签名、绝对时间/承诺/目标、outcome/missing原因、planned/valid repeats、raw组、恢复证据引用与逐字段判定、各方法独立view资格。实际传输字段名由A集中发布，不能两端各造一套。

B任务为 `B11_COMMON_POOL_VIEWS_CPU_V1`，从共享目录消费；A把READY路径写回执即可，不直接跨机会话投递。B的兼容反馈缺失不妨碍A完成独立CPU实现，但不得宣布双方集成通过。LVM-only正常示范资格不依赖终止字段；D5真实窗口与GAF完整目标/实际动作资格不放宽，GAF不足10步窗口沿B已冻结的排除规则，不补动作。首个parent不提取整套2500示范token，也不默认保存新增rollout全token。

## 有限未来提案与测试

- 只报一个A-only首parent提案，先CPU fixture，真实状态/C5/C10/首suffix步的检查嵌入该parent，完整结局亦在同一次计划采集中取得；不再额外开短诊断父源，不将短段当完整负标签。任何门失败留证并停，不自动降级为observable-only配对。
- 完整且无早停的算术交叉检查是15attempt、4500controls、453sample/4530flow、4515观测；这些不是本次授权或足够的完整caps。重报模型/编码/初始化/完整状态读取与序列化/graphics/loader/清理全部辅助上限；shelf冷初始化参考780native reset/1560reset_model/390000初始化子步须与具体实现逐项绑定。恢复/比较不能隐藏为零成本。
- 使用已验证真实recorder和真实controller的CPU组合路径，拒绝只测试另一个fake emit。覆盖未知字段、错误源/UUID/schema/SHA、partial write、磁盘失败、早停/异常、无末事件、首分支失败不启动后续分支、重复claim拒绝。只测本轮新增/改动，不重跑大套历史检查。
- 新未授权模板的board.status=ready、release.status=released语义与纯JSON发布checker同源；当前template必须UNAUTHORIZED_TEMPLATE。未来命令绑定新host/UUID/输入SHA/seed/run/output/claim及安装guard SHA，固定handoff300；每child timeout与整波/准备/恢复分别报价，未实测GPU秒/端到端不伪造上界。全A八holder直到整个wave退出才恢复；失败整组清理，B不参与。无需本任务实现跨机预约协调器。
- writer逐步保存无损RGB、真实动作/next/终止、特征及账本；定义可执行的新输出字节硬限、临时/RAM/单记录上限和空间不足拒绝行为，含失败保留。项目quota未知继续报告，不能把statvfs当项目容量。首parent报价与2.08TiB整批规划分开；不写大测试文件、不做容量压力试验、不删文件。

交付独立CPU_READY、代码/输入/外部manifest、变更表、sidecar_v1、字段闭包/支持矩阵、真实入口和未授权提案、定向CPU检查及短REPORT/RESULT。若某shelf字段无法静态闭合，允许以具体阻塞项交付，不伪造通过；不自动扩大到49任务或新增实验。

禁止真实模型/环境/重放/采样/特征提取/梯度、GPU/CUDA/EGL/NVML/dlopen、holder查询停算、真实launcher/claim、安装/训练/删除、大权重重hash、历史held加载。允许isolated实现和小型synthetic CPU测试。旧证据、公共v1、CONTROL/BOARD和B包不改。所有本轮产物保留；完成等分析验收，不自动执行未来提案。
