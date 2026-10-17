# 首轮 B200 实际五臂开发测评：分析端决定

2026-09-16。首轮训练、固定选模和训练后导出重载已独立复核通过。**条件放行一次既定的100源五臂开发测评**：完成独立prepare/runner接线、通过对应CPU检查并冻结后，执行端即可启动，无需再次等待用户或分析端许可。当前新增授权只覆盖本阶段，不覆盖第二轮、calibration或heldout。

## 1. 所选模型与本次要检验的问题

固定规则选出 B 第200步的四成员集成：旧开发候选库的a0为257/400，预测选候选为275/400，救回24、损害6。B2400同净增益但损害9，故不选；A200净增益+4.0pp，没有越过第一选择条件。所有成员共同构成既定集成，未按结果挑成员。

这个代理尚不能证明新梯度更有效：B200在95个有cut的开发源中选旧post 76次；同库固定旧velocity/direct/post分别为280/274/274次成功，B200选择为275。本次保持预登记B200选择，直接测试它重新生成的velocity/direct/post动作，不因上述描述追加模型、方法或第六臂。

训练后重载检查覆盖95个开发cut的13候选概率和槽0/11动作梯度，成员及集成逐位一致；5个无报警源保留完整分母。所选四成员及预处理均已核实来自B200及其train-only PCA。

## 2. 精确范围与预算

- stage与scope均为 `round1_development_policy`；optimizer updates上限0，simulator attempts上限2100。
- 只使用原100个development primary：env_seed 2026111600–2026111699，五任务各20个不同物理初态，原source/cut和场景身份不变。
- 五臂为 normal native10、replan、velocity、direct、post；每源4个配对后缀，只进行一次报警干预。模型只用上述一个四成员B200。
- 95个有cut源预计各1次独立bank恢复及20分支，共95＋1900＝1995次新尝试。5个无报警源保留已知共同结局：4成功、1失败，各广播4后缀，五臂总体分母均为400。
- 不新增capture、初始化替补、源筛选或训练fallback。缺失/身份不符应报技术错误，不能自动重建另一初态；不把无报警源删除或当缺失。
- 目前simulator累计23479，optimizer累计19200。两类资源分别计数，42679条总账本记录不是42679次仿真。若恰执行1995次新尝试，仿真累计为25474；全工作流simulator硬限50000、optimizer硬限51200不变。失败和合法技术重试保留真实attempt，节约不自动变成新搜索额度。

## 3. 保持原方法语义

保留G0、原首次合法报警cut、native10队列、raw命令接口、一次十步干预、总控制预算300、各方法flow时间点与强度、可行mask及matched规则。最终纠偏命令仍为raw_a0加实际可行delta，normal/replan保持原raw语义。

部署保护只核对身份、恢复、随机流、实际命令和预算。不能新增基于Q或不确定性的接受阈值、半径收缩规则、报警筛选或别的科学参数。原协议已有的退化/fallback须明确记录，不能用未登记的保护行为悄悄改变策略。

## 4. 新模型、新bank与配对证据

- 四个实际加载模型的身份须匹配selected seal与model hashes，不能仅凭配置指向正确路径宣称加载正确。
- 由所选critic重新生成新bank；原13候选bank只用于原raw50 a0、base seed、initial-noise hash、mask及source/suffix provenance核对，不能复用旧guided动作冒充新梯度。
- 在新分支执行前核对原a0及冻结随机流的匹配。方法内各臂使用同一后缀决策索引的配对seed，normal与干预的绝对采样时间差保持原定义。若不能符合该契约，暂停该阶段并说明差异，不能静默换流。
- 原、新bank或阶段间的额外比较，只有原始动作、状态、随机流及协议全部匹配且审计通过时才可称严格配对。主要结论仍以本次五臂内部配对为准。
- 保存实际执行动作、实际delta与幅度、mask/退化/fallback、Q预测和状态恢复证据。真实bank审计核实最终命令的matched关系及尾段恒等，不以名义alpha代替实际扰动。

## 5. 技术就绪条件

新 `policy_deployment_cpu_20260916_v2` 为31项通过，失败的v1归档保留。当前guard已独立检查方法边界；不能把v1到v2描述为只有测试文件变化。尚需将guard接入独立prepare与实际runner，归档完成接线后的必要CPU检查及对应代码SHA。

冻结新的部署配置、代码快照、READY v7、100源清单、原采集和训练/selected模型seal。明确关闭自动capture/替补与未授权阶段，并验证guard是实际入口依赖。原采集v4、预检v5、训练v6的冻结文件全部只读。

GPU工作通过lifecycle，沿已验证的8GPU×4worker配置；波次结束或失败恢复holder。不能因条件授权而在CPU检查未通过、绑定不全或runner未接guard时启动仿真。

## 6. 产物与分析口径

全100槽完成后审计并汇总，报告七项配对：三个A（V/D/post−replan）是本轮主要纠偏诊断；I（replan−normal）解释中断作用；三个T（V/D/post−normal）反映系统总体收益。固定五任务内按完整源等权有放回bootstrap，保留源内四后缀和五臂配对；10000次、seed2026091622、NumPy default_rng.choice直接抽源索引，percentile 95% CI。七项区间未做多比较校正，不能据其中一个过零即宣称独立验证成功。

各项同时给出救回/损害、正负零源，任务成功率及条件cut指标。四后缀不当作四个独立初态；无报警5源保留。方法间比较如附录报告，不变更既定选择规则；总体纠偏目标约+5pp不能由开发代理得分替代。保持原matched公式不要求新旧critic实际半径相同；记录新bank最终命令幅度，不新增跨bank调幅约束。

另外记录新critic对实际生成动作的Q预测与实测差异、可行维度/匹配幅度、零动作和失败/重试、bank/restore/branch耗时。预测Q升高不代替实际成功率。不得按中途成功率停跑、换模型或增加尝试。

本阶段是用于开发与下一轮决策的真实策略测评，使用过选模的开发初态，不是独立held验证。完成后由分析端判断第二轮300训练源的采集与后续训练安排；本次不自动启动下一阶段。

## 7. 固定模型身份与证据

- 模型目录：`outputs/native10_training_20260916/models/round1/round1_fit_v1/`，complete SHA `ff460f12c598a34a15a28ed7619ed071a60be195a3dd2f0c1c963a202ee22287`。
- selected complete SHA：`931c6f6043db92b5d9003eb2833dfc8edd0ab6c860a1979db3983cd7d893725f`。
- 训练后reload SHA：`ce43fc0888f807ef048612ad733795bc1ad5aef24103f0ed89e3c1d51c4beb7b`。
- 开发数据seal：`ff4084fa637fc5c50cbad1ee2010084d7b2658f42902700069b09ec71fdf8865`。
- 分析端：`analysis/round1_trained_selection_review.json`、`analysis/round1_selected_model_review.json`；执行端模型审计：`training_audits/round1_fit_v1_new/`（工作流outputs下）。

精确路径、SHA和阶段权限同时绑定于READY v7。本决定不改训练结果或重新选择检查点。
