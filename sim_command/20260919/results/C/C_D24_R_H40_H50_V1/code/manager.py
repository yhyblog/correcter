"""Eight resident A-main workers, C-only FIFO jobs, one inherited reservation."""
import argparse
import os
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path
import paths
from paths import ROOT
from qio import read, new_json, atomic_json, utc, process_identity
from reservation import send_existing_fd, holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group
from admission import authority, before_cutoff, validate_job, worker_environment

def main():
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);a=p.parse_args();chain=Path(a.chain)
    authority();own=process_identity();fds=held_reservation_fds()
    if own['pid'] != own['pgid'] or len(fds) != 1:
        raise RuntimeError('Requires exactly one original guard reservation and isolated group')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0])
    ack=holder_exit_ack(request)
    new_json(chain/'HOLDER_EXIT_ACK.json',ack)
    new_json(chain/'MANAGER_STARTED.json',dict(process=own,utc=utc(),single_reservation=True,
        holder_policy='all holders off for whole wave including loading/gaps/finished cards'))
    base=read(ROOT/'config/BASE.json');jobs=[]
    for path in (ROOT/'jobs').glob('*.json'):
        job=read(path);validate_job(job)
        jobs.append((job['priority'],job['task_order'],job['job_id'],path,job))
    jobs.sort()
    if len(jobs)!=100 or sum(len(x[4]['sources']) for x in jobs)!=1000:
        raise RuntimeError('Frozen 1000 first-entry scope differs')
    pending=[x for x in jobs if not (ROOT/'claims'/x[3].name).exists() and not (ROOT/'runs'/x[2]/'RESULT.json').exists()]
    workers={};stopping=False;fatal=None;last_beat=0;started=time.monotonic()
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,stop)
    try:
        for slot in range(8):
            wr=chain/'workers'/str(slot);wr.mkdir(parents=True,exist_ok=False)
            for name in ('inbox','done','tmp','cache','xdg'):(wr/name).mkdir(mode=0o700)
            argv=[base['python'],'-B',str(ROOT/'code/resident_worker.py'),'--slot',str(slot),'--root',str(wr)]
            with (wr/'stdout.log').open('xb') as so,(wr/'stderr.log').open('xb') as se:
                proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=so,stderr=se,
                    env=worker_environment(base,wr),cwd=ROOT,pass_fds=fds,start_new_session=False)
            new_json(wr/'PROCESS.json',process_identity(proc.pid))
            workers[slot]=dict(proc=proc,root=wr,index=0,busy=None,start=time.monotonic(),assigned_at=None,
                               exit_recorded=False,term_at=None)
        while True:
            authority()
            if time.monotonic()-started>=6*3600 or not before_cutoff():stopping=True
            alive=0
            for slot,w in workers.items():
                proc,wr=w['proc'],w['root']
                if proc.poll() is not None:
                    if not w['exit_recorded']:
                        new_json(wr/'PROCESS_EXIT.json',dict(exit_code=proc.returncode,utc=utc(),job=w['busy']))
                        w['exit_recorded']=True
                        if w['busy'] and not (ROOT/'runs'/w['busy']/'RESULT.json').exists():
                            new_json(ROOT/'failures'/(w['busy']+'.json'),dict(job_id=w['busy'],
                                status='worker_exit_without_job_result',exit_code=proc.returncode,
                                worker=str(wr),success=None,utc=utc(),source_results_remain_authoritative=True))
                    continue
                alive+=1
                timed_out=(not (wr/'MODEL_READY.json').exists() and time.monotonic()-w['start']>900) or (
                    w['busy'] and time.monotonic()-w['assigned_at']>19000)
                if stopping or timed_out:
                    if w['term_at'] is None:
                        proc.send_signal(signal.SIGTERM);w['term_at']=time.monotonic()
                    elif time.monotonic()-w['term_at']>30:proc.kill()
                    continue
                if w['busy'] and (wr/'done'/('%05d.json'%w['index'])).exists():
                    w['busy']=None;w['assigned_at']=None
                if not (wr/'MODEL_READY.json').exists() or w['busy']:continue
                if pending:
                    _,_,jid,path,job=pending.pop(0)
                    authority()
                    claim=dict(job_id=jid,slot=slot,GPU=base['device_list'][slot],job=str(path),utc=utc(),
                        process=process_identity(proc.pid),run_id='D24_C_R_H40_H50_r1_'+jid,no_automatic_retry=True)
                    new_json(ROOT/'claims'/path.name,claim)
                    w['index']+=1;w['busy']=jid;w['assigned_at']=time.monotonic()
                    new_json(wr/'inbox'/('%05d.json'%w['index']),dict(job=str(path),output=str(ROOT/'runs'/jid),claim=str(ROOT/'claims'/path.name)))
                elif not (wr/'STOP.json').exists():
                    new_json(wr/'STOP.json',dict(reason='no unclaimed jobs; other workers drain independently',utc=utc()))
            if time.monotonic()-last_beat>=5:
                atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),manager=own,status='draining' if stopping else 'running',
                    living_workers=alive,loaded_workers=sum((w['root']/'MODEL_READY.json').exists() and w['proc'].poll() is None for w in workers.values()),
                    active_jobs={str(k):w['busy'] for k,w in workers.items() if w['proc'].poll() is None},
                    pending_jobs=len(pending),resolved_jobs=len(list((ROOT/'runs').glob('*/RESULT.json'))),
                    holder_policy='all holders off entire formal wave',new_retry_attempts=0))
                last_beat=time.monotonic()
            if not alive:break
            time.sleep(.5)
    except BaseException as e:
        fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    finally:
        for w in workers.values():
            if w['proc'].poll() is None:w['proc'].send_signal(signal.SIGTERM)
        cleanup=drain_group(own['pgid'],own['pid'])
        for w in workers.values():w['proc'].wait()
        completed=all((ROOT/'runs'/j[2]/'RESULT.json').exists() and read(ROOT/'runs'/j[2]/'RESULT.json')['status']=='complete' for j in jobs)
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,
            workers={str(k):w['proc'].returncode for k,w in workers.items()},all_owned_processes_exited=True,
            all_jobs_complete=completed,remaining_unclaimed=len(pending),elapsed_seconds=time.monotonic()-started,
            auxiliary_holder_launches=0))
    return 0 if completed and not fatal and all(w['proc'].returncode==0 for w in workers.values()) else 3

if __name__=='__main__':sys.exit(main())
