数据采集与训练附录的来源、状态及执行配套说明

展示文档为 [APPENDIX_DATA_AND_TRAINING_ZH_20260926.md](APPENDIX_DATA_AND_TRAINING_ZH_20260926.md)，当前具体配置范围为π0.5＋MT50；其他底座与环境在展示页仅保留相同流程与接口适配的概括。本文件保存数据来源、实际协议、方案身份和待接入记录。2026-09-26本次更新执行文件检索、既有日志统计及文档编辑，新增采集与训练均为0。

本轮按用户要求，数值取自既有执行日志、运行配置、训练代码及其明确的算术换算。真机恢复阈值、辅助训练源数和费用尚未取得对应日志。用户本次删除了相关数值登记表，恢复与配对方案及具体日志接入项保存在本配套说明。此前自行拟定的统一R=R_G=4、每任务G0/Q测试5/10源、20%交互预留、D/Q/G0的20,000/20,000/16,000更新以及D窗口池上限移出展示页。这些取值及其118,000分支等推算仅保存在[上一版规划存档](../experiments/appendix_data_training_20260926/archive/APPENDIX_DATA_AND_TRAINING_EVIDENCE_ZH_20260926_before_platform_audit.md)和原PLAN/CALCULATIONS中，身份为未执行的草案，后续填数以正式运行记录为准。

用户确定的20/50训练源目标、仅训练集与测试集、D/Q冻结后训练G0一次保持为后续方案。LIBERO既有文件中的adapt_validation按其原始身份保留。当前MT50网络结构、动作规则和优化配置来源见下方索引；宽度改变及H/队列输入追加对应结构计算值，完整新训练的实际更新与耗时保留空值。本次沿实际训练启动路径核实了AdamW调用的β/ε有效值，并写入展示表；来源见本文件末尾的补全记录。

核对结果保存为 [PLATFORM_PROTOCOL_AUDIT.json](../experiments/appendix_data_training_20260926/PLATFORM_PROTOCOL_AUDIT.json)。[audit_platform_records.py](../experiments/appendix_data_training_20260926/audit_platform_records.py)直接读取现有JSON/JSONL，重算父源、候选、尝试、控制步、时间与epoch；脚本没有环境或模型调用。

LIBERO的实际数据与监督

LIBERO算子适配使用官方π0.5-LIBERO权重与本域normalizer，原生特征为329维，候选动作为7维控制指令。每源5候选、每候选1次执行，原始32父源划分为24训练和8原验证，得到120训练候选和40原验证候选。对应证据为[算子运行配置](../sim_command/20260919/work/B/B_D24_LIBERO_POST_V1_r1/configs/pi05official_Post_libero_10_s0_r1.json)、[逐次执行目录](../sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/jobs)和[训练完成记录](../sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/D24_E8_LIBERO_POST_r1/FIT_RESULT.json)。审计JSON保存了实际读取的8份development.jsonl路径。

候选为a0及两组按父源种子产生的反向XYZ扰动，第二组同时改变夹爪方向；配置dev_xyz_command_amplitude=0.6。每次执行调用env.seed(reset_seed)、env.reset()，运行10步稳定动作，使用相同首次policy_seed，从初态运行到第20控制步；执行候选前5步，随后按原生K=5续跑。初始仿真状态保存为记录，执行采用同种子复位和重新运行，未调用set_state复制切点。对应[实际执行代码](../sim_command/20260919/work/B/B_D24_LIBERO_POST_V1_r1/libero_eval.py)。

完整系统扩展使用D2/age2/old3–fresh3/native5/C5协议。新增40次尝试来自既有父源，其中30完成、10技术失败，原160次Q执行直接复用。D从真实逐步特征和动作中构建681训练行、225原验证行，共906个两步窗口行；跨分支相同前缀未去重，因此906不是互异物理状态窗口数。G0每支执行1次，目标为fresh成功标志减去old成功标志，形成7训练对和4原验证对，11个收益均为0。old3/fresh3中的3指执行步数，不是重复次数。数据见[DATA_STATUS.json](../sim_command/20260919/results/A/A_D24_LIBERO_FULL_NATIVE_V1/launch_r6/DATA_STATUS.json)，目标构造见[train_full.py](../sim_command/20260919/work/A/A_D24_LIBERO_FULL_NATIVE_V1_r6/train_full.py:27)。

