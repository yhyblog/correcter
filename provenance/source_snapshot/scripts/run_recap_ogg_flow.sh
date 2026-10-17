#!/usr/bin/env bash
set -euo pipefail
flow_repo=/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP
source "${flow_repo}/../embodied-ai-workspace/config/vla-corrector-mesa.env"
source "${VLA_PROTOCOL_ROOT}/prepare_torch_runtime.sh"
export PYTHONPATH="${flow_repo}/src:${VLA_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 LP_NUM_THREADS=4
export XDG_CACHE_HOME="/tmp/act_recap_ogg_flow_20260916/cache_${CUDA_VISIBLE_DEVICES:-0}"
mkdir -p "${XDG_CACHE_HOME}"
cd "${flow_repo}"
exec "${LEROBOT_ENV}/bin/python" -u -m "ac_tmil.ogg_flow.$1" "${@:2}"
