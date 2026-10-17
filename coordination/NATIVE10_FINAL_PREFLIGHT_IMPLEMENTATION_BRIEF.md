# 最终跨协议零更新模型预检：实现准备

2026-09-16。分析端认可已完成的66项合成输入接口检查。当前 `final_prepare` 生成pending规格；下一项可并行工程任务是补齐真正消费联合输入的零更新模型预检执行入口。当前只实现、审查及合成CPU验证，不运行真实PCA/模型初始化/推理/优化；真实执行待300槽收尾和联合输入通过后，由新READY绑定完整seal放行。round2当前冻结与运行不变。

## 必须保持的科学约定

1. 消费独立 `input_bundle_sha256`，验证两轮train子包及原dev100的真实协议/config/freeze、生成critic、canonical定义、purpose/round、source/scene/replacement身份。旧单协议断言由新的明确联合输入验证替代，不能伪改子包字段或跳过输入检查。全部实际输入审计通过后才允许真实预处理与初始化。
2. A从原旧四成员重新开始，沿用旧PCA/ActionTransform/状态及base冻结部分，只开放既定residual/advantage参数；B使用所有唯一有效train源拟共享vision16/language8 PCA后全新初始化小MLP。大VLA/D/特征提取器保持冻结。保留原floor、数值容差和特征定义。
3. PCA先于source bootstrap，每有效训练源一次；dev不参与。按任务有效源数N有放回抽N，四成员各保存完整bootstrap、训练minibatch种子/计划及trainable masks。保留600计划槽与实际有效源数的区分；不按轮次、teacher或收益加权。
4. 在任何优化之前完成A/B全部8个初态检查。封存canonical特征/概率/动作梯度的重载证据：13候选概率、既定槽0/11动作梯度，成员与集成均核对；a0相对优势严格为0。审查singleton与批量计算的一致性，使用原冻结数值约定，不为让检查通过放宽容差。明确实际检查的train/dev有效源集合，保留dev100选择分母。
5. 输出独立、不可变的PCA/变换、8成员初始权重、bootstrap/minibatch依据、mask及预检报告。正式fit随后必须复用这些封存初态和预处理，不重拟PCA或另生成未绑定的初始化。

## 权限和运行接口

- 预检拟使用独立stage/scope `final_fit_preflight`，simulator=0、optimizer=0。不得靠记一次虚假优化来满足旧预算入口的正数要求；需要真实的零资源权限检查。该stage目前尚未正式放行。
- 预检的独立prepare、config、代码快照与READY绑定必须覆盖实际跨协议执行入口。当前pending规格或旧round1执行器都不能代替最终真实预检封存。
- 最终训练仍是后续独立阶段 `training_final`，最多32000优化更新、0仿真；工作流优化总上限51200。损失1/1/0.5、A/B学习率和可训练范围、每成员最多4000步、固定检查点及原100dev选择规则沿既定ADDENDUM。
- 预检、训练和第二次实际开发策略测评各自记录成本与资源；检查程序通过不自动启动下一阶段。现在可完成必要的合成CPU测试并提交简短接口/冻结准备摘要，不需为工程实现另等用户许可。

本简报与 `NATIVE10_FINAL_INPUT_CONTRACT.md` 配套。若复用的数值实现确实无法支持上述检查，执行端报告具体差异，分析端据真实限制决定；不静默改数据、参数或容差。
