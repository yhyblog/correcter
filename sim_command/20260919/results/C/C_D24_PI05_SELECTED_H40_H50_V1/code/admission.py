"""C grants, exact transferred units, finite deadlines and ordinary capacity."""
import fcntl,os,socket,time
from pathlib import Path
from paths import ROOT,CAMPAIGN,AUTH_SHA,TASK,PREVIOUS
from qio import read,sha,new_json,atomic_json,utc,verify,ref,same_process
from process_family import group_members
from operational_hook import reject_completed_terminal
class AdmissionClosed(RuntimeError):pass
_fixed_checked=False

def authority():
    global _fixed_checked
    p=CAMPAIGN/'deadline_20260924/FULL_Q_AUTORUN_AUTHORIZATION_V2.json'
    if sha(p)!=AUTH_SHA:raise AdmissionClosed('V2 authorization changed')
    grant=read(p);node=read(CAMPAIGN/'persistent_queue/CONTROL.json')['nodes']['C'];identity=read(CAMPAIGN/'nodes/C/identity.json')
    if grant['status']!='released' or grant['nodes']['C']['task_id']!=TASK or not node['enabled']:raise AdmissionClosed('C not released')
    if socket.gethostname()!=node['owner_host'] or identity['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():raise AdmissionClosed('C host/boot mismatch')
    follow=[r for r in node.get('authorized_followups',[]) if r['task_id']==TASK and r['authorization']['sha256']==AUTH_SHA]
    if not follow:raise AdmissionClosed('C registered grant absent')
    cfg=read(ROOT/'config/CONFIG.json');a=grant['nodes']['C']
    if (cfg['stage_attempt_cap'],cfg['node_cumulative_attempt_cap'],cfg['source_first_cap'],cfg['evaluation_workers'])!=(a['stage_attempt_cap'],a['cumulative_attempt_cap'],a['pi05_transferred_first_maximum'],24):raise AdmissionClosed('C budget changed')
    post=CAMPAIGN/'deadline_20260924/POST_LED_SELECTION_OVERRIDE_V1.json'
    from selection import POST_RULE_SHA
    if sha(post)!=POST_RULE_SHA or read(post)['status']!='released':raise AdmissionClosed('Post-only selection override changed')
    if not _fixed_checked:
        for k in ['plan','ownership_plan','original_full_Q_authorization','concurrency_rule']:verify(grant[k])
        verify(cfg['original_A_configuration'])
        for r in read(ROOT/'SOURCE_PROVENANCE.json')['copied_modules']:
            if Path(r['copy']).name in ['controller.py','numeric_engine.py','resident_egl.py'] and sha(r['copy'])!=r['source']['sha256']:raise AdmissionClosed('frozen algorithm copy changed')
        _fixed_checked=True
    return grant

def before_cutoff():
    end=read(ROOT/'config/CONFIG.json')['absolute_wall_deadline_unix']
    names=['STAGE_DEADLINE.json'] if (ROOT/'DEPENDENCIES_SATISFIED.json').exists() else ['QUEUE_DEADLINE.json']
    for name in names:
        p=ROOT/name
        if p.exists():end=min(end,read(p)['deadline_unix'])
    return time.time()<end and not (ROOT/'STOP.json').exists()

def admissions_allowed():
    if not before_cutoff() or (ROOT/'DRAIN.json').exists():return False
    q=read(CAMPAIGN/'persistent_queue/CONTROL.json');c=read(CAMPAIGN/'CONTROL.json');n=q['nodes']['C']
    return not q.get('global_stop') and not c.get('stop_requested') and n['enabled'] and any(r['task_id']==TASK and r['authorization']['sha256']==AUTH_SHA for r in n.get('authorized_followups',[]))

def previous_exited():
    owner=read(PREVIOUS/'PROCESS.json')
    if same_process(dict(owner,host=owner['hostname'])):return None
    result_path=PREVIOUS/'RESULT.json'
    if not result_path.is_file():raise AdmissionClosed('native X waiter exited without reliable terminal; preserve claim')
    result=read(result_path)
    if not result.get('all_owned_descendants_exited'):raise AdmissionClosed('native X formal descendants not confirmed exited')
    for chain in (PREVIOUS/'chains').glob('*'):
        for name in ['MANAGER_STARTED.json','LIFECYCLE_STARTED.json']:
            p=chain/name
            if p.exists():
                i=read(p)['process']
                if same_process(i) or group_members(i['pgid'],i['pid']):raise AdmissionClosed('native X live formal family')
        release=chain/'BEFORE_RESERVATION_RELEASE.json'
        if not release.exists() or (read(release).get('cleanup') or {}).get('status') not in ['all_formal_group_members_exited','no_formal_entry']:raise AdmissionClosed('native X reservation cleanup unresolved')
    old=read(PREVIOUS/'config/CONFIG.json')['planned_prior_attempts']
    counter=PREVIOUS/'ATTEMPT_COUNTER.json';n=read(counter)['reserved_attempts'] if counter.exists() else 0
    if old!=11943 or not 0<=n<=1100:raise AdmissionClosed('native X cumulative accounting mismatch')
    if old+n+2200>16000:raise AdmissionClosed('C cumulative cap insufficient')
    return dict(utc=utc(),result=ref(result_path),process=owner,prior_native_attempts=n,prior_C_attempts=old+n,all_owned_family_exited=True,previous_status=result['status'],no_predecessor_ACK_gate=True)

_jobs=None;_sources=None
def frozen_jobs():
    global _jobs,_sources
    if _jobs is None:
        index=read(ROOT/'JOB_INDEX.json');_jobs={r['job_id']:r for r in index['jobs']}
        if len(_jobs)!=len(index['jobs']) or len(_jobs)>400:raise ValueError('transferred job index')
        _sources={s['source_id']:s for s in read(ROOT/'SOURCE_INDEX.json')['source_sets']['MAIN']}
    return _jobs

def validate_job(job,*,stage_gate=True):
    r=frozen_jobs().get(job['job_id']);cfg=read(ROOT/'config/CONFIG.json')
    if r is None or sha(r['path'])!=r['sha256'] or job!=read(r['path']):raise ValueError('frozen C job changed')
    if job['configuration_sha256']!=cfg['original_A_configuration']['sha256']:raise ValueError('original A scientific config changed')
    cell=next(c for c in cfg['cells'] if c['cell_id']==job['cell_id'])
    if any(job[k]!=v for k,v in cell.items()) or job['retry']!=0:raise ValueError('transferred cell changed')
    if not job['sources'] or any(s!=_sources.get(s['source_id']) or s['task']!=job['task'] for s in job['sources']):raise ValueError('fixed source changed')
    if stage_gate:
        from selection import consumed_selection
        from transfer import consumed_transfer
        consumed_selection();consumed_transfer()
    return cfg

def unit_id(source,job):return job['cell_id']+'__'+source['source_id']
def admit_episode(source,job):
    authority();validate_job(job)
    if source not in job['sources']:raise ValueError('source outside transferred job')
    uid=unit_id(source,job)
    reject_completed_terminal(ROOT/'runs'/job['job_id']/'episodes'/source['source_id']/'RESULT.json')
    from transfer import assert_not_A_owned
    with Path('/tmp/corrector_C_PI05_selected_attempt.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        if not admissions_allowed():raise AdmissionClosed('C episode admission closed')
        assert_not_A_owned(job['job_id'],uid)
        prior=read(ROOT/'PREDECESSOR_EXIT.json')['prior_C_attempts'];limit=read(ROOT/'TRANSFER_CONSUMED.json')['first_count']
        counter=ROOT/'ATTEMPT_COUNTER.json';n=read(counter)['count'] if counter.exists() else 0
        if n>=min(2200,limit) or prior+n>=16000:raise AdmissionClosed('C first/stage/cumulative cap')
        if job['H']==50 and not (ROOT/'H40_DISPATCH_COMPLETE.json').exists():raise AdmissionClosed('H40 barrier not complete')
        row=dict(unit_id=uid,task_id=TASK,cell_id=job['cell_id'],source=source,H=job['H'],mode=job['mode'],branch=job['method'],stage=job['stage'],loss=job['loss'],fit_seed=job['fit_seed'],attempt=0,stage_ordinal=n+1,node_cumulative_ordinal=prior+n+1,utc=utc(),retry=False)
        new_json(ROOT/'unit_claims'/(uid+'.json'),row)
        atomic_json(counter,dict(count=n+1,prior_D24_attempts=prior,node_cumulative=prior+n+1,stage_cap=2200,node_cap=16000,first_evaluation_cap=limit,utc=utc(),automatic_retry=False))
        return row

def resource_admission(stage='evaluate'):
    info={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        f=line.split()
        if f[0] in ['MemTotal:','MemAvailable:']:info[f[0][:-1]]=int(f[1])*1024
    required=(24*64+16)*1024**3;free=os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize
    cgroups={}
    for name in ['/sys/fs/cgroup/memory.max','/sys/fs/cgroup/memory.current','/sys/fs/cgroup/memory/memory.limit_in_bytes','/sys/fs/cgroup/memory/memory.usage_in_bytes']:
        if Path(name).is_file():cgroups[name]=Path(name).read_text().strip()
    maximum=cgroups.get('/sys/fs/cgroup/memory.max',cgroups.get('/sys/fs/cgroup/memory/memory.limit_in_bytes'))
    used=cgroups.get('/sys/fs/cgroup/memory.current',cgroups.get('/sys/fs/cgroup/memory/memory.usage_in_bytes'))
    if maximum and maximum!='max' and used and int(maximum)-int(used)<required:raise AdmissionClosed('cgroup remaining RAM below 24-worker estimate')
    if info['MemAvailable']<required or free<40*1024**3:raise AdmissionClosed('ordinary RAM/storage below 24-worker allowance')
    return dict(utc=utc(),host_memory=info,planning_RAM_bytes=required,filesystem_available_bytes=free,cgroup_observed=cgroups or None,cgroup_missing_reason=None if cgroups else 'masked in this container; not assumed unlimited',CPU_affinity_count=len(os.sched_getaffinity(0)),workers=24,workers_per_GPU=3,per_worker_RAM_GiB_estimate=64,measured_A_model_ready_GPU_reserved_bytes=9607053312,measured_A_model_ready_RSS_KiB=41225888,capacity_scope='same pi05 model on eight local H10080GB; A measurements are planning evidence, not C peaks',load_tranche=8,extra_GPU_probes=0)

def worker_environment(base,work):
    env=dict(os.environ)
    if env.get('NVIDIA_VISIBLE_DEVICES')!=base['cuda_environment']['NVIDIA_VISIBLE_DEVICES']:raise ValueError('C GPU visibility changed')
    env.update(base['cuda_environment'])
    env.update(PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=base['hf_home'],OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',NUMEXPR_NUM_THREADS='4',LP_NUM_THREADS='4',TOKENIZERS_PARALLELISM='false',PYTORCH_NVML_BASED_CUDA_CHECK='0',CUDA_CACHE_DISABLE='1',TMPDIR=str(work/'tmp'),XDG_CACHE_HOME=str(work/'cache'),XDG_RUNTIME_DIR=str(work/'xdg'),LD_LIBRARY_PATH=base['LD_LIBRARY_PATH'],MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',__EGL_VENDOR_LIBRARY_FILENAMES=base['native']['isolation_root']+'/isolation/vendor/10_nvidia.json')
    for k in ['LD_PRELOAD','__EGL_VENDOR_LIBRARY_DIRS','MUJOCO_EGL_DEVICE_ID','PYTHONPATH','LIBGL_ALWAYS_SOFTWARE','MESA_LOADER_DRIVER_OVERRIDE','GALLIUM_DRIVER','EGL_PLATFORM','LIBGL_DRIVERS_PATH']:env.pop(k,None)
    return env
