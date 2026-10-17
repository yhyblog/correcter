# 独立纠偏结构消融：分析端独立结果复核

日期：2026-09-18 UTC。**结论：PASS，独立从实际分支摘要重建的八臂结局、10 项预登记比较及全部区间与正式审计一致。**

本报告在正式 wave 全部结束、`audits/standalone_v2` complete 且正式审计 `status=passed`、100 源确认完整之后才读取新效果。未读取中途成功率，未运行模型、测试、训练或仿真。

## 1. 核验方法与分母

- 独立读取原 1,960 个五臂分支摘要和新 1,176 个三 solo 分支摘要，核 source/cut/method/repeat/suffix 命名域，重建 `100×8×4` 结局；总共核对 3,338 个受正式审计 SHA 绑定的输入文件。没有调用执行端统计模块或照抄汇总表。完整轨迹正确性由已通过的正式审计提供，本次不重复物理轨迹审计。
- 五任务各 20 个不同封存 scene fingerprint，每源 4 个后缀重复；每臂 400 个逻辑结局，每任务每臂 80。独立统计单位为源，不能把同源四次当四个独立初态。
- 98 个 cut 源真实执行三个新臂；两个 no-cut 源只复用已封存完整 episode 的共同结局：`pick-place-wall-v3__2026111866=False`、`pick-place-wall-v3__2026111881=True`。每臂保留对应 8 个位置，不新增物理分支、不伪造 Q。
- 任务内完整源有放回 bootstrap 10,000 次，`numpy.default_rng.choice`，seed `2026091801`；固定原 100 源及五任务顺序，八臂共用抽样索引。先平均源内四 repeats，再平均源；percentile/linear。三项主要比较的家族区间分位点为 `0.05/6`、`1−0.05/6`。

## 2. 八臂总体结果

| 方法 | 成功数 / 400 | 成功率 | 来源 |
|---|---:|---:|---|
| normal | 168 | 42.00% | 原封存复用 |
| replan | 214 | 53.50% | 原封存复用 |
| full velocity | 237 | 59.25% | 原封存复用 |
| full direct | 234 | 58.50% | 原封存复用 |
| full post | 250 | 62.50% | 原封存复用 |
| solo velocity | 240 | 60.00% | 本次新实测 |
| solo direct | 237 | 59.25% | 本次新实测 |
| solo post | 252 | 63.00% | 本次新实测 |

## 3. 三项共同主要比较

增益与区间单位均为百分点。Bonferroni 98.333333% percentile 区间提供近似家族控制。

| 比较 | 增益 | 95% CI | 家族区间 | 救回 / 损害 | 正 / 负 / 零源 |
|---|---:|---|---|---:|---|
| solo post − replan | +9.50 | [3.50, 15.75] | [2.50, 17.25] | 47/9 | 18/5/77 |
| solo direct − replan | +5.75 | [0.00, 11.75] | [-1.25, 13.00] | 37/14 | 16/5/79 |
| solo velocity − replan | +6.50 | [2.50, 11.25] | [1.50, 12.25] | 30/4 | 13/4/83 |

**本队列上 solo Post 与 solo Velocity 的调整区间下界大于 0。** solo Direct 点估计为正，95% 区间下界等于 0，调整区间包含负值，不能按本次注册口径宣称其收益已获确认。三个点估计均超过 +5pp，但三个调整区间下界均低于 +5pp；不能说已证明至少 +5pp。

## 4. 拆分相对同方法 full 版本

| 比较 | 增益 | 95% CI | 救回 / 损害 | 正 / 负 / 零源 |
|---|---:|---|---:|---|
| solo post − full post | +0.50 | [0.00, 1.25] | 2/0 | 2/0/98 |
| solo direct − full direct | +0.75 | [0.00, 1.75] | 3/0 | 3/0/97 |
| solo velocity − full velocity | +0.75 | [-1.50, 3.00] | 6/3 | 3/1/96 |

