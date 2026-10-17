#!/usr/bin/env bash
set -euo pipefail
# Usage: bash commands/run_preflight.sh ABSOLUTE_ANALYSIS_RELEASE
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_PREFLIGHT_REVISION_R2_r1_B_20260920
export PYTHONDONTWRITEBYTECODE=1
/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python preflight.py --config config.json --release "$1" --verify-release-only
exec /mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh run -- timeout --signal=TERM --kill-after=20 180 /mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_PREFLIGHT_REVISION_R2_r1_B_20260920/preflight.py --config /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_PREFLIGHT_REVISION_R2_r1_B_20260920/config.json --release "$1" --execute
