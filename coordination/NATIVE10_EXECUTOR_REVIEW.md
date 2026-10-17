# Native10 执行准备与协议审查

更新：2026-09-16。本文件是可更新执行说明，P0及主协议目录内的历史快照不改写。P0已完成564/600次：原500加并发复现64，审计通过。首轮300train＋100dev正在冻结READY v4下采集；live READY v5明确允许继续，并条件放行完整静态数据上的零优化器更新预检。正式优化器训练、第二轮及后续测评仍未放行。旧653/700封存只读。动态进度以STATUS为准。

## 已实现的隔离与运行语义

新代码只在 `experiments/native10_training_20260916/`；新输出只在 `outputs/native10_training_20260916/`。`src/corrector`、原ACT-RECAP运行时和旧模型作为只读依赖，新适配器不调用旧采集器的写盘/预算方法。不覆写旧READY、状态、代码或结果。

- 初始reset与所有实际policy queue容量均为10；模型仍生成50。独立raw队列仅承诺前10，不将环境命令注入内部归一化队列。
- 自然边界先更新队列，再旁路监控。age=0不报警；有效中点须剩余至少10步，最后为285。295仍记录G0，不启动截短候选。
- continue_native10在cut5只继续原计划[5:10]，t10自然重采；alarm_replan10/velocity/direct/post在cut5执行新十步，t15重采。后续均native10且不响应新的报警。
- state replay、原raw队列恢复、生成动作与正常队列隔离分别校验；同物理fingerprint不代替队列审查。
- source按自然决策序号取seed；a0及三种引导共用指定候选seed；suffix按episode/cut/repeat/后缀决策序号配对，不含method，不声称正常/干预分支相同绝对时刻采样。
- 注册episode身份、split和cut规则须与清单完全一致，不能通过case_id别名或改变split重复引入同源。无报警、未到达scheduled cut和提前成功均保留。

CPU已覆盖队列、边界、早终止、raw超界命令保留、restore stub、配对后缀、源身份与阶段预算。后续真实native_action/raw前十步队列探针与P0执行审计均已通过；CPU桩测试与真实仿真证据分开保存。主整合及零更新预检接口的检查归档见 `preparation/main_cpu_20260916_v1/`、`preparation/prefit_cpu_20260916_v1/`、`preparation/prepare_fit_cpu_20260916_v1/`。

## 命令处理：已批准并完成P0实测

旧流程的replan及三纠偏都以clip(raw_a0)为执行基准，正常臂则使用raw。MetaWorld实际源码只显式clip XYZ；gripper原值传给do_simulation。仅从这些代码不能证明全四维提前clip与正常执行完全等价。

新适配器保留原始raw_a0；旧匹配器在bounded代理上确定可行delta，再将delta施加到raw_a0。饱和坐标由原边界mask保证delta=0，故不修改原超界raw命令；未饱和的改变坐标直接使用匹配后的候选。这样replan执行raw_a0，三纠偏只增加所声明的可行扰动，实际XYZ/grip幅度与matched_delta相同。零纠偏与raw_a0逐位一致。

critic仍读取同一C/T表示，评分候选须等于最终raw命令映射所得。P0已核对零delta/mask外/tail逐位恒等、实际delta与表示差一致、正反对称，原mask保留0.05边界余量，真实clamp导数不变。五任务loaded actuator limits/disableflags及10对raw/clipped物理探针均通过；所测三步窗口物理效果一致，data.ctrl差0.5保留。结论仅限当前后端和已测状态，不宣称普遍物理等价。正式臂保留raw接口，历史跨版本诊断仍用原native50与bounded方案。完整证据见 `NATIVE10_RAW_RESTORE_EVIDENCE.md`。

## 注册与预算

