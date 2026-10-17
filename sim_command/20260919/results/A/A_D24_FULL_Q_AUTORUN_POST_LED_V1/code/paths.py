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
AUTH_SHA='fb15e23ad4ed75eaa1b9490784d58dc9dc925e440194e99cab066ae11af6414f'
TASK='A_D24_FULL_Q_AUTORUN_HANDOFF_V2'

ORIGINAL=CAMPAIGN/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1'
PREVIOUS=CAMPAIGN/'results/A/A_D24_FULL_Q_AUTORUN_HANDOFF_V2'
TRANSFER_ROOT=PREVIOUS
SELECTION_ROOT=ORIGINAL
EVIDENCE_ROOTS=(ORIGINAL,PREVIOUS,ROOT)
PRIOR_EVIDENCE_ROOTS=(ORIGINAL,PREVIOUS)
POST_OVERRIDE_SHA='fa907477112320e7f8356282c5ba64742452172dee998e9efc20a82b92b9c4b1'
EVENT_PREFIX=ROOT.name
