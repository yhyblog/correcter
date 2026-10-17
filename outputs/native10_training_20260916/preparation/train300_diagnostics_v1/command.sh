#!/usr/bin/env bash
set -euo pipefail
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector
export CUDA_VISIBLE_DEVICES=''
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python -u experiments/native10_training_20260916/summarize_train300_v1.py
