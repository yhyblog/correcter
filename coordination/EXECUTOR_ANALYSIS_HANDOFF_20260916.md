独立汇总完成：15个新源、每源8次，600正式分支；以下为源级统计。

| 方法 | 成功数/120 | 成功率 |
|---|---:|---:|
| continue_old | 31/120 | 25.83% |
| replan | 66/120 | 55.00% |
| velocity | 64/120 | 53.33% |
| direct | 67/120 | 55.83% |
| post | 66/120 | 55.00% |

7个配对比较：增益及95%CI单位为百分点；任务分层、完整源bootstrap 10000次，未做多比较校正。

| 比较 | 增益 [95%CI] | 救回/损害 | 正/负/零源 |
|---|---:|---:|---:|
| replan−continue_old | +29.17 [+16.67, +45.00] | 38/3 | 7/1/7 |
| velocity−replan | -1.67 [-2.50, +0.00] | 0/2 | 0/2/13 |
| direct−replan | +0.83 [+0.00, +2.50] | 3/2 | 1/0/14 |
| post−replan | +0.00 [-2.50, +2.50] | 2/2 | 1/1/13 |
| direct−velocity | +2.50 [+0.00, +5.00] | 3/0 | 2/0/13 |
| post−velocity | +1.67 [+0.00, +5.00] | 2/0 | 1/0/14 |
| post−direct | -0.83 [-2.50, +0.00] | 1/2 | 0/1/14 |

逐任务成功率（%，各3源×8）：

| 任务 | continue_old | replan | velocity | direct | post |
|---|---:|---:|---:|---:|---:|
| disassemble-v3 | 0.00 | 100.00 | 100.00 | 100.00 | 100.00 |
| pick-place-wall-v3 | 12.50 | 33.33 | 33.33 | 33.33 | 33.33 |
| shelf-place-v3 | 16.67 | 33.33 | 33.33 | 33.33 | 33.33 |
| stick-pull-v3 | 0.00 | 8.33 | 0.00 | 12.50 | 8.33 |
| stick-push-v3 | 100.00 | 100.00 | 100.00 | 100.00 | 100.00 |

主要异常/审计：三纠偏均未达相对replan +5pp。配对结局变化仅stick-pull的2026106003/6013；Q平均预测增益velocity/direct/post为+10.05/+10.13/+10.87pp，实际为−1.67/+0.83/0pp。XYZ零组0、收缩10；夹爪零组2、收缩4；velocity/direct fallback均0，无晚报警或预算截短。continue_old保持原raw队列及自然native50；与fixed10 replan的差异包含周期和命令处理差异，不能归因于单一报警中断。

成本（每触发源平均秒）：基础采样0.212245、velocity采样0.245046、direct采样0.233799、post梯度子步骤0.002789；源状态恢复0.962723、共享候选bank（排除回放）0.736192、整体wall（包含回放）1.698914。post梯度不是完整部署成本。

审计：独立从600分支重建15×5×8结局，5臂及7比较、逐任务和源级CI均与封存evaluation一致；冻结290代码hash保持不变。预算653/700=600正式+25预检+20capture+8并发复现，无重复；本次仅CPU汇总，新增仿真0，参数未改。

报告：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/docs/SMALL_BATCH_ANALYSIS_20260916.md
独立JSON：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/analysis/latest_review.json
逐源CSV：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/outputs/metaworld_small_20260916/report/per_source.csv
执行状态：/mnt/bn/arnold-recommend/yaohaoyang/Corrector/coordination/EXECUTOR_STATUS.json
