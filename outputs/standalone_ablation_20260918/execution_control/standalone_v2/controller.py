"""Authorized sequential orchestration only; frozen modules own all computation."""
from pathlib import Path
from datetime import datetime,timezone
import json,os,subprocess,sys,time,traceback
from experiments.standalone_ablation_20260918 import storage,protocol,audit
ROOT=storage.ROOT; CONTROL=ROOT/'execution_control/standalone_v2'; VERSION='standalone_v2'
CONFIG=ROOT/'protocols'/VERSION/'config.json'; FREEZE=CONFIG.with_name('freeze.json')
STATUS=storage.PACKAGE/'coordination/STANDALONE_ABLATION_EXECUTOR_STATUS.json'
THREAD='01a0a551-9ed3-7f53-9f39-b60d8674819d'
ENV=os.environ.copy();ENV.pop('CUDA_VISIBLE_DEVICES',None)
ENV.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
HASHES=dict(config_sha256=storage.sha256(CONFIG),freeze_sha256=storage.sha256(FREEZE))

def now():return datetime.now(timezone.utc).isoformat()
def mutable(path,value):
 tmp=path.with_name(path.name+'.tmp.'+str(os.getpid()));tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)
def resources():
 ledger=ROOT/'budget/attempts.jsonl';rows=[]
 if ledger.exists():
  raw=ledger.read_bytes()
  rows=[json.loads(line) for line in raw.splitlines(keepends=True) if line.endswith(b'\n')]
 by_stage={s:sum(r['amount'] for r in rows if r['stage']==s) for s in protocol.CAPS}
 return dict(new_simulator_attempts=sum(r['amount'] for r in rows),global_simulator_attempts=48183+sum(r['amount'] for r in rows),new_optimizer_updates=0,global_optimizer_updates=51200,by_stage=by_stage)
def update(state,**extras):
 s=storage.read(STATUS);s.update(updated_utc=now(),state=state,controller_pid=os.getpid(),actual_runtime_released=True,active_config=str(CONFIG),active_freeze=str(FREEZE),**HASHES,**resources());s.update(extras);mutable(STATUS,s);mutable(CONTROL/'latest.json',{k:s.get(k) for k in ('updated_utc','state','controller_pid','active_stage','stage_progress','new_simulator_attempts','global_simulator_attempts','new_optimizer_updates','global_optimizer_updates','by_stage','technical_error','holder_check')})
