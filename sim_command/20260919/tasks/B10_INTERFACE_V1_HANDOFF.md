# B10：A 接口 v1 已发布，请接入

这是 B10/P00_PREP_V1 既有 CPU 准备任务的共享交接补充，不新增 GPU、仿真或训练权限。

接口入口：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10/interface_v1/INTERFACE_READY.json`。

分析端已核对 READY 中三份文件的 SHA；schema SHA 为 `7d52f22e9d2e622a18a9a71fdac822ed50413aa3838aa3ad40d98e0bee10500f`。引用冻结见 `manifests/PUBLIC_INTERFACE_V1.json`。发布者报告七个显式 synthetic 样例通过 Draft2020-12；这不替代 B 适配兼容性检查或未来真实链路预检。

请执行：

1. 核对 READY、README、schema、examples 身份，记录实际消费的 `corrector-sim-interface/1` 和 SHA。v1 不原地修改，有缺口写反馈，由 A 发布新版本。
2. 按七类 record 对齐当前隔离适配；真实缺失字段保留 null 与原因，不能用 synthetic 示例填真实数据。
3. 针对已有 B 数据视图和事件样例做 CPU 兼容性检查，重点核对 parent split、真实 prefix、event_id 的 entered/returned/failed 计数、双账本及 N shadow 排除。
4. 检查 core 单次干预语义不会错误限制 E3 GAF 原生每次采样引导或 VLA-Corrector 原生频率；E6 才是两触发器同接 R、最多一次。若 schema 无法表达已冻结方法，作为接口阻塞反馈，不把外部算法改为 G0 一次门控。
5. 将消费确认、适配检查结果、具体差异/阻塞追加到 `receipts/B/A10_INTERFACE_FEEDBACK.md`；B10 最终回执引用这份反馈。准备有限预检命令，暂不执行。

同时读取 `contracts/INVENTORY_DECISIONS_V1.md` 和最新 `contracts/STORAGE_RETENTION_V1.md`。存储候选只报分析端，所有删除均等具体路径决定；不影响本接口准备继续。

有限语义审查确认 schema 可以表达 E3 多次决策及 E8 独立维度；集成前需澄清的摘要/事件计费规则见 `contracts/INTERFACE_V1_INTEGRATION_NOTES.md`，纳入当前 CPU 检查，无需等待新实验。
