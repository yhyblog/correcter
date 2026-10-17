# Native10 最终 heldout 执行交接

固定A4000 + matched-post在独立held100上相对仅重规划提升 **+9.00个百分点**，源级95% CI [3.25, 15.00]；救回46/损害10个配对后缀，正/负/零源18/6/76。点估计达到预登记的5个百分点目标。源级95%区间下界大于0，支持正向增益。点估计达到目标与真实增益至少5个百分点是不同结论，后者不能由此保证。

100个原注册主槽全部完成，每任务20个真实不同初态；98个报警源、2个无报警共同结局，全部保留于分母。4次后缀为源内配对，不是400个独立初态。P−R为唯一预登记主比较，其余六项为次要描述，七项区间未经多比较校正；不合并校准与held。

| 物理臂 | 成功数/400 | 成功率 |
|---|---:|---:|
| continue_native10 | 168 | 42.00% |
| alarm_replan10 | 214 | 53.50% |
| velocity | 237 | 59.25% |
| direct | 234 | 58.50% |
| post | 250 | 62.50% |

| 配对比较 | 增益pp [95% CI] | 救/害 | 正/负/零源 |
|---|---:|---:|---:|
| alarm_replan10_minus_continue_native10 | +11.50 [3.00, 20.25] | 79/33 | 28/13/59 |
| velocity_minus_alarm_replan10 | +5.75 [0.75, 11.00] | 32/9 | 13/5/82 |
| direct_minus_alarm_replan10 | +5.00 [-1.00, 10.75] | 36/16 | 15/7/78 |
| post_minus_alarm_replan10 | +9.00 [3.25, 15.00] | 46/10 | 18/6/76 |
| velocity_minus_continue_native10 | +17.25 [9.75, 25.00] | 84/15 | 30/9/61 |
| direct_minus_continue_native10 | +16.50 [9.25, 24.50] | 82/16 | 28/9/63 |
| post_minus_continue_native10 | +20.50 [13.00, 28.25] | 94/12 | 35/6/59 |

| 任务（各20源） | N / R / V / D / P 成功率% | P−R pp |
|---|---:|---:|
| disassemble-v3 | 65.00 / 61.25 / 73.75 / 80.00 / 75.00 | +13.75 |
| pick-place-wall-v3 | 37.50 / 72.50 / 72.50 / 75.00 / 82.50 | +10.00 |
| shelf-place-v3 | 20.00 / 17.50 / 22.50 / 21.25 / 27.50 | +10.00 |
| stick-pull-v3 | 8.75 / 21.25 / 27.50 / 26.25 / 27.50 | +6.25 |
| stick-push-v3 | 78.75 / 95.00 / 100.00 / 90.00 / 100.00 | +5.00 |

全轨迹/初始scene/原槽替补链/实际A4000/raw与同幅/后缀配对/账本审计及独立重聚合通过，10339项文件入索引，29974条后缀种子记录核验。held计费2158/2200；全局48183/50000仿真、51200/51200更新；技术储备使用0/1200。八卡holder已恢复。

完整matched-post依赖V/D/P及反向、随机方向共同定半径；没有改为post原生幅度或在held后重新选择策略。Q与真实收益关系只作描述，不据此增加门限或改参数。

完整Q/raw/成本与逐任务诊断：[报告](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_diagnostics/heldout_v1/report.md)。

逐源结果：[per_source.csv](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_diagnostics/heldout_v1/per_source.csv)。

参数：[parameters.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_handoffs/heldout_v1/parameters.json)；七比较与资源：[summary.json](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_handoffs/heldout_v1/summary.json)。

全量审计：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_audits/heldout_v1`，seal `d776f54ceb94879bc1945a6e5e02736d04ba9d7e4652e02e06280be3a85a833e`。

独立重聚合：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_independent_audits/heldout_v1`，seal `66fd7f8903d143822949dbddc297e31c16e132c06851f260ebf65cd8fcbd76ce`。

所有结论限定于本批五个固定任务、native10与首次合法报警的一次干预；未追加仿真、补样本或新训练。

交接包：`/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/native10_training_20260916/heldout_handoffs/heldout_v1`；seal `b8463a5588838bf4a06ffccde7048190d738921bcd14f11e3257ddd939c4fbd9`。
