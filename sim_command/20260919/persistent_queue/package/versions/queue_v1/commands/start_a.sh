#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
export CORRECTOR_OCCUPANCY_HANDOFF_TIMEOUT_SECONDS=300
exec /usr/bin/python -B /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/persistent_queue/package/versions/queue_v1/queue/main.py start --node A
