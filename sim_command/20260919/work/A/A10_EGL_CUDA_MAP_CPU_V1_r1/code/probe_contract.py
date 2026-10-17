"""CPU-only authority, immutable input verification and durable operation counts."""
from pathlib import Path
import hashlib
import json
import os
import re
import socket
import time
import uuid

TASK = 'A10_EGL_CUDA_MAP_GRAPHICS_PROBE_V1'
CAPS = dict(graphics_probe_attempts=1, egl_device_enumerations=1,
    egl_device_string_queries=8, probe_explicit_egl_get_proc_address_calls=5,
    egl_device_attribute_queries=8, cuda_driver_initializations=1, cuda_device_pci_queries=8,
    egl_error_queries=35, probe_explicit_driver_library_loads=2,
    probe_explicit_cuda_symbol_lookups=2, probe_explicit_egl_core_symbol_lookups=11,
    cuda_context_creations=0, cuda_kernel_launches=0, cuda_device_count_queries=0,
    cuda_uuid_queries=0, cuda_error_string_queries=0, egl_device_binary_queries=0, egl_drm_string_queries=0,
    egl_platform_display_calls=1, egl_initialize_calls=1,
    egl_choose_config_calls=1, egl_bind_api_calls=1,
    graphics_context_creations=1, egl_make_current_calls=2,
    egl_query_string_calls=2, probe_explicit_gl_string_queries=3,
    static_scene_constructions=1, static_scene_data_constructions=1,
    explicit_mj_forward_calls=1, mujoco_render_context_creations=1, mujoco_render_context_frees=1,
    mujoco_scene_updates=1, render_calls=1, rgb_readback_calls=1,
    egl_destroy_context_calls=1, egl_terminate_calls=1, egl_release_thread_calls=1,
    model_initializations=0, model_gpu_inference_calls=0,
    vla_sampling_calls=0, flow_forward_calls=0, simulator_attempts=0,
    metaworld_environment_instances=0, environment_reset_calls=0,
    physics_steps=0, env_steps=0, completed_rollouts=0, optimizer_updates=0)


class Refused(ValueError):
    pass


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write_new(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())


def current(campaign, release_path, release, proposal):
    campaign = Path(campaign).resolve()
    c = read(campaign / 'CONTROL.json')
    if c.get('stop_requested') or not c.get('formal_gpu_runs_enabled'):
        raise Refused('Current CONTROL does not authorize graphics execution')
    if c.get('mode') not in ('preflight', 'execute', 'run'):
        raise Refused('CONTROL mode is not a compute mode')
    if c.get('active_compute_release_id') != release['release_id']:
        raise Refused('Active release differs')
    if (campaign / c.get('active_compute_release', '')).resolve() != Path(release_path).resolve():
        raise Refused('Active release path differs')
    if TASK not in c.get('allowed_task_ids', []) or TASK not in c.get('active_compute_task_ids', []):
        raise Refused('Graphics task is not currently authorized')
    for key, value in CAPS.items():
        if c.get('current_compute_limits', {}).get(key, 0) < value:
            raise Refused('CONTROL budget too small: ' + key)
        per_task = c.get('per_task_compute_limits', {}).get(TASK, {})
        if per_task.get(key, 0) < value:
            raise Refused('Per-task CONTROL budget too small: ' + key)
    rows = [t for t in read(campaign / 'TASK_BOARD.json')['tasks'] if t['id'] == TASK]
    if len(rows) != 1:
        raise Refused('Exactly one graphics task board entry required')
    t = rows[0]
    if (t.get('owner'), t.get('revision')) != ('A', 1) or t.get('status') not in ('ready', 'released', 'running'):
        raise Refused('Task board owner/revision/status differs')
    if (campaign / t.get('release', '')).resolve() != Path(release_path).resolve():
        raise Refused('Task board release differs')
    if digest(release_path) != release['_sha256']:
        raise Refused('Release mutated during the wave')
    return c


