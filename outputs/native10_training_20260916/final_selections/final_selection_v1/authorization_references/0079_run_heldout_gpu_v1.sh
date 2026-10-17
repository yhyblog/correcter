#!/usr/bin/env bash
set -euo pipefail
heldout_code="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
heldout_package="$(cd "${heldout_code}/../.." && pwd)"
heldout_workspace="$(dirname "${heldout_package}")"
source "${heldout_workspace}/embodied-ai-workspace/config/vla-corrector-mesa.env"
source "${VLA_PROTOCOL_ROOT}/prepare_torch_runtime.sh"
export PYTHONPATH="${heldout_package}:${heldout_package}/src:${heldout_workspace}/ACT-RECAP/src:${VLA_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 LP_NUM_THREADS=4
export XDG_CACHE_HOME="/tmp/corrector_native10_main/cache_${CUDA_VISIBLE_DEVICES:-cpu}"
mkdir -p "${XDG_CACHE_HOME}"
cd "${heldout_package}"
exec "${LEROBOT_ENV}/bin/python" -u -m experiments.native10_training_20260916.heldout_runner_v1 "$@"
