import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAMPAIGN=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORKSPACE=CAMPAIGN.parents[2]
AUTH_SHA='6024320bc4b05cbdaa6e96062403c0d3f5fd1fc632c4f73872d3524cf7a4fdc3'
ACCEPTED=CAMPAIGN/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in [WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src',ACCEPTED,ACCEPTED/'vendor_vla/src']:
    sys.path.insert(0,str(p))
sys.path.insert(0,str(ROOT/'code'))
