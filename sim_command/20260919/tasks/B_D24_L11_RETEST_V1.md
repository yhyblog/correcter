# B_D24_L11_RETEST_V1 revision1 — 已授权有限正式L11重测

执行节点B，原会话01a0b9c5-1e4b-7b73-9336-229e6df349a2，host trial-303225685-trialrun-303225685-worker-0。读取本任务、本目录上级当前CONTROL，以及deadline_20260924/L11_RETEST_V1/AUTHORIZATION.json。用户已授权，不再按旧L01选择门或旧已完成预算拒绝新任务，也不等待第二次审批。

## 唯一科学范围

| 模型 | 分支 | 模式 | H/K | 新执行 | 精确复用 |
|---|---|---|---:|---:|---:|
| SmolVLA | Post | G0-multi | 10 | 500 | 0 |
| SmolVLA | Velocity | G0-multi | 10 | 500 | 0 |
| pi05 | Post | G0-multi | 20 | 500 | 0 |
| pi05 | Post | G0-multi | 50 | 500 | 0 |
| pi05 | Velocity | G0-multi | 20 | 500 | 0 |

唯一清单：`deadline_20260924/L11_RETEST_V1/prepared_by_analysis/NEW_UNITS_B.jsonl`，SHA256 `d361005183f1b070f57649c1988c9d368a8568280e1a3101047c5923e88df46e`；2500新episode。所有源/seed来自已有原协议；不要新增或替换源。仅执行owner=B。新task/run/claim/输出隔离，旧结果文件不改。科学单位key含model/source/method/mode/H/loss/fit；同一有效终局不得重跑。

## 模型及算法

固定L11=BCE+gain+0.5pair、fit9101、members1041..1044；具体已训权重见`deadline_20260924/L11_RETEST_V1/prepared_by_analysis/ASSET_REFERENCES.json`。复用现有模型/encoder/D/G0/归一化/投影，原冻结动作单位、G0阈值、检测频率、C10与恢复H、候选随机数流、Q引导公式均保持。Smol/X使用原专属头，不换成π0.5头。只需必要接口/动作单位/合法观测和真实结果检查，不做严格逐位一致性、巨量SHA、重复全测试或额外GPU预检；第一批计划episode即正式数据。

本轮7900新增之外的100复用记录在REUSED_UNITS.jsonl；仅A合并H10multi既有50/branch。复用的是同L11/fit9101结果，不是旧L01主结果。复用50参与L11选择，披露其与主500重叠，禁止宣称独立新盲测。新结果不得用于再次选loss/fit/阈值。

## 调度、资源与自动恢复

执行`deadline_20260924/L11_RETEST_V1/CONCURRENCY_192.md`：每卡24路独立活动分支、每台8卡、目标192；优先模型共享/批处理，不盲启192大模型副本。记录真实并发/模型副本/batch/资源。容量不足报告具体限制与最大可执行并发并继续有用授权任务，不能默认旧24全机，也不能只把24放进等待队列冒称并发。

先全部本机Post，后Velocity；同级可按模型降低装载开销。有限队列一次部署后自动衔接，零跨机退出屏障、零逐cell审批；本地旧健康任务不强杀，先确认本机正式族退出再接续。整正式wave全部holder停算，包括加载/间隙/空卡/尾部，整族退出后恢复原guard。

本任务最多2750episode attempts，首次科学单位2500；余量只用于真实技术缺项在明确私有修复后的恢复，不能重跑有效失败/成功。原累计预算加本次2750，不重置历史消耗。原故障/partial保留；同故障有修复最多2次重启，不盲重试。科学未知需报告分析，1800秒无可执行回应后保留并跳过阻塞项，其他独立任务立即继续。源/科学配置/所有权不能通过超时自行修改。12:00 UTC停止新准入，已准入有限工作按原约束排空。

## 输出与交接

先写`receipts/B/B_D24_L11_RETEST_V1_ACK.json`；私有结果`results/B/B_D24_L11_RETEST_V1/`，至少包括METHOD_FROZEN、实际CONCURRENCY/容量证据、逐episode结果/成功/技术缺项、调用/flow/干预/梯度/耗时（未知null+原因）、各cell分母与汇总、QUEUE_READY/STABLE_HANDOFF/终局事件、进程族退出与holder恢复。成本从本次结果重算，不复制L01数字。

部署后确认实际模型ready和正式结果推进，绑定原会话终局通知，写STABLE_HANDOFF并结束LLM等待；后台继续全有限队列。正常完整结果与工程恢复直接回执，不要求分析逐批再放行。终局写`receipts/B/B_D24_L11_RETEST_V1_RESULT_r1.json`和短REPORT，不能只投递“等待审批”。不要修改共享CONTROL/BOARD/别机代码/权重；禁止删除共享数据。控制面回执与科学启动状态分别报告。
