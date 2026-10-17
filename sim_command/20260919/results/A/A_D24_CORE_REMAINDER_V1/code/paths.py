"""Isolated online pilot; no archived launcher or budget ledger is invoked."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT.parents[2]
WORKSPACE = CAMPAIGN.parents[2]
ACCEPTED = CAMPAIGN / 'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in (WORKSPACE/'Corrector', WORKSPACE/'Corrector/src', WORKSPACE/'ACT-RECAP/src',
          ACCEPTED, ACCEPTED/'vendor_vla/src'):
    if str(p) not in sys.path: sys.path.insert(0,str(p))
sys.path.insert(0,str(ROOT/'code'))
AUTH_SHA = '3e6a0aab7abe79365192c953d45b4e13b44139ab26ffadb6f7c3f82547107d8b'
