# A：真实事件记录器与控制器集成修正（仅 CPU）

task_id=`A10_CAUSAL_EVENT_CPU_REPAIR_V1`；revision=1；owner=A；授权 `releases/P00_CAUSAL_EVENT_CPU_REPAIR_V1.json`。先读当前CONTROL/TASK_BOARD及本release，核对后写ACK。不要重投或重跑旧任务。

## 已验收事实与本次范围

A10_CAUSAL_C10_PREFLIGHT_V1按技术失败验收，见 `manifests/A_CAUSAL_C10_PREFLIGHT_V1_FAILURE_ACCEPTANCE.json`。命令1/claim1/Post attempt1；九次模型初始化和一次语言embedding已发生。首次branch_start的重复branch关键字使真实事件记录器在落盘与reset前失败，Velocity未启动、C10/H20覆盖为空。旧九份计算release均已关闭，不复用余量；已保存异常无运行栈，不能回填运行时traceback。

本次只修复独立新快照的事件接口和异常证据路径，并补足真实记录器与控制器的CPU组合检查。不改数值方法、不重新做库存、不补GPU小探针或handoff实测。无需等待B。

## 最小实现要求

1. 去掉run_branch在branch_start处重复传入的branch；身份统一由真实记录器提供。定向检查所有本控制器emit调用的payload是否与保留字段冲突。保留字段为schema/event_id/event/branch/source_id/parent_source_id/episode_id/split；payload试图覆盖这些字段应明确拒绝，不能以字典更新静默覆盖身份。冲突检查先于写入和事件计数提交，拒绝时不生成半条事件或消耗已写事件ID。
2. CPU fixture须实际调用发布快照将使用的recorder实现，控制器仍为真实run_branch，环境/模型回调使用已有fake。不要另写行为相似但绕过序列化的Fake.emit。可将记录器抽成仅标准库小模块供生产和fixture共用，或提取真实方法并用AST/源SHA证明来自同一实现；不导入Torch/GPU/环境模块或构造真实Engine模型。
3. 在已有定向案例上接入真实JSONL写入/读取：Post与Velocity正常全事件、G0阈值上下及等于0.05、真实与强制标记/强制关闭、prefix不匹配、reset/prefix/C10的提前终止。检查分支身份与source/episode隔离、事件顺序/ID、合法cut、C10实际步数、丢尾与H20剩19等保存结果，早停仅产生已到达阶段。复用既有fixture，不重跑无关全套或P/V数值实验。
4. 增加保留字段冲突拒绝及真实branch_start回归。应先证明旧真实组合的重复键错误可由纯CPU fixture捕获，再证明新组合通过；不调用旧真实launcher。CPU合成输入一律显式标注synthetic，不混入真实实验账本。
5. 在现有异常捕获点当场保存异常类型/消息、traceback、分支和可知阶段，主失败与cleanup失败分开，清理错误不得覆盖主错误。可用一次纯CPU合成异常检查同一保存路径；不为补堆栈执行模型、硬件或真实launcher。旧失败只保留原始证据，不生成追溯性“真实堆栈”。

## 冻结边界

保留六份P/V数值文件、UUID parser、strict loader、D/G0/encoder/Q输入和权重身份、配置/种子/阈值/目标语义；若代码耦合确需多改，只交具体差异说明，不扩大算法范围。成熟残差仍仅诊断，G0仍cut context＋已知next5＋D预测、两成员均值严格>0.05、execute5_then_fixed10目标。真实触发和预定强制工程干预分列。

下一提案仍固定shelf-place H20/cut5/C10、两个固定seed独立新进程顺序回放；同一formal组/锁/全8holder持续预约。Post不完整则停止wave；V可观测prefix不匹配则在干预前停止，匹配也不证明隐藏状态等价。所有数值、早停和C10→H20队列语义保持。上限111项、7采样/70flow/32控制、初始化预算、每child1800+30及handoff名义300保持，不追加采样/预算或改种子凑覆盖。

可准备未来独立 `A10_CAUSAL_C10_PREFLIGHT_V2` / `P10_A_CAUSAL_C10_PREFLIGHT_V2` revision1，新的run/wave/shard/output/cache/claim身份；模板必须UNAUTHORIZED_TEMPLATE、BOARD模板ready（真实release才released），不得创建真实计算release/claim。本任务不授权执行V2。

## 允许、禁止与交付

允许：已保存小文件/定向源码读取、私有快照修正、标准库/fake/AST/shell语法/纯JSON合同检查、小文件hash与差异manifest。实际Torch import/dlopen/CUDA/EGL/NVML、模型初始化/前反向、环境/reset/物理/渲染、真实launcher/claim、holder查询停算/信号、共享安装/daemon重启、训练/删除均0。不hash大权重，不改变公共interface_v1/旧发布包/回执/guard，不自动下一阶段。外部和大权重身份引用已冻结manifest，新真实入口仍需完整SHA守门。

交付新CPU_READY、短REPORT/RESULT、最小DIFF_MANIFEST、真实recorder/controller回归证据、CPU_FIX_HISTORY（保留实际失败）、异常保存fixture、代码/配置/输入/外部manifest；新PROPOSAL、111项预算不变证明、同源BOARD/CONTROL/未授权release模板、唯一真实sh与纯JSON发布检查用法。测试只列实际执行的项目，不用AST检查代替调用组合测试；不要求全仓库整套测试。所有本轮产物保留。

receipt=`receipts/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1_RESULT.json`，package=`results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1`。分析验收后才另决新计算release。
