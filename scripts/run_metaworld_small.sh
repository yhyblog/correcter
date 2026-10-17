#!/usr/bin/env bash
set -euo pipefail
corrector_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
corrector_workspace="$(dirname "${corrector_root}")"
corrector_reference="${corrector_workspace}/ACT-RECAP"
source "${corrector_workspace}/embodied-ai-workspace/config/vla-corrector-mesa.env"
source "${VLA_PROTOCOL_ROOT}/prepare_torch_runtime.sh"
export PYTHONPATH="${corrector_root}:${corrector_root}/src:${corrector_reference}/src:${VLA_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 LP_NUM_THREADS=4
export XDG_CACHE_HOME="/tmp/corrector_metaworld_small_20260916/cache_${CUDA_VISIBLE_DEVICES:-cpu}"
mkdir -p "${XDG_CACHE_HOME}"
cd "${corrector_root}"
exec "${LEROBOT_ENV}/bin/python" -u -m "experiments.metaworld_small.$1" "${@:2}"
