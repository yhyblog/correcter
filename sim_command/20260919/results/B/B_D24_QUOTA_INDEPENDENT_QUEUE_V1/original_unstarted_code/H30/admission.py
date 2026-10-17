import fcntl,os,time
from pathlib import Path
from paths import ROOT,CONFIG,CAMPAIGN
from qio import read,sha,new_json,atomic_json,utc
import gates
class AdmissionClosed(RuntimeError):pass

def authority():
 a=gates.authority()
 if not CONFIG.get('activation_finalized'):raise AdmissionClosed('stage not activated')
 if not gates.family_exited(CONFIG['predecessor_root']):raise AdmissionClosed('own predecessor family not exited')
 s=gates.selection()
 if s['chosen_loss']!=CONFIG['selected_loss'] or sha(gates.A/'SELECTION.json')!=CONFIG['selection_sha256']:raise AdmissionClosed('selected configuration changed')
 if CONFIG['planned_prior_attempts']+CONFIG['planned_current']>22000:raise AdmissionClosed('cumulative cap')
 return a

def before_cutoff():return time.time()<min(CONFIG['absolute_wall_deadline_unix'],1790164800) and not (ROOT/'STOP.json').exists()
def admissions_allowed():
 if not before_cutoff() or (ROOT/'DRAIN.json').exists():return False
 c=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json')
 return not c.get('stop_requested') and not q.get('global_stop') and q['nodes']['B']['enabled'] and gates.TASK in c['allowed_task_ids'] and any(v.get('sha256')==gates.AUTH for v in q['stage_authorizations'])

_jobs=None
def validate_job(job,stage_gate=True):
 global _jobs
 if _jobs is None:_jobs={x['job_id']:x for x in read(ROOT/'JOB_INDEX.json')['jobs']}
 row=_jobs.get(job['job_id'])
 if row is None or job!=read(row['path']) or sha(row['path'])!=row['sha256']:raise ValueError('frozen local job mismatch')
 if job['stage']!='MAIN' or job['H']!=CONFIG['H'] or job['method'] not in ['Post','Velocity'] or job['mode']!='G0-multi' or job['fit_seed']!=9101:raise ValueError('transferred protocol scope')
 if not 0<len(job['sources'])<=5:raise ValueError('finite source chunk')
 if stage_gate:gates.selection()
 return CONFIG

def admit_episode(source,job):
 authority();validate_job(job)
 if source not in job['sources']:raise ValueError('source not in exact transfer')
 uid=job['cell_id']+'__'+source['source_id']
 for a in [gates.A,gates.AH]:
  if (a/'unit_claims'/(uid+'.json')).exists() or (a/'claims'/(job['job_id']+'.json')).exists():raise AdmissionClosed('unit claimed by A')
 local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
 with (local/'attempts.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if not admissions_allowed():raise AdmissionClosed('live authority/cutoff closed')
  counter=ROOT/'ATTEMPT_COUNTER.json';n=read(counter)['count'] if counter.exists() else 0
  if n>=CONFIG['planned_current'] or n>=CONFIG['stage_attempt_cap'] or CONFIG['planned_prior_attempts']+n>=22000:raise AdmissionClosed('hard attempt cap')
  claim=dict(unit_id=uid,job_id=job['job_id'],task_id=gates.TASK,cell_id=job['cell_id'],source=source,H=job['H'],mode=job['mode'],branch=job['method'],stage='MAIN',loss=CONFIG['selected_loss'],fit_seed=9101,attempt=0,stage_ordinal=n+1,node_cumulative_ordinal=CONFIG['planned_prior_attempts']+n+1,utc=utc(),retry=False)
  new_json(ROOT/'unit_claims'/(uid+'.json'),claim)
  atomic_json(counter,dict(count=n+1,node_cumulative=CONFIG['planned_prior_attempts']+n+1,automatic_retry=False,utc=utc()))
  return claim

def resource_admission():
 info={}
 for line in open('/proc/meminfo'):
  f=line.split()
  if f[0] in ['MemAvailable:','MemTotal:']:info[f[0][:-1]]=int(f[1])*1024
 required=(24*64+16)*1024**3
 if info['MemAvailable']<required:raise RuntimeError('ordinary RAM below 24-worker 64GiB allowance; no speculative admission')
 stat=os.statvfs(ROOT);free=stat.f_bavail*stat.f_frsize
 if free<40*1024**3:raise RuntimeError('insufficient storage')
 return dict(host_memory=info,planned_RAM_bytes=required,workers=24,workers_per_GPU=3,CPU_affinity=len(os.sched_getaffinity(0)),filesystem_free_bytes=free,extra_GPU_probes=0)

def worker_environment(base,work):
 env=dict(os.environ)
 if env.get('NVIDIA_VISIBLE_DEVICES')!=base['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:raise ValueError('local GPU visibility changed')
 env.update(base['cuda_environment'])
 env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=base['hf_home'],OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',TOKENIZERS_PARALLELISM='false',CUDA_CACHE_DISABLE='1',TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),XDG_RUNTIME_DIR=str(work/'xdg'),LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
 for k in ['LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE','MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH']:env.pop(k,None)
 return env
