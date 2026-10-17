"""C CPU operational rules; GPU/scientific ownership stays in original task."""
import sys
from pathlib import Path
sys.path.insert(0,'/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/work/C/C_D24_AUTORECOVERY_QUEUE_RULE_V1_r1')
from c_recovery_policy import consume,record_fault,legal_terminal,prepare_resume,repair_gate
from ops_io import read
def reject_completed_terminal(path):
    p=Path(path)
    if p.is_file() and legal_terminal(read(p)):
        raise RuntimeError('Existing legal scientific terminal, including success=false, must not replay')
