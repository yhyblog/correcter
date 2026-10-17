"""One reservation, one owned process group, bounded concurrent parent slots."""
import inheritance
import argparse,os,signal,sys,time
from pathlib import Path
from authorization import load_authorization,gate
from core.contracts import read,configure_store
from core.wave_timing import held_reservation_fds
from core.event_recorder import EventRecorder
from core.process_family import drain_group
from core.failure_evidence import record_failure
from process_backend import ProcessBackend
from batch_scheduler import run_schedule,GlobalFault
from storage import Store

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',required=True);a=parser.parse_args()
    r,p=load_authorization(a.release,False);root=Path(p['paths']['output'])/'reserved';root.mkdir(exist_ok=False)
    store=Store(root,byte_limit=p['storage']['reserved_root_bytes'],record_limit=32*1024**2,file_limit=256)
    configure_store(store);backend=ProcessBackend(a.release,p,held_reservation_fds())
    recorder=EventRecorder(root/'SCHEDULER_EVENTS.jsonl',branch='batch_manager',source_id=p['authorization_identity']['run_id'],
        parent_source_id='not_applicable:batch',split='train',synthetic=False,writer=store)
    def stop(sig,frame):raise GlobalFault('formal wave signal '+str(sig))
    previous={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP,signal.SIGALRM)}
    signal.alarm(p['timeouts']['reserved_wave_seconds']+p['timeouts']['reserved_wave_grace_seconds'])
    result=None;primary=None;cleanup=None
    try:
        result=run_schedule(p['parents'],p['concurrency'],backend,
            gate=lambda:gate(a.release,r['_sha256'],p),emit=recorder.emit,
            limits=p['scheduler_caps'],timeouts=p['timeouts'])
        cleanup=result['cleanup']
    except BaseException as e:
        primary=record_failure(e,branch=None,stage='batch_manager',category='primary')
    finally:
        signal.alarm(0)
        # Do not allow a second TERM to bypass the reservation's exit barrier.
        for s in previous:signal.signal(s,signal.SIG_IGN)
        if cleanup is None:cleanup=drain_group(os.getpgrp(),os.getpid())
        configure_store(store);store.emergency_mode=True
        store.json('PROCESS_GROUP_EXIT.json',cleanup,emergency=True)
        store.json('WAVE_EXIT.json',dict(result=result,primary=primary,cleanup=cleanup,
            compute_exit_and_data_publication_separate=True,no_retry=True),emergency=True)
        for s,f in previous.items():signal.signal(s,f)
    return 0 if primary is None and result and result['status']=='complete' else 3
if __name__=='__main__':sys.exit(main())