def notify(event,message):
 try:
  p=subprocess.run(['/home/tiger/.local/bin/codex','queue','--thread',THREAD,'--message',message],capture_output=True,text=True,timeout=30)
  storage.dump(CONTROL/('notify_'+event+'.json'),dict(utc=now(),message=message,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
 except Exception as e:
  storage.dump(CONTROL/('notify_'+event+'_error.json'),dict(error=repr(e),message=message))
def holders(stage):
 deadline=time.monotonic()+90
 while True:
  guard=storage.read('/tmp/gpu_occupancy_guard/status.json');states={k:v['state'] for k,v in guard['gpus'].items()}
  row=dict(utc=now(),guard_pid=guard['pid'],states=states,eight_holders=len(states)==8 and set(states.values())=={'holder'})
  if row['eight_holders']:
   storage.dump(CONTROL/(stage+'_holder_restored.json'),row);return row
  if time.monotonic()>deadline:raise RuntimeError('Guard has not restored eight holders after lifecycle exit: '+repr(states))
  time.sleep(3)
def wave(stage,workers,wave_id):
 command=[sys.executable,'-u','-m','experiments.standalone_ablation_20260918.runner','launch','--config',str(CONFIG),'--freeze',str(FREEZE),'--stage',stage,'--wave-id',wave_id,'--workers',str(workers)]
 log=CONTROL/(stage+'_launcher.log')
 with log.open('x') as stream:
  process=subprocess.Popen(command,cwd=storage.PACKAGE,env=ENV,stdout=stream,stderr=subprocess.STDOUT)
  launch=dict(utc=now(),launcher_pid=process.pid,controller_pid=os.getpid(),command=command,**HASHES,stage=stage,wave_id=wave_id,real_workers=workers,model_loading_not_claimed_complete=True)
  storage.dump(CONTROL/(stage+'_actual_launch.json'),launch)
  update(stage+'_launcher_started',active_stage=stage,new_model_calls=None,model_call_count_aggregated=False,stage_progress=dict(loaded_workers=0,completed_workers=0,completed_source_slots=0,failed_workers=0,launcher_pid=process.pid))
  notify(stage+'_launch','[standalone actual launch] '+stage+' UTC '+launch['utc']+' launcherPID '+str(process.pid)+' controllerPID '+str(os.getpid())+' config '+HASHES['config_sha256']+' freeze '+HASHES['freeze_sha256']+'; READYv4 exact, '+str(workers)+' real workers; 5+3empty preflight/50 then same-freeze audit gates formal1274. Loading not yet complete; no intermediate outcomes read. Control '+str(CONTROL))
  while process.poll() is None:
   folder=ROOT/'execution'/stage/wave_id/'workers';children=list(folder.glob('worker_*')) if folder.exists() else []
   counts=dict(loaded_workers=sum((p/'loaded_model_identity.json').exists() for p in children),completed_workers=sum((p/'complete.json').exists() for p in children),completed_source_slots=sum(len(list((p/'slots').glob('*.json'))) for p in children),failed_workers=sum((p/'failure.json').exists() for p in children),launcher_pid=process.pid)
   update(stage+'_running',active_stage=stage,stage_progress=counts)
   time.sleep(10)
  rc=process.returncode
 storage.dump(CONTROL/(stage+'_exit.json'),dict(utc=now(),returncode=rc,**resources()))
 restored=holders(stage)
 update(stage+'_wave_exited',active_stage=stage,holder_check=restored,lifecycle_returncode=rc)
 if rc:raise RuntimeError(stage+' lifecycle wave failed with exit '+str(rc)+'; no retry/formal continuation')
 return ROOT/'execution'/stage/wave_id

def main():
 storage.checked(CONFIG,'db0a276204a35e13ad088a84e6955a005c72b7705b1663f26e67447d70b9d2b0');storage.checked(FREEZE,'c56083482b2b664e629cf1007ce824b26a41fead668f3fe4b1c2c0d62669f1e3')
 storage.dump(CONTROL/'controller_started.json',dict(utc=now(),pid=os.getpid(),controller_sha256=storage.sha256(__file__),executable=sys.executable,**HASHES))
 pre=wave(protocol.PREFLIGHT,5,'standalone_v2_preflight_01')
 update('standalone_preflight_audit_running',active_stage=protocol.PREFLIGHT)
 result=audit.audit_preflight(CONFIG,FREEZE,pre,version=VERSION);storage.dump(CONTROL/'preflight_audit_result.json',result)
 notify('preflight_passed','[standalone preflight passed] 5 sources /50 attempts, old replay + solo identity full audit passed, seal '+result['seal_sha256']+'; no solo success aggregate. Same freeze now proceeds to sole formal1274 as READYv4 authorizes. '+str(CONTROL/'preflight_audit_result.json'))
 formal=wave(protocol.FORMAL,32,'standalone_v2_formal_01')
 update('standalone_formal_full_audit_running',active_stage=protocol.FORMAL)
 result=audit.run_audit(CONFIG,FREEZE,formal,version=VERSION);storage.dump(CONTROL/'formal_audit_result.json',result)
 guard=holders('final')
 final=dict(status='complete',utc=now(),audit=result,**HASHES,**resources(),holder_check=guard,automatic_retry=False,no_further_wave_started=True)
 storage.dump(CONTROL/'result.json',final);update('standalone_complete_pending_final_handoff',active_stage=None,holder_check=guard,final_audit=result)
 notify('complete','[standalone complete] sole formal100 source structural ablation audit passed; '+str(resources())+'; eight holders restored. Audit '+result['path']+' seal '+result['seal_sha256']+'. Executor now final independent statistics/handoff; no newwave/optimization.')

if __name__=='__main__':
 try:main()
 except BaseException as error:
  fail=dict(status='failed',utc=now(),error=repr(error),traceback=traceback.format_exc(),**resources(),automatic_retry=False)
  storage.dump(CONTROL/'controller_failure.json',fail);update('standalone_stopped_on_technical_error',technical_error=dict(error=repr(error),path=str(CONTROL/'controller_failure.json')),next_step='Preserve attempts/logs; report actual error; no automatic retry or formal continuation.')
  notify('failure','[standalone technical stop] '+repr(error)+'; '+str(resources())+'; evidence '+str(CONTROL/'controller_failure.json')+'; no automatic retry, no extra wave.');raise
