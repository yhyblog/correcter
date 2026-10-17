cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONPATH=.:src:../ACT-RECAP/src /mnt/bn/arnold-recommend/yaohaoyang/.miniforge3/envs/lerobot/bin/python -m pytest -q -p no:cacheprovider experiments/native10_training_20260916/test_policy_deployment_v1.py experiments/native10_training_20260916/test_policy5_runner_v1.py tests/test_native10_policy5_audit_v1.py
bash -n /mnt/bn/arnold-recommend/yaohaoyang/Corrector/experiments/native10_training_20260916/run_policy5_gpu_v1.sh
