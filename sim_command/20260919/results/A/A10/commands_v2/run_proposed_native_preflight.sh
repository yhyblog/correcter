#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 1 ]]; then echo "usage: $0 /absolute/path/to/new-campaign-compute-release.json" >&2; exit 2; fi
exec /usr/bin/python3 -B "/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10/code_snapshot_v2/launch_preflight.py" --campaign "/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919" --release "$1" --proposal "/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A10/preflight_v2/PROPOSAL.json"
