import sys
from pathlib import Path
from qio import read
ROOT=Path(__file__).resolve().parents[1]
CAMPAIGN=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORKSPACE=CAMPAIGN.parents[2]
CONFIG=read(ROOT/'config/CONFIG.json')
AUTH_SHA=CONFIG['grant_sha256']
ARTIFACTS=Path(CONFIG['artifact_root'])
ACCEPTED=CAMPAIGN/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in [WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src',ACCEPTED,ACCEPTED/'vendor_vla/src']:
    sys.path.insert(0,str(p))
sys.path.insert(0,str(ROOT/'code'))
