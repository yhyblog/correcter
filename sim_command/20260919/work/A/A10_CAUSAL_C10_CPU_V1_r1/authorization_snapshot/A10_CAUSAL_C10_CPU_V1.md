# A：合法 cut 的因果触发与 C10 闭环集成准备（仅 CPU）

task_id=`A10_CAUSAL_C10_CPU_V1`；revision=1；owner=A；授权 `releases/P00_CAUSAL_C10_CPU_V1.json`。先写ACK。仅准备代码/接口/预算，不运行环境、模型、GPU或新的占卡交接。

## 已完成与本次目的

原生有限预检与单缓存step0的P/V数值路径均已验收。最近验收见 `manifests/A_PV_OFFLINE_PREFLIGHT_V3_FINAL_ACCEPTANCE.json`；八份旧计算release和一次安装release均已关闭，不能复用额度。Post/Velocity自身半径/raw约束通过，不代表D/G0触发、合法cut历史、真实C10执行或恢复nativeH已经验证。

下一步仅准备一个小规模**工程集成预检**，补齐以上缺口；不新增论文实验矩阵，不增加step0 sweep，不据单样本Q增益改算法/阈值/引导强度或加Q接受门。不执行共同池批量采集、训练、全任务评测，不等待B即可做本CPU准备。

## 最小目标场景与接口

优先沿用已冻结shelf-place开发环境/底座/种子作为一个固定诊断来源，H=20、C=10、monitor stride=5、至多一次干预、episode上限300。选H20是为了显式验证C10结束后恢复H20，而非误回H10；无需本次再测所有H。

计划在首个合法cut=5检查：非自然刷新、age>0、旧队列余量>=5、剩余控制预算>=10、未先终止。若提前成功/终止或cut实际不合法，记录原因停止对应路径，不换seed/任务凑样本。不得把已完成step0离线样本冒充合法报警点。

必须准备真实因果prefix、实际执行动作与逐步观测的对齐关系：D对将来观测的预测只用当时已可见信息；到cut才形成对应残差及G0输入，不能用cut后帧/同episode未来动作泄漏。冻结既有D/G0 checkpoint/encoder/normalizer/阈值与训练目标语义；历史五任务权重只作该开发场景兼容检查，不冒充MT50适配。D/G0收益目标仍为既定5步承诺/后续native10，不为C10诊断改成G10或换标签。

在同一个cut上，优先准备同prefix/同环境与RNG状态的P、V两个短后缀分支，各执行C10，再丢弃未执行尾部、恢复nativeH20采样，最多额外执行首个恢复动作以核验队列余量19。若终止较早，按真实terminated/truncated/success终止，不强行执行满预算；分清首次成功与环境终止语义，不将本短诊断计入完成任务样本。

复用prefix只能通过真实完整状态恢复实现；需覆盖MuJoCo/环境隐藏量、RNG、elapsed/time-limit、wrapper/动作队列及所需policy状态。若现有后端不能可靠恢复，明确缺口并报价两次固定seed独立prefix回放的有限替代路径，不能把仅qpos/qvel、几张图或train600轨迹当成完整可恢复状态；本CPU任务不凭空实现并宣称恢复等价。

初始期望是一个真实prefix加P/V两个短后缀，不补R/N对照rollout、不采其他源。没有完整rollout、成功率或性能排名结论，末态仅工程产物。不能可靠执行两分支时，报价最小可验证顺序和原因，由分析决定实际预算。

## 触发和分支执行的区分

D/G0的真实输出、既有阈值及是否触发必须保存，不为了走到P/V而改阈值。若该固定cut不触发，仍可在单独标记的“预定cut强制干预工程诊断”模式报价P/V后缀，以验证执行/恢复接口；这个模式不冒充完整方法触发、更不是收益触发有效性样本。普通触发判定与强制执行标记应独立、明确可审计。不要实现或测试额外异常触发器，本轮不做E6对照。

继承三套独立算法及部署口径：Post1次新完整采样；Velocity锚点新完整采样＋guided共2次，末3步动作梯度；固定锚点、独立自身半径、无Q接受门。若诊断共享缓存a0/特征/噪声或prefix，单列节省的诊断调用与原部署口径，不伪装为部署成本。只基于实际因果cut重新构建特征，不能拿step0的Q特征或step1未来观测直接替代。

## 必须交付的具体准备和报价

1. 数据/状态时序小表：每一步可见观测、已执行动作、D预测时点/对齐目标、G0输入/决策、P/V新计划/C10承诺/尾部丢弃/nativeH20恢复；标明每项真实输入来源和缺口。只定向读取接口及必要短函数，不盘点全仓库。
2. 新不可变代码/config/input/external manifest、明确差异和小范围CPU fake检查。继承已验收原生EGL隔离映射、Torch UUID、strict loader和P/V数值实现；不要自行把不同旧快照混拼成已验证整体，清楚列集成变化。
3. 精确资源提案：初始化环境/wrapper/taskset/reset_model/物理settling另计，prefix/分支恢复或回放/控制步/render读回/encoder/D/G0/Q/flow/动作梯度逐项计量；列派生计数别名，不重算成额外调用。若恢复会隐式render/forward/reset也须列入。以实际后端为准，不照抄旧52reset或推断固定次数。
4. 未来一个A-only wave，已装guard新SHA及显式handoff300、同formal.lock/全8holder直到整个进程组退出、成功失败恢复、不杀无关进程。已有成功empty-app原始poll未保存的限制保留，不补探针、不为本CPU任务再修改共享guard。未来正常日志能记录什么据实说明，未知值null。
5. 新纯JSON发布检查、同源BOARD_TASK_TEMPLATE ready、未授权RELEASE_TEMPLATE、CONTROL_REQUIRED、唯一真实命令、最大次数/各阶段timeout、RAM/VRAM/磁盘报价、完整失败回执。建议未来task=`A10_CAUSAL_C10_PREFLIGHT_V1`、release=`P10_A_CAUSAL_C10_PREFLIGHT_V1`，当前不创建真实release或claim。

公共interface_v1继续不变。新真实transition/事件需明确parent/source与开发用途，实际多事件不被一次干预摘要限制；私有诊断元数据/公共UUID事件账本边界保持，不把父子整数event_id直接拼成公共流。产物未来可为A11接口提供小样本，不能把本诊断冒充完整共同训练池。

## 当前零计算边界

仅静态/小元数据读取、私有编辑、针对集成变化的CPU fake/AST/shell检查。Torch/驱动导入或dlopen/NVML/CUDA/EGL、环境构造/reset/render/物理、模型/梯度/训练、真实launcher/claim/holder查询停算、共享安装/重启/删除均0；不重新hash大权重，不重跑旧全套或成功V3数值。准备失败报告具体缺口，不静默改变算法或增加预算。

交本任务短REPORT/RESULT、CPU_READY、时序/状态恢复证据、预算与提案。此阶段不要求实测成功；分析审阅后才决定新的单次计算release。所有证据保留，B原CPU任务不变。
