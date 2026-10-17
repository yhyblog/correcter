"""Frozen base imports; new overlay always precedes inherited modules."""
import sys
from pathlib import Path
BASE=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1')
BASE_CODE=BASE/"code"
SIDECAR=BASE/"sidecar_v1"
if str(BASE_CODE) not in sys.path:sys.path.append(str(BASE_CODE))
