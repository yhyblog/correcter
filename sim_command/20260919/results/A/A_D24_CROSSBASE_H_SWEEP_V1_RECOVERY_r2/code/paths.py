"""A-private Smol sweep; shared assets are read-only, identities are host-local."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAMPAIGN=ROOT.parents[2]
WORKSPACE=CAMPAIGN.parents[2]
ACCEPTED=CAMPAIGN/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in [WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src',ACCEPTED,ACCEPTED/'vendor_vla/src']:
    sys.path.insert(0,str(p))
sys.path.insert(0,str(ROOT/'code'))
from qio import read
CONFIG=read(ROOT/'config/CONFIG.json')
AUTH_SHA=CONFIG['grant_sha256']
TASK=CONFIG['task_id']
EVENT_PREFIX=CONFIG['event_prefix']
ORIGINAL=Path(CONFIG['old_root'])
ARTIFACTS=Path(CONFIG['artifact_root'])
SELECTION_SHA=None
