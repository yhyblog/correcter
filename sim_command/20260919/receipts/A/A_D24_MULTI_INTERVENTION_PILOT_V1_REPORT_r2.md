# 旧20初态 once/multi pilot r2 执行交接

固定 disassemble-v3 旧20源，repeat0，无新增初态。用户已在本 A 会话明确授权；使用 MULTI_INTERVENTION_AUTHORIZATION_V2。隔离包复用已运行成功的常驻模型/原生 EGL/同锁监督组件，旧包与回执未改。

科学实现复用原 Native10Queue、seed 函数、A4000 FrozenObjective、FlowHook 和 project_solo。H10、C10、每5步监测、成熟历史、G0>0.05、合法非边界 cut、300步及提前成功不变。仅 multi 总干预次数无限；承诺段不再次干预，执行满 C10 后恢复普通监测。无冷却、强制触发、Q接受门或方向/半径修改。

旧 standalone 的正式启动配置固定 Mesa llvmpipe；本机已验证入口为 NVIDIA EGL。旧 once 的观察/首报警流与新 online 入口不能直接合并作配对结果，所以本次在新入口补必要 once 对照。旧 repeat0 60份摘要作为独立历史参考保留。六组各20，最多120条计划样本，优先R/Post四组，Velocity随后自动衔接。不重复旧归档的物理命令/claim，不修改旧结果。

7项针对新增真实 controller/queue 的 CPU fake 组合检查通过，包括 once=1/multi=20、C10锁、历史成熟、真实JSON序列化、共用seed、提前成功、严格阈值和s300、120份身份与AST。首次CPU导入暴露旧controller同名冲突，已在真实启动前固定私有code的搜索优先级；不涉及GPU失败或额外试验。

N2500已全部完成并完整退出，技术失败0；每组500中H10/20/30/40/50成功308/240/205/205/196。pilot未中断N。八张holder已先按N完整退出恢复，pilot正式开始后经原guard全停；整组锁持续保留到所有子孙退出及数据发布，期间不补闲置子集holder。

pilot supervisor已脱离会话，8 worker已启动并处于模型加载。DAEMON_READY和heartbeat是实测进程证据；当前不预记新样本成功。首张R/Post表写 PRIMARY_RESULT.json / LIVE_TABLE.md；所有组写 SUMMARY.json。完成事件后台通知原A会话，分析投递仅证明queue收件。
