# SmolVLA / X-VLA 原生视觉反馈延时

汇总时间：2026-09-26T03:33:29.596335+00:00；状态：complete。

查询延迟直接来自外层实测 wall_seconds；均值/P95均从逐条墙钟计算，未用分项之和或最大值估算。预热排除，P95使用linear插值。各行≤1/3秒比例表示本批查询满足333.333毫秒预算的比例。

`N` 是完整原生策略采样，`monitor` 是原生视觉编码、池化/固定随机投影和两对D/G0；`parallel_feedback_no_intervention` 在同卡共时发起策略与完整监测。此次不包含Q或纠偏。

频率吞吐按每worker自身窗口内完成数/窗口时长计算；跨worker只报告单卡数值的均值与范围，不把多卡完成数当成单卡吞吐。service和deadline统计纳入窗口内释放、窗口后排空完成的任务，另提供仅窗内完成任务的service分布；因此最慢越界完成不会从deadline统计中消失。

策略deadline为 end−release>1/3秒；6/30Hz反馈分别为 end−release>1/6或1/30秒。无反馈目标周期的饱和模式不定义反馈deadline。未记录结束的pending不冒充已完成或按零耗时计入。

调度采用latest-due，跳过过期release且不堆积旧输入；跳过数和计划release数另列。deadline miss比例的分母是实际完成调用，跳过的release未混入该分母，需同时看跳过比例。policy_only_3Hz为无反馈的真实3Hz对照；30Hz是预录输入到达时钟，不执行env.step。

两个底座共享20个此前π0.5轨迹采集的真实cut5 RGB/本体/动作快照；不读取其中π0.5视觉或语言特征。Smol/X各用自己的原生视觉和语言embedding。每底座新建随机D两成员（width256）与G0两成员（width128），不加载旧权重或旧归一化，训练0步。形状适配为4×4空间池化、固定随机通道投影到256后展平4096，原生语言embedding有效token均值补零到2048。

因此本结果仅反映原生特征路径与指定随机D/G0结构的计算开销，不证明预测准确性、阈值有效性或成功率。输入与20260925旧外部π特征测试的原生轨迹cut不同，不能将两批时延差全部归因于编码器更换。

预定上下文：20；实际纳入不同context_id：20；非预热查询：600；预热：120。

## 查询墙钟

| 底座 | case | n | context数 | 均值 ms | P95 ms | ≤333.333ms比例 |
|---|---|---:|---:|---:|---:|---:|
| smolvla | N | 100 | 20 | 151.583 | 155.549 | 100.000% |
| smolvla | monitor | 100 | 20 | 34.947 | 35.888 | 100.000% |
| smolvla | parallel_feedback_no_intervention | 100 | 20 | 171.168 | 174.837 | 100.000% |
| xvla | N | 100 | 20 | 86.871 | 89.229 | 100.000% |
| xvla | monitor | 100 | 20 | 90.746 | 94.621 | 100.000% |
| xvla | parallel_feedback_no_intervention | 100 | 20 | 128.126 | 131.814 | 100.000% |

## 每worker频率与deadline

