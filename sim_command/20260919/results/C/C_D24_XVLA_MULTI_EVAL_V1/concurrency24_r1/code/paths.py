"""C-private paths; keep the native X runtime separate from the external encoder."""
import sys
from pathlib import Path
RUNROOT=Path(__file__).resolve().parents[1]
ROOT=RUNROOT.parent
CAMPAIGN=ROOT.parents[2]
WORKSPACE=CAMPAIGN.parents[2]
AUTH_SHA='767685a6fd14840f1f04001e14cf01980a17810be5d044dd0db9d665d7d05699'
TASK='C_D24_XVLA_MULTI_EVAL_V1'
HEADS=CAMPAIGN/'results/C/C_D24_XVLA_AUX_RETRAIN_V1'
ACCEPTED=CAMPAIGN/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in [WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src']:
    sys.path.insert(0,str(p))
sys.path.insert(0,str(RUNROOT/'code'))

def external_encoder_paths():
    for p in [ACCEPTED,ACCEPTED/'vendor_vla/src']:
        sys.path.insert(0,str(p))
    sys.path.insert(0,str(RUNROOT/'code'))
