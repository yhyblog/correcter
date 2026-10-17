# 小批量推理效率补测

汇总时间：2026-09-25T19:27:29.994200+00:00；数据状态：complete。

仅纳入源 RESULT.json 标记 complete 的非预热查询；技术失败或未结束源已经写出的计时保留在原始文件，排除数量另列。缺测为 NR，不填零。

统计量为逐查询算术均值和 P95（与 NumPy quantile 的 linear 插值一致）。重复查询不是独立环境初态；源覆盖与查询 n 同时报告。

N/R 计算时间覆盖原生预处理、完整采样与反归一化；Post 另含 Q objective、动作梯度及投影。Post extra 为每条 Post 记录的 query_seconds − policy_seconds 后再汇总，不是不同方法均值相减。

监测单独报告，每个源、每次 repetition 在 N/R/Post 中重复存储的 monitor 只计一次。Post 查询不含前置监测，完整辅助开销需结合监测表；分项可能包含/重叠，不能全部机械相加，更不能相加 P95。wall 是逐查询完整调用墙钟，包含该调用通信，不含单独 monitor。

模型加载、环境步进、渲染和预热不计入查询分布。Q 在 CPU，原生 GPU 计时边界同步。每卡 batch size 1，当前批次的每 GPU 汇总用于观察设备/上下文差异，不作跨主机性能校正。

## 源覆盖

| 底座 | 计划 | 完成 | cut前终止 | 技术失败 | partial | 未开始 | 未完整源非预热行 |
|---|---:|---:|---:|---:|---:|---:|---:|
| smolvla | 20 | 20 | 0 | 0 | 0 | 0 | 0 |
| xvla | 20 | 20 | 0 | 0 | 0 | 0 | 0 |

## 查询耗时

| 底座 | 方法/组件 | n | 源数 | 均值 ms | P95 ms |
|---|---|---:|---:|---:|---:|
| smolvla | N / policy_seconds | 100 | 20 | 161.507 | 166.298 |
| smolvla | N / query_seconds | 100 | 20 | 161.507 | 166.298 |
| smolvla | N / query_wall_seconds | 100 | 20 | 161.608 | 166.407 |
| smolvla | Post / policy_seconds | 100 | 20 | 162.721 | 167.294 |
| smolvla | Post / query_seconds | 100 | 20 | 172.679 | 177.459 |
| smolvla | Post / query_wall_seconds | 100 | 20 | 173.432 | 178.232 |
| smolvla | R / policy_seconds | 100 | 20 | 161.478 | 166.859 |
| smolvla | R / query_seconds | 100 | 20 | 161.478 | 166.859 |
| smolvla | R / query_wall_seconds | 100 | 20 | 161.568 | 167.002 |
| xvla | N / policy_seconds | 100 | 20 | 95.540 | 98.161 |
| xvla | N / query_seconds | 100 | 20 | 95.540 | 98.161 |
| xvla | N / query_wall_seconds | 100 | 20 | 95.632 | 98.268 |
| xvla | Post / policy_seconds | 100 | 20 | 95.997 | 98.399 |
| xvla | Post / query_seconds | 100 | 20 | 105.719 | 108.036 |
| xvla | Post / query_wall_seconds | 100 | 20 | 106.409 | 108.799 |
| xvla | R / policy_seconds | 100 | 20 | 96.381 | 99.021 |
| xvla | R / query_seconds | 100 | 20 | 96.381 | 99.021 |
| xvla | R / query_wall_seconds | 100 | 20 | 96.467 | 99.100 |

## 纠偏与监测组件

| 底座 | 方法/组件 | n | 源数 | 均值 ms | P95 ms |
|---|---|---:|---:|---:|---:|
| smolvla | Post / gradient_seconds | 100 | 20 | 3.512 | 3.708 |
| smolvla | Post / objective_seconds | 100 | 20 | 5.790 | 6.204 |
| smolvla | Post / post_extra_seconds | 100 | 20 | 9.958 | 10.573 |
| smolvla | Post / projection_seconds | 100 | 20 | 0.655 | 0.709 |
| smolvla | monitor / D_seconds | 100 | 20 | 3.668 | 3.899 |
| smolvla | monitor / G0_seconds | 100 | 20 | 1.896 | 2.044 |
| smolvla | monitor / context_seconds | 100 | 20 | 0.271 | 0.296 |
| smolvla | monitor / feature_seconds | 100 | 20 | 51.152 | 54.845 |
| smolvla | monitor / monitor_seconds | 100 | 20 | 57.335 | 61.212 |
| smolvla | monitor / rpc_wall_seconds | 100 | 20 | 61.604 | 66.195 |
| xvla | Post / gradient_seconds | 100 | 20 | 3.488 | 3.692 |
| xvla | Post / objective_seconds | 100 | 20 | 5.586 | 6.110 |
| xvla | Post / post_extra_seconds | 100 | 20 | 9.722 | 10.427 |
| xvla | Post / projection_seconds | 100 | 20 | 0.648 | 0.713 |
| xvla | monitor / D_seconds | 100 | 20 | 3.633 | 3.939 |
| xvla | monitor / G0_seconds | 100 | 20 | 1.856 | 1.965 |
| xvla | monitor / context_seconds | 100 | 20 | 0.269 | 0.292 |
| xvla | monitor / feature_seconds | 100 | 20 | 49.252 | 54.136 |
| xvla | monitor / monitor_seconds | 100 | 20 | 55.342 | 60.463 |
| xvla | monitor / rpc_wall_seconds | 100 | 20 | 59.342 | 64.360 |

