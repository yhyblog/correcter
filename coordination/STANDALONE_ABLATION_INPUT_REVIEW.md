# 三种独立纠偏分支：输入与协议独立复核

日期：2026-09-18 UTC。结论：**PASS，未发现当前输入、配对设计或预算中的执行准备阻断项。** 本审查不代替后续代码/CPU/真实预检验收，不授权模型或仿真。

## 复核范围与输入

- TASK：`coordination/STANDALONE_ABLATION_TASK_20260918.md`，SHA256 `363c50bedcb04d93a5904bf7ecf9873d691974e7e67d82f3a419af4c0065ff5e`。
- PREPARATION：`coordination/STANDALONE_ABLATION_PREPARATION_20260918.json`，SHA256 `bf338495d40abfd6cb0d9a4c833252b8c026f3da7b0bf5a647642f164ee68881`。
- 对照旧 `outputs/native10_training_20260916/preparation/main_registration_v2/primary_manifest.json`、`heldout_audits/heldout_v1/source_records.json`、原最终账本及准备文件列出的 11 项证据。
- 仅读取静态文件、核对引用 SHA、比较元数据及汇总旧账本；新增模型调用、仿真和优化均为 0，未读取任何新消融效果。

## 独立核对结果

1. **源清单一致。** 新准备的 100 个 ID 及顺序与原 held 主注册和最终审计完全一致；100 个 source binding 的所有已列字段与原审计逐项一致，包括 cut、scene fingerprint、source/collection 路径及 seal。
2. **分母正确。** 五任务各 20 源，任务内各有 20 个不同封存 scene fingerprint；98 个有效 cut、2 个无 cut，与原审计一致。两个无 cut ID 为 `pick-place-wall-v3__2026111866`、`pick-place-wall-v3__2026111881`，原共同结局已检查为每臂四个相同位置。每臂完整 400 个逻辑结果；无 cut 的 8 个位置不新增物理分支。本次没有重新初始化或替补。
3. **预检选择不依赖结局。** 固定五源 `disassemble-v3__2026111750`、`pick-place-wall-v3__2026111751`、`shelf-place-v3__2026111752`、`stick-pull-v3__2026111753`、`stick-push-v3__2026111754`，分别同时满足各任务 canonical 排序首个 cut 源及原 manifest 顺序首个 cut 源。选择规则只需 ID、task 和 cut 资格，不使用成功率、Q 或幅度。
4. **旧账本完整引用。** 准备文件列出的 11 项证据 SHA 均与现有文件一致。旧 `budget/attempts.jsonl` SHA 为 `3f293430a26d7c0405c33b797788fdfd099f3b8d0a42aec7c37a89338a4ef552`；独立逐行汇总得到 simulator attempts 48,183、optimizer updates 51,200，共 99,383 个唯一且递增编号。新账本必须以此为不可变 carry-in，不修改旧账本或 READY。
5. **预算闭合。** 预检 `5×(1+1+5+3)=50`；正式 `98×(1+3×4)=1274`；计划新增 1324，总计 49,507。阶段上限 `60+1400+40=1500`，跨账本最大 49,683，小于 50,000；新增优化 0。剩余 317 不是本阶段自动授权。准备文件列出的每方法单独恢复 1470 备选并非已选方案；加 50 预检会超过 1500，不能静默切换。
6. **配对及统计边界明确。** TASK 要求原 a0/noise、源上下文、旧队列、raw 动作、4 个 suffix 随机键与执行器保持一致，预检重放原五臂 rep0，正式每源继续核对 a0 和身份。三项 solo−R 为共同主要比较，三项 solo−full 为关键结构诊断；完整 100 源任务内整源 bootstrap 10,000 次、seed 2026091801、percentile/linear，三项主要比较同时报告 95% 和 Bonferroni 98.333333% 区间。无事后方法筛选或等效宣称。

## 非阻断观察与后续验收边界

- PREPARATION 早于 TASK，因此其中 `TASK not available`、`budget_authorized:false` 和尚未解决的发布事项是当时的草案状态；最终 future-ready 应绑定上列当前 TASK SHA、实际新代码/CPU证据、账本路径和权限，不能将该旧准备 JSON 当执行许可。
- TASK 已明确 J 为原四成员平均概率差，不改为 logit 或添加方差惩罚。此次主变化是自身可行半径，不是仅隐藏其余分支；部署入口独立与训练数据混合的范围区分准确。
- 本次只确认可复用输入与协议一致，不证明尚未实现的新入口已满足无交叉调用、原方向一致或轨迹复现。此三项由既定 CPU/预检关卡验证即可，无需等待新实现才能完成本输入审查。
- 旧 held 已揭晓，追加结果应称预先固定的同队列结构消融，不称新独立 held 成功；旧各臂注明封存复用，新 solo 臂注明新实测。
