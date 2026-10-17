"""CPU-only observer for one existing main wave. No GPU/job lifecycle mutations.

The caller supplies the already-running launch PID and both authorized Codex
thread IDs. This observer never launches/resumes simulation, trains, signals a
process, modifies a frozen file, or summarizes fastest-finished outcomes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid


PACKAGE = Path(__file__).resolve().parents[2]
ROOT = PACKAGE/'outputs/native10_training_20260916'
STATUS = PACKAGE/'coordination/NATIVE10_EXECUTOR_STATUS.json'
MODULE = 'experiments.native10_training_20260916.main_runner'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.writing.'+uuid.uuid4().hex)
    with temporary.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
        stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


def process_identity(pid):
    """Inspect only the supplied PID; never dump unrelated command lines."""
    try:
        path = Path('/proc')/str(pid)
        fields = (path/'stat').read_text().rsplit(')', 1)[1].split()
        args = [part.decode(errors='replace') for part in (path/'cmdline').read_bytes().split(b'\0') if part]
        return dict(pid=pid, start_ticks=int(fields[19]), state=fields[0], args=args)
    except (OSError, ValueError, IndexError):
        return None


def same_process(expected):
    actual = process_identity(expected['pid'])
    return actual is not None and actual['state'] != 'Z' and actual['start_ticks'] == expected['start_ticks']


def validate_launch_identity(launch, expected_ticks, config_path, bank_version, wave_id):
    if launch is None or launch['start_ticks'] != expected_ticks or launch['state'] == 'Z' or (
            MODULE not in launch['args'] or 'launch' not in launch['args'] or wave_id not in launch['args']
            or str(config_path) not in launch['args'] or bank_version not in launch['args']):
        raise ValueError('Supplied PID/start_ticks is not this existing main_runner launch process')


def jsonlines_snapshot(path, lock_path):
    """Readers share the writer's local lock, so appended lines are complete."""
    path = Path(path)
    if not path.exists():
        return []
    with Path(lock_path).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        return [json.loads(line) for line in path.read_text().splitlines() if line]


def sealed_json(folder, filename, protocols):
    """Cheap progress seal check; full branch validation belongs to the audit."""
    folder = Path(folder)
    if not (folder/'complete.json').exists():
        return None
    complete = read(folder/'complete.json')
    if complete.get('status') != 'complete' or complete.get('protocol_sha256') not in protocols:
        raise ValueError('Unexpected completed artifact protocol: '+str(folder))
    if complete.get('files', {}).get(filename) != sha(folder/filename):
        raise ValueError('Completed progress metadata SHA mismatch: '+str(folder))
    return read(folder/filename)


def fixed_cohort(config, bank_version):
    bank = config['main_collection']['banks'][bank_version]
    lookup = {case['episode_id']: case for case in config['episode_manifest']}
    primary = bank['episode_ids']
    if len(primary) != len(set(primary)) or any(lookup[key].get('replacement_of') for key in primary):
        raise ValueError('Watcher requires registered unique primary slots')
    training = [key for key in primary if lookup[key]['split'] == 'train']
    if len(training) < 50:
        raise ValueError('Round1 diagnostic requires at least 50 registered training slots')
    return lookup, list(primary), training[:50]


def holder_snapshot():
    path = Path('/tmp/gpu_occupancy_guard/status.json')
    try:
        value = read(path)
        freshness = max(0., time.time()-value['updated'])
        running = process_identity(value['pid']) is not None
        states = Counter(row['state'] for row in value['gpus'].values())
        return dict(source=str(path), snapshot_age_seconds=freshness, fresh=freshness <= 20,
                    guard_running=running, states=dict(states), holder_count=states.get('holder', 0),
                    all_eight_holders_reported=running and freshness <= 20 and states.get('holder', 0) == 8,
                    gpu_computation_launched_by_watcher=False)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return dict(source=str(path), status='unavailable', error_type=type(error).__name__,
                    all_eight_holders_reported=False, gpu_computation_launched_by_watcher=False)


