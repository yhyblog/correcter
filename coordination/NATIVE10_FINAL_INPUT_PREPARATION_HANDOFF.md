# 最终输入接口准备交接

按 FINAL_INPUT_CONTRACT（SHA `bceeccecbe2f5a41a27f05e8245ee8b9e68c525e8cb3d653a3460f275fab54a0`）完成三个独立新模块。原采集冻结不变，未读取第二轮中途结局作统计或调整。

| 模块 | 检查 | 行为边界 |
|---|---:|---|
| round2_dataset_audit_v1.py | 26通过 | 波次退出、32个实际B200身份、全部300槽处置、分资源完整账本先通过，才读取正式标签。readiness补充引用原round1封存SHA，保留round2真实protocol。 |
| final_input_bundle_v1.py | 20通过 | 独立input_bundle_sha绑定两轮train包/audit/config/freeze/生成critic、原dev100与canonical特征；不重标子包protocol，不拼PCA坐标。包含实际create/load到prepare的合成接口测试。 |
| final_prepare_v1.py | 20通过 | 只创建待放行规格；A从原旧权重/投影重新开始，B以后按唯一有效train做PCA16/8再初始化。记录实际有效源计数、各任务抽样数量/种子和用途隔离；当前不执行这些模型操作。 |

共66项合成CPU检查。已修复/覆盖原dev episode round=null、旧critic成员1041–1044与B200成员0–3身份、round2 full-completed-only审计兼容、dev推理源与完整100源选择分母分离。bundle v1中的一个场景去重负例误用跨task相同fingerprint，已纠正为同task重复；该失败日志保留，最终v2全通过，正式采集未受影响。

600仍是计划数。合法no-cut保留自然结局和计划覆盖，技术缺失不能声明完整。PCA每有效train源一次且先于bootstrap；后续bootstrap按各任务有效N有放回抽N，总N有效，不按teacher/轮次/Q/收益加权。normal独立，原source内部alias损失去重不变。原dev100保持独立，checkpoint_inference为有效cut源，checkpoint_selection保留全100（含共同结局）。

接口：`round2_dataset_audit_v1.run_audit(config_path, freeze_path, wave_id, version)`；`final_input_bundle_v1.create_bundle / validate_bundle / load_bundle`；`final_prepare_v1.prepare(bundle_binding, version)`。最后一个只生成pending规格，不是最终真实PCA/初始化/fit执行器。后续真实预检必须另有跨协议执行入口、完整代码冻结及明确READY，不能直接复用旧pipeline的单collection断言。

CPU证据及全部代码SHA：`outputs/native10_training_20260916/preparation/final_input_interfaces_20260916_v1/summary.json`。执行接线清单：`preparation/final_input_execution_plan_v1.json`。独立接口审查：`coordination/NATIVE10_FINAL_PREPARE_INTERFACE_REVIEW.md`。

全300槽处置且wave结束后，直接按已授权顺序创建新round2_train_full_v1数据审计/数据包、final_train600_input_v1联合包及final_pending_v1待放行规格；不另等静态审计许可。正式PCA/模型初始化/优化/dev2/cal/held继续锁定。此次准备新增仿真、真实PCA、初始化和优化均0，未创建正式600联合包。
