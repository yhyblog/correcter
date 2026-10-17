# 最终 600 源模型预检：分析端阶段决定

本决定的执行许可由后续 `NATIVE10_ANALYSIS_READY.json` 显式绑定真实输入与 specification SHA 后生效。当前文档单独出现不释放模型操作；不改变任何已封存采集、训练或测评。

## 方法判断

两轮计划训练源均已完成，每轮 300 源、每任务 60 源，合计 600 个有效训练源、每任务 120 源。联合训练含 31,200 个 critic 候选二值结局（600×13×4），另有 2,400 个 normal 分支作为控制；候选和重复后缀互相关联，不能把结局数量当作独立训练状态数或独立检验样本量。

第二轮候选由固定 B200 critic 生成，第一轮由旧 critic 生成。扩大状态覆盖并加入更新方向上的真实标签符合既定计划，但数据采齐与工程审计通过本身不证明纠偏收益提高。两轮生成器来源必须保留，不把训练轮次间的成功率差解释为训练的因果收益。

已封存联合包摘要为 train 600/600 有效；原 development 100 计划源、95 有效 cut，5 个无 cut 源保留共同结局及完整选模分母。两轮使用共同 canonical 原特征定义，不拼接不同 critic 的 PCA 坐标。监督诊断可并行只读开展，不按诊断结果换源、改损失、增加选择轮次，亦不作为零更新预检的新门槛。

## 本次可释放的唯一模型阶段

- stage 与 scope 均为 `final_fit_preflight`。
- simulator attempts = 0；optimizer updates = 0。
- 在独立真实 config/freeze 中绑定：两份 collection config/freeze/protocol、三份 child dataset/input audit、联合包 seal 与 `input_bundle_sha256`、pending/specification 与 metadata preview、实现及 CPU 证据、分析端真实输入审查、本决定及数值决定。
- 元数据 preview 不替代真实模型预检；真实输入验证全部通过后，方可执行既定 train-only PCA、A/B 初始化、数值推理与导出重载。
- 保留原 runtime：lerobot Python 环境，CPU float32、2 线程，Torch 2.7.1+cu126、NumPy 2.2.6。记录实际运行版本及成本，不把 PCA 或推理计为优化更新。若使用 GPU，遵守 lifecycle 与 holder 规则。

## 保持既定训练与数值方法

1. A 从原旧四成员权重及原 PCA 重新开始，保持既定冻结参数与 residual/advantage 可训练范围。B 在 600 个唯一有效 train 源上各取一次原特征拟合共享 vision16/language8 PCA，再全新初始化四成员小 MLP；开发数据不进 PCA 或 bootstrap。
2. 按任务进行 source bootstrap，每成员每任务有效 N 抽 N；当前为每任务 120、总计 600。保留源内去重及源等权，不按轮次、生成 critic 或观测收益重新加权。
3. 在任何未来优化之前完成全部八成员初态审查，封存 PCA、变换、初态权重、bootstrap、minibatch 依据及 trainable masks。未来 fit 必须复用并核实同一组封存资产。
4. 遵守 `NATIVE10_FINAL_NUMERICAL_DECISION.md`：同 shape canonical 特征、13 候选概率及槽 0/11 的成员/集成动作梯度导出重载严格逐位验收；a0 相对优势严格为 0，不要求其动作梯度为 0。
5. dense 与 singleton 的差异单独全量报告，不因单纯非逐位一致而失败，也不引入新 atol/rtol 或把 synthetic 差异上限当作真实数据界限。非有限值、来源/形状/次序错误、梯度错误缩放或源间耦合、初态变动等硬约束保持不变。明确真实审计覆盖的 train/dev 有效集合。

## 结束与后续边界

预检必须输出完整 seal、输入/规格绑定、实际数值报告、初态与采样资产、资源前后账本及成本。分析端审查真实 canonical 与 dense 证据后，另行决定 `training_final` / `final_critic_training`（最多 32,000 次优化、0 仿真）的释放。本次不释放最终训练、第二次开发策略仿真、cal 或 held。

当前工作流累计 42,874 次仿真、19,200 次优化，技术储备消耗 0；硬上限分别为 50,000 与 51,200。完成旧阶段的历史 scope 不构成重复启动授权。预检封存准备与条件核对通过后可直接执行一次，无需再次请求用户或分析端重复许可。
