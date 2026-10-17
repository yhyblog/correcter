"""Finite detached B batches; durable claims and ordinary process supervision."""
import argparse
import collections
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
import d24_common as d

def stop_owned(proc):
    if proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=10)
    # Children of a terminated leader may remain in its exclusively owned group.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 10
    while group_members(proc.pid) and time.monotonic() < deadline:
        time.sleep(.2)
    if group_members(proc.pid):
        os.killpg(proc.pid, signal.SIGKILL)
        deadline = time.monotonic() + 5
        while group_members(proc.pid) and time.monotonic() < deadline:
            time.sleep(.2)

def group_members(pgid):
    members = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            f = (p / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(f[2]) == pgid and f[0] != 'Z':
                members.append(int(p.name))
        except (OSError, ValueError, IndexError):
            pass
    return members

def reservation_fds():
    found = []
    for p in Path('/proc/self/fd').iterdir():
        try:
            if os.readlink(str(p)) == '/tmp/gpu_occupancy_guard/formal.lock':
                found.append(int(p.name))
        except OSError:
            pass
    return tuple(found)

def run(path):
    cfg = d.load(path)
    out = d.R
    out.mkdir(exist_ok=True)
    active, holders, results, failed_kinds = {}, {}, {}, collections.Counter()
    holder_contexts, holder_started = {}, {}
    pending = list(cfg['jobs'])
    inherited = reservation_fds()
    if cfg['kind'] == 'gpu' and len(inherited) != 1:
        raise RuntimeError('Exactly one inherited formal reservation required')
    handoff=d.load(out/'HOLDER_HANDOFF_REQUEST.json')
    remaining=[p for p in handoff['owned_processes'] if d.alive(p)]
    if remaining:raise RuntimeError('Own holders/descendants still alive before model Popen')
    d.exclusive(out/'HOLDER_EXIT_ACK.json',dict(utc=d.utc(),all_owned_holder_processes_exited=True,processes=handoff['owned_processes'],before_any_worker_Popen=True))
    running = True
    def halt(*_):
        nonlocal running
        running = False
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, halt)
    last_metrics = 0
    d.atomic(out / 'RUNNER_PROCESS.json', d.identity())
    try:
        while pending or active:
            d.authorize()
            if not running:
                raise RuntimeError('Batch stop requested')
            while pending and len(active) < cfg['max_workers']:
                job = pending.pop(0)
                family = 'e1' if job['job_id'].startswith('e1_') else job['job_id'].split('_N_')[0]
                if failed_kinds[family] >= 3:
                    results[job['job_id']] = dict(status='blocked', error='three failed jobs in this family; needs diagnosis', started=False)
                    continue
                d.authorize(admission=True)
                claim = d.R / 'claims' / (job['job_id'] + '.json')
                if claim.exists():
                    results[job['job_id']] = dict(status='execution_unknown', error='existing consumed claim; no replay')
                    continue
                for gpu in job['gpus']:
                    if gpu in holders:
                        stop_owned(holders.pop(gpu))
                output = Path(job['output'])
                output.mkdir(parents=True,exist_ok=True)
                env = dict(os.environ, **job.get('env', {}))
                env.update(CUDA_VISIBLE_DEVICES=','.join(map(str, job['gpus'])), PYTHONUNBUFFERED='1',
                           OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', OMP_NUM_THREADS='4', LP_NUM_THREADS='4')
                d.exclusive(claim, dict(job_id=job['job_id'], run_id=cfg['run_id'], at_utc=d.utc(),
                                       config=job['config'], config_sha256=hashlib.sha256(Path(job['config']).read_bytes()).hexdigest(),
                                       supervisor=d.identity(), gpu_assignment=job['gpus']))
                with (output / 'worker.log').open('a') as log:
                    proc = subprocess.Popen(job['argv'], cwd=str(d.W), env=env, stdin=subprocess.DEVNULL,
                                            stdout=log, stderr=subprocess.STDOUT, start_new_session=True, pass_fds=inherited)
                d.atomic(output / 'PROCESS.json', d.identity(proc.pid))
                active[job['job_id']] = (job, proc, time.monotonic(), family)
            for jid, (job, proc, started, family) in list(active.items()):
                timed_out = time.monotonic() - started > job['timeout_seconds']
                if timed_out:
                    stop_owned(proc)
                rc = proc.poll()
                if rc is None:
                    continue
                remaining = group_members(proc.pid)
                if remaining:
                    stop_owned(proc)
                    remaining = group_members(proc.pid)
                if remaining:
                    raise RuntimeError('Owned descendants still active after job exit: %s' % remaining)
                p = Path(job['output']) / 'status.json'
                status = d.load(p) if p.exists() else {}
                ok = rc == 0 and status.get('status') in ('complete','scientific_gap_no_Full_eval')
                results[jid] = dict(status=status.get('status','complete') if ok else 'failed', exit_code=rc, timeout=timed_out,
                                    worker_status=status, all_owned_descendants_exited=True)
                d.atomic(Path(job['output']) / 'TERMINAL.json', results[jid])
                if not ok:
                    failed_kinds[family] += 1
                del active[jid]
            if cfg['kind'] == 'gpu' and time.monotonic() - last_metrics >= 15:
                metrics = subprocess.run(['nvidia-smi', '--query-gpu=index,uuid,utilization.gpu,memory.used',
                                          '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=15)
                d.append(out / 'gpu_metrics.jsonl', dict(at_utc=d.utc(), rows=metrics.stdout.strip(), exit_code=metrics.returncode,
                                                       active_jobs=list(active), auxiliary_gpus=sorted(holders)))
                # All eight holders stay off throughout the owned wave.
                last_metrics = time.monotonic()
            d.atomic(out / 'PROGRESS.json', dict(at_utc=d.utc(), status='running', active=list(active),
                                                queued=len(pending), completed=sum(v['status'] == 'complete' for v in results.values()),
                                                resolved=len(results), auxiliary_gpus=sorted(holders)))
            if pending or active:
                time.sleep(3)
    finally:
        for jid, (job, proc, _, _) in active.items():
            stop_owned(proc)
            p = Path(job['output']) / 'status.json'
            try:
                worker_status = d.load(p) if p.exists() else {}
            except Exception as exc:
                worker_status = dict(metadata_error=repr(exc))
            results[jid] = dict(status='failed', exit_code=proc.poll(),
                                reason='batch interrupted; retained completed episode records are authoritative',
                                worker_status=worker_status,
                                all_owned_descendants_exited=not bool(group_members(proc.pid)))
            d.atomic(Path(job['output']) / 'TERMINAL.json', results[jid])
        for gpu, proc in holders.items():
            stop_owned(proc)
            d.append(out / 'auxiliary_events.jsonl', dict(event='stop', gpu=gpu, at_utc=d.utc(), remaining=group_members(proc.pid)))
        remaining = {str(proc.pid): group_members(proc.pid) for _, proc, _, _ in active.values()}
        remaining.update({str(proc.pid): group_members(proc.pid) for proc in holders.values()})
        d.atomic(out / 'DRAIN.json', dict(at_utc=d.utc(), all_owned_descendants_exited=not any(remaining.values()), remaining=remaining))
        d.atomic(out / 'JOB_RESULTS.json', results)
        d.atomic(out / 'PROGRESS.json', dict(at_utc=d.utc(), status='drained', active=[], queued=len(pending),
                                            resolved=len(results), completed=sum(v['status'] == 'complete' for v in results.values()),
                                            all_owned_descendants_exited=not any(remaining.values())))
    return 0 if len(results) == len(cfg['jobs']) and all(v['status'] == 'complete' for v in results.values()) else 1


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--batch",required=True);a=p.parse_args()
    try:
        rc=run(a.batch)
        from summarize import publish
        publish()
        sys.exit(rc or 0)
    except BaseException as e:
        if not isinstance(e,SystemExit):
            d.atomic(d.R/"RUNNER_ERROR.json",dict(error=repr(e),traceback=traceback.format_exc(),utc=d.utc()))
            from summarize import publish
            publish()
        raise
