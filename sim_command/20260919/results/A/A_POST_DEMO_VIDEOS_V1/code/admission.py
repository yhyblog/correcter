"""Exact V2 demo ownership, small manifest checks and finite arm claims."""
import fcntl,json,os,socket,time
from pathlib import Path
from paths import ROOT,CAMPAIGN,ORIGINAL,AUTH_SHA,TASK,CONFIG,OUTPUT
from qio import read,sha,new_json,atomic_json,utc,process_identity,same_process
class AdmissionClosed(RuntimeError):pass
AdmissionStop=AdmissionClosed
_UNITS=None

def authority():
    p=Path(CONFIG['grant']);a=read(p)
    if sha(p)!=AUTH_SHA or a['status']!='released' or a['revision']!=2:raise AdmissionClosed('demo V2 authorization changed')
    n=a['nodes']['A']
    if n['task_id']!=TASK or n['host']!=socket.gethostname() or n['thread_id']!='01a0b91f-7443-71b1-915d-6cdb6d6a1a13':raise AdmissionClosed('A demo identity mismatch')
    if sha(ROOT/'CANDIDATES.jsonl')!=n['candidates']['sha256']:raise AdmissionClosed('demo candidate list changed')
    if a['Q_loss']!='L11' or a['Q_fit_seed']!=9101 or n['candidate_pairs']!=79:raise AdmissionClosed('demo scientific identity mismatch')
    return a

def original_exit_verified():
    d=read(ORIGINAL/'RESULT.json');m=read(ORIGINAL/'chain/MANAGER_EXIT.json');ident=read(ORIGINAL/'STABLE_HANDOFF.json')['manager']
    from process_family import group_members
    if not d['all_owned_descendants_exited'] or not m['all_owned_processes_exited'] or same_process(ident) or group_members(ident['pgid'],ident['pid']):raise AdmissionClosed('previous formal family has not exited')

def before_cutoff():
    timer=ROOT/'RUN_TIME_BUDGET.json'
    return not (ROOT/'STOP.json').exists() and (not timer.exists() or time.time()<read(timer)['compute_end_unix'])

def admissions_allowed():
    if not before_cutoff() or (ROOT/'DRAIN.json').exists():return False
    c=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json')
    return not c.get('stop_requested') and not q.get('global_stop') and q['nodes']['A'].get('enabled') is True and c.get('active_post_demo_video_authorization',{}).get('sha256')==AUTH_SHA

def boundary(admission=False):
    if not before_cutoff():raise AdmissionClosed('finite demo stop/deadline')
    if admission and not admissions_allowed():raise AdmissionClosed('new demo admission closed')

def frozen_units():
    global _UNITS
    if _UNITS is None:
        rows=[json.loads(x) for x in (ROOT/'UNITS.jsonl').read_text().splitlines()];_UNITS={u['unit_id']:u for u in rows}
        candidates={x['candidate_id']:x for x in map(json.loads,(ROOT/'CANDIDATES.jsonl').read_text().splitlines())}
        if len(_UNITS)!=158:raise ValueError('demo arm count')
        for u in rows:
            c=candidates[u['candidate_id']]
            if u['owner']!='A' or u['method'] not in ('N','Post') or any(u[k]!=c[k] for k in ('source_id','task','env_seed','policy_seed','H')):raise ValueError('demo arm outside frozen candidates')
    return _UNITS

def claim_unit(unit,attempt):
    if unit!=frozen_units().get(unit['unit_id']) or attempt not in (1,2):raise ValueError('arm/attempt not authorized')
    local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
    with (local/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);boundary(True)
        p=ROOT/'unit_claims'/unit['uid_hash']/('attempt_%d.json'%attempt)
        if p.exists():raise AdmissionClosed('arm already claimed; do not duplicate')
        if attempt==2:
            old=read(ROOT/'episodes'/unit['uid_hash']/'attempt_1/RESULT.json')
            if old['status']!='technical_failure' or not old.get('retry_allowed',False):raise AdmissionClosed('only specifically recoverable technical failure may retry')
        count=read(ROOT/'ATTEMPT_COUNTER.json')['count'] if (ROOT/'ATTEMPT_COUNTER.json').exists() else 0
        if count>=316:raise AdmissionClosed('demo technical attempt cap')
        row=dict(unit_id=unit['unit_id'],candidate_id=unit['candidate_id'],method=unit['method'],attempt=attempt,ordinal=count+1,utc=utc(),process=process_identity(),qualitative_only=True)
        new_json(p,row);atomic_json(ROOT/'ATTEMPT_COUNTER.json',dict(count=count+1,cap=316,first_arm_cap=158,scientific_evaluation_units=0,utc=utc()))
        return row

def resource_admission():
    m=dict(x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines());available=int(m['MemAvailable'].split()[0])*1024
    st=os.statvfs(OUTPUT);free=st.f_bavail*st.f_frsize;cpu=len(os.sched_getaffinity(0))
    cpu_arms=max(0,(cpu-24)//2);ram_arms=max(0,int((available-128*1024**3)//(4*1024**3)))
    pairs=min(96,cpu_arms//2,ram_arms//2,53)
    if pairs<8 or free<30*1024**3 or st.f_favail<5000:raise AdmissionClosed('insufficient ordinary capacity for eight useful GPUs')
    return dict(utc=utc(),RAM_available_bytes=available,CPU_affinity=cpu,filesystem_available_bytes=free,inodes_available=st.f_favail,capacity_pairs=pairs,active_arm_limit=2*pairs,requested_logical_target=192,candidate_primary_arms=106,CPU_formula='2 threads/arm plus24 reserved; pair both arms remain concurrent',RAM_reserve_per_arm_bytes=4*1024**3,reservations_not_measured_hard_limits=True,cgroup_limits=None,cgroup_reason='ancestor controllers not mounted',frame_stream_memory_bound='one480x480RGB frame per writer plus finite pipe/codec buffers',GPU_preflight=False)

def worker_environment(base,work):
    env=dict(os.environ)
    if env.get('NVIDIA_VISIBLE_DEVICES')!=base['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:raise AdmissionClosed('GPU visibility changed')
    env.update(base['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=base['hf_home'],OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',CUDA_CACHE_DISABLE='1',TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),XDG_RUNTIME_DIR=str(work/'xdg'),LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for k in ['LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE','MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH']:env.pop(k,None)
    return env
