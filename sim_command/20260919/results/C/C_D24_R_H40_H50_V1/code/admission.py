"""C's released R supplement, exact sources, durable entry and bounded budgets."""
import datetime
import fcntl
import os
import socket
import time
from pathlib import Path
from paths import ROOT, CAMPAIGN, AUTH_SHA
from qio import read, sha, new_json, utc, process_identity

TASK = 'C_D24_R_H40_H50_V1'
_last = 0.
_doc = None

def authority():
    global _last, _doc
    if _doc is not None and time.monotonic() - _last < 10:
        return _doc
    p = CAMPAIGN/'deadline_20260924/R_H_SWEEP_AUTHORIZATION_V1.json'
    if sha(p) != AUTH_SHA:
        raise RuntimeError('R supplement authorization changed')
    doc = read(p)
    ctl = read(CAMPAIGN/'persistent_queue/CONTROL.json')
    node = doc['nodes']['C']
    ref = dict(path='deadline_20260924/R_H_SWEEP_AUTHORIZATION_V1.json', sha256=AUTH_SHA)
    identity = read(CAMPAIGN/'nodes/C/identity.json')
    if (doc['status'] != 'released' or node['task_id'] != TASK or node['H'] != [40, 50]
        or node['host'] != socket.gethostname() or ctl.get('global_stop')
        or not ctl['nodes']['C']['enabled'] or ref not in ctl['stage_authorizations']
        or identity['boot_id'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip()):
        raise RuntimeError('C R authorization, host or boot mismatch')
    _doc, _last = doc, time.monotonic()
    return doc

def before_cutoff():
    end = datetime.datetime.fromisoformat(read(ROOT/'config/CONFIG.json')['deadline_utc'].replace('Z', '+00:00'))
    return datetime.datetime.now(datetime.timezone.utc) < end and not (ROOT/'STOP.json').exists()

def validate_job(job):
    cfg = read(ROOT/'config/CONFIG.json')
    allowed = {(x['method'], x['H']):x['priority'] for x in cfg['cells']}
    if ((job['method'], job['H']) not in allowed or job['priority'] != allowed[(job['method'], job['H'])]
        or job['retry'] != 0 or job['job_id'] != 'R_H'+str(job['H'])+'_'+job['task']):
        raise ValueError('Not an authorized first-entry C R job')
    if job['configuration_sha256'] != sha(ROOT/'config/CONFIG.json') or job['source_table_sha256'] != sha(ROOT/'config/TEST_SOURCES_V1.json'):
        raise ValueError('Frozen small config/source table changed')
    exact = [s for s in read(ROOT/'config/TEST_SOURCES_V1.json')['rows'] if s['task'] == job['task'] and s['ordinal'] < 10]
    if job['sources'] != exact or len(exact) != 10 or job['model_id'] != cfg['model_id']:
        raise ValueError('Source/seed/model mismatch')
    return cfg

def claim_episode(source, H, method, out):
    authority()
    if not before_cutoff():
        raise RuntimeError('C episode admission cutoff/STOP')
    if method != 'R' or H not in (40, 50):
        raise ValueError('Wrong C cell')
    rows = read(ROOT/'config/TEST_SOURCES_V1.json')['rows']
    if source not in rows or source['ordinal'] >= 10 or source['split'] != 'test':
        raise ValueError('Unregistered source')
    folder = ROOT/'unit_claims'
    with (folder/'admission.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        count = len(list(folder.glob('*.json')))
        if count >= 1000 or count >= 1100 or 1013 + count >= 2400:
            raise RuntimeError('C first-entry/stage/cumulative attempt cap')
        new_json(folder/(f'R_H{H}__{source["source_id"]}__attempt1.json'),
                 dict(source=source, method=method, H=H, attempt=1, retry=False,
                      output=str(out), process=process_identity(), utc=utc()))

def resource_admission():
    info = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        fields = line.split()
        if fields[0] in ('MemTotal:', 'MemAvailable:'):
            info[fields[0].rstrip(':')] = int(fields[1])*1024
    required = (8*64 + 16)*1024**3
    if info.get('MemAvailable', 0) < required:
        raise RuntimeError('Insufficient ordinary RAM for eight resident workers')
    st = os.statvfs(ROOT)
    if st.f_bavail*st.f_frsize < 20*1024**3:
        raise RuntimeError('Insufficient disk space')
    return dict(host_memory=info, planning_RAM_bytes=required, CPU_affinity_count=len(os.sched_getaffinity(0)),
                filesystem_available_bytes=st.f_bavail*st.f_frsize, new_GPU_probe=False,
                cgroup_limit='not exposed; see INITIAL_RESOURCES.json')

def worker_environment(base, work):
    env = dict(os.environ)
    if env.get('NVIDIA_VISIBLE_DEVICES') != base['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:
        raise ValueError('Container GPU visibility changed')
    env.update(base['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HOME=base['hf_home'],
               OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', OPENBLAS_NUM_THREADS='4', NUMEXPR_NUM_THREADS='4',
               TOKENIZERS_PARALLELISM='false', PYTORCH_NVML_BASED_CUDA_CHECK='0', CUDA_CACHE_DISABLE='1',
               TMPDIR=str(work/'tmp'), XDG_CACHE_HOME=str(work/'cache'), XDG_RUNTIME_DIR=str(work/'xdg'),
               LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'], MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl',
               __EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for k in ('LD_PRELOAD', '__EGL_VENDOR_LIBRARY_DIRS', 'MUJOCO_EGL_DEVICE_ID', 'PYTHONPATH',
              'LIBGL_ALWAYS_SOFTWARE', 'MESA_LOADER_DRIVER_OVERRIDE', 'GALLIUM_DRIVER', 'EGL_PLATFORM', 'LIBGL_DRIVERS_PATH'):
        env.pop(k, None)
    return env
