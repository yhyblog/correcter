"""24 resident C evaluators, exact grants, H40 drain before H50 admission."""
import argparse,os,signal,subprocess,sys,time,traceback
from pathlib import Path
import paths
from paths import ROOT,TASK
from qio import read,new_json,atomic_json,utc,process_identity
from reservation import send_existing_fd,holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group
from operational_hook import consume,record_fault
from admission import authority,before_cutoff,admissions_allowed,validate_job,worker_environment

def ordered_jobs():
    jobs=[]
    for r in read(ROOT/'JOB_INDEX.json')['jobs']:
        p=Path(r['path']);j=read(p);validate_job(j)
        jobs.append((j['H'],j['chunk'],j['task_order'],j['method'],j['job_id'],p,j))
    return sorted(jobs)

def processed(jid):return (ROOT/'runs'/jid/'RESULT.json').exists() or (ROOT/'failures'/(jid+'.json')).exists()
def pending(rows,H):return [r for r in rows if r[0]==H and not processed(r[4]) and not (ROOT/'claims'/(r[4]+'.json')).exists()]

def main():
    p=argparse.ArgumentParser();p.add_argument('--chain',required=True);p.add_argument('--stage',choices=['evaluate'],required=True);a=p.parse_args();chain=Path(a.chain)
    authority();consume(ROOT,'evaluation_entry');own=process_identity();fds=held_reservation_fds()
    if own['pid']!=own['pgid'] or len(fds)!=1:raise RuntimeError('single original reservation/group required')
    request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
    new_json(chain/'MANAGER_STARTED.json',dict(process=own,utc=utc(),single_reservation=True))
    base=read(ROOT/'config/BASE.json');workers={};all_children={};stopping=False;fatal=None;started_slots=0;phase_index=0;phases=[40,50];rows=[]
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,stop)
    def beat(H,**extra):atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),manager=own,H=H,holder_policy='all8_off_entire_wave',**extra))
    def launch_tranche():
        nonlocal started_slots
        for slot in range(started_slots,min(started_slots+8,24)):
            wr=chain/'workers'/str(slot);wr.mkdir(parents=True,exist_ok=False)
            for name in ['inbox','done','tmp','cache','xdg']:(wr/name).mkdir(mode=0o700)
            argv=[base['python'],'-B',str(ROOT/'code/resident_worker.py'),'--slot',str(slot),'--root',str(wr),'--stage','EVAL']
            with (wr/'stdout.log').open('xb') as so,(wr/'stderr.log').open('xb') as se:
                proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=so,stderr=se,env=worker_environment(base,wr),cwd=ROOT,pass_fds=fds,start_new_session=False)
            all_children[slot]=proc;workers[slot]=dict(proc=proc,root=wr,index=0,busy=None,start=time.monotonic(),assigned_at=None,exit_recorded=False,term_at=None)
            new_json(wr/'PROCESS_STARTED.json',dict(process=process_identity(proc.pid),argv=argv,utc=utc(),GPU=base['device_list'][slot%8]))
        started_slots=min(started_slots+8,24)
    try:
        if not admissions_allowed():raise RuntimeError('C admission closed before model loading')
        rows=ordered_jobs();lastbeat=0;launch_tranche()
        while True:
            if not admissions_allowed() and not stopping:
                stopping=True
                if not (ROOT/'DRAIN.json').exists():new_json(ROOT/'DRAIN.json',dict(reason='live stop/cutoff/grant no longer admits new episodes',utc=utc()))
            H=phases[phase_index] if phase_index<len(phases) else None
            if not stopping and started_slots<24 and all((w['root']/'MODEL_READY.json').exists() or w['proc'].poll() is not None for w in workers.values()):launch_tranche()
            queue=pending(rows,H) if H and not stopping else [];alive=0
            for slot,w in workers.items():
                proc,wr=w['proc'],w['root']
                if proc.poll() is not None:
                    if not w['exit_recorded']:
                        new_json(wr/'PROCESS_EXIT.json',dict(exit_code=proc.returncode,utc=utc(),job=w['busy']));w['exit_recorded']=True
                        if w['busy'] and not (ROOT/'runs'/w['busy']/'RESULT.json').exists():
                            new_json(ROOT/'failures'/(w['busy']+'.json'),dict(job_id=w['busy'],status='worker_exit_without_complete_job',exit_code=proc.returncode,worker=str(wr),success=None,utc=utc()))
                        if proc.returncode:
                            terminal=read(wr/'WORKER_EXIT.json') if (wr/'WORKER_EXIT.json').exists() else {}
                            issue=dict(utc=utc(),worker=str(wr),job=w['busy'],exit_code=proc.returncode,terminal=terminal,classification='technical_worker_failure',completed_sources_preserved=True,unchanged_retry=False,independent_work_may_continue=True,analysis_wait_timeout_seconds=1800)
                            new_json(ROOT/'issues'/f'worker_{slot}.json',issue)
                            msg=(terminal.get('fatal') or {}).get('message','')
                            if terminal.get('cleanup') or not msg.startswith('worker stops after job/episode technical failure:'):raise RuntimeError('model/identity/cleanup worker failure: '+str(wr))
                        w['busy']=None
                    continue
                alive+=1
                if w['busy'] and (wr/'done'/('%05d.json'%w['index'])).exists():w['busy']=None;w['assigned_at']=None
                timed_out=(not (wr/'MODEL_READY.json').exists() and time.monotonic()-w['start']>1200) or (w['busy'] and time.monotonic()-w['assigned_at']>9200)
                if timed_out or not before_cutoff():
                    if w['term_at'] is None:proc.send_signal(signal.SIGTERM);w['term_at']=time.monotonic()
                    elif time.monotonic()-w['term_at']>30:proc.kill()
                    continue
                if stopping or H is None:
                    if not (wr/'STOP.json').exists():new_json(wr/'STOP.json',dict(reason='queue drained or graceful stop',utc=utc()))
                    continue
                if not (wr/'MODEL_READY.json').exists() or w['busy'] or not queue:continue
                if not admissions_allowed():continue
                _,_,_,_,jid,path,job=queue.pop(0);validate_job(job)
                from transfer import assert_not_A_owned
                assert_not_A_owned(jid)
                new_json(ROOT/'claims'/(jid+'.json'),dict(job_id=jid,cell_id=job['cell_id'],stage='MAIN',H=H,slot=slot,GPU=base['device_list'][slot%8],job=str(path),utc=utc(),process=process_identity(proc.pid),run_id=TASK+'_'+jid,no_automatic_retry=True))
                w['index']+=1;w['busy']=jid;w['assigned_at']=time.monotonic()
                new_json(wr/'inbox'/('%05d.json'%w['index']),dict(job=str(path),output=str(ROOT/'runs'/jid),claim=str(ROOT/'claims'/(jid+'.json'))))
            if H and all(processed(r[4]) for r in rows if r[0]==H) and not any(w['busy'] for w in workers.values()):
                new_json(ROOT/f'H{H}_DISPATCH_COMPLETE.json',dict(utc=utc(),H=H,status='all_assigned_jobs_terminal_or_failed',all_job_boundaries_drained=True,validity_requires_per_source_results=True))
                phase_index+=1
            now=time.monotonic()
            if now-lastbeat>=5:
                beat(H,status='draining' if stopping or H is None else 'running',living_workers=alive,loaded_workers=sum((w['root']/'MODEL_READY.json').exists() and w['proc'].poll() is None for w in workers.values()),started_workers=started_slots,active_jobs={str(k):w['busy'] for k,w in workers.items() if w['proc'].poll() is None},pending_jobs=len(pending(rows,H)) if H else 0)
                lastbeat=now
            if not alive:break
            time.sleep(.5)
    except BaseException as exc:
        fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        record_fault(ROOT,fatal,unit='evaluation_stage',evidence=[str(chain/'MANAGER_STARTED.json')],continuable=['next independent eligible C task'])
    finally:
        for proc in all_children.values():
            if proc.poll() is None:proc.send_signal(signal.SIGTERM)
        cleanup=drain_group(own['pgid'],own['pid'])
        for proc in all_children.values():proc.wait()
        new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,workers={k:p.returncode for k,p in all_children.items()},all_owned_processes_exited=cleanup.get('status')=='all_formal_group_members_exited',unclaimed_jobs=sum(not (ROOT/'claims'/(r[4]+'.json')).exists() for r in rows)))
    return 3 if fatal or any(p.returncode for p in all_children.values()) else 0

if __name__=='__main__':sys.exit(main())
