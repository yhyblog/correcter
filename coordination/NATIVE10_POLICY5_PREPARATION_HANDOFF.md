# 首轮 policy5 部署准备交接：实现检查与科学规则分界

2026-09-16。正式A/B训练已完成：20:09:19 UTC启动、20:23:58模型封存，19200优化更新、新仿真0。固定开发银行规则选B200，训练后95 reached源概率/动作梯度重载和独立产物审计通过；100计划分母含5个无报警共同结局。早先6372更新回执为中途快照。当前READY v6仅释放正式训练，本文不释放或启动policy5。

## 部署范围与算法保持项

只加载固定规则选出的B200四成员critic；VLA、D、G0与既有执行实现保持。100个原开发初态每任务20个，复用95个原报警cut及5个无报警共同结局（4成功1失败）；每个有cut源五臂×4重复，无第六臂。每臂总体分母为100×4，四后缀不是四个独立初态。

五臂为continue_native10、alarm_replan10、velocity、direct、post。episode起始native10；normal在cut后完成当前原10步队列的剩余命令，再自然native10；另外四臂使用新动作10步prefix，再fixed10后缀，总控制预算300。G0阈值仍0.05，固定首个合法报警cut，不引入部署fallback、重新触发或新阈值。

raw a0原样保留；仅可行mask内叠加delta，不添加二次clip。critic仍使用同一C(raw)=clip(raw,-1,1)表示，固定state及指定a0，仅候选求导。Flow的alpha=10，时点0.3/0.2/0.1；velocity/direct公式、真实clamp导数、post的S²梯度度量均沿用。没有新增Q阈值接受门、回溯、依结局丢弃、择优重试或按收益选源；原GuidanceError数值fallback及其记录沿用原实现。

XYZ RMS目标0.05/Linf上限0.15，grip RMS目标0.10/Linf上限0.40，边界余量0.05、tolerance1e-6，原common feasible radius与zero-group规则保持。原构造器仍生成reverse/random方向用于共同半径依赖，但它们不构成部署rollout臂。13候选训练生成器中的XYZ/grip正反、half/full随机、reverse-post局部标签臂不进入policy5。

保持相同matching配置不等于要求新旧critic产生相同实际可行半径：梯度方向变化可改变原公式计算的共同半径。**没有新增跨critic/跨bank半径相等约束**。新五臂内部的三种纠偏仍由原matched构造器保证同组RMS，最终raw命令的mask/tail/C映射及RMS/Linf另外重算留证；新模块目前没有额外的三臂RMS相等断言或调幅步骤。实际新bank尚不存在，不能预先宣称其物理执行/同幅核验已通过。

## 新增保护属于实现检查

| 检查 | 行为与边界 |
|---|---|
| 加载与模型身份 | 绑定训练总seal、selected seal、四成员SHA和真实selected_reload_audit；加载唯一选定critic，不再选checkpoint。 |
| 输入身份 | 绑定原config/freeze、100份source/resolution、95个旧bank，核case、cut、scene、模型和namespace；缺源直接报错，不自动capture/替补。 |
| 执行命令 | 新bank首branch前比较旧新raw50 a0、噪声与mask；核float32有限值、tail和mask外恒等、C(raw)与实际候选一致；只校验，不改写候选。 |
| 恢复与封存 | 原MainCollector负责restore与队列执行；独立审计核trajectory的原prefix、物理状态、实际raw prefix及自然后缀。 |
| 预算与阶段 | 独立round1_development_policy scope；仅允许已注册bank和五臂branch，不允许capture/替补/优化；单分支内restore已含，不重复计。 |
| 结局汇总 | 五无报警源保留共同结局；缺失/未知触发审计错误，不能填失败或丢分母；保存逐repeat结局，便于复算救回/损害。 |

预期新增95个独立bank restore＋1900个branch＝1995 attempts，阶段上限2100，global50000不变。尚余阶段空间不作为追加比较/第六臂授权。任何技术失败保留日志与计数，不按成功/Q改变source、cut或参数。

## 旧round1_labels与新policy5的随机流

namespace保持 `corrector_native10_training_20260916_v1`。

