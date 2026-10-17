训练 600 源方向诊断（2026-09-17；工作流 20260916）


已完成 train-only 只读诊断。联合 velocity/direct/post 相对 a0 的成功率差为 **+1.71/+2.29/+2.50 个百分点**；round2 分别为 +2.50/+4.00/+3.58 个百分点。这些是两套生成器收集的训练标签，不是最终 A/B 模型的独立评测，不能宣布达到“较仅重规划再提高约 5 个百分点”的目标，也不用于修改参数或选择赢家。

两个子包各 300 个完整有效训练源；联合 600 个实际 episode 和 planned slot 均唯一，每轮每 task 60 源、联合每 task 120 源。全部共同数组、rows 和逐源 provenance 与联合 train 包逐元素/逐记录相同；4 次后缀属于同一源内配对，不能将每臂 2400 次后缀当成 2400 个独立源。仅读取联合目录的 train 部分，未调用 load_bundle、模型、PCA、仿真或优化器，未读取 development/calibration/heldout 效果。

候选生成 teacher 保留原 provenance：round1 为旧 v3 critic 1041–1044，round2 为首轮选中的 B200 critic 0–3；四成员 SHA 和原 collection protocol 分别保存在 result.json。VLA/D/G0/实现哈希跨轮相同。两轮源、切点和 teacher 同时不同，分轮差异不能归因于 teacher 改进。

**切点与训练监督构成。** 两轮都登记 first_alarm 150、scheduled15/45/95 各 50；requested_cut 分别为 None 150、15/45/95 各 50。实际构成如下；完整 task × registered × requested × actual × selection × reason 交叉计数及分组结果在 JSON 的 cut_cross_counts/groups，未按结果筛源。

| 实际选择 | round1 | round2 | 联合 |
| --- | --- | --- | --- |
| alarm | 142 | 146 | 288 |
| scheduled | 129 | 130 | 259 |
| fallback | 29 | 24 | 53 |

| 实际 cut | round1 | round2 | 联合 |
| --- | --- | --- | --- |
| 5 | 93 | 88 | 181 |
| 15 | 82 | 84 | 166 |
| 25 | 7 | 6 | 13 |
| 35 | 15 | 16 | 31 |
| 45 | 70 | 70 | 140 |
| 55 | 1 | 1 | 2 |
| 65 | 1 | 2 | 3 |
| 85 | 0 | 1 | 1 |
| 95 | 29 | 31 | 60 |
| 125 | 0 | 1 | 1 |
| 135 | 1 | 0 | 1 |
| 235 | 1 | 0 | 1 |

| 监督信息（raw 同动作去重） | round1 | round2 | 联合 |
| --- | --- | --- | --- |
| raw 动作组（含 a0） | 3854 | 3876 | 7730 |
| 非 a0 动作组 | 3554 | 3576 | 7130 |
| 正 / 负方向不相同的无序组对 | 1477 | 1488 | 2965 |
| mean gain > 0 的组 | 172 | 232 | 404 |
| mean gain < 0 的组 | 274 | 199 | 473 |
| mean gain = 0 的组 | 3108 | 3145 | 6253 |
| 存在非 a0 mean 差的源 | 109 | 96 | 205 |
| 存在有益候选的源 | 56 | 54 | 110 |
| 存在有害候选的源 | 66 | 56 | 122 |
| 同时存在有益和有害候选的源 | 13 | 14 | 27 |
| 正反 mean 不同的组对 | 239 | 225 | 464 |
| 存在正反 mean 差的源 | 105 | 93 | 198 |
| XYZ 全零可变 mask 的源 | 1 | 0 | 1 |
| gripper 全零可变 mask 的源 | 13 | 7 | 20 |

联合有 205/600 源出现非 a0 候选的四后缀均值差，395 源的候选均值全部相同；198 源存在正反方向均值差。7130 个非 a0 raw 组中正/负/零 gain 为 404/473/6253。候选组不是独立源，benefit/harm 源可重叠；这些数表示可观察监督信息，不是知道真实结局后可部署的 oracle 上限。21 源出现 raw alias、共 70 个重复候选槽；独立 NumPy 核验逐元素重建 alias 和三组去重权重一致。

**按 task 的训练方向收益。** N 是完整源数；normal/a0 列为成功率，V/D/P 列为相对 a0 的百分点差；“信息源”是至少一个非 a0 raw-distinct 候选四后缀均值不同的源。表格直接读取已封存 JSON，未新增分组或按结果选取任务。

