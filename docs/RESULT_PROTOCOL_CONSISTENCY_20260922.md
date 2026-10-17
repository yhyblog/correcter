# 历史成功率与当前主表：口径核查及R补齐

2026-09-22。这里只读已有结果、配置和必要窄实现语义，不重跑已完成样本。新增计算仅用户明确要求的四格R。

## 0. 最先纠正的文献数字

VLA-Corrector原文Table 4的π0.5基线，执行H10为**64.50%**，H50为**48.72%**；不是H10只有40%多。我们当前H10为61.6%，并没有异常高过该文献H10报告值。论文Table1的48.70%和Very Hard单组41.0%不能替代H10全任务结果。[原文Table 4](https://arxiv.org/html/2607.01804v1#S4.T4)

这不等于证明我们实现无误：论文checkpoint、聚合权重和物理协议未全部与本地对齐，绝对数值只能作为口径定位；本地旧42%与当前五任务56%的剩余差异也没有被单因素分解。

## 1. 为什么B、C各1000条

每个H：MT50全部50任务×每任务10个原有固定test初态=500评测回合。B跑R_H20和R_H30，共1000；C跑R_H40和R_H50，共1000。两端合计2000个新的“方法×H×源”回合，但只有原主表的500个初态身份，新增初态和训练数据均为0。这不是每任务1000条，也不是重新跑N/Post/Velocity。

各格任务如下（均为MetaWorld v3，每个任务10源）：

```text
assembly-v3, basketball-v3, bin-picking-v3, box-close-v3, button-press-topdown-v3
button-press-topdown-wall-v3, button-press-v3, button-press-wall-v3, coffee-button-v3, coffee-pull-v3
coffee-push-v3, dial-turn-v3, disassemble-v3, door-close-v3, door-lock-v3
door-open-v3, door-unlock-v3, drawer-close-v3, drawer-open-v3, faucet-close-v3
faucet-open-v3, hammer-v3, hand-insert-v3, handle-press-side-v3, handle-press-v3
handle-pull-side-v3, handle-pull-v3, lever-pull-v3, peg-insert-side-v3, peg-unplug-side-v3
pick-out-of-hole-v3, pick-place-v3, pick-place-wall-v3, plate-slide-back-side-v3, plate-slide-back-v3
plate-slide-side-v3, plate-slide-v3, push-back-v3, push-v3, push-wall-v3
reach-v3, reach-wall-v3, shelf-place-v3, soccer-v3, stick-pull-v3
stick-push-v3, sweep-into-v3, sweep-v3, window-close-v3, window-open-v3
```

原始清单：[TEST_SOURCES_V1.json](../sim_command/20260919/deadline_20260924/A/config/TEST_SOURCES_V1.json)。[BC独立派单与固定协议](../sim_command/20260919/deadline_20260924/R_H_SWEEP_SUPPLEMENT_V1.md)。

## 2. 旧42%与当前61.6%


本次只读既有小报告、配置、2500行旧结果和50行当前任务表；没有GPU、重跑、模型加载或重新hash大权重。

## 可确定结论

1. 用户记忆中的42%有精确来源：旧五任务held100/standalone的N=168/400。它不是MT50全50任务均值。当前61.6%为全50任务、每任务10个新test初态、每源一次，N=308/500。
2. 任务组成不是全部解释：当前抽回相同五任务，N=28/50=56.0%；因此只能描述当前样本任务组成从56.0%变为61.6%的5.6pp，旧42%到当前同五任务56%的14pp仍混有初态/策略噪声/渲染/续跑统计协议差异，不能分解其因果贡献。
3. 找到另一份历史完整MT50评测：1931/2500=77.24%，并不是40%多。此旧报告H=50指生成长度，K=10指执行长度；当前报告H=10指执行长度，不能把相同字母H直接对齐。该旧MT50的物理步长也不同。
4. 未发现旧42%与新61.6%由更换底座权重或归一化文件所致：保存身份均绑定π0.5 MT50 SFT030000、同权重SHA和同normalizer SHA。相同权重不代表两版执行器或图像相同。
5. 因而现有证据不支持把数字上升当作模型突然提升，也不足以宣布绝无实现问题；应在论文中分开三套评测口径，用同一当前协议内N/R/P/V比较。

## 同五任务对照（当前不重跑，只重聚合已存任务表）

| 任务 | 旧N（每任务20初态×4续跑） | 当前N（新10初态） | 当前R | 当前Post | 当前Velocity |
|---|---:|---:|---:|---:|---:|
| disassemble-v3 | 65.00% | 10/10 | 9/10 | 10/10 | 10/10 |
| pick-place-wall-v3 | 37.50% | 7/10 | 7/10 | 7/10 | 7/10 |
| shelf-place-v3 | 20.00% | 3/10 | 2/10 | 2/10 | 1/10 |
| stick-pull-v3 | 8.75% | 3/10 | 4/10 | 7/10 | 5/10 |
| stick-push-v3 | 78.75% | 5/10 | 10/10 | 10/10 | 10/10 |
| 合计 | 168/400 = 42.0% | 28/50 = 56.0% | 32/50 = 64.0% | 36/50 = 72.0% | 33/50 = 66.0% |

当前其余45任务N=280/450=62.22%，与五任务28/50合计308/500。当前五任务中stick-push由旧78.75%变为50%，其余四任务上升；这并非所有任务统一提高。每任务当前只有10源，不能通过两张表推断渲染的固定提升方向。

## 旧held42% vs 当前A主表H10配置

| 维度 | 旧held100 / standalone | 当前D24 MT50 |
|---|---|---|
| 底座 | π0.5 MT50 SFT030000 | 相同保存权重身份 |
| 权重SHA | dff338a91dbe534ca3c4525ba82df9324662e3c87131f42ed6e3d1b7bf0e94d4 | 相同 |
| normalizer SHA | 4fff91faea9afc9208e5519088f2bc8fb9cb21102bfeec8a9b3f259863c5cf00 | 相同 |
| 任务/独立初态 | 固定五任务×20=100 | 全50任务×10=500，新test |
| 续跑统计 | 原报警prefix固定后，每源4个配对suffix seed；无报警2源共同结局保留 | 每初态完整online rollout一次；同源跨H/方法配对 |
| control / action scale | 30Hz / .015 | 30Hz / .015 |
| physics | 400Hz backend | 400Hz，执行frame_skip按13/13/14序列 |
| 生成/执行/NFE | raw50 / execute10 / NFE10 | raw50 / execute10 / NFE10 |
| 最大控制步 | 绝对300 | 绝对300 |
| 成功 | 轨迹any成功；成功终止 | info.success即提前终止，所以终局成功等价any成功 |
| 渲染 | 固定Mesa llvmpipe启动环境 | NVIDIA EGL，已保存NVIDIA H100 renderer身份 |
| 随机初态 | 旧held源如disassemble__2026111750 | 新域corrector_D24_new_test_v1，如disassemble ordinal0 env398075461 |
| policy noise | source_natural_decision与branch_suffix_decision分域，逐决策显式seed；4后缀 | source policy_seed独立Generator连续取noise；同源跨H冻结 |
| 选择 | 100原held主槽全保留，98有cut+2无cut | 500冻结新源、全50任务，无技术失败 |

旧held normal并非严格“从头到尾只有一条不改随机流的N轨迹”：其prefix到首次报警后，normal保留旧队列继续，但后续重规划使用该repeat的suffix域随机流。它是合法的旧配对实验定义，却不能与新完整online单次seed流视为同一观测。

## 额外发现：历史完整MT50=77.24%

旧run.json直接声明2500episode、50任务各50，task_macro=.7724。读取其保存episodes.jsonl独立求和得到1931成功/2500，没有新仿真。该报告采用每任务reset seed1000..1049、policy seed100000+task_id*1000+episode_index、Mesa、corner2、480²、NFE10、执行K10、300步。保存全部episode的simulation_timestep=.0025、frame_skip=5，即有效控制80Hz；当前A是30Hz、.015动作尺度。旧run.json本身未单列action_scale，本核查不凭缺项填写该值。
旧完整MT50的五任务均值为71.2%：disassemble36、pick-place-wall86、shelf80、stick-pull60、stick-push94%。这进一步说明历史库存在多种协议，不能用“之前π0.5成功率”泛指单一数字。

## 仍不能证明的部分

- 这次没有同初态同噪声只换renderer的实验，不能定量归因于Mesa→NVIDIA。也不能宣称renderer变化必然提升表现。
- 旧100源与当前500源不同，不能把旧42%和新61.6%作配对增益或称提升19.6pp。
- 此核查验证报告分母、身份、主要协议、成功条件；未执行逐像素/逐轨迹一致性，不声称两版实现等价。
- 即使控制Hz/权重相同，环境初始化、随机流、恢复/续跑执行器仍可能影响结果。当前数据没有分离这些因素。
- 暂无必要重跑全部旧实验；主表和新增R扫描必须沿用当前主表的冻结500源/底座/normalizer/NVIDIA/30Hz/.015/300步，保留一张协议差异表。若发现具体动作单位、H语义或reset实现不一致，再定向修正，不将统计差异本身直接判为bug。

## 来源（准确路径）

- `codex_history/CORRECTOR_MIGRATION_CONTEXT.md`
- `Corrector/docs/STANDALONE_CORRECTOR_ABLATION_20260918.md`
- `Corrector/coordination/NATIVE10_HELDOUT_EXECUTOR_HANDOFF.md`
- `Corrector/outputs/native10_training_20260916/heldout_protocols/heldout_v1/config.json`
- `Corrector/outputs/native10_training_20260916/heldout_protocols/heldout_v1/freeze.json`
- `Corrector/outputs/native10_training_20260916/heldout_handoffs/heldout_v1/parameters.json`
- `Corrector/experiments/native10_training_20260916/protocol.py`
- `Corrector/experiments/native10_training_20260916/adapter.py`
- `ACT-RECAP/src/ac_tmil/idea3/metaworld_runtime.py`
- `Corrector/experiments/native10_training_20260916/run_main_gpu.sh`
- `Corrector/experiments/standalone_ablation_20260918/run_gpu.sh`
- `embodied-ai-workspace/config/vla-corrector-mesa.env`
- `Corrector/sim_command/20260919/deadline_20260924/MAIN_FINAL_TASKS.csv`
- `Corrector/sim_command/20260919/deadline_20260924/A/config/CONFIG.json`
- `Corrector/sim_command/20260919/deadline_20260924/A/config/BASE.json`
- `Corrector/sim_command/20260919/deadline_20260924/A/config/TEST_SOURCES_V1.json`
- `Corrector/sim_command/20260919/deadline_20260924/A/chain/workers/0/renderer_identity.json`
- `Corrector/sim_command/20260919/deadline_20260924/A/code/resident_worker.py`
- `Corrector/sim_command/20260919/receipts/A/A_D24_MULTI_INTERVENTION_PILOT_V1_REPORT_r2.md`
- `embodied-ai-workspace/artifacts/vla-baselines/evaluations/metaworld/pi05/mt50-pi05-mb-20260912-v1/run.json`
- `embodied-ai-workspace/artifacts/vla-baselines/evaluations/metaworld/pi05/mt50-pi05-mb-20260912-v1/episodes.jsonl`


## 3. 旧20源Post80%与当前全MT50 Post69%


结论：不能把这两个数字解释为相同实验从80%跌至69%。旧pilot是一个子任务disassemble的20个已揭晓开发初态；当前主表是50个任务各10个独立新test初态，共500。当前主表中同一个disassemble任务的Post是10/10=100%，并非69%。但10个新源与旧20个源不重合，所以100%也不能据此宣称对旧80%提高20pp。

| 数据范围（H10） | N | R | Post | Velocity |
|---|---:|---:|---:|---:|
| 旧20 disassemble pilot，once | 本pilot未测N | 13/20=65% | 16/20=80% | 15/20=75% |
| 旧20同初态pilot，multi | 本pilot未测N | 13/20=65% | 16/20=80% | 15/20=75% |
| 当前MT50主表，仅disassemble | 10/10=100% | 9/10=90% | 10/10=100% | 10/10=100% |
| 当前MT50主表，历史五任务名称子集 | 28/50=56% | 32/50=64% | 36/50=72% | 33/50=66% |
| 当前MT50全50任务 | 308/500=61.6% | 336/500=67.2% | 345/500=69% | 340/500=68% |

## 当前五任务明细

| 任务 | N/10 | R/10 | Post/10 | Velocity/10 |
|---|---:|---:|---:|---:|
| disassemble | 10 | 9 | 10 | 10 |
| pick-place-wall | 7 | 7 | 7 | 7 |
| shelf-place | 3 | 2 | 2 | 1 |
| stick-pull | 3 | 4 | 7 | 5 |
| stick-push | 5 | 10 | 10 | 10 |

旧20 once/multi三种方法的逐源最终成败均一样；R/Post/Velocity分别有6/4/6个multi源真正触发至少两次，故不是多次路径没运行，但当前80%也不是放开多次使结果由较低数值升至80%。同一pilot的Post_once本身也是80%。

## 已核对的一致项与差异

- Pilot与主表均使用声明SHA相同的pi05_MT50_SFT030000；选定Q的元数据、guidance、独立自身半径solo_rule一致。没有重新hash大权重，不能把这一点称为本轮独立数值复现。
- 两个新实验均NVIDIA EGL；H10/C10、最多300真实控制步、30Hz控制/400Hz物理、0.015动作scale、corner2 480×480、raw50/NFE10相同。G0阈值0.05、每5步、历史成熟/承诺锁不变，once最多一次。
- 实际语言也一致：pilot `chain/workers/0/MODEL_READY.json`记录`Pick a nut out of a peg`，主表冻结source instruction也相同。pilot BASE继承的`Disassemble a nut from a peg.`只是模板残留，实际由TASK_DESCRIPTIONS覆盖，不能据模板宣称语言更改。
- 当前pilot120个回合复用了旧20初态的已保存小数组检查，仍不是完整隐藏状态证明。主表为50任务各10个全新test源。CPU核对pilot20环境seed与主表500环境seed交集为0。
- 随机策略流也不是同一批：pilot沿旧source_seed/suffix_seed/candidate_seed；主表自然采样使用与N一致的episode CUDA generator，纠偏候选用D24_designated_a0按source/policy_seed/cut固定。不能将旧20与新10做逐源配对差值，也不能把差值完全归因为某一个因素。
- 定向读取两份controller和runtime终止/成功字段：均来自`info.success`，遇成功即结束，或done/截断/300步结束；技术异常success=null。因此没有发现这两组采用“末帧成功”与“任意帧成功”导致的成功定义差别（因首次成功立即停止，两者在保存结局等价）。

## 保存结果内部核对

读取主表5500行标量CSV，11格每格500、全部complete、步数1..300，成功数重新求和与FINAL_CELLS/MAIN_FINAL_TASKS一致；11格source/env_seed/policy_seed/task/ordinal身份逐源一致，0不匹配。Pilot PER_SOURCE_RESULTS20条×6方法重新求和得到13/16/15，once/multi逐源成败一致。未发现漏分母、重复源把69%压低、或把技术失败计0的迹象。这一结论只覆盖保存结果和上述窄语义，不等于全面证明实现无错。

## 论文建议

主表69%是MT50整体成绩；80%只放在标注“disassemble / 已揭晓开发20初态”的小实验中，不写成MT50整体。新增R的H20/30/40/50必须严格复用当前500个主test源及当前N/P/V同一评估条件，才可补齐H扫描。无需为了让历史百分比相同重跑成功样本。

## 定向来源

- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/MAIN_FINAL_TASKS.csv`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MAIN_ONCE_V1/FINAL_EPISODES.csv`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MAIN_ONCE_V1/FINAL_SUMMARY.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MAIN_ONCE_V1/config/CONFIG.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MAIN_ONCE_V1/config/TEST_SOURCES_V1.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/FINAL_SUMMARY.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/PER_SOURCE_RESULTS.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/COMPLETION_CHECK.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/config/CONFIG.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/config/SOURCES.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/NUMERICAL_BINDING.md`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/chain/workers/0/MODEL_READY.json`
- `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1/evidence/ONCE_REUSE_DECISION.json`


## 4. 文献逐表核查


**关键纠正：目前直接相关的 VLA-Corrector 原文并不支持“H=10只有40%多”。其 Table 4 的 H=10 原始π0.5成功率是64.50%。**

| 执行H | VLA-Corrector论文 Baseline SR% | 当前本项目 N SR% |
|---:|---:|---:|
| 10 | 64.50 | 61.60 |
| 20 | 61.40 | 48.00 |
| 30 | 56.10 | 41.00 |
| 40 | 54.45 | 41.00 |
| 50 | 48.72 | 39.20 |

左列来源：[原文Table 4，PDF第8页](https://arxiv.org/pdf/2607.01804v1#page=8)；右列是本地 `deadline_20260924/MAIN_FINAL_CELLS_WITH_COSTS.csv`。这些只是定位参照，不能作为同协议排名。H10我们的61.6%较文献64.5%低2.9pp，而不是异常超过文献约40%的基准。

**40%多的容易混淆出处：**Table 1的平均48.70%；Table 3明确写H50、48.72%；Table 1的Very Hard单组是41.0%。不能把这些字段改称H10全MetaWorld。[Table 1/3，PDF第6–7页](https://arxiv.org/pdf/2607.01804v1#page=6)。Table 1的48.70恰为四难度列(70.5+45.0+38.3+41.0)/4；不能默认等于50任务等权的分母口径。

## 协议已知与未知

- 原文H定义为每次生成后实际执行动作数；与生成chunk长度C区分。[§2，PDF第3页](https://arxiv.org/pdf/2607.01804v1#page=3)
- 原文按四难度组报告、每任务20 episodes；Table 13明确50任务。因此不是本项目旧五任务开发集。[§C.1，第17页；Table 13，第19页](https://arxiv.org/pdf/2607.01804v1#page=17)
- 作者官方README示例为n_action_steps10、chunk_size50、episode_length300、每任务20、seed1000；这里是公开示例，不能据此断言论文每一表均用了该命令。README明确不提供数据、微调VLA权重、corrector checkpoint或原始日志。[官方Evaluation/Data and Checkpoints](https://github.com/ZJU-OmniAI/vla-corrector#evaluation)
- 已核论文/README没有明确给出该π0.5 MetaWorld底座的SFT更新步数、精确checkpoint身份、逐源seed表、renderer和控制频率/动作scale。当前本地030000是我们保存的复现底座，**不能写成已证明与作者底座相同**。官方示例中的seed1000也不等于我们主表500个哈希新test seeds。
- 本项目当前固定30Hz控制/400Hz物理、动作scale.015、NVIDIA EGL、每任务10新源；上述原文缺项不能擅自补齐。即使H相同，绝对成功率仍不可要求逐点相等。

## 另外三篇不能佐证“π0.5＋MetaWorld H10都是40多”

| 工作 | 原文实际对应实验 |
|---|---|
| [QGF，§6/附录A](https://arxiv.org/html/2606.11087v1) | OGBench flow策略离线RL，不是π0.5-MetaWorld主表。 |
| [QPILOTS，§5.2](https://arxiv.org/html/2606.14801v1) | π0.5在6个LIBERO-90任务上的在线critic学习；不同环境与数据范围。 |
| [GAF v3，Table II](https://arxiv.org/html/2607.02092v3) | 47.5%=19/40，底座SmolVLA、真实机器人放瓶，不是π0.5-MetaWorld。 |

目前这四篇中没有查到另一条“π0.5＋MetaWorld、执行H10、统一协议约40%”的原文证据；若用户指具体其他工作/第三方复现，需按其具体表号核查，不能先假设与我们的61.6%可比。

本地文献已存在：`Corrector/references/vla_guidance/REPORTED_RESULTS_20260919.md` §3.2早已摘录Table 4；此次再次核对arXiv原文HTML/PDF页码和官方仓库。未启动任何模型、仿真或新实验；未改共享文档/controls。


## 5. 当前判断与执行边界

- 主表保存结果重聚合吻合；目前没有查到把技术失败填成功、改底座权重或算错分母的证据。这是必要的结果核查，不是全面实现正确性证明。
- 不把42%→61.6%写成同协议提升，也不把80%→69%写成性能退步。论文各表显式列任务集、独立源数、repeat、执行H、renderer和随机流。
- 用户要求的新增R四格已独立授权到B/C，复用当前500源。B/C的既有Mesa环境与主表不同，须移植当前NVIDIA EGL路线；禁止静默换协议后合表。无需为历史数字不同重跑已完成主表或独立GPU预检。
