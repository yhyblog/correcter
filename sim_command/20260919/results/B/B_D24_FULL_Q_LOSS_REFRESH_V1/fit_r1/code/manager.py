"""Sixteen useful small-Q fits across all eight GPUs under one formal lease."""
import argparse
import os
import signal
import subprocess
import time
import traceback
from pathlib import Path
import paths
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity,optional_snapshot
from common import reservation_fds,boundary,runtime_command
from reservation import send_existing_fd,holder_exit_ack
from process_family import drain_group

def main(chain):
    chain=Path(chain);boundary(admission=True);own=process_identity();fds=reservation_fds()
    assert own['pid']==own['pgid']
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0])
    new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
    new_json(chain/'MANAGER_STARTED.json',dict(process=own,at_utc=utc(),single_reservation=True))
    processes=[];fatal=None;stopping=False;last=0
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,stop)
    try:
        jobs=[(loss,member) for loss in CONFIG['losses'] for member in CONFIG['member_seeds']]
        assert len(jobs)==16
        for j,(loss,member) in enumerate(jobs):
            boundary(admission=True)
            if stopping:raise RuntimeError('manager stopped')
            slot=j%8;ident=loss+'_fit9101_member'+str(member)
            argv=runtime_command('mw-pi05-legacy','train_q.py','--loss',loss,'--member',member)
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES=str(slot),OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',MKL_NUM_THREADS='4')
            with (chain/(ident+'.log')).open('xb') as log:
                p=subprocess.Popen(argv,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,pass_fds=fds)
            processes.append((p,ident,slot))
            new_json(chain/(ident+'_PROCESS.json'),dict(process=process_identity(p.pid),slot=slot,job_id=ident,at_utc=utc()))
        while any(p.poll() is None for p,*_ in processes):
            boundary()
            if stopping:raise RuntimeError('owned training stop')
            if any(p.poll() not in (None,0) for p,*_ in processes):raise RuntimeError('Q fit failed; no implicit retry')
            if time.monotonic()-last>=5:
                atomic_json(chain/'HEARTBEAT.json',dict(at_utc=utc(),utc=utc(),manager=own,status='running',phase='full_Q_training',
                    living_workers=sum(p.poll() is None for p,*_ in processes),target_workers=16,workers_per_gpu=2,
                    loaded_workers=sum((ROOT/'fits'/ident/'MODEL_READY.json').exists() and p.poll() is None for p,ident,slot in processes),
                    jobs={ident:dict(pid=p.pid,slot=slot,exit_code=p.poll()) for p,ident,slot in processes},
                    progress={ident:optional_snapshot(ROOT/'fits'/ident/'PROGRESS.json') for p,ident,slot in processes},
                    holder_policy='all8off throughout full formal family'))
                last=time.monotonic()
            time.sleep(1)
        if any(p.wait()!=0 for p,*_ in processes):raise RuntimeError('Q worker failed')
    except BaseException as exc:fatal=dict(error=repr(exc),traceback=traceback.format_exc())
    finally:
        cleanup=drain_group(own['pgid'],own['pid'])
        new_json(chain/'MANAGER_EXIT.json',dict(at_utc=utc(),fatal=fatal,phase='full_Q_training',cleanup=cleanup,all_owned_processes_exited=True))
    return 3 if fatal else 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);raise SystemExit(main(p.parse_args().chain))
