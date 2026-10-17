# SmolVLA / X-VLA 原生并行反馈＋Q延时

汇总时间：2026-09-26T03:49:44.434536+00:00；状态：complete。

本次仅新增 `parallel_feedback_with_Q`：有效查询200条，预热40条。未重跑N、monitor、无纠偏并行或频率实验。

策略与原生完整D/G0反馈同卡并行，二者完成后执行CPU Q纠偏。主指标是外层直接实测墙钟；P95按逐条墙钟linear插值，未以分项和或最大值替代。feedback_seconds可包含供Q使用的特征CPU传输；q_seconds是本条查询实际计时的Q段，不能由新旧批次总耗时之差替代。

D/G0沿用上轮随机网络与本底座原生特征。Q新建四个随机w512成员，各3,781,122参数，CPU FP32、2线程；16维视觉＋8维语言＋37维其余输入的预处理也未训练。残差尺度为[0.15,0.15,0.15,0.4]重复10步。Q段包含动作梯度、各自原生保存的postprocessor导数/std构成的S²及project_solo投影，不使用π0.5动作尺度。全部训练0步。

两个底座复用相同20个π0.5轨迹保存的真实RGB/本体/原始动作快照，重新计算原生特征，不读取π特征。本结果仅验证此随机网络结构的计算延时，不证明成功率、预测准确性或纠偏有效性。

## 本次实测

| 底座 | 指标 | n | contexts | 均值 ms | P95 ms | ≤333.333ms比例 |
|---|---|---:|---:|---:|---:|---:|
| smolvla | wall_seconds | 100 | 20 | 190.567 | 196.090 | 100.000% |
| smolvla | policy_seconds | 100 | 20 | 175.963 | 180.907 | — |
| smolvla | feedback_seconds | 100 | 20 | 50.472 | 54.400 | — |
| smolvla | q_seconds | 100 | 20 | 14.275 | 16.079 | — |
| xvla | wall_seconds | 100 | 20 | 148.610 | 152.483 | 100.000% |
| xvla | policy_seconds | 100 | 20 | 130.968 | 133.592 | — |
| xvla | feedback_seconds | 100 | 20 | 134.588 | 138.313 | — |
| xvla | q_seconds | 100 | 20 | 13.690 | 15.118 | — |

## 上轮对照：历史批次复用，不计入本次样本数

来源：[上轮SUMMARY](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_latency_20260926/SUMMARY.json)。仅并列不同批次的实际墙钟，不将其差值解释为单独Q成本。

| 底座 | 历史case | n（历史） | 均值 ms | P95 ms |
|---|---|---:|---:|---:|
| smolvla | N | 100 | 151.583 | 155.549 |
| smolvla | parallel_feedback_no_intervention | 100 | 171.168 | 174.837 |
| xvla | N | 100 | 86.871 | 89.229 |
| xvla | parallel_feedback_no_intervention | 100 | 128.126 | 131.814 |

## 每worker新查询墙钟

| 底座/worker/GPU | n | 均值 ms | P95 ms |
|---|---:|---:|---:|
| smolvla/0/0 | 25 | 192.070 | 210.080 |
| smolvla/1/1 | 25 | 191.761 | 195.819 |
| smolvla/2/2 | 25 | 189.330 | 192.006 |
| smolvla/3/3 | 25 | 189.107 | 191.579 |
| xvla/4/4 | 25 | 149.235 | 153.117 |
| xvla/5/5 | 25 | 150.819 | 161.544 |
| xvla/6/6 | 25 | 145.444 | 149.043 |
| xvla/7/7 | 25 | 148.941 | 150.705 |

## 完成状态与证据

数据问题0项，详见SUMMARY.issues。技术失败/partial状态保留；已写出的有效计时保留，缺测NR不填0。

[SUMMARY](SUMMARY.json) · [LATENCY.csv](LATENCY.csv) · [CONFIG](CONFIG.json)

| 底座/worker | 终局 | 纳入/预热/排除 | 原始计时 | RESULT |
|---|---|---:|---|---|
| smolvla/0 | complete | 25/5/0 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_0/latency.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_0/RESULT.json) |
| smolvla/1 | complete | 25/5/0 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_1/latency.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_1/RESULT.json) |
| smolvla/2 | complete | 25/5/0 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_2/latency.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_2/RESULT.json) |
| smolvla/3 | complete | 25/5/0 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_3/latency.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_3/RESULT.json) |
| xvla/4 | complete | 25/5/0 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_4/latency.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_4/RESULT.json) |
| xvla/5 | complete | 25/5/0 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_5/latency.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_5/RESULT.json) |
| xvla/6 | complete | 25/5/0 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_6/latency.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_6/RESULT.json) |
| xvla/7 | complete | 25/5/0 | [latency](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_7/latency.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/smol_x_native_feedback_q_latency_20260926/workers/worker_7/RESULT.json) |
