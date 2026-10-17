"""Explicit, frozen, stage-gated main waves; no simulator work runs on import.

The analysis-approved config supplies stage budgets and registered bank versions.
The launcher does not grant scopes, select a critic, choose concurrency or change
episode seeds. Eight GPU supervisors each own 1/2/4 workers according to frozen
``main_collection.concurrency.workers_per_gpu``. Primary slot assignment is a
fixed strided partition; all random streams are independent of worker rank.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import traceback

from .main_collection import MainSourceRejected, _require_main, _sealed, create_main_collector
from .storage import ROOT, PACKAGE, dump, seal, sha256


WORKSPACE = PACKAGE.parent
CODE = Path(__file__).resolve().parent


class SystemicInitializationFailure(RuntimeError):
    """Stop the full wave after a primary and two reserves share one reset error."""
    def __init__(self, primary_id, failure_chain):
        self.failure_chain = failure_chain
        super().__init__('Three identical consecutive pre-action reset failures for '+primary_id+
                         '; preserved failures require inspection before any new wave')


def _json(path):
    return json.loads(Path(path).read_text())


def _component(value, name):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', value):
        raise ValueError(name+' must be a safe single path component')
    return value


def _within_new_main(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()) or path.is_relative_to((ROOT/'p0').resolve()):
        raise ValueError('Main config/freeze must be a new output artifact outside frozen P0')
    return path


def worker_layout(config, workers=None):
    count = config.get('main_collection', {}).get('concurrency', {}).get('workers_per_gpu')
    if type(count) is not int or count not in (1, 2, 4):
        raise ValueError('Freeze measured workers_per_gpu as exactly 1, 2 or 4; no automatic choice')
    total = 8*count
    if workers is not None and (type(workers) is not int or workers != total):
        raise ValueError('Requested workers differ from frozen eight-GPU concurrency')
    return count, total


def registered_slots(config, bank_version):
    registration = config['main_collection']['banks'][bank_version]
    lookup = {case['episode_id']: case for case in config['episode_manifest']}
    slots = registration['episode_ids']
    if not slots or len(set(slots)) != len(slots):
        raise ValueError('Bank primary slots must be nonempty, unique and preregistered')
    if any(identity not in lookup or lookup[identity].get('replacement_of') for identity in slots):
        raise ValueError('Bank episode_ids must contain primary slots, not reserve identities')
    return [lookup[identity] for identity in slots]


def assigned_slots(config, bank_version, rank, workers):
    worker_layout(config, workers)
    if type(rank) is not int or not 0 <= rank < workers:
        raise ValueError('Worker rank outside frozen wave')
    return registered_slots(config, bank_version)[rank::workers]


def verify_frozen(config_path, freeze_path, stage, bank_version, workers=None):
    config_path, freeze_path = _within_new_main(config_path), _within_new_main(freeze_path)
    _component(stage, 'stage'); _component(bank_version, 'bank_version')
    config, frozen = _json(config_path), _json(freeze_path)
    _require_main(config, stage)
    registration = config['main_collection']['banks'][bank_version]
    if registration['stage'] != stage:
        raise ValueError('Bank version belongs to a different registered stage')
    worker_layout(config, workers)
    registered_slots(config, bank_version)
    files = frozen['files']
    required = [config_path]+[CODE/name for name in (
        'main_runner.py', 'run_main_gpu.sh', 'main_collection.py', 'scene_identity.py',
        'adapter.py', 'engine.py', 'commands.py', 'bank_audit.py', 'candidates13.py',
        'semantics.py', 'protocol.py', 'storage.py')]
    required += [WORKSPACE/'gpu_occupancy_lifecycle.sh', WORKSPACE/'gpu_occupancy_guard.py',
                 WORKSPACE/'ACT-RECAP/scripts/run_recap_gpu_wave.py']
    if any(str(path.resolve()) not in files for path in required):
        raise ValueError('Main freeze omits required config/code/lifecycle dependencies')
    for name, expected in files.items():
        if sha256(name) != expected:
            raise ValueError('Frozen main dependency changed: '+name)
    for name, identity in frozen.get('large_files_verified_once_then_stat', {}).items():
        stat = Path(name).stat()
        if not identity.get('verified_streaming_before_launch') or (
                stat.st_size != identity['bytes'] or stat.st_mtime_ns != identity['mtime_ns']
                or stat.st_ino != identity['inode'] or stat.st_dev != identity['device']):
            raise ValueError('Byte-verified large frozen asset changed: '+name)
    assets = Path(config.get('critic_assets', PACKAGE/'assets/critic')).resolve()
    ranking = _json(assets/'ranking.json')
    if ranking['model_hashes'] != registration['critic_member_hashes']:
        raise ValueError('Frozen critic ranking differs from bank registration')
    for path in [assets/'ranking.json']+[assets/f'models/refit/member_{member}/selected.pt' for member in ranking['model_hashes']]:
        if str(path) not in files:
            raise ValueError('New critic assets missing from main freeze')
    approval = config['analysis_approval']
    for path in (config['analysis_ready']['path'], approval['document_path']):
        if str(Path(path).resolve()) not in files:
            raise ValueError('Main freeze must include immutable stage READY and approval snapshot')
    return config


def _require_lifecycle():
    """Require an actual ancestor handoff, rather than an untrusted env flag."""
    pid = os.getppid()
    for _ in range(64):
        if pid <= 1:
            break
        path = Path('/proc')/str(pid)
        try:
            args = (path/'cmdline').read_bytes().split(b'\0')
            names = [Path(part.decode(errors='replace')).name for part in args if part]
            if ('gpu_occupancy_guard.py' in names or 'gpu_occupancy_lifecycle.sh' in names) and b'run' in args:
                return
            fields = (path/'stat').read_text().rsplit(')', 1)[1].split()
            pid = int(fields[1])
        except (OSError, ValueError, IndexError):
            break
    raise RuntimeError('Formal main workers must descend from gpu_occupancy_lifecycle.sh run -- ...')


@contextmanager
def _slot_lock(primary_id):
    folder = Path('/tmp/corrector_native10_main_slot_locks')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/(hashlib.sha256(primary_id.encode()).hexdigest()+'.lock')
    with path.open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('Registered slot already owned by another live worker') from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def resolve_slot(collector, primary):
    """Only initialization failure/duplicate-before-action activates backups."""
    cfg = collector.config
    lookup = {case['episode_id']: case for case in cfg['episode_manifest']}
    candidates = [primary['episode_id']]+cfg['main_collection'].get('replacement_candidates', {}).get(primary['episode_id'], [])
    rejections, reset_failures = [], []
    with _slot_lock(primary['episode_id']):
        for identity in candidates:
            case = lookup[identity]
            try:
                completed = collector.collect_episode(case)
            except MainSourceRejected as error:
                if error.before_first_action is not True or error.reason not in ('initialization_failed', 'duplicate_initial_scene'):
                    raise
                rejections.append(dict(episode_id=identity, reason=error.reason,
                                       budget_attempt=error.record['budget_attempt'], before_first_action=True))
                if error.reason == 'initialization_failed':
                    detail = error.record['details']
                    signature = (detail['exception'], detail['message'])
                    if reset_failures and reset_failures[-1]['signature'] != signature:
                        reset_failures = []
                    reset_failures.append(dict(episode_id=identity, budget_attempt=error.record['budget_attempt'],
                        signature=signature, rejection_path=str(ROOT/'sources'/identity/'rejection.json')))
                    if len(reset_failures) >= 3:
                        raise SystemicInitializationFailure(primary['episode_id'], reset_failures)
                else:
                    reset_failures = []
                continue
            summary = _json(completed/'summary.json')
            source = ROOT/'sources'/identity
            source_summary = _json(source/'summary.json')
            resolution = dict(status='resolved', planned_slot_id=primary['episode_id'], resolved_episode_id=identity,
                task=primary['task'], split=primary['split'], round=primary.get('round'),
                original_env_seed=primary['env_seed'], resolved_env_seed=case['env_seed'],
                source_seal_sha256=sha256(source/'complete.json'),
                source_protocol_sha256=_json(source/'complete.json')['protocol_sha256'],
                scene_fingerprint=source_summary['scene_fingerprint'], exact_state_sha256=source_summary['exact_state_sha256'],
                ordered_rejections=rejections, substitution_after_outcome_forbidden=True)
            folder = ROOT/'slot_resolution'/primary['episode_id']
            if folder.exists():
                existing = _json(folder/'resolution.json')
                _sealed(folder, [existing['source_protocol_sha256']])
                if existing != resolution:
                    raise ValueError('Primary slot resolved to a different source across banks/phases')
            else:
                folder.mkdir(parents=True)
                dump(folder/'resolution.json', resolution)
                seal(folder, protocol_sha256=resolution['source_protocol_sha256'])
            return dict(status='complete', planned_slot_id=primary['episode_id'], resolved_episode_id=identity,
                        completion_path=str(completed), completion_sha256=sha256(completed/'complete.json'),
                        resolution_path=str(folder), actual_branch_count=summary['actual_branch_count'],
                        no_cut=summary['no_cut'], ordered_rejections=rejections)
    # Never replace an ordinary failure, no-alarm source or unreachable cut.
    # Exhaustion is a visible coverage gap, not a fabricated unsuccessful state.
    return dict(status='missing_unique_initial_scene', planned_slot_id=primary['episode_id'],
                resolved_episode_id=None, ordered_rejections=rejections, outcome_unknown=True,
                distinct_state_requirement_satisfied=False)


def execution_root(stage, bank_version, wave_id):
    return ROOT/'main_execution'/_component(stage, 'stage')/_component(bank_version, 'bank_version')/_component(wave_id, 'wave_id')


def worker(args):
    config = verify_frozen(args.config, args.freeze, args.stage, args.bank_version, args.workers)
    _require_lifecycle()
    selected = assigned_slots(config, args.bank_version, args.rank, args.workers)
    folder = execution_root(args.stage, args.bank_version, args.wave_id)/'workers'/f'worker_{args.rank:02d}'
    folder.mkdir(parents=True, exist_ok=False)
    begin, started_utc = time.perf_counter(), datetime.now(timezone.utc).isoformat()
    collector, active, completed = None, None, []
    try:
        import torch
        torch.set_num_threads(config['cpu']['worker_threads'])
        torch.cuda.set_device(0)
        collector = create_main_collector(config, args.stage, bank_version=args.bank_version)
        loaded = time.perf_counter()
        for active in selected:
            row = resolve_slot(collector, active)
            dump(folder/'slots'/f"{active['episode_id']}.json", row)
            completed.append(row)
            print(json.dumps(dict(event='main_slot_finished', **row), ensure_ascii=False), flush=True)
        missing = [row['planned_slot_id'] for row in completed if row['status'] != 'complete']
        dump(folder/'status.json', dict(status='complete_with_missing_slots' if missing else 'complete',
            stage=args.stage, bank_version=args.bank_version, wave_id=args.wave_id, rank=args.rank, workers=args.workers,
            started_utc=started_utc, finished_utc=datetime.now(timezone.utc).isoformat(),
            config_sha256=sha256(args.config), freeze_sha256=sha256(args.freeze),
            protocol_sha256=config['analysis_approval']['protocol_sha256'],
            assigned_slot_ids=[case['episode_id'] for case in selected], completed_slot_records=len(completed),
            missing_slot_ids=missing, loading_seconds=loaded-begin, wall_seconds=time.perf_counter()-begin,
            attempted_replacement_records=sum(len(row['ordered_rejections']) for row in completed),
            independent_states_not_inferred_from_seed=True, next_stage_automatically_started=False))
        seal(folder, protocol_sha256=config['analysis_approval']['protocol_sha256'])
    except BaseException as error:
        dump(folder/'failure.json', dict(status='failed', error_type=type(error).__name__, error=str(error),
            traceback=traceback.format_exc(), utc=datetime.now(timezone.utc).isoformat(),
            active_primary_slot=active, completed_slots=completed,
            initialization_failure_chain=getattr(error, 'failure_chain', None),
            attempts_not_rolled_back=True, automatic_retry=False, outcome_based_replacement=False))
        raise
    finally:
        if collector is not None:
            collector.engine.close()


def supervisor(args):
    config = verify_frozen(args.config, args.freeze, args.stage, args.bank_version, args.workers)
    _require_lifecycle()
    copies, workers = worker_layout(config, args.workers)
    if type(args.gpu_rank) is not int or not 0 <= args.gpu_rank < 8:
        raise ValueError('GPU supervisor rank must be 0..7')
    root = execution_root(args.stage, args.bank_version, args.wave_id)
    log_root = root/'worker_logs'
    log_root.mkdir(parents=True, exist_ok=True)
    processes, streams = [], []
    previous = {}
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'signal {signum}')
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous[sig] = signal.signal(sig, interrupted)
    try:
        for copy in range(copies):
            rank = args.gpu_rank+8*copy
            stream = (log_root/f'worker_{rank:02d}.log').open('x')
            streams.append(stream)
            command = [sys.executable, '-u', '-m', __package__+'.main_runner', 'worker',
                '--config', str(Path(args.config).resolve()), '--freeze', str(Path(args.freeze).resolve()),
                '--stage', args.stage, '--bank-version', args.bank_version, '--wave-id', args.wave_id,
                '--rank', str(rank), '--workers', str(workers)]
            processes.append(subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT))
        while any(process.poll() is None for process in processes):
            if any(process.poll() not in (None, 0) for process in processes):
                raise RuntimeError('An owned main worker failed; inspect preserved attempt and failure records')
            time.sleep(.5)
        if any(process.returncode for process in processes):
            raise RuntimeError('An owned main worker failed')
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=10)
        for stream in streams:
            stream.close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def launch_spec(args):
    config = verify_frozen(args.config, args.freeze, args.stage, args.bank_version, args.workers)
    _, workers = worker_layout(config, args.workers)
    wave_id = args.wave_id or 'wave_'+str(time.time_ns())
    root = execution_root(args.stage, args.bank_version, wave_id)
    spec_path = root/'wave_spec.json'
    jobs = []
    for gpu in range(8):
        jobs.append(dict(devices=[gpu], command=['bash', str(CODE/'run_main_gpu.sh'), 'supervisor',
            '--config', str(Path(args.config).resolve()), '--freeze', str(Path(args.freeze).resolve()),
            '--stage', args.stage, '--bank-version', args.bank_version, '--wave-id', wave_id,
            '--gpu-rank', str(gpu), '--workers', str(workers)]))
    dump(spec_path, dict(hold_idle=False, log_root=str(root/'supervisor_logs'), jobs=jobs,
        config_sha256=sha256(args.config), freeze_sha256=sha256(args.freeze),
        stage=args.stage, bank_version=args.bank_version, workers=workers,
        assignment='registered primary slot order strided by rank; seeds never include worker rank'))
    return spec_path


def launch(args):
    # This is the sole direct launch path: the holder handoff surrounds the whole
    # eight-GPU wave, including supervisors whose individual workers finish early.
    spec = launch_spec(args)
    begin = time.perf_counter()
    command = ['bash', str(WORKSPACE/'gpu_occupancy_lifecycle.sh'), 'run', '--',
               '/usr/bin/python', str(WORKSPACE/'ACT-RECAP/scripts/run_recap_gpu_wave.py'), '--spec', str(spec)]
    completed = subprocess.run(command, cwd=PACKAGE)
    dump(spec.parent/'launch_result.json', dict(status='complete' if completed.returncode == 0 else 'failed',
        returncode=completed.returncode, wall_seconds_including_lifecycle=time.perf_counter()-begin,
        command=command, lifecycle_covers_entire_wave=True, hold_idle=False,
        worker_status_must_be_audited_for_missing_slots=True, next_stage_automatically_started=False))
    return completed.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('verify', 'launch-spec', 'launch', 'supervisor', 'worker'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--stage', required=True)
    parser.add_argument('--bank-version', required=True)
    parser.add_argument('--workers', type=int)
    parser.add_argument('--wave-id')
    parser.add_argument('--gpu-rank', type=int)
    parser.add_argument('--rank', type=int)
    args = parser.parse_args()
    if args.action in ('worker', 'supervisor') and (args.wave_id is None or args.workers is None):
        parser.error('worker/supervisor require explicit wave-id and frozen total workers')
    if args.action == 'verify':
        config = verify_frozen(args.config, args.freeze, args.stage, args.bank_version, args.workers)
        print(json.dumps(dict(status='passed', stage=args.stage, bank_version=args.bank_version,
            primary_slots=len(registered_slots(config, args.bank_version)), workers=worker_layout(config)[1],
            real_work_started=False)))
    elif args.action == 'launch-spec':
        print(launch_spec(args))
    elif args.action == 'launch':
        raise SystemExit(launch(args))
    elif args.action == 'supervisor':
        supervisor(args)
    else:
        worker(args)


if __name__ == '__main__':
    main()
