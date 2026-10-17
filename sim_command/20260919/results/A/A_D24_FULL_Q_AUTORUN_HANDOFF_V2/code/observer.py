"""One finite host-scoped stage observer; one continuation command, no retries."""
import argparse,fcntl,os,signal,subprocess,sys,time,traceback
from pathlib import Path
from paths import ROOT,ORIGINAL,TASK,AUTH_SHA
from qio import read,new_json,atomic_json,utc,process_identity,same_process,ref
from admission import authority,admissions_allowed
from transfer import original_exit_verified

def stage_snapshot():
 p=ROOT/'chain/HEARTBEAT.json';h=read(p) if p.exists() else {}
 return dict(stage=h.get('stage','NOT_ENTERED'),started_workers=h.get('started_workers',0),loaded_workers=h.get('loaded_workers',0),living_workers=h.get('living_workers',0),active_jobs=h.get('active_jobs',{}),selection_locked=(ORIGINAL/'SELECTION_LOCK.json').is_file(),transfer_ready=(ROOT/'TRANSFER_READY.json').is_file(),science_terminal=(ROOT/'RESULT.json').is_file())

def serve():
 local=Path('/tmp/corrector_D24_A_full_Q_autorun_observer_v2');local.mkdir(exist_ok=True)
 lock=(local/'observer.lock').open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:return 0
 authority();own=process_identity();end=min(time.time()+43200,read(ORIGINAL/'RUN_TIME_BUDGET.json')['absolute_end_unix'],1790164800)
 if time.time()>=end:raise RuntimeError('original finite stage deadline already expired')
 if (ROOT/'QUEUE_COMMAND.json').exists():raise RuntimeError('existing observer command must not replay')
 new_json(ROOT/'QUEUE_COMMAND.json',dict(task_id=TASK,process=own,utc=utc(),absolute_end_unix=end,one_continuation_only=True))
 original_exit_verified()
 new_json(ROOT/'QUEUE_READY.json',dict(task_id=TASK,status='OBSERVER_DEPLOYED',process=own,host=own['host'],utc=utc(),authorization_sha256=AUTH_SHA,original_manager_already_exited=True,prior_DEV_preserved=1546,unentered_DEV=854,worker_target=24,stdin='DEVNULL',independent_of_Codex_window=True,absolute_end_unix=end,ordered_stages=ref(ROOT/'ORDERED_STAGES.json'),code=ref(ROOT/'CODE_MANIFEST.json'),callback_thread='01a0b91f-7443-71b1-915d-6cdb6d6a1a13',ready_does_not_mean_model_ready=True))
 if not admissions_allowed():raise RuntimeError('current V2 grant does not admit continuation')
 new_json(ROOT/'CONTINUATION_LAUNCH_INTENT.json',dict(utc=utc(),argv=['/usr/bin/python','-B',str(ROOT/'code/service.py'),'start'],unique_opportunity=True))
 launch=subprocess.run(['/usr/bin/python','-B',str(ROOT/'code/service.py'),'start'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
 new_json(ROOT/'CONTINUATION_LAUNCH_RESULT.json',dict(utc=utc(),exit_code=launch.returncode,stdout=launch.stdout,stderr=launch.stderr,not_model_readiness=True))
 if launch.returncode:raise RuntimeError('continuation command failed; no automatic relaunch')
 seen_stable=False;lastmerge=0;oldsignature=None;seen_terminal=False;stop=False
 def signal_stop(*_):
  nonlocal stop
  stop=True
 for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,signal_stop)
 while not stop and time.time()<end:
  snapshot=stage_snapshot();daemon=read(ROOT/'DAEMON_READY.json') if (ROOT/'DAEMON_READY.json').exists() else None
  daemon_alive=bool(daemon and same_process(daemon['process']))
  count=read(ROOT/'ATTEMPT_COUNTER.json')['count'] if (ROOT/'ATTEMPT_COUNTER.json').exists() else 0
  atomic_json(ROOT/'QUEUE_HEARTBEAT.json',dict(utc=utc(),observer=own,daemon=daemon['process'] if daemon else None,daemon_alive=daemon_alive,absolute_end_unix=end,local_new_attempts=count,**snapshot))
  if not seen_stable and snapshot['loaded_workers']>0 and count>0:
   stable=dict(utc=utc(),status='RUNNING_STABLE_HANDOFF',task_id=TASK,observer=own,daemon=daemon['process'],actual_snapshot=snapshot,local_new_attempts=count,original_valid_DEV_preserved=1546,selection_before_test=True,unclaimed_remote_H_only=True,holder_policy='all8_off_whole_formal_family',bounded_end_unix=end,terminal_event_registered=True,callback_thread='01a0b91f-7443-71b1-915d-6cdb6d6a1a13')
   new_json(ROOT/'STABLE_HANDOFF.json',stable);seen_stable=True
   new_json(ROOT/'outbox/startup_progress.json',dict(event_id=TASK+'_startup_progress',synthetic=False,kind='stable_startup',result=str(ROOT/'STABLE_HANDOFF.json'),utc=utc()))
  if snapshot['science_terminal'] and not seen_terminal:
   final=read(ROOT/'RESULT.json');seen_terminal=True
   new_json(ROOT/'SCIENCE_CHAIN_OBSERVED.json',dict(utc=utc(),result=ref(ROOT/'RESULT.json'),all_owned_descendants_exited=final['all_owned_descendants_exited'],next_step='CPU incremental remote tables only',no_new_scientific_launch=True))
  if not daemon_alive and not snapshot['science_terminal'] and daemon:
   raise RuntimeError('daemon disappeared before terminal; no implicit retry')
  # Derived tables are a separate bounded CPU process. No scientific barrier.
  if time.time()-lastmerge>=60:
   candidates=[ROOT/'MAIN_CELLS.csv']+[ROOT.parents[1]/node/task/'FINAL_CELLS.csv' for node,task in [('B','B_D24_PI05_SELECTED_H20_H30_V1'),('C','C_D24_PI05_SELECTED_H40_H50_V1')]]
   sig=[]
   for p in candidates:
    if p.exists():st=p.stat();sig.append((str(p),st.st_size,st.st_mtime_ns))
   if sig!=oldsignature or snapshot['selection_locked'] and oldsignature is None:
    base=read(ROOT/'config/BASE.json')
    try:
     run=subprocess.run([base['python'],'-B',str(ROOT/'code/merge_remote.py')],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=180)
     atomic_json(ROOT/'MERGE_LAST_RUN.json',dict(utc=utc(),exit_code=run.returncode,stdout=run.stdout[-2000:],stderr=run.stderr[-4000:],scientific_compute=0))
    except Exception as e:atomic_json(ROOT/'MERGE_LAST_RUN.json',dict(utc=utc(),publication_error=str(e),scientific_compute=0))
    oldsignature=sig
   lastmerge=time.time()
  if not daemon_alive:
   from notify import pump
   pump()
  if seen_terminal and (ROOT/'aggregate/STATUS.json').exists():
   aggregate=read(ROOT/'aggregate/STATUS.json')
   if aggregate['known_cells']==10 and not aggregate['rejected']:break
  time.sleep(5)
 new_json(ROOT/'QUEUE_EXIT.json',dict(utc=utc(),observer=own,science_terminal_seen=seen_terminal,reason='observer_stop' if stop else 'complete_or_original_finite_deadline',no_new_launches=True,scientific_compute=0))
 return 0

def start():
 authority();ready=ROOT/'QUEUE_READY.json'
 if ready.exists() and same_process(read(ready)['process']):print('EXISTING_OBSERVER',read(ready)['process']);return 0
 if (ROOT/'QUEUE_COMMAND.json').exists():raise RuntimeError('previous observer opportunity exists; reconcile instead of duplicating')
 with (ROOT/'observer.stdout.log').open('ab') as so,(ROOT/'observer.stderr.log').open('ab') as se:
  p=subprocess.Popen(['/usr/bin/python','-B',str(ROOT/'code/observer.py'),'serve'],cwd=ROOT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True)
 print('OBSERVER_SPAWNED_NOT_READY',p.pid);return 0

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);a=p.parse_args()
 try:sys.exit(start() if a.action=='start' else serve())
 except Exception as e:
  error=dict(utc=utc(),type=type(e).__name__,message=str(e),traceback=traceback.format_exc(),scientific_relaunch=False)
  atomic_json(ROOT/'OBSERVER_ERROR.json',error)
  if not (ROOT/'outbox/observer_failure.json').exists():new_json(ROOT/'outbox/observer_failure.json',dict(event_id=TASK+'_observer_failure',synthetic=False,kind='failure',result=str(ROOT/'OBSERVER_ERROR.json'),utc=utc()))
  raise