| 底座/worker/GPU | mode | role | 窗内完成 | 窗后完成 | 跳过/计划 | 吞吐 Hz | service均值/P95 ms | deadline miss/n |
|---|---|---|---:|---:|---:|---:|---:|---:|
| smolvla/0/0 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 155.031 / 158.027 | 0/30 |
| smolvla/0/0 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| smolvla/0/0 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| smolvla/0/0 | feedback_alone_max | feedback | 149 | 1 | 0/NR | 29.800 | 33.467 / 34.202 | NR/0 |
| smolvla/0/0 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 184.394 / 186.774 | 0/30 |
| smolvla/0/0 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 44.443 / 50.329 | 0/60 |
| smolvla/0/0 | feedback_30Hz | policy | 30 | 0 | 0/30 | 3.000 | 267.874 / 277.571 | 0/30 |
| smolvla/0/0 | feedback_30Hz | feedback | 229 | 1 | 70/300 | 22.900 | 43.510 / 47.910 | 228/230 |
| smolvla/0/0 | feedback_saturated_with_policy | policy | 30 | 0 | 0/30 | 3.000 | 264.482 / 268.828 | 0/30 |
| smolvla/0/0 | feedback_saturated_with_policy | feedback | 225 | 1 | 0/NR | 22.500 | 44.263 / 49.326 | NR/0 |
| smolvla/1/1 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 151.020 / 152.055 | 0/30 |
| smolvla/1/1 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| smolvla/1/1 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| smolvla/1/1 | feedback_alone_max | feedback | 151 | 1 | 0/NR | 30.200 | 32.926 / 34.728 | NR/0 |
| smolvla/1/1 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 176.180 / 180.506 | 0/30 |
| smolvla/1/1 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 42.833 / 49.436 | 0/60 |
| smolvla/1/1 | feedback_30Hz | policy | 30 | 0 | 0/30 | 3.000 | 259.006 / 261.772 | 0/30 |
| smolvla/1/1 | feedback_30Hz | feedback | 234 | 1 | 65/300 | 23.400 | 42.624 / 47.221 | 230/235 |
| smolvla/1/1 | feedback_saturated_with_policy | policy | 30 | 0 | 0/30 | 3.000 | 259.946 / 263.454 | 0/30 |
| smolvla/1/1 | feedback_saturated_with_policy | feedback | 235 | 1 | 0/NR | 23.500 | 42.507 / 46.997 | NR/0 |
| smolvla/2/2 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 152.238 / 153.816 | 0/30 |
| smolvla/2/2 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| smolvla/2/2 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| smolvla/2/2 | feedback_alone_max | feedback | 154 | 1 | 0/NR | 30.800 | 32.257 / 32.695 | NR/0 |
| smolvla/2/2 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 173.520 / 175.511 | 0/30 |
| smolvla/2/2 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 42.240 / 48.731 | 0/60 |
| smolvla/2/2 | feedback_30Hz | policy | 30 | 0 | 0/30 | 3.000 | 259.718 / 263.136 | 0/30 |
| smolvla/2/2 | feedback_30Hz | feedback | 234 | 1 | 65/300 | 23.400 | 42.562 / 47.194 | 233/235 |
| smolvla/2/2 | feedback_saturated_with_policy | policy | 30 | 0 | 0/30 | 3.000 | 260.696 / 263.844 | 0/30 |
| smolvla/2/2 | feedback_saturated_with_policy | feedback | 236 | 1 | 0/NR | 23.600 | 42.317 / 46.868 | NR/0 |
| smolvla/3/3 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 152.093 / 153.416 | 0/30 |
| smolvla/3/3 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| smolvla/3/3 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| smolvla/3/3 | feedback_alone_max | feedback | 149 | 1 | 0/NR | 29.800 | 33.340 / 33.984 | NR/0 |
| smolvla/3/3 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 176.632 / 180.557 | 0/30 |
| smolvla/3/3 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 42.701 / 49.025 | 0/60 |
| smolvla/3/3 | feedback_30Hz | policy | 29 | 0 | 1/30 | 2.900 | 330.974 / 358.885 | 22/29 |
| smolvla/3/3 | feedback_30Hz | feedback | 181 | 1 | 118/300 | 18.100 | 55.059 / 60.388 | 182/182 |
| smolvla/3/3 | feedback_saturated_with_policy | policy | 30 | 0 | 0/30 | 3.000 | 259.551 / 267.051 | 0/30 |
| smolvla/3/3 | feedback_saturated_with_policy | feedback | 234 | 1 | 0/NR | 23.400 | 42.664 / 47.108 | NR/0 |
| xvla/4/4 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 87.299 / 88.669 | 0/30 |
| xvla/4/4 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| xvla/4/4 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| xvla/4/4 | feedback_alone_max | feedback | 56 | 1 | 0/NR | 11.200 | 87.914 / 90.926 | NR/0 |
| xvla/4/4 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 128.630 / 130.759 | 0/30 |
| xvla/4/4 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 107.458 / 128.544 | 0/60 |
| xvla/4/4 | feedback_30Hz | policy | 30 | 0 | 0/30 | 3.000 | 126.848 / 129.040 | 0/30 |
| xvla/4/4 | feedback_30Hz | feedback | 102 | 1 | 197/300 | 10.200 | 97.860 / 120.540 | 103/103 |
| xvla/4/4 | feedback_saturated_with_policy | policy | 30 | 0 | 0/30 | 3.000 | 131.971 / 156.269 | 0/30 |
| xvla/4/4 | feedback_saturated_with_policy | feedback | 102 | 1 | 0/NR | 10.200 | 97.540 / 123.288 | NR/0 |
| xvla/5/5 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 89.653 / 91.017 | 0/30 |
| xvla/5/5 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| xvla/5/5 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| xvla/5/5 | feedback_alone_max | feedback | 55 | 1 | 0/NR | 11.000 | 89.707 / 91.662 | NR/0 |
| xvla/5/5 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 130.572 / 132.669 | 0/30 |
| xvla/5/5 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 109.644 / 130.572 | 0/60 |
| xvla/5/5 | feedback_30Hz | policy | 30 | 0 | 0/30 | 3.000 | 129.049 / 131.367 | 0/30 |
| xvla/5/5 | feedback_30Hz | feedback | 99 | 1 | 199/300 | 9.900 | 100.450 / 120.191 | 100/100 |
| xvla/5/5 | feedback_saturated_with_policy | policy | 30 | 0 | 0/30 | 3.000 | 129.368 / 131.159 | 0/30 |
| xvla/5/5 | feedback_saturated_with_policy | feedback | 98 | 1 | 0/NR | 9.800 | 101.597 / 125.089 | NR/0 |
| xvla/6/6 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 87.808 / 89.948 | 0/30 |
| xvla/6/6 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| xvla/6/6 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| xvla/6/6 | feedback_alone_max | feedback | 56 | 1 | 0/NR | 11.200 | 88.039 / 90.459 | NR/0 |
| xvla/6/6 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 125.202 / 127.081 | 0/30 |
| xvla/6/6 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 106.100 / 125.362 | 0/60 |
| xvla/6/6 | feedback_30Hz | policy | 30 | 0 | 0/30 | 3.000 | 125.147 / 126.881 | 0/30 |
| xvla/6/6 | feedback_30Hz | feedback | 101 | 1 | 198/300 | 10.100 | 98.685 / 120.799 | 102/102 |
| xvla/6/6 | feedback_saturated_with_policy | policy | 30 | 0 | 0/30 | 3.000 | 125.466 / 127.127 | 0/30 |
| xvla/6/6 | feedback_saturated_with_policy | feedback | 101 | 1 | 0/NR | 10.100 | 98.179 / 121.417 | NR/0 |
| xvla/7/7 | policy_only_3Hz | policy | 30 | 0 | 0/30 | 3.000 | 88.618 / 91.031 | 0/30 |
| xvla/7/7 | policy_only_3Hz | feedback | 0 | 0 | 0/NR | 0.000 | NR / NR | NR/0 |
| xvla/7/7 | feedback_alone_max | policy | 0 | 0 | 0/0 | 0.000 | NR / NR | NR/0 |
| xvla/7/7 | feedback_alone_max | feedback | 56 | 1 | 0/NR | 11.200 | 88.895 / 91.375 | NR/0 |
| xvla/7/7 | feedback_6Hz | policy | 30 | 0 | 0/30 | 3.000 | 126.358 / 129.872 | 0/30 |
| xvla/7/7 | feedback_6Hz | feedback | 60 | 0 | 0/60 | 6.000 | 107.937 / 129.876 | 0/60 |
| xvla/7/7 | feedback_30Hz | policy | 30 | 0 | 0/30 | 3.000 | 125.161 / 126.225 | 0/30 |
| xvla/7/7 | feedback_30Hz | feedback | 101 | 1 | 198/300 | 10.100 | 98.791 / 120.632 | 102/102 |
| xvla/7/7 | feedback_saturated_with_policy | policy | 30 | 0 | 0/30 | 3.000 | 127.022 / 128.080 | 0/30 |
| xvla/7/7 | feedback_saturated_with_policy | feedback | 101 | 1 | 0/NR | 10.100 | 98.782 / 122.250 | NR/0 |

