import datetime
import fcntl
import os
import socket
import time
from pathlib import Path
from paths import ROOT,OLD_ROOT,CAMPAIGN,AUTH_SHA,TASK
from qio import read,sha,new_json,atomic_json,utc


def authority():
    p=CAMPAIGN/'deadline_20260924/TRIGGER_TIMING_MULTIPLICITY_AUTHORIZATION_V1.json'
    if sha(p)!=AUTH_SHA:raise RuntimeError('new trigger-mode authority identity changed')
    doc=read(p);ctl=read(CAMPAIGN/'persistent_queue/CONTROL.json');node=ctl['nodes']['A'];a=doc['nodes']['A']
    if (doc['status']!='released' or a['task_id']!=TASK or a['branch']!='Velocity' or a['host']!=socket.gethostname()
        or ctl.get('global_stop') or not node['enabled'] or read(CAMPAIGN/'CONTROL.json').get('stop_requested')
        or ctl.get('active_trigger_mode_authorization',{}).get('sha256')!=AUTH_SHA
        or node.get('priority_authorization',{}).get('sha256')!=AUTH_SHA):raise RuntimeError('trigger-mode authority inactive')
    return doc


def before_cutoff():
    end=datetime.datetime.fromisoformat(read(ROOT/'config/CONFIG.json')['deadline_utc'].replace('Z','+00:00')).timestamp()
    timer=ROOT/'RUN_TIME_BUDGET.json'
    if timer.exists():end=min(end,read(timer)['absolute_end_unix'])
    return time.time()<end and not (ROOT/'STOP.json').exists()


_SOURCES=None
_SCHEDULE=None
_PLAN=None
_ELIGIBLE=None

def recovery_plan():
    global _PLAN,_ELIGIBLE
    if _PLAN is None:
        _PLAN=read(ROOT/'RECOVERY_PLAN.json')
        _ELIGIBLE={x['unit_id']:x for x in _PLAN['eligible']}
        protected={x['unit_id'] for x in _PLAN['preserved_valid']}
        if (len(_ELIGIBLE)!=3784 or len(protected)!=1216 or protected&set(_ELIGIBLE)
            or _PLAN['old_attempts']!=1232 or _PLAN['prior_D24_attempts']!=9360
            or read(ROOT/'RUN_TIME_BUDGET.json')!=read(OLD_ROOT/'RUN_TIME_BUDGET.json')):
            raise RuntimeError('recovery identity/budget mismatch')
    return _PLAN,_ELIGIBLE

def validate_job(job):
    global _SOURCES,_SCHEDULE
    cfg=read(ROOT/'config/CONFIG.json')
    allowed={(x['mode'],x['H']):x['priority'] for x in cfg['cells']}
    if (job['method']!='Velocity' or (job['mode'],job['H']) not in allowed or
        job['priority']!=allowed[job['mode'],job['H']] or job['retry']!=0 or
        job['job_id']!=f"Velocity_{job['mode']}_H{job['H']:02d}_{job['task']}"):
        raise ValueError('not a frozen new trigger-mode unit')
    if job['configuration_sha256']!=sha(ROOT/'config/CONFIG.json'):raise ValueError('new config changed')
    if _SOURCES is None:
        if sha(ROOT/'config/TEST_SOURCES_V1.json')!=cfg['source_table_sha256']:raise ValueError('sources changed')
        if sha(ROOT/'config/RANDOM_ONCE_SCHEDULE_V1.json')!=cfg['random_schedule_sha256']:raise ValueError('schedule changed')
        _SOURCES=read(ROOT/'config/TEST_SOURCES_V1.json')['rows']
        _SCHEDULE={(x['source_id'],x['H']):x for x in read(ROOT/'config/RANDOM_ONCE_SCHEDULE_V1.json')['rows']}
        if len(_SOURCES)!=500 or len(_SCHEDULE)!=2500 or any(not 0<=x['ordinal']<10 for x in _SOURCES):raise ValueError('wrong source scope')
    plan,eligible=recovery_plan()
    exact=[s for s in _SOURCES if s['task']==job['task'] and f"{job['mode']}_H{job['H']:02d}_{s['source_id']}" in eligible]
    expected_attempts={s['source_id']:eligible[f"{job['mode']}_H{job['H']:02d}_{s['source_id']}"]['attempt'] for s in exact}
    if (job['sources']!=exact or not 1<=len(exact)<=10 or job['model_id']!=cfg['model_id']
        or job.get('source_attempts')!=expected_attempts or job.get('recovery')!='r3'):
        raise ValueError('source/model/retry mismatch or completed source replay')
    if job['random_schedule']!=[_SCHEDULE[s['source_id'],job['H']] for s in exact]:raise ValueError('random slot table mismatch')
    return cfg


def admit_episode(source,H,mode):
    """One frozen source entry, including at most one correction per interrupted unit."""
    plan,eligible=recovery_plan()
    uid=f"{mode}_H{H:02d}_{source['source_id']}"
    if uid not in eligible:raise RuntimeError('completed or undeclared recovery source rejected')
    selected=eligible[uid]
    if selected['task']!=source['task'] or selected['attempt'] not in (0,1):raise RuntimeError('source/retry identity')
    with Path('/tmp/corrector_A_D24_velocity_trigger_attempt.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not before_cutoff():raise RuntimeError('original admission time exhausted')
        cfg=read(ROOT/'config/CONFIG.json');counter=ROOT/'ATTEMPT_COUNTER.json'
        n=read(counter)['count'] if counter.exists() else plan['old_attempts']
        if n>=5500 or 9360+n>=18000 or n-plan['old_attempts']>=plan['expected_base_new_attempts']:
            raise RuntimeError('stage/node/recovery base attempt cap exhausted')
        record=dict(unit_id=uid,task_id=TASK,recovery='r3',source=source,H=H,mode=mode,branch='Velocity',attempt=selected['attempt'],
            stage_ordinal=n+1,node_cumulative_ordinal=9360+n+1,utc=utc(),retry=bool(selected['attempt']),classification=selected['classification'])
        new_json(ROOT/'unit_claims'/(uid+'.json'),record)
        atomic_json(counter,dict(count=n+1,recovery_entries=n+1-plan['old_attempts'],old_stage_attempts=plan['old_attempts'],prior_D24_attempts=9360,node_cumulative=9360+n+1,
            stage_cap=5500,node_cap=18000,recovery_base_cap=plan['expected_base_new_attempts'],utc=utc(),failures_and_retries_count=True))
        return record


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
        MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for k in ('LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE',
              'MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH'):env.pop(k,None)
    return env
