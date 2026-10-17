# π0.5 并发墙钟与反馈频率补测

汇总时间：2026-09-26T02:51:50.151197+00:00；状态：complete。

查询延迟直接来自外层实测 wall_seconds；均值/P95均从逐条墙钟计算，未用分项之和或最大值估算。预热排除，P95使用linear插值。各行≤1/3秒比例表示本批查询满足333.333毫秒预算的比例。

`parallel_feedback_no_intervention` 与 `parallel_feedback_with_Q` 在正常计划更新点共时发起策略与反馈，不额外投机采样；`feedback_then_replan_Q` 从中途反馈发起计时，先反馈再fresh采样及Q，是单独的因果串联路径。

频率吞吐按每worker自身窗口内完成数/窗口时长计算；跨worker只报告单卡数值的均值与范围，不把多卡完成数当成单卡吞吐。service和deadline统计纳入窗口内释放、窗口后排空完成的任务，另提供仅窗内完成任务的service分布；因此最慢越界完成不会从deadline统计中消失。

策略deadline为 end−release>1/3秒；6/30Hz反馈分别为 end−release>1/6或1/30秒。无反馈目标周期的饱和模式不定义反馈deadline。未记录结束的pending不冒充已完成或按零耗时计入。

调度采用latest-due，跳过过期release且不堆积旧输入；跳过数和计划release数另列。deadline miss比例的分母是实际完成调用，跳过的release未混入该分母，需同时看跳过比例。policy_only_3Hz为无反馈的真实3Hz对照；30Hz是预录输入到达时钟，不执行env.step。

此处使用真实cut5快照重复查询，非成功率评测。w512 Q为四个随机初始化成员，每成员3,781,122参数，仅测速、无训练；D/G0沿用既有π0.5权重。Q在CPU，含动作梯度、S²及投影。每卡共享模型、两个CUDA streams的实测协议以worker记录为准。

预定上下文：20；实际纳入不同context_id：20；非预热查询：400；预热：80。

## 查询墙钟

| case | n | context数 | 均值 ms | P95 ms | ≤333.333ms比例 |
|---|---:|---:|---:|---:|---:|
| N | 100 | 20 | 189.076 | 200.342 | 100.000% |
| parallel_feedback_no_intervention | 100 | 20 | 214.938 | 225.177 | 100.000% |
| parallel_feedback_with_Q | 100 | 20 | 230.005 | 235.838 | 100.000% |
| feedback_then_replan_Q | 100 | 20 | 255.271 | 263.924 | 99.000% |

## 每worker频率与deadline

| worker/GPU | mode | role | 窗内完成 | 窗后完成 | 跳过/计划 | 吞吐 Hz | service均值/P95 ms | deadline miss/n |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 4/4 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 187.367 / 188.755 | 0/30 |
| 4/4 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| 4/4 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| 4/4 | feedback_alone_max | feedback | 101 | 1 | 0/NR | 20.200 | 49.262 / 50.261 | NR/0 |
| 4/4 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 247.354 / 251.026 | 0/30 |
| 4/4 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 76.393 / 77.905 | 0/60 |
| 4/4 | feedback_30Hz | policy | 30 | 0 | 0/30 | 3.000 | 305.986 / 312.211 | 0/30 |
| 4/4 | feedback_30Hz | feedback | 139 | 1 | 160/300 | 13.900 | 71.682 / 77.554 | 140/140 |
| 4/4 | feedback_saturated_with_policy | policy | 30 | 0 | 0/30 | 3.000 | 305.234 / 307.984 | 0/30 |
| 4/4 | feedback_saturated_with_policy | feedback | 140 | 1 | 0/NR | 14.000 | 71.132 / 75.928 | NR/0 |
| 5/5 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 191.345 / 194.031 | 0/30 |
| 5/5 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| 5/5 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| 5/5 | feedback_alone_max | feedback | 100 | 1 | 0/NR | 20.000 | 49.938 / 50.752 | NR/0 |
| 5/5 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 249.439 / 251.054 | 0/30 |
| 5/5 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 77.966 / 80.015 | 0/60 |
| 5/5 | feedback_30Hz | policy | 30 | 0 | 0/30 | 3.000 | 312.122 / 316.070 | 0/30 |
| 5/5 | feedback_30Hz | feedback | 137 | 1 | 162/300 | 13.700 | 72.718 / 76.894 | 138/138 |
| 5/5 | feedback_saturated_with_policy | policy | 30 | 0 | 0/30 | 3.000 | 312.434 / 316.379 | 0/30 |
| 5/5 | feedback_saturated_with_policy | feedback | 137 | 1 | 0/NR | 13.700 | 72.505 / 77.233 | NR/0 |
| 6/6 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 196.056 / 213.853 | 0/30 |
| 6/6 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| 6/6 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| 6/6 | feedback_alone_max | feedback | 101 | 1 | 0/NR | 20.200 | 49.304 / 49.902 | NR/0 |
| 6/6 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 253.621 / 262.034 | 0/30 |
| 6/6 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 78.808 / 89.823 | 0/60 |
| 6/6 | feedback_30Hz | policy | 30 | 0 | 0/30 | 3.000 | 317.440 / 332.740 | 1/30 |
| 6/6 | feedback_30Hz | feedback | 136 | 1 | 162/300 | 13.600 | 73.071 / 76.444 | 137/137 |
| 6/6 | feedback_saturated_with_policy | policy | 30 | 0 | 0/30 | 3.000 | 318.908 / 333.783 | 2/30 |
| 6/6 | feedback_saturated_with_policy | feedback | 137 | 1 | 0/NR | 13.700 | 72.504 / 76.229 | NR/0 |
| 7/7 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 197.668 / 205.907 | 0/30 |
| 7/7 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| 7/7 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| 7/7 | feedback_alone_max | feedback | 100 | 1 | 0/NR | 20.000 | 49.706 / 50.765 | NR/0 |
| 7/7 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 252.444 / 255.149 | 0/30 |
| 7/7 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 75.803 / 78.273 | 0/60 |
| 7/7 | feedback_30Hz | policy | 30 | 0 | 0/30 | 3.000 | 320.293 / 329.082 | 1/30 |
| 7/7 | feedback_30Hz | feedback | 133 | 1 | 165/300 | 13.300 | 74.810 / 78.126 | 134/134 |
| 7/7 | feedback_saturated_with_policy | policy | 29 | 1 | 0/30 | 2.900 | 330.494 / 362.483 | 14/30 |
| 7/7 | feedback_saturated_with_policy | feedback | 131 | 1 | 0/NR | 13.100 | 76.150 / 79.750 | NR/0 |