| 配对项 | 实际检查 | 实际处理 |
|---|---|---|
| G0 | 切点2；reset_seed、policy_seed相同；old3形状3×7；prefix_actions满足rtol=1e-5、atol=1e-6 | 仅完整、通过检查的old/fresh形成终局差；缺失与技术结果逐项写invalid |
| Q L11 | 切点20；split、两类种子一致；329维feature满足rtol=1e-5、atol=1e-5；reference满足rtol=1e-5、atol=1e-6 | 2个父源整组排除，剩30父源：22训练、8原验证 |

Q筛选见[prepare_q.py](../sim_command/20260919/work/A/A_D24_LIBERO_FULL_NATIVE_V1_r6/prepare_q.py:24)。被排除父源为D24_LIBERO_DEV_v1_libero_10_t03及D24_LIBERO_DEV_v1_libero_spatial_t04，原因均为actual candidate cut/reference does not align。原始记录保留；后续L11的数据筛选未改写此前BCE的120/40候选训练记录。G0记录中的physical_state_equivalence_proven为null；代码检查的是种子、动作前缀和规定的特征/锚点条件，没有物体位置、姿态或接触误差阈值。这些allclose值属于数值数组检查，不能改写为真机毫米、角度或关节容差。

实际训练完成的是算子版BCE Q：399→128→64→1，ReLU，种子9301–9304，4成员各4,000更新，总16,000。batch64按candidate行有放回采样；AdamW的显式配置为lr=3e-4、weight_decay=1e-3，代码没有scheduler及clip操作，β/ε由该次训练所用环境中的AdamW实现提供，有效值为β=(0.9,0.999)、ε=1e-8；配置和权重文件本身没有显式保存这两个字段。正类权重由训练标签计算为5/115，使用最后一步权重。每成员等效epoch=4,000×64/120=2,133.333。CPU4线程，训练阶段回执19.770698s。计时起点在输入矩阵准备完成后，涵盖成员拟合、导出及导出检查；它不是含全部预处理的端到端训练时长。证据为[train_head.py](../sim_command/20260919/work/B/B_D24_LIBERO_POST_V1_r1/train_head.py:51)及上述FIT_RESULT。

完整D/G0/L11流程在标签检查后以SCIENTIFIC_GAP结束，实际更新0，完整系统测试尝试0。依据[RESULT.json](../sim_command/20260919/results/A/A_D24_LIBERO_FULL_NATIVE_V1/launch_r6/RESULT.json)及[终局回执](../sim_command/20260919/receipts/A/A_D24_LIBERO_FULL_NATIVE_V1_RESULT_r13.json)。算子版Q与完整系统数据分列，保留各自监督与执行身份。

LIBERO实际费用口径

| 项目 | 由日志或配置得到的数值 | 计量范围 |
|---|---:|---|
| Q登记执行 | 160 | 全部完成；32父源×5候选×1次 |
| Q策略控制步 | 24,825 | development.jsonl的steps之和，包含3,200前缀控制步 |
| Q稳定步 | 1,600 | 160次完成执行×配置settle_steps=10，额外计于策略控制步 |
| Q回合耗时和 | 5,988.882171s | 逐行elapsed_seconds相加 |
| Q回合采集跨度 | 966.354695s | 最早at_utc−elapsed至最晚at_utc；含首次模型/环境加载的完整墙钟另计 |
| D/G0新增尝试 | 40 | 30完成、10技术失败，来自20个既有父源 |
| D/G0策略控制步 | 4,499 | RESOURCE_SUMMARY中的development.steps |
| D/G0已保存回合耗时和 | 9,305.158599s | summed_saved_episode_host_seconds |
| 总登记尝试 | 200 | 160＋40，复用Q数据计一次 |
| 已记策略控制步 | 29,324 | 24,825＋4,499 |
| 全部环境交互步数 | 空值 | 还需合并全部reset/settle及失败初始化中的实际控制推进 |
| 完整采集墙钟 | 空值 | 还需合并各轮加载、初始化、执行与退出的起止记录 |

