"""Three resident generations, one original guard reservation and formal group."""
import argparse
import os
import signal
import subprocess
import sys
import time
import traceback
from pathlib import Path
import paths
from paths import ROOT,WORKSPACE,TASK
from qio import read,new_json,atomic_json,utc,process_identity
from reservation import send_existing_fd,holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group
from admission import authority,before_cutoff,validate_job,worker_environment
from publication import publish
from publication_data import load_evidence,identity

_JOBS=None
def job_rows():
    global _JOBS
    if _JOBS is None:
        _JOBS=[]
        for row in read(ROOT/'JOB_INDEX.json')['jobs']:
            path=Path(row['path']);job=read(path);validate_job(job)
            _JOBS.append((job['priority'],job['task_order'],job['job_id'],path,job))
        _JOBS.sort()
    return _JOBS

def processed(jid):return (ROOT/'runs'/jid/'RESULT.json').exists() or (ROOT/'failures'/(jid+'.json')).exists()
def available_jobs(stage):
    unfinished=[r for r in job_rows() if r[4]['stage']==stage and not processed(r[2])]
    if not unfinished:return []
    priority=min(r[0] for r in unfinished)
    return [r for r in unfinished if r[0]==priority and not (ROOT/'claims'/r[3].name).exists()]
def remaining_unclaimed(stage):return any(r[4]['stage']==stage and not (ROOT/'claims'/r[3].name).exists() for r in job_rows())

