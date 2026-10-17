#!/bin/sh
set -eu
export CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300
[ "$#" -eq 1 ] || { echo "usage: run_proposed_causal_c10.sh NEW_RELEASE_JSON" >&2; exit 2; }
exec /mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/environments/lerobot/bin/python -B /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1/code/launch.py --release "$1"
