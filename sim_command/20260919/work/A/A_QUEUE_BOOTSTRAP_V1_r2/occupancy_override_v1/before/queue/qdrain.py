"""Guard-created PGID, same inherited formal lock across all runnable batches."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code'))
import inheritance
import argparse
import os
import signal
import time
from qio import PACKAGE, QUEUE, read, ref, new_json, atomic_json, process_identity, utc
from qauthority import AUTH_SHA, collection_gate, first_grant
from qjobs import prepare_next, terminal
from qreservation import send_existing_fd, holder_exit_ack
from core.wave_timing import held_reservation_fds
from core.process_family import drain_group


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--first-release',required=True);parser.add_argument('--chain',required=True)
    args=parser.parse_args();chain=Path(args.chain);context=read(chain/'REQUEST.json')
    fds=held_reservation_fds()
    if not fds or os.getpid()!=os.getpgrp():raise RuntimeError('guard-created isolated PGID and inherited lock required')
    new_json(chain/'DRAIN_STARTED.json',dict(process=process_identity(),utc=utc(),existing_lock_fds=list(fds)))
    send_existing_fd(context['socket'],fds[0])
    ack=holder_exit_ack(context);new_json(chain/'HOLDER_EXIT_ACK.json',ack)
    from qbatch import execute
    from qevents import enqueue
    release_path=Path(args.first_release);r=read(release_path);p=read(r['proposal']['path']);last=None;fault=None
    try:
        while True:
            atomic_json(chain/'PROGRESS.json',dict(phase='running_batch',utc=utc(),process=process_identity(),job_id=p['job_id'],
                proposal=r['proposal'],claim=p['paths']['claim'],formal_GPU_count=len(p['parents']),reservation='same_inherited_open_file_description'))
            launch,validation=execute(release_path,p,fds,ack);last=launch
            okay=launch['status']=='complete'
            result=dict(status='machine_validated' if okay else 'blocked',reason=launch['primary'],
                validation_ref=launch['validation_ref'] or ref(Path(p['paths']['output'])/'launcher/LAUNCH_RESULT.json'),
                process_exit_proven=launch['process_exit_proven'],publication_complete=launch['publication_complete'],
                source_dispositions=validation['source_dispositions'] if okay else {s:'technical_or_unstarted_consumed' for s in p['source_keys']},
                parents=validation['completion_order_failure_signatures'] if okay else [])
            terminal(p,result)
            enqueue('A',p['job_id'],outcome=result['status'],proposal=p,launch=launch,
                    results=[ref(Path(p['paths']['output'])/'launcher/LAUNCH_RESULT.json'),ref(Path(p['paths']['output'])/'TERMINAL_MANIFEST.json')])
            if not okay:break
            if p['sequence']==1:
                first,first_ref=first_grant()
                if first.get('automatic_continuation_after_machine_pass') is not True:break
                new_json(QUEUE/'nodes/A/CONTINUATION_GRANT.json',dict(schema='queue_continuation_grant_v1',
                    authorization_sha256=AUTH_SHA,automatic_continuation=True,first_release=first_ref,
                    first_validation=launch['validation_ref'],runtime_manifest=ref(PACKAGE/'RUNTIME_MANIFEST.json'),
                    remaining_frozen_sources_only=True,created_utc=utc()))
            atomic_json(chain/'PROGRESS.json',dict(phase='between_batches_admission',utc=utc(),process=process_identity(),last_job=p['job_id']))
            following=prepare_next()
            if following is None:break
            release_path,p=following;r=read(release_path)
    except BaseException as error:
        import traceback
        fault=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
    finally:
        for s in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(s,signal.SIG_IGN)
        cleanup=drain_group(os.getpgrp(),os.getpid())
        new_json(chain/'DRAIN_EXIT.json',dict(utc=utc(),cleanup=cleanup,last=last,fault=fault,
            reservation_release_by_outer_supervisor_only_after_final_publication=True))
    return 0 if fault is None and last and last['status']=='complete' else 3


if __name__=='__main__':sys.exit(main())
