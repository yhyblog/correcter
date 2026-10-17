第二次开发五臂测评的隔离工程准备已完成；真实测评尚未启动。最终训练已完成且唯一选择固定 A4000，本材料不重启 final fit。

新 prepare、guard、runner、shell 与 audit 位于 experiments/native10_training_20260916 的 round2 独立模块。prepare 的 inputs/freeze 首先检查显式 round2_development_policy READY；live v10 仍只释放已完成训练，无法通过该入口启动策略阶段。pending 元数据不是 READY，也不是可运行 config。

实际接线为 policy5_round2_prepare_v1 → policy_deployment_round2_v1.validate_deployment_inputs → policy5_round2_runner_v1 → create_policy_collector/collect_existing_slot → 原 MainCollector。新 worker 保存实际 selector 路径、四权重 SHA 与只读状态核验。首次 branch 前核原 raw50 a0、初噪声、mask、tail、critic C(raw) 与本轮 V/D/P 同幅。动作/噪声/匹配/账本包装的六段核心实现与旧版 AST 相同，未新增 Q 门、半径、alpha、G0 或接受规则。新审计直接引用原 summarize 与后缀身份函数，并拒绝本阶段任何优化记账。

原 dev100 身份与顺序、每任务20个物理初态、95cut 和5共同结局（4成功1失败）保持。source/case/旧银行 provenance 仍为 round1；仅新银行 generation_round=2、生成critic=A4000。原100 source、100 resolution、95 bank的seal绑定已核，四个selected权重只作字节SHA核对，未反序列化模型。原开发dataset/audit身份保留，没有读取旧候选结局重新选模型，没有新capture/替补/第六臂/旧guided复用。

配对键保留原namespace/source/cut/repeat/decision_index，候选和后缀seed不含critic/stage/bank/worker；新bank_version改变分支执行排列。主结果仅本轮五臂内部七比较（I、三个A、三个T），完整100源分母，任务分层整源bootstrap10000次/seed2026091622/percentile95/linear，无多比较校正。不据同源先宣称跨轮配对因果收益。

统一合成CPU检查41项通过（pytest16.09秒，进程墙钟18.14秒），覆盖stage拒绝、A4000/审查身份、100/95+5输入、raw/noise/mask/匹配、禁止capture/替补/优化、实际新runner接线/错误不重试、统计函数复用和pending。新prepare自身CPU证据入口亦通过。11个受测代码/控制文件前后SHA一致，34份旧冻结代码/config/freeze核验未变。没有重复模型预检或真实fit。

预期95bank restore+1900branch=1995次，阶段硬限2100；0优化/capture/替补。累计仍42,874/50,000仿真、51,200/51,200优化、technical reserve0，账本逐字不变，八卡holder保留。实际新bank与真实轨迹尚未生成，CPU准备不能当真实策略验证。交接构建首次曾因报告字典字段重名报错，写入前已修复并保留控制日志；无正式计算失败或资源影响。

- CPU证据：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/preparation/round2_policy_cpu_20260917_v1；seal `8dff6d4fba6b04c0a3673f6a42e5873aca659729c547388749801c4074ad0db1`。
- Pending输入：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_preparations/round2_policy_pending_v1；seal `f81ea00b85d3ccd936b68605db880eb9daef24f30afa6ede65d343db5ecaa7f7`。
- 未来READY阶段契约：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_preparations/round2_policy_pending_v1/ready_contract.json；SHA `ee4480883eb7acd25da146286c5550f945ff50efe647717609546d3fa685232f`。status为pending，guard_cpu_evidence留空供分析端绑定本次CPU证据；旧v7仅为不可变来源/统计模板。
- 原100槽canonical SHA `7febdc814dee2c203378865a8371de6698bc727e783ee537312dce734a37db89`。
- 最终selected seal `f40ff4f3356ee8f14d687348f9f9cc7addf1b1e93233b81645312973f7e02d6a`；selected reload SHA `b16b8183e6d6a69345375a266840afaffebf514873d62868f0327496bf795a92`。
- 完整代码SHA/模型和输入绑定：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_preparation_handoffs/round2_policy_v1/summary.json；READY绑定补充：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/policy_preparation_handoffs/round2_policy_v1/ready_binding_supplement.json。
- 控制结果：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/execution_control/round2_policy_preparation_v1/result.json；账本SHA `ef493c95d51a77eae82cdec142f63d0f63cb6805a9b676588274684e40213bee`。

后续获新READY显式释放并绑定材料后，通过新prepare inputs→freeze生成独立config/code/READY快照，再核验并由lifecycle启动一次既定8GPU×4worker测评。cal/held保持锁定；不重做最终训练或等待同一训练seal审批。
