"""Executor transport for the one authorized frozen command; no compute edits."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

B=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
W=Path(__file__).parent
P=B/'results/A/A10_PV_OFFLINE_PREFLIGHT_CPU_V1'
R=B/'releases/P10_A_PV_OFFLINE_PREFLIGHT_V1.json'
CLAIM=B/'results/A/P10_PV_release_claims/P10_A_PV_OFFLINE_PREFLIGHT_V1.json'
EXPECTED='4a1b7ccb7ca1964da38000b9ccdff0666a411ec382aeca76c6a6e1658591392f'

def stamp():return dict(utc=datetime.now(timezone.utc).isoformat(),unix=time.time(),monotonic=time.monotonic())
def write(name,data):
    with (W/name).open('x') as f:f.write(json.dumps(data,indent=2,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
def guard_snapshot(name):
    p=Path('/tmp/gpu_occupancy_guard/status.json')
    try:
        b=p.read_bytes();x=json.loads(b)
        write(name,dict(observed_at=stamp(),source=str(p),source_sha256=hashlib.sha256(b).hexdigest(),
            source_mtime=p.stat().st_mtime,mode='read_existing_guard_status_only_no_GPU_query',status=x))
    except (OSError,ValueError) as e:write(name,dict(observed_at=stamp(),error=str(e),GPU_query_performed=False))

def main():
    assert hashlib.sha256(R.read_bytes()).hexdigest()==EXPECTED
    assert platform.node()=='trial-303224955-trialrun-303224955-worker-0'
    if CLAIM.exists():
        write('ALREADY_CLAIMED_NO_RUN.json',dict(claim=str(CLAIM),observed_at=stamp(),command_executions=0))
        return 4
    cmd=['bash',str(P/'commands/run_proposed_pv_offline.sh'),str(R)]
    start=stamp()
    write('COMMAND_ATTEMPT.json',dict(command=cmd,cwd=str(P),release_sha256=EXPECTED,started_at=start,
        attempts=1,max_retries=0,extra_checker=False,extra_probe=False))
    guard_snapshot('GUARD_BEFORE.json')
    with (W/'launcher.log').open('xb') as stream:
        child=subprocess.Popen(cmd,cwd=P,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        write('COMMAND_PROCESS.json',dict(pid=child.pid,process_group=child.pid,started_at=stamp()))
        code=child.wait()
    end=stamp()
    guard_snapshot('GUARD_AFTER.json')
    write('COMMAND_EXIT.json',dict(returncode=code,child_pid=child.pid,child_wait_returned=True,
        child_proc_exists=Path('/proc/'+str(child.pid)).exists(),started_at=start,finished_at=end,
        observed_wall_seconds=end['monotonic']-start['monotonic'],release_claim_exists=CLAIM.exists(),automatic_retry=False))
    print(json.dumps(dict(returncode=code,log=str(W/'launcher.log'),claim_exists=CLAIM.exists(),wall_seconds=end['monotonic']-start['monotonic'])))
    return code

if __name__=='__main__':raise SystemExit(main())
