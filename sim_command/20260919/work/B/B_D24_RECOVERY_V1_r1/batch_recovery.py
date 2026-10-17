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
    out = d.R / cfg['batch_id']
    out.mkdir(exist_ok=True)
    active, holders, results, failed_kinds = {}, {}, {}, collections.Counter()
    holder_contexts, holder_started = {}, {}
    pending = list(cfg['jobs'])
    inherited = reservation_fds()
    if cfg['kind'] == 'gpu' and len(inherited) != 1:
        raise RuntimeError('Exactly one inherited formal reservation required')
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
                output.mkdir(exist_ok=True)
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
                ok = rc == 0 and status.get('status') == 'complete'
                results[jid] = dict(status='complete' if ok else 'failed', exit_code=rc, timeout=timed_out,
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
                busy = {g for job, _, _, _ in active.values() for g in job['gpus']}
                # Only inactive cards may get auxiliary occupancy inside the reservation.
                apps = subprocess.run(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'],
                                      capture_output=True, text=True, timeout=15)
                contexts = collections.defaultdict(set)
                if apps.returncode == 0:
                    for line in apps.stdout.splitlines():
                        cells = [v.strip() for v in line.split(',')]
                        if len(cells) == 2:
                            contexts[cells[0]].add(cells[1])
                devices = {}
                if metrics.returncode == 0:
                    for line in metrics.stdout.splitlines():
                        cells = [v.strip() for v in line.split(',')]
                        devices[int(cells[0])] = cells[1]
                for gpu in range(8):
                    if gpu in holders and holders[gpu].poll() is not None:
                        holders.pop(gpu)
                        holder_contexts.pop(gpu, None)
                    if gpu in holders:
                        current = contexts.get(devices.get(gpu), set())
                        known = holder_contexts.get(gpu)
                        if known is None and len(current) == 1:
                            holder_contexts[gpu] = set(current)
                            known = set(current)
                        if (apps.returncode or len(current) > 1 or (known and current - known)
                                or (time.monotonic() - holder_started[gpu] > 60 and not current)):
                            stop_owned(holders.pop(gpu))
                            holder_contexts.pop(gpu, None)
                            d.append(out / 'auxiliary_events.jsonl', dict(event='yield_or_retry', gpu=gpu, at_utc=d.utc()))
                            continue
                    if gpu in busy or gpu in holders or not active:
                        continue
                    if apps.returncode or gpu not in devices or devices[gpu] in apps.stdout:
                        continue
                    env = dict(os.environ)
                    env.pop('CUDA_VISIBLE_DEVICES', None)
                    with (out / 'auxiliary_holders.log').open('a') as log:
                        proc = subprocess.Popen(['/usr/bin/python', str(d.ROOT / 'gpu_hold.py'), '--devices', str(gpu),
                                                 '--size', '8192', '--dtype', 'bf16', '--target-util', '0.50',
                                                 '--period-seconds', '0.20', '--log-interval', '300'],
                                                env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                                start_new_session=True, pass_fds=inherited)
                    holders[gpu] = proc
                    holder_started[gpu] = time.monotonic()
                    d.append(out / 'auxiliary_events.jsonl', dict(event='start', gpu=gpu, process=d.identity(proc.pid), at_utc=d.utc()))
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

def supervise(path):
    cfg = d.load(path)
    out = d.R / cfg['batch_id']
    out.mkdir(exist_ok=True)
    local = Path('/tmp/corrector_B_D24')
    local.mkdir(exist_ok=True)
    with (local / (cfg['batch_id'] + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        d.authorize(admission=True)
        claim = out / 'CLAIM.json'
        d.exclusive(claim, dict(batch_id=cfg['batch_id'], run_id=cfg['run_id'], config=path,
                               config_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(), process=d.identity(), at_utc=d.utc()))
        d.atomic(out / 'PROCESS.json', d.identity())
        manifest = dict(job_id=cfg['batch_id'], task_id='B_D24_SPRINT_V1', revision=1, run_id=cfg['run_id'], attempt=1,
                        claim_identity=dict(path=str(claim), sha256=hashlib.sha256(claim.read_bytes()).hexdigest()),
                        process_identity=d.identity(), result_path=str(out / 'RESULT.json'), error_summary_path=str(out / 'supervisor.log'))
        d.atomic(out / 'WAKEUP_REGISTRATION.json', manifest)
        subprocess.run(['/usr/bin/python', str(d.C / 'work/B/B_LONG_TASK_WAKEUP_V1_r1/wakeup.py'),
                        'register', '--manifest', str(out / 'WAKEUP_REGISTRATION.json')], check=True)
        try:
            # A lightweight dependency wait; it does not own a GPU reservation.
            for dependency in cfg.get('after_batches', []):
                dep = d.R / dependency
                while (dep / 'PROCESS.json').exists() and d.alive(d.load(dep / 'PROCESS.json')):
                    d.authorize(admission=True)
                    d.atomic(out / 'PROGRESS.json', dict(status='waiting_for_predecessor', predecessor=dependency,
                                                       at_utc=d.utc(), scientific_operations=0))
                    time.sleep(15)
            argv = ['/usr/bin/python', str(Path(__file__).resolve()), 'run', '--batch', path]
            if cfg['kind'] == 'gpu':
                argv = ['bash', str(d.ROOT / 'gpu_occupancy_lifecycle.sh'), 'run', '--'] + argv
            started = time.monotonic()
            try:
                child = subprocess.Popen(argv, stdin=subprocess.DEVNULL)
                rc = child.wait()
                jobs = d.load(out / 'JOB_RESULTS.json') if (out / 'JOB_RESULTS.json').exists() else {}
                drain = d.load(out / 'DRAIN.json') if (out / 'DRAIN.json').exists() else {}
                guard_handoff = None
                if cfg['kind'] == 'gpu' and drain.get('all_owned_descendants_exited'):
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        guard = d.load('/tmp/gpu_occupancy_guard/status.json')
                        if len(guard.get('gpus', {})) == 8 and all(v['state'] != 'reserved' for v in guard['gpus'].values()):
                            guard_handoff = True
                            d.atomic(out / 'GUARD_HANDOFF.json', guard)
                            break
                        time.sleep(1)
                d.atomic(out / 'RESULT.json', dict(status='complete' if rc == 0 else 'partial' if jobs else 'failed',
                         exit_code=rc, batch_id=cfg['batch_id'], job_count=len(cfg['jobs']), jobs=jobs,
                         all_owned_descendants_exited=drain.get('all_owned_descendants_exited'), publication_completed=True,
                         occupancy_handoff_complete=guard_handoff,
                         occupancy_note='temporary holders reaped; inherited reservation released; original guard resumes on next poll' if cfg['kind'] == 'gpu' else 'CPU only; no CUDA reservation required',
                         elapsed_seconds=time.monotonic() - started, at_utc=d.utc()))
                return rc
            except BaseException as exc:
                d.atomic(out / 'RESULT.json', dict(status='execution_unknown', exit_code=None, error=repr(exc),
                         all_owned_descendants_exited=None, publication_completed=True, occupancy_handoff_complete=None, at_utc=d.utc()))
                raise
        except BaseException as exc:
            if not (out / 'RESULT.json').exists():
                entered = (out / 'RUNNER_PROCESS.json').exists()
                d.atomic(out / 'RESULT.json', dict(status='execution_unknown' if entered else 'blocked',
                         failure_phase='runner' if entered else 'predecessor_wait_or_launch', exit_code=None,
                         scientific_job_entered=entered, error=repr(exc), at_utc=d.utc(),
                         all_owned_descendants_exited=True if not entered else None,
                         publication_completed=True, occupancy_handoff_complete=None))
            raise

def start(path):
    cfg = d.load(path)
    out = d.R / cfg['batch_id']
    out.mkdir(exist_ok=True)
    if (out / 'CLAIM.json').exists():
        return dict(status='existing_claim_no_restart', claim=d.load(out / 'CLAIM.json'))
    d.authorize(admission=True)
    with (out / 'supervisor.log').open('a') as log:
        proc = subprocess.Popen(['/usr/bin/python', str(Path(__file__).resolve()), 'supervise', '--batch', path],
                                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return dict(status='launched', process=d.identity(proc.pid), output=str(out))

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['start', 'supervise', 'run'])
    p.add_argument('--batch', required=True)
    args = p.parse_args()
    try:
        value = globals()[args.command](str(Path(args.batch).resolve()))
        if isinstance(value, dict):
            print(json.dumps(value, indent=2))
        else:
            sys.exit(value)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
