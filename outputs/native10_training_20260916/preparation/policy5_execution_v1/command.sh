#!/usr/bin/env bash
set -euo pipefail
cd /mnt/bn/arnold-recommend/yaohaoyang/Corrector
exec bash experiments/native10_training_20260916/run_policy5_gpu_v1.sh launch --config outputs/native10_training_20260916/policy_protocols/round1_policy_v1/config.json --freeze outputs/native10_training_20260916/policy_protocols/round1_policy_v1/freeze.json --bank-version round1_policy_v1 --workers 32 --wave-id round1_policy_v1_01
