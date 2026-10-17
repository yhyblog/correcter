#!/usr/bin/env bash
set -euo pipefail
# Usage: bash run_formal_job.sh CONFIG RELEASE UNIQUE_OUTPUT
# Only a later explicit independent single-host release can pass this check.
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/B/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z
/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python future_jobs.py --config "$1" --release "$2" --verify-release-only
job_timeout=$(/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python -c 'import json,sys;print(json.load(open(sys.argv[1]))["timeout_seconds"])' "$1")
exec /mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_lifecycle.sh run -- timeout --signal=TERM --kill-after=20 "$job_timeout" /mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python future_jobs.py --config "$1" --release "$2" --output "$3" --execute
