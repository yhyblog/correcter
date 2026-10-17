"""Exact recovery manifest, host-local claims and cumulative finite accounting."""
import fcntl,json,os,socket,time
from pathlib import Path
from paths import ROOT,CAMPAIGN,ORIGINAL,AUTH_SHA,TASK,CONFIG,SELECTION_SHA
from qio import read,sha,new_json,atomic_json,utc,process_identity,same_process

class AdmissionClosed(RuntimeError):pass
AdmissionStop=AdmissionClosed
_UNITS=None

def authority():
    p=Path(CONFIG['grant']);a=read(p)
    if sha(p)!=AUTH_SHA or a['status']!='released':raise AdmissionClosed('recovery authorization changed')
    node=a['nodes']['A']
    if node['task_id']!=TASK or node['host']!=socket.gethostname() or node['thread_id']!='01a0b91f-7443-71b1-915d-6cdb6d6a1a13':raise AdmissionClosed('A recovery identity mismatch')
    if sha(CAMPAIGN/'deadline_20260924/L11_RETEST_V1/L11_SELECTION_OVERRIDE.json')!=SELECTION_SHA:raise AdmissionClosed('fixed L11 selection changed')
    return a

def original_exit_verified():
    d=read(ORIGINAL/'RESULT.json');m=read(ORIGINAL/'chain/MANAGER_EXIT.json');ident=read(ORIGINAL/'STABLE_HANDOFF.json')['manager']
    if not d['all_owned_descendants_exited'] or not m['all_owned_processes_exited']:raise AdmissionClosed('old family exit unconfirmed')
    from process_family import group_members
    if same_process(ident) or group_members(ident['pgid'],ident['pid']):raise AdmissionClosed('old owned formal processes still live')

def before_cutoff():
    timer=ROOT/'RUN_TIME_BUDGET.json'
    end=read(timer)['absolute_end_unix'] if timer.exists() else CONFIG['absolute_wall_deadline_unix']
    return not (ROOT/'STOP.json').exists() and time.time()<end

def admissions_allowed():
    if not before_cutoff() or time.time()>=CONFIG['admission_cutoff_unix'] or (ROOT/'DRAIN.json').exists():return False
    c=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json')
    return not c.get('stop_requested') and not q.get('global_stop') and q['nodes']['A'].get('enabled') is True and all(x.get('active_L11_execution_recovery',{}).get('sha256')==AUTH_SHA for x in (c,q))

def boundary(admission=False):
    if not before_cutoff():raise AdmissionClosed('finite recovery stop/deadline')
    if admission and not admissions_allowed():raise AdmissionClosed('new recovery episode admission closed')

def frozen_units():
    global _UNITS
    if _UNITS is None:
        rows=[json.loads(x) for x in (ROOT/'UNITS.jsonl').read_text().splitlines()]
        _UNITS={u['unit_id']:u for u in rows}
        if len(_UNITS)!=1900 or any(u['owner']!='A' or u['H']!=10 for u in rows):raise ValueError('recovery unit inventory')
    return _UNITS

def claim_unit(unit):
    if unit!=frozen_units().get(unit['unit_id']):raise ValueError('unit not frozen recovery manifest')
    local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
    with (local/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);boundary(True)
        counter=ROOT/'ATTEMPT_COUNTER.json';n=read(counter)['count'] if counter.exists() else 0
        if n>=1900 or n>=2100 or 23396+n>=32300:raise AdmissionClosed('finite recovery attempt budget')
        target=ROOT/'unit_claims'/(unit['uid_hash']+'.json')
        if target.exists():raise AdmissionClosed('recovery already claimed; no implicit retry')
        if unit['recovery_reason']!='pre_Q_path_divergence_shared_renderer_risk_in_new_A_runner':raise ValueError('not an authorized invalid prior unit')
        claim=dict(unit_id=unit['unit_id'],uid_hash=unit['uid_hash'],source=unit['source'],cell_id=unit['cell_id'],method=unit['method'],mode=unit['mode'],H=10,loss='L11',fit_seed=9101,attempt=1,stage_ordinal=n+1,node_cumulative_ordinal=23397+n,utc=utc(),process=process_identity(),prior_result=unit['prior_result'],prior_disposition='quality_hold',recovery=True)
        new_json(target,claim)
        atomic_json(counter,dict(count=n+1,prior_A_attempts=23396,node_cumulative=23397+n,first_cap=1900,attempt_cap=2100,node_cap=32300,utc=utc()))
        return claim

def resource_admission():
    mem=dict(x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines());available=int(mem['MemAvailable'].split()[0])*1024
    st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize
    if available<768*1024**3 or free<40*1024**3 or len(os.sched_getaffinity(0))<208:raise AdmissionClosed('192-process ordinary resource admission limit')
    return dict(utc=utc(),RAM_available_bytes=available,RAM_planning_reserve_bytes=768*1024**3,planning_is_not_measured_peak=True,filesystem_available_bytes=free,CPU_affinity=len(os.sched_getaffinity(0)),cgroup_hard_limits=None,unknown_reason='ancestor controller files not mounted',model_processes=8,environment_processes=192,model_threads=2,environment_threads=1,no_GPU_preflight=True)

def worker_environment(base,work):
    env=dict(os.environ)
    if env.get('NVIDIA_VISIBLE_DEVICES')!=base['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:raise AdmissionClosed('GPU visibility changed')
    env.update(base['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=base['hf_home'],OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',CUDA_CACHE_DISABLE='1',TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),XDG_RUNTIME_DIR=str(work/'xdg'),LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for k in ['LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE','MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH']:env.pop(k,None)
    return env
