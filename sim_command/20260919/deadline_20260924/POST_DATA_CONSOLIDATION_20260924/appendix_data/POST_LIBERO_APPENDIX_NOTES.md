# LIBERO 附录数据：已有算子适配，非 L11 完整方法

配置：官方 π0.5 LIBERO 权重/normalizer，raw H=10、实际执行 K=5、NFE=10；执行20个命令后的自然重规划点固定一次纠偏，只改5步 XYZ/夹爪，不含 D/G0。不属于当前 MT50 的 L11 + multi 完整系统。四suite各10任务、每任务每方法10次，合计计划400；N399有效、Goal/task0有1个未知，Post400有效。已有随机 reset/policy seeds 逐源配对，不是官方固定初态榜单。

| Suite | N SR (%) | Post Operator SR (%) | N Calls | Post Calls | Post Interventions | Paired Δ (pp) | Rescue / Harm | 95% CI (pp) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| libero_spatial | 98.00 | 96.00 | 21.990 | 22.130 | 0.380 | -2.00 | 0 / 2 | [-4.76, +0.76] |
| libero_object | 100.00 | 100.00 | 28.590 | 28.280 | 0.870 | +0.00 | 0 / 0 | [+0.00, +0.00] |
| libero_goal | 98.99 | 100.00 | 22.768 | 22.680 | 0.580 | +1.01 | 1 / 0 | [-0.97, +2.99] |
| libero_10 | 91.00 | 91.00 | 55.320 | 55.200 | 0.640 | +0.00 | 4 / 4 | [-5.57, +5.57] |
| all_four_suites | 96.99 | 96.75 | 32.190 | 32.072 | 0.618 | -0.25 | 5 / 6 | [-1.88, +1.38] |

N整体387/399；Post整体387/400。严格共同399对中Post386成功、N387成功，5救回/6损害，因此不能直接拿不同分母总成功率的差当配对差。区间沿原配对正态近似；描述性且未多重校正；Object [0,0]不证明等效。

## 每任务明细

| Suite | Task ID | Task | N SR (%) | Post Operator SR (%) | N Calls | Post Calls | Rescue / Harm |
|---|---:|---|---:|---:|---:|---:|---:|
| libero_spatial | 0 | pick up the black bowl between the plate and the ramekin and place it on the plate | 90.0 | 90.0 | 21.700 | 19.900 | 0 / 0 |
| libero_spatial | 1 | pick up the black bowl next to the ramekin and place it on the plate | 100.0 | 100.0 | 22.100 | 22.200 | 0 / 0 |
| libero_spatial | 2 | pick up the black bowl from table center and place it on the plate | 100.0 | 100.0 | 19.500 | 19.300 | 0 / 0 |
| libero_spatial | 3 | pick up the black bowl on the cookie box and place it on the plate | 100.0 | 100.0 | 17.200 | 17.300 | 0 / 0 |
| libero_spatial | 4 | pick up the black bowl in the top drawer of the wooden cabinet and place it on the plate | 100.0 | 100.0 | 25.300 | 25.400 | 0 / 0 |
| libero_spatial | 5 | pick up the black bowl on the ramekin and place it on the plate | 100.0 | 90.0 | 20.700 | 22.600 | 0 / 1 |
| libero_spatial | 6 | pick up the black bowl next to the cookie box and place it on the plate | 100.0 | 100.0 | 21.500 | 21.400 | 0 / 0 |
| libero_spatial | 7 | pick up the black bowl on the stove and place it on the plate | 100.0 | 100.0 | 24.500 | 24.100 | 0 / 0 |
| libero_spatial | 8 | pick up the black bowl next to the plate and place it on the plate | 100.0 | 100.0 | 20.600 | 20.700 | 0 / 0 |
| libero_spatial | 9 | pick up the black bowl on the wooden cabinet and place it on the plate | 90.0 | 80.0 | 26.800 | 28.400 | 0 / 1 |
| libero_object | 0 | pick up the alphabet soup and place it in the basket | 100.0 | 100.0 | 30.600 | 30.900 | 0 / 0 |
| libero_object | 1 | pick up the cream cheese and place it in the basket | 100.0 | 100.0 | 29.300 | 27.200 | 0 / 0 |
| libero_object | 2 | pick up the salad dressing and place it in the basket | 100.0 | 100.0 | 25.500 | 24.900 | 0 / 0 |
| libero_object | 3 | pick up the bbq sauce and place it in the basket | 100.0 | 100.0 | 26.900 | 26.100 | 0 / 0 |
| libero_object | 4 | pick up the ketchup and place it in the basket | 100.0 | 100.0 | 29.300 | 29.000 | 0 / 0 |
| libero_object | 5 | pick up the tomato sauce and place it in the basket | 100.0 | 100.0 | 29.400 | 27.500 | 0 / 0 |
| libero_object | 6 | pick up the butter and place it in the basket | 100.0 | 100.0 | 31.200 | 31.800 | 0 / 0 |
| libero_object | 7 | pick up the milk and place it in the basket | 100.0 | 100.0 | 26.200 | 27.400 | 0 / 0 |
| libero_object | 8 | pick up the chocolate pudding and place it in the basket | 100.0 | 100.0 | 31.600 | 32.700 | 0 / 0 |
| libero_object | 9 | pick up the orange juice and place it in the basket | 100.0 | 100.0 | 25.900 | 25.300 | 0 / 0 |
| libero_goal | 0 | open the middle drawer of the cabinet | 100.0 | 100.0 | 24.444 | 25.500 | 0 / 0 |
| libero_goal | 1 | put the bowl on the stove | 90.0 | 100.0 | 21.400 | 17.300 | 1 / 0 |
| libero_goal | 2 | put the wine bottle on top of the cabinet | 100.0 | 100.0 | 18.000 | 18.200 | 0 / 0 |
| libero_goal | 3 | open the top drawer and put the bowl inside | 100.0 | 100.0 | 38.800 | 39.500 | 0 / 0 |
| libero_goal | 4 | put the bowl on top of the cabinet | 100.0 | 100.0 | 18.300 | 17.900 | 0 / 0 |
| libero_goal | 5 | push the plate to the front of the stove | 100.0 | 100.0 | 30.400 | 32.500 | 0 / 0 |
| libero_goal | 6 | put the cream cheese in the bowl | 100.0 | 100.0 | 18.700 | 18.600 | 0 / 0 |
| libero_goal | 7 | turn on the stove | 100.0 | 100.0 | 15.400 | 15.100 | 0 / 0 |
| libero_goal | 8 | put the bowl on the plate | 100.0 | 100.0 | 15.300 | 15.100 | 0 / 0 |
| libero_goal | 9 | put the wine bottle on the rack | 100.0 | 100.0 | 27.100 | 27.100 | 0 / 0 |
| libero_10 | 0 | put both the alphabet soup and the tomato sauce in the basket | 100.0 | 90.0 | 53.800 | 57.900 | 0 / 1 |
| libero_10 | 1 | put both the cream cheese box and the butter in the basket | 100.0 | 100.0 | 50.900 | 50.400 | 0 / 0 |
| libero_10 | 2 | turn on the stove and put the moka pot on it | 90.0 | 90.0 | 56.900 | 57.500 | 1 / 1 |
| libero_10 | 3 | put the black bowl in the bottom drawer of the cabinet and close it | 90.0 | 100.0 | 50.600 | 45.100 | 1 / 0 |
| libero_10 | 4 | put the white mug on the left plate and put the yellow and white mug on the right plate | 90.0 | 100.0 | 52.100 | 46.200 | 1 / 0 |
| libero_10 | 5 | pick up the book and place it in the back compartment of the caddy | 100.0 | 100.0 | 36.000 | 38.600 | 0 / 0 |
| libero_10 | 6 | put the white mug on the plate and put the chocolate pudding to the right of the plate | 90.0 | 90.0 | 50.800 | 50.500 | 0 / 0 |
| libero_10 | 7 | put both the alphabet soup and the cream cheese box in the basket | 100.0 | 100.0 | 54.600 | 56.000 | 0 / 0 |
| libero_10 | 8 | put both moka pots on the stove | 50.0 | 40.0 | 93.300 | 95.700 | 1 / 2 |
| libero_10 | 9 | put the yellow and white mug in the microwave and close it | 100.0 | 100.0 | 54.200 | 54.100 | 0 / 0 |

