"""Outer receipt for exactly one frozen command; no probes or retries."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time

B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
TASK='A10_PV_OFFLINE_PREFLIGHT_V2'
W=B/'work/A'/f'{TASK}_r1'
OUT=B/'results/A'/TASK
PACKAGE=B/'results/A/A10_PV_AUTH_METADATA_CPU_V1'
RELEASE=B/'releases/P10_A_PV_OFFLINE_PREFLIGHT_V2.json'
RUN=B/'results/A/P10_PV_V2_launcher_runs/A10_PV_OFFLINE_PREFLIGHT_V2_r1_A_wave07'
CLAIM=B/'results/A/P10_PV_V2_release_claims/P10_A_PV_OFFLINE_PREFLIGHT_V2.json'
GUARD=Path('/tmp/gpu_occupancy_guard/status.json')

def stamp():
    return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),unix_seconds=time.time(),monotonic_seconds=time.monotonic())

def put(path,value):
    with path.open('x') as f:
        f.write(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
        f.flush();os.fsync(f.fileno())

def read_guard():
    try:return json.loads(GUARD.read_text())
    except (OSError,ValueError) as e:return dict(read_error=str(e))

def heartbeat(phase,process=None):
    item=dict(phase=phase,**stamp(),command_pid=None if process is None else process.pid,
              command_alive=None if process is None else process.poll() is None,claim_exists=CLAIM.exists())
    guard=read_guard()
    item['guard_cache_updated']=guard.get('updated')
    item['guard_cache_states']={k:v.get('state') for k,v in guard.get('gpus',{}).items()}
    for name,path in [('launcher',RUN/'launcher_events.jsonl'),('diagnostic',RUN/'diagnostic/events.jsonl')]:
        if path.exists():
            lines=path.read_text().splitlines()
            try:item[name+'_last_event']=json.loads(lines[-1]) if lines else None
            except ValueError:item[name+'_last_event']='partial_write'
    with (W/'HEARTBEAT.jsonl').open('a') as f:
        f.write(json.dumps(item,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())

def session_members(sid):
    rows=[]
    for root in Path('/proc').iterdir():
        if not root.name.isdigit():continue
        try:
            text=(root/'stat').read_text();tail=text[text.rfind(')')+2:].split()
            if int(tail[3])==sid:
                rows.append(dict(pid=int(root.name),state=tail[0],ppid=int(tail[1]),pgid=int(tail[2]),sid=int(tail[3])))
        except (OSError,ValueError,IndexError):pass
    return rows

assert hashlib.sha256(RELEASE.read_bytes()).hexdigest()=='b7baf846254e9c63dca4efef354e56f56c0afcb69bfee88754e8eddc20db8522'
assert not CLAIM.exists() and not RUN.exists()
assert not (B/'releases/P10_A_PV_OFFLINE_PREFLIGHT_V2_CLOSED.json').exists()
assert (B/'receipts/A'/f'{TASK}_ACK.json').exists()
command=['bash',str(PACKAGE/'commands/run_proposed_pv_offline.sh'),str(RELEASE)]
start=stamp()
put(W/'COMMAND_OPPORTUNITY.json',dict(command=command,cwd=str(PACKAGE),started=start,opportunity_limit=1,automatic_retry=False))
put(W/'HOLDER_GUARD_BEFORE.json',dict(observed_at=stamp(),source='existing guard status cache; no new NVML query',status=read_guard()))
heartbeat('before_command')
process=None;returncode=None;error=None
try:
    with (W/'COMMAND.log').open('x') as log:
        process=subprocess.Popen(command,cwd=PACKAGE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        put(W/'COMMAND_PROCESS.json',dict(pid=process.pid,pgid=os.getpgid(process.pid),sid=os.getsid(process.pid),started_at=stamp(),argv=command))
        def forward(sig,_):
            if process.poll() is None:
                try:os.killpg(process.pid,sig)
                except ProcessLookupError:pass
        for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,forward)
        print(json.dumps(dict(phase='frozen_command_started',pid=process.pid,log=str(W/'COMMAND.log'))),flush=True)
        while True:
            try:
                returncode=process.wait(timeout=30)
                break
            except subprocess.TimeoutExpired:
                heartbeat('running',process)
        heartbeat('command_exited',process)
except BaseException as e:
    error=dict(type=type(e).__name__,message=str(e))
finally:
    end=stamp()
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    members=session_members(process.pid) if process is not None else []
    result=dict(origin='executor_outer_receipt_not_frozen_launcher',command=command,cwd=str(PACKAGE),
        command_invocations=1 if process is not None else 0,command_opportunity_recorded=True,
        command_pid=None if process is None else process.pid,returncode=returncode,error=error,
        started_at=start,finished_at=end,wall_seconds=end['monotonic_seconds']-start['monotonic_seconds'],
        command_reaped=process is not None and process.returncode is not None,
        outer_command_session_members=members,claim_exists=CLAIM.exists(),
        frozen_launch_result_path=str(RUN/'LAUNCH_RESULT.json'),frozen_launch_result_exists=(RUN/'LAUNCH_RESULT.json').exists(),
        child_usage=dict(user_cpu_seconds=usage.ru_utime,system_cpu_seconds=usage.ru_stime,max_RSS_KiB=usage.ru_maxrss,scope='waited outer command and inherited child resource accounting; not GPU utilization'),
        automatic_retry=False,remaining_opportunity_reusable=False,extra_checker_or_probe_invocations=0)
    put(OUT/'OUTER_COMMAND_RESULT.json',result)
    put(W/'HOLDER_GUARD_AFTER_COMMAND.json',dict(observed_at=stamp(),source='existing guard status cache; no new NVML query',status=read_guard()))
    print(json.dumps(result,indent=2),flush=True)
raise SystemExit(returncode if returncode is not None else 99)
