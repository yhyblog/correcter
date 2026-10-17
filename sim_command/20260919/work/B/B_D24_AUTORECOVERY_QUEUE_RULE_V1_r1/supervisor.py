"""Finite CPU issue timer and scans alongside the original unique scientific queues."""
import argparse,fcntl,os,signal,subprocess,time,traceback,sys
from pathlib import Path
from recovery_policy import CONTROL_ROOT as ROOT,C,ISSUES,OUTBOX,THREAD,consume,issue,repair_gate
from qio import read,new_json,atomic_json,ref,utc,process_identity,same_process
P=C/'results/B/B_D24_PI05_SELECTED_H20_H30_V1'
F=C/'results/B/B_D24_FULL_Q_LOSS_REFRESH_V1'
WAKE=C/'work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py'
TASK='B_D24_AUTORECOVERY_QUEUE_RULE_V1';RUN='D24_B_AUTORECOVERY_r1'
sys.path.insert(0,str(P/'code'))
import gates

def snapshot(path):return read(path) if path.is_file() else {}
def scan():
 selector=C/'results/A/A_D24_FULL_Q_LOSS_SELECTION_V1/SELECTION_LOCK.json'
 transfer=C/'results/A/A_D24_FULL_Q_AUTORUN_HANDOFF_V2/TRANSFER_READY.json'
 roots=[F/'evaluation_r1',P/'R_cancelled_r3',P/'H20_r1',P/'H30_r1'];rows=[]
 try:gates.selection();selection_ready=True
 except (FileNotFoundError,ValueError,KeyError):selection_ready=False
 for i,r in enumerate(roots):
  blockers=[]
  if not selection_ready:blockers.append('Post-only scientific selection pending')
  if i>=2 and not (P/'TRANSFER_SNAPSHOT.json').is_file():blockers.append('exact A ownership transfer not yet consumed by unique queue')
  predecessor=(F if i==1 else roots[i-1] if i>1 else None)
  if predecessor and not snapshot(predecessor/'RESULT.json').get('all_owned_descendants_exited'):blockers.append('own predecessor family terminal pending')
  result=snapshot(r/'RESULT.json');claim=snapshot(r/'CLAIM.json')
  if result:state='terminal'
  elif claim:state='admitted_owned_family'
  else:state='waiting' if blockers else 'eligible_for_existing_unique_queue'
  rows.append(dict(root=str(r),state=state,blockers=blockers,terminal_status=result.get('status')))
 if all(r['state'] in ['waiting','terminal'] for r in rows):
  atomic_json(ROOT/'NO_RUNNABLE_TASKS.json',dict(utc=utc(),status='NO_RUNNABLE_TASKS',rows=rows,no_unplanned_GPU_work=True))
 atomic_json(ROOT/'SCAN.json',dict(utc=utc(),rows=rows,launch_owner='existing native and successor queue only',no_duplicate_launch=True))
 return rows

def timers():
 for path in ISSUES.glob('B_recovery_*.json'):
  if path.name.endswith('_DECISION.json'):continue
  row=read(path);decision=Path(row['response_path']);d=snapshot(decision)
  actionable=d.get('status') in ['released','actionable'] and bool(d.get('action')) and bool(d.get('evidence') or d.get('authorization'))
  if actionable and row['status']!='actionable_decision_available':
   row.update(status='actionable_decision_available',decision=ref(decision),decision_at=utc());atomic_json(path,row)
  elif not actionable and row['status']=='reported' and time.time()>=row['analysis_response_due_unix']:
   row.update(status='blocked_deferred',deferred_at=utc(),next_action='existing scheduler continues only independent eligible units; scientific dependencies remain mandatory');atomic_json(path,row)

def deliver_once():
 for path in OUTBOX.glob('B_recovery_*.json'):
  delivered=ROOT/'transport'/(path.stem+'.json')
  if delivered.exists():continue
  event=read(path);record=dict(utc=utc(),target_thread=THREAD,event=str(path),attempts=1,handler_ACK=False)
  # Persist before transport. No retries or recursive callbacks to analysis.
  new_json(delivered,dict(record,status='attempt_entered'))
  try:
   result=subprocess.run(['codex','queue','--thread',THREAD,'--message',event['message']],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30,cwd=C.parents[2])
   record.update(status='transport_accepted_not_handler_ACK' if result.returncode==0 else 'transport_failed',exit_code=result.returncode,stdout=result.stdout[-2000:],stderr=result.stderr[-2000:])
  except BaseException as e:record.update(status='transport_failed',error=str(e))
  atomic_json(delivered,record)