按后续EVAL20修订登记P0 20、train600（300+300）、development100、calibration100、heldout100；五任务均衡。train/dev每源4后缀，cal2、held4。主900槽及有序初始化替补见 `preparation/main_registration_v2/`。物理初态指纹不含RNG/seed/time；只允许首次动作前的重复场景/初始化失败按预登记替补，不按结局换源，held初始化须待最终策略冻结。当前仅首轮400主槽采集中。

训练cut采用50/50：每轮每任务30首次报警，scheduled15/45/95各10。LEAD固定fallback已经实现并冻结：15→5、45→15→5、95→45→15→5；无合法报警仅train可按15→5选择。只从已到达、非终止且余至少十步的合法cut按固定序列取用，不看结局/Q/反事实收益；无合法cut保留episode和原因。dev/cal/held无报警保持正常native10共同结局与完整分母。source和collection summary均保存requested/actual cut、reason、category。

预算历史：TASK47600＋2400储备，经RAW_BUDGET补1000独立bank变为48600＋1400；EVAL20再增100capture＋100bank，当前为 **48800计划＋1200储备＝50000硬限**。新账本与旧700独立。阶段上限依次为P0 600、首轮标签23200、首轮开发2100、第二轮标签17400、第二轮开发2100、cal1200、held2200。权限以当前READY及对应阶段冻结为准；不能将未放行阶段映射成P0/CPU权限。

主阶段独立bank恢复已明确拨1100：首轮标签400、首轮开发100、第二轮标签300、第二轮开发100、cal100、held100。branch内部restore归已计branch，不重复计；P0的独立恢复含在其600内。失败、重试、独立probe逐项入账，G0新cut/额外仿真需单列协调，不能暗用假设节约。逐阶段capture/bank/branch表见 `NATIVE10_RAW_RESTORE_EVIDENCE.md`。

挂载历史不支持flock，新预算互斥锁在 `/tmp/corrector_native10_training_20260916_budget.lock`；账本仍在新输出。产物使用独占创建，不依赖挂载hardlink。失败attempt不回收、不删除；失败源必须保留计划身份，由执行入口写明错误及已消耗额度，不能换seed。

## 吞吐与磁盘

P0的400分支均值5.789秒、P90 10.098秒；轻量已审产物39.046MiB。32-worker探针通过完整轨迹复现且无OOM，支持冻结8GPU×4worker、模型常驻；加载均值174.366秒，加载后32个bank＋branch工作对跨度22.946秒。短探针不等于13候选稳态负载，也没有实测8-vs32吞吐增益。

首固定50训练源已真实执行13候选＋normal、各4次共2800分支，并通过审计：branch均值8.736秒、P95 16.406秒，bank均值2.476秒、branch restore均值1.064秒，轻量产物263.199MiB。总墙钟外推需另计加载、capture/bank、长尾、审计及训练，不能将累计worker秒当墙钟。旧资源估计是历史准备材料，不是实测全流程成本。

P0及并发的加载、source、restore、bank、后缀和产物成本已分别保存，未测的整波NVML峰值/RSS/PSS不得冒称已测。正式GPU均通过lifecycle，整波结束/失败恢复八卡holder。

详细证据：`experiments/native10_training_20260916/RESOURCE_ESTIMATE.md` 与 `outputs/native10_training_20260916/preparation/resource_estimate.json`。

## 当前下一步

- P0及旧两正例＋4005中性例诊断已完成，13候选P0预览没有rollout标签；不从P0选训练赢家。
- 等首轮400主槽全部终态，完成静态train/dev审计与seal；增长中的live bank或小批smoke不代替正式输入。
- 按READY v5独立冻结零更新预检，完成train-only PCA及八成员初始化/重载审计，再交分析端审查正式训练放行。当前真实PCA和优化器更新均为0。
- 阶段完成/真正阻塞写短报告、STATUS并直接queue分析线程；常规工程自主处理，方法/数据/阶段变更由分析端判断。

运行与完成状态以 `coordination/NATIVE10_EXECUTOR_STATUS.json` 为准；此审查不把准备完成等同P0或主实验成功。