## 证据局限

- 本地原生Q为BCE四成员、9301–9304、各4000步；train120候选/24父源仅5负例，validation40候选/8父源全部成功。不是L11，不把描述性validation100%视作故障判别能力。
- Full系统新增开发40attempt中30有效成功、10技术失败，G0仅7train+4validation全零收益；D2/G0/L11实际更新0，Full-Post测试0，成功率应填“未评测”，不填0%或算子数字。
- 400 Post按suite/40任务与399 N比对，调用全部可读；Post总12829、平均32.0725，实际干预247、平均0.6175。调用数应与本配置对比，不能套用MT50预算或解释成当前multi成本。

## 精确小文件来源

- Post_summary: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/D24_E8_LIBERO_POST_r1/N_POST_SUMMARY.json`
- Post_batch: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B_D24_LIBERO_POST_V1_r1/LIBERO_POST_BATCH.json`
- N_combined_index: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1/COMBINED_N_INDEX.json`
- paired_published: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1/revisions/r03/E8_PAIRED.csv`
- full_result: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/receipts/A/A_D24_LIBERO_FULL_NATIVE_V1_RESULT_r13.json`
- Post_episode_jsonls:
  - `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/jobs/pi05official_Post_libero_spatial_s0_r1/episodes.jsonl`
  - `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/jobs/pi05official_Post_libero_spatial_s1_r1/episodes.jsonl`
  - `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/jobs/pi05official_Post_libero_object_s0_r1/episodes.jsonl`
  - `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/jobs/pi05official_Post_libero_object_s1_r1/episodes.jsonl`
  - `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/jobs/pi05official_Post_libero_goal_s0_r1/episodes.jsonl`
  - `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/jobs/pi05official_Post_libero_goal_s1_r1/episodes.jsonl`
  - `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/jobs/pi05official_Post_libero_10_s0_r1/episodes.jsonl`
  - `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_EXTENSION_REMAINDER_V1/r1/jobs/pi05official_Post_libero_10_s1_r1/episodes.jsonl`
