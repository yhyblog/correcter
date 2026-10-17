# A11：批量采集参数化与多GPU波次CPU准备

task_id=`A11_BATCH_SCALING_CPU_V1`；revision=1；owner=A。release=`releases/P00_A_BATCH_SCALING_CPU_V1.json`。核对CONTROL45/TASK_BOARD52、host/release SHA后写新ACK。V4已验收关闭，禁止续用额度。先读 `manifests/A11_FIRST_PARENT_V4_ANALYSIS.md` 和 `manifests/COMMON_POOL_ACCEPTED_PARENTS_V1.json`；不重投旧任务或重跑首父源。

## 固定目标

把已经跑通的父源采集器准备成能在A不同GPU上并行处理不同完整父源的有限波次。保留每个父源内部15个cold-policy-replay分支的顺序、种子与配对语义；本轮不实现常驻模型、跨branch状态复用、改变采样数或删减监督。可用已存计时拆分说明优化空间，但不追加profile/GPU探针。

下一有限候选波次固定为A所有权的8个尚未采集train槽位，作为原500覆盖计划一部分：

|task|train ordinal|cut|
|---|---:|---:|
|disassemble-v3|0|5|
|pick-place-wall-v3|0|5|
|stick-pull-v3|0|5|
|stick-push-v3|0|5|
|disassemble-v3|1|55|
|pick-place-wall-v3|1|55|
|shelf-place-v3|1|55|
|stick-pull-v3|1|55|

顺序按既定五任务的ordinal0→1、task字典序并跳过已接受shelf0得到，未按任何成功结果挑选。下一stick-push ordinal1仍留待后续；其余任务不会从MT50覆盖中移除。按原owner=floor(i/2)%2两值映射A/B，上述均属A。原已接受源ID/seed逐字保留；本包为新增8源给出可审核的独立确定seed/source提案及去重检查，未授权前不创建真实run/shard/claim/cache。

## 交付内容

1. **任务/cut参数化和静态预算**：隔离实现支持以上5任务及cut5/55，实际初始化/状态捕获规则按每任务窄源证据核验；不把shelf的52reset/26000子步直接断言适用于其他任务。可证明的数目和保守上限给出推导，未知具体标明并设置默认拒绝，不能补造已实测兼容。真实状态/MJB资格仍在各自第一个计划parent内检验，不新增诊断轨迹。其余45任务本轮默认拒绝，但总体覆盖计划保留。
2. **有界并发实现**：一个父源绑定一个固定GPU UUID，所有branch/repeat随该父源，不按候选拆GPU。至多8个父源worker；全A波次只由一个外层预约管理8holder，子worker不能重复预约/提前恢复holder。普通父源技术失败停止该父源剩余branch，不补seed；已运行其他父源可按冻结计划结束。共享存储/身份/全局停止等系统故障结束owned wave；任何情况下全部正式子进程退出后才释放预约恢复holder，不能杀无关进程。保留数据发布与计算退出分开的屏障。
3. **容量与吞吐报价**：复用保存的72.29分钟父源及逐阶段数据，给并发1/2/4/8的RAM/VRAM/输出/inode/I/O与上限推导，实测和估计分列，不承诺线性加速。可窄读CPU `/proc/meminfo`、cgroup内存限制及既有节点身份/8UUID快照，不查询GPU/holder，不重做库存或大权重hash。推荐能被现有证据支持的首波并发值；输出总caps为实际父源上限之和加明示调度开销，不能仅乘已成功一例的实际消耗。存储按新波次明示分批额度，原单parent风险接受不能冒充全批quota；本轮不做平台配额工程或预分配大文件。
4. **真实组件CPU组合检查**：小型明确synthetic环境/调度替身，覆盖5任务元数据、两个cut、跨GPU隔离、source不重叠、单worker失败/全局停止、整组退出后一次恢复、重复claim拒绝、并发资源/存储界限、原301阶段合同与公共/sidecar视图。验证真实collector/发布器/调度路径组合，不只自建fake controller；不重跑旧全集。
5. **独立未授权运行包**：新proposal/BOARD/CONTROL/RELEASE模板与唯一真实命令/纯JSON入口同源，run/wave/claim/source列表及包SHA独立。候选task=`A11_COMMON_POOL_BATCH1_V1`、release=`P11_A_COMMON_POOL_BATCH1_V1`。若某候选任务存在不可闭合的CPU阻塞，给逐项清单及可执行子集方案，分析再定，不能自行换成新源或创建计算release。B不参与首波；未来联合波次待B准备完毕另冻结两端退出屏障。

交短REPORT/RESULT/CPU_READY、最小差异、逐源/逐worker资源表、定向检查、未授权提案。既有V4数据、旧train600、历史standalone不重采/不改；不扩大论文实验矩阵。所有新CPU产物保留，本轮不清理。

本轮模型/encoder/候选真实生成/环境/reset/采样、Torch/MuJoCo/driver dlopen、GPU/EGL/CUDA/NVML、holder查询停算、真实launcher/claim、安装/训练/删除均0；纯CPU synthetic操作另账。允许上述必要代码修改/小文件静态读取/CPU资源元数据读取。完成等分析验收，无自动采集。
