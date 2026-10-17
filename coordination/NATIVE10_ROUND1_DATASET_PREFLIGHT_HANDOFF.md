# 首轮完整数据与零更新预检交接

2026-09-16。首轮400主槽采集、正式静态train/dev审计及READY v5零优化器更新预检均已通过。当前模型尚未训练；这些结果证明输入与数值链路符合协议，不证明纠偏有效。方法判断、优化器训练及后续仿真仍由分析端按阶段放行。

## 完整数据与预算

| 用途 | 计划episode | 有效critic源 | 合法无cut | capture / bank / branch | 引用attempt |
|---|---:|---:|---:|---:|---:|
| train round1 | 300 | 300 | 0 | 300 / 300 / 16800 | 17400 |
| development | 100 | 95 | 5 | 100 / 95 / 5320 | 5515 |
| 合计 | 400 | 395 | 5 | 400 / 395 / 22120 | 22915 |

五个dev无报警源保留完整正常共同结局，开发总体分母仍100；只因无cut不进入critic候选数组。所有300/100主槽终态齐全，400个物理初态唯一，无替补、无未知缺失、无技术错误。train/dev目的ID及有效数组ID交集均0。PCA、损失及source bootstrap只使用train；dev仅供后续预登记checkpoint选择，校准/held/第二轮尚未初始化。

冻结后完整审计核对train 72782、dev 22999个输入产物，包含source/bank/branch seals、真实raw→critic映射、四配对后缀、alias/正反对、scene/replacement链及ledger引用。两用途引用同一静态ledger，引用集合无重复、无交集，并集精确为本轮22915。完整审计约301.96秒，正式数据包另由独立子任务核验pack/seal/ID及attempt集合；没有把3源smoke seal用于正式输入。

全账本仍 **23479/50000＝P0 564＋本轮22915**，技术储备0/1200、优化器更新0。预检前后ledger字节SHA相同：`59366c2e08f34f1914b721e16111d1324b07cad187eab343efc21a460576d44f`。第一轮采集低于23200阶段上限；合法无报警减少实际计数不意味着自动授权额外搜索。

采集32/32 worker正常结束，整波lifecycle墙钟7834.785秒（约2.18小时）；这是实际整波成本，不是32worker四倍加速声明。八卡holder已恢复并保持。完整性收尾独立记录见 `NATIVE10_ROUND1_COMPLETION_CHECK.md`。

## 真实零更新预检

新协议 `fit_protocols/round1_preflight_v1` 绑定live READY v5 SHA `f060993392cb4e776b5d2694fc4ceb4a62ee0fbbc788f269565ef390d58cef49`。原采集READY v4、config/freeze和全部冻结依赖不变。预检仿真/优化预算严格0/0，运行CPU float32、PyTorch两线程；实际完成至seal约190.80秒，进程退出码0。

- A保留原四成员权重及投影，每成员7058参数中2529个residual/advantage参数可训练。
- B新初始化四成员，7058个小MLP参数全部可训练。新PCA仅拟合300个唯一train源，视觉16维、语言8维；未用bootstrap重复源或开发特征拟合。
- 视觉投影无尺度下限命中；语言8分量中4个近零分量命中预登记1e-3尺度下限，clip比例均0。没有改维数、放宽容差或改变方法。
- A/B八成员全部对300源核验canonical特征、13候选成员概率；a0和post槽（0/11）的成员及集成动作梯度保存重载逐位一致。a0优势精确0，固定state/a0不变。
- 离线float64集成与在线float32增益的最大汇总差：A `5.2154064e-8`、B `0`；按预登记口径单独报告，不把汇总精度差混同成员重载一致性。
- 八份source bootstrap/minibatch seeds、可训练参数mask、PCA及初始权重均封存。后续正式训练必须绑定这份预检，并直接加载同一初态，不重拟PCA、不重新初始化。

CPU autograd日志保留一次环境CUDA探测warning；预检设备为CPU，全部数值审计通过，未执行GPU模型工作。未调用优化器或新增仿真。

独立只读验收随后通过：顶层22文件和A/B子seal哈希匹配，八份真实模型初态已载入核对。A四成员所有state tensor与对应旧权重逐位一致；B各MLP模块采用新权重。八份bootstrap按已登记seed独立重建相同，每份300次整源抽样、每任务60次；A不同源数193/187/182/194，B为192/184/198/191，符合有放回source bagging。验收未重跑PCA/预检、未新增训练，未发现异常。

## 精确交接绑定

以下路径相对 `outputs/native10_training_20260916/`：

| 产物 | SHA256 |
|---|---|
| `datasets/round1_train_full_v1/complete.json` | `08d8bf56408f65dc4302a588be987626ea2d4f420ab3a156c8c360ef8a7fd14a` |
| `datasets/round1_development_full_v1/complete.json` | `ff4084fa637fc5c50cbad1ee2010084d7b2658f42902700069b09ec71fdf8865` |
| `dataset_audits/round1_train_full_v1/input_audit.json` | `7de6ee45b9ee8bd68e9ba082d55a973b02a55741bc3a12c11e2d4ca472d9c1db` |
| `dataset_audits/round1_development_full_v1/input_audit.json` | `b540489d63ad00b23fa183f4b4d47f268df8d444eafa0c6a527e2254cbc2876b` |
| `fit_protocols/round1_preflight_v1/config.json` | `ae9f8ca468f6493bb46f943070b347c52b017c16f962e0ca8153fde81cfba2d3` |
| `fit_protocols/round1_preflight_v1/freeze.json` | `ad23f3862d5f2b8da6cba231d238a496e353c6f6610357b085bc06483a8fb600` |
| `fit_preflight/round1/round1_preflight_v1/complete.json` | `3a97fff5235b804ec05afd6cc4dc6f25e89319c393d2fa21f70eda2296ed3930` |

正式训练可用binding：`preparation/round1_preflight_execution_v1/preflight_binding.json`。正式数据bindings及purpose实际ID清单：`preparation/round1_dataset_audit_v1/{train_binding.json,development_binding.json,result.json}`。两个阶段的command/log/result均有独立seal，旧产物不覆盖。

预检明细：`fit_preflight/round1/round1_preflight_v1/{result.json,pca_fit_audit.json,sampling.json,trainable_masks.json,A/reload_audit.json,B/reload_audit.json}`。首固定50源分析及requested/actual/fallback分层仍见 `NATIVE10_FIRST50_EXECUTOR_HANDOFF.md`，未因本次技术预检改半径、配额、loss、门控或选赢家。

执行端建议：输入和数值链路已满足本轮fit-before要求，可由分析端独立复核此seal后，明确释放 `training_round1 → round1_critic_training` 并绑定上述同一初态。实际开发部署另按预登记一次100×5×4及阶段READY控制；本报告不启动未放行阶段。
