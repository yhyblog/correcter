"""Finite host-scoped successor. Does not launch/restart the existing native queue."""
import argparse,fcntl,os,signal,subprocess,time,traceback
from pathlib import Path
from qio import read,new_json,atomic_json,utc,process_identity,same_process,ref,optional_snapshot
import gates
P=gates.P;C=gates.C;CFG=read(P/'CONFIG.json');F=Path(CFG['predecessor_root']);WAKE=C/'work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py'

def normalized(p):return dict(p,host=p.get('host',p.get('hostname')))
def terminal_claim(root):
 for name in ['CLAIM.json','QUEUE_CLAIM.json']:
  if (root/name).exists():return normalized(read(root/name)['process'])
 return None
def current_attempts(root):
 if (root/'ATTEMPT_COUNTER.json').exists():
  x=read(root/'ATTEMPT_COUNTER.json');return x.get('count',x.get('reserved_attempts',0))
 return 0
def cumulative_prior():
 # Historical 15598 includes the original 28 R admissions and the 472 continuation.
 return 15598+current_attempts(F/'evaluation_r1')+sum(current_attempts(P/n) for n in ['R_cancelled_r3','H20_r1','H30_r1'])

def prepare_wave(root,predecessor,choice,transfer=None):
 assert not (root/'CLAIM.json').exists() and not (root/'CHAIN_COMMAND.json').exists()
 cfg=read(root/'config/CONFIG.json');cfg.update(activation_finalized=True,predecessor_root=str(predecessor),
  planned_prior_attempts=cumulative_prior(),absolute_wall_deadline_unix=min(time.time()+43200,CFG['deadline_unix'],1790164800),
  selected_loss=choice['chosen_loss'],selected_fit_seed=9101,selection_sha256=ref(gates.A/'SELECTION.json')['sha256'],activation_utc=utc())
 if transfer is not None:
  selected=[j for j in transfer['nodes']['B']['jobs'] if j['H']==cfg['H']];jobs=[]
  for row in selected:
   original=read(row['path']);job=dict(original,sources=row['sources'],transfer_owner='B')
   path=root/'jobs'/(job['job_id']+'.json');new_json(path,job);jobs.append(dict(job_id=job['job_id'],**ref(path)))
  cfg['planned_current']=sum(len(j['sources']) for j in selected)
  new_json(root/'JOB_INDEX.json',dict(jobs=jobs,selection=ref(gates.A/'SELECTION.json'),transfer=ref(Path(CFG['transfer_ready']))))
  new_json(root/'TRANSFER_SNAPSHOT.json',transfer)
 if cfg['planned_prior_attempts']+cfg['planned_current']>22000:raise ValueError('remaining node capacity insufficient')
 atomic_json(root/'config/CONFIG.json',cfg)
 new_json(root/'CODE_MANIFEST.json',dict(utc=utc(),files=[ref(p) for p in sorted((root/'code').glob('*.py'))]+[ref(p) for p in sorted((root/'config').glob('*.json'))]))
 return cfg

def publish_chain(stages,status,phase,error=None):
 result=dict(status=status,phase=phase,at_utc=utc(),task_id=CFG['task_id'],run_id=CFG['run_id'],stages=stages,
  all_owned_descendants_exited=all(v.get('family_exited',True) for v in stages),
  occupancy_handoff_complete=all(v.get('family_exited',True) for v in stages),
  cumulative_B_attempts=cumulative_prior(),error=error,new_training_updates=0,new_collection=0,
  original_native_queue=str(F),original_native_queue_was_not_relaunched=True,A_waits_for_B=False)
 atomic_json(P/'RESULT.json',result);atomic_json(C/f"receipts/B/{CFG['task_id']}_RESULT_r1.json",result)
 rows=[]
 for name in ['H20_r1','H30_r1']:
  path=P/name/'FINAL_SUMMARY.json'
  if path.exists():rows.extend(read(path)['cells'])
 atomic_json(P/'FINAL_CELLS.json',dict(cells=rows,Post_primary=True,Velocity_current_paper=False,missing_not_failure=True))
 (P/'MASTER_UPDATE.md').write_text('B selected-Q successor: '+status+'\nPost is current-paper primary; Velocity separately retained.\n'+''.join(f"H{r['H']} {r['method']}: {r['successes']}/{r['valid']} valid; {r['missing']} missing.\n" for r in rows))
 return result

