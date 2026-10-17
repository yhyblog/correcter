"""Single-instance deployment of the authorized finite CPU observer only."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

WORK=Path(__file__).resolve().parent
BASE=WORK.parents[2]
ROOT=BASE/'results/A/A_D24_PAPER_RESULTS_ASSEMBLY_V1'
OBS=ROOT/'observer'


def save(path,data):
    with path.open('x') as f:
        json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())


def main():
    OBS.mkdir(exist_ok=True)
    # Shared object-store mount does not implement flock; node-local CPU lock only.
    with Path('/tmp/A_D24_PAPER_RESULTS_ASSEMBLY_V1_deployment.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        existing=OBS/'LAUNCH.json'
        if existing.exists():
            print(json.dumps(dict(existing_launch=json.loads(existing.read_text()),new_launch=False)));return
        ap=BASE/'deadline_20260924/A_PAPER_RESULTS_AUTHORIZATION_V1.json'
        raw=ap.read_bytes();auth=json.loads(raw)
        assert hashlib.sha256(raw).hexdigest()=='6f0d7eea491696782df115e9cf1f326e542fcfc66f8cb0317cffa2eb2c5e36a1'
        assert auth['status']=='released' and socket.gethostname()==auth['host']
        assert auth['new_episode_attempts']==auth['model_forward_or_backward_calls']==auth['holder_lifecycle_changes']==0
        assert (ROOT/'CURRENT.json').exists(), 'Publish current evidence before background appends'
        reg=dict(task_id=auth['task_id'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            authorization_path=str(ap),authorization_sha256=hashlib.sha256(raw).hexdigest(),
            deadline_utc=auth['append_observer_deadline_utc'],max_consumptions_per_node=1,
            CPU_only=True,scientific_compute=0,holder_changes=0,no_BC_barrier=True,
            original_thread_id=auth['thread_id'],only_child_command=[sys.executable,str(WORK/'observer.py')],
            inputs=['B_D24_R_H20_H30_V1 terminal + CSV','C_D24_R_H40_H50_V1 latest-run terminal + CSV'],
            files=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [WORK/'paper_results.py',WORK/'observer.py',Path(__file__)]])
        save(OBS/'REGISTRATION.json',reg)
        env=os.environ.copy();env['OMP_NUM_THREADS']='1';env['OPENBLAS_NUM_THREADS']='1'
        env['MPLCONFIGDIR']=str(WORK/'matplotlib_cache');env['XDG_CACHE_HOME']=str(WORK/'cache')
        with (OBS/'stdout.log').open('xb') as so,(OBS/'stderr.log').open('xb') as se:
            p=subprocess.Popen([sys.executable,str(WORK/'observer.py')],cwd=WORK,
                stdin=subprocess.DEVNULL,stdout=so,stderr=se,start_new_session=True,close_fds=True,env=env)
        fields=Path('/proc',str(p.pid),'stat').read_text().rsplit(') ',1)[1].split()
        launch=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),pid=p.pid,start_ticks=int(fields[19]),
            host=socket.gethostname(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            command=[sys.executable,str(WORK/'observer.py')],registration=str(OBS/'REGISTRATION.json'),
            scientific_compute=0,holder_changes=0,READY_observed=False)
        save(existing,launch);print(json.dumps(launch))


if __name__=='__main__':main()
