#!/bin/bash
set -euo pipefail
cd "/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_D24_L11_RETEST_V1"
exec /usr/bin/python -B code/service.py start
