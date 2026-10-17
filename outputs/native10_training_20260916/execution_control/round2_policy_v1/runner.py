"""One explicitly released v11 policy wave, followed by its static full audit."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import fcntl, hashlib, json, os, shutil, subprocess, sys, time, traceback

PACKAGE=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector')
ROOT=PACKAGE/'outputs/native10_training_20260916'
CONTROL=ROOT/'execution_control/round2_policy_v1'
STAGE='round2_development_policy'
BANK='round2_policy_v1'
WAVE='round2_policy_v1_01'
READY_SHA='7af5045a44944894cc8c89eb10f8110c2098d7458718fe0550d03a42fe30b953'
THREAD='01a0a551-9ed3-7f53-9f39-b60d8674819d'

def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def write(p,value,replace=False):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if replace:
  temp=p.with_name(p.name+'.writing.'+str(os.getpid()))
  temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(temp,p)
 else:
  with p.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def status(state,**info):
 p=PACKAGE/'coordination/NATIVE10_EXECUTOR_STATUS.json'
 with open('/tmp/corrector_native10_executor_status.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);d=read(p);now=utc()
  d['state']=state
  item=d.setdefault('round2_policy_execution',{})
  item.update(state=state,updated_utc=now,stage=STAGE,bank_version=BANK,wave_id=WAVE,
              ready_version=11,ready_sha256=READY_SHA,controller_pid=os.getpid(),**info)
  resource_info=info.get('runtime_resources',info.get('resources_after_wave'))
  if resource_info:
   totals=resource_info['global_totals']
   d['global_simulator_attempts']=totals.get('simulator_attempts',0)
   d['actual_optimizer_updates']=d['optimizer_updates']=totals.get('training_updates',0)
  for k in ('updated_at','updated_at_utc','updated_utc'):d[k]=now
  write(p,d,replace=True)
def queue(name,message):
 try:
  p=subprocess.run(['/home/tiger/.local/bin/codex','queue','--thread',THREAD,'--message',message],
                   capture_output=True,text=True,check=False)
  write(CONTROL/(name+'_queue.json'),dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr,message=message))
 except Exception as e:write(CONTROL/(name+'_queue_error.json'),dict(error=repr(e),message=message))
def resources():
 total=Counter();stage=Counter();kinds=Counter();records=0
 with (ROOT/'budget/attempts.jsonl').open() as f:
  for line in f:
   r=json.loads(line);records+=1;total[r['resource']]+=r['amount']
   if r['stage']==STAGE:stage[r['resource']]+=r['amount'];kinds[r['kind']]+=r['amount']
 return dict(global_totals=dict(total),stage=dict(stage),by_kind=dict(kinds),records=records)

def run():
 write(CONTROL/'started.json',dict(pid=os.getpid(),utc=utc(),stage=STAGE,bank_version=BANK,wave_id=WAVE))
 live=PACKAGE/'coordination/NATIVE10_ANALYSIS_READY.json'
 if sha(live)!=READY_SHA:raise ValueError('Expected exact v11 READY; do not silently bind another release')
 auth=CONTROL/'authorization';auth.mkdir()
 shutil.copyfile(live,auth/live.name)
 before=resources()
 if before['global_totals']!={'simulator_attempts':42874,'training_updates':51200} or before['stage']:
  raise ValueError('Unexpected before resources or previously started round2 policy; no automatic repeat')
 write(CONTROL/'resources_before.json',dict(**before,ledger_sha256=sha(ROOT/'budget/attempts.jsonl')))
 write(CONTROL/'gpu_before.json',read('/tmp/gpu_occupancy_guard/status.json'))
 from experiments.native10_training_20260916 import policy5_round2_prepare_v1 as prep
 from experiments.native10_training_20260916 import policy5_round2_runner_v1 as runner
 base=ROOT/'main_protocols/round1_v1/config.json'
 inputs=ROOT/'preparation/round2_policy_inputs_v1'
 cpu=ROOT/'preparation/round2_policy_cpu_20260917_v1'
 status('round2_policy_v11_inputs_running',execution_released=True,real_wave_started=False)
 ib=prep.inputs(base,auth/live.name,inputs)
 write(CONTROL/'inputs_result.json',ib)
 status('round2_policy_v11_freeze_running',input_binding=ib)
 frozen=prep.freeze(base,auth/live.name,inputs,[cpu],version=BANK,bank_version=BANK)
 write(CONTROL/'freeze_result.json',frozen)
 config=runner.verify_frozen(frozen['config'],frozen['freeze'],STAGE,BANK,32)
 ids=config['main_collection']['banks'][BANK]['episode_ids']
 if resources()!=before:raise RuntimeError('Preparation must not consume resources')
 frozen_at=utc();status('round2_policy_frozen_starting',frozen=frozen,freeze_verified_utc=frozen_at)
 command=[sys.executable,'-u','-m','experiments.native10_training_20260916.policy5_round2_runner_v1',
  'launch','--config',frozen['config'],'--freeze',frozen['freeze'],'--stage',STAGE,
  '--bank-version',BANK,'--wave-id',WAVE,'--workers','32']
 started=utc();begin=time.perf_counter()
 with (CONTROL/'wave.log').open('x') as log:
  process=subprocess.Popen(command,cwd=PACKAGE,stdout=log,stderr=subprocess.STDOUT)
  write(CONTROL/'actual_launch.json',dict(started_utc=started,pid=process.pid,controller_pid=os.getpid(),command=command,
       **frozen,expected_simulator_attempts=1995,stage_cap=2100,optimizer_updates=0,lifecycle_owned_by_runner=True))
  status('round2_policy_wave_running',started_utc=started,pid=process.pid,real_wave_started=True,frozen=frozen,
         loaded_worker_count=0,completed_source_count=0)
  queue('actual_launch',f'[native10 round2 policy actual launch] READYv11绑定通过，A4000原100dev五臂×4正式wave入口已启动。UTC{started} PID{process.pid}；config {frozen["config_sha256"]}；freeze {frozen["freeze_sha256"]}。控制目录{CONTROL}。lifecycle全波次8GPU×4worker，1995预计/2100cap/0opt；当前开始输入校验/装载，不等同已产数据。禁capture/替补/旧guided复用；cal/held未启动。')
  execution=ROOT/'policy5_execution'/STAGE/BANK/WAVE
  while process.poll() is None:
   complete=sum((ROOT/'collections'/STAGE/BANK/i/'complete.json').is_file() for i in ids)
   loaded=len(list((execution/'workers').glob('worker_*/loaded_critic_identity.json')))
   done=len(list((execution/'workers').glob('worker_*/complete.json')))
   failures=list(execution.rglob('failure.json')) if execution.exists() else []
   snapshot=dict(utc=utc(),phase='running',loaded_worker_count=loaded,completed_worker_count=done,
     completed_source_count=complete,total_sources=100,failures=[str(p) for p in failures],resources=resources(),
     wall_seconds=time.perf_counter()-begin)
   write(CONTROL/'progress.json',snapshot,replace=True)
   status('round2_policy_wave_running',loaded_worker_count=loaded,completed_worker_count=done,
          completed_source_count=complete,runtime_resources=snapshot['resources'],technical_failure_count=len(failures))
   time.sleep(30)
  rc=process.wait()
 write(CONTROL/'wave_result.json',dict(returncode=rc,started_utc=started,finished_utc=utc(),wall_seconds=time.perf_counter()-begin,
      resources=resources(),attempts_preserved=True,automatic_retry=False))
 if rc:raise RuntimeError('Policy wave failed; preserve owned logs and all attempts, no automatic retry')
 if sum((ROOT/'collections'/STAGE/BANK/i/'complete.json').is_file() for i in ids)!=100:
  raise RuntimeError('Wave returned without all original100 completed slots')
 after=resources()
 if after['stage']!={'simulator_attempts':1995} or after['global_totals']!={'simulator_attempts':44869,'training_updates':51200}:
  raise RuntimeError('Unexpected wave resource closure')
 # Lifecycle has exited; allow guard poll to restore all idle holders.
 holder=read('/tmp/gpu_occupancy_guard/status.json')
 for _ in range(15):
  if len(holder.get('gpus',{}))==8 and all(x.get('state')=='holder' for x in holder['gpus'].values()):break
  time.sleep(2);holder=read('/tmp/gpu_occupancy_guard/status.json')
 write(CONTROL/'gpu_after_wave.json',holder)
 status('round2_policy_wave_complete_raw_audit_running',completed_source_count=100,resources_after_wave=after)
 queue('wave_complete',f'[native10 round2 policy complete] 原100槽完整，lifecycle rc0；阶段1995=95bank+1900branch，global44869sim/51200opt。现开始已授权全轨迹只读审计；未按中途结局停止/换臂，cal/held不启动。{CONTROL}/wave_result.json')
 from experiments.native10_training_20260916 import policy5_round2_audit_v1 as audit
 from experiments.native10_training_20260916 import storage
 audit_dest=ROOT/'policy5_audits/round2_policy_v1'
 if audit_dest.exists():raise FileExistsError(audit_dest)
 abegin=time.perf_counter();result=audit.audit(config,BANK)
 storage.dump(audit_dest/'result.json',result)
 storage.seal(audit_dest,role='native10_policy5_readonly_audit',simulator_attempts=0,optimizer_updates=0)
 finish=dict(status='wave_and_primary_audit_complete',frozen=frozen,input_binding=ib,
   primary_audit=dict(path=str(audit_dest),seal_sha256=sha(audit_dest/'complete.json'),result_sha256=sha(audit_dest/'result.json')),
   audit_wall_seconds=time.perf_counter()-abegin,resources=resources(),ledger_sha256=sha(ROOT/'budget/attempts.jsonl'),
   further_policy_or_training_started=False)
 write(CONTROL/'result.json',finish)
 status('round2_policy_primary_audit_complete_pending_diagnostics',primary_audit=finish['primary_audit'],resources_after_wave=finish['resources'])
 queue('primary_audit_complete',f'[native10 round2 policy audit] 全100源原始审计PASS；{audit_dest} seal{finish["primary_audit"]["seal_sha256"]}。root继续独立统计/Q/raw/成本交接；资源44869sim/51200opt，未启动其他阶段。')

if __name__=='__main__':
 try:run()
 except BaseException as error:
  failure=dict(status='failed_no_automatic_retry',utc=utc(),error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),resources=resources())
  write(CONTROL/'failure.json',failure)
  status('round2_policy_technical_failure',failure_path=str(CONTROL/'failure.json'),error=str(error))
  queue('technical_failure',f'[native10 round2 policy technical failure] {type(error).__name__}: {error}；日志/账本保留，未自动重试或改参数。{CONTROL}/failure.json')
  raise
