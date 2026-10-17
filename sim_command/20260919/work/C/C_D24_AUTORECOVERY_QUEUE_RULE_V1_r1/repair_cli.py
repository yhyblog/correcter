"""CPU-only unit manifest for the original executor after a concrete private fix."""
import argparse
from pathlib import Path
from c_recovery_policy import prepare_resume
from ops_io import read
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--task-root',required=True);p.add_argument('--issue',required=True);p.add_argument('--fix-record',required=True);a=p.parse_args()
    print(prepare_resume(Path(a.task_root),Path(a.issue),read(a.fix_record)))
