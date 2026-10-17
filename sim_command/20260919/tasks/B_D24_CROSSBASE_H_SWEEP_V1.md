# B_D24_CROSSBASE_H_SWEEP_V1 revision1

执行节点 B；host trial-303225685-trialrun-303225685-worker-0；原对话 01a0b9c5-1e4b-7b73-9336-229e6df349a2。
用户已明确授权本次H扫描，请直接领取并实现必要私有H/C适配、部署后台队列，不等待另一次release。
先读 deadline_20260924/CROSSBASE_H_SWEEP_V1/ASSIGNMENT.md、ASSET_AND_ADAPTATION_GUIDE.md 和 AUTHORIZATION.json。
范围：SmolVLA H=[40, 50]，每H N/Post-multi/R-multi/Velocity-multi，各500旧源；新单元固定 UNITS_B.jsonl 共4000。
H10完成结果全部复用；不得运行单次、随机或新训练/采集，不复用旧claim。执行依据本新授权取代旧complete/list-only状态。
先写 receipts/B/B_D24_CROSSBASE_H_SWEEP_V1_ACK.json（引用本授权SHA和本机身份）；单元实际结果与终局回调必须落盘，queue投递不代表ACK。
实现 normal_H 与 C10 分离、显式 N 无触发、逐源隔离环境。维持原基座、原专属L11辅助模型/阈值/动作单位/渲染协议，定向CPU检查后直接使用首批正式episode，不加GPU预检。
目标8卡×24逻辑分支，按本机实际容量实现模型共享/批处理。全wave禁止holder并行，整组退出后恢复；节点间无屏障。
按 N两格→Post两格→R两格→Velocity两格自动衔接，成功及环境任务失败均已完成；技术问题修复后只续未完成源。有限队列22:45北京时间停止新单元，23:00退出发布；若范围无法全部完成，必须保留未完成清单。
只向自己固定原会话注册事件；发现服务旧任务白名单如需扩展，仅在本机私有配置处理。保持原通知CPU授权，不把科学授权当作服务根授权。
