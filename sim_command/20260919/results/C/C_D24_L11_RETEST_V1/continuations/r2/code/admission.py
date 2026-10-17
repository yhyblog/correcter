"""Finite, unique L11 unit admission; no legacy L01 selection dependency."""
import fcntl, hashlib, json, os, socket, time
from pathlib import Path
from paths import ROOT,CAMPAIGN,AUTH_SHA,TASK
from qio import read,new_json,atomic_json,sha,utc,process_identity
AUTH=CAMPAIGN/'deadline_20260924/L11_RETEST_V1/AUTHORIZATION.json'
LOCAL=Path('/tmp/corrector_C_L11_RETEST_r2')
_last_check=0.
class AdmissionClosed(RuntimeError):pass
AdmissionStop=AdmissionClosed
def before_cutoff():return time.time()<1790164800.
def authority():
    global _last_check
    if time.monotonic()-_last_check<10:return
    a=read(AUTH);control=read(CAMPAIGN/'persistent_queue/CONTROL.json');node=control['nodes']['C']
    if sha(AUTH)!=AUTH_SHA or a['status']!='released':raise AdmissionClosed('L11 authorization changed')
    if socket.gethostname()!=a['nodes']['C']['host']:raise AdmissionClosed('wrong host')
    identity=read(CAMPAIGN/'nodes/C/identity.json')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=identity['boot_id']:raise AdmissionClosed('reboot requires reconciliation')
    if control.get('global_stop') or not node.get('enabled') or node['priority_authorization']['sha256']!=AUTH_SHA:raise AdmissionClosed('live queue admission withdrawn')
    selection=read(CAMPAIGN/a['selection']['path'])
    if sha(CAMPAIGN/a['selection']['path'])!=a['selection']['sha256'] or selection['chosen_loss']!='L11' or selection['fit_seed']!=9101:raise AdmissionClosed('fixed L11 selection changed')
    _last_check=time.monotonic()
def boundary(admission=False):
    authority()
    if admission and (not before_cutoff() or (ROOT/'PAUSE_ADMISSIONS.json').exists()):raise AdmissionClosed('cutoff or new engineering fault pause')
def admissions_allowed():
    try:boundary(True);return True
    except AdmissionClosed:return False
def resource_admission():authority();return True
def validate_job(job):
    if job['loss']!='L11' or job['fit_seed']!=9101 or job['mode']!='G0-multi':raise ValueError('job scientific identity')
def claim_unit(unit):
    boundary(True);key=hashlib.sha256(unit['unit_id'].encode()).hexdigest()
    frozen=read(ROOT/'units'/(key+'.json'))
    if unit!=frozen or unit['owner']!='C':raise ValueError('unit differs from exact owned manifest')
    LOCAL.mkdir(exist_ok=True)
    with (LOCAL/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        boundary(True)
        p=ROOT/'claims/units'/(key+'.json')
        if p.exists():raise AdmissionClosed('unit already entered; no implicit replay')
        counter=ROOT/'ATTEMPT_COUNTER.json';n=read(counter)['count'] if counter.exists() else 0
        if n+447>=2750 or 14943+447+n>=18750:raise AdmissionClosed('stage/node attempt cap')
        plan=read(ROOT/'RECOVERY_PLAN.json');retry=unit['unit_id'] in plan['corrected_retry_unit_ids']
        old=Path(plan['original_task_root'])
        if retry:
            old_result=read(old/'evaluation'/unit['method']/unit['source_id']/'RESULT.json')
            if old_result.get('status')!='technical_failure' or old_result.get('error')!="ValueError('invalid real observation')":raise AdmissionClosed('retry lacks diagnosed renderer fault')
        elif (old/'claims/units'/(key+'.json')).exists():raise AdmissionClosed('unclassified existing original claim')
        value=dict(unit_id=unit['unit_id'],storage_key=key,stage_ordinal=447+n+1,attempt=2 if retry else 1,retry=retry,process=process_identity(),utc=utc(),loss='L11',fit_seed=9101)
        new_json(p,value);atomic_json(counter,dict(count=n+1,prior_C_attempts=14943,previous_task_attempts=447,task_attempts_total=447+n+1,cumulative_C_reserved=14943+447+n+1,utc=utc()))
        return value
def admit_episode(source,job):
    u=job['unit']
    if source!=u['runtime_source']:raise ValueError('runtime source identity')
    return claim_unit(u)