拆分后观察到的总体点估计均未下降，变化仅 +0.50～+0.75pp。Post 两个新增成功分别来自 shelf-place 和 stick-pull；Direct 的三个新增成功来自 disassemble 一个、pick-place-wall 两个；Velocity 同时存在救回和损害。三个结构差值区间均包含 0；这不是等效/非劣效证明，也不是拆分本身显著提高成功率的证明。

## 5. 逐任务成功数

每个单元格分母均为 80，即 20 初态 × 4 后缀重复。

| 任务 | normal | replan | full V | full D | full P | solo V | solo D | solo P |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| disassemble-v3 | 52 | 49 | 59 | 64 | 60 | 61 | 65 | 60 |
| pick-place-wall-v3 | 30 | 58 | 58 | 60 | 66 | 59 | 62 | 66 |
| shelf-place-v3 | 16 | 14 | 18 | 17 | 22 | 18 | 17 | 23 |
| stick-pull-v3 | 7 | 17 | 22 | 21 | 22 | 22 | 21 | 23 |
| stick-push-v3 | 63 | 76 | 80 | 72 | 80 | 80 | 72 | 80 |

solo Post 相对 replan 五任务点增益依次为 +13.75、+10.00、+11.25、+7.50、+5.00pp；不能由此声称各任务均显著。solo Direct 在 stick-push 为 −5pp，说明总体正点估计仍可包含任务层损害。

## 6. 其余预登记参照

以下为描述性次要比较，95% 区间未作额外确认性声明。

| 比较 | 增益 | 95% CI | 救回 / 损害 | 正 / 负 / 零源 |
|---|---:|---|---:|---|
| solo post − normal | +21.00 | [13.50, 29.00] | 96/12 | 35/6/59 |
| solo direct − normal | +17.25 | [9.75, 25.00] | 85/16 | 29/9/62 |
| solo velocity − normal | +18.00 | [10.75, 25.51] | 86/14 | 32/8/60 |
| replan − normal | +11.50 | [3.25, 20.00] | 79/33 | 28/13/59 |

## 7. 预算与范围

- 独立读取新封存 ledger：1,324 个连续唯一 attempt 编号、1,324 个唯一 identity，无重复、无 repair、无额外失败/重试记录。
- 预检 50 = 10 次 bank 恢复 + 40 条分支；正式 1,274 = 98 次 bank 恢复 + 1,176 条分支。预检结果不进入正式统计。
- 新增 simulator attempts 1,324，旧 carry-in 48,183，累计 **49,507 / 50,000**；新增 optimizer updates 0，旧累计 51,200。不将未使用余额当作新搜索授权。
- 本批复用已揭晓原 held100；这是预先固定的同源结构消融，不能称新独立 held 验证，不能据此挑赢家后作独立确认声明。
- 本审查确认成功率/统计/预算，完整单分支成本和幅度/Q 解释另用已封存 diagnostics；不把 post 梯度子步骤视为完整部署成本。

## 8. 精确证据

- 正式审计：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/standalone_ablation_20260918/audits/standalone_v2`；complete SHA256 `4b2453ff907a0b6c9ef2524f0ed798d30d07912f08ed182a8c69c00d99fdc53b`。
- result SHA256：`da86f3495d345ea2ed5da9ebdfb2efd539c33b0c28fe576090c975f2103735a8`。
- source_records SHA256：`c55c119608735ff727f5d899c7b33db9241446b1feb803a96a65025659b343b9`。
- budget_snapshot SHA256：`9faab26622a0e28b455037c5620086ea82d625839844d4a346cf01c91a7f083d`。
- 独立 JSON：`analysis/STANDALONE_ABLATION_INDEPENDENT_REVIEW_20260918.json`；SHA256 `c580eba373dc5ba7d16ec458f7ba439c56f5c56b924b55943c1efaa853c75d28`。
- JSON 保留精确数值、每任务救害/源计数、重建顺序、输入集合摘要哈希；正文区间显示保留两位小数。