def snapshot(config, bank_version, wave, root=ROOT):
    lookup, primary, first50 = fixed_cohort(config, bank_version)
    bank = config['main_collection']['banks'][bank_version]
    stage = bank['stage']; protocol = config['analysis_approval']['protocol_sha256']
    allowed = [protocol]+bank.get('allowed_source_protocol_sha256', [])
    completed, technical_errors = [], []
    for identity in primary:
        folder = root/'slot_resolution'/identity
        try:
            resolution = sealed_json(folder, 'resolution.json', allowed)
            if resolution is None:
                continue
            actual = resolution.get('resolved_episode_id')
            chain = [identity]+config['main_collection'].get('replacement_candidates', {}).get(identity, [])
            if actual not in chain or resolution.get('planned_slot_id') != identity or resolution.get('status') != 'resolved':
                raise ValueError('Invalid primary resolution')
            collection = root/'collections'/stage/bank_version/lookup[actual]['case_id']
            # Only hash this summary. No deserialization of success/label values.
            if not (collection/'complete.json').exists():
                continue
            sealed = read(collection/'complete.json')
            if sealed.get('protocol_sha256') != protocol or sealed.get('status') != 'complete' or (
                    sealed.get('files', {}).get('summary.json') != sha(collection/'summary.json')):
                raise ValueError('Collection completion metadata seal mismatch')
            completed.append(identity)
        except (OSError, ValueError, KeyError, TypeError) as error:
            technical_errors.append(dict(primary_id=identity, error_type=type(error).__name__, message=str(error)))
    ledger = jsonlines_snapshot(root/'budget/attempts.jsonl', '/tmp/corrector_native10_training_20260916_budget.lock')
    scenes = jsonlines_snapshot(root/'scene_registry/entries.jsonl', '/tmp/corrector_native10_scene_registry.lock')
    counts, kinds = Counter(), Counter()
    updates = 0
    for row in ledger:
        if row['resource'] == 'simulator_attempts':
            counts[row['stage']] += row['amount']
            if row['stage'] == stage:
                kinds[row['kind']] += row['amount']
        elif row['resource'] == 'training_updates':
            updates += row['amount']
    worker_failures = []
    for path in sorted((wave/'workers').glob('worker_*/failure.json')):
        failure = read(path)
        worker_failures.append(dict(path=str(path), error_type=failure.get('error_type'),
                                   message=str(failure.get('error', ''))[:400]))
    worker_states = [read(path) for path in (wave/'workers').glob('worker_*/status.json')]
    missing = [identity for record in worker_states for identity in record.get('missing_slot_ids', [])]
    source_rejections = []
    relevant_sources = {identity for primary_id in primary for identity in
                        [primary_id]+config['main_collection'].get('replacement_candidates', {}).get(primary_id, [])}
    for row in ledger:
        if row['kind'] != 'source_capture' or row['identity'] not in relevant_sources:
            continue
        rejection = root/'sources'/lookup[row['identity']]['case_id']/'rejection.json'
        if rejection.exists() and (rejection.parent/'complete.json').exists():
            value = sealed_json(rejection.parent, 'rejection.json', allowed)
            source_rejections.append(dict(episode_id=value['episode_id'], reason=value['reason'],
                                          budget_attempt=value['budget_attempt'], path=str(rejection)))
    accepted = [row for row in scenes if row['status'] == 'accepted']
    unique = {(row['task'], row['scene_fingerprint']) for row in accepted}
    done = set(completed)
    reserve_limit = config['budget']['stages']['technical_reserve']['simulator_attempts']
    limits = {key: value['simulator_attempts'] for key, value in config['budget']['stages'].items()}
    return dict(updated_at=utc(), stage=stage, bank_version=bank_version,
        planned_primary_slots=len(primary), completed_primary_slots=len(completed),
        completed_primary_ids=completed, completed_by_split=dict(Counter(lookup[key]['split'] for key in completed)),
        first50_training_primary_ids=first50, first50_complete_count=sum(key in done for key in first50),
        first50_all_complete=all(key in done for key in first50),
        global_simulator_attempts=sum(counts.values()), attempts_by_stage=dict(counts),
        stage_attempts=counts[stage], stage_attempts_limit=limits[stage], stage_attempt_kinds=dict(kinds),
        training_updates=updates, reserve_used=counts['technical_reserve'], reserve_limit=reserve_limit,
        reserve_remaining=reserve_limit-counts['technical_reserve'],
        budget_within_limits=sum(counts.values()) <= config['budget']['hard_total'] and
                             all(value <= limits.get(key, -1) for key, value in counts.items()),
        scene_records=len(scenes), scene_status_counts=dict(Counter(row['status'] for row in scenes)),
        accepted_scene_count=len(accepted), unique_task_scene_count=len(unique),
        duplicate_accepted_scenes=len(accepted)-len(unique),
        worker_status_counts=dict(Counter(row['status'] for row in worker_states)),
        missing_primary_slots=missing, worker_failures=worker_failures, metadata_errors=technical_errors,
        source_rejection_counts=dict(Counter(row['reason'] for row in source_rejections)),
        source_rejections=source_rejections,
        holder=holder_snapshot(), scientific_success_statistics_computed=False,
        completion_counter_scope='Sealed resolution and collection metadata only; full dataset audit remains required.')


