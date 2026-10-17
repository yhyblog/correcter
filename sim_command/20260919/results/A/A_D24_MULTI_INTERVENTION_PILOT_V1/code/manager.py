"""Guard-owned continuous formal group. No nested lifecycle or holder launch."""
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
from qio import read,new_json,atomic_json,utc,process_identity
from reservation import send_existing_fd,holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group
from admission import authority,before_cutoff,validate_job,worker_environment


def available_jobs():
    rows=[]
    for path in (ROOT/'jobs').glob('*.json'):
        if (ROOT/'claims'/path.name).exists():continue
        job=read(path);validate_job(job)
        rows.append((job['priority'],job['task_order'],job['job_id'],path,job))
    return sorted(rows)


from reporting import summarize


def main():
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);a=p.parse_args();chain=Path(a.chain)
    authority();own=process_identity();fds=held_reservation_fds()
    if own['pid']!=own['pgid'] or len(fds)!=1:raise RuntimeError('requires original single guard reservation and group')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0])
    new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
    new_json(chain/'MANAGER_STARTED.json',dict(process=own,utc=utc(),single_reservation=True))
    base=read(ROOT/'config/BASE.json');workers={};stopping=False;fatal=None;last_beat=0;last_summary=0
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,stop)
    try:
        for slot in range(8):
            wr=chain/'workers'/str(slot);wr.mkdir(parents=True,exist_ok=False)
            for name in ('inbox','done','tmp','cache'): (wr/name).mkdir()
            command=[base['python'],'-B',str(ROOT/'code/resident_worker.py'),'--slot',str(slot),'--root',str(wr)]
            with (wr/'stdout.log').open('xb') as so,(wr/'stderr.log').open('xb') as se:
                proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=so,stderr=se,
                    env=worker_environment(base,wr),cwd=ROOT,pass_fds=fds,start_new_session=False)
            workers[slot]=dict(proc=proc,root=wr,index=0,busy=None,start=time.monotonic(),assigned_at=None,exit_recorded=False,term_at=None)
        while True:
            pending=available_jobs() if not stopping and before_cutoff() else []
            alive=0
            for slot,w in workers.items():
                proc,wr=w['proc'],w['root']
                if proc.poll() is not None:
                    if not w['exit_recorded']:
                        new_json(wr/'PROCESS_EXIT.json',dict(exit_code=proc.returncode,utc=utc(),job=w['busy']))
                        w['exit_recorded']=True
                        if w['busy'] and not (ROOT/'runs'/w['busy']/'RESULT.json').exists():
                            new_json(ROOT/'failures'/(w['busy']+'.json'),dict(job_id=w['busy'],status='worker_exit_without_complete_job',
                                exit_code=proc.returncode,worker=str(wr),success=None,utc=utc()))
                        if proc.returncode:
                            new_json(ROOT/'outbox'/('worker_'+str(slot)+'_'+str(own['pid'])+'.json'),dict(
                                event_id='D24_A_pilot_worker_failure_'+str(own['pid'])+'_'+str(slot),node='A',kind='worker_failure',
                                synthetic=False,worker=str(wr),job=w['busy'],exit_code=proc.returncode,utc=utc()))
                    continue
                alive+=1
                timed_out=(not (wr/'MODEL_READY.json').exists() and time.monotonic()-w['start']>900) or (w['busy'] and time.monotonic()-w['assigned_at']>2100)
                if stopping or timed_out:
                    if w['term_at'] is None:proc.send_signal(signal.SIGTERM);w['term_at']=time.monotonic()
                    elif time.monotonic()-w['term_at']>30:proc.kill()
                    continue
                if w['busy'] and (wr/'done'/('%05d.json'%w['index'])).exists():w['busy']=None;w['assigned_at']=None
                if not (wr/'MODEL_READY.json').exists():
                    continue
                if w['busy']:
                    continue
                if pending:
                    authority()
                    _,_,jid,path,job=pending.pop(0)
                    if len(list((ROOT/'claims').glob('*.json')))>=120:raise RuntimeError('fixed old20 six-arm attempt admission cap')
                    claim=dict(job_id=jid,slot=slot,GPU=base['device_list'][slot],job=str(path),utc=utc(),
                        process=process_identity(proc.pid),run_id='D24_A_multi_pilot_r2_'+jid,no_retry=True)
                    new_json(ROOT/'claims'/path.name,claim)
                    w['index']+=1;w['busy']=jid;w['assigned_at']=time.monotonic()
                    new_json(wr/'inbox'/('%05d.json'%w['index']),dict(job=str(path),output=str(ROOT/'runs'/jid),claim=str(ROOT/'claims'/path.name)))
                elif not available_jobs() or stopping or not before_cutoff():
                    if not (wr/'STOP.json').exists():new_json(wr/'STOP.json',dict(reason='queue drained or cutoff',utc=utc()))
            now=time.monotonic()
            if now-last_beat>=5:
                atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),manager=own,status='draining' if stopping else 'running',
                    living_workers=alive,active_jobs={str(k):w['busy'] for k,w in workers.items() if w['proc'].poll() is None},
                    loaded_workers=sum((w['root']/'MODEL_READY.json').exists() and w['proc'].poll() is None for w in workers.values()),
                    pending_jobs=len(available_jobs()),holder_policy='all8off_until_all_descendants_exit_and_publication'))
                last_beat=now
            if now-last_summary>=5:summarize(chain);last_summary=now
            if not alive:break
            time.sleep(.5)
    except BaseException as e:
        fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    finally:
        for w in workers.values():
            if w['proc'].poll() is None:w['proc'].send_signal(signal.SIGTERM)
        cleanup=drain_group(own['pgid'],own['pid'])
        for w in workers.values():w['proc'].wait()
        summary=summarize(chain)
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,summary=summary,
            workers={str(k):w['proc'].returncode for k,w in workers.items()},all_owned_processes_exited=True))
    return 3 if fatal or any(w['proc'].returncode for w in workers.values()) else 0

if __name__=='__main__':sys.exit(main())
