#!/usr/bin/env bash
set -euo pipefail
solo_code="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
solo_package="$(cd "${solo_code}/../.." && pwd)"
solo_workspace="$(dirname "${solo_package}")"
source "${solo_workspace}/embodied-ai-workspace/config/vla-corrector-mesa.env"
source "${VLA_PROTOCOL_ROOT}/prepare_torch_runtime.sh"
export PYTHONPATH="${solo_package}:${solo_package}/src:${solo_workspace}/ACT-RECAP/src:${VLA_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 LP_NUM_THREADS=4
export XDG_CACHE_HOME="/tmp/corrector_standalone_ablation_20260918/cache_${CUDA_VISIBLE_DEVICES:-cpu}"
mkdir -p "${XDG_CACHE_HOME}"
cd "${solo_package}"
exec "${LEROBOT_ENV}/bin/python" -u -m experiments.standalone_ablation_20260918.runner "$@"
