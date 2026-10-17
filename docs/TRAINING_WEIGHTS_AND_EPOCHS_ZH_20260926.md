π0.5、SmolVLA、X-VLA 历史权重、训练参数与等效 epoch 核对（2026-09-26）

本次核对对象是历史实验实际使用的三个底座，以及各自的 D、G0 和最终 L11、fit9101 的 Q。三份底座权重与二十四份辅助成员权重均已确认文件存在；完整绝对路径和换算结果保存在 [SUMMARY.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/training_history_audit_20260926/SUMMARY.json)。这里的底座 epoch 指本地 MT50 任务训练，不包含公开底座此前的预训练。

换算采用 `等效 epoch = optimizer 更新数 × 每次更新的有效 batch / 对应训练采样池大小`。底座有效 batch 包含数据并行卡数和梯度累积；独立训练的辅助成员各自计算。辅助训练大量使用有放回抽样，Q 还先按任务 bootstrap，因此这里表示累计抽样量相当于多少遍池大小，不代表每个原始样本都被完整、均匀地遍历了这些次数。D 每步混合两个采样池，分别给出两个 epoch。

三个底座使用同一版本 `lerobot/metaworld_mt50@a59f742d218c903328164257ecf180f9b18018a1`，共 204,806 个帧起点、2,500 条 demonstration，即 50 个环境任务各 50 条。元数据中的 49 是唯一任务索引/文本的数量，环境任务数仍为 50。一个帧起点会生成对应的未来动作 chunk，epoch 分母采用帧起点数，不再乘 chunk 长度。数据量见 [原始数据核对记录](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/artifacts/vla-baselines/preparation/20260911/metaworld.data-audit.json)。

| 底座所用权重 | 权重对应更新数 | 每卡 batch × 卡数 × 梯度累积 | 有效 batch | 等效 epoch | 总参数 / 可训练参数 |
|---|---:|---|---:|---:|---|
| π0.5，030000 | 30,000 | 32 × 8 × 1 | 256 | **37.4989** | 4,143,404,816 / 4,143,404,816 |
| SmolVLA，050000 | 50,000 | 8 × 8 × 1 | 64 | **15.6245** | 450,046,176 / 99,880,992 |
| X-VLA，030000 | 30,000 | 8 × 8 × 1 | 64 | **9.3747** | 879,482,456 / 879,482,456 |

底座参数量采用实际训练日志口径。π0.5 和 X-VLA 全量训练；SmolVLA 冻结视觉语言主干，训练 action expert 及相关状态/动作投影。三者均未使用 PEFT。底座 DataLoader 的末批及分布式补齐会使精确迭代器遍数与上述曝光当量略有差别；例如 π0.5 每个 loader 周期约 801 次更新，30,000/801=37.4532，而日志使用的样本曝光口径是 37.4989。

| 底座 | 优化器与峰值学习率 | weight decay | 梯度裁剪 | 调度 | 种子 | 训练动作 chunk |
|---|---|---|---:|---|---:|---:|
| π0.5 | AdamW，2.5e-5 | 0.01 | 1 | warmup 1,000；cosine 到 30,000；末值 2.5e-6 | 1000 | 50 |
| SmolVLA | AdamW，1e-4 | 1e-10 | 10 | warmup 1,000；计划 cosine 到 100,000；计划末值 2.5e-6 | 42 | 50 |
| X-VLA | xvla-adamw；VLM 组 1e-5，soft prompts/其余组 1e-4 | VLM 1e-5，其余 1e-4 | 10 | warmup 1,000；cosine 到 30,000；末值分别 2.5e-7 / 2.5e-6 | 42 | 30 |

三个底座优化器均使用 β=(0.9,0.95)、eps=1e-8。π0.5 配置为 bfloat16 并开启 gradient checkpointing；Smol/X 使用 FP32 主权重配合 BF16 混合精度。π0.5 保存的训练配置中 `n_action_steps=50`，实验执行时的 H=10 是运行配置；Smol/X 保存配置的 `n_action_steps=10`。训练 chunk 长度、控制执行 H 和 epoch 的样本单位分别处理。

