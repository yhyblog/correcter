#!/usr/bin/env bash
set -euo pipefail
round2_code="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
round2_package="$(cd "${round2_code}/../.." && pwd)"
round2_workspace="$(dirname "${round2_package}")"
source "${round2_workspace}/embodied-ai-workspace/config/vla-corrector-mesa.env"
source "${VLA_PROTOCOL_ROOT}/prepare_torch_runtime.sh"
export PYTHONPATH="${round2_package}:${round2_package}/src:${round2_workspace}/ACT-RECAP/src:${VLA_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 LP_NUM_THREADS=4
export XDG_CACHE_HOME="/tmp/corrector_native10_main/cache_${CUDA_VISIBLE_DEVICES:-cpu}"
mkdir -p "${XDG_CACHE_HOME}"
cd "${round2_package}"
exec "${LEROBOT_ENV}/bin/python" -u -m experiments.native10_training_20260916.round2_runner_v1 "$@"
