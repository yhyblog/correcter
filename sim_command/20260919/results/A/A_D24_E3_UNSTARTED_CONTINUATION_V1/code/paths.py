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

# E3 uses its pinned native modified-policy implementation, never the collector vendor.
sys.path.insert(0,str(WORKSPACE/"vla-corrector/src"))

SUPPLEMENT_SHA = '3a6c62f0a40b4aa5eb08dafa9cef65d15717cb7edcbe505bc951ab37c40f79ad'
SOURCE_SHA = '12314afe0cefa81cc20f621056efc512e040be65092c4d9aff9c8f3b2ff704d5'