SmolVLA 的 `train_config.steps=100000` 是计划值，所用 checkpoint 的 `training_state.step=50000`；历史日志后来继续到约 54,580 步并收到 SIGTERM。该 050000 权重按 50,000 步计算 15.6245 epoch，其 scheduler 也还未走到计划末值。π0.5 实际保存 30,000 步权重后曾出现进程组退出挂起，历史记录保留了清理结果；该退出问题不改变已经保存的权重步数。

初始化来源与已训练权重如下。SmolVLA 的训练起点尤其需要明确：初始化脚本加载了预训练 SmolVLM2，但 action expert 从配置随机初始化；X-VLA 则严格加载了完整 X-VLA base checkpoint，再适配 MT50 接口。初始化在 smoke 更新前保存，smoke 更新不计入正式权重。

| 底座 | 初始来源 | 本地初始化目录 | 本地已训练权重 |
|---|---|---|---|
| π0.5 | `lerobot/pi05_base@b211f3d44c36b6acfcf7ae94a64e8e96f75a64ba`，本地补齐 processors | [pi05 初始化](/mnt/bn/arnold-recommend/yaohaoyang/vla-corrector/outputs/metaworld_very_hard/inputs/pi05_base_b211_weights_a538_processors) | [030000/model.safetensors](/mnt/bn/arnold-recommend/yaohaoyang/vla-corrector/outputs/metaworld_very_hard/sft_pi05_mt50/checkpoints/030000/pretrained_model/model.safetensors) |
| SmolVLA | `HuggingFaceTB/SmolVLM2-500M-Video-Instruct@7b375e1b73b11138ff12fe22c8f2822d8fe03467`；action expert 随机初始化 | [smolvla-mt50-s42](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/models/initializations/smolvla-mt50-s42) | [050000/model.safetensors](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints/050000/pretrained_model/model.safetensors) |
| X-VLA | `lerobot/xvla-base@cdb7964e4fe842935d671bfab5a5ebe00a96648c`，完整权重接口适配 | [xvla-mt50-s42](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/models/initializations/xvla-mt50-s42) | [030000/model.safetensors](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/jobs/xvla_mt50_s42_D24_r2/training/checkpoints/030000/pretrained_model/model.safetensors) |

初始化依据为 [初始化脚本](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/projects/vla-baselines/launchers/initialize_metaworld.py:34)、[Smol action expert 初始化代码](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/projects/upstream/lerobot-smolvla-8fff0fd/src/lerobot/policies/smolvla/smolvlm_with_expert.py:76)、[SmolVLM 下载记录](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/artifacts/vla-baselines/preparation/20260911/smolvlm.download.json) 和 [X-VLA 下载记录](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/artifacts/vla-baselines/preparation/20260911/xvla.download.json)。三个底座训练配置的关键字段另存于 [BASE_CONFIG_EXTRACT.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/training_history_audit_20260926/BASE_CONFIG_EXTRACT.json)，其中包含原始配置文件路径。

历史辅助网络的容量与优化器如下，参数量均按一个成员计算。

| 网络 | 成员数 | 每成员结构与参数量 | 学习率 | weight decay | 主要监督 |
|---|---:|---|---:|---:|---|
| D | 2 | 主宽度 256；4,474,116 参数 | 3e-4 | 1e-4 | 未来视觉特征与本体状态；局部组另有分支差异损失 |
| G0 | 2 | 主宽度 128；1,468,033 参数 | 1e-4 | 1e-3 | 重规划相对 old 的终局成功率收益，SmoothL1，beta=0.1 |
| Q | 4 | 五个 MLP：state/action/head/residual/advantage；隐藏维度 16/32；7,058 参数 | 3e-4 | 0.01 | 最终 L11：BCE + gain + 0.5pair |

辅助网络均使用 AdamW、固定学习率、梯度裁剪 1；代码未覆盖的 AdamW 参数使用 β=(0.9,0.999)、eps=1e-8。每个成员独立执行 optimizer 更新，没有把多个成员的 batch 合并成一个模型的全局 batch。D/G0 的训练不反传更新 VLA。最终完整 Q 从头训练五个 MLP，固定归一化和 PCA 等预处理，不沿用旧 Q 的网络参数。Q 结构见 [critic.py](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src/corrector/critic.py:35)。

