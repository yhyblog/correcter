# MT50 R补齐：B/C独立并行（2026-09-22）

用户明确新增H=20、30、40、50的R扫描，并要求交给B、C加速。此文覆盖旧`MAIN_ONCE_CONTINUATION.md`中“不新增四个H的R”这一范围限制，原已完成结果仍不重跑。

| 节点 | 独占任务 | 新单元 | 数量 |
|---|---|---|---:|
| B | B_D24_R_H20_H30_V1 | R_H20、R_H30 | 各500，共1000 |
| C | C_D24_R_H40_H50_V1 | R_H40、R_H50 | 各500，共1000 |

各节点八卡常驻独立worker、有限后台队列，两格自动续跑；节点间没有执行/退出屏障。A现有LIBERO任务不受影响。B/C不是复现外部方法，按本方法优先执行。

## 科学合同：直接复用A主表的R实现

- 同一π0.5-MT50 SFT030000、预处理/norm、冻结D/G0（241/242、341/342）、语言及环境包装。输入身份以已完成A主表为准，不重新选模或拟合。
- 原500源：`deadline_20260924/A/config/TEST_SOURCES_V1.json`，50任务各10、ordinal0..9、repeat0。原env_seed、policy_seed逐源照用；不采新初态，不复用已揭晓20源。
- 复用`results/A/A_D24_MAIN_ONCE_V1/code/`与`config/CONFIG.json`、`NUMERICAL_BINDING.md`里的**实际主链**，在各自私有包改节点绑定、输出路径、method/H列表和当前holder策略。不要执行原A的START_MAIN.sh，不复制其claim。
- 原生raw50/NFE10；H只取本节点两值。自然采样沿A/N逐episode CUDA generator；candidate仍按`D24_designated_a0`、source_id、policy_seed、absolute_cut派生，独立于自然流，与主表相同，不能恢复pilot的legacy自然seed规则。
- 成熟D5/实时G0，每5步检查、阈值0.05、总干预帽1、原合法cut及历史条件不变。不同H自然形成不同轨迹/cut，不强行借用H10的报警时刻。
- R触发后只生成普通新计划，承诺执行10步，丢弃其余尾部，恢复该格native H。无动作纠偏、无Q选择门、无额外冷却、无强制触发。未报警和提前成功都保留在分母。
- 固定总预算300控制步、30Hz控制/400Hz物理、动作尺度0.015、corner2 480×480、相同终局success口径。**禁止使用B/C此前Smol/X的80Hz/0.01环境或Mesa/OSMesa渲染替代主表NVIDIA EGL。**
- 必要移植仅限B/C本机UUID/PCI、NVIDIA535隔离库搜索与节点runtime/输出。两机已有H100/535身份；实际GPU/renderer身份由第一批计划R任务自身记录。没有单独GPU预检、不跑N/R_H10对照、不要求跨机逐位动作/RGB或完整状态一致性证明。若同协议渲染无法运行，记录具体阻塞和未完成源，不能静默换renderer形成可合并的主表。
- 旧A数值配置可能保留历史matching描述，实际执行以A主链R路径为准；不因此恢复共享半径、全部候选生成或改变已完成算法。

## 已授权范围与执行

授权`R_H_SWEEP_AUTHORIZATION_V1.json`同时包含必要实现和正式评测；不再分CPU_READY后等待第二次放行。每节点计划1000首次评测、最多1100真实attempt（包含失败）；只有明确修复后的失败源允许一次纠错重试，已完成源绝不重算。阶段/节点累计额度同时生效；未进入额度不产生额外实验。optimizer/SFT/新数据采集=0。候选噪声和正常R采样属于这2000条正式评测，不是新增开发任务。

仅做必要的源表、模型/动作单位、有效观测和异常处理检查，首条正式episode直接计入评测。无需重复大权重hash、旧全套测试、百万事件审计、MJB或逐帧证明。若启动/发布错误发生于科学调用前，保存失败原因、做必要修复并继续同一任务的未完成部分；不把启动修复当新科学机会，也不无限重复启动。

两端使用自己的唯一claim、host/UUID、进程组和formal.lock。正式波内所有holder停算（包括加载、空隙和提前结束卡）；整组及后代退出后恢复8holder，失败也恢复；不杀无关进程，不用旧A的尾卡辅助holder。稳定执行且终局事件登记后结束LLM轮次，后台队列自动完成并唤醒各自原线程。若收到重复派单，只核对既有claim并续读，不再次启动。

## 交付和论文更新

各自输出`results/{B,C}/{task_id}/`及`receipts/{B,C}/{task_id}_RESULT.json`，保存：

1. 每格成功/有效/技术失败/未启动数量及50任务分表；逐源source、env/policy_seed、H、终局success、结束步、实际干预数/cut、调用/flow及既有计时。
2. 小型实际协议说明（checkpoint/norm引用、renderer/GL、30/400Hz/0.015、H/C10、once、source表、进程退出）。记录跨主机运行，不声称耗时严格同机可比。
3. 直接与已完成同H的N/Post/Velocity按source配对，给R−N、Post−R、Velocity−R及救回/损害；复用主表固定任务内bootstrap2000次/seed20260921口径，不能从test选择模型/阈值。已有主表数值不改。
4. 先保存各完整格，再交总回执。分析端填充`Corrector/docs/EXPERIMENT_RESULTS_MASTER.md`，主矩阵从已完成16格扩为计划20格；新格在终局前留空。

截止沿原北京时间9月23日20:00停止新增实验、23:00交表图。正常任务不等其他节点，也不等待历史成功率口径分析结束。
