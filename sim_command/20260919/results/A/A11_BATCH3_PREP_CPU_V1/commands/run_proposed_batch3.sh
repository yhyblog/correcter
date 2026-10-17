#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then exit 64; fi
export CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300
export PYTHONDONTWRITEBYTECODE=1
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_BATCH3_PREP_CPU_V1
exec /mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/environments/lerobot/bin/python -B /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_BATCH3_PREP_CPU_V1/code/launch.py --release "$1"