成员时间数组仅保留在原始记录，不作为标量时延分项汇总：D_member_seconds、G0_member_seconds。D/G0整组的标量耗时仍正常汇总。

## 每 GPU 查询摘要

| 主机 | GPU | UUID | 底座 | 方法 | n | 均值 ms | P95 ms |
|---|---|---|---|---|---:|---:|---:|
| trial-303269581-trialrun-303269581-worker-0 | 0 | GPU-7f71438a-f878-bc66-8a4e-569afc9e059e | smolvla | N | 25 | 159.589 | 162.717 |
| trial-303269581-trialrun-303269581-worker-0 | 1 | GPU-660cc922-7249-e74d-ef3f-2375a073a009 | smolvla | N | 25 | 164.184 | 172.082 |
| trial-303269581-trialrun-303269581-worker-0 | 2 | GPU-7a6af46c-023f-10a9-3320-5f77d6931ceb | smolvla | N | 25 | 162.984 | 164.561 |
| trial-303269581-trialrun-303269581-worker-0 | 3 | GPU-f8683145-0833-8aa1-5ded-e026f9ad9adb | smolvla | N | 25 | 159.272 | 162.995 |
| trial-303269581-trialrun-303269581-worker-0 | 0 | GPU-7f71438a-f878-bc66-8a4e-569afc9e059e | smolvla | Post | 25 | 169.816 | 172.085 |
| trial-303269581-trialrun-303269581-worker-0 | 1 | GPU-660cc922-7249-e74d-ef3f-2375a073a009 | smolvla | Post | 25 | 179.755 | 196.647 |
| trial-303269581-trialrun-303269581-worker-0 | 2 | GPU-7a6af46c-023f-10a9-3320-5f77d6931ceb | smolvla | Post | 25 | 172.776 | 175.261 |
| trial-303269581-trialrun-303269581-worker-0 | 3 | GPU-f8683145-0833-8aa1-5ded-e026f9ad9adb | smolvla | Post | 25 | 168.368 | 171.128 |
| trial-303269581-trialrun-303269581-worker-0 | 0 | GPU-7f71438a-f878-bc66-8a4e-569afc9e059e | smolvla | R | 25 | 160.064 | 162.415 |
| trial-303269581-trialrun-303269581-worker-0 | 1 | GPU-660cc922-7249-e74d-ef3f-2375a073a009 | smolvla | R | 25 | 164.093 | 171.023 |
| trial-303269581-trialrun-303269581-worker-0 | 2 | GPU-7a6af46c-023f-10a9-3320-5f77d6931ceb | smolvla | R | 25 | 162.499 | 166.674 |
| trial-303269581-trialrun-303269581-worker-0 | 3 | GPU-f8683145-0833-8aa1-5ded-e026f9ad9adb | smolvla | R | 25 | 159.256 | 161.772 |
| trial-303269581-trialrun-303269581-worker-0 | 4 | GPU-c3f3580b-5658-e4bb-b7cf-006b40028a97 | xvla | N | 25 | 94.952 | 96.004 |
| trial-303269581-trialrun-303269581-worker-0 | 5 | GPU-57220e5f-dc72-b04c-39bb-9857d5d720cd | xvla | N | 25 | 95.201 | 96.968 |
| trial-303269581-trialrun-303269581-worker-0 | 6 | GPU-6e06f449-5763-6e68-28a2-bb311c033bcd | xvla | N | 25 | 97.293 | 98.672 |
| trial-303269581-trialrun-303269581-worker-0 | 7 | GPU-ff17fd89-47b4-887c-f53a-ccdde554cb80 | xvla | N | 25 | 94.714 | 96.591 |
| trial-303269581-trialrun-303269581-worker-0 | 4 | GPU-c3f3580b-5658-e4bb-b7cf-006b40028a97 | xvla | Post | 25 | 105.329 | 106.625 |
| trial-303269581-trialrun-303269581-worker-0 | 5 | GPU-57220e5f-dc72-b04c-39bb-9857d5d720cd | xvla | Post | 25 | 104.574 | 106.265 |
| trial-303269581-trialrun-303269581-worker-0 | 6 | GPU-6e06f449-5763-6e68-28a2-bb311c033bcd | xvla | Post | 25 | 107.483 | 123.117 |
| trial-303269581-trialrun-303269581-worker-0 | 7 | GPU-ff17fd89-47b4-887c-f53a-ccdde554cb80 | xvla | Post | 25 | 105.490 | 107.480 |
| trial-303269581-trialrun-303269581-worker-0 | 4 | GPU-c3f3580b-5658-e4bb-b7cf-006b40028a97 | xvla | R | 25 | 95.544 | 97.003 |
| trial-303269581-trialrun-303269581-worker-0 | 5 | GPU-57220e5f-dc72-b04c-39bb-9857d5d720cd | xvla | R | 25 | 94.817 | 97.140 |
| trial-303269581-trialrun-303269581-worker-0 | 6 | GPU-6e06f449-5763-6e68-28a2-bb311c033bcd | xvla | R | 25 | 98.187 | 112.817 |
| trial-303269581-trialrun-303269581-worker-0 | 7 | GPU-ff17fd89-47b4-887c-f53a-ccdde554cb80 | xvla | R | 25 | 96.976 | 98.083 |

