"""Private finite qualitative recordings; no old scientific admissions."""
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
AUTH_SHA='632b9cde9a7cf0528c8c0d5a974f526f08b4faa590bde3d80c7ffa1e2fbd4024'
TASK='A_POST_DEMO_VIDEOS_V1'
EVENT_PREFIX=TASK
ORIGINAL=CAMPAIGN/'results/A/A_D24_CROSSBASE_H_SWEEP_V1_RECOVERY_r2'
OUTPUT=Path(CONFIG['output_root'])
