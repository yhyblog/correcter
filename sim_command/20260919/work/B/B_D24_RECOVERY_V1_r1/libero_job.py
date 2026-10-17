"""Own one persistent model server and its simulator client on one GPU."""
import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.request
import d24_common as d

def main(config_path):
    cfg = d.load(config_path)
    d.authorize(admission=True)
    output = Path(cfg['output'])
    output.mkdir(parents=True, exist_ok=True)
    d.atomic(output / 'status.json', dict(status='loading_server', job_id=cfg['job_id'], at_utc=d.utc()))
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', cfg['port']))
    workspace = d.ROOT / 'embodied-ai-workspace'
    runtime = workspace / 'projects/vla-baselines/launchers/runtime.sh'
    # Both children stay in the job's owned process group for bounded cleanup.
    server = client = None
    def terminate(*_):
        raise RuntimeError('LIBERO job termination requested')
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, terminate)
    try:
        with (output / 'server.log').open('a') as log:
            server = subprocess.Popen(['bash', str(runtime), 'pi05-openpi-jax', str(workspace / 'environments/pi05-openpi-jax/bin/python'),
                                       str(d.W / 'libero_server.py'), '--config', config_path],
                                      stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        d.atomic(output / 'SERVER_PROCESS.json', d.identity(server.pid))
        deadline = time.monotonic() + 1200
        while True:
            d.authorize()
            if server.poll() is not None:
                raise RuntimeError('LIBERO server exited during loading: %s' % server.returncode)
            try:
                with urllib.request.urlopen('http://127.0.0.1:%d/healthz' % cfg['port'], timeout=2) as response:
                    if response.status == 200:
                        break
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise TimeoutError('LIBERO model loading timeout')
            time.sleep(2)
        env = dict(os.environ, CUDA_VISIBLE_DEVICES='')
        client = subprocess.Popen(['bash', str(runtime), 'libero-sim-openpi', str(workspace / 'environments/libero-sim-openpi/bin/python'),
                                   str(d.W / 'libero_eval.py'), '--config', config_path], env=env, stdin=subprocess.DEVNULL)
        d.atomic(output / 'CLIENT_PROCESS.json', d.identity(client.pid))
        rc = client.wait()
        if rc:
            raise RuntimeError('LIBERO client exited: %d' % rc)
    except BaseException as exc:
        prior = d.load(output / 'status.json')
        prior.update(status='failed', job_error=repr(exc), at_utc=d.utc())
        d.atomic(output / 'status.json', prior)
        raise
    finally:
        for proc in (client, server):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    main(p.parse_args().config)