## 原始证据与缺测

[CONFIG](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/CONFIG.json) · [SUMMARY.json](SUMMARY.json) · [查询 CSV](QUERY_LATENCY.csv) · [组件 CSV](COMPONENT_LATENCY.csv) · [协议](PROTOCOL.md)

数据问题记录 0 项，逐项见 SUMMARY.json 的 issues；各类排除/缺字段计数见 SAMPLE_COUNTS。

| 底座 | 源 | 任务 | 状态 | 纳入查询 | 原始计时 | 终局 |
|---|---|---|---|---:|---|---|
| smolvla | efficiency20260925_smolvla_t00 | assembly-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_0/sources/efficiency20260925_smolvla_t00/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_0/sources/efficiency20260925_smolvla_t00/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t10 | coffee-push-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_0/sources/efficiency20260925_smolvla_t10/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_0/sources/efficiency20260925_smolvla_t10/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t21 | hammer-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_0/sources/efficiency20260925_smolvla_t21/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_0/sources/efficiency20260925_smolvla_t21/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t31 | pick-place-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_0/sources/efficiency20260925_smolvla_t31/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_0/sources/efficiency20260925_smolvla_t31/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t41 | reach-wall-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_0/sources/efficiency20260925_smolvla_t41/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_0/sources/efficiency20260925_smolvla_t41/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t03 | box-close-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_1/sources/efficiency20260925_smolvla_t03/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_1/sources/efficiency20260925_smolvla_t03/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t13 | door-close-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_1/sources/efficiency20260925_smolvla_t13/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_1/sources/efficiency20260925_smolvla_t13/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t23 | handle-press-side-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_1/sources/efficiency20260925_smolvla_t23/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_1/sources/efficiency20260925_smolvla_t23/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t34 | plate-slide-back-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_1/sources/efficiency20260925_smolvla_t34/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_1/sources/efficiency20260925_smolvla_t34/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t44 | stick-pull-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_1/sources/efficiency20260925_smolvla_t44/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_1/sources/efficiency20260925_smolvla_t44/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t05 | button-press-topdown-wall-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_2/sources/efficiency20260925_smolvla_t05/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_2/sources/efficiency20260925_smolvla_t05/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t15 | door-open-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_2/sources/efficiency20260925_smolvla_t15/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_2/sources/efficiency20260925_smolvla_t15/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t26 | handle-pull-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_2/sources/efficiency20260925_smolvla_t26/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_2/sources/efficiency20260925_smolvla_t26/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t36 | plate-slide-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_2/sources/efficiency20260925_smolvla_t36/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_2/sources/efficiency20260925_smolvla_t36/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t46 | sweep-into-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_2/sources/efficiency20260925_smolvla_t46/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_2/sources/efficiency20260925_smolvla_t46/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t08 | coffee-button-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_3/sources/efficiency20260925_smolvla_t08/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_3/sources/efficiency20260925_smolvla_t08/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t18 | drawer-open-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_3/sources/efficiency20260925_smolvla_t18/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_3/sources/efficiency20260925_smolvla_t18/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t28 | peg-insert-side-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_3/sources/efficiency20260925_smolvla_t28/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_3/sources/efficiency20260925_smolvla_t28/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t39 | push-wall-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_3/sources/efficiency20260925_smolvla_t39/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_3/sources/efficiency20260925_smolvla_t39/RESULT.json) |
| smolvla | efficiency20260925_smolvla_t49 | window-open-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_3/sources/efficiency20260925_smolvla_t49/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_3/sources/efficiency20260925_smolvla_t49/RESULT.json) |
| xvla | efficiency20260925_xvla_t00 | assembly-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_4/sources/efficiency20260925_xvla_t00/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_4/sources/efficiency20260925_xvla_t00/RESULT.json) |
| xvla | efficiency20260925_xvla_t10 | coffee-push-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_4/sources/efficiency20260925_xvla_t10/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_4/sources/efficiency20260925_xvla_t10/RESULT.json) |
| xvla | efficiency20260925_xvla_t21 | hammer-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_4/sources/efficiency20260925_xvla_t21/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_4/sources/efficiency20260925_xvla_t21/RESULT.json) |
| xvla | efficiency20260925_xvla_t31 | pick-place-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_4/sources/efficiency20260925_xvla_t31/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_4/sources/efficiency20260925_xvla_t31/RESULT.json) |
| xvla | efficiency20260925_xvla_t41 | reach-wall-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_4/sources/efficiency20260925_xvla_t41/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_4/sources/efficiency20260925_xvla_t41/RESULT.json) |
| xvla | efficiency20260925_xvla_t03 | box-close-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_5/sources/efficiency20260925_xvla_t03/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_5/sources/efficiency20260925_xvla_t03/RESULT.json) |
| xvla | efficiency20260925_xvla_t13 | door-close-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_5/sources/efficiency20260925_xvla_t13/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_5/sources/efficiency20260925_xvla_t13/RESULT.json) |
| xvla | efficiency20260925_xvla_t23 | handle-press-side-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_5/sources/efficiency20260925_xvla_t23/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_5/sources/efficiency20260925_xvla_t23/RESULT.json) |
| xvla | efficiency20260925_xvla_t34 | plate-slide-back-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_5/sources/efficiency20260925_xvla_t34/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_5/sources/efficiency20260925_xvla_t34/RESULT.json) |
| xvla | efficiency20260925_xvla_t44 | stick-pull-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_5/sources/efficiency20260925_xvla_t44/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_5/sources/efficiency20260925_xvla_t44/RESULT.json) |
| xvla | efficiency20260925_xvla_t05 | button-press-topdown-wall-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_6/sources/efficiency20260925_xvla_t05/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_6/sources/efficiency20260925_xvla_t05/RESULT.json) |
| xvla | efficiency20260925_xvla_t15 | door-open-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_6/sources/efficiency20260925_xvla_t15/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_6/sources/efficiency20260925_xvla_t15/RESULT.json) |
| xvla | efficiency20260925_xvla_t26 | handle-pull-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_6/sources/efficiency20260925_xvla_t26/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_6/sources/efficiency20260925_xvla_t26/RESULT.json) |
| xvla | efficiency20260925_xvla_t36 | plate-slide-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_6/sources/efficiency20260925_xvla_t36/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_6/sources/efficiency20260925_xvla_t36/RESULT.json) |
| xvla | efficiency20260925_xvla_t46 | sweep-into-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_6/sources/efficiency20260925_xvla_t46/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_6/sources/efficiency20260925_xvla_t46/RESULT.json) |
| xvla | efficiency20260925_xvla_t08 | coffee-button-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_7/sources/efficiency20260925_xvla_t08/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_7/sources/efficiency20260925_xvla_t08/RESULT.json) |
| xvla | efficiency20260925_xvla_t18 | drawer-open-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_7/sources/efficiency20260925_xvla_t18/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_7/sources/efficiency20260925_xvla_t18/RESULT.json) |
| xvla | efficiency20260925_xvla_t28 | peg-insert-side-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_7/sources/efficiency20260925_xvla_t28/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_7/sources/efficiency20260925_xvla_t28/RESULT.json) |
| xvla | efficiency20260925_xvla_t39 | push-wall-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_7/sources/efficiency20260925_xvla_t39/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_7/sources/efficiency20260925_xvla_t39/RESULT.json) |
| xvla | efficiency20260925_xvla_t49 | window-open-v3 | complete | 15 | [timings](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_7/sources/efficiency20260925_xvla_t49/timings.jsonl) | [RESULT](/mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/inference_efficiency_20260925/workers/worker_7/sources/efficiency20260925_xvla_t49/RESULT.json) |
