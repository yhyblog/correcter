"""Current L11 grant, finite unit claims, no old L01 selection dependency."""
import hashlib
import json
import os
import socket
import time
import fcntl
from pathlib import Path
from paths import ROOT, CAMPAIGN, CONFIG, AUTH_SHA
from qio import read, sha, new_json, atomic_json, utc, process_identity

class AdmissionStop(RuntimeError): pass
AdmissionClosed = AdmissionStop
_last = 0.
_units = None

def units():
    global _units
    if _units is None: _units = {u['unit_id']:u for u in read(ROOT/'SOURCE_INDEX.json')['units']}
    return _units

def authority():
    if not CONFIG.get('activation_finalized'):
        raise AdmissionStop('corrected continuation awaits predecessor exit and final budget')
    if not read(ROOT/'PREDECESSOR_EXIT_CHECK.json')['all_predecessor_processes_exited']:raise AdmissionStop('predecessor exit unproven')
    if (ROOT/'ENGINEERING_FAILURE.json').exists():raise AdmissionStop('recorded recovery fault; no additional entries')
    a = read(CONFIG['grant']); c = read(CAMPAIGN/'CONTROL.json'); q = read(CAMPAIGN/'persistent_queue/CONTROL.json')
    if sha(CONFIG['grant']) != AUTH_SHA or a['status'] != 'released': raise AdmissionStop('L11 grant changed')
    b=a['nodes']['B']
    if b['host'] != socket.gethostname() or b['thread_id'] != os.environ.get('CODEX_THREAD_ID'): raise AdmissionStop('B identity mismatch')
    if c.get('stop_requested') or q.get('global_stop') or not q['nodes']['B']['enabled']: raise AdmissionStop('live stop')
    next_task=read(CAMPAIGN/'nodes/B/NEXT_TASK.json')
    if (q['nodes']['B']['active_runtime_authorization']['sha256'] != AUTH_SHA
        or c.get('active_crossbase_H_sweep',{}).get('sha256') != AUTH_SHA
        or next_task['task_id'] != CONFIG['task_id']
        or next_task['authorization']['sha256'] != AUTH_SHA): raise AdmissionStop('crossbase authority superseded')
    if CONFIG['task_id'] not in c['allowed_task_ids'] or not c['formal_gpu_runs_enabled']:raise AdmissionStop('formal scope not enabled')
    if c['accepted_Post_selection']['chosen_loss'] != 'L11': raise AdmissionStop('L11 selection superseded')
    return a

def boundary(admission=False):
    global _last
    if time.monotonic()-_last > 5 or admission:
        authority(); _last=time.monotonic()
    if time.time() >= CONFIG['absolute_wall_deadline_unix']: raise AdmissionStop('finite wave wall deadline')
    if admission and time.time() >= CONFIG['admission_cutoff_unix']: raise AdmissionStop('new admission cutoff')

def before_cutoff(): return time.time() < CONFIG['absolute_wall_deadline_unix']
def admissions_allowed():
    try: boundary(True); return True
    except AdmissionStop: return False

def claim_unit(unit):
    boundary(True)
    if unit != units().get(unit['unit_id']): raise ValueError('unit differs from frozen B manifest')
    key=hashlib.sha256(unit['unit_id'].encode()).hexdigest()
    local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
    with (local/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        target=ROOT/'unit_claims'/(key+'.json')
        lineage=read(ROOT/'RECOVERY_MANIFEST.json')['units'][unit['unit_id']]
        for parent in CONFIG['parent_roots']:
            old_claim=Path(parent)/'unit_claims'/(key+'.json')
            if not old_claim.exists():continue
            if str(old_claim)!=lineage.get('previous_claim'):
                raise AdmissionStop('unit has an unrelated predecessor claim')
            previous=read(lineage['previous_result'])
            if previous['status']!='technical_failure' or previous['success'] is not None:
                raise AdmissionStop('valid or unknown predecessor cannot be replayed')
            if 'Inference tensors cannot be saved for backward' not in previous.get('error',''):
                raise AdmissionStop('recovery fault differs from frozen manifest')
        if target.exists(): raise AdmissionStop('existing unit claim; no implicit replay')
        counter=ROOT/'ATTEMPT_COUNTER.json';n=read(counter)['reserved_attempts'] if counter.exists() else 0
        if n>=CONFIG['stage_attempt_cap'] or CONFIG['planned_prior_attempts']+n>=CONFIG['node_cumulative_attempt_cap']:raise AdmissionStop('attempt cap')
        atomic_json(counter,dict(reserved_attempts=n+1,prior_B_attempts=CONFIG['planned_prior_attempts'],cumulative_B_reserved=CONFIG['planned_prior_attempts']+n+1,utc=utc()))
        row=dict(unit_id=unit['unit_id'],unit=unit,number=n+1,process=process_identity(),utc=utc(),attempt=lineage['attempt_ordinal'],lineage=lineage)
        new_json(target,row)
    return row

def resource_admission():
    return dict(utc=utc(),host=socket.gethostname(),cpu_affinity=len(os.sched_getaffinity(0)),capacity_evidence=str(ROOT/'CAPACITY_PREPARATION.json'),no_extra_GPU_preflight=True)

def worker_environment(base, work):
    env=dict(os.environ);env.update(base['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=base['hf_home'],OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',CUDA_CACHE_DISABLE='1',TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),XDG_RUNTIME_DIR=str(work/'xdg'),LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for k in ['LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE','MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH']:env.pop(k,None)
    return env