## 各底座跨worker单卡吞吐分布

| 底座 | mode | role | worker数 | 均值 Hz | 范围 Hz |
|---|---|---|---:|---:|---:|
| smolvla | policy_only_3Hz | policy | 4 | 3.000 | 3.000–3.000 |
| smolvla | policy_only_3Hz | feedback | 4 | 0.000 | 0.000–0.000 |
| smolvla | feedback_alone_max | policy | 4 | 0.000 | 0.000–0.000 |
| smolvla | feedback_alone_max | feedback | 4 | 30.150 | 29.800–30.800 |
| smolvla | feedback_6Hz | policy | 4 | 3.000 | 3.000–3.000 |
| smolvla | feedback_6Hz | feedback | 4 | 6.000 | 6.000–6.000 |
| smolvla | feedback_30Hz | policy | 4 | 2.975 | 2.900–3.000 |
| smolvla | feedback_30Hz | feedback | 4 | 21.950 | 18.100–23.400 |
| smolvla | feedback_saturated_with_policy | policy | 4 | 3.000 | 3.000–3.000 |
| smolvla | feedback_saturated_with_policy | feedback | 4 | 23.250 | 22.500–23.600 |
| xvla | policy_only_3Hz | policy | 4 | 3.000 | 3.000–3.000 |
| xvla | policy_only_3Hz | feedback | 4 | 0.000 | 0.000–0.000 |
| xvla | feedback_alone_max | policy | 4 | 0.000 | 0.000–0.000 |
| xvla | feedback_alone_max | feedback | 4 | 11.150 | 11.000–11.200 |
| xvla | feedback_6Hz | policy | 4 | 3.000 | 3.000–3.000 |
| xvla | feedback_6Hz | feedback | 4 | 6.000 | 6.000–6.000 |
| xvla | feedback_30Hz | policy | 4 | 3.000 | 3.000–3.000 |
| xvla | feedback_30Hz | feedback | 4 | 10.075 | 9.900–10.200 |
| xvla | feedback_saturated_with_policy | policy | 4 | 3.000 | 3.000–3.000 |
| xvla | feedback_saturated_with_policy | feedback | 4 | 10.050 | 9.800–10.200 |

