from paths import SCIENCE_ROOT,CAMPAIGN
import sys
sys.path.append(str(CAMPAIGN/"work/C/C_D24_AUTORECOVERY_QUEUE_RULE_V1_r1"))
import c_recovery_policy as p
def consume(root,component):return p.consume(SCIENCE_ROOT,"quota_continuation_"+component)
def record_fault(root,error,**kwargs):return p.record_fault(SCIENCE_ROOT,error,**kwargs)
def reject_completed_terminal(path):
    if path.exists() and p.legal_terminal(p.read(path)):raise RuntimeError("completed terminal cannot replay")
