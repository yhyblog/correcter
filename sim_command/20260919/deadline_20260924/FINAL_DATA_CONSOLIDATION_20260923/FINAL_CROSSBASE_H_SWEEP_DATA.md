# Final cross-backbone H sweep

All 24 new cells complete, 12000 unique valid terminal units. Checked 2026-09-23T17:06:18.313165+00:00.

| Model | Method | H | Successes / valid | SR (%) | Policy calls | Flow calls | Interventions | Action gradients |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| SmolVLA | N | 20 | 226 / 500 | 45.2 | 9.996 | 99.960 | 0.000 | 0.000 |
| SmolVLA | N | 30 | 205 / 500 | 41.0 | 7.036 | 70.360 | 0.000 | 0.000 |
| SmolVLA | Post | 20 | 251 / 500 | 50.2 | 13.338 | 133.380 | 3.096 | 3.096 |
| SmolVLA | Post | 30 | 238 / 500 | 47.6 | 11.098 | 110.980 | 3.194 | 3.194 |
| SmolVLA | R | 20 | 246 / 500 | 49.2 | 13.328 | 133.280 | 3.044 | 0.000 |
| SmolVLA | R | 30 | 234 / 500 | 46.8 | 11.212 | 112.120 | 3.224 | 0.000 |
| SmolVLA | Velocity | 20 | 245 / 500 | 49.0 | 16.680 | 166.800 | 3.142 | 9.426 |
| SmolVLA | Velocity | 30 | 234 / 500 | 46.8 | 14.728 | 147.280 | 3.324 | 9.972 |
| SmolVLA | N | 40 | 191 / 500 | 38.2 | 5.780 | 57.800 | 0.000 | 0.000 |
| SmolVLA | N | 50 | 169 / 500 | 33.8 | 4.576 | 45.760 | 0.000 | 0.000 |
| SmolVLA | Post | 40 | 223 / 500 | 44.6 | 10.134 | 101.340 | 3.200 | 3.200 |
| SmolVLA | Post | 50 | 228 / 500 | 45.6 | 9.280 | 92.800 | 3.172 | 3.172 |
| SmolVLA | R | 40 | 222 / 500 | 44.4 | 10.302 | 103.020 | 3.276 | 0.000 |
| SmolVLA | R | 50 | 226 / 500 | 45.2 | 9.462 | 94.620 | 3.264 | 0.000 |
| SmolVLA | Velocity | 40 | 219 / 500 | 43.8 | 13.816 | 138.160 | 3.360 | 10.080 |
| SmolVLA | Velocity | 50 | 218 / 500 | 43.6 | 12.994 | 129.940 | 3.344 | 10.032 |
| X-VLA | N | 20 | 388 / 500 | 77.6 | 6.612 | 66.120 | 0.000 | 0.000 |
| X-VLA | N | 30 | 385 / 500 | 77.0 | 4.572 | 45.720 | 0.000 | 0.000 |
| X-VLA | Post | 20 | 398 / 500 | 79.6 | 10.352 | 103.520 | 3.396 | 3.396 |
| X-VLA | Post | 30 | 385 / 500 | 77.0 | 9.898 | 98.980 | 3.848 | 3.848 |
| X-VLA | R | 20 | 393 / 500 | 78.6 | 10.524 | 105.240 | 3.490 | 0.000 |
| X-VLA | R | 30 | 394 / 500 | 78.8 | 9.584 | 95.840 | 3.716 | 0.000 |
| X-VLA | Velocity | 20 | 399 / 500 | 79.8 | 13.586 | 135.860 | 3.346 | 10.038 |
| X-VLA | Velocity | 30 | 388 / 500 | 77.6 | 13.654 | 136.540 | 3.822 | 11.466 |

Mean costs aggregate only the 500 unique valid terminal episodes in each cell, including successes and scientific failures. Technical-failure attempts are excluded from these means and retained separately. Sampling is returned policy_queries; flow=NFE10*sampling.

Explicit_rows and structural_zero_rows are separate. A zero-intervention episode cannot execute a correction gradient; N/R cannot execute Q/action-gradient. Missing nonstructural values are left unknown, never filled as zero.

A: 4381 attempts, 4000 valid, 381 preserved technical failures. B: 4384 attempts, 4000 valid, 384 preserved technical failures; zero-episode r2 launch failure also preserved. C: 4000 attempts/valid, no technical failures.

- A: 2026-09-23T13:50:35.206990+00:00, complete; /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_CROSSBASE_H_SWEEP_V1_RECOVERY_r2/RESULT.json
- B: 2026-09-23T14:10:15.578023+00:00, complete; /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/B/B_D24_CROSSBASE_H_SWEEP_V1/recovery/velocity_r3/RESULT.json
- C: 2026-09-23T13:36:34.856439+00:00, authorized_H_sweep_complete; /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_CROSSBASE_H_SWEEP_V1/RESULT.json

- No new blind test: fixed already revealed MT50 500-source set. No selection or calibration on these values.
- Frozen per-model L11 fit9101 and native10 D/G0 heads; no per-H retraining/calibration.
- SmolVLA raw50, X-VLA raw30; natural H independent of correction C10.
- Velocity remains other-work data, excluded from Post paper.
- A publication retried on CPU; publication attempts are not scientific episode attempts. B r2 startup failure consumed no episode and is preserved; r3 terminates complete.
- No new compute, hardware query, large hashes, weights/images or whole-event logs read.
