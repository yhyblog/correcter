"""Complete-Q training then 24 resident evaluators under one original reservation."""
import argparse,os,signal,subprocess,sys,time,traceback
from pathlib import Path
import paths
from paths import ROOT,ORIGINAL,TASK
from qio import read,new_json,atomic_json,utc,process_identity
from reservation import send_existing_fd,holder_exit_ack
from wave_timing import held_reservation_fds
from process_family import drain_group
from admission import authority,before_cutoff,admissions_allowed,validate_job,worker_environment
from publication import publish
from publication_data import load_evidence,identity
from selection import make_selection
from transfer import publish_transfer,original_exit_verified

_JOBS=None
def job_rows():
 global _JOBS
 if _JOBS is None:
  _JOBS=[]
  for row in read(ROOT/'JOB_INDEX.json')['jobs']:
   path=Path(row['path']);job=read(path);validate_job(job,stage_gate=False);_JOBS.append((job['priority'],job['chunk'],job['task_order'],job['job_id'],path,job))
  _JOBS.sort()
 return _JOBS

def processed(jid):return (ROOT/'runs'/jid/'RESULT.json').exists() or (ROOT/'failures'/(jid+'.json')).exists()
def pending_jobs(stage):
 rows=[r for r in job_rows() if r[5]['stage']==stage and not processed(r[3])]
 if not rows:return []
 priority=min(r[0] for r in rows)
 return [r for r in rows if r[0]==priority and not (ROOT/'claims'/r[4].name).exists()]
def stage_done(stage):return all(processed(r[3]) for r in job_rows() if r[5]['stage']==stage)

