"""Full-Q identity, finite budgets and per-episode cooperative admission."""
import datetime,fcntl,os,socket,time
from pathlib import Path
from paths import ROOT,CAMPAIGN,AUTH_SHA,TASK
from qio import read,sha,new_json,atomic_json,utc

def authority():
 p=CAMPAIGN/'deadline_20260924/FULL_Q_LOSS_SELECTION_AUTHORIZATION_V1.json'
 if sha(p)!=AUTH_SHA:raise RuntimeError('full-Q authorization changed')
 d=read(p);a=d['nodes']['A']
 if socket.gethostname()!='trial-303224955-trialrun-303224955-worker-0' or d['status']!='released' or a['task_id']!=TASK or a['revision']!=1 or a['stage_attempt_cap']!=10100 or a['cumulative_attempt_cap']!=27000:raise RuntimeError('authority identity mismatch')
 return d

_END=None
def before_cutoff():
 global _END
 if _END is None:
  _END=datetime.datetime.fromisoformat(read(ROOT/'config/CONFIG.json')['deadline_utc'].replace('Z','+00:00')).timestamp()
  timer=ROOT/'RUN_TIME_BUDGET.json'
  if timer.exists():_END=min(_END,read(timer)['absolute_end_unix'])
 return time.time()<_END and not (ROOT/'STOP.json').exists()

def admissions_allowed():
 if not before_cutoff() or (ROOT/'DRAIN.json').exists():return False
 root=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json');node=q['nodes']['A']
 return (not root.get('stop_requested') and not q.get('global_stop') and node.get('enabled') is True and root.get('active_full_Q_loss_selection',{}).get('sha256')==AUTH_SHA and node.get('priority_authorization',{}).get('sha256')==AUTH_SHA)

_INDEX=None
_SOURCES=None
def frozen_jobs():
 global _INDEX,_SOURCES
 if _INDEX is None:
  rows=read(ROOT/'JOB_INDEX.json')['jobs'];_INDEX={j['job_id']:j for j in rows}
  if len(rows)!=len(_INDEX) or len(rows)!=1920:raise ValueError('job index')
  _SOURCES=read(ROOT/'SOURCE_INDEX.json')['source_sets']
 return _INDEX

def validate_job(job,*,stage_gate=True):
 index=frozen_jobs();cfg=read(ROOT/'config/CONFIG.json')
 if job['job_id'] not in index or sha(index[job['job_id']]['path'])!=index[job['job_id']]['sha256']:raise ValueError('job changed')
 if job!=read(index[job['job_id']]['path']) or job['configuration_sha256']!=sha(ROOT/'config/CONFIG.json'):raise ValueError('configuration changed')
 cell=next(c for c in cfg['cells'] if c['cell_id']==job['cell_id'])
 if any(job[k]!=v for k,v in cell.items()) or job['retry']!=0:raise ValueError('cell changed')
 canonical={s['source_id']:s for s in _SOURCES[job['stage']]}
 if not job['sources'] or any(s!=canonical.get(s['source_id']) or s['task']!=job['task'] for s in job['sources']):raise ValueError('source changed')
 if stage_gate and job['stage']!='DEV':
  from selection import locked_selection
  locked_selection()
 return cfg

class AdmissionClosed(RuntimeError):pass

def unit_id(source,job):return job['cell_id']+'__'+source['source_id']
def admit_episode(source,job):
 authority();validate_job(job)
 if source not in job['sources']:raise ValueError('source outside job')
 uid=unit_id(source,job)
 with Path('/tmp/corrector_A_D24_full_Q_attempt.lock').open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX)
  if not admissions_allowed():raise AdmissionClosed('episode admission revoked or expired')
  counter=ROOT/'ATTEMPT_COUNTER.json';n=read(counter)['count'] if counter.exists() else 0
  if n>=10100 or 14896+n>=27000 or n>=9600:raise RuntimeError('first-entry/stage/node cap')
  row=dict(unit_id=uid,task_id=TASK,cell_id=job['cell_id'],source=source,H=job['H'],mode=job['mode'],branch=job['method'],stage=job['stage'],loss=job['loss'],fit_seed=job['fit_seed'],attempt=0,stage_ordinal=n+1,node_cumulative_ordinal=14896+n+1,utc=utc(),retry=False)
  new_json(ROOT/'unit_claims'/(uid+'.json'),row)
  atomic_json(counter,dict(count=n+1,prior_D24_attempts=14896,node_cumulative=14896+n+1,stage_cap=10100,node_cap=27000,first_evaluation_cap=9600,utc=utc(),automatic_retry=False))
  return row

def resource_admission():
 info={}
 for line in open('/proc/meminfo'):
  f=line.split()
  if f[0] in ('MemTotal:','MemAvailable:'):info[f[0][:-1]]=int(f[1])*1024
 required=(24*64+16)*1024**3
 if info.get('MemAvailable',0)<required:raise RuntimeError('24-worker allowance exceeds current RAM; actual maximum must be recorded before admission')
 st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize
 if free<40*1024**3:raise RuntimeError('insufficient ordinary storage')
 return dict(host_memory=info,planning_not_measured_RAM_bytes=required,filesystem_available_bytes=free,filesystem_quota_proven=False,cgroup_hard_limit_bytes=None,cgroup_reason='masked ext4 mount',CPU_affinity_count=len(os.sched_getaffinity(0)),workers=24,workers_per_GPU=3,new_GPU_probe=False)

def worker_environment(base,work):
 env=dict(os.environ)
 if env.get('NVIDIA_VISIBLE_DEVICES')!=base['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:raise ValueError('GPU visibility changed')
 env.update(base['cuda_environment'])
 env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=base['hf_home'],OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',LP_NUM_THREADS='4',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',CUDA_CACHE_DISABLE='1',TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),XDG_RUNTIME_DIR=str(work/'xdg'),LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
 for k in ('LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE','MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH'):env.pop(k,None)
 return env
