import datetime
import os
import socket
from paths import ROOT, CAMPAIGN, AUTH_SHA
from qio import read, sha

def authority():
    p=CAMPAIGN/'deadline_20260924/R_H_SWEEP_AUTHORIZATION_V1.json'
    if sha(p)!=AUTH_SHA:raise RuntimeError('R sweep authorization changed')
    doc=read(p);ctl=read(CAMPAIGN/'persistent_queue/CONTROL.json');rootctl=read(CAMPAIGN/'CONTROL.json');node=ctl['nodes']['B'];spec=doc['nodes']['B']
    task='B_D24_R_H20_H30_V1'
    if (doc['status']!='released' or spec['host']!=socket.gethostname() or ctl.get('global_stop') or rootctl.get('stop_requested') or not node['enabled'] or task not in rootctl['active_compute_task_ids'] or node.get('priority_authorization',{}).get('sha256')!=AUTH_SHA or spec['H']!=[20,30]):raise RuntimeError('B R sweep not currently authorized')
    cfg=read(ROOT/'config/CONFIG.json')
    if cfg['planned_prior_attempts']+cfg['stage_attempt_cap']>spec['node_cumulative_attempt_cap']:raise RuntimeError('cumulative attempt budget exhausted')
    return doc

def before_cutoff():
    end=datetime.datetime.fromisoformat(read(ROOT/'config/CONFIG.json')['deadline_utc'].replace('Z','+00:00'))
    return datetime.datetime.now(datetime.timezone.utc)<end and not (ROOT/'STOP.json').exists()

def validate_job(job):
    cfg=read(ROOT/'config/CONFIG.json')
    allowed={(x['method'],x['H']):x['priority'] for x in cfg['cells']}
    if ((job['method'],job['H']) not in allowed or job['priority']!=allowed[(job['method'],job['H'])] or
        job['retry']!=0 or job['job_id']!=job['method']+'_H'+str(job['H']).zfill(2)+'_'+job['task']):
        raise ValueError('not frozen main once cell')
    if job['configuration_sha256']!=sha(ROOT/'config/CONFIG.json') or job['source_table_sha256']!=sha(ROOT/'config/TEST_SOURCES_V1.json'):
        raise ValueError('small config/source changed')
    sources=read(ROOT/'config/TEST_SOURCES_V1.json')['rows']
    exact=[s for s in sources if s['task']==job['task'] and s['ordinal']<10]
    if job['sources']!=exact or len(exact)!=10 or job['model_id']!=cfg['model_id']:raise ValueError('main test source/model mismatch')
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

