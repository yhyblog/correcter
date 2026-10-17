"""Consume immutable A publication; exact source partition, no cross-host PID tests."""
from pathlib import Path
import time
from paths import ROOT,CAMPAIGN,ORIGINAL,A_HANDOFF,TRANSFER,AUTH_SHA,TASK
from qio import read,new_json,ref,verify,utc

def assert_not_A_owned(job_id,unit_id=None):
    for root in (ORIGINAL,A_HANDOFF,CAMPAIGN/'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1'):
        if (root/'claims'/(job_id+'.json')).exists():raise ValueError('A already claimed job '+job_id)
        if unit_id and (root/'unit_claims'/(unit_id+'.json')).exists():raise ValueError('A already admitted unit '+unit_id)

def validate_partition(row,planned,selected):
    if row.get('status')!='TRANSFER_READY' or row.get('authorization_sha256')!=AUTH_SHA or row.get('old_manager_cannot_dispatch') is not True or row.get('A_new_manager_contains_remote_jobs') is not False:raise ValueError('source ownership handoff not established')
    if row['selection']['sha256']!=selected['A_selection']['sha256'] or row['selection_lock']['sha256']!=selected['A_lock']['sha256'] or row['chosen_loss']!=selected['chosen_loss'] or row['fixed_fit_seed']!=9101 or row['ensemble']!=selected['ensemble']:raise ValueError('transfer selection mismatch')
    node=row['nodes']['C']
    if node['task_id']!=TASK or node['Hs']!=[40,50] or node['attempt_cap']!=2200:raise ValueError('C transfer task/budget')
    if node['jobs']!=row['owners']['C']:raise ValueError('transfer job list mismatch')
    expected={j['cell_id']+'__'+s['source_id']:(j,s) for j in planned.values() for s in j['sources']}
    jobs={};granted={}
    for r in node['jobs']:
        jid=r['job_id']
        if jid in jobs or jid not in planned or r['owner']!='C':raise ValueError('duplicate/foreign transfer job')
        j=planned[jid];sources=r['sources'];original={s['source_id']:s for s in j['sources']}
        if not sources or any(s!=original.get(s['source_id']) for s in sources):raise ValueError('changed transfer source')
        if [s for s in j['sources'] if s['source_id'] in set(r['source_ids'])]!=sources:raise ValueError('source order changed')
        ids=[j['cell_id']+'__'+s['source_id'] for s in sources]
        if r['source_ids']!=[s['source_id'] for s in sources] or r['unit_ids']!=ids or len(set(ids))!=len(ids):raise ValueError('transfer source duplicate/identity')
        if any(r[k]!=j[k] for k in ['cell_id','method','H','mode']):raise ValueError('transfer scientific configuration changed')
        for uid,s in zip(ids,sources):
            if uid in granted:raise ValueError('duplicate granted unit')
            granted[uid]=dict(unit_id=uid,job_id=jid,cell_id=j['cell_id'],source_id=s['source_id'],source=s,method=j['method'],H=j['H'],mode=j['mode'],fit_seed=9101)
        jobs[jid]=dict(j,sources=sources)
    if len(node['units'])!=len(granted) or {u['unit_id']:u for u in node['units']}!=granted or node['first_count']!=len(granted) or len(granted)>2000:raise ValueError('unit publication disagreement')
    excluded=[u for u in row.get('excluded_A_units',[]) if u['owner']=='C']
    excluded_ids={u['unit_id'] for u in excluded}
    if len(excluded_ids)!=len(excluded) or set(granted)&excluded_ids or set(granted)|excluded_ids!=set(expected):raise ValueError('planned/transferred/A-retained partition incomplete')
    for u in excluded:
        j,s=expected[u['unit_id']]
        if u['job_id']!=j['job_id'] or u['source']!=s:raise ValueError('exclusion source mismatch')
    other={u['unit_id'] for name,n in row['nodes'].items() if name!='C' for u in n['units']}
    if set(granted)&other:raise ValueError('cross-node ownership overlap')
    return jobs,granted,excluded

