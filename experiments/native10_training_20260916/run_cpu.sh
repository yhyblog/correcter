#!/usr/bin/env bash
set -euo pipefail
native10_code="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
native10_package="$(cd "${native10_code}/../.." && pwd)"
native10_workspace="$(dirname "${native10_package}")"
export CUDA_VISIBLE_DEVICES=''
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export PYTHONPATH="${native10_package}:${native10_package}/src:${native10_workspace}/ACT-RECAP/src${PYTHONPATH:+:${PYTHONPATH}}"
cd "${native10_package}"
exec "${native10_workspace}/.miniforge3/envs/lerobot/bin/python" -m experiments.native10_training_20260916.prepare "$@"
