"""B-only finite LVM preflight R2. Authorization/identity paths use stdlib only."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[2]

class Refused(RuntimeError):
    pass

def require(ok, reason):
    if not ok:
        raise Refused(reason)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def timestamp(value):
    require(isinstance(value, str), 'release time missing')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise Refused('release time invalid') from error
    require(result.tzinfo is not None, 'release time must include timezone')
    return result

def covered(available, needed, scope):
    require(isinstance(available, dict), scope + ' caps missing')
    for key, amount in needed.items():
        cap = available.get(key, 0)
        require(type(cap) is int and cap >= 0 and cap >= amount, scope + ' insufficient/invalid cap: ' + key)

def metadata(control, board, release, config, *, host, relative_release, now):
    """Pure validation used by both production entry and CPU synthetic cases."""
    require(control.get('campaign_id') == board.get('campaign_id') == release.get('campaign_id') == config['campaign_id'], 'campaign mismatch')
    require(not control.get('stop_requested', True), 'CONTROL stop requested')
    require(control.get('formal_gpu_runs_enabled') is True, 'CONTROL formal execution disabled')
    require(release.get('status') == 'released', 'release is not released')
    require(release.get('kind') == 'formal_compute', 'wrong release kind')
    require(release.get('release_id') == config['compute_release_id'] == control.get('active_compute_release_id'), 'active release identity mismatch')
    require(control.get('active_compute_release') == relative_release, 'active release path mismatch')
    task_id = config['compute_task_id']
    require(control.get('active_compute_task_ids') == [task_id], 'active task must be unique B task')
    require(task_id in control.get('allowed_task_ids', []), 'task not allowed')
    require(not any(x.get('release_id') == release['release_id'] for x in control.get('closed_compute_releases', [])), 'release already closed')
    require(release.get('task_id') == task_id and release.get('task_revision') == config['compute_task_revision'], 'release task/revision mismatch')
    entries = [entry for entry in board.get('tasks', []) if entry.get('id') == task_id]
    require(len(entries) == 1, 'task board task missing/duplicated')
    entry = entries[0]
    require(entry.get('owner') == release.get('owner') == 'B', 'task owner mismatch')
    require(entry.get('revision') == config['compute_task_revision'], 'board revision mismatch')
    require(entry.get('status') in ('ready', 'running'), 'board task not ready/running')
    require(entry.get('release') == relative_release, 'board release mismatch')
    require(host == config['hostname'] == release.get('hostname') == control.get('roles', {}).get('B', {}).get('hostname'), 'host mismatch')
    require(release.get('participating_hosts') == [host], 'only independent B-only wave supported')
    require(timestamp(release.get('valid_from_utc')) <= now < timestamp(release.get('expires_at_utc')), 'release not yet valid or expired')
    require(release.get('gpu') == config['gpu'], 'release GPU binding mismatch')
    require(release.get('job_id') == config['job_id'], 'job identity mismatch')
    require(release.get('retry_cap') == config['retry_cap'] == 0, 'no retry authorized')
    require(release.get('timeout_seconds') == config['timeout_seconds'] == 180 and release.get('termination_grace_seconds') == config['termination_grace_seconds'] == 20, 'timeout changed')
    caps = config['limits']
    require(all(type(value) is int and value >= 0 for value in caps.values()), 'config caps invalid')
    require(caps.get('model_initializations') == 1 and caps.get('model_gpu_inference_calls') == 2, 'LVM probe budget changed')
    require(all(value == 0 for key, value in caps.items() if key not in ('model_initializations', 'model_gpu_inference_calls')), 'nonprobe compute forbidden')
    require(release.get('limits') == caps, 'release caps differ from config')
    covered(control.get('current_compute_limits'), caps, 'CONTROL global')
    covered(control.get('per_task_compute_limits', {}).get(task_id), caps, 'CONTROL task')
    return entry

def parse_gpu_rows(text):
    rows = []
    for values in csv.reader(io.StringIO(text)):
        if not values:
            continue
        require(len(values) == 5, 'GPU identity query malformed')
        index, uuid, name, driver, pci = [value.strip() for value in values]
        require(index.isdigit() and uuid.startswith('GPU-'), 'GPU identity query incomplete')
        rows.append(dict(index=int(index), uuid=uuid, name=name, driver_version=driver, pci_bus_id=pci))
    return rows

def gpu_identity(rows, expected):
    require(len(rows) == 8 and len({row['uuid'] for row in rows}) == 8, 'expected eight unique host GPUs')
    matches = [row for row in rows if row['uuid'] == expected['uuid']]
    require(len(matches) == 1, 'selected GPU UUID absent/duplicated')
    found = matches[0]
    for key in ('name', 'driver_version', 'pci_bus_id'):
        require(found[key] == expected[key], 'GPU ' + key + ' mismatch')
    require(expected['cuda_visible_devices'] == expected['uuid'] and expected['logical_device'] == 'cuda:0', 'GPU visibility must bind full UUID to logical cuda:0')
    return found

def query_gpu():
    result = subprocess.run(['/usr/bin/nvidia-smi', '--query-gpu=index,uuid,name,driver_version,pci.bus_id', '--format=csv,noheader,nounits'], text=True, capture_output=True, timeout=20)
    require(result.returncode == 0, 'read-only GPU identity query failed: ' + result.stderr.strip()[:200])
    return parse_gpu_rows(result.stdout)

def files(package, config_path, release, config):
    package = Path(package).resolve()
    require(Path(config_path).resolve() == package / 'config.json', 'only frozen package config allowed')
    require(release.get('config_path') == str(Path(config_path).resolve()) and release.get('config_sha256') == sha(config_path), 'config path/SHA mismatch')
    manifest_path = package / 'CODE_SNAPSHOT.json'
    require(release.get('code_manifest_path') == str(manifest_path) and release.get('code_manifest_sha256') == sha(manifest_path), 'code manifest path/SHA mismatch')
    manifest = read(manifest_path)
    listed = set()
    for entry in manifest['files']:
        path = (package / entry['path']).resolve()
        require(path.is_relative_to(package), 'code manifest path escapes package')
        require(entry['path'] not in listed, 'duplicate code manifest file')
        listed.add(entry['path'])
        require(path.is_file() and sha(path) == entry['sha256'], 'code/config SHA changed: ' + entry['path'])
    require({'config.json', 'preflight.py', 'local_source_snapshot/siglip_dynamics_mlp.py', 'commands/run_preflight.sh'} <= listed, 'incomplete code manifest')
    require(release.get('inputs') == config['inputs'], 'release input identity mismatch')
    for name, entry in config['inputs'].items():
        path = Path(entry['path'])
        require(path.is_file() and path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], 'input identity changed: ' + name)
    model = Path(config['inputs']['model']['path']).resolve()
    require(model.name == 'best_cosine_model.pt' and Path(config['inputs']['model_config']['path']).resolve() == model.parent / 'config.json', 'LVM loader selection differs from pinned input')
    for entry in config['lifecycle_dependencies']:
        require(sha(entry['path']) == entry['sha256'], 'lifecycle dependency SHA changed')

def authorize(config_path, release_path, *, check_gpu=True):
    require(release_path is not None, 'an analysis-owned release path is required')
    path = Path(release_path).resolve()
    require(path.parent == (CAMPAIGN / 'releases').resolve(), 'release is outside analysis-owned releases')
    config = read(config_path)
    release = read(path)
    require(path.name == config['compute_release_id'] + '.json', 'release filename mismatch')
    metadata(read(CAMPAIGN / 'CONTROL.json'), read(CAMPAIGN / 'TASK_BOARD.json'), release, config,
             host=socket.gethostname(), relative_release=str(path.relative_to(CAMPAIGN)), now=datetime.now(timezone.utc))
    files(HERE, config_path, release, config)
    selected = gpu_identity(query_gpu(), config['gpu']) if check_gpu else None
    return config, release, selected

def atomic(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    with tmp.open('rb') as stream:
        os.fsync(stream.fileno())
    os.replace(tmp, path)

def execute(config_path, release_path):
    # No torch import, claim, model call or CUDA initialization precedes validation.
    config, release, selected = authorize(config_path, release_path)
    require(not any(name in sys.modules for name in ('torch', 'jax', 'cupy', 'tensorflow')), 'model runtime imported before UUID binding')
    output = Path(release['output_dir']).resolve()
    require(output.is_relative_to((CAMPAIGN / 'results/B').resolve()) and not output.exists(), 'output must be new B-owned directory')
    claims = CAMPAIGN / 'results/B/compute_claims'
    claims.mkdir(exist_ok=True)
    claim = claims / (release['release_id'] + '__' + config['job_id'] + '.json')
    with claim.open('x') as stream:
        json.dump({'release_id': release['release_id'], 'job_id': config['job_id'], 'pid': os.getpid(), 'hostname': socket.gethostname(), 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'output': str(output)}, stream)
        stream.flush(); os.fsync(stream.fileno())
    output.mkdir(parents=True, exist_ok=False)
    os.environ['CUDA_VISIBLE_DEVICES'] = config['gpu']['uuid']
    os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    release_sha = sha(release_path)
    counts = dict.fromkeys(config['limits'], 0)
    started = time.monotonic()
    status, error = 'running', None
    def save():
        atomic(output / 'status.json', {'status': status, 'error': error, 'resource_counts': counts, 'gpu_identity': selected, 'CUDA_VISIBLE_DEVICES': os.environ['CUDA_VISIBLE_DEVICES'], 'release_sha256': release_sha, 'elapsed_wall_seconds': time.monotonic() - started})
    def boundary():
        require(sha(release_path) == release_sha, 'release changed during work')
        metadata(read(CAMPAIGN / 'CONTROL.json'), read(CAMPAIGN / 'TASK_BOARD.json'), release, config,
                 host=socket.gethostname(), relative_release=str(Path(release_path).resolve().relative_to(CAMPAIGN)), now=datetime.now(timezone.utc))
        require(time.monotonic() - started < 180, 'job timeout')
        require(os.environ['CUDA_VISIBLE_DEVICES'] == config['gpu']['uuid'], 'GPU visibility changed')
    def charge(key):
        boundary()
        require(counts[key] < config['limits'][key], 'resource cap reached before operation')
        counts[key] += 1
        save()
    save()
    try:
        boundary()
        import numpy as np
        import torch
        spec = importlib.util.spec_from_file_location('r2_pinned_lvm', HERE / 'local_source_snapshot/siglip_dynamics_mlp.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        charge('model_initializations')
        predictor = module.SiglipDynamicsPredictor(Path(config['inputs']['model']['path']).parent, device='cuda:0')
        for _ in range(2):
            charge('model_gpu_inference_calls')
            prediction = predictor.predict_delta_z(np.zeros((256, 2048), np.float32), np.zeros(4, np.float32))
            require(prediction.shape == (256, 2048) and np.isfinite(prediction).all(), 'LVM output shape/finiteness check failed')
        torch.cuda.synchronize()
        status = 'complete'
    except BaseException as exc:
        status, error = 'failed', type(exc).__name__ + ': ' + str(exc)
        raise
    finally:
        save()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default=str(HERE / 'config.json'))
    parser.add_argument('--release')
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--verify-release-only', action='store_true')
    modes.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.verify_release_only:
        config, release, selected = authorize(args.config, args.release)
        print(json.dumps({'verified': True, 'release_id': release['release_id'], 'gpu_identity': selected, 'cuda_visible_devices_for_execution': config['gpu']['uuid'], 'model_runtime_imported': False, 'claim_created': False}))
    else:
        execute(args.config, args.release)

if __name__ == '__main__':
    try:
        main()
    except (Refused, OSError, KeyError, ValueError) as exc:
        print(json.dumps({'status': 'refused', 'reason': str(exc), 'no_automatic_retry': True}), file=sys.stderr)
        raise SystemExit(2)