| 分布 | task | N | normal | a0 | V − a0 pp | D − a0 pp | P − a0 pp | 信息源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| round1 | disassemble-v3 | 60 | 59.17% | 69.17% | +2.92 | -1.25 | -0.83 | 30 |
| round1 | pick-place-wall-v3 | 60 | 43.75% | 57.50% | -4.17 | -3.75 | -1.67 | 16 |
| round1 | shelf-place-v3 | 60 | 18.75% | 20.00% | -2.50 | -2.50 | -2.50 | 20 |
| round1 | stick-pull-v3 | 60 | 16.25% | 18.33% | +3.33 | +3.75 | +5.42 | 30 |
| round1 | stick-push-v3 | 60 | 80.00% | 81.67% | +5.00 | +6.67 | +6.67 | 13 |
| round2 | disassemble-v3 | 60 | 70.00% | 78.75% | -3.75 | -2.50 | -1.25 | 32 |
| round2 | pick-place-wall-v3 | 60 | 47.08% | 62.50% | +2.50 | +3.33 | +3.75 | 15 |
| round2 | shelf-place-v3 | 60 | 17.08% | 18.33% | +2.08 | +2.50 | +0.00 | 18 |
| round2 | stick-pull-v3 | 60 | 10.83% | 11.67% | +7.92 | +11.25 | +10.00 | 23 |
| round2 | stick-push-v3 | 60 | 85.00% | 84.58% | +3.75 | +5.42 | +5.42 | 8 |
| 联合 | disassemble-v3 | 120 | 64.58% | 73.96% | -0.42 | -1.88 | -1.04 | 62 |
| 联合 | pick-place-wall-v3 | 120 | 45.42% | 60.00% | -0.83 | -0.21 | +1.04 | 31 |
| 联合 | shelf-place-v3 | 120 | 17.92% | 19.17% | -0.21 | +0.00 | -1.25 | 38 |
| 联合 | stick-pull-v3 | 120 | 13.54% | 15.00% | +5.62 | +7.50 | +7.71 | 53 |
| 联合 | stick-push-v3 | 120 | 82.50% | 83.12% | +4.38 | +6.04 | +6.04 | 21 |

**按实际 alarm/scheduled/fallback 的训练方向收益。** task 构成按 D/W/S/L/P 顺序记为 disassemble-v3 / pick-place-wall-v3 / shelf-place-v3 / stick-pull-v3 / stick-push-v3；这些是实际训练切点分层，不替代部署评测的全计划分母。

| 分布 | 实际选择 | N | task D/W/S/L/P | normal | a0 | V − a0 pp | D − a0 pp | P − a0 pp | 信息源 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| round1 | alarm | 142 | 30/25/27/30/30 | 40.67% | 54.58% | +4.75 | +3.70 | +5.46 | 71 |
| round1 | scheduled | 129 | 27/25/28/28/21 | 36.24% | 35.27% | -3.10 | -2.71 | -2.71 | 36 |
| round1 | fallback | 29 | 3/10/5/2/9 | 90.52% | 86.21% | +0.00 | +0.00 | +0.00 | 2 |
| round2 | alarm | 146 | 30/28/28/30/30 | 45.21% | 57.71% | +5.31 | +6.16 | +7.02 | 65 |
| round2 | scheduled | 130 | 26/25/29/29/21 | 37.12% | 36.15% | -0.38 | +1.92 | -0.19 | 30 |
| round2 | fallback | 24 | 4/7/3/1/9 | 98.96% | 92.71% | +1.04 | +2.08 | +3.12 | 1 |
| 联合 | alarm | 288 | 60/53/55/60/60 | 42.97% | 56.16% | +5.03 | +4.95 | +6.25 | 136 |
| 联合 | scheduled | 259 | 53/50/57/57/42 | 36.68% | 35.71% | -1.74 | -0.39 | -1.45 | 66 |
| 联合 | fallback | 53 | 7/17/8/3/18 | 94.34% | 89.15% | +0.47 | +0.94 | +1.42 | 3 |

registered cut 的精确分组结果位于 `diagnostics.{round1,round2,combined}.groups.registered_cut.{first_alarm,scheduled15,scheduled45,scheduled95}`；requested/actual cut 分别在同级 `groups.requested_cut` / `groups.actual_cut`，六维交叉计数在同级 `cut_cross_counts`。所有组包含源 ID、14 臂、配对差和原定义 CI；上述表格未据此选择参数。

