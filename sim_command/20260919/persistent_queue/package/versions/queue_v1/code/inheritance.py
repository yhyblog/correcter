"""Isolated batch overlay over accepted immutable CPU bundles."""
import sys
from pathlib import Path
PREVIOUS=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_OBSERVATION_PHASE_CPU_REPAIR_V1')
CONTRACTS=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_COLLECTOR_CONTRACT_CPU_REPAIR_V1')
BASE=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'queue'))
BASE_CODE=BASE/'code'
SIDECAR=BASE/'sidecar_v1'
for code in (PREVIOUS/'code',CONTRACTS/'code',BASE_CODE):
    if str(code) not in sys.path:sys.path.append(str(code))
