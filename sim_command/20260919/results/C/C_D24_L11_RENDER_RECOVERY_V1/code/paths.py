"""C-only ordered continuation of A's exact transferred pi05 units."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAMPAIGN=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORKSPACE=CAMPAIGN.parents[2]
ACCEPTED=CAMPAIGN/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
ORIGINAL=CAMPAIGN/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1'
A_HANDOFF=CAMPAIGN/'results/A/A_D24_FULL_Q_AUTORUN_HANDOFF_V2'
PREVIOUS=CAMPAIGN/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1'
SELECTION=ORIGINAL/'SELECTION.json'
TRANSFER=A_HANDOFF/'TRANSFER_READY.json'
AUTH_SHA='ca6f92258260815495a016d8c25eb079e9e0949a38a2c5ece6b836c2ef6d0ccc'
TASK='C_D24_L11_RENDER_RECOVERY_V1'
JOB='D24_C_L11_RENDER_RECOVERY_r1'
HEADS=CAMPAIGN/'results/C/C_D24_XVLA_AUX_RETRAIN_V1'
for p in (WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src'):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
sys.path.insert(0,str(ROOT/'code'))
def external_encoder_paths():
    for p in (ACCEPTED,ACCEPTED/'vendor_vla/src'):
        if str(p) not in sys.path:sys.path.insert(0,str(p))
    sys.path.insert(0,str(ROOT/'code'))

import json
CONFIG=json.loads((ROOT/'config/CONFIG.json').read_text())
