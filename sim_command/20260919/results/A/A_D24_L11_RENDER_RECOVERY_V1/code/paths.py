"""A-private, process-isolated recovery; no mutation of the source packages."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAMPAIGN=ROOT.parents[2]
WORKSPACE=CAMPAIGN.parents[2]
ACCEPTED=CAMPAIGN/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in (WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src',ACCEPTED,ACCEPTED/'vendor_vla/src'):
    sys.path.insert(0,str(p))
sys.path.insert(0,str(ROOT/'code'))
from qio import read
CONFIG=read(ROOT/'config/CONFIG.json')
AUTH_SHA='ca6f92258260815495a016d8c25eb079e9e0949a38a2c5ece6b836c2ef6d0ccc'
TASK='A_D24_L11_RENDER_RECOVERY_V1'
EVENT_PREFIX=TASK
ORIGINAL=CAMPAIGN/'results/A/A_D24_L11_RETEST_V1'
SELECTION_SHA='2006bc5818911d80a7b325bc91699c789675bb62b75647a4abcc8012119dffe2'