D/G0费用来源为[RESOURCE_SUMMARY.json](../sim_command/20260919/results/A/A_D24_LIBERO_FULL_NATIVE_V1/launch_r6/RESOURCE_SUMMARY.json)。前序失败初始化记录均列于该文件prior_initialization_costs_retained_in_runtime_results。回合时间和、并行跨度、GPU分配时长分别记账；本配套费用表中的29,324为日志策略控制步；用户已从展示文档删除费用表及相关计量说明。

真机来源与实施接入

真机已有档案是AgileX PiPER上的用户评测汇总：Pick-place、Alignment、Disturbance三任务，每任务每方法60回合，两方法合计360回合；baseline成功41/29/26，Ours成功49/40/39。来源类型为用户提供并确认的汇总，位于[真实场景归档](../sim_command/20260919/deadline_20260924/analysis_20260923_master_completion/HISTORICAL_PAIR_AND_REAL_DATA.json)及[实验总表F4](EXPERIMENT_RESULTS_MASTER.md:843)。这些计数不是原始采集日志，故本次展示页未将其写为辅助训练源、R、R_G或分支总数。

归档中ours_branch、Q_configuration、intervention_count_mode、per_trial_pairing均为null。历史分析会话记载真机由用户独立完成，[会话记录](../../codex_history/corrector_context_20260924T133320Z/conversations/analysis/20260924T133504367677Z/conversation.md:447)及后续回填仅包含汇总。当前可读记录没有真机D/Q/G训练manifest、机器人/物体复位配置、状态阈值和不匹配回放日志。

配套记录中的真机方案是后续采集的操作定义：按任务恢复表重建初态，闭环回放实际运动与夹爪指令，按连续状态误差及离散接触关系组织配对，偏离记录转入独立日志并保留其有效D转移。ε_j按本次补充的参考回放校准流程生成：参考回放重复误差上界与任务几何/控制允许偏差逐项取较小值，再冻结到任务恢复配置。该校准规则是新增操作规划，真实校准记录和各物理量阈值尚待接入；没有填入毫米、角度、速度或时间的通用常数。该方案的实施状态保存在本文件；现有档案尚未提供实际采用的替代协议，所以本轮不将一种假设的采集方法写成已执行真机流程。

| 接入项 | 对应文件与字段 | 用途 |
|---|---|---|
| 真实恢复过程 | robot_recovery、object_reset、controller_mode、gripper/contact_state | 按实际操作替换展示页的恢复描述 |
| 配对判定 | 每项误差定义、单位、阈值、判定窗口、实际误差与结果 | 填写ε_j并区分位置、姿态、速度与接触条件 |
| Q监督 | parent_family_id、split、anchor、candidate、repeat、实际起点与终局 | 按完整源组统计N_Q、候选数与R |
| G0监督 | parent_family_id、paired_attempt_id、frozen_Q_checkpoint、corrected/keep结果 | 统计N_G、R_G和真实配对终局差 |
| D监督 | trajectory_id、有效观测/动作时钟、窗口索引、mask | 统计实际训练/测试窗口及来源 |
| 偏离回放 | attempt_id、mismatch_reason、实际状态、重采关联、保留用途 | 统计通过/偏离/重采及其交互费用 |
| 训练 | checkpoint、optimizer配置、seed、batch单位、实际step与起止时间 | 填入每成员epoch和完整集成成本 |
| 采集成本 | reset/prefix/suffix实际控制步、全部尝试起止时间、加载与退出记录 | 汇总真实交互量和墙钟，保留失败与丢弃费用 |

已检索Corrector的docs、configs、provenance、coordination、analysis及实验目录，embodied-ai-workspace的docs/manifests与datasets/artifacts浅层目录，ACT-RECAP的docs/datasets、ACT-SAFE-RECAP/docs、vla-corrector/docs及上述历史会话。piper-wine-pi05-rl属于PiperRandomizedBottleLift-v0仿真SFT/PPO项目；vendor中的机器人回放文件属于库代码，两者均未作为本算法真机采集证据。真机原始日志目录已向用户询问，接入后按本配套接入表保存实际协议和数值。

MT50原有规格的来源索引

