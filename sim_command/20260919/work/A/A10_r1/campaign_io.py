from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import uuid

BASE = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
WORK = BASE / 'work/A/A10_r1'
RESULTS = BASE / 'results/A/A10'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path, data):
    path = Path(path)
    assert any(path.is_relative_to(BASE / p) for p in ('work/A', 'results/A', 'receipts/A', 'nodes/A'))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp.' + uuid.uuid4().hex)
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    os.replace(temp, path)


def preparation_gate():
    control = json.loads((BASE / 'CONTROL.json').read_text())
    release = json.loads((BASE / 'releases/P00_PREP_V1.json').read_text())
    assert not control['stop_requested'] and control['mode'] == 'prepare'
    assert 'A10' in control['allowed_task_ids'] and not control['formal_gpu_runs_enabled']
    assert all(v == 0 for v in control['current_compute_limits'].values())
    assert release['owner_hosts']['A10'] == platform.node()
    for reference in [release['contract'], release['data_log_contract'], release['task_briefs']['A10']]:
        assert sha(BASE / reference['path']) == reference['sha256']
    return control


def heartbeat(progress):
    control = preparation_gate()
    atomic(BASE / 'receipts/A/A10_HEARTBEAT.json', {
        'task_id': 'A10', 'revision': 1, 'role': 'A', 'hostname': platform.node(),
        'updated_at_utc': now(), 'status': 'running', 'progress': progress,
        'control_revision': control['revision'], 'pid': os.getpid(),
        'pid_scope': 'short_lived_preparation_writer',
        'process_start_ticks': Path('/proc/self/stat').read_text().split()[21],
        'resource_counts': {'simulator_attempts': 0, 'vla_sampling_calls': 0, 'optimizer_updates': 0, 'gpu_seconds': 0},
    })