## 跨worker单卡吞吐分布

| mode | role | worker数 | 均值 Hz | 范围 Hz |
|---|---|---:|---:|---:|
| policy_only_3Hz | policy | 4 | 3.000 | 3.000–3.000 |
| policy_only_3Hz | feedback | 4 | 0.000 | 0.000–0.000 |
| feedback_alone_max | policy | 4 | 0.000 | 0.000–0.000 |
| feedback_alone_max | feedback | 4 | 20.100 | 20.000–20.200 |
| feedback_6Hz | policy | 4 | 3.000 | 3.000–3.000 |
| feedback_6Hz | feedback | 4 | 6.000 | 6.000–6.000 |
| feedback_30Hz | policy | 4 | 3.000 | 3.000–3.000 |
| feedback_30Hz | feedback | 4 | 13.625 | 13.300–13.900 |
| feedback_saturated_with_policy | policy | 4 | 2.975 | 2.900–3.000 |
| feedback_saturated_with_policy | feedback | 4 | 13.625 | 13.100–14.000 |

## 覆盖、缺测与来源

数据问题 0 项；缺失case：无；缺失worker/mode窗口：0。缺测NR不填零，部分worker已记录的有效查询仍保留。

[SUMMARY](SUMMARY.json) · [LATENCY](LATENCY.csv) · [FREQUENCY](FREQUENCY.csv) · [CONFIG](CONFIG.json) · [上下文](contexts.json) · [资产](assets.json)

| worker | 主机/GPU/UUID | 终局 | contexts | 原始latency | 原始frequency |
|---|---|---|---:|---|---|
| 0 | trial-303269581-trialrun-303269581-worker-0 / 0 / GPU-7f71438a-f878-bc66-8a4e-569afc9e059e | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_0/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_0/frequency.jsonl) |
| 1 | trial-303269581-trialrun-303269581-worker-0 / 1 / GPU-660cc922-7249-e74d-ef3f-2375a073a009 | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_1/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_1/frequency.jsonl) |
| 2 | trial-303269581-trialrun-303269581-worker-0 / 2 / GPU-7a6af46c-023f-10a9-3320-5f77d6931ceb | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_2/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_2/frequency.jsonl) |
| 3 | trial-303269581-trialrun-303269581-worker-0 / 3 / GPU-f8683145-0833-8aa1-5ded-e026f9ad9adb | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_3/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_3/frequency.jsonl) |
| 4 | trial-303269581-trialrun-303269581-worker-0 / 4 / GPU-c3f3580b-5658-e4bb-b7cf-006b40028a97 | complete | 1 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_4/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_4/frequency.jsonl) |
| 5 | trial-303269581-trialrun-303269581-worker-0 / 5 / GPU-57220e5f-dc72-b04c-39bb-9857d5d720cd | complete | 1 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_5/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_5/frequency.jsonl) |
| 6 | trial-303269581-trialrun-303269581-worker-0 / 6 / GPU-6e06f449-5763-6e68-28a2-bb311c033bcd | complete | 1 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_6/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_6/frequency.jsonl) |
| 7 | trial-303269581-trialrun-303269581-worker-0 / 7 / GPU-ff17fd89-47b4-887c-f53a-ccdde554cb80 | complete | 1 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_7/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/pi05_parallel_latency_20260926/workers/worker_7/frequency.jsonl) |