**14 臂成功次数。** round1、round2 分母各 1200；联合分母 2400。normal 独立于 13 个 critic 候选槽，a0 为仅重规划。

| 臂 | round1 | round2 | 联合成功次数 | 联合成功率 |
| --- | --- | --- | --- | --- |
| a0 | 592 | 614 | 1206 | 50.25% |
| xyz_positive | 605 | 644 | 1249 | 52.04% |
| xyz_negative | 583 | 594 | 1177 | 49.04% |
| gripper_positive | 587 | 620 | 1207 | 50.29% |
| gripper_negative | 549 | 578 | 1127 | 46.96% |
| random_half_positive | 561 | 601 | 1162 | 48.42% |
| random_half_negative | 574 | 615 | 1189 | 49.54% |
| random_full_positive | 539 | 600 | 1139 | 47.46% |
| random_full_negative | 541 | 602 | 1143 | 47.62% |
| velocity | 603 | 644 | 1247 | 51.96% |
| direct | 599 | 662 | 1261 | 52.54% |
| post | 609 | 657 | 1266 | 52.75% |
| reverse_post | 522 | 528 | 1050 | 43.75% |
| continue_native10 | 523 | 552 | 1075 | 44.79% |

**相对 a0 的 12 个候选配对差。** 单位为百分点；方括号为源级 95% bootstrap CI。沿用旧脚本 seed=2026091621、10,000 次 task-stratified multinomial 整源重采样，保持每个分组实际 task 构成，四后缀一起重采样。CI 是训练分布事后描述，未作多重比较校正。

| 候选 − a0 | round1 差 [CI] | round2 差 [CI] | 联合差 [CI] |
| --- | --- | --- | --- |
| xyz_positive | +1.08 [-0.92, +3.25] | +2.50 [+1.17, +4.00] | +1.79 [+0.54, +3.08] |
| xyz_negative | -0.75 [-2.83, +1.25] | -1.67 [-3.67, +0.17] | -1.21 [-2.63, +0.17] |
| gripper_positive | -0.42 [-1.42, +0.67] | +0.50 [-0.50, +1.50] | +0.04 [-0.71, +0.79] |
| gripper_negative | -3.58 [-5.75, -1.58] | -3.00 [-5.33, -0.83] | -3.29 [-4.83, -1.79] |
| random_half_positive | -2.58 [-4.83, -0.50] | -1.08 [-3.00, +0.83] | -1.83 [-3.29, -0.42] |
| random_half_negative | -1.50 [-3.25, +0.25] | +0.08 [-2.00, +2.17] | -0.71 [-2.08, +0.63] |
| random_full_positive | -4.42 [-7.42, -1.67] | -1.17 [-3.83, +1.42] | -2.79 [-4.75, -0.83] |
| random_full_negative | -4.25 [-7.08, -1.50] | -1.00 [-3.92, +2.00] | -2.62 [-4.62, -0.58] |
| velocity | +0.92 [-1.33, +3.25] | +2.50 [+0.42, +4.67] | +1.71 [+0.17, +3.25] |
| direct | +0.58 [-2.00, +3.17] | +4.00 [+1.75, +6.33] | +2.29 [+0.58, +4.04] |
| post | +1.42 [-1.00, +3.92] | +3.58 [+1.42, +5.92] | +2.50 [+0.88, +4.21] |
| reverse_post | -5.83 [-9.00, -2.83] | -7.17 [-10.08, -4.42] | -6.50 [-8.58, -4.42] |

**主纠偏的救回/损害与源级方向。** 救回/损害按配对后缀计数；正/负/零按该源四后缀成功数之差计数。

| 分布/方法 | 救回/损害（后缀） | 正/负/零（源） |
| --- | --- | --- |
| round1/velocity | 46/35 | 21/18/261 |
| round1/direct | 51/44 | 22/21/257 |
| round1/post | 53/36 | 20/20/260 |
| round2/velocity | 54/24 | 26/11/263 |
| round2/direct | 68/20 | 30/9/261 |
| round2/post | 63/20 | 26/11/263 |
| 联合/velocity | 100/59 | 47/29/524 |
| 联合/direct | 119/64 | 52/30/518 |
| 联合/post | 116/56 | 46/31/523 |

**中断 I 与系统总增益 T。** I = a0 − continue_native10；T = 方法 − continue_native10。两者与纠偏自身增益 C = 方法 − a0 分开报告。

