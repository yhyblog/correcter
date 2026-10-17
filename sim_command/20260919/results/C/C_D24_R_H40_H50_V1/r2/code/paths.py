"""Isolated online pilot; no archived launcher or budget ledger is invoked."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT.parents[3]
WORKSPACE = CAMPAIGN.parents[2]
ACCEPTED = CAMPAIGN / 'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in (WORKSPACE/'Corrector', WORKSPACE/'Corrector/src', WORKSPACE/'ACT-RECAP/src',
          ACCEPTED, ACCEPTED/'vendor_vla/src'):
    if str(p) not in sys.path: sys.path.insert(0,str(p))
sys.path.insert(0,str(ROOT/'code'))
AUTH_SHA = 'c9233a9b2f92fe97cd3b03515f18dde7f2803bb46ee07123a32881ff90b4a71a'
