#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 1 ]]; then
  echo "Usage: $0 NEW_RELEASE_JSON" >&2
  exit 2
fi
exec /mnt/bn/arnold-recommend/yaohaoyang/embodied-ai-workspace/environments/lerobot/bin/python -B /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_NATIVE_EGL_INTEGRATION_CPU_V1/code/authorize_cpu.py --campaign /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919 --proposal /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10_NATIVE_EGL_INTEGRATION_CPU_V1/proposal/PROPOSAL.json --release "$1"