| 随机用途 | 冻结seed输入 | 新旧关系 |
|---|---|---|
| 原episode自然策略 | source_natural_decision＋task/env_seed＋自然决策索引 | 复用旧封存source，不新增capture。 |
| 指定a0/flow初噪声 | designated_a0＋task/env_seed＋cut＋candidate_index=0 | 不含critic、臂名、bank版本、worker或repeat；预期同流。V/D与replan同初噪声。 |
| 匹配随机方向 | matching_random＋task＋env_seed＋cut | namespace不变即同方向随机流；只作为原共同半径构造依赖，不另跑随机臂。 |
| 配对后缀 | branch_suffix_decision＋task/env_seed＋cut＋repeat＋decision_index | 不含critic、臂名或bank版本；每repeat独立，同repeat同决策索引共享噪声。 |
| branch执行次序 | main_branch_order＋episode_id＋cut＋bank_version | 新bank版本使执行排列改变；模型抽样使用上面显式keyed seed，不使用此排列RNG。 |
| 旧13候选额外随机探针 | main_local_labels_v1＋episode_id＋cut及SeedSequence子流 | 仅旧局部标签探针使用，不引入新五臂。 |

实际静态重建已检查全部100dev：95个旧a0 seed及replan/V/D noise一致；1900份旧五种对应臂summary中的24187个实际suffix记录均符合上述suffix函数，并核同repeat/decision_index噪声一致。旧labels13的V/D/P raw50计划逐位等于其原formal matched计划，没有在13候选生成时再次归一化。

这证明旧记录符合拟沿用的函数，并不证明尚未执行的新bank已复现。新生成时guard必须检查实际raw a0和噪声；新branch审计必须检查实际suffix seed/noise。normal与中断臂的后缀绝对起始时刻可以不同；配对单位是同源、同repeat、同决策索引，不是相同绝对控制步。

**主要效应报告只比较新五臂内部配对**。若实测旧新后缀不一致，不把跨轮成功差当成配对效应，不增加oldcritic第六臂。相同source/a0本身不足以证明跨轮后缀已配对。

## 单列待分析端冻结的统计实现默认值

以下已经写成可测试汇总代码，尚未随正式policy5配置冻结；CPU测试通过不等于分析端批准这些统计细节：

- 七个描述比较：I=replan−normal；三个A=V/D/P−replan；三个T=V/D/P−normal。
- 五任务内按整episode/source等权有放回bootstrap；源内4后缀、五臂保持配对；10000重采样，seed2026091622，NumPy default_rng.choice直接抽源索引。
- percentile 95% CI，不做多重性校正；正/负/零源按源平均配对差分类。七比较主次及多重性解释由分析端明确，不由执行端新增成功判据。
- 保留全100源总体与报警条件/逐任务分层。无新增Q接受阈值、收益阈值搜索、半径选择或样本剔除；用户约+5pp的真实纠偏目标不由离线开发选模成绩替代。

## 证据、入口与尚未执行项

保护模块：`experiments/native10_training_20260916/policy_deployment_v1.py`。只读汇总模块：`policy5_audit_v1.py`。31项合成CPU测试通过，证据 `preparation/policy_deployment_cpu_20260916_v2/`；旧v1的准备期语法/fixture失败日志保留，未修改冻结依赖，未发生仿真或优化。

新正式prepare/config/READY及runner尚未创建/绑定；旧main_runner不会自动使用新guard。未来独立入口须显式调用 `create_policy_collector` 与 `collect_existing_slot`，冻结加载/输入/阶段身份后才走lifecycle启动。本文及静态seed核验都没有加载真实模型、创建环境、生成新候选或运行新分支。

精确封存（路径相对 `outputs/native10_training_20260916/`）：

| 产物 | SHA256 |
|---|---|
| `models/round1/round1_fit_v1/complete.json` | `ff460f12c598a34a15a28ed7619ed071a60be195a3dd2f0c1c963a202ee22287` |
| `models/round1/round1_fit_v1/selected/complete.json` | `931c6f6043db92b5d9003eb2833dfc8edd0ab6c860a1979db3983cd7d893725f` |
| `models/round1/round1_fit_v1/selected_reload_audit.json` | `ce43fc0888f807ef048612ad733795bc1ad5aef24103f0ed89e3c1d51c4beb7b` |
| `preparation/policy_deployment_cpu_20260916_v2/complete.json` | `791db4b5a52fc904260c7d86ef29b9791bf1eec123574992f3f23a537810cfa5` |
| `progress_audits/policy5_seed_review_v1/complete.json` | `55990abc225e71272b6bc208c23f05851683170b7df67d683e05948f99ac0146` |
| `progress_audits/policy5_seed_review_v1/result.json` | `a4bc2f6a0196e81187806f9ddd96c33262299174402cd14fbb9781ca79800139` |

静态seed复现命令与执行日志：`preparation/policy5_seed_execution_v1/`，可复现代码 `experiments/native10_training_20260916/policy5_seed_review_v1.py`。完整训练交接另见 `coordination/NATIVE10_ROUND1_TRAINING_EXECUTOR_HANDOFF.md`。