| 底座 / 网络阶段 | 每成员更新数 | 每步抽样单位 | 对应训练池 | 等效 epoch |
|---|---:|---|---|---:|
| π0.5 D，预训练 | 1,600 | 64 个自然轨迹窗口 | 57,792 个合法窗口起点 | 1.7719 |
| π0.5 D，实际所用权重 | 预训练 1,600 + 微调 400 | 每步 64 个自然窗口；微调另抽 16 个局部组 | 自然 57,792 窗口；局部 80 组 | 自然累计 **2.2148**；局部 **80.00** |
| π0.5 D，完整已执行预算 | 预训练 1,600 + 微调 1,600 | 同上 | 同上 | 自然累计 **3.5437**；局部 **320.00** |
| π0.5 G0，所用成员 341 / 342 | 1,000 / 1,200 | 16 个切点组 | 80 组 | **200.00 / 240.00** |
| π0.5 G0，完整已执行预算 | 各 1,600 | 16 个切点组 | 80 组 | 各 **320.00** |
| π0.5 最终完整 Q | 各 4,000 | 32 个源组 | 600 个源组 | **213.3333** |
| SmolVLA D | 各 4,000 | 64 个普通窗口 + 16 个局部组 | 普通 267,487 窗口；局部 188 组 | 普通 **0.9571**；局部 **340.4255** |
| SmolVLA G0 | 各 4,000 | 16 个有效切点父源 | 188 个父源 | **340.4255** |
| SmolVLA 首轮 Q | 各 4,000 | 16 个父源组 | 188 个父源组 | **340.4255** |
| SmolVLA 最终完整 Q | 各 4,000 | 32 个父源组 | 188 个父源组 | **680.8511** |
| X-VLA D | 各 4,000 | 64 个普通窗口 + 16 个局部组 | 普通 142,113 窗口；局部 187 组 | 普通 **1.8014**；局部 **342.2460** |
| X-VLA G0 | 各 4,000 | 16 个有效切点父源 | 191 个父源 | **335.0785** |
| X-VLA 首轮 Q | 各 4,000 | 16 个父源组 | 191 个父源组 | **335.0785** |
| X-VLA 最终完整 Q | 各 4,000 | 32 个父源组 | 191 个父源组 | **670.1571** |

π0.5 D 的自然池来自 300 条轨迹、58,092 个观测，对应 57,792 个合法采样起点；实际先均匀抽轨迹，再在轨迹中抽起点。局部采集计划 50 个父源，其中 40 个实际到达切点，每源两个切点，共 80 个切点组；每组四个候选窗口。微调每步同时抽 64 个自然窗口和 16×4 个局部分支窗口，两路 loss 各乘 0.5。loss 权重不减半样本曝光量。两个 D 都完成全部 1,600 步微调，但按验证结果选中了 `finetune_400.pt`，因此论文描述实际所用模型时对应自然累计 2.2148、局部 80 epoch。

π0.5 G0 的标签使用三份 fresh 的平均成功率减去 old 成功率，batch 的单位仍为一个切点组；成员 341、342 分别选择第 1,000、1,200 步权重。G0 训练前还为每个成员执行两折、每折 400 步的临时 D 交叉拟合，产生 out-of-fold 预测；这部分另计计算成本，不计入 G0 head 的更新数，也不改变部署 D 的 checkpoint。

Smol/X 各计划采集 200 train + 50 dev 父源，实际到达切点分别为 188/47 和 191/49。D 的普通动力学窗口池包含 old、a0、local± 各分支的完整采集轨迹，公共前缀只保留一次。Smol 训练池有 200 个父源、1,516 条分支轨迹、267,487 个窗口；未到切点的 12 个父源仍贡献早期窗口。X 训练池有 200 个父源、1,537 条轨迹、142,113 个窗口；9 个未到切点父源贡献其中 324 个窗口。Smol 的普通窗口允许末端目标 mask，X 的普通窗口枚举要求完整五步未来。X 的四分支局部组还要求每条分支都有完整五步目标，实际是 187 组，不能直接用 191 替代。G0 在 Smol/X 中使用冻结的配对 D 预测，标签为 a0 相对 old 的收益；这里没有沿用 π0.5 G0 的两折 crossfit 过程。

