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


_JOBS=None

def job_rows():
    global _JOBS
    if _JOBS is None:
        _JOBS=[]
        for path in (ROOT/'jobs').glob('*.json'):
            job=read(path);validate_job(job)
            _JOBS.append((job['priority'],job['task_order'],job['job_id'],path,job))
        _JOBS.sort()
    return _JOBS

def group(job):return job['priority']

def processed(jid):return (ROOT/'runs'/jid/'RESULT.json').exists() or (ROOT/'failures'/(jid+'.json')).exists()

def available_jobs():
    unfinished=[row for row in job_rows() if not processed(row[2])]
    if not unfinished:return []
    current_group=min(group(row[4]) for row in unfinished)
    return [row for row in unfinished if group(row[4])==current_group and not (ROOT/'claims'/row[3].name).exists()]

def remaining_unclaimed():return any(not (ROOT/'claims'/row[3].name).exists() for row in job_rows())


def summarize(chain):
    rows=[]
    for path in (ROOT/'runs').glob('*/JOB_SUMMARY.json'):
        rows.append(read(path))
    cells={}
    for row in rows:
        key=row['method']+'_'+row['mode']+'_H'+str(row['H']);cell=cells.setdefault(key,dict(jobs=0,attempts=0,terminals=0,successes=0,technical_failures=0,tasks={}))
        cell['jobs']+=1
        for name,field in [('attempts','entered_episodes'),('terminals','terminal_episodes'),('successes','successes'),('technical_failures','technical_failures')]:cell[name]+=row.get(field,0)
        cell['tasks'][row['task']]={k:row.get(k) for k in ('status','entered_episodes','terminal_episodes','successes','technical_failures','elapsed_seconds')}
    for cell in cells.values():
        cell['planned_episodes']=500
        cell['full_cell_complete']=cell['terminals']==500
        cell['terminal_success_rate']=cell['successes']/cell['terminals'] if cell['full_cell_complete'] else None
        cell['technical_failures_are_excluded_not_scored_zero']=True
    result=dict(utc=utc(),cells=cells,actual_completed_job_count=len(rows),source_count_is_per_cell=True)
    atomic_json(ROOT/'SUMMARY.json',result)
    for key,cell in cells.items():
        if cell['jobs']==50 and not (ROOT/'outbox'/(key+'.json')).exists():
            new_json(ROOT/'outbox'/(key+'.json'),dict(event_id='D24_B_POST_TRIGGER_MODES_'+key,node='B',kind='method_H_all_jobs_terminal_or_partial',
                synthetic=False,summary=result,chain=str(chain),utc=utc()))
    for key,cell in cells.items():
        if cell['jobs']!=50:continue
        folder=ROOT/'cell_publications'/key;folder.mkdir(exist_ok=True)
        if (folder/'PUBLICATION_ATTEMPT.json').exists():continue
        new_json(folder/'PUBLICATION_ATTEMPT.json',dict(utc=utc(),source='all50jobs_terminal'))
        try:
            published=subprocess.run([read(ROOT/'config/BASE.json')['python'],'-B',str(ROOT/'code/publish_trigger.py'),'--cell',key],
                cwd=ROOT,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'),capture_output=True,text=True,timeout=180)
            atomic_json(folder/'PUBLICATION_PROCESS.json',dict(exit_code=published.returncode,stdout=published.stdout[-4000:],stderr=published.stderr[-4000:],utc=utc()))
        except BaseException as error:
            atomic_json(folder/'PUBLICATION_PROCESS.json',dict(error=str(error),utc=utc()))
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);a=p.parse_args();chain=Path(a.chain)
    authority();own=process_identity();fds=held_reservation_fds()
    if own['pid']!=own['pgid'] or len(fds)!=1:raise RuntimeError('requires original single guard reservation and group')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0])
    ack=holder_exit_ack(request);new_json(chain/'HOLDER_EXIT_ACK.json',ack)
    new_json(chain/'MANAGER_STARTED.json',dict(process=own,utc=utc(),single_reservation=True))
    base=read(ROOT/'config/BASE.json');workers={};stopping=False;fatal=None;last_beat=0;last_summary=0;last_occupancy=0
    from occupancy_adapter import WorkerOccupancy
    occupancy=WorkerOccupancy(chain,base['device_list'],ack,own)
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,stop)
    try:
        for slot in range(8):
            wr=chain/'workers'/str(slot);wr.mkdir(parents=True,exist_ok=False)
            for name in ('inbox','done','tmp','cache'): (wr/name).mkdir()
            command=[base['python'],'-B',str(ROOT/'code/resident_worker.py'),'--slot',str(slot),'--root',str(wr)]
            occupancy.before(slot)
            with (wr/'stdout.log').open('xb') as so,(wr/'stderr.log').open('xb') as se:
                proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=so,stderr=se,
                    env=worker_environment(base,wr),cwd=ROOT,pass_fds=fds,start_new_session=False)
            occupancy.started(slot,proc.pid)
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
                                event_id='D24_B_POST_worker_failure_'+str(own['pid'])+'_'+str(slot),node='B',kind='worker_failure',
                                synthetic=False,worker=str(wr),job=w['busy'],exit_code=proc.returncode,utc=utc()))
                    continue
                alive+=1
                timed_out=(not (wr/'MODEL_READY.json').exists() and time.monotonic()-w['start']>900) or (w['busy'] and time.monotonic()-w['assigned_at']>19000)
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
                    if len(list((ROOT/'claims').glob('*.json')))*10>=5000:raise RuntimeError('B initial5000 attempt admission cap')
                    claim=dict(job_id=jid,slot=slot,GPU=base['device_list'][slot],job=str(path),utc=utc(),
                        process=process_identity(proc.pid),run_id='D24_B_POST_TRIGGER_MODES_v1_'+jid,no_retry=True)
                    new_json(ROOT/'claims'/path.name,claim)
                    w['index']+=1;w['busy']=jid;w['assigned_at']=time.monotonic()
                    new_json(wr/'inbox'/('%05d.json'%w['index']),dict(job=str(path),output=str(ROOT/'runs'/jid),claim=str(ROOT/'claims'/path.name)))
                elif not remaining_unclaimed() or stopping or not before_cutoff():
                    if not (wr/'STOP.json').exists():new_json(wr/'STOP.json',dict(reason='queue drained or cutoff',utc=utc()))
            now=time.monotonic()
            if now-last_beat>=5:
                atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),manager=own,status='draining' if stopping else 'running',
                    living_workers=alive,active_jobs={str(k):w['busy'] for k,w in workers.items() if w['proc'].poll() is None},
                    loaded_workers=sum((w['root']/'MODEL_READY.json').exists() and w['proc'].poll() is None for w in workers.values()),
                    pending_jobs=len(available_jobs()),holder_policy='all8off_entire_formal_wave; no idle subset holders'))
                last_beat=now
            if now-last_occupancy>=5:occupancy.refresh(workers);last_occupancy=now
            if now-last_summary>=30:summarize(chain);last_summary=now
            if not alive:break
            time.sleep(.5)
    except BaseException as e:
        fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    finally:
        for w in workers.values():
            if w['proc'].poll() is None:w['proc'].send_signal(signal.SIGTERM)
        cleanup=drain_group(own['pgid'],own['pid'])
        for w in workers.values():w['proc'].wait()
        auxiliary=occupancy.close()
        summary=summarize(chain)
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,summary=summary,
            workers={str(k):w['proc'].returncode for k,w in workers.items()},all_owned_processes_exited=True,auxiliary_exit=auxiliary))
    return 3 if fatal or any(w['proc'].returncode for w in workers.values()) else 0

if __name__=='__main__':sys.exit(main())
