# A11：MT50 后续采集的 CPU 准备

task_id=`A11_MT50_CONTINUATION_CPU_V1`；revision=1；owner=A；release=`P00_A_MT50_CONTINUATION_CPU_V1`。读取最新 CONTROL/TASK_BOARD、自己 DISPATCH；本任务只做隔离 CPU 准备，不运行任何真实采集入口。

## 已冻结的分析决定

Batch1 已验收并关闭：8计划源均已处理，7个源配对合格；p04 disassemble ordinal1/cut55 在 s48 成功，作为合法 cut 前终局保留，不是技术失败，不重跑、补源、换seed或改cut。累计处理9/500计划源，配对合格8个train、dev0，另1个normal-only；剩余491个未执行计划槽。以 `manifests/COMMON_POOL_ACCEPTED_PARENTS_V2.json` 与 `manifests/COMMON_POOL_SOURCE_DISPOSITIONS_V1.json` 为准。旧V1、原始raw exit3及所有失败/成功证据不改。

当前已验证采集仍覆盖既有5任务，其他45任务的实际初始化与完整状态资格未得到实测证明。新任务补齐正式MT50覆盖的准备，不修改原始500源覆盖计划，不宣称500源足够训练。

## 五项交付

1. **任务级初始化预算表。** 用冻结真实MT50任务字典、示范任务目录/已有清单与环境源码做定向静态分析，列50任务与task index/语言index（push与push-back共享语言index但仍不同任务）。既有5任务复用已验收证据，只审剩余45任务受调用的初始化/reset_model/_get_obs/mj_forward/do_simulation及wrapper路径；不全文重扫工程/资产。为每任务区分taskset、wrapper、诊断reset与控制阶段的caps，给源文件SHA/窄行依据。未知不能套用shelf的52/104/26000或猜常数；标unknown并保持该任务真实入口拒绝。
2. **确定下一批8个原计划A源。** 对实际冻结50任务名称按ASCII字典顺序排列，选择其中尚未处理的 train ordinal0/cut5 槽，取前8个；若不足8个，停止并报告，不自行改ordinal、节点或cut填满。此规则仅基于已处理身份表，不能按成功率、标签、运行快慢或静态审计是否容易改变选择。源/seed仍用既有确定规则、A owner划分；全部500的未执行清单可做小JSON元数据，不创建真实shard。若选中任务cap未知，仍保留槽位并报告阻断，不跳过。p04和旧shelf0不进入新批。
3. **隔离的 Batch2 未授权包。** 沿用已实测scheduler、每parent15顺序cold分支、同一parent固定UUID、并发2、单外层预约和退出/发布屏障；只做新任务支持所必需的表驱动config/预算/身份参数化与窄拒绝检查。不得复用模型跨分支、扩大并发、改采样/动作/噪声/状态容差/终局/标签或公共接口。保留原始状态语义，本次不为外层partial_or_failed码重构调度器；分析端已将合法cut前终局单独归类。按所选8任务逐项合计数值caps与调度aux、存储/timeout/固定source-device映射；准备新task/release/run/wave/claim/output/cache、board ready/release template UNAUTHORIZED_TEMPLATE 同源元数据和纯JSON发布入口。新正式路径不创建，不claim。
4. **有针对性的CPU检查。** 复用真实组件的小合成fixture覆盖新任务映射/初始化预算拒绝、已处理source排除（含p04不补源）、固定8源/并发2、源身份/RNG规则、两repeat与C10/C5隔离、早成功到cut前/commit内/边界的合法mask和未采H10语义。只检查新增或改变路径；不要重跑全部旧133/185/85套，不重做完整库存，不读取held集合或大权重。synthetic算量与真实操作向量分开，旧约束测试复用已封存证据。
5. **参数化资源与证据。** 引用已验收Batch1时序：16143.591s、106cold loads、峰值并行2；单载入平均124.80s和约46.45% child host区间占比仅为该批观察，不是GPU秒、实际IO或可消除耗时。下一批按满120分支报价，不能把本批cut前成功/早终局带来的较少步数当预算上界。项目quota、容器内存、RSS/VRAM峰值、实际IO/监测超调仍未知；存储风险接受仅属于已关闭Batch1，新模板不继承。不要另做硬件/内存/磁盘探针；读取既有证据即可。可列加载复用的未来思路与语义风险，但本任务不实现此类优化，不新增短GPU实验。

## 禁止与收尾

Torch/MuJoCo/GPU库导入、dlopen、NVML/设备/holder/实时进程查询、模型/encoder/候选器实算、环境/reset/仿真/真实RNG/梯度/训练、真实launcher/claim/预约/安装/共享guard改动/删除/大权重hash均0。允许标准库/NumPy合成测试与小型JSON/静态源码解析；真实数据只读引用，不批量重编码或重hash17GB产物。旧13计算release全部不可复用。不要改CONTROL/TASK_BOARD/共享dispatch或B文件，不向B会话发送命令。

交 ACK、短 REPORT、RESULT、CPU_READY、定向验证/差异及manifest，说明50任务中静态可报价与仍未知的数量；只交一个固定8源/并发2的未授权Batch2提案。若完整支持不能在本轮闭合，报告具体源码/字段阻断，保持同一8源，禁止隐式降级。完成后停止；真实采集、训练、评测与删除均需独立后续授权。
