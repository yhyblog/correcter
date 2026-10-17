"""C-only ordered continuation of A's exact transferred pi05 units."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CAMPAIGN=ROOT.parents[2]
WORKSPACE=CAMPAIGN.parents[2]
ACCEPTED=CAMPAIGN/'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
ORIGINAL=CAMPAIGN/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1'
A_HANDOFF=CAMPAIGN/'results/A/A_D24_FULL_Q_AUTORUN_HANDOFF_V2'
PREVIOUS=CAMPAIGN/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1'
SELECTION=ORIGINAL/'SELECTION.json'
TRANSFER=A_HANDOFF/'TRANSFER_READY.json'
AUTH_SHA='fb15e23ad4ed75eaa1b9490784d58dc9dc925e440194e99cab066ae11af6414f'
TASK='C_D24_PI05_SELECTED_H40_H50_V1'
JOB='D24_C_PI05_SELECTED_H40_H50_r1'
for p in (WORKSPACE/'Corrector',WORKSPACE/'Corrector/src',WORKSPACE/'ACT-RECAP/src',ACCEPTED,ACCEPTED/'vendor_vla/src'):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
sys.path.insert(0,str(ROOT/'code'))
EVIDENCE_ROOTS=(ROOT,)
