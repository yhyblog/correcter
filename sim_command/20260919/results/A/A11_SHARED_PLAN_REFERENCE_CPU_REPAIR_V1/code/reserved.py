import inheritance
"""All 15 sequential children stay under one inherited group and reservation."""
import argparse,os,signal,sys,time
from pathlib import Path
from authorization import load_authorization
from core.contracts import PACKAGE,ContractError,read,configure_store
from core.process_family import drain_group,group_members
from core.wave_timing import held_reservation_fds
from controller import sequential_jobs
from pool_protocol import ARMS
from storage import Store
from execution import run
from budget import TIMEOUTS
def main():
    p=argparse.ArgumentParser();p.add_argument('--release',required=True);a=p.parse_args()
    r,proposal=load_authorization(a.release,False);parent=Path(proposal['paths']['output'])
    out=parent/'reserved';out.mkdir(exist_ok=False);store=Store(out,byte_limit=32*1024**2,record_limit=1024**2,file_limit=128);configure_store(store)
    fds=held_reservation_fds()
    if not fds or os.getpgrp()!=os.getpid():raise ContractError('guard-created isolated group and inherited formal lock required')
    cfg=read(proposal['config']['path']);rows=[];primary=None
    def timeout(sig,frame):raise TimeoutError('reserved wave admission deadline; drain before reservation release')
    old=signal.signal(signal.SIGALRM,timeout);signal.alarm(TIMEOUTS['reserved_wave_seconds'])
    def one(job):
        name=job[0];started=time.monotonic()
        code=run(['timeout','--foreground','--signal=TERM','--kill-after=30s','1800s',cfg['python'],'-B',str(PACKAGE/'code/child.py'),
            '--release',a.release,'--branch',name],cwd=PACKAGE/'code',pass_fds=fds,
            stdout=out/(name+'.stdout'),stderr=out/(name+'.stderr'))
        remaining=group_members(os.getpgrp(),os.getpid())
        result=read(parent/name/'BRANCH_RESULT.json') if (parent/name/'BRANCH_RESULT.json').exists() else None
        row=dict(branch=name,returncode=code,remaining_group=remaining,cleanup_complete=not remaining,
            elapsed_seconds=time.monotonic()-started,result=result)
        store.json(name+'_EXIT.json',row);return row
    try:rows=sequential_jobs(ARMS,one)
    except BaseException as e:
        from core.failure_evidence import record_failure
        primary=record_failure(e,branch=None,stage='reserved_wave',category='primary')
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,old)
        cleanup=drain_group(os.getpgrp(),os.getpid())
        store.json('PROCESS_GROUP_EXIT.json',cleanup,emergency=True)
        store.json('WAVE_EXIT.json',dict(rows=rows,primary=primary,children_max=15,no_retry=True),emergency=True)
    store.json('ATTEMPT_COVERAGE.json',dict(planned=[dict(role=j[0],family=j[1],repeat=j[2],
        started=(parent/j[0]).exists(),result_present=(parent/j[0]/'BRANCH_RESULT.json').exists(),
        sidecar_present=(parent/j[0]/'SIDECAR_V1.json').exists()) for j in ARMS],
        actual_complete_qualification_must_be_read_from_each_sidecar=True,never_fill_missing=True))
    from audit_indices import private_cost_index
    private_cost_index(parent,store,synthetic=False)
    from sidecar_output import aggregate
    aggregate(parent,store)
    return 0 if not primary and rows and all(x['returncode']==0 for x in rows) else 3
if __name__=='__main__':sys.exit(main())
