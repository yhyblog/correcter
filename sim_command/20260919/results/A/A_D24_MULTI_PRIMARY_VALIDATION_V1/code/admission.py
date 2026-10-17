"""Finite multi-primary authorization, source identity and physical admissions."""
import datetime
import errno
import fcntl
import hashlib
import json
import os
import socket
import time
from pathlib import Path
from paths import ROOT,CAMPAIGN,WORKSPACE,AUTH_SHA,TASK
from qio import read,sha,new_json,atomic_json,utc

HOST='trial-303224955-trialrun-303224955-worker-0'

def bounded_read(reader,seconds=30):
    end=time.monotonic()+seconds
    while True:
        try:return reader()
        except (OSError,json.JSONDecodeError) as error:
            if isinstance(error,OSError) and error.errno not in (errno.ENOENT,errno.ESTALE,errno.EIO,errno.EAGAIN,errno.ETIMEDOUT):raise
            if time.monotonic()>=end:raise RuntimeError('required metadata unavailable after bounded read') from error
            time.sleep(min(.25,max(0,end-time.monotonic())))

def authority():
    p=CAMPAIGN/'deadline_20260924/MULTI_PRIMARY_VALIDATION_AUTHORIZATION_V1.json'
    raw=bounded_read(p.read_bytes)
    if hashlib.sha256(raw).hexdigest()!=AUTH_SHA:raise RuntimeError('multi-primary authority identity changed')
    doc=json.loads(raw)
    ctl=bounded_read(lambda:read(CAMPAIGN/'persistent_queue/CONTROL.json'))
    root=bounded_read(lambda:read(CAMPAIGN/'CONTROL.json'));node=ctl['nodes']['A'];a=doc['nodes']['A']
    if (socket.gethostname()!=HOST or doc['status']!='released' or a['task_id']!=TASK or a['revision']!=1
        or ctl.get('global_stop') or root.get('stop_requested') or not node['enabled']
        or any(ref.get('sha256')!=AUTH_SHA for ref in (ctl.get('active_multi_primary_validation',{}),root.get('active_multi_primary_validation',{}),node.get('priority_authorization',{})))
        or a['stage_attempt_cap']!=9500 or a['cumulative_attempt_cap']!=25000):
        raise RuntimeError('multi-primary authority inactive or changed')
    if (ROOT/'STOP.json').exists():raise RuntimeError('local stop requested')
    return doc

def before_cutoff():
    end=datetime.datetime.fromisoformat(read(ROOT/'config/CONFIG.json')['deadline_utc'].replace('Z','+00:00')).timestamp()
    timer=ROOT/'RUN_TIME_BUDGET.json'
    if timer.exists():end=min(end,read(timer)['absolute_end_unix'])
    return time.time()<end and not (ROOT/'STOP.json').exists()

_INDEX=None
_SOURCES=None
def frozen_jobs():
    global _INDEX,_SOURCES
    if _INDEX is None:
        rows=read(ROOT/'JOB_INDEX.json')['jobs'];_INDEX={j['job_id']:j for j in rows}
        if len(rows)!=len(_INDEX) or len(rows)!=1010:raise ValueError('job index identity')
        _SOURCES=read(ROOT/'SOURCE_INDEX.json')['source_sets']
    return _INDEX

def validate_job(job):
    index=frozen_jobs();cfg=read(ROOT/'config/CONFIG.json')
    if job['job_id'] not in index or sha(index[job['job_id']]['path'])!=index[job['job_id']]['sha256']:raise ValueError('unregistered/changed job')
    if job!=read(index[job['job_id']]['path']) or job['configuration_sha256']!=sha(ROOT/'config/CONFIG.json'):raise ValueError('job/config identity changed')
    cell=next(c for c in cfg['cells'] if c['cell_id']==job['cell_id'])
    if any(job[k]!=v for k,v in cell.items()) or job['retry']!=0:raise ValueError('cell/retry identity')
    canonical={s['source_id']:s for s in _SOURCES[job['stage']]}
    if not job['sources'] or any(s!=canonical.get(s['source_id']) or s['task']!=job['task'] for s in job['sources']):raise ValueError('source identity changed')
    if job.get('numeric_config') and sha(job['numeric_config'])!=job['numeric_config_sha256']:raise ValueError('E1 ensemble config changed')
    return cfg

def unit_id(source,job):return job['cell_id']+'__'+source['source_id']

def admit_episode(source,job):
    authority();validate_job(job)
    if source not in job['sources']:raise ValueError('source outside frozen job')
    uid=unit_id(source,job)
    with Path('/tmp/corrector_A_D24_multi_primary_attempt.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not before_cutoff():raise RuntimeError('new-stage admission time exhausted')
        counter=ROOT/'ATTEMPT_COUNTER.json';n=read(counter)['count'] if counter.exists() else 0
        if n>=9500 or 14376+n>=25000 or n>=8800:raise RuntimeError('stage/node/first-entry cap exhausted')
        record=dict(unit_id=uid,task_id=TASK,cell_id=job['cell_id'],source=source,H=job['H'],mode=job['mode'],branch=job['method'],stage=job['stage'],loss=job['loss'],fit_seed=job['fit_seed'],attempt=0,stage_ordinal=n+1,node_cumulative_ordinal=14376+n+1,utc=utc(),retry=False)
        new_json(ROOT/'unit_claims'/(uid+'.json'),record)
        atomic_json(counter,dict(count=n+1,prior_D24_attempts=14376,node_cumulative=14376+n+1,stage_cap=9500,node_cap=25000,first_evaluation_cap=8800,utc=utc(),automatic_retry=False))
        return record

def resource_admission():
    info={}
    for line in open('/proc/meminfo'):
        f=line.split()
        if f[0] in ('MemTotal:','MemAvailable:'):info[f[0].rstrip(':')]=int(f[1])*1024
    required=(8*64+16)*1024**3
    if info.get('MemAvailable',0)<required:raise RuntimeError('insufficient ordinary RAM')
    st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize
    if free<20*1024**3:raise RuntimeError('insufficient space')
    return dict(host_memory=info,planning_not_measured_RAM_bytes=required,filesystem_available_bytes=free,filesystem_quota_proven=False,cgroup_hard_limit_bytes=None,CPU_affinity_count=len(os.sched_getaffinity(0)),new_gpu_probe=False)

def worker_environment(base,work):
    env=dict(os.environ)
    if env.get('NVIDIA_VISIBLE_DEVICES')!=base['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:raise ValueError('visibility changed')
    env.update(base['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=base['hf_home'],OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',LP_NUM_THREADS='4',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',CUDA_CACHE_DISABLE='1',TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),XDG_RUNTIME_DIR=str(work/'xdg'),LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for k in ('LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE','MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH'):env.pop(k,None)
    return env
