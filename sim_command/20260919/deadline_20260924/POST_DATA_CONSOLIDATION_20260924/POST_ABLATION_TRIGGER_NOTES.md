# Post ablation / trigger consolidation: source extraction

## Complete-Q loss ablation (same row per loss)

| Loss | DEV three-fit SR (%) | DEV mean ± sample SD | Revealed50 three-fit SR (%) | Revealed50 mean ± sample SD | DEV Policy Calls | Revealed50 Policy Calls | Selected |
|---|---|---:|---|---:|---:|---:|---|
| L00: BCE | 65.0 / 68.0 / 69.0 | 67.33 ± 2.08 | 76.0 / 70.0 / 70.0 | 72.00 ± 3.46 | 16.297 | 15.813 | No |
| L10: BCE + gain | 68.0 / 67.0 / 68.0 | 67.67 ± 0.58 | 70.0 / 70.0 / 68.0 | 69.33 ± 1.15 | 16.310 | 16.253 | No |
| L01: BCE + 0.5pair | 70.0 / 68.0 / 69.0 | 69.00 ± 1.00 | 70.0 / 70.0 / 66.0 | 68.67 ± 2.31 | 16.043 | 16.260 | No |
| L11: BCE + gain + 0.5pair | 69.0 / 67.0 / 67.0 | 67.67 ± 1.15 | 74.0 / 72.0 / 70.0 | 72.00 ± 2.00 | 16.277 | 15.513 | Yes |

Fit order9101/9102/9103. DEV denominator100 each; revealed selection denominator50 each. Call means pool3fits because denominators equal; values are not SD.

- Every member trained from untrained initialization with all Q parameters trainable; four losses x three fits x four members, 4000 updates/member. No old residual/advantage-only fine-tuning mixed in.
- Development uses five tasks x 20 distinct sources=100; revealed supplementary selection uses five tasks x 10 sources=50. Three fits reuse the same source set. 3 x 50 is not 150 independent states.
- L11 chosen by user from revealed selection50: highest three-fit mean tied with L00; L11 has smaller observed sample SD among tied best means. L10 has smaller SD but lower mean. Deployment fit9101 fixed.
- Selection50 overlaps MT50 main500. L11 H10 main result reuses 50 ablation results. Do not describe main500 as untouched blind test.
- Historical development-only selection chose L01. It is preserved history and is not current L11 selection evidence.
- Call means added here use direct sums over saved valid episode rows; costs include valid task failures, no new inference or tests.

## Modes: L11 Post and Q-independent R; same standard columns

| Scope | Method | Trigger / Count | H | SR (%) | Policy Calls | Mean Interventions |
|---|---|---|---:|---:|---:|---:|
| MT50 main500; L11 fit9101 Post | Post | G0-once | 10 | 68.6 | 13.840 | 0.782 |
| MT50 main500; L11 fit9101 Post | Post | G0-multi | 10 | 69.2 | 14.248 | 2.050 |
| MT50 main500; Q-independent R | R | G0-once | 10 | 67.2 | 14.156 | 0.782 |
| MT50 main500; Q-independent R | R | Random-once | 10 | 61.4 | 15.632 | 0.500 |
| MT50 main500; Q-independent R | R | G0-multi | 10 | 68.6 | 14.452 | 2.034 |
| MT50 main500; Q-independent R | R | G0-once | 20 | 62.4 | 8.742 | 0.814 |
| MT50 main500; Q-independent R | R | Random-once | 20 | 48.4 | 10.144 | 0.618 |
| MT50 main500; Q-independent R | R | G0-multi | 20 | 64.8 | 10.158 | 2.412 |
| MT50 main500; Q-independent R | R | G0-once | 30 | 61.4 | 6.690 | 0.830 |
| MT50 main500; Q-independent R | R | Random-once | 30 | 42.0 | 7.944 | 0.682 |
| MT50 main500; Q-independent R | R | G0-multi | 30 | 66.0 | 8.650 | 2.568 |
| MT50 main500; Q-independent R | R | G0-once | 40 | 58.0 | 5.872 | 0.830 |
| MT50 main500; Q-independent R | R | Random-once | 40 | 42.2 | 6.326 | 0.674 |
| MT50 main500; Q-independent R | R | G0-multi | 40 | 63.6 | 8.276 | 2.734 |
| MT50 main500; Q-independent R | R | G0-once | 50 | 59.4 | 4.844 | 0.816 |
| MT50 main500; Q-independent R | R | Random-once | 50 | 39.2 | 5.508 | 0.690 |
| MT50 main500; Q-independent R | R | G0-multi | 50 | 64.2 | 7.584 | 2.676 |

- R has no Q so these once/random/multi data remain reusable after L11 change. Historical Post random-once uses old Q; do not relabel it L11.
- Random-once schedule fixed before execution, independent of trajectory/G0/outcome; before-slot termination or invalid slot does not trigger retry, forced intervention or another sampled time.
- G0-once and Random-once actual intervention rates differ. Difference is policy-level mechanism evidence, not perfectly intervention-count matched pure timing effect.
- R paired bootstrap intervals are previously published 2000 within-task replicates seed20260921; pointwise, not multiple-corrected. L11 Post multi-once has separately published paired normal interval and exact McNemar p. Do not mix interval definitions.

## E6 trigger controls: separate50-source scope

| Method | Trigger / Count | H | SR (%) | Policy Calls | Mean Interventions | n0/n1/n≥2 |
|---|---|---:|---:|---:|---:|---|
| R | G0-once | 10 | 52.0 | 19.460 | 0.920 | 4/46/0 |
| R | D5-once | 10 | 60.0 | 17.680 | 0.900 | 5/45/0 |
| R | G0-multi | 10 | 52.0 | 21.440 | 4.800 | 4/11/35 |
| R | D5-multi | 10 | 62.0 | 20.020 | 7.600 | 5/2/43 |

- Separate five tasks x ten test ordinals10..19, disjoint from main ordinals0..9; same 50 reused across once/multi, H10/C10.
- D5 threshold0.2521600950570383 fixed on 100 development sources by matching95/100 hypothetical alarms, without reading success; not an equal multi-opportunity intervention budget.
- G0 did not beat D5 in observed once or multi outcomes. Multi reduces interventions vs D5 but increases policy calls; do not claim better SR or lower system cost.

## Sources

- full_q_result: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/RESULT.json`
- full_q_episodes: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/TECHNICAL_EPISODES_ALL_METHODS.csv`
- l11_rollup: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json`
- l11_pairs: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/FINAL_L11_POST_PAIRED_STATS.json`
- r_trigger_costs: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/analysis_20260922_current/trigger/TRIGGER_CELLS_AND_COSTS.csv`
- r_trigger_pairs: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_R_TRIGGER_MODES_V1/FINAL_PAIRED.json`
- e6_once: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_CORE_REMAINDER_V1/E6_FINAL_SUMMARY.json`
- e6_multi: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/deadline_20260924/analysis_20260923_claims/master_costs_e6_addendum.json`
- e6_multi_pairs: `/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_PRIMARY_VALIDATION_V1/PAIRED.json`
