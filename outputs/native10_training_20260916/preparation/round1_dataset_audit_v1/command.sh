#!/usr/bin/env bash
set -euo pipefail
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector
export CUDA_VISIBLE_DEVICES=''
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export PYTHONPATH=/mnt/bn/arnold-recommend/yaohaoyang/Corrector:/mnt/bn/arnold-recommend/yaohaoyang/Corrector/src:/mnt/bn/arnold-recommend/yaohaoyang/ACT-RECAP/src
/mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python -u outputs/native10_training_20260916/preparation/round1_dataset_audit_v1/run.py > outputs/native10_training_20260916/preparation/round1_dataset_audit_v1/run.log 2>&1
