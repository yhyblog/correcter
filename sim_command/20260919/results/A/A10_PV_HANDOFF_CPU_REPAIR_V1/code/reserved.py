"""Reserved wrapper retains all-holder lock until the entire group exits."""
import argparse
import os
from pathlib import Path
import sys
from core.contracts import PACKAGE, ContractError, read, write_new
from core.process_family import drain_group
from core.wave_timing import held_reservation_fds,mark,run_forwarded

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',required=True);parser.add_argument('--launch-directory',required=True)
    a=parser.parse_args();out=Path(a.launch_directory).resolve();mark(out,'reserved_command_started')
    fds=held_reservation_fds()
    if not fds:raise ContractError('All-eight-holder reservation required')
    cfg=read(PACKAGE/'config/CONFIG.json')
    cmd=['timeout','--foreground','--signal=TERM','--kill-after=30s','1800s',cfg['python'],'-B',str(PACKAGE/'code/diagnostic.py'),
         '--release',a.release,'--launch-directory',str(out)]
    result=None;mark(out,'timed_process_started')
    try:
        result=run_forwarded(cmd,cwd=PACKAGE/'code',pass_fds=fds);return result
    finally:
        write_new(out/'process_family_cleanup.json',drain_group(os.getpgrp(),os.getpid()))
        mark(out,'timed_process_exited',returncode=result,automatic_retry=False)

if __name__=='__main__':sys.exit(main())
