#!/bin/sh
set -eu
[ "$#" -eq 3 ] || exit 2
exec /usr/bin/python -B /mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1/code/publication_check.py --control "$1" --board "$2" --release "$3"
