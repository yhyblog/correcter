"""One persistent native base plus external feature server, both inside one wave."""
import argparse
import os
import signal
import subprocess
import time
from pathlib import Path
import paths
from qio import read,atomic_json,utc,process_identity
from common import reservation_fds,runtime_command,boundary

def main(config_path):
    cfg=read(config_path);out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    boundary(admission=True);fds=reservation_fds();server=client=None
    def terminate(*_):raise RuntimeError('owned GPU job stopped')
    for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,terminate)
    try:
        Path(cfg['socket_path']).parent.mkdir(parents=True,exist_ok=True)
        if Path(cfg['socket_path']).exists():raise RuntimeError('existing socket; do not duplicate')
        with (out/'encoder.log').open('xb') as log:
            server=subprocess.Popen(runtime_command('mw-pi05-legacy','feature_server.py','--config',config_path),
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,pass_fds=fds)
        atomic_json(out/'SERVER_PROCESS.json',process_identity(server.pid));deadline=time.monotonic()+1200
        while not (out/'encoder/READY.json').exists():
            boundary()
            if server.poll() is not None:raise RuntimeError('external encoder load failed '+str(server.returncode))
            if time.monotonic()>deadline:raise TimeoutError('external encoder loading deadline')
            time.sleep(2)
        with (out/'native.log').open('xb') as log:
            client=subprocess.Popen(runtime_command('mw-xvla-lr044','native_client.py','--config',config_path),
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,pass_fds=fds)
        atomic_json(out/'CLIENT_PROCESS.json',process_identity(client.pid))
        while client.poll() is None:
            boundary()
            if server.poll() is not None and not (out/'CLIENT_COMPUTE_DONE.json').exists():raise RuntimeError('encoder exited before client completion')
            time.sleep(2)
        if client.returncode:raise RuntimeError('native worker failed '+str(client.returncode))
        if server.wait(timeout=30):raise RuntimeError('encoder shutdown failed')
        atomic_json(out/'JOB_RESULT.json',dict(status='complete',at_utc=utc()))
    except BaseException as exc:
        atomic_json(out/'JOB_RESULT.json',dict(status='failed',error=repr(exc),at_utc=utc()));raise
    finally:
        for proc in [client,server]:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=25)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);main(p.parse_args().config)