| 比较 | round1 差 [CI] | round2 差 [CI] | 联合差 [CI] | 联合救回/损害 |
| --- | --- | --- | --- | --- |
| I: a0 − normal | +5.75 [+1.58, +10.08] | +5.17 [+1.75, +8.58] | +5.46 [+2.75, +8.17] | 254/123 |
| T: velocity − normal | +6.67 [+2.92, +10.58] | +7.67 [+4.08, +11.25] | +7.17 [+4.50, +9.75] | 267/95 |
| T: direct − normal | +6.33 [+2.50, +10.33] | +9.17 [+5.42, +13.00] | +7.75 [+5.00, +10.42] | 281/95 |
| T: post − normal | +7.17 [+3.25, +11.08] | +8.75 [+5.17, +12.50] | +7.96 [+5.29, +10.67] | 283/92 |

**五组正反方向。** 下表是 positive − negative（post − reverse_post），不是相对 a0 的纠偏收益。各轮完整救回/损害、正/负/零源和 raw-distinct 源数在 JSON；联合保留所有 600 源分母。

| 方向对 | round1 差 [CI] | round2 差 [CI] | 联合差 [CI] | 联合救回/损害 |
| --- | --- | --- | --- | --- |
| xyz_positive__minus__xyz_negative | +1.83 [-0.92, +4.67] | +4.17 [+1.92, +6.58] | +3.00 [+1.17, +4.92] | 135/63 |
| gripper_positive__minus__gripper_negative | +3.17 [+1.08, +5.33] | +3.50 [+1.42, +5.75] | +3.33 [+1.83, +4.87] | 114/34 |
| random_half_positive__minus__random_half_negative | -1.08 [-3.67, +1.58] | -1.17 [-4.00, +1.67] | -1.12 [-3.04, +0.79] | 89/116 |
| random_full_positive__minus__random_full_negative | -0.17 [-3.75, +3.50] | -0.17 [-3.83, +3.58] | -0.17 [-2.71, +2.46] | 158/162 |
| post__minus__reverse_post | +7.25 [+3.67, +11.00] | +10.75 [+7.42, +14.17] | +9.00 [+6.50, +11.46] | 279/63 |

联合 post − reverse_post 为 +9.00 pp，而 post − a0 为 +2.50 pp；前者只能说明这些已采集候选的正反方向有区分，不能代替后者或证明线上纠偏成功。正负标签仍稀疏、部分方向和任务存在损害；本报告保留这些负例，不新增筛选或调参规则。

**核验与可复现证据。** 新聚合 CPU 测试 4 项通过；round1 原 result 的 total/groups/per_source 全字段（含所有旧 CI）严格相等。独立 NumPy 实现未调用新聚合函数；14 臂、V/D/P 的 C/I/T、五对方向、信息计数及三类分组共 3777 个核对节点通过，最大浮点运算顺序差 3.552713678800501e-15。未重复独立计算 CI，CI 证据为原 round1 完全回归与固定重采样实现。

账本前后 SHA 完全相同：`189cdf5c04a3782b5e540c3761fa682481dedad6ea91e703e705713e2d076973`；既有总量 42,874 simulator_attempts + 19,200 training_updates，增量均为 0；models/PCA 调用均为 0。未改旧脚本、封存产物、模型或科学参数。

- [统计脚本](../experiments/native10_training_20260916/summarize_train600_v1.py)，SHA `03a62f49516e3f20d8226e0770fc3f10d751617788e4f945f2df55e11e8d4757`。
- [完整结果 JSON](../outputs/native10_training_20260916/progress_audits/train600_direction_v1/result.json)；[逐源 CSV](../outputs/native10_training_20260916/progress_audits/train600_direction_v1/per_source.csv)；seal `c3e8b13279d9ac78556ee137c9e2a2ade1c944a9496549e146b1b326239d66b6`。
- [CPU 与真实只读执行日志](../outputs/native10_training_20260916/preparation/train600_direction_cpu_v1/result.json)。
- [独立核验](NATIVE10_TRAIN600_DIAGNOSTIC_INDEPENDENT_CHECK.json)，SHA `295ab3fb3a6f34a359dff816b1c21943fadba6adc5f55b199e69a24fa4b43459`；[交叉核验回执](../outputs/native10_training_20260916/preparation/train600_direction_crosscheck_v1/crosscheck.json)。

复现命令（目录必须是新版本）：

```bash
CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONPATH=. /mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python -m experiments.native10_training_20260916.summarize_train600_v1 --destination outputs/native10_training_20260916/progress_audits/train600_direction_reproduction_v1
```
