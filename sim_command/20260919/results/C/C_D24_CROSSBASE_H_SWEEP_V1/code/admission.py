"""Exact recovery-manifest admission with protected valid results and lifetime costs."""
import fcntl,hashlib,socket,time
from pathlib import Path
from paths import ROOT,CAMPAIGN,AUTH_SHA,TASK,JOB,CONFIG
from qio import read,new_json,atomic_json,sha,utc,process_identity
AUTH=CAMPAIGN/'deadline_20260924/CROSSBASE_H_SWEEP_V1/AUTHORIZATION.json'
LOCAL=Path(CONFIG['local_dir'])
_last_check=0.
class AdmissionClosed(RuntimeError):pass
AdmissionStop=AdmissionClosed
def before_cutoff():return time.time()<CONFIG['cutoff_unix']
def authority():
    global _last_check
    if time.monotonic()-_last_check<10:return
    a=read(AUTH);control=read(CAMPAIGN/'persistent_queue/CONTROL.json');node=control['nodes']['C']
    if sha(AUTH)!=AUTH_SHA or a['status']!='released':raise AdmissionClosed('recovery authorization changed')
    if socket.gethostname()!=a['nodes']['C']['host']:raise AdmissionClosed('wrong host')
    identity=read(CAMPAIGN/'nodes/C/identity.json')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=identity['boot_id']:raise AdmissionClosed('reboot requires reconciliation')
    if control.get('global_stop') or not node.get('enabled'):raise AdmissionClosed('queue withdrawn')
    if not any(node.get(k,{}).get('sha256')==AUTH_SHA for k in ('priority_authorization','active_runtime_authorization','authorization')):raise AdmissionClosed('live recovery authority withdrawn')
    selection=CAMPAIGN/'deadline_20260924/L11_RETEST_V1/L11_SELECTION_OVERRIDE.json'
    if sha(selection)!='2006bc5818911d80a7b325bc91699c789675bb62b75647a4abcc8012119dffe2':raise AdmissionClosed('frozen selection changed')
    if a['Q_loss']!='L11' or a['Q_fit_seed']!=9101:raise AdmissionClosed('fixed science identity changed')
    _last_check=time.monotonic()
def boundary(admission=False,model=None):
    authority()
    if admission and (not before_cutoff() or (model and (ROOT/('PAUSE_ADMISSIONS_'+model+'.json')).exists())):raise AdmissionClosed('cutoff or engineering fault admission pause')
def admissions_allowed(model=None):
    try:boundary(True,model);return True
    except AdmissionClosed:return False
def resource_admission():authority();return True
def validate_job(job):
    if job['method'] in ('Post','Velocity') and (job['loss']!='L11' or job['fit_seed']!=9101 or job['mode']!='G0-multi'):raise ValueError('job scientific identity')
def claim_unit(unit):
    boundary(True,unit['model']);key=hashlib.sha256(unit['unit_id'].encode()).hexdigest()
    if unit!=read(ROOT/'units'/(key+'.json')) or unit['owner']!='C':raise ValueError('unit differs from exact owned manifest')
    if unit['H'] not in (20,30) or unit['method'] not in ('N','Post','R','Velocity'):raise AdmissionClosed('unlisted horizon/method')
    LOCAL.mkdir(exist_ok=True)
    with (LOCAL/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);boundary(True,unit['model'])
        p=ROOT/'claims/units'/(key+'.json')
        if p.exists():raise AdmissionClosed('existing recovery claim; no implicit replay')
        counter=ROOT/'ATTEMPT_COUNTER.json';n=read(counter)['count'] if counter.exists() else 0
        prior=read(ROOT/'DEPENDENCY_EXIT.json')['prior_C_attempts']
        if n>=CONFIG['stage_attempt_cap'] or prior+n>=CONFIG['node_cumulative_attempt_cap']:raise AdmissionClosed('finite stage/node attempt cap')
        value=dict(task_id=TASK,run_id=JOB,unit_id=unit['unit_id'],storage_key=key,stage_ordinal=n+1,attempt=1,lifetime_attempt=1,prior_attempt_count=0,new_H_unit=True,implicit_retry=False,process=process_identity(),utc=utc(),model=unit['model'],H=unit['H'],method=unit['method'],mode=unit['mode'],loss=unit['Q_loss'],fit_seed=unit['Q_fit_seed'],source_id=unit['source_id'],authorization_sha256=AUTH_SHA)
        new_json(p,value);atomic_json(counter,dict(count=n+1,prior_C_attempts=prior,cumulative_C_reserved=prior+n+1,utc=utc()))
        return value
def admit_episode(source,job):
    if source!=job['unit']['runtime_source']:raise ValueError('runtime source identity')
    return claim_unit(job['unit'])
