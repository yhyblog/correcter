# Batch3：复用已验收MT50采集器的CPU参数准备

task_id=`A11_BATCH3_PREP_CPU_V1`；revision=1；owner=A；release=`P00_A_BATCH3_PREP_CPU_V1`。先读最新CONTROL/TASK_BOARD/DISPATCH_A核对身份并写ACK。本任务只准备下一未授权包。

Batch2已验收关闭：新增8配对train源，累计16配对train/dev0，已处理17/500，另1源为此前p04 cut前成功的normal-only；剩余483未执行槽。以 `manifests/COMMON_POOL_ACCEPTED_PARENTS_V3.json` 与 `manifests/COMMON_POOL_SOURCE_DISPOSITIONS_V2.json` 为准。原Batch1/2 raw日志、前版索引及14个已消费计算release不改、不复用、不补p04。

下一批保持固定8源、并发2。沿用任务名ASCII顺序中尚未处理的A/train ordinal0/cut5槽，确定为：coffee-button-v3、coffee-pull-v3、coffee-push-v3、dial-turn-v3、door-close-v3、door-lock-v3、door-open-v3、door-unlock-v3。按已有确定性seed规则提出source与seed；即使某任务未来实际资格失败也不改cut/换seed/补源。此名单是原计划的继续，不按结果、标签或任务快慢挑选。

仅交四项增量：

1. 复用 `results/A/A11_MT50_CONTINUATION_CPU_V1/config/MT50_TASK_TABLE.json` 及其冻结源证据、数值代码、typed state协议、scheduler和直接mj_step hook；不重新审查50任务/45源码、不重复库存、表证明或旧89/133/185套。引用Batch2 box-close实际计量证据，不能说door-lock已实测。仅为新8任务生成CPU配置/确定seed/元数据/逐parent计量预算；door-lock的静态直接mj_step额外520/attempt要正确计入，其他任务按原表，不统一套shelf。
2. 独立 `A11_COMMON_POOL_BATCH3_V1 / P11_A_COMMON_POOL_BATCH3_V1` 未授权提案，保留原116操作向量+调度aux、每parent15顺序cold、同组同锁单预约、固定UUID与8holder整波退出/发布后恢复。只改必要任务身份/path及config绑定，不实现跨branch模型复用、扩大并发、改变动作/噪声/终局/标签/容差或重构调度器。若确有必要代码变化，单列窄理由与diff，未知按原门拒绝，不临时降级。新run/wave/shard/output/cache/command/claim均独立，仅元数据提案、不创建真实路径。
3. 对真正改变路径做小型CPU验证：V3索引和V2处置精确排除17槽（含normal-only）、固定8名称/seed/owner/cut/UUID、resource逐项合计、CONFIG301观测phase、同源完整CONTROL/BOARD ready与UNAUTHORIZED_TEMPLATE、独立 `bounded_batch3` 风险缺失拒绝和既有关闭release拒绝。若科学/初始化函数字节相同，引用已验收fixture与SHA，不重跑旧数值/渲染/状态/调度全套。只使用标准库/NumPy的显式synthetic数据；真实操作0。
4. 更新满120分支的参数化时间/存储报价，保留按阶段timeout与未知项。引用已保存Batch1/2时序，不用37/83终局比例压缩本批上限，也不外推GPU秒或线性加速。仍保持并发2及原受控writer/log/cache范围，引用最后保存容量证据时注明不是当前项目quota；不新增容量/硬件/holder或进程探针。本批风险必须独立决定，模板accepts_monitoring_gaps=false，不能继承Batch2合同。没有新GPU验证报价；实际新任务的初始化/full-state/MJB资格只在未来计划parent内检查。

500源计划、owner与cut规则不改。当前8都是A/train0；未来dev在第一次发布前需冻结“实际任务名→task ordinal→owner”显式映射及SHA，不把wrapper ID/字典index/语言index混用。本任务不用为此重算或冻结dev，只保留已知区别。

禁止实际Torch/MuJoCo/dlopen/硬件/NVML/holder查询停算/环境/reset/模型/encoder/采样/梯度/训练/真实launcher/claim/安装/共享包改动/删除/大权重hash，也不重新hash14.5GB运行产物。B任务仍独立，不改B/CONTROL/TASK_BOARD/dispatch，不向B会话发命令。

交CPU_READY、短REPORT/RESULT、精确diff、元数据验证和完整引用manifest；只交一个上述固定8/并发2的未授权Batch3包。完成后停止，等待独立计算release，不自动采集、训练或评测。
