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
AUTH_SHA='8fc0bf2c7c0c761d9fba424fb7fb127af8a9c505668fccd7231126535c6422c1'
TASK='A_D24_FULL_Q_LOSS_SELECTION_V1'

EVIDENCE_ROOTS=(ROOT,)
