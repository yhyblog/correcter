#!/bin/bash
set -euo pipefail
cd "/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A_POST_DEMO_VIDEOS_V1"
exec /usr/bin/python -B code/service.py start
