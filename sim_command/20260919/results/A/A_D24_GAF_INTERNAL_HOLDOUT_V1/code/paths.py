"""Deadline runner locations; imports have no model or hardware effects."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT.parents[2]
WORKSPACE = CAMPAIGN.parents[2]
ACCEPTED = CAMPAIGN / 'results/A/A11_COMMON_POOL_COLLECTOR_CPU_V1/code'
for p in (ACCEPTED, ACCEPTED / 'vendor_vla/src'):
    if str(p) not in sys.path:
        sys.path.insert(0,str(p))

AUTH_SHA='3e6a0aab7abe79365192c953d45b4e13b44139ab26ffadb6f7c3f82547107d8b'
SUPPLEMENT_SHA='00164634bff4149593e0110c1bed6491eb0f042f94d2a599157b73a4912c18ec'
UPSTREAM=CAMPAIGN/'work/B/B10_r1_trial-303225685-trialrun-303225685-worker-0_20260919T150956Z/upstream/guided-action-flow/src'
sys.path.insert(0,str(UPSTREAM))
