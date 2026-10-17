#!/bin/sh
set -eu
export CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300
[ "$#" -eq 1 ] || exit 2
exec /mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/environments/lerobot/bin/python -B /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_SHARED_PLAN_REFERENCE_CPU_REPAIR_V1/code/launch.py --release "$1"
