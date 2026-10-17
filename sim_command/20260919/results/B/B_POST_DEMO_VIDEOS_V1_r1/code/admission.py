"""Finite explicitly authorized qualitative recording, separate from scientific units."""
import os, socket, time, hashlib, fcntl
from pathlib import Path
from paths import ROOT, CAMPAIGN, CONFIG, AUTH_SHA
from qio import read, sha, new_json, atomic_json, utc, process_identity
class AdmissionStop(RuntimeError):pass
AdmissionClosed=AdmissionStop
_last=0.
_units=None
def units():
 global _units
 if _units is None:_units={u['unit_id']:u for u in read(ROOT/'SOURCE_INDEX.json')['units']}
 return _units
def authority():
 if not CONFIG.get('activation_finalized'):raise AdmissionStop('activation not finalized')
 a=read(CONFIG['grant']);c=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json');b=q['nodes']['B']
 if sha(CONFIG['grant'])!=AUTH_SHA or a['status']!='released':raise AdmissionStop('demo grant changed')
 if a['task_type']!='qualitative_paired_video_capture' or not a['historical_completed_episode_recording_replay_explicitly_authorized']:raise AdmissionStop('not recording authority')
 if a['nodes']['B']['host']!=socket.gethostname() or a['nodes']['B']['thread_id']!=os.environ.get('CODEX_THREAD_ID'):raise AdmissionStop('B identity mismatch')
 if c.get('stop_requested') or q.get('global_stop') or not b['enabled']:raise AdmissionStop('live stop')
 if not c.get('formal_gpu_runs_enabled') or not c.get('demo_recording_admissions_enabled'):raise AdmissionStop('recording disabled')
 if b.get('priority_task')!=CONFIG['task_id'] or b['active_runtime_authorization']['sha256']!=AUTH_SHA:raise AdmissionStop('recording authority superseded')
 return a
def boundary(admission=False):
 global _last
 if admission or time.monotonic()-_last>5:authority();_last=time.monotonic()
 if time.time()>=CONFIG['absolute_wall_deadline_unix']:raise AdmissionStop('finite formal-family deadline')
 if admission and time.time()>=CONFIG['admission_cutoff_unix']:raise AdmissionStop('recording admission deadline')
def before_cutoff():return time.time()<CONFIG['absolute_wall_deadline_unix']
def claim_unit(unit):
 boundary(True)
 if units().get(unit['unit_id'])!=unit:raise AdmissionStop('not frozen owned candidate')
 row=dict(unit=unit,utc=utc(),process=process_identity())
 new_json(ROOT/'pair_claims'/(unit['candidate_id']+'.json'),row);return row
def claim_arm(unit,arm):
 boundary(True)
 if units().get(unit['unit_id'])!=unit or arm not in ('N','Post'):raise AdmissionStop('invalid recording arm')
 local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
 with (local/'attempts.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  path=ROOT/'arm_claims'/(unit['candidate_id']+'_'+arm+'_a1.json')
  if path.exists():raise AdmissionStop('duplicate arm')
  counter=ROOT/'ATTEMPT_COUNTER.json';n=read(counter)['recording_attempts'] if counter.exists() else 0
  if n>=CONFIG['recording_rollouts_cap']:raise AdmissionStop('recording arm cap')
  row=dict(unit_id=unit['unit_id'],arm=arm,attempt=1,number=n+1,utc=utc(),process=process_identity(),scientific_evaluation_units=0)
  new_json(path,row);atomic_json(counter,dict(recording_attempts=n+1,new_scientific_units=0,utc=utc()))
 return row
def resource_admission():return dict(utc=utc(),host=socket.gethostname(),cpu_affinity=len(os.sched_getaffinity(0)),capacity_evidence=str(ROOT/'CAPACITY_PREPARATION.json'),no_extra_GPU_preflight=True)
def worker_environment(base,work):
 env=dict(os.environ);env.update(base['cuda_environment'])
 env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=base['hf_home'],OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',CUDA_CACHE_DISABLE='1',TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),XDG_RUNTIME_DIR=str(work/'xdg'),LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
 for k in ['LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE','MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH']:env.pop(k,None)
 return env
