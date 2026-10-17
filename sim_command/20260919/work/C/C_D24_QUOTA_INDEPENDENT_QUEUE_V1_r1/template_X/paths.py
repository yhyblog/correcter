"""C-private paths; keep the native X runtime separate from the external encoder."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAMPAIGN=ROOT.parents[2]
WORKSPACE=CAMPAIGN.parents[2]
AUTH_SHA='8fc0bf2c7c0c761d9fba424fb7fb127af8a9c505668fccd7231126535c6422c1'
TASK='C_D24_FULL_Q_LOSS_REFRESH_V1'
HEADS=CAMPAIGN/'results/C/C_D24_XVLA_AUX_RETRAIN_V1'
ACCEPTED=CAMPAIGN/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in [WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src']:
    sys.path.insert(0,str(p))
sys.path.insert(0,str(ROOT/'code'))

def external_encoder_paths():
    for p in [ACCEPTED,ACCEPTED/'vendor_vla/src']:
        sys.path.insert(0,str(p))
    sys.path.insert(0,str(ROOT/'code'))

PREVIOUS=CAMPAIGN/'results/C/C_D24_XVLA_MULTI_EVAL_V1'
SELECTION=CAMPAIGN/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION.json'

SCIENCE_ROOT=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_FULL_Q_LOSS_REFRESH_V1')
