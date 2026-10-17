#!/usr/bin/env bash
set -euo pipefail
exec /mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_PREFLIGHT_REVISION_R2_r1_B_20260920/preflight.py --config /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_PREFLIGHT_REVISION_R2_r1_B_20260920/config.json --release "$1" --verify-release-only
