"""One frozen command; CPU-only observation of existing status and process files."""
from pathlib import Path
import datetime,hashlib,json,os,signal,subprocess,time
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W=B/'work/A/A10_PREFLIGHT_NATIVE_V3_r1';TASK='A10_PREFLIGHT_NATIVE_V3'
RELEASE=B/'releases/P10_A_NATIVE_PREFLIGHT_V3.json'
EXPECTED='5c431d7d44e10630354d3349cf7c8d5c2367da1c25826dd9f2de5df0fe088f5f'
STATUS=Path('/tmp/gpu_occupancy_guard/status.json')
GUARDLOG=Path('/mnt/bn/arnold-recommend/yaohaoyang/gpu_occupancy_guard.log')
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def publish(path,value):
 tmp=path.with_name(path.name+'.publish.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,path)
def write_new(path,value):
 with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def guard_status():
 try:return json.loads(STATUS.read_text())
 except (OSError,ValueError) as e:return dict(read_error=str(e))
def processes():
 rows=[]
 for entry in Path('/proc').iterdir():
  if not entry.name.isdigit():continue
  try:
   raw=(entry/'cmdline').read_bytes();cmd=raw.decode(errors='replace').split('\0')
   if not any(s.endswith('/preflight_pi05.py') or s.endswith('/run_reserved_diagnostic.py') or s.endswith('/launch_preflight.py') for s in cmd):continue
   if not any('A10_TORCH_UUID_ABI_CPU_REPAIR_V1' in s for s in cmd):continue
   stat=(entry/'stat').read_text().rsplit(') ',1)[1].split();info={}
   for line in (entry/'status').read_text().splitlines():
    if line.startswith(('VmRSS:','VmHWM:')):
     key,value=line.split(':',1);info[key+'_KiB']=int(value.split()[0])
   rows.append(dict(pid=int(entry.name),ppid=int(stat[1]),pgid=int(stat[2]),state=stat[0],start_ticks=int(stat[19]),argv=cmd,**info))
  except (OSError,ValueError,IndexError):pass
 return rows
assert hashlib.sha256(RELEASE.read_bytes()).hexdigest()==EXPECTED
r=json.loads(RELEASE.read_text());c=json.loads((B/'CONTROL.json').read_text())
assert c['active_compute_release_id']==r['release_id'] and c['active_compute_task_ids']==[TASK] and not c['stop_requested']
claim=B/'results/A/P10_native_release_claims'/f"{r['release_id']}.json"
assert not claim.exists(),'Existing release claim: no invocation permitted'
assert (B/'receipts/A'/f'{TASK}_ACK.json').exists()
command=['bash',r['command'],str(RELEASE)]
write_new(W/'INVOCATION.json',dict(command=command,cwd=r['working_directory'],release_sha256=EXPECTED,invocation_number=1,started_at_utc=stamp(),no_retry=True,extra_CPU_checker=False))
write_new(W/'OCCUPANCY_BEFORE.json',dict(at_utc=stamp(),source=str(STATUS),status=guard_status()))
log_offset=GUARDLOG.stat().st_size if GUARDLOG.exists() else 0
started=time.monotonic();samples=0;peak_rss=0;peak_hwm=0
with (W/'COMMAND_STDOUT_STDERR.log').open('x') as log,(W/'CPU_PROCESS_AND_GUARD_OBSERVATIONS.jsonl').open('x') as obs:
 proc=subprocess.Popen(command,cwd=r['working_directory'],stdout=log,stderr=subprocess.STDOUT)
 def forward(sig,_):
  if proc.poll() is None:proc.send_signal(sig)
 for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,forward)
 print(json.dumps(dict(event='frozen_sh_started',pid=proc.pid,at_utc=stamp())),flush=True)
 last_heartbeat=0
 while True:
  rows=processes();now=time.monotonic();status=guard_status();samples+=1
  for row in rows:
   peak_rss=max(peak_rss,row.get('VmRSS_KiB',0));peak_hwm=max(peak_hwm,row.get('VmHWM_KiB',0))
  obs.write(json.dumps(dict(at_utc=stamp(),monotonic=now,processes=rows,guard_status=status))+'\n');obs.flush()
  if now-last_heartbeat>=25:
   publish(B/'receipts/A'/f'{TASK}_HEARTBEAT.json',dict(task_id=TASK,task_revision=1,node_role='A',status='running',observer_pid=os.getpid(),launcher_pid=proc.pid,updated_at_utc=stamp(),progress=dict(real_sh_invocations=1,release_claim_present=claim.exists(),observation_samples=samples,process_pids=[x['pid'] for x in rows]),GPU_probe_calls_by_observer=0))
   last_heartbeat=now
  rc=proc.poll()
  if rc is not None:break
  time.sleep(2)
 elapsed=time.monotonic()-started
write_new(W/'COMMAND_EXIT.json',dict(returncode=rc,elapsed_seconds=elapsed,finished_at_utc=stamp(),real_sh_invocations=1,automatic_retries=0,release_claim_present=claim.exists(),CPU_observation_samples=samples,peak_observed_per_process_RSS_KiB=peak_rss,peak_observed_per_process_HWM_KiB=peak_hwm,resource_scope='CPU /proc samples of matching launcher/timeout/diagnostic processes; no NVML or GPU API queries; not a process-tree summed peak'))
write_new(W/'OCCUPANCY_AFTER_COMMAND.json',dict(at_utc=stamp(),source=str(STATUS),status=guard_status()))
write_new(W/'POST_COMMAND_PROCESSES.json',dict(at_utc=stamp(),matching_native_processes=processes()))
if GUARDLOG.exists():
 with GUARDLOG.open('rb') as f:f.seek(log_offset);window=f.read()
 with (W/'GUARD_LOG_WINDOW.log').open('xb') as f:f.write(window)
publish(B/'receipts/A'/f'{TASK}_HEARTBEAT.json',dict(task_id=TASK,task_revision=1,node_role='A',status='command_exited_audit_pending',updated_at_utc=stamp(),progress=dict(real_sh_invocations=1,returncode=rc,release_claim_present=claim.exists()),GPU_probe_calls_by_observer=0))
print(json.dumps(dict(event='frozen_sh_exited',returncode=rc,elapsed_seconds=elapsed,at_utc=stamp())),flush=True)
raise SystemExit(rc)
