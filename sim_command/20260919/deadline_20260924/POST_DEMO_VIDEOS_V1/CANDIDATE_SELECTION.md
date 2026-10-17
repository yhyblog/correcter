# Post qualitative comparison candidates

Historical N failure / Post L11 multi success; actual video reruns must reconfirm outcomes.

573 historical same-H rescue pairs across 38/50 tasks; 203 distinct task/initial states. Priority 103 pairs, reserve 54 pairs; at most 314 rollouts if every reserve is needed.

| Task | Rescue pairs (all H) | Distinct sources | H10 pairs | Primary | Reserve |
|---|---:|---:|---:|---:|---:|
| assembly-v3 | 0 | 0 | 0 | 0 | 0 |
| basketball-v3 | 5 | 2 | 1 | 2 | 0 |
| bin-picking-v3 | 12 | 6 | 3 | 3 | 2 |
| box-close-v3 | 28 | 7 | 3 | 3 | 2 |
| button-press-topdown-v3 | 10 | 4 | 0 | 3 | 1 |
| button-press-topdown-wall-v3 | 1 | 1 | 0 | 1 | 0 |
| button-press-v3 | 0 | 0 | 0 | 0 | 0 |
| button-press-wall-v3 | 32 | 10 | 0 | 3 | 2 |
| coffee-button-v3 | 0 | 0 | 0 | 0 | 0 |
| coffee-pull-v3 | 16 | 6 | 1 | 3 | 2 |
| coffee-push-v3 | 3 | 2 | 0 | 2 | 0 |
| dial-turn-v3 | 0 | 0 | 0 | 0 | 0 |
| disassemble-v3 | 40 | 10 | 0 | 3 | 2 |
| door-close-v3 | 6 | 6 | 0 | 3 | 2 |
| door-lock-v3 | 15 | 8 | 4 | 3 | 2 |
| door-open-v3 | 2 | 2 | 0 | 2 | 0 |
| door-unlock-v3 | 5 | 2 | 1 | 2 | 0 |
| drawer-close-v3 | 0 | 0 | 0 | 0 | 0 |
| drawer-open-v3 | 5 | 4 | 0 | 3 | 1 |
| faucet-close-v3 | 20 | 10 | 0 | 3 | 2 |
| faucet-open-v3 | 25 | 9 | 0 | 3 | 2 |
| hammer-v3 | 20 | 8 | 1 | 3 | 2 |
| hand-insert-v3 | 24 | 6 | 6 | 3 | 2 |
| handle-press-side-v3 | 1 | 1 | 0 | 1 | 0 |
| handle-press-v3 | 0 | 0 | 0 | 0 | 0 |
| handle-pull-side-v3 | 9 | 4 | 1 | 3 | 1 |
| handle-pull-v3 | 1 | 1 | 0 | 1 | 0 |
| lever-pull-v3 | 0 | 0 | 0 | 0 | 0 |
| peg-insert-side-v3 | 3 | 2 | 1 | 2 | 0 |
| peg-unplug-side-v3 | 17 | 5 | 1 | 3 | 2 |
| pick-out-of-hole-v3 | 0 | 0 | 0 | 0 | 0 |
| pick-place-v3 | 19 | 5 | 3 | 3 | 2 |
| pick-place-wall-v3 | 12 | 5 | 2 | 3 | 2 |
| plate-slide-back-side-v3 | 0 | 0 | 0 | 0 | 0 |
| plate-slide-back-v3 | 7 | 4 | 0 | 3 | 1 |
| plate-slide-side-v3 | 0 | 0 | 0 | 0 | 0 |
| plate-slide-v3 | 0 | 0 | 0 | 0 | 0 |
| push-back-v3 | 17 | 6 | 1 | 3 | 2 |
| push-v3 | 31 | 7 | 4 | 3 | 2 |
| push-wall-v3 | 19 | 5 | 4 | 3 | 2 |
| reach-v3 | 23 | 6 | 3 | 3 | 2 |
| reach-wall-v3 | 14 | 4 | 1 | 3 | 1 |
| shelf-place-v3 | 11 | 4 | 0 | 3 | 1 |
| soccer-v3 | 0 | 0 | 0 | 0 | 0 |
| stick-pull-v3 | 28 | 8 | 5 | 3 | 2 |
| stick-push-v3 | 5 | 5 | 5 | 3 | 2 |
| sweep-into-v3 | 21 | 5 | 5 | 3 | 2 |
| sweep-v3 | 30 | 6 | 6 | 3 | 2 |
| window-close-v3 | 19 | 10 | 0 | 3 | 2 |
| window-open-v3 | 17 | 7 | 0 | 3 | 2 |

Zero-rescue tasks: assembly-v3, button-press-v3, coffee-button-v3, dial-turn-v3, drawer-close-v3, handle-press-v3, lever-pull-v3, pick-out-of-hole-v3, plate-slide-back-side-v3, plate-slide-side-v3, plate-slide-v3, soccer-v3

Ordering is H10 first, then H20/30/40/50; unique source IDs. These are selected demonstrations and must not change the existing aggregate success-rate tables. Preserve failed re-recordings, and use reserves only within the fixed list.

All explicit task/env_seed/policy_seed/H/action-unit/control-frequency/Q identity checks passed for all historical rescues. Same seeds identify the intended initial-state protocol, not proof of arbitrary hidden-state equality. No GPU/model/render call performed.
