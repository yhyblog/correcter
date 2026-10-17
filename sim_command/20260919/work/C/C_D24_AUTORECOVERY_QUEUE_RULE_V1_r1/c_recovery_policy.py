"""CPU policy gates; scientific execution remains with each unique C queue."""
import datetime,fcntl,hashlib,json,os,socket,time
from pathlib import Path
from ops_io import read,new_json,atomic_json,utc,ref,sha,verify,same_process,process_identity
C=Path(__file__).resolve().parents[3]
ROOT=C/'results/C/C_D24_AUTORECOVERY_QUEUE_RULE_V1'
ISSUES=C/'nodes/C/issues'
OUTBOX=C/'nodes/C/outbox'
AUTH=C/'deadline_20260924/AUTONOMOUS_RECOVERY_AND_SKIP_AUTHORIZATION_V2.json'
AUTH_SHA='0e0c6a309bf90c1d79d75d34a7d96470704c60e084c9b05b76621115341f82f7'
TASK='C_D24_AUTORECOVERY_QUEUE_RULE_V1'
EXECUTOR='01a0c793-10d2-7791-a250-fd65d88e1ccb'
ANALYSIS='01a0b91f-355f-7cd1-ae36-412500534ffb'
X=C/'results/C/C_D24_FULL_Q_LOSS_REFRESH_V1'
P=C/'results/C/C_D24_PI05_SELECTED_H40_H50_V1'
ALLOWED={X.name:X,P.name:P}
POST_SHA='fa907477112320e7f8356282c5ba64742452172dee998e9efc20a82b92b9c4b1'
COMPAT_SHA='2ae5a001cec168399a9733d038ed56d1ebeefd311081999f45429dc75e24ac16'
def snapshot(p):return read(p) if Path(p).is_file() else {}

