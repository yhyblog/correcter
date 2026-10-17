"""C-private paths; keep the native X runtime separate from the external encoder."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAMPAIGN=ROOT.parents[2]
WORKSPACE=CAMPAIGN.parents[2]
AUTH_SHA='6024320bc4b05cbdaa6e96062403c0d3f5fd1fc632c4f73872d3524cf7a4fdc3'
TASK='C_D24_XVLA_AUX_RETRAIN_V1'
ACCEPTED=CAMPAIGN/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in [WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src']:
    sys.path.insert(0,str(p))
sys.path.insert(0,str(ROOT/'code'))

def external_encoder_paths():
    for p in [ACCEPTED,ACCEPTED/'vendor_vla/src']:
        sys.path.insert(0,str(p))
    sys.path.insert(0,str(ROOT/'code'))
