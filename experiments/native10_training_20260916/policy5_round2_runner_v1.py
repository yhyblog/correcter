"""Separately frozen A4000 policy5 wave; all execution uses existing-source guards.

No models, simulators, subprocesses or writes run on import. This launcher never
calls main_runner.resolve_slot/create_main_collector and never advances stages.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback

from . import main_runner as legacy
from .policy_deployment_round2_v1 import (STAGE, create_policy_collector,
                                   collect_existing_slot, validate_deployment_inputs)
from .storage import ROOT, PACKAGE, dump, seal, sha256


CODE = Path(__file__).resolve().parent
WORKSPACE = PACKAGE.parent
MODULE = __package__+'.policy5_round2_runner_v1'
REQUIRED_CODE = ('policy5_round2_runner_v1.py', 'run_policy5_round2_gpu_v1.sh',
                 'policy_deployment_round2_v1.py', 'policy5_round2_audit_v1.py',
                 'policy5_audit_v1.py')


def verify_frozen(config_path, freeze_path, stage, bank_version, workers=None):
    """Verify exact old implementation plus new guard/runner and input bindings."""
    if stage != STAGE or workers not in (None, 32):
        raise ValueError('This launcher permits only round2_development_policy with 32 workers')
    config = legacy.verify_frozen(config_path, freeze_path, stage, bank_version, workers)
    if legacy.worker_layout(config, workers) != (4, 32):
        raise ValueError('Approved policy5 deployment requires eight GPUs with four workers each')
    inputs = validate_deployment_inputs(config, bank_version)
    frozen = legacy._json(freeze_path)
    required = [CODE/name for name in REQUIRED_CODE]
    binding = config['policy_deployment']
    old = binding['old_collection']; training = Path(binding['selected_training']['path'])
    required += [Path(old['config_path']), Path(old['freeze_path']),
                 training/'complete.json', training/'result.json', training/'selected_reload_audit.json',
                 training/'selected/complete.json', training/'selected/config.json',
                 Path(binding['selected_training']['model_review']['path'])]
    for source in inputs['sources'].values():
        required += [Path(source['source_path'])/'complete.json', Path(source['resolution_path'])/'complete.json']
        if source['old_bank_path'] is not None:
            required.append(Path(source['old_bank_path'])/'complete.json')
    if any(str(path.resolve()) not in frozen['files'] for path in required):
        raise ValueError('Policy5 freeze omits guard/runner, selected training or original source/bank seals')
    return config


def execution_root(stage, bank_version, wave_id):
    if stage != STAGE:
        raise ValueError('Policy5 execution cannot enter another stage')
    return ROOT/'policy5_execution'/legacy._component(stage, 'stage')/legacy._component(bank_version, 'bank_version')/legacy._component(wave_id, 'wave_id')


def worker(args):
    config = verify_frozen(args.config, args.freeze, args.stage, args.bank_version, args.workers)
    legacy._require_lifecycle()
    selected = legacy.assigned_slots(config, args.bank_version, args.rank, args.workers)
    folder = execution_root(args.stage, args.bank_version, args.wave_id)/'workers'/f'worker_{args.rank:02d}'
    folder.mkdir(parents=True, exist_ok=False)
    begin, started = time.perf_counter(), datetime.now(timezone.utc).isoformat()
    collector, active, completed = None, None, []
    try:
        import torch
        torch.set_num_threads(config['cpu']['worker_threads'])
        torch.cuda.set_device(0)
        collector = create_policy_collector(config, args.stage, bank_version=args.bank_version)
        loaded = time.perf_counter()
        dump(folder/'loaded_critic_identity.json', collector.loaded_critic_identity)
        for active in selected:
            row = collect_existing_slot(collector, active)
            if (row.get('status') != 'complete' or row.get('planned_slot_id') != active['episode_id']
                    or row.get('resolved_episode_id') != active['episode_id'] or row.get('ordered_rejections') != []):
                raise ValueError('Policy5 slot was missing or replaced; fail without new capture')
            dump(folder/'slots'/f"{active['episode_id']}.json", row)
            completed.append(row)
            print(json.dumps(dict(event='policy5_slot_finished', **row), ensure_ascii=False), flush=True)
        dump(folder/'status.json', dict(status='complete', stage=args.stage, bank_version=args.bank_version,
            wave_id=args.wave_id, rank=args.rank, workers=args.workers, started_utc=started,
            finished_utc=datetime.now(timezone.utc).isoformat(), config_sha256=sha256(args.config),
            freeze_sha256=sha256(args.freeze), protocol_sha256=config['analysis_approval']['protocol_sha256'],
            assigned_slot_ids=[case['episode_id'] for case in selected], completed_slot_records=len(completed),
            missing_slot_ids=[], loading_seconds=loaded-begin, wall_seconds=time.perf_counter()-begin,
            actual_branch_count=sum(row['actual_branch_count'] for row in completed),
            no_cut_sources=sum(row['no_cut'] for row in completed), source_captures=0,
            attempted_replacement_records=0, guard_factory='create_policy_collector',
            slot_entry='collect_existing_slot', next_stage_automatically_started=False))
        seal(folder, protocol_sha256=config['analysis_approval']['protocol_sha256'], role='guarded_policy5_worker')
    except BaseException as error:
        dump(folder/'failure.json', dict(status='failed', error_type=type(error).__name__, error=str(error),
            traceback=traceback.format_exc(), utc=datetime.now(timezone.utc).isoformat(),
            active_primary_slot=active, completed_slots=completed, attempts_not_rolled_back=True,
            automatic_retry=False, source_capture_allowed=False, replacement_allowed=False,
            next_stage_automatically_started=False))
        raise
    finally:
        if collector is not None:
            collector.engine.close()


def _child_command(args, rank, workers):
    return [sys.executable, '-u', '-m', MODULE, 'worker',
        '--config', str(Path(args.config).resolve()), '--freeze', str(Path(args.freeze).resolve()),
        '--stage', args.stage, '--bank-version', args.bank_version, '--wave-id', args.wave_id,
        '--rank', str(rank), '--workers', str(workers)]


def supervisor(args):
    config = verify_frozen(args.config, args.freeze, args.stage, args.bank_version, args.workers)
    legacy._require_lifecycle()
    copies, workers = legacy.worker_layout(config, args.workers)
    if type(args.gpu_rank) is not int or not 0 <= args.gpu_rank < 8:
        raise ValueError('GPU supervisor rank must be 0..7')
    log_root = execution_root(args.stage, args.bank_version, args.wave_id)/'worker_logs'
    log_root.mkdir(parents=True, exist_ok=True)
    processes, streams, previous = [], [], {}
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'signal {signum}')
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous[sig] = signal.signal(sig, interrupted)
    try:
        for copy in range(copies):
            rank = args.gpu_rank+8*copy
            stream = (log_root/f'worker_{rank:02d}.log').open('x')
            streams.append(stream)
            processes.append(subprocess.Popen(_child_command(args, rank, workers), stdout=stream, stderr=subprocess.STDOUT))
        while any(process.poll() is None for process in processes):
            if any(process.poll() not in (None, 0) for process in processes):
                raise RuntimeError('An owned policy5 worker failed; preserve attempts and stop this wave')
            time.sleep(.5)
        if any(process.returncode for process in processes):
            raise RuntimeError('An owned policy5 worker failed')
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
    _, workers = legacy.worker_layout(config, args.workers)
    wave_id = args.wave_id or 'wave_'+str(time.time_ns())
    root = execution_root(args.stage, args.bank_version, wave_id)
    jobs = []
    for gpu in range(8):
        jobs.append(dict(devices=[gpu], command=['bash', str(CODE/'run_policy5_round2_gpu_v1.sh'), 'supervisor',
            '--config', str(Path(args.config).resolve()), '--freeze', str(Path(args.freeze).resolve()),
            '--stage', args.stage, '--bank-version', args.bank_version, '--wave-id', wave_id,
            '--gpu-rank', str(gpu), '--workers', str(workers)]))
    path = root/'wave_spec.json'
    dump(path, dict(hold_idle=False, log_root=str(root/'supervisor_logs'), jobs=jobs,
        config_sha256=sha256(args.config), freeze_sha256=sha256(args.freeze), stage=args.stage,
        bank_version=args.bank_version, workers=workers, expected_candidate_restores=95,
        expected_branches=1900, hard_attempt_limit=2100, original_sources=100,
        source_capture_allowed=False, replacement_allowed=False, guard_factory='create_policy_collector',
        assignment='original primary slot order strided by rank; worker rank never enters random seeds'))
    return path


def launch(args):
    path = launch_spec(args)
    begin = time.perf_counter()
    command = ['bash', str(WORKSPACE/'gpu_occupancy_lifecycle.sh'), 'run', '--',
        '/usr/bin/python', str(WORKSPACE/'ACT-RECAP/scripts/run_recap_gpu_wave.py'), '--spec', str(path)]
    completed = subprocess.run(command, cwd=PACKAGE)
    dump(path.parent/'launch_result.json', dict(status='complete' if completed.returncode == 0 else 'failed',
        returncode=completed.returncode, command=command, wall_seconds_including_lifecycle=time.perf_counter()-begin,
        lifecycle_covers_entire_wave=True, hold_idle=False, source_capture_allowed=False,
        replacement_allowed=False, policy5_artifact_audit_required=True, next_stage_automatically_started=False))
    return completed.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('verify', 'launch-spec', 'launch', 'supervisor', 'worker'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--stage', default=STAGE)
    parser.add_argument('--bank-version', required=True)
    parser.add_argument('--workers', type=int, default=32)
    parser.add_argument('--wave-id')
    parser.add_argument('--gpu-rank', type=int)
    parser.add_argument('--rank', type=int)
    args = parser.parse_args()
    if args.action in ('worker', 'supervisor') and args.wave_id is None:
        parser.error('worker/supervisor require an explicit wave-id')
    if args.action == 'verify':
        config = verify_frozen(args.config, args.freeze, args.stage, args.bank_version, args.workers)
        print(json.dumps(dict(status='passed', stage=args.stage, bank_version=args.bank_version,
            primary_slots=len(legacy.registered_slots(config, args.bank_version)), workers=32,
            real_work_started=False, guard_factory='create_policy_collector')))
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