## 覆盖、缺测与来源

数据问题 0 项；缺失case：无；缺失worker/mode窗口：0。缺测NR不填零，部分worker已记录的有效查询仍保留。

[SUMMARY](SUMMARY.json) · [LATENCY](LATENCY.csv) · [FREQUENCY](FREQUENCY.csv) · [CONFIG](CONFIG.json) · [上下文](contexts.json) · [资产](assets.json)

| 底座/worker | 主机/GPU/UUID | 终局 | contexts | 原始latency | 原始frequency |
|---|---|---|---:|---|---|
| smolvla/0 | trial-303269581-trialrun-303269581-worker-0 / 0 / GPU-7f71438a-f878-bc66-8a4e-569afc9e059e | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_0/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_0/frequency.jsonl) |
| smolvla/1 | trial-303269581-trialrun-303269581-worker-0 / 1 / GPU-660cc922-7249-e74d-ef3f-2375a073a009 | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_1/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_1/frequency.jsonl) |
| smolvla/2 | trial-303269581-trialrun-303269581-worker-0 / 2 / GPU-7a6af46c-023f-10a9-3320-5f77d6931ceb | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_2/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_2/frequency.jsonl) |
| smolvla/3 | trial-303269581-trialrun-303269581-worker-0 / 3 / GPU-f8683145-0833-8aa1-5ded-e026f9ad9adb | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_3/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_3/frequency.jsonl) |
| xvla/4 | trial-303269581-trialrun-303269581-worker-0 / 4 / GPU-c3f3580b-5658-e4bb-b7cf-006b40028a97 | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_4/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_4/frequency.jsonl) |
| xvla/5 | trial-303269581-trialrun-303269581-worker-0 / 5 / GPU-57220e5f-dc72-b04c-39bb-9857d5d720cd | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_5/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_5/frequency.jsonl) |
| xvla/6 | trial-303269581-trialrun-303269581-worker-0 / 6 / GPU-6e06f449-5763-6e68-28a2-bb311c033bcd | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_6/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_6/frequency.jsonl) |
| xvla/7 | trial-303269581-trialrun-303269581-worker-0 / 7 / GPU-ff17fd89-47b4-887c-f53a-ccdde554cb80 | complete | 5 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_7/latency.jsonl) | [frequency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/workers/worker_7/frequency.jsonl) |