D/G0结构、loss与优化器显式参数来自[历史动力学实现](../../ACT-RECAP/src/ac_tmil/future_aware/models.py)、[训练实现](../../ACT-RECAP/src/ac_tmil/future_aware/training.py)、[历史训练参数核对](TRAINING_WEIGHTS_AND_EPOCHS_ZH_20260926.md)及其原始配置。D宽度768、G0宽度256与Q宽度512的参数量是既有结构加H/队列标量后的计算值；[单次训练方案](SINGLE_PASS_TRAINING_AND_CONTRIBUTIONS_ZH_20260926.md)保存输入维度与计算关系。原生视觉适配依据[π接口](../experiments/pi05_parallel_latency_20260926/model.py)、[Smol接口](../experiments/smol_x_native_feedback_q_latency_20260926/smol_native.py)、[X接口](../experiments/smol_x_native_feedback_q_latency_20260926/x_native.py)。新原生特征训练的实际统计量、优化器完整保存配置、更新数和成本由正式成员记录接入。

上版全部来源、候选构造、原生特征处理与训练规划说明保存在[配套说明存档](../experiments/appendix_data_training_20260926/archive/APPENDIX_DATA_AND_TRAINING_EVIDENCE_ZH_20260926_before_platform_audit.md)，[展示页存档](../experiments/appendix_data_training_20260926/archive/APPENDIX_DATA_AND_TRAINING_ZH_20260926_before_platform_audit.md)保留修改前内容。原始实验结果、历史失败、权重和已完成单元保持原记录。


本次用户删减后的计划补全

本次以用户手改后的展示文档为编辑基准，保留其段落与表格取舍。已移除的源数登记、实测采集、权重路径、实测训练成本、LIBERO费用和真机数值登记表均保持删除；同时清理对应的路径说明、采集/训练费用计量段落和费用标题。用户编辑版本保存于[修改前快照](../experiments/appendix_data_training_20260926/archive/APPENDIX_DATA_AND_TRAINING_ZH_20260926_user_edited_before_completion.md)。

| 补全项 | 写入展示计划的值或规则 | 实际依据与规划身份 |
|---|---|---|
| D/Q/G0 AdamW | β=(0.9,0.999)，ε=1e-8 | 按实际启动解释器、AdamW调用和环境源码核实有效值；本计划显式固定这些参数 |
| LIBERO算子Q AdamW | β=(0.9,0.999)，ε=1e-8 | 运行代码使用同一解释器，调用未覆盖这两个参数；由实现签名还原有效值 |
| D/Q/G0更新预算 | 每成员4,000，末步权重 | 沿用Smol历史辅助训练已执行的固定预算；新宽网络的单次训练预算，不是已完成的新训练步数 |
| 九候选Q重复数 | R=4，每源36次候选执行 | π0.5历史train600的outcomes数组形状600×13×4；本计划将已使用的4次终局重复配置用于九候选集合 |
| 纠偏收益G0重复数 | R_G=1，每源1对、2次分支执行 | LIBERO真实配对记录repeats_per_branch=1；本计划保留一次真实配对的采样单位，将干预内容定义为最终Q纠偏C10 |
| epoch | D普通256,000/N_D；D局部64,000/N_local；Q为128,000/N_Q；G0为64,000/N_G | 4,000更新乘各自batch；分母由固定的数据索引确定 |
| D窗口与局部组 | 五步历史/五步未来，末端mask；局部四动作形成六对 | 沿用现有D目标与batch结构，补全源组资格和索引固定规则 |
| 真机ε_j | 参考回放重复误差上界与任务允许偏差逐项取较小值 | 新增校准操作定义，具体数值来自任务恢复记录；不设置通用物理容差 |

Q与G0的重复次数是本次选定的采集配置。G0单个标签为一对真实终局差，MSE跨源拟合条件期望；新G0的纠偏C10目标沿用已确定的D/Q→G0方案。R_G=1的来源是已执行配对协议的采样次数，历史old3/fresh3动作内容与当前纠偏目标分别保留各自身份。各任务使用同一R/R_G，本配套文档保留历史LIBERO每候选1次与原始监督定义。