def summarize(chain):
    jobs,attempts,claims,selected=load_evidence();cells={}
    for cell in read(ROOT/'config/CONFIG.json')['cells']:
        key=cell['cell_id'];unique=[x for x in selected if x['cell_id']==key];valid=[x for x in unique if x['status']=='complete']
        physical=[x for x in attempts if x['cell_id']==key];admitted=[x for x in claims if x['cell_id']==key]
        cells[key]=dict(attempts=len(admitted),unique_entered=len({identity(x) for x in admitted}),terminals=len(valid),successes=sum(x['success'] is True for x in valid),technical_failures=sum(x['status']!='complete' for x in physical),unresolved_failed_units=sum(x['status']!='complete' for x in unique),planned_episodes=cell['planned_episodes'],full_cell_complete=len(valid)==cell['planned_episodes'],unstarted=cell['planned_episodes']-len({identity(x) for x in admitted}))
    result=dict(utc=utc(),cells=cells,actual_completed_job_count=len(jobs),valid=sum(x['terminals'] for x in cells.values()),actual_attempts=len(claims),prior_D24_attempts=14376,A_cumulative_attempts=14376+len(claims),compute_complete=all(x['full_cell_complete'] for x in cells.values()),source_count_is_per_cell=True)
    atomic_json(ROOT/'SUMMARY.json',result)
    for key,cell in cells.items():
        if not cell['full_cell_complete']:continue
        state=publish(key)
        event=ROOT/'outbox'/(key+'.json')
        if state['status']=='published' and not event.exists():new_json(event,dict(event_id=TASK+'_'+key,node='A',kind='cell_terminal',synthetic=False,publication=state['publication'],chain=str(chain),utc=utc()))
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--chain',required=True);a=parser.parse_args();chain=Path(a.chain)
    authority();own=process_identity();fds=held_reservation_fds()
    if own['pid']!=own['pgid'] or len(fds)!=1:raise RuntimeError('one original guard reservation/group required')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
    new_json(chain/'MANAGER_STARTED.json',dict(process=own,utc=utc(),single_reservation=True))
    base=read(ROOT/'config/BASE.json');all_workers={};stopping=False;fatal=None;last_beat=0;last_summary=0
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,stop)
    try:
        for stage in ['E6','E1','Random']:
            if stopping or not before_cutoff():break
            authority();workers={};phase=chain/'phases'/stage;phase.mkdir(parents=True,exist_ok=False)
            new_json(phase/'START.json',dict(stage=stage,utc=utc(),reservation_released=False,renderer='Mesa llvmpipe' if stage=='E1' else 'NVIDIA_EGL'))
            for slot in range(8):
                wr=phase/'workers'/str(slot);wr.mkdir(parents=True,exist_ok=False)
                for name in ('inbox','done','tmp','cache','xdg'):(wr/name).mkdir(mode=0o700)
                argv=[base['python'],'-B',str(ROOT/'code/resident_worker.py'),'--slot',str(slot),'--root',str(wr),'--stage',stage]
                env=worker_environment(base,wr)
                if stage=='E1':
                    env['VLA_RENDERER']='mesa';env['VLA_EGL_DEVICE_ID']='0'
                    argv=['bash',str(WORKSPACE/'embodied-ai-workspace/projects/vla-baselines/launchers/runtime.sh'),'mw-pi05-legacy']+argv
                with (wr/'stdout.log').open('xb') as so,(wr/'stderr.log').open('xb') as se:
                    proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=so,stderr=se,env=env,cwd=ROOT,pass_fds=fds,start_new_session=False)
                w=dict(proc=proc,root=wr,index=0,busy=None,start=time.monotonic(),assigned_at=None,exit_recorded=False,term_at=None)
                workers[slot]=w;all_workers[stage+'_'+str(slot)]=w
            while True:
                pending=available_jobs(stage) if not stopping and before_cutoff() else [];alive=0
                for slot,w in workers.items():
                    proc,wr=w['proc'],w['root']
                    if proc.poll() is not None:
                        if not w['exit_recorded']:
                            new_json(wr/'PROCESS_EXIT.json',dict(exit_code=proc.returncode,utc=utc(),job=w['busy']));w['exit_recorded']=True
                            if w['busy'] and not (ROOT/'runs'/w['busy']/'RESULT.json').exists():
                                new_json(ROOT/'failures'/(w['busy']+'.json'),dict(job_id=w['busy'],status='worker_exit_without_complete_job',exit_code=proc.returncode,worker=str(wr),success=None,utc=utc()))
                            if proc.returncode:
                                event=ROOT/'outbox'/('worker_'+stage+'_'+str(slot)+'.json')
                                new_json(event,dict(event_id=TASK+'_worker_failure_'+stage+'_'+str(slot),kind='worker_failure',synthetic=False,worker=str(wr),job=w['busy'],exit_code=proc.returncode,utc=utc()))
                                terminal=read(wr/'WORKER_EXIT.json') if (wr/'WORKER_EXIT.json').exists() else {}
                                message=(terminal.get('fatal') or {}).get('message','')
                                if terminal.get('cleanup') or not message.startswith('worker stops after job/episode technical failure:'):
                                    raise RuntimeError('model/identity/cleanup worker failure: '+str(wr))
                        continue
                    alive+=1
                    timed_out=(not (wr/'MODEL_READY.json').exists() and time.monotonic()-w['start']>900) or (w['busy'] and time.monotonic()-w['assigned_at']>19000)
                    if stopping or timed_out:
                        if w['term_at'] is None:proc.send_signal(signal.SIGTERM);w['term_at']=time.monotonic()
                        elif time.monotonic()-w['term_at']>30:proc.kill()
                        continue
                    if w['busy'] and (wr/'done'/('%05d.json'%w['index'])).exists():w['busy']=None;w['assigned_at']=None
                    if not (wr/'MODEL_READY.json').exists() or w['busy']:continue
                    if pending:
                        authority();_,_,jid,path,job=pending.pop(0)
                        new_json(ROOT/'claims'/path.name,dict(job_id=jid,cell_id=job['cell_id'],stage=stage,slot=slot,GPU=base['device_list'][slot],job=str(path),utc=utc(),process=process_identity(proc.pid),run_id=TASK+'_'+jid,no_automatic_retry=True))
                        w['index']+=1;w['busy']=jid;w['assigned_at']=time.monotonic()
                        new_json(wr/'inbox'/('%05d.json'%w['index']),dict(job=str(path),output=str(ROOT/'runs'/jid),claim=str(ROOT/'claims'/path.name)))
                    elif not remaining_unclaimed(stage) or stopping or not before_cutoff():
                        if not (wr/'STOP.json').exists():new_json(wr/'STOP.json',dict(reason='phase queue drained or cutoff',utc=utc()))
                now=time.monotonic()
                if not before_cutoff():stopping=True
                if now-last_beat>=5:
                    authority()
                    atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),manager=own,stage=stage,status='draining' if stopping else 'running',living_workers=alive,active_jobs={str(k):w['busy'] for k,w in workers.items() if w['proc'].poll() is None},loaded_workers=sum((w['root']/'MODEL_READY.json').exists() and w['proc'].poll() is None for w in workers.values()),pending_jobs=len(available_jobs(stage)),holder_policy='all8_off_entire_wave_including_loading_gaps_tail'))
                    last_beat=now
                if now-last_summary>=60:summarize(chain);last_summary=now
                if not alive:break
                time.sleep(.5)
            for w in workers.values():w['proc'].wait()
            # No generation overlap, and no release/reacquisition of formal.lock.
            drain=drain_group(own['pgid'],own['pid'])
            new_json(phase/'EXIT.json',dict(utc=utc(),workers={str(k):w['proc'].returncode for k,w in workers.items()},drain=drain,reservation_released=False))
            summarize(chain)
    except BaseException as e:fatal=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    finally:
        for w in all_workers.values():
            if w['proc'].poll() is None:w['proc'].send_signal(signal.SIGTERM)
        cleanup=drain_group(own['pgid'],own['pid'])
        for w in all_workers.values():w['proc'].wait()
        try:summary=summarize(chain);atomic_json(ROOT/'COMPUTE_SUMMARY.json',summary)
        except BaseException as error:
            if fatal is None:fatal=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
            summary=read(ROOT/'SUMMARY.json') if (ROOT/'SUMMARY.json').exists() else None
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,summary=summary,workers={k:w['proc'].returncode for k,w in all_workers.items()},all_owned_processes_exited=cleanup.get('status')=='all_formal_group_members_exited',auxiliary_exit=[]))
    return 3 if fatal or any(w['proc'].returncode for w in all_workers.values()) else 0

if __name__=='__main__':sys.exit(main())