π0.5 完整 Q 使用历史五任务 train600，每任务 120 个源；每源包含 13 个候选动作块，每候选 4 个终局结果。一次 batch=32 抽取的是 32 个源组，而非 32 条单独后缀。Smol/X 完整 Q 各使用本底座有效父源，每组为 a0/local± 三个候选，每候选两次 suffix 结果先聚合成成功率。分母分别为 188、191，不能再乘候选数或后缀次数。Q 每个成员按任务 bootstrap 后再有放回抽 minibatch，所以 680.85 或 670.16 是池大小归一化的曝光当量。

π0.5 完整 Q 扫描为四 loss × 三 fit × 四成员 × 4,000，共 192,000 次独立模型更新；Smol/X 各为四 loss × 一 fit × 四成员 × 4,000，共 64,000 次更新。Smol/X 的首轮 D/G0/Q 各自合计 `(2+2+4)×4000=32000` 次更新。最终三个底座各取 L11、fit9101 的四个 Q 成员，每个只对应本轮 4,000 步；首轮 Q 和完整 Q 刷新是分别从头训练，不能将两轮步数累加到最终成员上。

辅助权重目录与成员编号如下。表中花括号表示分别存在的成员文件，逐个展开的绝对路径在 SUMMARY.json 中；加载 Q 时还需使用对应的 ranking/预处理资产。

| 简写 | 根目录 |
|---|---|
| PI_DG | [ACT-RECAP 历史 D/G0](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_future_aware_20260914) |
| PI_Q | [A_D24_FULL_Q_LOSS_SELECTION_V1](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1) |
| SMOL_AUX | [B_D24_SMOL_AUX_RETRAIN_V1](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1) |
| SMOL_Q | [B_D24_FULL_Q_LOSS_REFRESH_V1](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_FULL_Q_LOSS_REFRESH_V1) |
| X_AUX | [C_D24_XVLA_AUX_RETRAIN_V1](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1) |
| X_Q | [C_D24_FULL_Q_LOSS_REFRESH_V1](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1) |

| 底座 | 网络 | 实际所用权重相对路径 | 补充资产 |
|---|---|---|---|
| π0.5 | D | `PI_DG/models/spatial_pair_{241,242}/finetune_400.pt` | 对应成员目录的 `normalization.json` |
| π0.5 | G0 | `PI_DG/critics/gate_{341,342}/selected.pt` | 341/342 分别为第 1,000/1,200 步 |
| π0.5 | Q | `PI_Q/training/s9101_m{1041,1042,1043,1044}/L11/final.pt` | `PI_Q/ensembles/L11_s9101/ranking.json` |
| SmolVLA | D | `SMOL_AUX/fits/D_{1241,1242}/final.pt` | `SMOL_AUX/dataset/NORMALIZATION.json` |
| SmolVLA | G0 | `SMOL_AUX/fits/G0_{1341,1342}/final.pt` | 同上 |
| SmolVLA | Q | `SMOL_Q/fit_r1/fits/L11_fit9101_member{1041,1042,1043,1044}/final.pt` | `SMOL_Q/models/L11/ranking.json` |
| X-VLA | D | `X_AUX/fits/D_{2241,2242}/final.pt` | `X_AUX/dataset/NORMALIZATION.json` |
| X-VLA | G0 | `X_AUX/fits/G0_{2341,2342}/final.pt` | 同上 |
| X-VLA | Q | `X_Q/training/L11_s9101_m{1041,1042,1043,1044}/final.pt` | `X_Q/ensembles/L11_s9101/ranking.json` |

历史首轮 Q 另保存在 `SMOL_AUX/fits/Q_{19301,19302,19303,19304}/final.pt` 和 `X_AUX/fits/Q_{29301,29302,29303,29304}/final.pt`。这些是每成员 batch16、4,000 步的上一轮权重；上表最终 L11 Q 使用完整刷新后的 batch32 权重。

