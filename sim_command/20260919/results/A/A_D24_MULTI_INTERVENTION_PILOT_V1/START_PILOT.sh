#!/usr/bin/env bash
set -euo pipefail
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_MULTI_INTERVENTION_PILOT_V1
export PYTHONDONTWRITEBYTECODE=1
exec /usr/bin/python -B code/service.py start
