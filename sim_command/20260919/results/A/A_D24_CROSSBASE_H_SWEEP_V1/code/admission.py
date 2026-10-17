"""Frozen A unit identities, fixed L11 assets, finite host-local admission."""
import fcntl,json,os,socket,time,hashlib
from pathlib import Path
from paths import ROOT,CAMPAIGN,ORIGINAL,AUTH_SHA,TASK,CONFIG
from qio import read,sha,new_json,atomic_json,utc,process_identity,same_process

class AdmissionStop(RuntimeError):pass
AdmissionClosed=AdmissionStop
_UNITS=None

def authority():
    p=Path(CONFIG['grant']);a=read(p)
    if sha(p)!=AUTH_SHA or a['status']!='released':raise AdmissionStop('authorization changed')
    node=a['nodes']['A']
    if node['task_id']!=TASK or node['host']!=socket.gethostname() or node['thread_id']!=CONFIG['thread_id']:raise AdmissionStop('A identity mismatch')
    if sha(ROOT/'UNITS.jsonl')!=node['units']['sha256']:raise AdmissionStop('unit manifest changed')
    q=read(ROOT/'config/Q_ASSETS.json')
    if sha(ROOT/'config/Q_ASSETS.json')!=a['Q_assets']['sha256']:raise AdmissionStop('Q binding metadata changed')
    asset=q['assets']['SmolVLA'];ranking=read(asset['ranking']['path'])
    if sha(asset['ranking']['path'])!=asset['ranking']['sha256']:raise AdmissionStop('Smol L11 ranking changed')
    if CONFIG['selected_Q_assets']!=asset['asset_root'] or ranking['loss']!='L11' or ranking['fit_seed']!=9101 or ranking['member_seeds']!=[1041,1042,1043,1044]:raise AdmissionStop('L11 four-member binding')
    for member in asset['members']:
        if not Path(member['checkpoint']).is_file():raise AdmissionStop('missing Smol L11 checkpoint')
    return a

def original_exit_verified():
    result=read(ORIGINAL/'RESULT.json');ident=read(ORIGINAL/'STABLE_HANDOFF.json')['manager']
    from process_family import group_members
    if not result['all_owned_descendants_exited'] or same_process(ident) or group_members(ident['pgid'],ident['pid']):raise AdmissionStop('previous A formal family has not exited')

def before_cutoff():
    return not (ROOT/'STOP.json').exists() and time.time()<CONFIG['absolute_wall_deadline_unix']

def admissions_allowed():
    if not before_cutoff() or time.time()>=CONFIG['admission_cutoff_unix'] or (ROOT/'DRAIN.json').exists():return False
    c=read(CAMPAIGN/'CONTROL.json');q=read(CAMPAIGN/'persistent_queue/CONTROL.json')
    return not c.get('stop_requested') and not q.get('global_stop') and q['nodes']['A'].get('enabled') is True and all(x.get('active_crossbase_H_sweep',{}).get('sha256')==AUTH_SHA for x in [c,q])

def boundary(admission=False):
    if not before_cutoff():raise AdmissionStop('finite sweep stop/deadline')
    if admission and not admissions_allowed():raise AdmissionStop('new fixed-unit admission closed')

def frozen_units():
    global _UNITS
    if _UNITS is None:
        rows=[json.loads(x) for x in (ROOT/'UNITS.jsonl').read_text().splitlines() if x]
        _UNITS={u['unit_id']:u for u in rows}
        if len(_UNITS)!=4000 or any(u['owner']!='A' or u['model']!='SmolVLA' or u['H'] not in (20,30) or u['method'] not in ('N','Post','R','Velocity') for u in rows):raise ValueError('owned units changed')
        for u in rows:
            if u['method'] in ('Post','Velocity') and (u['Q_loss']!='L11' or u['Q_fit_seed']!=9101 or u['Q_members']!=[1041,1042,1043,1044]):raise ValueError('unit Q binding')
    return _UNITS
units=frozen_units

def unit_hash(u):return hashlib.sha256(u['unit_id'].encode()).hexdigest()
def cell_id(u):return 'SmolVLA_'+u['method']+'_'+u['mode']+'_H'+str(u['H'])

def claim_unit(unit):
    if unit!=frozen_units().get(unit['unit_id']):raise ValueError('unit not in frozen manifest')
    local=Path(CONFIG['local_dir']);local.mkdir(exist_ok=True)
    with (local/'attempts.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);boundary(True)
        counter=ROOT/'ATTEMPT_COUNTER.json';n=read(counter)['count'] if counter.exists() else 0
        if n>=CONFIG['first_episode_cap'] or n>=CONFIG['stage_attempt_cap'] or CONFIG['prior_A_attempts']+n>=CONFIG['cumulative_attempt_cap']:raise AdmissionStop('finite sweep attempt budget')
        uid=unit_hash(unit);target=ROOT/'unit_claims'/(uid+'.json')
        if target.exists():raise AdmissionStop('unit already claimed; preserve terminal and reconcile incomplete explicitly')
        claim=dict(unit_id=unit['unit_id'],uid_hash=uid,cell_id=cell_id(unit),source_id=unit['source_id'],method=unit['method'],mode=unit['mode'],H=unit['H'],Q_loss=unit['Q_loss'],Q_fit_seed=unit['Q_fit_seed'],attempt=1,stage_ordinal=n+1,node_cumulative_ordinal=CONFIG['prior_A_attempts']+n+1,utc=utc(),process=process_identity())
        new_json(target,claim)
        atomic_json(counter,dict(count=n+1,prior_A_attempts=CONFIG['prior_A_attempts'],node_cumulative=CONFIG['prior_A_attempts']+n+1,first_cap=4000,attempt_cap=4400,node_cap=CONFIG['cumulative_attempt_cap'],utc=utc()))
        return claim

def resource_admission():
    mem=dict(x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines());available=int(mem['MemAvailable'].split()[0])*1024
    st=os.statvfs(ROOT);free=st.f_bavail*st.f_frsize;cpus=len(os.sched_getaffinity(0))
    # 192 x 3 GiB environment planning reserve + 8 x 24 GiB CPU model loading reserve.
    reserve=768*1024**3;threads=192+8*2+8*2
    if available<reserve or free<40*1024**3 or cpus<threads:raise AdmissionStop('192-branch capacity: need RAM reserve768GiB, disk40GiB, CPU224; observed '+str((available,free,cpus)))
    return dict(utc=utc(),RAM_available_bytes=available,RAM_planning_reserve_bytes=reserve,planning_not_measured_peak=True,filesystem_available_bytes=free,CPU_affinity=cpus,CPU_planned_threads=threads,environment_processes_target=192,policy_processes=8,external_encoder_processes=8,model_sharing=True,inference_batch_size=1,cgroup_hard_limits=None,cgroup_unknown_reason='ancestor controller limits not exposed; observed capacity is not a hard memory guarantee',no_GPU_preflight=True)
