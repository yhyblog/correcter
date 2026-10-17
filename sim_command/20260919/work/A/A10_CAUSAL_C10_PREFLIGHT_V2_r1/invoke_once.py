"""Outer evidence only: invoke the authorized frozen bash exactly once."""
import datetime,hashlib,json,os,subprocess,time,traceback
from pathlib import Path
W=Path(__file__).resolve().parent
B=W.parents[2]
RELEASE=B/'releases/P10_A_CAUSAL_C10_PREFLIGHT_V2.json'
EXPECTED='a48bd0659372f7ed9591720d021b7cf6c5253c63e952ea570f9e50ee7715cbfe'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(name,obj):
    with (W/name).open('x') as f:
        f.write(json.dumps(obj,indent=2,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
assert hashlib.sha256(RELEASE.read_bytes()).hexdigest()==EXPECTED
r=json.loads(RELEASE.read_text())
command=['bash',str(B/'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1/commands/run_proposed_causal_c10.sh'),str(RELEASE)]
assert r['real_command']==command
cwd=B/'results/A/A10_CAUSAL_EVENT_CPU_REPAIR_V1'
assert r['working_directory']==str(cwd)
claim=B/'results/A/P10_CAUSAL_C10_V2_release_claims'/(r['release_id']+'.json')
assert not claim.exists()
assert (B/'receipts/A/A10_CAUSAL_C10_PREFLIGHT_V2_ACK.json').is_file()
started=now();clock=time.monotonic()
save('COMMAND_STARTED.json',dict(task_id=r['task_id'],command=command,cwd=str(cwd),release_sha256=EXPECTED,
    at_utc=started,outer_pid=os.getpid(),command_opportunity_consumed=True,repeat_forbidden=True))
print(json.dumps(dict(status='COMMAND_STARTED',at_utc=started,command=command)),flush=True)
error=None;returncode=None;pid=None
with (W/'command.stdout.log').open('xb') as out,(W/'command.stderr.log').open('xb') as err:
    try:
        proc=subprocess.Popen(command,cwd=cwd,stdout=out,stderr=err)
        pid=proc.pid
        save('COMMAND_PROCESS.json',dict(pid=pid,at_utc=now(),outer_pid=os.getpid(),command=command))
        returncode=proc.wait()
    except BaseException as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        raise
    finally:
        result=dict(task_id=r['task_id'],command=command,cwd=str(cwd),release_sha256=EXPECTED,
            started_at_utc=started,finished_at_utc=now(),elapsed_seconds=time.monotonic()-clock,
            pid=pid,returncode=returncode,outer_error=error,real_command_attempts=1,retry=False,
            stdout=str(W/'command.stdout.log'),stderr=str(W/'command.stderr.log'),claim_exists=claim.exists())
        save('COMMAND_RESULT.json',result)
        print(json.dumps(result),flush=True)
