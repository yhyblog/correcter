# A11：采集器状态、记录与有限资源准入CPU修订

task_id=`A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1`，revision=1，owner=A。
授权 `releases/P00_A_COLLECTOR_CONTRACT_CPU_REPAIR_V1.json`。先核对当前CONTROL/TASK_BOARD/host/release再ACK。前任务已作为CPU实现交付审阅完成，但尚不可运行；不重投旧任务、不启动旧未授权提案。

读 `manifests/COMMON_POOL_COLLECTOR_CPU_V1_REVIEW.json` 和 `contracts/COMMON_POOL_COLLECTOR_REPAIR_DECISIONS_V1.md`，按后者实施。保持科学候选/源/seed提案、动作公式、状态精度、采样及物理预算和单机整wave生命周期；只修本次明确缺项，保留旧包。

## 必交修订

1. full_state.typed区分Box定义与物理数组。用安装版MetaWorld观测空间的静态low/high结构构造明确synthetic fixture，先证明旧检查拒绝合法±inf，再让新实际serializer仅在正确字段放行。NaN/非有限物理状态/错类型继续拒绝，无真实MuJoCo/Gym环境导入或调用。
2. 统一episode ID函数及producer引用，保留source/parent分工。实际public episode/transition的null原因检查、无跨episode悬空引用、private整数账本不混public UUID。按分析决定使用空cost_event_refs+原因及独立私有费用索引，不另造公共事件桥。
3. aggregate修physical_alias_of=null，发布独立aggregate引用解释/索引schema与显式synthetic例子，所有paired_members的资格独立核验。旧sidecar_v1保持SHA；把新增解释路径写CPU_READY供B消费。非normal cut前结束至少保留真实BRANCH_RESULT/缺sidecar原因，不伪造配对；若改此路径，仅CPU定向检查，无新增GPU实验。
4. 移除自设RLIMIT_AS128GiB，保留继承平台限制；无需硬件probe验证。RAM估计/实际观测/硬限未知分列。纯CPU可读当前进程limits/cgroup小元数据作说明，不查询holder/GPU或安装任何限制器。
5. 按 `bounded_first_parent` 准入重写未授权storage合同和实际gate：不再要求虚假project quota/exclusive reservation或第三方写入0证明。受控输出硬限、日志、两份gate前JSON、有限temp/cache预算与已知写点、容量证据及unknown、写失败停止与监测超调分别记。只允许小型CPU临时文件验证必要writer行为，不做压力/大文件预分配/删除或共享cache更改。容量/监测只能证明其实际范围，不能伪造硬边界。
6. 新独立提案建议身份 `A11_COMMON_POOL_FIRST_PARENT_V2` / `P11_A_COMMON_POOL_FIRST_PARENT_V2`，未来run/output/cache/claim路径与V1分开，同源BOARD/CONTROL/UNAUTHORIZED_TEMPLATE和纯JSONchecker。不创建真实release/claim/shard，不运行真实launcher。沿用同一未执行源/seed建议，不换源挑结果；116原caps未改变项逐项diff，额外CPU/序列化/temp成本另报，不暗加模型/仿真额度。

交独立新目录的CPU_READY/REPORT/RESULT、最小DIFF、关键新旧SHA、定向CPU checks、输入/代码/证据manifest和新未授权具体命令/提案。继承大量未变代码/外部源可用原manifest引用加新diff，不重做全库审计、不hash大权重、不重跑133整套旧fixtures；只复现本轮实际失败与新增修改的组合路径。

所有模型/特征/训练/环境/真实投影/真实采样/GPU/CUDA/EGL/NVML/dlopen/holder/真实launcher/claim/安装/删除均0；允许标准库/NumPy小型synthetic CPU检查、隔离代码配置修改、必要窄静态读取。public interface_v1、已发布sidecar_v1、旧包、CONTROL/BOARD/B/共享guard不改。新证据保留；完成等待分析，不自动采集。