def summarize(chain):
 jobs,attempts,claims,selected=load_evidence();cells={}
 for cell in read(ROOT/'config/CONFIG.json')['cells']:
  key=cell['cell_id'];unique=[x for x in selected if x['cell_id']==key];valid=[x for x in unique if x['status']=='complete'];admitted=[x for x in claims if x['cell_id']==key]
  cells[key]=dict(attempts=len(admitted),terminals=len(valid),successes=sum(x['success'] is True for x in valid),technical_failures=sum(x['status']=='technical_failure' for x in unique),user_cancelled=sum(x['status']=='user_cancelled' for x in unique),planned_episodes=cell['planned_episodes'],full_cell_complete=len(valid)==cell['planned_episodes'],unstarted=cell['planned_episodes']-len(admitted))
 result=dict(utc=utc(),cells=cells,actual_completed_job_count=len(jobs),valid=sum(x['terminals'] for x in cells.values()),actual_attempts=len(claims),local_new_attempts=len(claims)-1546,prior_D24_attempts=14896,A_cumulative_attempts=14896+len(claims),original_preserved_DEV=1546,new_training_updates=0,compute_complete=all(x['full_cell_complete'] for x in cells.values()),source_count_is_per_cell=True)
 atomic_json(ROOT/'SUMMARY.json',result)
 for key,cell in cells.items():
  if not cell['full_cell_complete']:continue
  state=publish(key);event=ROOT/'outbox'/(key+'.json')
  if key.startswith(('MAIN_','ONCE_')) and state['status']=='published' and not event.exists():new_json(event,dict(event_id=TASK+'_'+key,kind='cell_terminal',synthetic=False,publication=state['publication'],chain=str(chain),utc=utc()))
 return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--chain',required=True);a=parser.parse_args();chain=Path(a.chain)
 authority();own=process_identity();fds=held_reservation_fds()
 if own['pid']!=own['pgid'] or len(fds)!=1:raise RuntimeError('single original reservation/group required')
 request=read(chain/'REQUEST.json');send_existing_fd(request['socket'],fds[0]);new_json(chain/'HOLDER_EXIT_ACK.json',holder_exit_ack(request))
 new_json(chain/'MANAGER_STARTED.json',dict(process=own,utc=utc(),single_reservation=True))
 base=read(ROOT/'config/BASE.json');all_children={};workers={};stopping=False;fatal=None
 def stop(*_):
  nonlocal stopping
  stopping=True
 for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,stop)
 def spawn(argv,dest,env,label):
  dest.mkdir(parents=True,exist_ok=True)
  with (dest/'stdout.log').open('xb') as so,(dest/'stderr.log').open('xb') as se:
   proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=so,stderr=se,env=env,cwd=ROOT,pass_fds=fds,start_new_session=False)
  all_children[label]=proc;return proc
 def beat(stage,**extra):atomic_json(chain/'HEARTBEAT.json',dict(utc=utc(),manager=own,stage=stage,holder_policy='all8_off_entire_wave',**extra))
 try:
  if any(j[5]['stage']=='MAIN' and j[5]['H']!=10 for j in job_rows()):raise ValueError('remote H in local cache')
  if not admissions_allowed():raise RuntimeError('new task not currently admitted')
  original_exit_verified()
  trained=read(ORIGINAL/'TRAINING_COMPLETE.json')
  if trained['fits']!=48 or trained['training_updates']!=192000:raise ValueError('original completed Q training required')
  new_json(chain/'TRAINING_REUSED.json',dict(utc=utc(),source=str(ORIGINAL/'TRAINING_COMPLETE.json'),fits=48,previous_updates=192000,new_updates=0,all_original_weights_read_only=True))
  # The 24 resident policy processes are shared across dev/selection/test cells.
  phase=chain/'phases/EVAL';phase.mkdir(parents=True,exist_ok=False);lastbeat=lastsummary=0;stage_index=0;stages=['DEV','ABLATION','MAIN','ONCE'];started_slots=0
  def launch_tranche():
   nonlocal started_slots
   for slot in range(started_slots,min(started_slots+8,24)):
    wr=phase/'workers'/str(slot);wr.mkdir(parents=True,exist_ok=False)
    for name in ('inbox','done','tmp','cache','xdg'):(wr/name).mkdir(mode=0o700)
    argv=[base['python'],'-B',str(ROOT/'code/resident_worker.py'),'--slot',str(slot),'--root',str(wr),'--stage','EVAL']
    proc=spawn(argv,wr,worker_environment(base,wr),f'eval_{slot}')
    workers[slot]=dict(proc=proc,root=wr,index=0,busy=None,start=time.monotonic(),assigned_at=None,exit_recorded=False,term_at=None)
   started_slots=min(started_slots+8,24)
  launch_tranche()
  while True:
   if not admissions_allowed() and not stopping:
    stopping=True
    if not (ROOT/'DRAIN.json').exists():new_json(ROOT/'DRAIN.json',dict(reason='live authorization/cutoff no longer admits new episodes',utc=utc()))
   stage=stages[stage_index] if stage_index<len(stages) else None
   if not stopping and started_slots<24 and all((w['root']/'MODEL_READY.json').exists() for w in workers.values()):launch_tranche()
   if stage and stage_done(stage):
    summary=summarize(chain)
    new_json(chain/(stage+'_STAGE_COMPLETE.json'),dict(utc=utc(),stage=stage,cells={k:v for k,v in summary['cells'].items() if k.startswith(stage+'_')}))
    if stage=='DEV':
     try:
      make_selection();publish_transfer()
     except ValueError as error:
      new_json(ROOT/'SELECTION_BLOCKED.json',dict(utc=utc(),reason=str(error),no_test_launched=True))
      new_json(ROOT/'outbox/selection_blocked.json',dict(event_id=TASK+'_selection_blocked',synthetic=False,kind='selection_blocked',result=str(ROOT/'SELECTION_BLOCKED.json'),utc=utc()))
      stopping=True
    stage_index+=1;stage=stages[stage_index] if stage_index<len(stages) else None
   pending=pending_jobs(stage) if stage and not stopping else [];alive=0
   for slot,w in workers.items():
    proc,wr=w['proc'],w['root']
    if proc.poll() is not None:
     if not w['exit_recorded']:
      new_json(wr/'PROCESS_EXIT.json',dict(exit_code=proc.returncode,utc=utc(),job=w['busy']));w['exit_recorded']=True
      if w['busy'] and not (ROOT/'runs'/w['busy']/'RESULT.json').exists():new_json(ROOT/'failures'/(w['busy']+'.json'),dict(job_id=w['busy'],status='worker_exit_without_complete_job',exit_code=proc.returncode,worker=str(wr),success=None,utc=utc()))
      if proc.returncode:
       new_json(ROOT/'outbox'/f'worker_{slot}.json',dict(event_id=TASK+f'_worker_{slot}_failure',kind='worker_failure',synthetic=False,worker=str(wr),utc=utc()))
       terminal=read(wr/'WORKER_EXIT.json') if (wr/'WORKER_EXIT.json').exists() else {}
       message=(terminal.get('fatal') or {}).get('message','')
       if terminal.get('cleanup') or not message.startswith('worker stops after job/episode technical failure:'):raise RuntimeError('model/identity/cleanup worker failure: '+str(wr))
     continue
    alive+=1
    timed_out=(not (wr/'MODEL_READY.json').exists() and time.monotonic()-w['start']>1200) or (w['busy'] and time.monotonic()-w['assigned_at']>9200)
    if timed_out or not before_cutoff():
     if w['term_at'] is None:proc.send_signal(signal.SIGTERM);w['term_at']=time.monotonic()
     elif time.monotonic()-w['term_at']>30:proc.kill()
     continue
    if w['busy'] and (wr/'done'/('%05d.json'%w['index'])).exists():w['busy']=None;w['assigned_at']=None
    if stopping or stage is None:
     if not (wr/'STOP.json').exists():new_json(wr/'STOP.json',dict(reason='queue drained or graceful admission stop',utc=utc()))
     continue
    if not (wr/'MODEL_READY.json').exists() or w['busy']:continue
    if pending:
     if not admissions_allowed():continue
     _,_,_,jid,path,job=pending.pop(0);validate_job(job)
     new_json(ROOT/'claims'/path.name,dict(job_id=jid,cell_id=job['cell_id'],stage=stage,slot=slot,GPU=base['device_list'][slot%8],job=str(path),utc=utc(),process=process_identity(proc.pid),run_id=TASK+'_'+jid,no_automatic_retry=True))
     w['index']+=1;w['busy']=jid;w['assigned_at']=time.monotonic()
     new_json(wr/'inbox'/('%05d.json'%w['index']),dict(job=str(path),output=str(ROOT/'runs'/jid),claim=str(ROOT/'claims'/path.name)))
   now=time.monotonic()
   if now-lastbeat>=5:
    beat(stage or 'DRAIN',status='draining' if stopping or stage is None else 'running',living_workers=alive,loaded_workers=sum((w['root']/'MODEL_READY.json').exists() and w['proc'].poll() is None for w in workers.values()),started_workers=started_slots,active_jobs={str(k):w['busy'] for k,w in workers.items() if w['proc'].poll() is None},pending_jobs=len(pending_jobs(stage)) if stage else 0)
    lastbeat=now
   if now-lastsummary>=300:summarize(chain);lastsummary=now
   if not alive:break
   time.sleep(.5)
 except BaseException as error:fatal=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
 finally:
  for proc in all_children.values():
   if proc.poll() is None:proc.send_signal(signal.SIGTERM)
  cleanup=drain_group(own['pgid'],own['pid'])
  for proc in all_children.values():proc.wait()
  try:summary=summarize(chain);atomic_json(ROOT/'COMPUTE_SUMMARY.json',summary)
  except BaseException as error:
   if fatal is None:fatal=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc())
   summary=read(ROOT/'SUMMARY.json') if (ROOT/'SUMMARY.json').exists() else None
  new_json(chain/'MANAGER_EXIT.json',dict(utc=utc(),fatal=fatal,cleanup=cleanup,summary=summary,workers={k:p.returncode for k,p in all_children.items()},all_owned_processes_exited=cleanup.get('status')=='all_formal_group_members_exited'))
 return 3 if fatal or any(p.returncode for p in all_children.values()) else 0

if __name__=='__main__':sys.exit(main())
