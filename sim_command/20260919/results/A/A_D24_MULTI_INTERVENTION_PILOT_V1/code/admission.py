import datetime
import os
import socket
from paths import ROOT, CAMPAIGN, AUTH_SHA
from qio import read, sha

def authority():
    p=CAMPAIGN/'deadline_20260924/MULTI_INTERVENTION_AUTHORIZATION_V2.json'
    if sha(p)!=AUTH_SHA: raise RuntimeError('pilot authorization changed')
    doc=read(p);ctl=read(CAMPAIGN/'persistent_queue/CONTROL.json');node=ctl['nodes']['A']
    if (doc['status']!='released' or not doc['scientific_compute_authorized_now'] or
        doc['owner_host']!=socket.gethostname() or ctl.get('global_stop') or not node['enabled'] or
        node.get('priority_authorization',{}).get('sha256')!=AUTH_SHA):
        raise RuntimeError('pilot host or authorization inactive')
    if sha(CAMPAIGN/doc['cohort']['path'])!=doc['cohort']['sha256']:raise RuntimeError('cohort changed')
    return doc

def before_cutoff():
    end=datetime.datetime.fromisoformat(read(ROOT/'config/CONFIG.json')['deadline_utc'].replace('Z','+00:00'))
    return datetime.datetime.now(datetime.timezone.utc)<end and not (ROOT/'STOP.json').exists()

def validate_job(job):
    cfg=read(ROOT/'config/CONFIG.json');sources=read(ROOT/'config/SOURCES.json')['sources']
    if (job['method'] not in cfg['methods'] or job['H']!=10 or job['retry']!=0 or len(job['sources'])!=1 or
        job['sources'][0] not in sources or job['sources'][0]['repeat_id']!=0 or
        job['job_id']!=job['method']+'__'+job['sources'][0]['source_id'] or
        job['configuration_sha256']!=sha(ROOT/'config/CONFIG.json') or
        job['source_table_sha256']!=sha(ROOT/'config/SOURCES.json') or job['model_id']!=cfg['model_id']):
        raise ValueError('not one registered old20 repeat0 pilot job')
    return cfg

def resource_admission():
    info={}
    for line in open('/proc/meminfo'):
        fields=line.split()
        if fields[0] in ('MemTotal:','MemAvailable:'):info[fields[0].rstrip(':')]=int(fields[1])*1024
    required=(8*64+16)*1024**3
    if info.get('MemAvailable',0)<required:raise RuntimeError('insufficient ordinary RAM')
    st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize
    if free<20*1024**3:raise RuntimeError('insufficient space')
    return dict(host_memory=info,planning_not_measured_RAM_bytes=required,filesystem_available_bytes=free,
        filesystem_quota_proven=False,cgroup_hard_limit_bytes=None,CPU_affinity_count=len(os.sched_getaffinity(0)),new_gpu_probe=False)

def worker_environment(base,work):
    env=dict(os.environ)
    if env.get('NVIDIA_VISIBLE_DEVICES')!=base['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:raise ValueError('visibility changed')
    env.update(base['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=base['hf_home'],
        OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',
        TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',CUDA_CACHE_DISABLE='1',
        TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],
        MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',
        __EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for k in ('LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE',
              'MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH'):env.pop(k,None)
    return env

