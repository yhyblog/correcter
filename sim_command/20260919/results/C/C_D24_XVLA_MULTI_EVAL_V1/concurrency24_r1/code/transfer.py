"""Park unclaimed groups; let in-flight sources finish, then acquire a new wave."""
import hashlib,time
from pathlib import Path
from paths import ROOT as DATA,RUNROOT,CAMPAIGN
from qio import read,new_json,atomic_json,ref,utc,same_process
from admission import boundary,before_cutoff
from process_family import group_members

def prepare_and_wait(owner,job):
    state=CAMPAIGN/'persistent_queue/nodes/C/wakeup'
    # Both registration and the new detached owner already exist. One final event
    # will cover this scheduler transfer, not each physical wave.
    target=state/'jobs'/f'{job}.json';registered=read(target)
    assert registered['task_id']=='C_D24_XVLA_MULTI_EVAL_V1'
    oldpath=state/'jobs/D24_C_XVLA_MULTI_r1.json';old=read(oldpath)
    new_json(RUNROOT/'evidence/PREVIOUS_NOTIFICATION_REGISTRATION.json',old)
    old.update(notification_coalesced_into=job,coalescing_record=str(RUNROOT/'USER_CONCURRENCY_OVERRIDE.json'),
               coalescing_reason='user authorized concurrency change; old scientific claim/results preserved',coalesced_at_utc=utc())
    atomic_json(oldpath,old)
    sources=read(DATA/'config/TEST_SOURCES.json')['sources'];tasks=list(dict.fromkeys(s['task'] for s in sources));parked=[];active=[]
    for method in ['R','Post','Velocity']:
        for task in tasks:
            boundary(True);key=method+'/'+task;p=DATA/'claims/eval_jobs'/(hashlib.sha256(key.encode()).hexdigest()+'.json')
            row=dict(identity=key,method=method,task=task,at_utc=utc(),process=owner,handoff_for=job,
                     status='unstarted_group_parked_for_concurrency24',scientific_attempts=0,
                     authorization=str(RUNROOT/'USER_CONCURRENCY_OVERRIDE.json'))
            try:new_json(p,row)
            except FileExistsError:active.append(key);continue
            parked.append(dict(identity=key,method=method,task=task,claim=ref(p),
                               sources=[s['source_id'] for s in sources if s['task']==task]))
            atomic_json(RUNROOT/'TRANSFER.json',dict(utc=utc(),status='parking',groups=parked,groups_count=len(parked),
                new_first_sources=sum(len(g['sources']) for g in parked),old_claims_retained=True,original_claims_never_deleted=True))
    atomic_json(RUNROOT/'TRANSFER.json',dict(utc=utc(),status='parked_waiting_original_wave_exit',groups=parked,
        groups_count=len(parked),new_first_sources=sum(len(g['sources']) for g in parked),already_claimed_groups=active,
        old_claims_retained=True,original_claims_never_deleted=True,scientific_replays=0))
    own_old=read(DATA/'PROCESS.json');expected=dict(own_old,host=own_old['hostname']);last=0.
    while same_process(expected) or not (DATA/'RESULT.json').exists():
        boundary()
        if not before_cutoff():raise RuntimeError('cutover deadline; preserve parked groups and notify')
        if time.monotonic()-last>=10:
            atomic_json(RUNROOT/'HEARTBEAT.json',dict(utc=utc(),status='waiting_original8_workers_finish_claimed_groups',
                pending_groups=len(parked),pending_first_sources=sum(len(g['sources']) for g in parked),original_process=own_old,
                formal_GPU_entries_by_new_wave=0));last=time.monotonic()
        time.sleep(1)
    result=read(DATA/'RESULT.json');manager=read(DATA/'chain/MANAGER_STARTED.json')['process']
    if not result['all_owned_descendants_exited'] or group_members(manager['pgid'],manager['pid']) or same_process(manager):
        raise RuntimeError('original family exit not verified')
    if result['exit_code']!=0 or result.get('fatal'):raise RuntimeError('original wave failed during safe drain; audit before requeue')
    if not result['occupancy_handoff_complete']:raise RuntimeError('original guard restoration not verified')
    # Historical wave summary stays immutable even though task-wide tables are
    # regenerated after all parked groups finish under the same source budget.
    for name in ['RESULT.json','FINAL_SUMMARY.json','RESOURCE_SUMMARY.json','FINAL_CELLS.csv','PAIRED.json','MASTER_UPDATE.md']:
        source=DATA/name
        if source.exists():
            target=RUNROOT/'evidence'/('FIRST8_'+name)
            with target.open('xb') as f:f.write(source.read_bytes())
    new_json(RUNROOT/'PREDECESSOR_EXIT_ACK.json',dict(utc=utc(),original_process=own_old,
        original_result=ref(DATA/'RESULT.json'),original_manager=manager,formal_group_empty=True,
        whole_family_exited=True,guard_restored=True,remaining_groups=len(parked),remaining_first_sources=sum(len(g['sources']) for g in parked),
        old_scientific_attempts=read(DATA/'ATTEMPT_COUNTER.json')['reserved_attempts'],interruptions=0))
