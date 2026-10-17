"""Cancel queued work without interrupting the minimum delivered chunks.

Only the exact current formal manager receives STOP/CONT. GPU workers receive
their existing idle STOP marker and finish their already delivered job first.
No scientific code, weights, shared controls, claims or input data are changed.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'code'))
from qio import read,new_json,atomic_json,utc,process_identity,same_process

EXPECTED_SHA='7e7c84f47284a71dee130bae1239ee3d18f04b176bbea7ad5a66e06da792b5a7'
CAMPAIGN=ROOT.parents[2]
OVERRIDE=CAMPAIGN/'deadline_20260924/Q_LOSS_PRIORITY_OVERRIDE_V1.json'

def command(pid):return Path('/proc',str(pid),'cmdline').read_bytes().replace(b'\0',b' ').decode()
def validated_manager():
    row=read(ROOT/'chain/MANAGER_STARTED.json')['process']
    if not same_process(row):return None
    if row['host']!=socket.gethostname() or row['pid']!=row['pgid']:raise RuntimeError('manager identity mismatch')
    if str(ROOT/'code/manager.py') not in command(row['pid']):raise RuntimeError('manager command mismatch')
    return row

def signal_exact(row,sig):
    if same_process(row):os.kill(row['pid'],sig)

def main():
    if hashlib.sha256(OVERRIDE.read_bytes()).hexdigest()!=EXPECTED_SHA:raise RuntimeError('override identity mismatch')
    doc=read(OVERRIDE)
    if not doc['cancel_Random_multi'] or doc['A']['new_legacy_E1_episode_admissions'] is not False:raise RuntimeError('wrong cancellation scope')
    with Path('/tmp/corrector_A_multi_primary_cancel_v1.lock').open('a') as singleton:
        try:fcntl.flock(singleton,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        if (HERE/'DONE.json').exists():return
        new_json(HERE/'OBSERVER_STARTED.json',dict(utc=utc(),process=process_identity(),scientific_compute=0))
        manager=validated_manager();paused=False
        try:
            if manager is not None:
                signal_exact(manager,signal.SIGSTOP);paused=True
                end=time.monotonic()+10
                while same_process(manager) and process_identity(manager['pid'])['state'] not in ('T','t'):
                    if time.monotonic()>=end:raise RuntimeError('owned scheduler did not pause')
                    time.sleep(.05)
            counter=read(ROOT/'ATTEMPT_COUNTER.json') if (ROOT/'ATTEMPT_COUNTER.json').exists() else {'count':0}
            claims={p.stem:read(p) for p in (ROOT/'unit_claims').glob('*.json')}
            delivered=[];workers=[]
            for wr in sorted((ROOT/'chain/phases').glob('*/workers/*')):
                started=wr/'STARTED.json'
                if not started.exists():continue
                worker=read(started)['process']
                if not same_process(worker):continue
                if manager is None or worker['pgid']!=manager['pgid'] or str(ROOT/'code/resident_worker.py') not in command(worker['pid']):raise RuntimeError('worker identity mismatch')
                workers.append(dict(root=str(wr),process=worker))
                for inbox in sorted((wr/'inbox').glob('*.json')):
                    if (wr/'done'/inbox.name).exists():continue
                    payload=read(inbox);job=read(payload['job'])
                    if len(job['sources'])>5 and job['stage']=='E1':raise RuntimeError('unexpected E1 chunk size')
                    not_entered=[s['source_id'] for s in job['sources'] if job['cell_id']+'__'+s['source_id'] not in claims]
                    delivered.append(dict(worker=str(wr),inbox=str(inbox),job_id=job['job_id'],stage=job['stage'],cell_id=job['cell_id'],sources=[s['source_id'] for s in job['sources']],not_entered_at_pause=not_entered,minimum_bounded_chunk=True))
                stop=wr/'STOP.json'
                if not stop.exists():new_json(stop,dict(reason='user Q loss priority cancellation; finish already delivered chunk then exit',override_sha256=EXPECTED_SHA,utc=utc()))
            snap=dict(utc=utc(),status='DISPATCH_FROZEN_MINIMUM_DELIVERED_CHUNKS_DRAINING',manager=manager,manager_signal='SIGSTOP exact PID only',worker_signals=0,workers=workers,delivered_chunks=delivered,maximum_additional_chunk_entries=sum(len(x['not_entered_at_pause']) for x in delivered),counter_at_pause=counter,Random_multi_claims_at_pause=sum(c['stage']=='Random' for c in claims.values()),all_unhanded_jobs_cancelled=True,new_legacy_E1_dispatch=False,new_Random_dispatch=False,root_STOP_deferred_until_workers_exit=True,override_sha256=EXPECTED_SHA,scientific_compute_by_observer=0)
            new_json(HERE/'CANCELLATION_APPLIED.json',snap)
            deadline=time.monotonic()+5*1800+120
            while True:
                living=[w for w in workers if same_process(w['process'])]
                atomic_json(HERE/'HEARTBEAT.json',dict(utc=utc(),status='draining_delivered_chunks',living_workers=[w['process']['pid'] for w in living],observer=process_identity(),scientific_compute=0))
                if not living:break
                if time.monotonic()>deadline:
                    new_json(HERE/'DRAIN_TIMEOUT.json',dict(utc=utc(),living=living,note='no forced worker termination; original finite controller/deadline remains in force'))
                    # Preserve natural completion; report the bounded observer
                    # timeout rather than inventing a right to kill a worker.
                    deadline=time.monotonic()+1800
                time.sleep(1)
            stop=ROOT/'STOP.json'
            if not stop.exists():new_json(stop,dict(reason='user canceled remaining legacy E1 and all Random-multi; all delivered workers have exited',override_sha256=EXPECTED_SHA,utc=utc(),disposition='cancelled_not_scientific_failure'))
            if manager is not None:signal_exact(manager,signal.SIGCONT);paused=False
            new_json(HERE/'ALL_DELIVERED_WORKERS_EXITED.json',dict(utc=utc(),workers=workers,manager_resumed_for_original_cleanup=True,root_STOP=str(stop),worker_signals=0))
            end=time.monotonic()+600
            while not (ROOT/'RESULT.json').exists():
                if time.monotonic()>=end:
                    new_json(HERE/'TERMINAL_OBSERVATION_TIMEOUT.json',dict(utc=utc(),original_chain_responsible_for_cleanup_and_restore=True));return
                time.sleep(1)
            result=read(ROOT/'RESULT.json');counts=read(ROOT/'ATTEMPT_COUNTER.json')
            new_json(HERE/'DONE.json',dict(utc=utc(),status='CANCELLED_REMAINDER_ORIGINAL_CHAIN_TERMINAL',result=str(ROOT/'RESULT.json'),counter=counts,original_status=result['status'],all_owned_descendants_exited=result.get('all_owned_descendants_exited'),restoration=result.get('restoration'),override_sha256=EXPECTED_SHA,scientific_compute_by_observer=0))
        except BaseException as e:
            atomic_json(HERE/'OBSERVER_ERROR.json',dict(utc=utc(),type=type(e).__name__,message=str(e),traceback=traceback.format_exc(),manager_paused=paused))
            # Never resume an unguarded scheduler and thereby admit revoked
            # work. A reconciliation turn can inspect this durable error.
            raise

if __name__=='__main__':main()
