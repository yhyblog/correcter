"""A00 read-only inventory helpers; writes only this campaign's A directories."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import platform
import uuid

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang')
BASE = ROOT / 'Corrector/sim_command/20260919'
WORK = BASE / 'work/A/A00_r1'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic(path, value):
    path = Path(path)
    assert any(path.is_relative_to(BASE / directory) for directory in
               ('work/A', 'receipts/A', 'nodes/A', 'results/A'))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp.' + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, path)


def progress(label):
    control = json.loads((BASE / 'CONTROL.json').read_text())
    assert not control['stop_requested'] and 'A00' in control['allowed_task_ids']
    # Re-read the current revision, validate A00's unchanged authorization, and
    # do not confuse another task's release with permission to compute in A00.
    assert isinstance(control['revision'], int) and control['mode'] == 'prepare'
    assert not control['formal_gpu_runs_enabled']
    assert all(value == 0 for value in control['current_compute_limits'].values())
    ack = json.loads((BASE / 'receipts/A/A00_ACK.json').read_text())
    assert set(ack['allowed_scope']).issubset(control['preparation_scope'])
    assert control['roles']['A']['hostname'] == ack['hostname']
    assert control['roles']['A']['executor_session_id'] == ack['executor_session_id']
    task_expected = next(x['sha256'] for x in ack['inputs_checked']
                         if x['path'].endswith('/tasks/A00.md'))
    assert hashlib.sha256((BASE / 'tasks/A00.md').read_bytes()).hexdigest() == task_expected
    atomic(BASE / 'receipts/A/A00_HEARTBEAT.json', {
        'campaign_id': control['campaign_id'], 'task_id': 'A00', 'revision': 1,
        'role': 'A', 'hostname': platform.node(), 'updated_at_utc': now(),
        'control_revision': control['revision'],
        'pid': os.getpid(), 'pid_scope': 'short_lived_cpu_inventory_writer',
        'process_start_ticks': Path('/proc/self/stat').read_text().split()[21],
        'progress': label, 'status': 'running',
        'resource_counts': {'simulator_attempts': 0, 'completed_rollouts': 0,
                            'vla_sampling_calls': 0, 'optimizer_updates': 0,
                            'gpu_seconds': 0},
    })


def save(name, data):
    atomic(WORK / name, {'checked_at_utc': now(), 'data': data})


def info(path, expected=None, hash_small=False):
    path = Path(path)
    result = {'path': str(path), 'exists': path.exists(),
              'is_symlink': path.is_symlink(), 'resolved': str(path.resolve()),
              'expected_sha256': expected, 'verified_sha256': None}
    if path.exists():
        stat = path.stat()
        result.update(kind='directory' if path.is_dir() else 'file',
                      bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)
        if path.is_file() and stat.st_size <= 16 * 1024 * 1024 and (expected or hash_small):
            result['verified_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    result['identity_status'] = ('missing' if not result['exists'] else
        'sha256_matched' if expected and expected == result['verified_sha256'] else
        'sha256_mismatch' if expected and result['verified_sha256'] else
        'small_file_sha256_observed' if result['verified_sha256'] else
        'exists_metadata_only')
    return result


def compact(value, depth=2):
    if isinstance(value, dict):
        if depth <= 0:
            return {'_keys': list(value)[:35], '_length': len(value)}
        return {k: compact(v, depth - 1) for k, v in value.items()}
    if isinstance(value, list):
        return {'_length': len(value), '_sample': [compact(x, depth - 1) for x in value[:3]]}
    return value[:700] + '…' if isinstance(value, str) and len(value) > 700 else value