历史正式 Smol/X 辅助网络使用外部冻结的 π0.5 视觉/语言特征桥，虽然采集动作与成功率来自各自底座。2026-09-26 后续延时测试才适配为各底座原生视觉特征，并按用户要求不训练。该原生特征 D/G0 和 width512、约 3.78M 参数/成员的 Q 均属于随机初始化测速网络，训练更新数为 0、epoch 为 0；上面的正式训练配置仍是 D 4.47M、G0 1.47M、Q 7,058 参数/成员。历史接口依据见 [assets.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/assets.json:50)，后续测速依据见 [原生反馈加 Q 报告](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/REPORT.md)。

主要原始证据索引如下，数据分母采用实际构建产物和采样代码，步数采用 checkpoint 与完成回执。

| 对象 | 配置、实际记录及采样代码 |
|---|---|
| π0.5 底座 | [训练配置](/mnt/bn/arnold-recommend/yaohaoyang/vla-corrector/outputs/metaworld_very_hard/sft_pi05_mt50/checkpoints/030000/pretrained_model/train_config.json)、[实际步数](/mnt/bn/arnold-recommend/yaohaoyang/vla-corrector/outputs/metaworld_very_hard/sft_pi05_mt50/checkpoints/030000/training_state/training_step.json)、[训练日志](/mnt/bn/arnold-recommend/yaohaoyang/vla-corrector/outputs/metaworld_very_hard/logs/sft_8gpu_20260819T120245Z.log:1914) |
| SmolVLA 底座 | [训练配置](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints/050000/pretrained_model/train_config.json)、[实际步数](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/artifacts/vla-baselines/runs/metaworld/smolvla/mt50-smolvla-s42-mb-20260912-v1/checkpoints/050000/training_state/training_step.json)、[训练日志](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/artifacts/vla-baselines/coordination/20260912/machine-b/mt50-smolvla-s42-mb-20260912-v1.log:424) |
| X-VLA 底座 | [训练配置](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/jobs/xvla_mt50_s42_D24_r2/training/checkpoints/030000/pretrained_model/train_config.json)、[完成摘要](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SPRINT_V1/r1/XVLA_TRAINING_COMPLETE_SUMMARY.json)、[优化器分组](/mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/projects/upstream/lerobot-xvla-8fff0fd/src/lerobot/optim/optimizers.py:198) |
| π0.5 D/G0 | [原配置](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_future_aware_20260914/config.json)、[切点统计](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/outputs/act_recap_future_aware_20260914/audits/train.json)、[窗口采样](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/data.py:28)、[D 更新](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/training.py:88)、[G0 更新](/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src/ac_tmil/future_aware/critic.py:128)；成员完成回执路径另见 [PI05_AUXILIARY.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/training_history_audit_20260926/PI05_AUXILIARY.json) |
| π0.5 完整 Q | [配置](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/config/TRAIN.json)、[训练代码](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/code/train_pair.py:28)、[训练完成记录](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/TRAINING_COMPLETE.json) |
| Smol D/G0/首轮 Q | [数据统计](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/DATA_SUMMARY.json)、[训练完成记录](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/FIT_SUMMARY.json)、[数据构建](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/code/prepare_data.py:29)、[训练代码](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_SMOL_AUX_RETRAIN_V1/code/train_head.py:51) |
| Smol 完整 Q | [bootstrap 与 batch](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/code/prepare_q.py:22)、[训练代码](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/code/train_q.py:32)、[完成摘要](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_FULL_Q_LOSS_REFRESH_V1/fit_r1/FINAL_SUMMARY.json) |
| X D/G0/首轮 Q | [数据统计](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1/DATA_SUMMARY.json)、[训练完成记录](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1/FIT_SUMMARY.json)、[数据构建](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1/code/prepare_data.py:29)、[训练代码](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1/code/train_head.py:49) |
| X 完整 Q | [配置](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/config/TRAIN.json)、[bootstrap 与 batch](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/code/prepare_cpu.py:20)、[训练代码](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1/code/train_fit.py:12) |
