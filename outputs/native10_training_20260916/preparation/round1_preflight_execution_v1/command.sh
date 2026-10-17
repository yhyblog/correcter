#!/usr/bin/env bash
set -euo pipefail
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector
export CUDA_VISIBLE_DEVICES=''
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export PYTHONPATH=/mnt/bn/arnold-recommend/yaohaoyang/Corrector:/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src:/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src
/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python -u -m experiments.native10_training_20260916.training_pipeline preflight --config outputs/native10_training_20260916/fit_protocols/round1_preflight_v1/config.json --phase round1 --version round1_preflight_v1
