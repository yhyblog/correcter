"""One native pi05 server and one LIBERO client, under the whole-wave lock."""
import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.request
import d24_common as d
from batch import reservation_fds


def main(config_path):
    cfg=d.load(config_path);d.authorize(admission=True)
    out=Path(cfg['output']);out.mkdir(parents=True,exist_ok=True)
    d.atomic(out/'status.json',dict(status='loading_server',job_id=cfg['job_id'],at_utc=d.utc()))
    inherited=reservation_fds()
    if len(inherited)!=1:
        raise RuntimeError('Missing whole-wave formal reservation')
    workspace=d.ROOT/'embodied-ai-workspace';runtime=workspace/'projects/vla-baselines/launchers/runtime.sh'
    server=client=None
    def terminate(*_):
        raise RuntimeError('LIBERO job termination requested')
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):
        signal.signal(sig,terminate)
    try:
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',cfg['port']))
        with (out/'server.log').open('a') as log:
            server=subprocess.Popen(['bash',str(runtime),'pi05-openpi-jax',
                str(workspace/'environments/pi05-openpi-jax/bin/python'),'-B',str(d.W/'libero_server.py'),
                '--config',config_path],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,pass_fds=inherited)
        d.atomic(out/'SERVER_PROCESS.json',d.identity(server.pid))
        deadline=time.monotonic()+1200
        while True:
            d.authorize()
            if server.poll() is not None:
                raise RuntimeError('Native server exited during load: '+str(server.returncode))
            try:
                with urllib.request.urlopen('http://127.0.0.1:%d/healthz'%cfg['port'],timeout=2) as response:
                    if response.status==200:break
            except OSError:pass
            if time.monotonic()>deadline:raise TimeoutError('Native server loading timeout')
            time.sleep(2)
        with (out/'client.log').open('a') as log:
            client=subprocess.Popen(['bash',str(runtime),'libero-sim-openpi',
                '/usr/bin/env','-u','MUJOCO_EGL_DEVICE_ID',
                str(workspace/'environments/libero-sim-openpi/bin/python'),'-B',str(d.W/'libero_eval.py'),
                '--config',config_path],env=dict(os.environ,CUDA_VISIBLE_DEVICES='',VLA_RENDERER='mesa'),stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,pass_fds=inherited)
        d.atomic(out/'CLIENT_PROCESS.json',d.identity(client.pid))
        while client.poll() is None:
            d.authorize()
            if server.poll() is not None:raise RuntimeError('Native server exited during active client work')
            time.sleep(2)
        if client.returncode:raise RuntimeError('LIBERO client exited: '+str(client.returncode))
    except BaseException as exc:
        d.atomic(out/'status.json',dict(status='failed',error=repr(exc),at_utc=d.utc()))
        try:d.exclusive(Path(cfg['pipeline_output'])/'PIPELINE_FAILED.json',
            dict(job_id=cfg['job_id'],error=repr(exc),at_utc=d.utc()))
        except FileExistsError:pass
        raise
    finally:
        for proc in (client,server):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill();proc.wait(timeout=10)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True)
    main(p.parse_args().config)
