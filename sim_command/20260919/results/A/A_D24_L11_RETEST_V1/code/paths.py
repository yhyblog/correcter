"""Private A trigger-mode package; existing scientific assets remain read-only."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAMPAIGN=ROOT.parents[2]
WORKSPACE=CAMPAIGN.parents[2]
ACCEPTED=CAMPAIGN/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in (WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src',ACCEPTED,ACCEPTED/'vendor_vla/src'):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
sys.path.insert(0,str(ROOT/'code'))
AUTH_SHA='a978519ba24dfb3aba22cf5ce8472d9b855e788e44266a28e0d006be876d5e87'
TASK='A_D24_L11_RETEST_V1'
EVENT_PREFIX=TASK
ORIGINAL=CAMPAIGN/'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1'
SELECTION_SHA='2006bc5818911d80a7b325bc91699c789675bb62b75647a4abcc8012119dffe2'
