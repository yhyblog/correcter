import datetime
import os
import socket
from paths import ROOT,CAMPAIGN,AUTH_SHA,SUPPLEMENT_SHA
from qio import read,sha

def authority():
    p=CAMPAIGN/'deadline_20260924/CONTINUATION_AUTHORIZATION_20260922_V1.json'
    if sha(p)!=AUTH_SHA:raise RuntimeError('continuation authorization changed')
    doc=read(p);ctl=read(CAMPAIGN/'persistent_queue/CONTROL.json');node=ctl['nodes']['A']
    if (doc['status']!='released' or not doc['scientific_execution_authorized'] or
        doc['nodes']['A']['owner_host']!=socket.gethostname() or ctl.get('global_stop') or not node['enabled'] or
        ctl.get('deadline_continuation',{}).get('sha256')!=AUTH_SHA):
        raise RuntimeError('continuation authority inactive')
    supplement=CAMPAIGN/'deadline_20260924/GAF_INTERNAL_HOLDOUT_20260922_V1.json'
    if sha(supplement)!=SUPPLEMENT_SHA or read(supplement)['status']!='effective':
        raise RuntimeError('GAF internal holdout decision changed')
    if sha(ROOT/'config/TEST_SOURCES_V1.json')!=read(ROOT/'config/CONFIG.json')['test_source_sha256']:
        raise RuntimeError('frozen A500 test-source table changed')
    if sha(ROOT/'config/EVAL_SOURCES_V1.json')!=read(ROOT/'config/CONFIG.json')['eval_source_sha256']:
        raise RuntimeError('actual frozen500 evaluation source identity changed')
    return doc

def before_cutoff():
    end=datetime.datetime.fromisoformat(read(ROOT/'config/CONFIG.json')['deadline_utc'].replace('Z','+00:00'))
    return datetime.datetime.now(datetime.timezone.utc)<end and not (ROOT/'STOP.json').exists()

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

