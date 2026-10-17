#!/usr/bin/env bash
set -euo pipefail
check_dir="/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/A/A10_cpu_checks_$(date +%s%N)"
PYTHONDONTWRITEBYTECODE=1 exec /usr/bin/python3 -B -m pytest -q -p no:cacheprovider "/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10/code_snapshot_v1/test_cpu_contract.py" --basetemp="$check_dir"
