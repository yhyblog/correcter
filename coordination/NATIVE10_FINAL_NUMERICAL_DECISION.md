# 最终预检数值口径：canonical严格验收与dense诊断

2026-09-16。针对 `preparation/final_numerical_contract_cpu_20260916_v1` 的分析端决定。本决定明确新预检/装载入口的验收语义，供独立实现与下一次冻结使用；当前采集与已封存代码不变，真实模型预检和训练仍未放行。

## 1. 明确决定

**采用“原canonical同shape严格验收；dense跨shape差异独立报告”的口径。** 不新增atol/rtol，不将现有bitexact改成allclose，不改变训练batch算法、dtype、PCA floor、梯度规则或模型结构。

解除仅由 `dense != singleton` 的逐位差异导致的 `pending_numerical_review` 阻断。新preflight/load/fit可以接受“canonical严格检查通过、dense差异已报告”的明确状态；不能把它重命名为“dense逐位一致通过”，不能因此跳过其他模型、输入或权限检查。

真实预检产生的差异仍须随封存结果交分析端审阅后，才放行正式训练。这里没有预先批准任意规模差异，也没有建立实数据误差上界；单纯存在非零dense差异不再是失败条件。

## 2. 依据与证据边界

原 `training_pipeline` 的重载验收明确使用identical shapes及原singleton双槽 `[a0,candidate]` 运算。13个候选概率沿既有逐源canonical路径收集；动作梯度检查槽0和11。训练原本使用batch loss，推理/选模沿原逐源路径。此前没有要求两种不同batch shape数值逐位相同。

独立结构检查确认：本次dense成员梯度对逐源gain求和，ensemble先平均成员再对源求和，没有多出1/N缩放；MLP为Linear/SiLU，无BatchNorm或Dropout；归一化与历史聚合只在单源内部。上游observed特征完全相同，差异从矩阵投影出现。这与有限精度下的运算路径差异相容，不能据此单独断言真实模型在所有状态上的决策均不受影响。

[PyTorch 2.7官方数值精度说明](https://docs.pytorch.org/docs/2.7/notes/numerical_accuracy.html#batched-computations-or-slice-computations) 明确：浮点运算顺序会影响结果，batch与逐片计算即使数学上等价，也不保证逐位相同。这不是放宽同路径导出/重载身份检查的理由。

当前只有5个合成源、4个随机小MLP、seed2026091607、F32 CPU2线程。最大差为：projected features 1.6093254089355469e-6；概率5.960464477539063e-8；成员梯度槽0/11分别1.3969838619232178e-9/1.862645149230957e-9；ensemble两槽均4.656612873077393e-10。raw/observed特征差为0。原canonical同shape概率/梯度/cache重载全部bitexact，1 ULP坏缓存被拒绝。

这些数值仅描述该次合成检查。本次数值记录使用Torch2.6.0+cu124、NumPy1.26.4；首轮正式预检记录为Torch2.7.1+cu126、NumPy2.2.6。当前代码SHA仅事后记录，不能称before/after/current全一致。原日志、warning及这些限制保留；不追改归档事实。

## 3. 继续硬性阻断的事项

- 相同输入、形状、冻结环境和canonical路径下，导出/重载的特征cache、13概率、槽0/11成员或集成梯度不逐位一致；包括仅1 ULP的缓存损坏。
- NaN/Inf、输入来源/shape/顺序错误、错误的source/member轴、意外1/N梯度缩放或真实跨源耦合。
- state/a0被候选求导改写，指定a0未按既定方式detach，或a0的相对优势不严格为0。**a0处相对优势为0不意味着该点动作梯度必须为0。**
- PCA、ActionTransform、floor、dtype、模型身份、trainable masks、bootstrap或其他冻结约定漂移。
- 模型预检/训练的真实阶段权限、完整数据与seal绑定、资源检查未通过。

不能通过替换cache、转dtype、改单例训练、调整线程/floor或改损失来强行消除dense差异。需要变更算法或运行配置时须单独如实说明。

## 4. 真实预检的dense报告要求

保留实际检查的源ID与数量、batch形状、dtype/device/软件版本/线程数、模型与输入身份。分别报告上游observed、projected features、13概率、槽0/11成员与ensemble动作梯度的差异与非有限值检查；记录绝对差和参考值尺度，必要的相对量须说明近零处理，不能以未定义相对误差掩盖问题。

报告仍按真实模型/实际有效train和dev范围生成；合成误差不作为阈值，也不改用标签收益选择“容易一致”的样本。预测选模及部署继续使用原canonical路径，不因dense报告自动切换推理算法。发现语义、缩放、状态修改等实质问题仍按上一节阻断并报告。

正式预检与随后fit须冻结并记录其实际软件环境及数值路径，保持一致；若与首轮正式环境不同须显式说明。不能将跨PyTorch版本、CPU/GPU或不同shape的结果包装成同条件bitexact重载。

## 5. 实施与后续放行

执行端现在可在独立新模块中落实上述状态/检查逻辑，继续完整跨协议预检与封存装载接线，完成相应合成CPU检查。记录本决定SHA并纳入未来真实预检的新config/代码/READY冻结。无需再为这一个dense非逐位一致问题等待许可。

这项数值决定不启动真实PCA、模型初始化/推理、优化或额外仿真；仍按全部300槽收尾→静态数据与联合输入审计→正式零更新预检READY→训练READY的既定顺序推进。

证据：`outputs/native10_training_20260916/preparation/final_numerical_contract_cpu_20260916_v1/result.json` SHA `8a0ec08be89a89a230bc85fbcf65da94a7abf1c8cba2a790d9ecd11be3cba2cd`；首轮正式预检 `fit_preflight/round1/round1_preflight_v1/result.json` 的 `numeric_runtime` 字段。均未重跑模型或修改旧封存。
