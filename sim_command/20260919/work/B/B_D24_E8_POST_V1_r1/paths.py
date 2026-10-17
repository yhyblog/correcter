"""B-owned integration of immutable A numerical components."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
CAMPAIGN = ROOT.parents[2]
WORKSPACE = CAMPAIGN.parents[2]
ACCEPTED = CAMPAIGN / 'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in (WORKSPACE/'Corrector', WORKSPACE/'Corrector/src', WORKSPACE/'ACT-RECAP/src',
          ACCEPTED, ACCEPTED/'vendor_vla/src'):
    sys.path.insert(0, str(p))
sys.path.insert(0, str(ROOT))
