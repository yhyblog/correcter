# 首固定50训练源执行回传

本报告仅汇总预登记训练切点诊断，未选方法、未改采集参数。50源全部封存后才读取科学比较；50个不同物理初态，4配对后缀、13候选＋独立normal，共2800个实际分支；无技术缺失、无替补，审计通过。

| 方法 | 成功率 | 相对replan增量 | 救回/损害（对replan） | 正/负/零源 |
|---|---:|---:|---:|---:|
| continue_native10 | 38.5% | — | — | — |
| replan / a0 | 51.5% | 0 | — | — |
| velocity | 55.0% | +3.5pp | 8/1 | 5/1/44 |
| direct | 55.0% | +3.5pp | 10/3 | 5/3/42 |
| post | 54.0% | +2.5pp | 11/6 | 4/3/43 |
| reverse_post | 47.0% | -4.5pp | 3/12 | 2/4/44 |
| xyz_positive | 54.0% | +2.5pp | 6/1 | 4/1/45 |
| xyz_negative | 50.5% | -1.0pp | 1/3 | 1/2/47 |
| gripper_positive | 51.5% | +0.0pp | 0/0 | 0/0/50 |
| gripper_negative | 49.5% | -2.0pp | 2/6 | 2/3/45 |
| random_half_positive | 48.5% | -3.0pp | 1/7 | 1/3/46 |
| random_half_negative | 51.5% | +0.0pp | 5/5 | 2/2/46 |
| random_full_positive | 45.0% | -6.5pp | 1/14 | 1/6/43 |
| random_full_negative | 44.0% | -7.5pp | 6/21 | 2/7/41 |

中断项 replan−normal 为 +13.0pp，救回38/损害12，正/负/零源11/5/34。系统项 velocity/direct/post−normal 分别 +16.5/+16.5/+15.5pp，救回/损害41/8、41/8、42/11。I+A=T按源核对通过。配对共享后缀决策索引的随机流；normal与干预臂的绝对重采样时刻允许不同。

| 任务（各10源） | normal | replan | velocity | direct | post |
|---|---:|---:|---:|---:|---:|
| disassemble-v3 | 60.0% | 87.5% | 90.0% | 85.0% | 77.5% |
| pick-place-wall-v3 | 20.0% | 60.0% | 60.0% | 60.0% | 60.0% |
| shelf-place-v3 | 17.5% | 7.5% | 17.5% | 20.0% | 17.5% |
| stick-pull-v3 | 15.0% | 22.5% | 27.5% | 30.0% | 35.0% |
| stick-push-v3 | 80.0% | 80.0% | 80.0% | 80.0% | 80.0% |

覆盖：预登记25首次报警＋25scheduled；实际24报警、22原scheduled、4固定fallback。实际cut5/15/25/45/95/235分别16/16/2/13/2/1。18/50源出现候选均值差异；8源至少一个候选获益，12源至少一个候选受损。别名平均独立raw动作组12.84/13，3源夹爪全不可修改；XYZ无全锁源。各维平均可修改比例X/Y/Z/gripper为94.6%/96.8%/55.2%/82.6%。

补充分层仅使用上述已封存固定50源审计，没有读取后续源效果。raw组按源内唯一命令累加；“信息源”指四重复候选均值存在差异，本批也恰等于存在配对结局差异的源数，不是统计显著性。不同配对槽按12个非a0命名候选×4重复比较a0，包含别名及同源相关性，不能当独立样本量。

| 预登记请求 | 源数 | 实际cut:源数 | raw组/候选槽 | XYZ/grip零通道源 | 信息源 | 不同配对槽/总槽 |
|---|---:|---|---:|---:|---:|---:|
| first_alarm | 25 | 5:16，15:6，25:2，235:1 | 319/325 | 0/2 | 12 | 110/1200 |
| scheduled15 | 10 | 15:10 | 128/130 | 0/1 | 3 | 18/480 |
| scheduled45 | 10 | 45:10 | 130/130 | 0/0 | 1 | 1/480 |
| scheduled95 | 5 | 45:3，95:2 | 65/65 | 0/0 | 2 | 4/240 |

| 实际选择 | 源数 | 实际cut:源数 | raw组/候选槽 | XYZ/grip零通道源 | 信息源 | 不同配对槽/总槽 |
|---|---:|---|---:|---:|---:|---:|
| alarm | 24 | 5:16，15:5，25:2，235:1 | 306/312 | 0/2 | 12 | 110/1152 |
| scheduled | 22 | 15:10，45:10，95:2 | 284/286 | 0/1 | 5 | 22/1056 |
| fallback | 4 | 15:1，45:3 | 52/52 | 0/0 | 1 | 1/192 |

四个fallback均为训练cut回退，没有换seed/scene：shelf-place `2026111022` 无合法报警，按固定规则取15；disassemble `2026111025`、pick-place-wall `2026111026`、stick-push `2026111029` 均由requested95回退到已保存合法45。各源requested/actual/reason见补充JSON。650候选槽共642源内唯一raw组：47源13组、2源11组、1源9组；三个夹爪零通道源均为shelf-place，seed `2026111007/1012/1042`，每源两个非a0别名指向a0。

注册身份记录的scheduled `cut_rule` 仍保留最初的 `fallback=none_pending_analysis_review` 历史文字；实际主版本由冻结的 `source_selection=analysis_lead_v1` 和明确的优先序控制。以上已保存的早期anchor、实际选择及逐源reason证明fallback确实执行，不能仅从这一历史字段推断未实现。保持注册及运行冻结不变，不回写历史记录。

这些源用于训练分布诊断，scheduled/fallback不是部署first-alarm策略；不把上述均值当泛化效果或独立验证。无置信区间/显著性或赢家声明，结果判断由分析端进行。

成本：分支均值8.736s、P95 16.406s，bank均值2.476s，restore均值1.064s。固定50源轻量产物逻辑文件合计263.2 MiB（12218个文件）。用该均值理想均摊到32workers，首轮22400分支约1.70h，全计划46200分支约3.50h纯分支时间；这不是完工时长承诺，未含加载、capture/bank、尾部负载差异、未来分布变化、CPU训练/审计等。

审计快照总尝试6874=P0 564＋主采集6310，优化0；采集仍增长，当前值见EXECUTOR_STATUS。

- 逐源/全部配对/输入SHA：`outputs/native10_training_20260916/progress_audits/watcher_round1_v1_01_first50.json`。
- 请求/实际选择分层补充：`outputs/native10_training_20260916/progress_audits/watcher_round1_v1_01_first50_strata.json`，仅派生原审计，含输入SHA、逐组源身份和计算定义；新增仿真/训练均0。
- 资源测量：`outputs/native10_training_20260916/preparation/main_first50_resource_measurement.json`。
- 监控与已发送通知：`outputs/native10_training_20260916/progress/watcher/round1_v1_01/`。
