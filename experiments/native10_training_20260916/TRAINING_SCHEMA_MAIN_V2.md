# Native10 主版本数据与训练接线说明 v2

P0 封存的 `training_design.json` 与旧 schema 保留。本文件及 `training_design_v2.json` 记录主版本最新要求；当前无主采集或训练授权，真实优化更新为 0。CPU 合成测试不构成真实数据数值审计。

## 最新已批准规则

600训练episode（300+300），100开发、100校准、100保留；原五任务、VLA/D/大特征提取器固定。训练cut按50%首次合法报警、50% scheduled 15/45/95预登记。从初始native10，正常臂finish-current-10；raw a0加可行delta，critic使用原C映射。

训练早期合法anchor保存5/15/45/95。scheduled fallback为15→5、45→15→5、95→45→15→5；首次报警组整集没有合法报警才按15→5。只选已观察、非终止且剩余预算≥10的anchor；保存requested_cut、actual_cut、selection_reason及可选anchor清单；无合法cut保留计划记录，不换seed。开发、校准、保留不使用训练fallback。依据 `coordination/NATIVE10_ANALYSIS_LEAD.md` 第3节。

13候选及独立normal的4后缀标签，每源最多56条；a0为第0槽。raw命令完全一致才允许alias，必须同状态、同repeat后缀种子与模型协议。缺失标签不填0；训练行需四个完整配对标签。源内distinct动作/正反对加权后再对源平均。损失权重BCE/gainMSE/pairDiffMSE为1/1/.5，不除以半径。

A从旧4成员重新warm start，只训residual/advantage；B全部小MLP重新初始化，当前阶段唯一有效训练episode上拟合16/8 PCA，再做source bootstrap，四成员共享train-only投影。每成员round1最多2400、final最多4000，总51200更新上限。CPU float32/2线程、singleton预处理；开发候选bank只做模型选择，不拟合PCA。完整参数见v2 JSON。

## 独立实现接口

- `main_collection.py`：版本化banks/rollouts、训练fallback与主stage权限；保留P0 adapter只读。
- `dataset.py`：封存source/bank/branch审计、完整计划coverage、raw/critic动作和控制分离、实际attempt和paired流引用；train/development目的分开，禁止提前读取calibration/heldout。
- `training.py`：去重损失、train-only PCA、分层episode bootstrap、A/B初始化和逐更新账本、离线checkpoint选择。
- `training_pipeline.py`：四成员编排、实际FrozenObjective概率/梯度重载检查、开发预测、ranking与权重导出；当前正在实现。

实现完成/测试状态以 `coordination/NATIVE10_EXECUTOR_STATUS.json` 和独立main CPU日志为准。后续CPU日志不会覆写P0冻结的cpu_checks。

## 真实fit与选择前审计

数据装载核对注册split/round、源与bank seal、raw→C映射、正反对称、完整4后缀及attempt引用；技术缺失阻断完整性声明。记录PCA奇异值、尺度、clip频率，验证保存重载后的单源预处理、成员概率、动作梯度与FrozenObjective。没有实际训练数据前不称上述真实审计已通过。

所有A/B检查点在同一100计划episode开发bank比较：预测赢家真实净增益、harm、gain MSE、早step、B优先。无cut共同结局保留总体分母。四成员float64概率汇总用于选择，在线目标float32；两者差异明确记录并验证部署重载排序。每轮只选一个critic跑100×5×4真实部署对照。轮2生成critic整轮固定。校准不训权重，保留集须最终模型/方法/接受规则冻结后才打开。

## 预算与权限

修订计划48800次，技术储备1200，总硬限50000；包含1100次主candidate-bank独立恢复。P0硬限600，正式主阶段仍需新的READY；预先注册预算不构成放行。失败、重试、独立restore均记账。原ACT-RECAP和上一批代码/产物只读；所有新模型/数据仅写本工作流新版本目录。


## EVAL20 最新修订与初态记录

依据 `coordination/NATIVE10_EVAL20_AMENDMENT.md`，train/dev/cal/held重复分别4/4/2/4，开发/校准/保留各任务20个不同物理初态。主manifest900，保留原800身份；另100新cal/held身份预登记，1800备用身份另列且不算已采样或计划测评分母。初态重复或初始化失败才使用每原slot两条有序备用，保留原拒绝attempt链；源group按实际episode，测评按planned_slot_id各一票。无报警、早成功、不可达cut均不触发替补。

`scene_identity.py` 在reset后首次policy动作前记录实际qpos/qvel、act、mocap、目标与model body/site/geom的位置和姿态。位置1e-6米、角1e-6弧度、线速度1e-6米/秒、角速度1e-6弧度/秒、规范化单位四元数1e-8、act1e-8。排除seed/RNG/time/计数器/未作用的random vector；原始完整物理数据和独立exact hash保存。哈希是上述固定网格规范化后的相等判定，不宣称任意欧氏距离1e-6内都等价。

跨主split同task scene hash相同即拒绝新条目；记录registry首个已接受scene与拒绝关系。初始化数据为审计专用，不进入critic。历史P0未保存完整model位姿scene记录，不冒充完成同schema全量去重；可仅作已保存初态+goal辅助筛查。held包括备用初态一律最终冻结后才reset。