优化器有效参数的证据链为[Smol实际启动命令](../sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/claims/jobs/D_1241.json)、[D/G0/Q训练调用](../sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/code/train_head.py:54)、[对应解释器中的AdamW签名](../../embodied-ai-workspace/environments/lerobot/lib/python3.12/site-packages/torch/optim/adamw.py:26)及[版本文件](../../embodied-ai-workspace/environments/lerobot/lib/python3.12/site-packages/torch/version.py:4)。LIBERO使用相同解释器的调用见[libero_eval.py](../sim_command/20260919/work/B/B_D24_LIBERO_POST_V1_r1/libero_eval.py:151)及[train_head.py](../sim_command/20260919/work/B/B_D24_LIBERO_POST_V1_r1/train_head.py:67)。这些值通过实际代码路径核实，区别于根据常用配置猜填。

每成员4,000的预算来源为[METHOD_FROZEN.json](../sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/METHOD_FROZEN.json)及[FIT_SUMMARY.json](../sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/FIT_SUMMARY.json)，后者记录2D、2G0、4Q共32,000次实际更新。Q的重复数直接读取[train600数据包](../outputs/native10_training_20260916/input_bundles/final_train600_input_v1/train/arrays.npz)的NPY头，outcomes.shape=(600,13,4)、control_outcomes.shape=(600,4)，读取过程未加载模型。G0重复数来自前述LIBERO DATA_STATUS逐源记录。

当前补全规格保存于[CURRENT_TRAINING_PLAN.json](../experiments/appendix_data_training_20260926/CURRENT_TRAINING_PLAN.json)。其执行状态为未执行，来源字段逐项指向上述实际配置与记录；历史PLAN/CALCULATIONS继续保留归档身份。


π0.5＋MT50范围调整

本次以用户已删除LIBERO内容的版本为基准，展示页具体介绍π0.5＋MT50。已清理LIBERO的开头残留、三个骨干共用的表述、其他底座的token/投影/精度细节及独立真机方案。保留当前采集与训练配置，包括R=4、R_G=1、九候选、C10、D/Q→G0、训练/测试划分、每成员4,000更新、网络宽度与参数量；MT50继续采用本文既定的复位和前缀回放流程。历史来源及其他平台资料留在本配套文档中。编辑基准见[用户删除LIBERO后的版本](../experiments/appendix_data_training_20260926/archive/APPENDIX_DATA_AND_TRAINING_ZH_20260926_user_removed_libero_before_pi05_scope.md)。

真机后续采集方案存档

真机采集方案由任务恢复表、参考执行记录和分支记录组成。任务恢复表保存物体身份、初始位姿、支撑与接触关系、机器人关节位置和速度、末端位姿、夹爪状态及控制器模式。每次采集按该表恢复物体布置和机器人起始状态，再由闭环控制器跟踪已保存的关节或末端参考轨迹，同步执行夹爪指令并记录实际反馈。到达切点后，保存实际观测、近期动作、活动队列、队列相位与剩余预算，形成该次候选执行的上下文。

配对判定同时使用连续状态误差和离散关系。连续项包括物体位置与姿态、机器人关节位置与速度、末端位置与姿态、夹爪开度及前缀跟踪误差；各项误差记为e_j，对应任务恢复配置中的阈值ε_j。配对条件为各项e_j≤ε_j，且物体身份、支撑/夹持/接触关系、控制器模式、切点和队列相位一致。任务恢复配置由采集前的参考回放校准生成：在物体身份、支撑、夹持与接触关系一致的参考回放中，按同一轨迹时刻计算各项重复误差上界，并与任务几何及控制配置中的允许偏差逐项取较小值，得到ε_j。实际误差、阈值单位、判定时刻与配对结果随分支记录保存，训练与测试沿用同一份恢复配置。

匹配回放进入同源候选组，执行冻结的候选动作并采集终局结果。偏离回放保存实际轨迹、偏离项与原因码，归入回放偏离记录；其中连续有效的状态转移进入普通D窗口池，配对监督由通过匹配的候选组形成。该源重新恢复初态并回放前缀后继续采集，Q使用匹配候选的真实终局结果训练，D使用实际观测转移训练；D/Q冻结后，G0使用最终Q产生的纠偏替换与保留队列配对终局差训练。数据按初始场景族划分训练集和测试集，各成员共享采集结果。
