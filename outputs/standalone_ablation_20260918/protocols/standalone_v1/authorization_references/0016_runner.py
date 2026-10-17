"""One frozen standalone wave; stage-specific workers and whole-wave GPU guard."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import traceback

from . import storage
from .collection import create_collector, stage_plan

CODE = Path(__file__).resolve().parent
MODULE = __package__+'.runner'


def component(value):
    if not isinstance(value, str) or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', value) is None:
        raise ValueError('Explicit safe stage/wave component required')
    return value


def worker_layout(config, stage, requested=None):
    count = stage_plan(config, stage).get('workers')
    if type(count) is not int or count not in (5, 32) or requested is not None and requested != count:
        raise ValueError('Worker count must equal the frozen stage plan (5 preflight or 32 formal)')
    return (1, 5) if count == 5 else (4, 8)


def verify_frozen(config_path, freeze_path, stage, workers=None):
    from .prepare import verify_frozen as verify
    config = verify(config_path, freeze_path, stage)
    worker_layout(config, stage, workers)
    return config


def assigned_slots(config, stage, rank, workers):
    copies, gpus = worker_layout(config, stage, workers)
    if type(rank) is not int or not 0 <= rank < copies*gpus:
        raise ValueError('Worker rank is outside the preregistered fixed partition')
    lookup = {row['episode_id']: row for row in config['episode_manifest']}
    return [lookup[key] for key in stage_plan(config, stage)['episode_ids'][rank::workers]]


def require_lifecycle():
    pid = os.getppid()
    for _ in range(64):
        if pid <= 1: break
        path = Path('/proc')/str(pid)
        try:
            args = (path/'cmdline').read_bytes().split(b'\0')
            names = [Path(x.decode(errors='replace')).name for x in args if x]
            if ('gpu_occupancy_guard.py' in names or 'gpu_occupancy_lifecycle.sh' in names) and b'run' in args:
                return
            pid = int((path/'stat').read_text().rsplit(')', 1)[1].split()[1])
        except (OSError, ValueError, IndexError): break
    raise RuntimeError('Real workers must descend from gpu_occupancy_lifecycle.sh run --')


def execution_root(stage, wave):
    return storage.ROOT/'execution'/component(stage)/component(wave)


def worker(args):
    config = verify_frozen(args.config, args.freeze, args.stage, args.workers)
    require_lifecycle()
    cases = assigned_slots(config, args.stage, args.rank, args.workers)
    folder = execution_root(args.stage, args.wave_id)/'workers'/f'worker_{args.rank:02d}'
    folder.mkdir(parents=True, exist_ok=False)
    begin = time.perf_counter(); started = datetime.now(timezone.utc).isoformat()
    collector, active, finished = None, None, []
    try:
        import torch
        torch.set_num_threads(config['cpu']['worker_threads']); torch.cuda.set_device(0)
        collector = create_collector(config, args.stage)
        storage.dump(folder/'loaded_model_identity.json', collector.loaded_identity)
        loaded = time.perf_counter()
        for active in cases:
            row = collector.collect_episode(active)
            if row.get('status') != 'complete' or row.get('episode_id') != active['episode_id']:
                raise ValueError('A failed/missing original source cannot be replaced or skipped')
            storage.dump(folder/'slots'/f"{active['episode_id']}.json", row)
            finished.append(row)
            print(json.dumps(dict(event='standalone_slot_complete', **row)), flush=True)
        storage.dump(folder/'status.json', dict(status='complete', stage=args.stage, wave_id=args.wave_id,
            rank=args.rank, workers=args.workers, started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
            config_sha256=storage.sha256(args.config), freeze_sha256=storage.sha256(args.freeze),
            protocol_sha256=config['analysis_approval']['protocol_sha256'],
            assigned_slot_ids=[c['episode_id'] for c in cases], completed_slot_records=len(finished),
            missing_slot_ids=[], loading_seconds=loaded-begin, wall_seconds=time.perf_counter()-begin,
            actual_branch_count=sum(r['actual_branch_count'] for r in finished),
            no_cut_sources=sum(r['no_cut'] for r in finished), source_capture_allowed=False,
            replacement_allowed=False, next_stage_automatically_started=False))
        storage.seal(folder, protocol_sha256=config['analysis_approval']['protocol_sha256'], role='standalone_worker')
    except BaseException as error:
        storage.dump(folder/'failure.json', dict(status='failed', error=repr(error), traceback=traceback.format_exc(),
            generation_failure_evidence=getattr(error, 'evidence', None),
            active_case=active, completed_slot_ids=[r['episode_id'] for r in finished],
            attempts_preserved=True, automatic_retry=False, source_capture_allowed=False, replacement_allowed=False))
        raise
    finally:
        if collector is not None: collector.engine.close()


def child_command(args, rank):
    return [sys.executable, '-u', '-m', MODULE, 'worker', '--config', str(Path(args.config).resolve()),
        '--freeze', str(Path(args.freeze).resolve()), '--stage', args.stage, '--wave-id', args.wave_id,
        '--rank', str(rank), '--workers', str(args.workers)]


def supervisor(args):
    config = verify_frozen(args.config, args.freeze, args.stage, args.workers)
    require_lifecycle(); copies, gpus = worker_layout(config, args.stage, args.workers)
    if type(args.gpu_rank) is not int or not 0 <= args.gpu_rank < gpus:
        raise ValueError('Unregistered GPU rank')
    folder = execution_root(args.stage, args.wave_id)/'worker_logs'; folder.mkdir(parents=True, exist_ok=True)
    processes, streams, previous = [], [], {}
    def interrupted(signum, frame): raise KeyboardInterrupt(f'signal {signum}')
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): previous[sig] = signal.signal(sig, interrupted)
    try:
        for copy in range(copies):
            rank = args.gpu_rank+gpus*copy
            stream = (folder/f'worker_{rank:02d}.log').open('x'); streams.append(stream)
            processes.append(subprocess.Popen(child_command(args, rank), stdout=stream, stderr=subprocess.STDOUT))
        while any(p.poll() is None for p in processes):
            if any(p.poll() not in (None, 0) for p in processes):
                raise RuntimeError('An owned standalone worker failed; no retry or next wave')
            time.sleep(.5)
        if any(p.returncode for p in processes): raise RuntimeError('Standalone worker failed')
    finally:
        # Only this supervisor's own children are stopped on failure.
        for p in processes:
            if p.poll() is None: p.terminate()
        for p in processes:
            try: p.wait(timeout=20)
            except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=10)
        for stream in streams: stream.close()
        for sig, handler in previous.items(): signal.signal(sig, handler)


def launch_spec(args):
    config = verify_frozen(args.config, args.freeze, args.stage, args.workers)
    copies, gpus = worker_layout(config, args.stage, args.workers); plan = stage_plan(config, args.stage)
    wave = component(args.wave_id); folder = execution_root(args.stage, wave)
    folder.mkdir(parents=True, exist_ok=False)
    jobs = [dict(devices=[gpu], command=['bash', str(CODE/'run_gpu.sh'), 'supervisor',
        '--config', str(Path(args.config).resolve()), '--freeze', str(Path(args.freeze).resolve()),
        '--stage', args.stage, '--wave-id', wave, '--gpu-rank', str(gpu), '--workers', str(args.workers)]) for gpu in range(gpus)]
    path = folder/'wave_spec.json'
    storage.dump(path, dict(hold_idle=False, log_root=str(folder/'supervisor_logs'), jobs=jobs,
        config_sha256=storage.sha256(args.config), freeze_sha256=storage.sha256(args.freeze), stage=args.stage,
        workers=copies*gpus, episode_ids=plan['episode_ids'], original_primary_slots=len(plan['episode_ids']),
        methods=plan['methods'], repeats=plan['repeats'], bank_mode=plan['bank_mode'],
        reference_methods=plan.get('reference_methods', []), ref_repeats=plan.get('ref_repeats', []),
        expected_attempts=plan['expected_attempts'], source_capture_allowed=False, replacement_allowed=False,
        assignment='original source order strided by rank; rank never enters random keys',
        whole_wave_reserves_all_eight_gpus=True, next_stage_automatically_started=False))
    return path


def launch(args):
    path = launch_spec(args); begin = time.perf_counter(); workspace = storage.PACKAGE.parent
    command = ['bash', str(workspace/'gpu_occupancy_lifecycle.sh'), 'run', '--',
        '/usr/bin/python', str(workspace/'ACT-RECAP/scripts/run_recap_gpu_wave.py'), '--spec', str(path)]
    try:
        completed = subprocess.run(command, cwd=storage.PACKAGE); rc = completed.returncode
    except BaseException as error:
        storage.dump(path.parent/'launch_failure.json', dict(error=repr(error), attempts_preserved=True, automatic_retry=False))
        raise
    storage.dump(path.parent/'launch_result.json', dict(status='complete' if rc == 0 else 'failed',
        returncode=rc, command=command, wall_seconds_including_lifecycle=time.perf_counter()-begin,
        lifecycle_covers_entire_wave=True, hold_idle=False, source_capture_allowed=False,
        replacement_allowed=False, attempts_preserved=True, automatic_retry=False,
        next_stage_automatically_started=False))
    return rc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('verify', 'launch-spec', 'launch', 'supervisor', 'worker'))
    parser.add_argument('--config', type=Path, required=True); parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--stage', required=True); parser.add_argument('--wave-id')
    parser.add_argument('--workers', type=int, required=True); parser.add_argument('--gpu-rank', type=int)
    parser.add_argument('--rank', type=int); args = parser.parse_args()
    if args.action != 'verify' and args.wave_id is None: parser.error('Explicit unique --wave-id required')
    if args.action == 'verify':
        config = verify_frozen(args.config, args.freeze, args.stage, args.workers)
        print(json.dumps(dict(status='passed', stage=args.stage, workers=args.workers,
            expected_attempts=stage_plan(config, args.stage)['expected_attempts'], real_work_started=False)))
    elif args.action == 'launch-spec': print(launch_spec(args))
    elif args.action == 'launch': raise SystemExit(launch(args))
    elif args.action == 'supervisor': supervisor(args)
    else: worker(args)


if __name__ == '__main__': main()
