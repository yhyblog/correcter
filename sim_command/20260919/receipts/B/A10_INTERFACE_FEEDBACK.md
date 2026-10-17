# B10 → A10 接口反馈（准备中）

B10已领取P00_PREP_V1，B00 complete。B在独立work目录准备GAF-v1、LVM、E6和E1接口，不改公共runner。

- GAF冻结公开commit `ee67a70e576dc7f02a00cff86c9dd97f868c896f`，MSE / discounted success-to-go；native E3在每次采样中引导，不挂G0一次报警门。
- π0.5生成50、实际H10：GAF只引导前10步×物理4维，剩余时域和padding保持原velocity；每次flow/critic调用分别记账。
- 轨迹视图需parent/source/branch/suffix、episode级split、state/action实际执行序列、逐步success与真实obs/next引用；GAF须完整结局标记，不能把未结束cut后的未知未来标成失败。
- A00确认旧trajectory有reward/success/done但无逐步RGB/完整obs且done未拆terminated/truncated。请保留missing_reason；公共原始池不能自动宣称已满足所有baseline。
- E6使用D5已发出预测与5步后实际到达的同一动作序列窗口，开发集按episode干预比例匹配G0，测试阈值冻结，统一下游R且最多一次。
- LVM需要256×2048 token的(t,t+10)正常动态视图；旧帧随机split需改为公共parent分组，记为数据适配。
- 请公共schema区分完整E3原生频率与E6一次干预；完整VLA采样失败、进入/返回事件都需保留。

等待 `results/A/A10/interface_v1/INTERFACE_READY.json`，到达后B将核对SHA、消费示例并追加兼容性结果。

## v1 消费与兼容性结果（2026-09-19T15:46:36.972018+00:00）

上文等待状态已解除。已消费 `corrector-sim-interface/1`；READY 中 README/schema/examples 三个 SHA 全部一致，schema=`7d52f22e9d2e622a18a9a71fdac822ed50413aa3838aa3ad40d98e0bee10500f`。

- 27 项 CPU 检查通过，A 七类样例与 B 的 23 条合成记录通过同一 schema；证据 `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z/evidence/CPU_CHECK_RESULT.json`。B 原样使用 v1，未修改 A 文件。
- `resource_units` 在 entered/returned/failed 保持同一操作元数据；仅去重后的 entered 计一次。已对照 A 工作区 accounting.py 的冻结副本验证成功、部分失败、末事件缺失、复用引用不重复计费及 N shadow 排除。A 工作区副本 SHA 见 `a_accounting_snapshot/PROVENANCE.json`，不是声称 A 正式 runtime 已发布。
- B 增加 entered-before-call 的 fsync 日志绑定；真实接入必须调用 attach_durable_public_journal 或桥接 A EventJournal。默认内存 ledger 仅供 CPU 样例。
- E3 用完整事件流和可变 decision_index/sampling_index，可表达每次采样引导及反复截断。episode 单值 cut/entry 仅摘要；多次 E3 的摘要可 null+原因，不限制真实事件次数。
- 首次成功按 A 的动作后状态时间 step+1；GAF 原代码 action-index 折扣为 gamma**(first_success_state-start_step-1)，没有把50步生成长度冒充10步真实转移。
- 数据缺口：GAF 滑窗与 LVM 配对需要真实逐步 observation_ref/next_ref。当前聚合 prefix>1 的端点记录可合法归档，但若无中间观测 sidecar，B 拒绝展开为逐步训练数据。建议 A 新采集写 prefix1 记录或冻结逐步引用索引；不要求修改 v1 schema。
- GAF 还需四维 policy-preprocessed state 与 frozen pi05 task embedding 的真实值及提取代码/normalizer SHA。原始 proprio 字段不自动等价于规范化后的 policy state。
- E6 需要同一真实分支 s 时已保存的 D241/242 预测及 s+1..s+5 实际4096维特征。缺失、动作不同、reset不同均 score=null/no alarm，覆盖率另报；阈值目前 null，不能以示例值当成已校准。
- 接口本身无阻塞；真实 GPU/仿真接入仍需 A 冻结 driver、共同 manifest、D/feature 绑定、有限 release。B 有可执行2次 LVM GPU预检命令，但未执行；联合 A/B wave 必须先有共同完成/失败屏障，B 单机命令拒绝联合wave。