def authorize(campaign, release_path, proposal_path):
    p = read(proposal_path); r = read(release_path)
    # Deny CPU preparation and stale releases before any external library work.
    if r.get('status') != 'released' or r.get('task_id') != TASK or r.get('task_revision') != 1:
        raise Refused('A new released graphics-only task is required')
    if r.get('role') != 'A' or r.get('hostname') != socket.gethostname():
        raise Refused('Released node identity differs')
    for k in ('run_id', 'wave_id', 'shard_id', 'release_id'):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', r.get(k, '')):
            raise Refused('Invalid unique identity: ' + k)
    if r.get('resource_caps') != CAPS or p.get('resource_caps') != CAPS:
        raise Refused('Finite graphics budget differs')
    for k, v in {'max_retries': 0, 'timeout_seconds': 120, 'kill_grace_seconds': 10,
                 'wave_participants': ['A'], 'renderer_route': 'NVIDIA_EGL'}.items():
        if r.get(k) != v or p.get(k) != v:
            raise Refused('Frozen field differs: ' + k)
    for k in ('gpu_uuid', 'gpu_index', 'gpu_model', 'driver', 'pci_bus_id'):
        if r.get(k) != p['device'][k]:
            raise Refused('Physical GPU identity differs: ' + k)
    p['_sha256'] = digest(proposal_path); r['_sha256'] = digest(release_path)
    if r.get('proposal_sha256') != p['_sha256']:
        raise Refused('Proposal SHA differs')
    current(campaign, release_path, r, p)
    root = Path(proposal_path).resolve().parent.parent
    if root != Path(p['published_root']).resolve():
        raise Refused('Use the published bundle location')
    manifest = root / 'BUNDLE_MANIFEST.json'
    if r.get('bundle_manifest_sha256') != digest(manifest) or p['bundle_manifest_sha256'] != digest(manifest):
        raise Refused('Bundle manifest differs')
    for entry in read(manifest)['files']:
        f = (root / entry['path']).resolve()
        if not f.is_relative_to(root) or digest(f) != entry['sha256']:
            raise Refused('Bundle file changed: ' + entry['path'])
    for e in read(root / 'EXTERNAL_SOURCE_MANIFEST.json')['files']:
        if str(Path(e['path']).resolve()) != e['realpath'] or digest(e['path']) != e['sha256']:
            raise Refused('Runtime file changed: ' + e['path'])
    return r, p


class Journal:
    def __init__(self, path, caps, gate=lambda: None):
        self.path = Path(path)
        self.path.open('x').close()
        self.caps = dict(caps); self.gate = gate
        self.counts = dict.fromkeys(caps, 0)

    def append(self, row):
        with self.path.open('a') as f:
            f.write(json.dumps(row, allow_nan=False) + '\n'); f.flush(); os.fsync(f.fileno())

    def call(self, key, fn, *, check=None, cleanup=False):
        if not cleanup:
            self.gate()
        if self.counts.get(key, 0) >= self.caps.get(key, 0):
            raise Refused('Operation cap exceeded before entry: ' + key)
        identity = dict(event_id=str(uuid.uuid4()), operation=key, resource_units={key: 1})
        self.append(dict(identity, phase='entered', monotonic_ns=time.monotonic_ns()))
        self.counts[key] += 1
        try:
            value = fn()
            if check is not None and not check(value):
                raise RuntimeError('Operation returned an invalid result: ' + key)
        except BaseException as e:
            self.append(dict(identity, phase='failed', error_type=type(e).__name__, error=str(e), monotonic_ns=time.monotonic_ns()))
            raise
        self.append(dict(identity, phase='returned', monotonic_ns=time.monotonic_ns()))
        return value


def reconcile(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    entered, terminal = {}, {}
    for row in rows:
        eid = row['event_id']
        if row['phase'] == 'entered':
            if eid in entered: raise Refused('Duplicate entry')
            entered[eid] = row
        else:
            if eid not in entered or eid in terminal or row['operation'] != entered[eid]['operation']:
                raise Refused('Invalid terminal identity')
            terminal[eid] = row
    counts = dict.fromkeys(CAPS, 0)
    for row in entered.values(): counts[row['operation']] += 1
    return dict(entered_budget_usage=counts, returned=sum(r['phase']=='returned' for r in terminal.values()),
        failed=sum(r['phase']=='failed' for r in terminal.values()), incomplete=len(entered)-len(terminal),
        missing_terminal_billing='Entered is charged once; terminal rows add zero; no refunds/retries')