def verify_dispatcher_exit(evidence):
    # Post-only continuation publishes both superseded dispatchers as a list.
    # The original format had the same references directly on the evidence object.
    if 'prior_families' in evidence:
        families=evidence['prior_families']
        if not isinstance(families,list) or {r.get('root') for r in families}!={str(ORIGINAL),str(A_HANDOFF)} or len(families)!=2:raise ValueError('both prior A dispatchers require exit evidence')
        verify(evidence['normal_stop_request'])
    else:families=[dict(evidence,root=str(ORIGINAL))]
    for family in families:
        root=Path(family['root'])
        if Path(family['whole_family_exit']['path'])!=root/'RESULT.json' or Path(family['manager_exit']['path'])!=root/'chain/MANAGER_EXIT.json':raise ValueError('dispatcher exit reference identity mismatch')
        if not read(verify(family['whole_family_exit']))['all_owned_descendants_exited'] or not read(verify(family['manager_exit']))['all_owned_processes_exited']:raise ValueError('original A dispatcher exit evidence absent')
    return families

def try_consume():
    if (ROOT/'TRANSFER_CONSUMED.json').exists():return consumed_transfer()
    if not TRANSFER.is_file():return None
    from selection import consumed_selection
    selected=consumed_selection();row=read(TRANSFER)
    ownership=read(CAMPAIGN/'deadline_20260924/FULL_Q_AUTORUN_OWNERSHIP_PLAN_V2.json')
    if row['ownership_plan']['sha256']!=ref(CAMPAIGN/'deadline_20260924/FULL_Q_AUTORUN_OWNERSHIP_PLAN_V2.json')['sha256']:raise ValueError('ownership plan changed')
    refs={r['job_id']:r for r in ownership['owners']['C']}
    planned={r['job_id']:read(verify(r)) for r in read(ROOT/'PLANNED_JOB_INDEX.json')['jobs']}
    jobs,units,excluded=validate_partition(row,planned,selected)
    for r in row['nodes']['C']['jobs']:
        if r['path']!=refs[r['job_id']]['path'] or r['sha256']!=refs[r['job_id']]['sha256']:raise ValueError('transfer original job reference mismatch')
    evidence=row['old_exit_evidence']
    verify_dispatcher_exit(evidence)
    continuation=read(verify(row['A_continuation_job_index']))
    if {r['job_id'] for r in continuation['jobs']}&set(planned):raise ValueError('A continuation can still dispatch C jobs')
    for u in units.values():assert_not_A_owned(u['job_id'],u['unit_id'])
    index=[]
    for jid,j in sorted(jobs.items(),key=lambda x:(x[1]['H'],x[1]['chunk'],x[1]['task_order'],x[1]['method'])):
        p=ROOT/'jobs'/(jid+'.json');new_json(p,j)
        index.append(dict(job_id=jid,**ref(p),original=refs[jid]))
    new_json(ROOT/'JOB_INDEX.json',dict(jobs=index,transferred_source_count=len(units),stage_order=[40,50],transfer=ref(TRANSFER)))
    new_json(ROOT/'TRANSFER_CONSUMED.json',dict(utc=utc(),task_id=TASK,transfer=ref(TRANSFER),selection=selected['A_selection'],first_count=len(units),jobs=len(jobs),excluded_A_units=excluded,job_index=ref(ROOT/'JOB_INDEX.json'),whole_A_host_exit_required=False))
    return consumed_transfer()

_checked_at=0.
_consumed=None
def consumed_transfer():
    global _checked_at,_consumed
    if _consumed is None or time.monotonic()-_checked_at>=15:
        row=read(ROOT/'TRANSFER_CONSUMED.json');verify(row['transfer']);verify(row['selection']);verify(row['job_index'])
        _consumed=row;_checked_at=time.monotonic()
    return _consumed
