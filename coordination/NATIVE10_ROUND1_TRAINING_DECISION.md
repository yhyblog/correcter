# 第一轮正式 A/B 训练：分析端放行

2026-09-16。完整采集、静态数据和真实零更新预检均通过独立复核，**放行第一轮 A/B critic 训练及既定开发银行上的检查点选择**。本阶段不产生新仿真，不放行第二轮、实际开发策略 rollout、校准或 heldout。

## 1. 放行依据

- 400 个预登记槽位完成：300 train、100 development；400 个实际初态唯一，无替补。395 源有合法 cut，5 个 dev 无报警源保留共同结局及完整分母。
- 400 capture＋395 bank restore＋22120 branch＝22915 次主阶段尝试；加 P0 564，总计 23479/50000，储备使用 0。比上限少 285 次对应 5 个 dev 无报警源各省 57 次，没有缺失分支。
- 静态数据的全部必填检查通过，包括 scene_identity、replacement_chain、raw 映射、alias、配对后缀及 attempt 绑定。train/dev ID 无交集。
- 真实预检使用 CPU float32、两线程。B 的 PCA 仅拟合 300 个唯一 train 源，视觉16/语言8维；语言4个低方差维度使用既定0.001下限，投影clip比例为0，没有见结果后调整维数或容差。
- A/B 共8个初始成员在全部300个train源上完成13候选成员概率重载检查；动作梯度检查覆盖预登记槽0（a0）与11（post），成员及集成均逐位一致。不是对所有候选梯度位置的穷尽验证。A 的离线float64/在线float32集成gain最大差5.2154e-8，按原约定单独报告；B为0。
- 每成员的bootstrap均为300个train源、各任务60，含既定重复，不使用结果加权；A仅residual/advantage可训练，B全部小critic MLP可训练，buffers与大模型保持冻结。预检仿真0、优化更新0。

## 2. 数据支持训练，但不代表已经改善模型

全300训练源的旧critic下，replan成功率49.33%，velocity/direct/post为50.25/49.92/50.75%；相对replan仅+0.92/+0.58/+1.42pp，源级区间均跨0。109/300源提供候选标签差异，56源有至少一个更优候选。实际报警组与scheduled组的收益方向不同，保留全部负例和原source-uniform权重，不依据这些训练结果挑方法或删源。

本轮学习目标是13候选的成功概率、相对a0增益及正反差，重点检查方向辨别和损害控制。normal控制不进入critic候选，G0本阶段不更新；训练不会自动获得“继续旧队列还是中断”的新决策器。后续实际策略评价仍分别报告 I、A、T。

## 3. 精确训练范围

- scope：`round1_critic_training`；budget stage：`training_round1`；phase：`round1`。
- A/B各4成员，每成员最多2400个优化更新，总上限 **19200**；本阶段 simulator attempts 上限 **0**。全工作流优化总上限51200、仿真硬上限50000保持不变。
- A加载预检封存的旧投影和初始权重，只更新residual/advantage，lr=1e-4；B加载预检的新train-only投影和随机初始权重，更新全部小critic MLP，lr=3e-4。大VLA/D/视觉语言提取器不更新。
- AdamW weight_decay=.01，gradient_clip=1，batch=32完整source；损失BCE/gain MSE/正反概率差MSE权重1/1/.5，保持原mask、alias去重与源内/源间归一化。
- 使用预检封存的8份任务分层bootstrap和minibatch seed，不重新抽取、拟合PCA或生成初始化。数据、设计、代码、投影、初态、抽样和可训练mask均须匹配预检绑定。
- 检查点固定200/400/800/1600/2400。在同一100源开发银行上按已登记预测赢家的真实配对净增益选一个A/B集成检查点；a0候选并列优先，检查点并列依次少harm、低gain MSE、较早步数、B优先。5个无报警dev源保留共同结局，不进入优化或PCA。

## 4. 必须复用的封存身份

所有路径相对 `Corrector/`。权威绑定同时写入 READY v6。

| 产物 | SHA256 |
|---|---|
| `datasets/round1_train_full_v1/complete.json`（位于本工作流outputs下） | `08d8bf56408f65dc4302a588be987626ea2d4f420ab3a156c8c360ef8a7fd14a` |
| `datasets/round1_development_full_v1/complete.json` | `ff4084fa637fc5c50cbad1ee2010084d7b2658f42902700069b09ec71fdf8865` |
| `fit_preflight/round1/round1_preflight_v1/complete.json` | `3a97fff5235b804ec05afd6cc4dc6f25e89319c393d2fa21f70eda2296ed3930` |
| 同目录 `result.json` | `add02eae9a61d3576981197910132bffa35afdc3983cc99c8ec7995c72c0d0fe` |
| `fit_protocols/round1_preflight_v1/training_design.json` | `3b9bbf7a67fc15123ac761c13358c0bfd8492ea9aea3c25649cefb02c66ef0cf` |

上表短路径均位于 `outputs/native10_training_20260916/`。正式训练另建独立协议，绑定新的 READY v6；采集v4与预检v5的冻结产物只读。训练配置应复用预检的同一设计内容和输入身份，授权状态更新放在新配置/READY中，不要因刷新design元数据而意外破坏预检的设计SHA绑定。

## 5. 运行与完成交接

执行端通过现有入口冻结正式训练配置并开跑，无需用户再次许可。使用现有预算账本记录实际优化更新；失败与技术修复如实保留，不能重开同一版本隐去已发生更新。正式GPU工作经lifecycle；CPU训练时保持空闲GPU holder。

输出A/B各成员训练记录、检查点开发指标、固定规则的选择理由、所选模型及导出SHA。**训练后所选critic还需概率和动作梯度的导出重载检查**，不能仅引用零更新初始化的检查。现有run已实现：在95个有cut的dev源上核对13候选概率及槽0/11动作梯度，并核对开发选择指标，写出 `selected_reload_audit.json`；直接提交该实际产物，100计划分母仍保留。

完成后交分析端复核并冻结所选critic，再放行既定一次100源×5臂×4后缀的实际开发策略比较。实际开发比较上限2100尝试，不在本次scope中执行；第二轮300训练源也须使用后续冻结的所选critic。本次不以离线候选选择成绩宣布真实flow引导改善。

## 证据

- `analysis/round1_collection_completion_review.json`：采集完整性和预算独立复核。
- `analysis/round1_train300_20260916_review.md`、同名JSON：完整训练源方法诊断。
- `analysis/round1_prefit_independent_review.json`：真实数据、PCA、8成员及封存独立核验。
- `outputs/native10_training_20260916/preparation/round1_dataset_audit_v1/`：执行端完整静态数据审计。
