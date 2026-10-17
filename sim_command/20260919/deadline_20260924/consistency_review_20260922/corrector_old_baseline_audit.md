# 旧42%与当前61.6%：只读来源核查（2026-09-22）

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
