"""Full-Q identity, finite budgets and per-episode cooperative admission."""
import datetime,fcntl,os,socket,time
from pathlib import Path
from paths import ROOT,ORIGINAL,PRIOR_EVIDENCE_ROOTS,CAMPAIGN,AUTH_SHA,TASK,POST_OVERRIDE_SHA
from qio import read,sha,new_json,atomic_json,utc

def authority():
 p=CAMPAIGN/'deadline_20260924/FULL_Q_AUTORUN_AUTHORIZATION_V2.json'
 if sha(p)!=AUTH_SHA:raise RuntimeError('full-Q authorization changed')
 d=read(p);a=d['nodes']['A']
 if socket.gethostname()!='trial-303224955-trialrun-303224955-worker-0' or d['status']!='released' or a['task_id']!=TASK or a['revision']!=1 or a['continuation_attempt_cap']!=3500 or a['cumulative_attempt_cap']!=27000:raise RuntimeError('authority identity mismatch')
 override=CAMPAIGN/'deadline_20260924/POST_LED_SELECTION_OVERRIDE_V1.json'
 if sha(override)!=POST_OVERRIDE_SHA or read(override)['selection']['Post_only'] is not True:raise RuntimeError('mandatory Post-only override mismatch')
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
 # Live stage grants, not mutable descriptive priority labels, authorize this
 # finite continuation. Explicit stop/revocation still closes every episode.
 return (not root.get('stop_requested') and not q.get('global_stop') and node.get('enabled') is True and root.get('active_full_Q_autorun_assignment',{}).get('sha256')==AUTH_SHA and q.get('active_full_Q_autorun_assignment',{}).get('sha256')==AUTH_SHA and root.get('active_Post_selection_override',{}).get('sha256')==POST_OVERRIDE_SHA and q.get('active_Post_selection_override',{}).get('sha256')==POST_OVERRIDE_SHA)

_INDEX=None
_SOURCES=None
def frozen_jobs():
 global _INDEX,_SOURCES
 if _INDEX is None:
  doc=read(ROOT/'JOB_INDEX.json');rows=doc['jobs'];_INDEX={j['job_id']:j for j in rows}
  if len(rows)!=len(_INDEX) or len(rows)!=doc['job_count']:raise ValueError('job index')
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
 original_ref=job['original_job_ref'];original=read(original_ref['path'])
 if sha(original_ref['path'])!=original_ref['sha256'] or original['job_id']!=job['job_id']:raise ValueError('original job changed')
 for k in original:
  if k not in ['sources','configuration_sha256'] and original[k]!=job[k]:raise ValueError('original scientific field changed: '+k)
 if any(s not in original['sources'] for s in job['sources']):raise ValueError('new source not original')
 if job['stage']=='MAIN' and job['H']!=10:raise ValueError('remote-owned H forbidden in A continuation')
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
 with Path('/tmp/corrector_A_D24_full_Q_post_led_attempt.lock').open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX)
  if not admissions_allowed():raise AdmissionClosed('episode admission revoked or expired')
  if any((root/'unit_claims'/(uid+'.json')).exists() for root in PRIOR_EVIDENCE_ROOTS):raise RuntimeError('prior entered unit must not replay')
  counter=ROOT/'ATTEMPT_COUNTER.json';prior=read(counter) if counter.exists() else dict(count=0,DEV_count=0,test_count=0)
  n=prior['count'];dev=prior['DEV_count'];tests=prior['test_count'];is_dev=job['stage']=='DEV'
  plan=read(ROOT/'RESUME_PLAN.json');base=plan['prior_A_attempts']
  if n>=plan['new_first'] or n>=plan['new_attempt_cap'] or base+n>=27000 or is_dev and dev>=plan['remaining_DEV_first'] or not is_dev and (tests>=3200 or tests>=3500):raise RuntimeError('continuation first/stage/node cap')
  row=dict(unit_id=uid,task_id=TASK,cell_id=job['cell_id'],source=source,H=job['H'],mode=job['mode'],branch=job['method'],stage=job['stage'],loss=job['loss'],fit_seed=job['fit_seed'],attempt=0,stage_ordinal=n+1,node_cumulative_ordinal=base+n+1,utc=utc(),retry=False,original_task='A_D24_FULL_Q_LOSS_SELECTION_V1',original_job_ref=job['original_job_ref'],Post_selection_override_sha256=POST_OVERRIDE_SHA)
  new_json(ROOT/'unit_claims'/(uid+'.json'),row)
  atomic_json(counter,dict(count=n+1,DEV_count=dev+int(is_dev),test_count=tests+int(not is_dev),prior_D24_attempts=base,node_cumulative=base+n+1,DEV_first_cap=plan['remaining_DEV_first'],test_first_cap=3200,test_attempt_cap=3500,node_cap=27000,first_evaluation_cap=plan['new_first'],utc=utc(),automatic_retry=False))
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