def report_repairs():
 # Only one well-scoped automatic correction is implemented: recover an
 # interrupted report after shared-file availability is restored. Science is read only.
 for stage in [F/'evaluation_r1',P/'R_cancelled_r3',P/'H20_r1',P/'H30_r1']:
  result=snapshot(stage/'RESULT.json');error=result.get('publication_error')
  if not error or not result.get('all_owned_descendants_exited'):continue
  marker=ROOT/'repairs'/(stage.name+'.json')
  if marker.exists():continue
  row=issue(stage,error,evidence=[str(stage/'RESULT.json')],continuable=['next independent authorized stage'])
  text=str(error).lower()
  if not any(x in text for x in ['stale file','input/output','filenotfounderror','jsondecodeerror']):
   new_json(marker,dict(status='needs_specific_private_fix',issue_id=row['issue_id'],science_relaunch=False,utc=utc()));continue
  # Actual source availability is the observed correction; no identical science retry.
  required=[stage/'SOURCE_INDEX.json',stage/'config/CONFIG.json',stage/'chain/CHAIN_RESULT.json']
  if not all(p.is_file() for p in required):continue
  for path in required:read(path)
  fix=dict(change='shared JSON prerequisites now readable after recorded transient I/O failure',evidence=[ref(p) for p in required],science_changed=False)
  repair_gate(ISSUES/(row['issue_id']+'.json'),fix,[],{},0)
  new_json(marker,dict(status='CPU_publication_retry_entered',issue_id=row['issue_id'],fix=fix,science_relaunch=False,utc=utc()))
  base=read(stage/'config/BASE.json')
  proc=subprocess.run([base['python'],'-B',str(stage/'code/publish.py')],cwd=stage,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=600)
  atomic_json(marker,dict(status='CPU_publication_recovered' if proc.returncode==0 else 'CPU_publication_still_failed',exit_code=proc.returncode,stdout=proc.stdout[-3000:],stderr=proc.stderr[-3000:],issue_id=row['issue_id'],old_RESULT_preserved=True,science_relaunch=False,utc=utc()))

def serve():
 local=Path('/tmp/corrector_B_autorecovery_r1');local.mkdir(exist_ok=True);lock=(local/'lock').open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:return 0
 consume(ROOT,'supervisor');own=process_identity();identity=dict(hostname=own['host'],boot_id=own['boot_id'],pid=own['pid'],start_ticks=own['start_ticks'],session_id=os.getsid(0))
 new_json(ROOT/'CLAIM.json',dict(task_id=TASK,run_id=RUN,process=identity,utc=utc(),CPU_only=True))
 manifest=dict(job_id=RUN,task_id=TASK,revision=1,run_id=RUN,attempt=1,claim_identity=ref(ROOT/'CLAIM.json'),process_identity=identity,result_path=str(ROOT/'RESULT.json'),error_summary_path=str(ROOT/'stderr.log'))
 new_json(ROOT/'WAKEUP_REGISTRATION.json',manifest)
 subprocess.run(['/usr/bin/python',str(WAKE),'register','--manifest',str(ROOT/'WAKEUP_REGISTRATION.json')],check=True)
 end=read(P/'CONFIG.json')['deadline_unix'];stop=False
 def halt(*_):
  nonlocal stop
  stop=True
 for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,halt)
 new_json(ROOT/'READY.json',dict(utc=utc(),process=own,finite_end_unix=end,CPU_only=True,scientific_launches=0,terminal_trigger=ref(ROOT/'WAKEUP_REGISTRATION.json')))
 try:
  while not stop and time.time()<end:
   rows=scan();timers();report_repairs();deliver_once()
   native=snapshot(F/'QUEUE_HEARTBEAT.json');successor=snapshot(P/'QUEUE_HEARTBEAT.json')
   reason=successor.get('dependency_status','')
   if reason and 'pending' not in reason and 'not fully exited' not in reason:
    issue(P,reason,kind='scientific_or_ownership_decision',evidence=[str(P/'QUEUE_HEARTBEAT.json')],continuable=['existing healthy native queue and authorized CPU preparation'])
   atomic_json(ROOT/'HEARTBEAT.json',dict(utc=utc(),process=own,status='monitoring',scan=rows,issue_count=len(list(ISSUES.glob('B_recovery_*.json'))),native_phase=native.get('phase'),successor_phase=successor.get('phase'),finite_end_unix=end))
   if (P/'RESULT.json').exists():break
   time.sleep(15)
  result=dict(status='complete',utc=utc(),task_id=TASK,run_id=RUN,CPU_only=True,all_owned_descendants_exited=True,occupancy_handoff_complete=True,scientific_launches=0)
 except BaseException as error:result=dict(status='failed',error=repr(error),traceback=traceback.format_exc(),utc=utc(),all_owned_descendants_exited=True,occupancy_handoff_complete=True)
 new_json(ROOT/'RESULT.json',result)
 return 0 if result['status']=='complete' else 3

def start():
 if (ROOT/'CLAIM.json').exists():print('EXISTING_CLAIM_NO_DUPLICATE');return 0
 ROOT.mkdir(parents=True,exist_ok=True)
 with (ROOT/'stdout.log').open('ab') as so,(ROOT/'stderr.log').open('ab') as se:
  p=subprocess.Popen(['/usr/bin/python','-B',str(Path(__file__)),'serve'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
 print('SPAWNED_NOT_YET_READY',p.pid);return 0
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('action',choices=['start','serve']);o=a.parse_args();raise SystemExit(start() if o.action=='start' else serve())
