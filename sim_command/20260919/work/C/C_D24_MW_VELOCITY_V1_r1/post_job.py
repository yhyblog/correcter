"""One formal GPU worker owns a base client and its frozen feature server."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import time
import d24_common as d


def main(config_path):
    cfg = d.load(config_path)
    d.authorize(admission=True)
    out = Path(cfg['output'])
    out.mkdir(parents=True, exist_ok=True)
    d.atomic(out/'CONFIG.json',cfg)
    d.atomic(out/'status.json', dict(status='loading_server', job_id=cfg['job_id'], at_utc=d.utc()))
    workspace = d.ROOT/'embodied-ai-workspace'
    runtime = workspace/'projects/vla-baselines/launchers/runtime.sh'
    server = client = None
    inherited = []
    for p in Path('/proc/self/fd').iterdir():
        try:
            if os.readlink(str(p)) == '/tmp/gpu_occupancy_guard/formal.lock':
                inherited.append(int(p.name))
        except OSError:
            pass
    if len(inherited) != 1:
        raise RuntimeError('Missing whole-wave reservation')
    def terminate(*_):
        raise RuntimeError('Velocity job termination requested')
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):
        signal.signal(sig,terminate)
    try:
        Path(cfg['socket_path']).parent.mkdir(parents=True,exist_ok=True)
        if Path(cfg['socket_path']).exists():
            raise RuntimeError('Existing socket; never duplicate or remove unknown server')
        with (out/'corrector.log').open('a') as log:
            server = subprocess.Popen(['bash',str(runtime),'mw-pi05-legacy',
                str(workspace/'environments/lerobot/bin/python'),'-B',str(d.W/'correction_server.py'),
                '--config',config_path], stdin=subprocess.DEVNULL, stdout=log,stderr=subprocess.STDOUT,
                pass_fds=tuple(inherited))
        d.atomic(out/'SERVER_PROCESS.json',d.identity(server.pid))
        deadline = time.monotonic()+1200
        while not (out/'corrector/READY.json').exists():
            d.authorize()
            if server.poll() is not None:
                raise RuntimeError('Correction server exited during load: '+str(server.returncode))
            if time.monotonic()>deadline:
                raise TimeoutError('Correction server loading timeout')
            time.sleep(2)
        with (out/'client.log').open('a') as log:
            client = subprocess.Popen(['bash',str(runtime),cfg['base_environment'],
                str(workspace/'environments'/cfg['base_environment']/'bin/python'),'-B',
                str(d.W/'mw_post.py'),'--config',config_path], stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,pass_fds=tuple(inherited))
        d.atomic(out/'CLIENT_PROCESS.json',d.identity(client.pid))
        while client.poll() is None:
            d.authorize()
            # A normally drained server may exit after the client's close request.
            if server.poll() is not None and not (out/'CLIENT_COMPUTE_DONE.json').exists():
                raise RuntimeError('Correction server exited during active client work')
            time.sleep(2)
        if client.returncode:
            raise RuntimeError('Base client failed: '+str(client.returncode))
        rc = server.wait(timeout=30)
        if rc:
            raise RuntimeError('Correction server failed: '+str(rc))
    except BaseException as exc:
        prior = d.load(out/'status.json')
        prior.update(status='failed',job_error=repr(exc),at_utc=d.utc())
        d.atomic(out/'status.json',prior)
        raise
    finally:
        for proc in (client,server):
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=10)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--config',required=True)
    main(p.parse_args().config)
