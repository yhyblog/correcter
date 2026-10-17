"""Finite 24 resident evaluators; original numerical worker, exact transferred jobs."""
import argparse,os,signal,subprocess,time,traceback
from pathlib import Path
import paths
from paths import ROOT,CONFIG
from qio import read,new_json,atomic_json,utc,process_identity
from reservation import send_existing_fd,holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group
from admission import authority,before_cutoff,admissions_allowed,validate_job,worker_environment

def main(chain):
 chain=Path(chain);authority();__import__('recovery_policy').consume(ROOT,'manager');own=process_identity();fds=held_reservation_fds()
 if own['pid']!=own['pgid'] or len(fds)!=1:raise RuntimeError('single original formal reservation/group required')
 request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
 new_json(chain/'MANAGER_STARTED.json',dict(process=own,utc=utc(),single_reservation=True))
 base=read(ROOT/'config/BASE.json');workers={};fatal=None;stopping=False;last=0;started=0
 def stop(*_):
  nonlocal stopping
  stopping=True
 for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,stop)
 jobs=[]
 for row in read(ROOT/'JOB_INDEX.json')['jobs']:
  j=read(row['path']);validate_job(j);jobs.append((j['chunk'],j['task_order'],j['method'],j['job_id'],Path(row['path']),j))
 jobs.sort()
 def pending():return [j for j in jobs if not (ROOT/'claims'/j[4].name).exists()]
 def launch_tranche():
  nonlocal started
  for slot in range(started,min(started+8,24)):
   wr=chain/'workers'/str(slot);wr.mkdir(parents=True,exist_ok=False)
   for name in ['inbox','done','tmp','cache','xdg']:(wr/name).mkdir(mode=0o700)
   argv=[base['python'],'-B',str(ROOT/'code/resident_worker.py'),'--slot',str(slot),'--root',str(wr),'--stage','EVAL']
   with (wr/'stdout.log').open('xb') as so,(wr/'stderr.log').open('xb') as se:
    proc=subprocess.Popen(argv,cwd=ROOT,env=worker_environment(base,wr),stdin=subprocess.DEVNULL,stdout=so,stderr=se,pass_fds=fds,start_new_session=False)
   workers[slot]=dict(proc=proc,root=wr,index=0,busy=None,started=time.monotonic(),assigned=None,term=None,exit_recorded=False)
  started=min(started+8,24)
 try:
  if not admissions_allowed():raise RuntimeError('admission closed before wave')
  launch_tranche()
  while True:
   if not admissions_allowed():stopping=True
   if not stopping and started<24 and all((w['root']/'MODEL_READY.json').exists() for w in workers.values()):launch_tranche()
   todo=pending() if not stopping else [];alive=0
   for slot,w in workers.items():
    proc,wr=w['proc'],w['root']
    if proc.poll() is not None:
     if not w['exit_recorded']:
      new_json(wr/'PROCESS_EXIT.json',dict(exit_code=proc.returncode,job=w['busy'],utc=utc()));w['exit_recorded']=True
      if w['busy'] and not (ROOT/'runs'/w['busy']/'RESULT.json').exists():new_json(ROOT/'failures'/(w['busy']+'.json'),dict(status='execution_unknown',success=None,worker=str(wr),utc=utc()))
      if proc.returncode and not (wr/'MODEL_READY.json').exists():raise RuntimeError('model loading failed; no blind retry '+str(wr))
     continue
    alive+=1
    timeout=(not (wr/'MODEL_READY.json').exists() and time.monotonic()-w['started']>1200) or (w['busy'] and time.monotonic()-w['assigned']>9200)
    if timeout or not before_cutoff():
     if w['term'] is None:proc.send_signal(signal.SIGTERM);w['term']=time.monotonic()
     elif time.monotonic()-w['term']>30:proc.kill()
     continue
    if w['busy'] and (wr/'done'/('%05d.json'%w['index'])).exists():w['busy']=None;w['assigned']=None
    if stopping or (not todo and not pending()):
     if not (wr/'STOP.json').exists():new_json(wr/'STOP.json',dict(reason='finite queue drained',utc=utc()))
     continue
    if w['busy'] or not (wr/'MODEL_READY.json').exists():continue
    if todo:
     _,_,_,jid,jpath,j=todo.pop(0)
     if not admissions_allowed():continue
     new_json(ROOT/'claims'/jpath.name,dict(job_id=jid,slot=slot,job=str(jpath),process=process_identity(proc.pid),utc=utc(),owner='B',automatic_retry=False))
     w['index']+=1;w['busy']=jid;w['assigned']=time.monotonic()
     new_json(wr/'inbox'/('%05d.json'%w['index']),dict(job=str(jpath),output=str(ROOT/'runs'/jid),claim=str(ROOT/'claims'/jpath.name)))
   if time.monotonic()-last>=5:
    atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),manager=own,status='draining' if stopping else 'running',H=CONFIG['H'],living_workers=alive,loaded_workers=sum(w['proc'].poll() is None and (w['root']/'MODEL_READY.json').exists() for w in workers.values()),target_workers=24,workers_per_gpu=3,started_workers=started,pending_jobs=len(pending()),active_jobs={str(k):w['busy'] for k,w in workers.items()},holders='all8off_entire_family'))
    last=time.monotonic()
   if not alive:break
   time.sleep(.5)
 except BaseException as exc:fatal=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
 finally:
  cleanup=drain_group(own['pgid'],own['pid'])
  for w in workers.values():w['proc'].wait()
  new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,all_owned_processes_exited=cleanup.get('status')=='all_formal_group_members_exited'))
 return 3 if fatal else 0
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--chain',required=True);raise SystemExit(main(p.parse_args().chain))