def serve():
 local=Path(CFG['local_dir']);local.mkdir(exist_ok=True);lock=(local/'queue.lock').open('a')
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:return 0
 gates.authority();own=process_identity();identity=dict(hostname=own['host'],boot_id=own['boot_id'],pid=own['pid'],start_ticks=own['start_ticks'],session_id=os.getsid(0))
 new_json(P/'QUEUE_CLAIM.json',dict(task_id=CFG['task_id'],run_id=CFG['run_id'],process=identity,authority=ref(C/CFG['grant']),at_utc=utc()))
 manifest=dict(job_id=CFG['run_id'],task_id=CFG['task_id'],revision=1,run_id=CFG['run_id'],attempt=1,claim_identity=ref(P/'QUEUE_CLAIM.json'),process_identity=identity,result_path=str(P/'RESULT.json'),error_summary_path=str(P/'queue.stderr.log'))
 new_json(P/'WAKEUP_REGISTRATION.json',manifest)
 subprocess.run(['/usr/bin/python',str(WAKE),'register','--manifest',str(P/'WAKEUP_REGISTRATION.json')],check=True)
 new_json(P/'QUEUE_READY.json',dict(status='ready',process=own,utc=utc(),terminal_trigger=ref(P/'WAKEUP_REGISTRATION.json'),ordered_stages=ref(P/'ORDERED_STAGES.json'),original_native_waiter=ref(F/'QUEUE_CLAIM.json'),finite_deadline_unix=CFG['deadline_unix'],GPU_work_started=False))
 stopping=False;phase='waiting_existing_native_and_Post_selection';active=None;child=None;stages=[]
 def stop(*_):
  nonlocal stopping
  stopping=True
  if child and child.poll() is None:child.send_signal(signal.SIGTERM)
 for sig in [signal.SIGTERM,signal.SIGINT,signal.SIGHUP]:signal.signal(sig,stop)
 def check():
  gates.authority()
  if stopping or (P/'STOP.json').exists():raise RuntimeError('own finite queue stopped')
  if time.time()>=CFG['deadline_unix']:raise TimeoutError('original finite successor deadline reached')
 def beat(**extra):
  value=dict(status='running',phase=phase,utc=utc(),process=own,active_root=str(active) if active else None,stages=stages,deadline_unix=CFG['deadline_unix'],A_waits_for_B=False,**extra)
  atomic_json(P/'QUEUE_HEARTBEAT.json',value);atomic_json(C/f"receipts/B/{CFG['task_id']}_RUNNING.json",value)
 def wait_dependencies(need_transfer=False):
  while True:
   check()
   try:choice=gates.selection();trans=gates.transfer() if need_transfer else None
   except (FileNotFoundError,ValueError,KeyError) as exc:beat(dependency_status=str(exc));time.sleep(15);continue
   if not gates.family_exited(F):beat(dependency_status='original native selected PV queue has not fully exited',original_native=optional_snapshot(F/'QUEUE_HEARTBEAT.json'));time.sleep(15);continue
   return choice,trans
 def run_wave(root,predecessor,choice,transfer=None):
  nonlocal active,child
  check()
  if not gates.family_exited(predecessor):raise RuntimeError('own previous formal family still alive')
  cfg=prepare_wave(root,predecessor,choice,transfer)
  if cfg['planned_current']==0:
   new_json(root/'RESULT.json',dict(status='complete',all_owned_descendants_exited=True,occupancy_handoff_complete=True,reason='all original units retained by A; none transferred',at_utc=utc()))
   return dict(stage=root.name,status='complete',family_exited=True,attempts=0)
  with (root/'daemon.stdout.log').open('xb') as so,(root/'daemon.stderr.log').open('xb') as se:
   child=subprocess.Popen(['/usr/bin/python','-B',str(root/'code/service.py'),'serve'],cwd=root,stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
  active=root;new_json(root/'FORMAL_SERVICE_STARTED.json',dict(process=process_identity(child.pid),utc=utc()))
  while True:
   check();code=child.poll()
   if code is not None:
    if gates.family_exited(root):
     t=read(root/'RESULT.json');active=None;child=None
     return dict(stage=root.name,status=t['status'],result=ref(root/'RESULT.json'),family_exited=True,attempts=current_attempts(root))
    # A service failure before any lifecycle command cannot have started GPU work.
    if not (root/'CHAIN_COMMAND.json').exists():
     t=dict(status='failed',reason='service exited before formal launch',exit_code=code,all_owned_descendants_exited=True,occupancy_handoff_complete=True,utc=utc())
     atomic_json(root/'RESULT.json',t);active=None;child=None
     return dict(stage=root.name,status='failed',family_exited=True,attempts=0,result=ref(root/'RESULT.json'))
    raise RuntimeError('formal terminal/cleanup unknown; next stage cannot overlap')
   beat(progress=optional_snapshot(root/'chain/HEARTBEAT.json'));time.sleep(10)
 try:
  choice,_=wait_dependencies()
  new_json(P/'SELECTION_SNAPSHOT.json',choice)
  phase='R_cancelled_once';predecessor=F
  r=run_wave(P/'R_cancelled_r3',predecessor,choice);stages.append(r);predecessor=P/'R_cancelled_r3'
  phase='waiting_exact_A_transfer';choice,t=wait_dependencies(need_transfer=True)
  new_json(P/'TRANSFER_SNAPSHOT.json',t)
  for H in [20,30]:
   phase=f'PI05_H{H}';root=P/f'H{H}_r1';r=run_wave(root,predecessor,choice,t);stages.append(r);predecessor=root
  phase='CPU_publication';status='complete' if all(r['status']=='complete' for r in stages) else 'partial';publish_chain(stages,status,phase);beat(terminal_status=status)
 except BaseException as exc:
  error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
  resolved=active is None
  if active:
   stop();end=time.monotonic()+300
   while time.monotonic()<end and child and child.poll() is None:time.sleep(2)
   resolved=gates.family_exited(active)
   stages.append(dict(stage=active.name,status='partial' if resolved else 'execution_unknown',family_exited=resolved,attempts=current_attempts(active)))
  publish_chain(stages,'blocked' if resolved and phase.startswith('waiting') else 'partial' if resolved else 'execution_unknown',phase,error)
  return 3
 return 0

def start():
 if (P/'QUEUE_CLAIM.json').exists():
  alive=same_process(normalized(read(P/'QUEUE_CLAIM.json')['process']));print('ALREADY_RUNNING' if alive else 'EXISTING_CLAIM_NO_REPLAY');return 0 if alive else 3
 gates.authority()
 with (P/'queue.stdout.log').open('ab') as so,(P/'queue.stderr.log').open('ab') as se:
  child=subprocess.Popen(['/usr/bin/python','-B',str(P/'code/queue.py'),'serve'],cwd=P,stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
 print('SPAWNED_NOT_YET_READY',child.pid);return 0
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['start','serve']);arg=p.parse_args();raise SystemExit(start() if arg.action=='start' else serve())
