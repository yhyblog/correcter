#!/usr/bin/env python3
"""Run disjoint GPU jobs without occupancy computation during a formal wave.

Invoke INSIDE ../gpu_occupancy_lifecycle.sh run -- ... . The outer lifecycle
restores the persistent eight-GPU holder on success/error/signal; this process
owns and cleans up only its children and temporary subset holders.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def stop_owned(process: subprocess.Popen) -> None:
    # The leader may have exited while its child CUDA workers still live.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def run_wave(spec_path: Path) -> int:
    root = Path(__file__).resolve().parents[1]
    spec = json.loads(spec_path.read_text())
    jobs = spec['jobs']
    hold_idle = bool(spec.get('hold_idle', False))
    devices = [int(g) for job in jobs for g in job['devices']]
    if sorted(devices) != list(range(8)):
        raise ValueError('Each wave must assign every physical GPU exactly once')
    log_root = Path(spec['log_root']).resolve()
    log_root.mkdir(parents=True, exist_ok=True)
    processes, holders, streams = [], [], []
    finished = set()
    old_handlers = {}

    def interrupted(signum: int, _frame: object) -> None:
        raise KeyboardInterrupt(f'signal {signum}')

    for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        old_handlers[sig] = signal.signal(sig, interrupted)
    try:
        for index, job in enumerate(jobs):
            stream = (log_root/f'job_{index}.log').open('x')
            streams.append(stream)
            environment = os.environ.copy()
            environment['CUDA_VISIBLE_DEVICES'] = ','.join(map(str, job['devices']))
            environment.update(job.get('env', {}))
            process = subprocess.Popen(job['command'], cwd=root, env=environment,
                                       stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            processes.append(process)
            print(json.dumps({'event':'job_started', 'index':index, 'pid':process.pid,
                              'devices':job['devices'], 'command':job['command']}), flush=True)
        while len(finished) < len(processes):
            for index, process in enumerate(processes):
                if index in finished:
                    continue
                status = process.poll()
                if status is None:
                    continue
                finished.add(index)
                print(json.dumps({'event':'job_finished', 'index':index, 'status':status}), flush=True)
                if status:
                    return status
                stop_owned(process)
                if hold_idle and len(finished) < len(processes):
                    holder_log = (log_root/f'holder_{index}.log').open('x')
                    streams.append(holder_log)
                    holder = subprocess.Popen(
                        ['/usr/bin/python', str(root.parent/'gpu_hold.py'),
                         '--devices', ','.join(map(str, jobs[index]['devices'])),
                         '--size', '8192', '--dtype', 'bf16', '--log-interval', '30'],
                        cwd=root, stdout=holder_log, stderr=subprocess.STDOUT, start_new_session=True,
                    )
                    holders.append(holder)
                    print(json.dumps({'event':'idle_subset_holder_started', 'devices':jobs[index]['devices'],
                                      'pid':holder.pid}), flush=True)
            for holder in holders:
                if holder.poll() is not None:
                    raise RuntimeError(f'Idle subset holder exited unexpectedly: {holder.pid}')
            time.sleep(.5)
        return 0
    finally:
        for process in reversed(processes + holders):
            stop_owned(process)
        for stream in streams:
            stream.close()
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    args = parser.parse_args()
    try:
        status = run_wave(args.spec)
    except KeyboardInterrupt:
        status = 130
    sys.exit(status)