def update_shared_status(progress, wave_id, phase, status_path=STATUS):
    """Merge only changing operational fields; preserve manifest/config metadata."""
    with Path('/tmp/corrector_native10_executor_status.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        value = read(status_path)
        if value.get('main_wave') not in (None, wave_id):
            raise ValueError('Another wave now owns shared executor status')
        value.update(updated_at=progress['updated_at'], new_simulator_attempts=progress['global_simulator_attempts'],
                     remaining_technical_reserve=progress['reserve_remaining'], main_runtime_progress=progress,
                     attempts_by_stage=progress['attempts_by_stage'],
                     main_complete_collections=progress['completed_primary_slots'],
                     state=phase, watcher_updates_operational_fields_only=True)
        gpu = dict(value.get('gpu_policy', {})); holder = progress['holder']
        if 'guard_running' in holder:
            gpu['guard_running'] = holder['guard_running']
            gpu['idle_holders'] = holder['holder_count']
        gpu['active_formal_wave'] = wave_id if phase == 'round1_collection_running' else None
        value['gpu_policy'] = gpu
        atomic(status_path, value)


def event(state, key, message):
    return state.setdefault('events', {}).setdefault(key, dict(message=message, recipients={}))


def integrity_problems(progress):
    problems = []
    if progress['worker_failures']:
        problems.append('worker_failures='+str(len(progress['worker_failures'])))
    if progress['metadata_errors']:
        problems.append('metadata_errors='+str(len(progress['metadata_errors'])))
    if progress['duplicate_accepted_scenes'] > 0:
        problems.append('duplicate_accepted_scenes='+str(progress['duplicate_accepted_scenes']))
    if not progress['budget_within_limits']:
        problems.append('budget_within_limits=false')
    if progress['training_updates'] > 0:
        problems.append('unexpected_training_updates='+str(progress['training_updates']))
    return problems


def deliver(state, path, targets, codex):
    for key, record in state.get('events', {}).items():
        for role, thread in targets.items():
            item = record['recipients'].get(role, {})
            if item.get('status') in ('sent', 'ambiguous') or time.time() < item.get('retry_after_unix', 0):
                continue
            # A watcher crash after dispatch leaves uncertain delivery. On resume
            # preserve that uncertainty instead of automatically sending twice.
            if item.get('status') == 'inflight':
                item.update(status='ambiguous', error='Watcher restarted during queue dispatch; inspect event ID before manual retry')
                atomic(path, state); continue
            item = dict(status='inflight', thread=thread, attempts=item.get('attempts', 0)+1, dispatched_at=utc())
            record['recipients'][role] = item; atomic(path, state)
            message = f"[native10 watcher {state['wave_id']}:{key}] {record['message']}"
            try:
                result = subprocess.run([codex, 'queue', '--thread', thread, '--message', message],
                                        text=True, capture_output=True, timeout=20)
                output = (result.stdout+'\n'+result.stderr)[-2000:]
                if result.returncode == 0 and re.search(r'Queued message \S+ for thread ', output):
                    item.update(status='sent', sent_at=utc(), response=output[-600:])
                else:
                    item.update(status='failed', returncode=result.returncode, error=output,
                                retry_after_unix=time.time()+60)
            except subprocess.TimeoutExpired:
                item.update(status='ambiguous', error='Queue timeout; delivery unknown, no automatic duplicate')
            except OSError as error:
                item.update(status='failed', error=str(error), retry_after_unix=time.time()+60)
            atomic(path, state)


def audit_tick(state, path, config_path, bank_version, folder, progress):
    audit = state.get('first50_audit')
    if audit is None and progress['first50_all_complete']:
        output = ROOT/'progress_audits'/('watcher_'+state['wave_id']+'_first50.json')
        log = folder/'first50_audit.log'
        if output.exists() or log.exists():
            raise FileExistsError('Unregistered first50 audit output; preserve it and inspect before retry')
        audit = dict(status='starting', output=str(output), log=str(log), started_at=utc(),
                     auditor_sha256=sha(Path(__file__).with_name('main_progress_audit.py')))
        state['first50_audit'] = audit; atomic(path, state)
        env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
                   PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='')
        with log.open('x') as stream:
            child = subprocess.Popen([sys.executable, '-m', 'experiments.native10_training_20260916.main_progress_audit',
                '--config', str(config_path), '--bank-version', bank_version, '--min-train', '50', '--output', str(output)],
                cwd=PACKAGE, env=env, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        identity = process_identity(child.pid)
        audit.update(status='running', process=identity, pid=child.pid); atomic(path, state)
    if audit is None or audit['status'] in ('complete', 'failed'):
        return
    output = Path(audit['output'])
    alive = audit.get('process') is not None and same_process(audit['process'])
    if alive:
        return
    if audit.get('pid'):
        try:
            os.waitpid(audit['pid'], os.WNOHANG)  # Reap only our audit, without signaling it.
        except ChildProcessError:
            pass
    try:
        result = read(output)
        if result.get('threshold_ready') is not True or result.get('scientific_summary_emitted') is not True:
            raise ValueError('Fixed50 audit did not emit the required complete-cohort diagnostic')
        if result.get('config_sha256') != state['config_sha256'] or result.get('minimum_training_slots') != 50 or (
                result.get('auditor_sha256') != audit['auditor_sha256']):
            raise ValueError('Fixed50 audit config/cohort size/code identity mismatch')
        audit.update(status='complete', finished_at=utc(), output_sha256=sha(output))
        event(state, 'first50_complete', '固定前50训练主槽已全部封存，独立诊断已生成：'+str(output)+
              '。请分析端审查；这是预登记训练开发诊断，不是独立验证成功。正式采集继续，未训练或启动下一阶段。')
    except (OSError, ValueError, KeyError) as error:
        audit.update(status='failed', finished_at=utc(), error_type=type(error).__name__, error=str(error))
        event(state, 'first50_audit_failed', '固定前50训练主槽已齐，但只读审计未通过/未生成完整结果。请查 '+
              audit['log']+'；保留原采集不变，不自动重跑仿真或启动训练。')
    atomic(path, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--bank-version', required=True)
    parser.add_argument('--wave-id', required=True)
    parser.add_argument('--wave-pid', type=int, required=True, help='Existing main_runner launch PID')
    parser.add_argument('--wave-start-ticks', type=int, required=True, help='Previously recorded /proc launch PID start_ticks')
    parser.add_argument('--analysis-thread', required=True)
    parser.add_argument('--executor-thread', required=True)
    parser.add_argument('--codex', default='codex')
    parser.add_argument('--interval', type=float, default=30.)
    args = parser.parse_args()
    if args.interval < 30 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', args.wave_id):
        parser.error('Use a safe wave ID and interval >=30 seconds')
    if args.analysis_thread == args.executor_thread:
        parser.error('Analysis and executor must be distinct authorized threads')
    config_path = args.config.resolve()
    if not config_path.is_relative_to((ROOT/'main_protocols').resolve()):
        parser.error('Observe only a separately frozen main config')
    config = read(config_path); bank = config['main_collection']['banks'][args.bank_version]
    if bank['stage'] != 'round1_labels' or bank['kind'] != 'labels13':
        parser.error('This watcher is restricted to the released round1 labels stage')
    from .protocol import require_stage_budget
    require_stage_budget(config, bank['stage'])
    wave = ROOT/'main_execution'/bank['stage']/args.bank_version/args.wave_id
    spec = read(wave/'wave_spec.json')
    if spec['config_sha256'] != sha(config_path) or spec['stage'] != bank['stage'] or spec['bank_version'] != args.bank_version:
        parser.error('Wave/config identity mismatch')
    _, primary, first50 = fixed_cohort(config, args.bank_version)
    folder = ROOT/'progress/watcher'/args.wave_id
    folder.mkdir(parents=True, exist_ok=True); state_path = folder/'state.json'
    lockname = hashlib.sha256(str(folder).encode()).hexdigest()
    with Path('/tmp/native10_watcher_'+lockname+'.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('An observer already owns this wave; no second watcher started')
        identity = dict(config_sha256=sha(config_path), bank_version=args.bank_version, wave_id=args.wave_id,
                        wave_pid=args.wave_pid, wave_start_ticks=args.wave_start_ticks, first50_training_primary_ids=first50,
                        planned_primary_ids=primary, analysis_thread=args.analysis_thread, executor_thread=args.executor_thread)
        if state_path.exists():
            state = read(state_path)
            if any(state.get(key) != value for key, value in identity.items()):
                raise ValueError('Watcher resume identity/cohort/notification targets changed')
        else:
            launch = process_identity(args.wave_pid)
            validate_launch_identity(launch, args.wave_start_ticks, config_path, args.bank_version, args.wave_id)
            state = dict(identity, started_at=utc(), launch_process=launch, events={}, observer_only=True)
            atomic(state_path, state)
        targets = dict(analysis=args.analysis_thread, executor=args.executor_thread)
        while True:
            try:
                if sha(config_path) != state['config_sha256']:
                    raise ValueError('Frozen watched config changed')
                progress = snapshot(config, args.bank_version, wave)
                problems = integrity_problems(progress)
                if problems:
                    event(state, 'runtime_integrity_alert', '运行中技术告警：'+', '.join(problems)+
                          '。请立即审查 '+str(folder/'latest.json')+'；watcher 未改动/暂停/终止任何采集进程。')
                launch_alive = same_process(state['launch_process'])
                result_path = wave/'launch_result.json'
                launch_result = read(result_path) if result_path.exists() else None
                ended = not launch_alive
                if ended and launch_result is None:
                    state.setdefault('exit_seen_unix', time.time())
                finalized = ended and (launch_result is not None or time.time()-state['exit_seen_unix'] >= 90)
                phase = 'round1_collection_running'
                if finalized:
                    success = launch_result is not None and launch_result.get('returncode') == 0
                    complete = progress['completed_primary_slots'] == len(primary) and not problems
                    phase = 'round1_collection_complete_pending_dataset_audit' if success and complete else 'round1_collection_failed_or_incomplete'
                update_shared_status(progress, args.wave_id, phase)
                atomic(folder/'latest.json', dict(progress, launch_process_alive=launch_alive,
                                                phase=phase, launch_result=launch_result))
                audit_tick(state, state_path, config_path, args.bank_version, folder, progress)
                if finalized:
                    # Give the guard one poll to publish restored holders. This
                    # observer only waits/reads; it never starts a holder.
                    state.setdefault('final_seen_unix', time.time())
                    guard_ready = progress['holder']['all_eight_holders_reported']
                    if guard_ready or time.time()-state['final_seen_unix'] >= 90:
                        event(state, 'wave_finished', f"首轮采集退出：{phase}；主槽 {progress['completed_primary_slots']}/{len(primary)}，"
                            f"全局尝试 {progress['global_simulator_attempts']}/50000，reserve {progress['reserve_used']}/{progress['reserve_limit']}，"
                            f"holder8恢复记录={guard_ready}。状态/错误证据：{folder/'latest.json'}。"
                            '请执行端和分析端进行真实 dataset 审计及阶段审查；未自动训练、恢复仿真或启动下一阶段。')
                        state['finalized'] = True
                atomic(state_path, state)
            except Exception as error:
                state['watcher_error'] = dict(at=utc(), error_type=type(error).__name__, message=str(error))
                event(state, 'observer_error', '只读 watcher 遇到错误，采集进程未被修改。请检查 '+str(state_path)+'；不能把该错误当作仿真结局。')
                atomic(state_path, state)
            deliver(state, state_path, targets, args.codex)
            audited = state.get('first50_audit', {}).get('status') not in ('starting', 'running')
            notifications_settled = all(record.get('recipients', {}).get(role, {}).get('status') in ('sent', 'ambiguous')
                for record in state.get('events', {}).values() for role in targets)
            if state.get('finalized') and audited and notifications_settled:
                state['observer_finished_at'] = utc(); atomic(state_path, state)
                return
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
