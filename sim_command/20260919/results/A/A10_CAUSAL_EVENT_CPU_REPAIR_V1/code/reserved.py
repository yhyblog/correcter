"""One inherited reservation, two sequential fresh processes, no retry/restore."""
import argparse,os,sys
from pathlib import Path
from core.contracts import PACKAGE,ContractError,read,write_new
from core.process_family import drain_group,group_members
from core.wave_timing import held_reservation_fds,mark,run_forwarded

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',required=True);parser.add_argument('--launch-directory',required=True)
    a=parser.parse_args();out=Path(a.launch_directory).resolve();mark(out,'reserved_command_started')
    fds=held_reservation_fds()
    if not fds or os.getpgrp()!=os.getpid():raise ContractError('Inherited all-eight reservation and own process group required')
    cfg=read(PACKAGE/'config/CONFIG.json');result=None;rows=[]
    try:
        for branch in cfg['control']['branch_order']:
            cmd=['timeout','--foreground','--signal=TERM','--kill-after=30s','1800s',cfg['python'],'-B',str(PACKAGE/'code/diagnostic.py'),
                 '--release',a.release,'--launch-directory',str(out),'--branch',branch]
            mark(out,'timed_process_started',branch=branch)
            result=run_forwarded(cmd,cwd=PACKAGE/'code',pass_fds=fds)
            # Do not start another model while any preceding formal descendant
            # remains. The outer finally drains this group before lock release.
            remaining=group_members(os.getpgrp(),os.getpid())
            row=dict(branch=branch,returncode=result,remaining_group=remaining);rows.append(row)
            mark(out,'timed_process_exited',**row,automatic_retry=False)
            if result!=0 or remaining:
                if result==0:result=3
                break
            br=read(out/branch/'BRANCH_RESULT.json')
            if br['status']!='C10_and_H20_checked':
                # No outcome replacement: stop this small wave on a natural
                # early stop or nonmatching prefix; retain unentered caps.
                break
        return result
    finally:
        write_new(out/'branch_process_exit.json',dict(branches=rows,automatic_retry=False))
        write_new(out/'process_family_cleanup.json',drain_group(os.getpgrp(),os.getpid()))
        mark(out,'all_branches_exited',returncode=result)
if __name__=='__main__':sys.exit(main())
