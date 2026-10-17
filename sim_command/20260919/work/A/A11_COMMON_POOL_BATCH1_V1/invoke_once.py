"""Outer receipt for exactly one frozen bash command; never retries or probes."""
from pathlib import Path
import datetime,json,os,signal,subprocess,sys,time,traceback
B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W=B/'work/A/A11_COMMON_POOL_BATCH1_V1'
P=B/'results/A/A11_BATCH_SCALING_CPU_V1'
ARGV=['bash',str(P/'commands/run_proposed_batch1.sh'),str(B/'releases/P11_A_COMMON_POOL_BATCH1_V1.json')]
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(name,value):
    with (W/name).open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
started=time.monotonic();save('OUTER_INVOCATION.json',dict(at_utc=now(),argv=ARGV,cwd=str(P),
    command_opportunity_invocations=1,retry_allowed=False,wrapper_pid=os.getpid(),
    scope='invoke the frozen sh once; no independent checker/hardware/holder probe'))
child=None;error=None;code=None
try:
    with (W/'command.stdout').open('xb') as so,(W/'command.stderr').open('xb') as se:
        child=subprocess.Popen(ARGV,cwd=P,stdout=so,stderr=se)
        save('OUTER_CHILD_STARTED.json',dict(at_utc=now(),pid=child.pid,argv=ARGV))
        def forward(sig,frame):
            if child.poll() is None:child.send_signal(sig)
        for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,forward)
        code=child.wait()
except BaseException as e:
    error=dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc())
    if child is not None and child.poll() is None:code=child.wait()
finally:
    result=dict(at_utc=now(),argv=ARGV,cwd=str(P),raw_exit_code=code,
        elapsed_seconds=time.monotonic()-started,outer_error=error,
        command_opportunity_invocations=1,retry_performed=False,
        stdout_path=str(W/'command.stdout'),stderr_path=str(W/'command.stderr'))
    save('OUTER_COMMAND_RESULT.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
sys.exit(code if code is not None and code>=0 else 3)
