"""Finite L11 authority and exclusive scientific-unit claims; CPU only."""
import datetime,fcntl,os,socket,time
from pathlib import Path
from paths import ROOT,CAMPAIGN,ORIGINAL,AUTH_SHA,TASK,SELECTION_SHA
from qio import read,sha,new_json,atomic_json,utc,process_identity,same_process

class AdmissionClosed(RuntimeError):pass

def authority():
 p=CAMPAIGN/'deadline_20260924/L11_RETEST_V1/AUTHORIZATION.json'
 if sha(p)!=AUTH_SHA:raise ValueError('L11 grant changed')
 d=read(p);a=d['nodes']['A']
 if d['status']!='released' or a['task_id']!=TASK or a['host']!=socket.gethostname():raise ValueError('L11 host/task/status mismatch')
 if sha(CAMPAIGN/d['selection']['path'])!=SELECTION_SHA:raise ValueError('L11 selection directive changed')
 return d

def original_exit_verified():
 d=read(ORIGINAL/'RESULT.json');m=read(ORIGINAL/'chain/MANAGER_EXIT.json');h=read(ORIGINAL/'chain/HEARTBEAT.json')
 if not d['all_owned_descendants_exited'] or not m['all_owned_processes_exited']:raise ValueError('prior family exit not confirmed')
 from process_family import group_members
 ident=h['manager']
 if same_process(ident) or group_members(ident['pgid'],ident['pid']):raise ValueError('prior formal process still exists')

def before_cutoff():
 timer=ROOT/'RUN_TIME_BUDGET.json'
 return not (ROOT/'STOP.json').exists() and (not timer.exists() or time.time()<read(timer)['absolute_end_unix'])

def admissions_allowed():
 if not before_cutoff() or time.time()>=1790164800 or (ROOT/'DRAIN.json').exists():return False
 c=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json')
 return not c.get('stop_requested') and not q.get('global_stop') and q['nodes']['A'].get('enabled') is True and all(d.get('active_L11_formal_retest',{}).get('sha256')==AUTH_SHA for d in [c,q])

_UNITS=None
def frozen_units():
 global _UNITS
 if _UNITS is None:
  import json
  rows=[json.loads(x) for x in (ROOT/'UNITS.jsonl').read_text().splitlines()];_UNITS={u['unit_id']:u for u in rows}
  if len(_UNITS)!=2900:raise ValueError('unit inventory')
 return _UNITS

def admit_unit(unit,slot):
 if unit!=frozen_units().get(unit['unit_id']):raise ValueError('unit not frozen A manifest')
 with Path('/tmp/corrector_A_L11_retest_attempt.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if not admissions_allowed():raise AdmissionClosed('L11 new episode admission closed')
  counter=ROOT/'ATTEMPT_COUNTER.json';prior=read(counter) if counter.exists() else {'count':0};n=prior['count']
  if n>=2900 or n>=3200 or 20496+n>=30200:raise AdmissionClosed('finite scientific budget')
  row=dict(unit_id=unit['unit_id'],uid_hash=unit['uid_hash'],source=unit['source'],cell_id=unit['cell_id'],method=unit['method'],mode=unit['mode'],H=unit['H'],loss='L11',fit_seed=9101,slot=slot,attempt=0,stage_ordinal=n+1,node_cumulative_ordinal=20497+n,utc=utc(),process=process_identity(),retry=False)
  new_json(ROOT/'unit_claims'/(unit['uid_hash']+'.json'),row)
  atomic_json(counter,dict(count=n+1,prior_A_attempts=20496,node_cumulative=20497+n,first_cap=2900,attempt_cap=3200,node_cap=30200,utc=utc()))
  return row

def resource_admission():
 v=read(ROOT/'CAPACITY_BEFORE.json');m=int(v['meminfo']['MemAvailable'].split()[0])*1024
 st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize
 if m<768*1024**3 or free<40*1024**3:raise ValueError('shared-model planning RAM/storage reserve not available')
 return dict(capacity_evidence=str(ROOT/'CAPACITY_BEFORE.json'),RAM_reserve_estimate_bytes=768*1024**3,RAM_reserve_is_not_measured_peak=True,filesystem_available_bytes=free,cgroup_hard_limits=None,cgroup_reason='controller mounts masked/unavailable; no hard-limit claim',CPU_count=len(os.sched_getaffinity(0)),model_processes=8,contexts_per_model=24,logical_target=192,batch_size=1,formal_first_episodes_are_validation=True)

def worker_environment(base,work):
 env=dict(os.environ)
 if env.get('NVIDIA_VISIBLE_DEVICES')!=base['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:raise ValueError('GPU visibility changed')
 env.update(base['cuda_environment'])
 env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=base['hf_home'],OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',CUDA_CACHE_DISABLE='1',TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),XDG_RUNTIME_DIR=str(work/'xdg'),LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
 for k in ['LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE','MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH']:env.pop(k,None)
 return env
