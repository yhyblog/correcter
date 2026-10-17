#!/usr/bin/env bash
set -euo pipefail
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_BATCH_SCALING_CPU_V1
exec /mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/environments/lerobot/bin/python -B /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_BATCH_SCALING_CPU_V1/code/publication_check.py "$@"