def authority():
    a=read(AUTH);q=read(C/'persistent_queue/CONTROL.json');ident=read(C/'nodes/C/identity.json')
    if sha(AUTH)!=AUTH_SHA or a['status']!='released' or socket.gethostname()!=a['nodes']['C']['host'] or ident['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():raise ValueError('C recovery host/boot/grant mismatch')
    if not any(v.get('task_id')==TASK and v['authorization']['sha256']==AUTH_SHA for v in q['nodes']['C'].get('control_plane_followups',[])):raise ValueError('C CPU followup not registered')
    if a['new_GPU_claims']!=0 or a['scientific_compute_added']!=0 or a['analysis_wait_timeout_seconds']!=1800:raise ValueError('operational scope changed')
    for k in ['rule','selection_rule','runtime_compatibility','predecessor']:verify(a[k],base=C)
    return a

def consume(root,component):
    a=authority();root=Path(root)
    if root not in [ROOT,X,P]:raise ValueError('recovery not authorized for historical/foreign task')
    row=dict(utc=utc(),component=component,task_id=root.name,authorization=ref(AUTH),Post_selection_override=ref(C/a['selection_rule']['path']),runtime_compatibility=ref(C/a['runtime_compatibility']['path']),same_fault_max_corrected_restarts=2,per_failed_source_max_corrected_retry=1,analysis_timeout_seconds=1800,issues=str(ISSUES),outbox=str(OUTBOX),valid_success_and_failure_replay=False,owner_selection_budget_deadline_bypass=False,continue_independent_tasks_immediately=True,scientific_compute_added=0,GPU_calls=0)
    atomic_json(root/('RECOVERY_POLICY_'+component.upper()+'.json'),row);return row

def classify(error):
    text=str(error).lower()
    if any(s in text for s in ['selection','post-only','ownership','transferred','source changed','action scale','physics cadence','model changed']):return 'scientific_or_ownership_dependency'
    if any(s in text for s in ['ram','out of memory','storage','no space left']):return 'resource_constraint'
    if any(s in text for s in ['publication','serializ','json','file','path','no such','stale','i/o']):return 'engineering'
    return 'engineering_requires_specific_diagnosis'

def issue(root,error,*,kind=None,unit='stage_or_dependency',blocked=None,continuable=None,evidence=None,decision_required=None,signature=None):
    root=Path(root);identity=str(root)+'|'+unit+'|'+(signature or str(error))
    iid='C_recovery_'+hashlib.sha256(identity.encode()).hexdigest()[:20];dest=ISSUES/(iid+'.json')
    if dest.exists():return read(dest)
    now=time.time()
    row=dict(issue_id=iid,node='C',task_id=root.name,task_root=str(root),unit=unit,reported_at=utc(),reported_at_unix=now,error=error,kind=kind or classify(error),attempted_repairs=[],decision_required=decision_required or 'Concrete engineering fix or required scientific/ownership publication; an ACK is not a decision.',blocked_tasks=blocked or [root.name],continuable_tasks=continuable or [],analysis_response_due_at=datetime.datetime.fromtimestamp(now+1800,datetime.timezone.utc).isoformat(),analysis_response_due_unix=now+1800,status='reported',evidence=evidence or [],unchanged_blind_retry=False,response_path=str(ISSUES/(iid+'_DECISION.json')),executor_thread=EXECUTOR)
    try:new_json(dest,row)
    except FileExistsError:return read(dest)
    event=dict(event_id=iid,event_type='operational_issue',node='C',synthetic=False,target_thread_id=ANALYSIS,issue_path=str(dest),issue_at_report=ref(dest),utc=utc(),message=f'C 自主恢复问题 {iid}：读取 {dest}。现有科学进程和合法终局保留；具体可执行决定可写 {row["response_path"]}。普通 ACK 不重置1800秒时限，选择/所有权不因超时豁免；独立授权任务继续。')
    new_json(OUTBOX/(iid+'.json'),event);return row

def record_fault(root,error,**extra):
    # Publication failure must not mask the manager's original error or cleanup.
    try:return issue(root,error,**extra)
    except Exception as exc:
        try:atomic_json(Path(root)/'RECOVERY_ISSUE_WRITE_ERROR.json',dict(utc=utc(),original_error=error,report_error=repr(exc)))
        except Exception:pass
        return None

def actionable(decision,row):
    return (decision.get('issue_id')==row['issue_id'] and decision.get('status') in ['released','actionable']
        and decision.get('action') in ['apply_documented_fix','publish_required_dependency','defer_preserving_results','continue_independent_authorized_task']
        and bool(decision.get('evidence') or decision.get('authorization')))

def advance_issue(row,decision,now):
    result=dict(row)
    if actionable(decision,row) and row.get('status')!='actionable_decision_available':result.update(status='actionable_decision_available',decision_at=utc(),decision_action=decision['action'])
    elif row['status'] in ['reported','awaiting_analysis'] and now>=row['analysis_response_due_unix']:
        result.update(status='blocked_deferred',deferred_at=utc(),deferred_at_unix=now,next_action='continue independent eligible tasks; retain missing prerequisites')
    return result

def timers():
    for path in ISSUES.glob('C_recovery_*.json'):
        if path.name.endswith('_DECISION.json'):continue
        old=read(path);decision_path=Path(old['response_path']);d=snapshot(decision_path);new=advance_issue(old,d,time.time())
        if new!=old:
            if actionable(d,old):new['decision']=ref(decision_path)
            atomic_json(path,new)

def legal_terminal(row):
    return row.get('status')=='complete' and type(row.get('success')) is bool

def validate_repair(row,fix,units,terminal_by_unit,budget,*,family_exited,attempts_by_unit=None):
    if not fix.get('change') or not fix.get('evidence') or fix.get('science_changed') is not False:raise ValueError('specific documented engineering correction required')
    fingerprint=hashlib.sha256(json.dumps(fix,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    attempts=row.get('attempted_repairs',[])
    if len(attempts)>=2:raise ValueError('same-fault corrected restart cap reached')
    if any(a.get('fix_fingerprint')==fingerprint for a in attempts):raise ValueError('unchanged retry of same correction forbidden')
    if not family_exited:raise ValueError('own family must exit before corrected continuation')
    if len(units)!=len(set(units)) or len(units)>budget:raise ValueError('unit uniqueness/budget gate')
    for u in units:
        value=terminal_by_unit.get(u,{})
        if legal_terminal(value) or value.get('status') in ['user_cancelled','cancelled','closed_historical']:raise ValueError('valid/cancelled/historical unit cannot replay')
        if (attempts_by_unit or {}).get(u,0)>=2:raise ValueError('per-source one corrected retry exhausted')
        if (attempts_by_unit or {}).get(u,0)>=1 and any(u in a.get('units',[]) for a in attempts):raise ValueError('corrected continuation already reserved for failed source')
    return fingerprint

def repair_gate(issue_path,fix,units,terminal_by_unit,budget,*,family_exited,attempts_by_unit=None):
    """Durable CPU reservation for a later correction; it launches no science."""
    authority();local=Path('/tmp/corrector_C_autorecovery_r1');local.mkdir(exist_ok=True)
    with (local/'repair.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        row=read(issue_path);fingerprint=validate_repair(row,fix,units,terminal_by_unit,budget,family_exited=family_exited,attempts_by_unit=attempts_by_unit)
        for evidence in fix['evidence']:
            if not isinstance(evidence,dict) or 'path' not in evidence or 'sha256' not in evidence:raise ValueError('fix evidence must be inspectable file references')
            verify(evidence,base=C)
        attempt=dict(fix=fix,fix_fingerprint=fingerprint,units=units,utc=utc(),state='reserved_for_corrected_continuation',scientific_launch=False)
        row['attempted_repairs'].append(attempt);atomic_json(issue_path,row);return row

def live_identity(row):
    return same_process(dict(row,host=row.get('host',row.get('hostname')))) if row else False

def own_family_exited(root):
    root=Path(root);owner=snapshot(root/'PROCESS.json');terminal=snapshot(root/'RESULT.json')
    if live_identity(owner) or not terminal.get('all_owned_descendants_exited'):return False
    # Host /proc identity and process groups, without querying a GPU.
    for path in (root/'chains').glob('*/MANAGER_STARTED.json'):
        identity=read(path)['process']
        if live_identity(identity):return False
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():continue
            try:
                f=(proc/'stat').read_text().rsplit(') ',1)[1].split()
                if int(f[2])==identity['pgid'] and f[0]!='Z':return False
            except (OSError,ValueError,IndexError):pass
    return True

def current_budgets():
    nx=snapshot(X/'ATTEMPT_COUNTER.json').get('reserved_attempts',0);np=snapshot(P/'ATTEMPT_COUNTER.json').get('count',0)
    return {X.name:dict(stage_used=nx,stage_cap=1100,node_used=11943+nx+np,node_cap=14000),P.name:dict(stage_used=np,stage_cap=2200,node_used=11943+nx+np,node_cap=16000)}

def unfinished_units(root):
    """Read only this active task. Partial job completion never discards a tail."""
    root=Path(root)
    if root not in [X,P]:raise ValueError('historical tasks not reopened')
    expected={};states={};claims=set();evidence=[]
    if root==X:
        for method in ['Post','Velocity']:
            for s in read(root/'config/TEST_SOURCES.json')['sources']:expected[method+'/'+s['source_id']]=dict(source=s,method=method)
        for path in (root/'claims/attempts').glob('*.json'):
            r=read(path)
            if r.get('phase')=='evaluate':claims.add(r['identity'])
        for path in (root/'evaluation').glob('*/*/RESULT.json'):
            r=read(path);key=path.parents[1].name+'/'+path.parent.name
            if key not in expected:raise ValueError('native source outside original scope')
            states[key]=dict(r,result_path=str(path))
    else:
        if not (root/'JOB_INDEX.json').exists():return dict(expected=0,remaining=[],states={},claims=[],scope='ownership not yet granted')
        for jr in read(root/'JOB_INDEX.json')['jobs']:
            j=read(jr['path'])
            for s in j['sources']:expected[j['cell_id']+'__'+s['source_id']]=dict(source=s,job_id=j['job_id'],H=j['H'],method=j['method'])
        for path in (root/'unit_claims').glob('*.json'):claims.add(read(path)['unit_id'])
        for path in (root/'runs').glob('*/episodes/*/RESULT.json'):
            r=read(path);uid=r['unit_id']
            if uid not in expected:raise ValueError('pi05 source outside exact transfer')
            states[uid]=dict(r,result_path=str(path))
        # A complete job's embedded source terminal can salvage a missing export.
        for path in (root/'runs').glob('*/RESULT.json'):
            for r in read(path).get('episodes',[]):
                uid=r.get('unit_id')
                if uid not in expected or uid in states or not legal_terminal(r) or r.get('terminal') is not True:continue
                if any(r.get(k)!=expected[uid]['source'][k] for k in ['source_id','task','env_seed','policy_seed']):raise ValueError('log-derived terminal identity mismatch')
                states[uid]=dict(r,result_path=str(path),log_derived=True,missing_costs_not_imputed=True);evidence.append(str(path))
    if claims-set(expected):raise ValueError('claim outside authorized task scope')
    remaining=[]
    for uid,definition in expected.items():
        r=states.get(uid,{})
        if legal_terminal(r) or r.get('status') in ['user_cancelled','cancelled']:continue
        remaining.append(dict(unit_id=uid,**definition,status=r.get('status','unknown_entered' if uid in claims else 'not_started'),prior_attempts=1 if uid in claims else 0))
    return dict(expected=len(expected),remaining=remaining,states=states,claims=sorted(claims),log_recovered_evidence=sorted(set(evidence)))

def prepare_resume(root,issue_path,fix):
    """Called by the fixed executor after a concrete fix; no model/GPU calls."""
    root=Path(root);authority()
    if not own_family_exited(root):raise ValueError('live scientific family: no continuation plan')
    cfg=read(root/'config/CONFIG.json')
    if time.time()>=cfg['absolute_wall_deadline_unix']:raise ValueError('scientific cutoff expired')
    from selection_bridge import locked_post_choice
    selection=locked_post_choice()
    if selection is None:raise ValueError('complete Post selection required')
    if root==P:
        consumed=read(root/'TRANSFER_CONSUMED.json');verify(consumed['transfer'],base=C)
    u=unfinished_units(root);budget=current_budgets()[root.name];remaining_budget=min(budget['stage_cap']-budget['stage_used'],budget['node_cap']-budget['node_used'])
    units=[v['unit_id'] for v in u['remaining']]
    if len(units)>remaining_budget:raise ValueError('remaining units exceed unchanged attempt cap; preserve issue')
    # A different issue ID must not grant another corrected retry of the same unit.
    reserved_counts={v['unit_id']:v['prior_attempts'] for v in u['remaining']}
    for prior_path in (ROOT/'resume_plans').glob('*.json'):
        prior=read(prior_path)
        if prior['task_id']!=root.name:continue
        for v in prior['remaining']:
            if v['unit_id'] in reserved_counts:reserved_counts[v['unit_id']]+=1
    row=repair_gate(issue_path,fix,units,u['states'],remaining_budget,family_exited=True,attempts_by_unit=reserved_counts)
    p=ROOT/'resume_plans'/f"{row['issue_id']}_r{len(row['attempted_repairs'])}.json"
    new_json(p,dict(task_id=root.name,utc=utc(),status='corrected_continuation_manifest',issue=str(issue_path),fix=fix,remaining=u['remaining'],preserved_valid=sum(legal_terminal(v) for v in u['states'].values()),log_recovered_evidence=u.get('log_recovered_evidence',[]),budget=budget,selection=selection['selection_ref'],whole_own_family_exit_checked=True,launch_owner='fixed original executor using this task scientific entry and grant',new_scientific_units=0))
    return p
