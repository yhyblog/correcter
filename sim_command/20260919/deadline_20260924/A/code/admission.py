import datetime
import os
import socket
from paths import ROOT, CAMPAIGN, AUTH_SHA
from qio import read, sha


def baseline_enabled(node):
    return node.get('priority_task') == 'A_D24_SPRINT_V1' or node.get('baseline_N_and_existing_jobs_continue') is True


def authority():
    p = CAMPAIGN / 'deadline_20260924/AUTHORIZATION_V1.json'
    if sha(p) != AUTH_SHA:
        raise RuntimeError('deadline authorization changed')
    doc = read(p)
    control = read(CAMPAIGN / 'persistent_queue/CONTROL.json')
    if (doc['status'] != 'released' or not doc['scientific_execution_authorized']
            or doc['nodes']['A']['owner_host'] != socket.gethostname()
            or control.get('global_stop') or not control['nodes']['A']['enabled']
            or not baseline_enabled(control['nodes']['A'])
            or control['nodes']['A']['deadline_authorization']['sha256'] != AUTH_SHA):
        raise RuntimeError('deadline task/host/authority inactive')
    explicit=read(ROOT/'USER_SCOPE_APPROVAL.json')['scope']
    if explicit != dict(model='pi05_MT50_SFT030000',resident_workers=8,tasks=50,test_sources_per_task=10,
            method='N',H=[10,30,50,20,40],max_episodes=2500,automatic_background_continuation=True,
            training=False,deletion=False,remaining475_collection=False):
        raise RuntimeError('explicit executor user scope differs')
    return doc


def before_cutoff():
    deadline = datetime.datetime.fromisoformat(read(ROOT/'config/CONFIG.json')['deadline_utc'].replace('Z', '+00:00'))
    return datetime.datetime.now(datetime.timezone.utc) < deadline and not (ROOT/'STOP.json').exists()


def validate_job(job):
    cfg = read(ROOT/'config/CONFIG.json')
    if (job['method'] != 'N' or job['H'] not in [10,30,50,20,40] or job['retry'] != 0
            or job['job_id'] != f'N_H{job["H"]:02d}_{job["task"]}'):
        raise ValueError('not an implemented frozen N setting')
    if job['configuration_sha256'] != sha(ROOT/'config/CONFIG.json') or job['source_table_sha256'] != sha(ROOT/'config/TEST_SOURCES_V1.json'):
        raise ValueError('small frozen config/source identity differs')
    table = read(ROOT/'config/TEST_SOURCES_V1.json')['rows']
    exact = [r for r in table if r['task'] == job['task'] and r['ordinal'] < 10]
    if job['sources'] != exact or len(exact) != 10 or job['model_id'] != cfg['model_id']:
        raise ValueError('test source/model mismatch')
    return cfg


def resource_admission():
    """One ordinary check; host availability is not a container hard limit."""
    info = {}
    for line in open('/proc/meminfo'):
        fields = line.split()
        if fields[0] in ('MemTotal:', 'MemAvailable:'):
            info[fields[0].rstrip(':')] = int(fields[1]) * 1024
    required = (8 * 64 + 16) * 1024**3
    if info.get('MemAvailable', 0) < required:
        raise RuntimeError('insufficient RAM for requested eight resident workers')
    st = os.statvfs(ROOT)
    free = st.f_bavail * st.f_frsize
    if free < 20 * 1024**3:
        raise RuntimeError('insufficient ordinary free space for metrics and private temporary files')
    return dict(host_memory=info,planning_not_measured_RAM_bytes=required,
        cgroup_hard_limit_bytes=None,cgroup_missing_reason='controller not visible in earlier authorized observation',
        filesystem_available_bytes=free,filesystem_quota_proven=False,
        CPU_affinity_count=len(os.sched_getaffinity(0)),new_gpu_benchmark=False)


def worker_environment(base, work):
    env = dict(os.environ)
    if env.get('NVIDIA_VISIBLE_DEVICES') != base['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:
        raise ValueError('container visibility changed')
    env.update(base['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        HF_HOME=base['hf_home'],OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
        NUMEXPR_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',
        CUDA_CACHE_DISABLE='1',TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),
        LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',
        __EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for k in ('LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH'):
        env.pop(k,None)
    return env
