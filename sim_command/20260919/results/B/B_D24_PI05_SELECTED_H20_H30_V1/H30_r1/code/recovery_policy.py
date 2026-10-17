"""Shared B-private operational policy, consumed at each future formal entry."""
import hashlib,json,socket,time
from pathlib import Path
C=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
CONTROL_ROOT=C/'results/B/B_D24_AUTORECOVERY_QUEUE_RULE_V1'
ISSUES=C/'nodes/B/issues'
OUTBOX=C/'nodes/B/outbox'
AUTH=C/'deadline_20260924/AUTONOMOUS_RECOVERY_AND_SKIP_AUTHORIZATION_V1.json'
AUTH_SHA='87878b0e2019048935904d639d1d15a1af9f0778047171a508054fecaadd4ab0'
THREAD='01a0b91f-355f-7cd1-ae36-412500534ffb'
from qio import read,new_json,atomic_json,utc,ref,sha

def consume(root,component):
 a=read(AUTH);q=read(C/'persistent_queue/CONTROL.json')
 if sha(AUTH)!=AUTH_SHA or a['status']!='released' or a['tasks']['B']['host']!=socket.gethostname():raise ValueError('B recovery authority mismatch')
 if not any(v.get('task_id')=='B_D24_AUTORECOVERY_QUEUE_RULE_V1' and v['authorization']['sha256']==AUTH_SHA for v in q['nodes']['B'].get('control_plane_followups',[])):raise ValueError('B recovery followup not registered')
 record=dict(utc=utc(),component=component,authorization=ref(AUTH),Post_selection_override=ref(C/'deadline_20260924/POST_LED_SELECTION_OVERRIDE_V1.json'),
  runtime_compatibility=ref(C/'deadline_20260924/AUTORUN_LIVE_CHAIN_COMPATIBILITY_V1.json'),same_fault_max_corrected_restarts=2,
  analysis_timeout_seconds=1800,issues=str(ISSUES),outbox=str(OUTBOX),valid_scientific_terminal_replay=False,
  owner_and_selection_gates_bypass=False,continue_independent_tasks_immediately=True)
 atomic_json(Path(root)/('RECOVERY_POLICY_'+component.upper()+'.json'),record)
 return record

def classify(error):
 text=str(error).lower()
 if any(s in text for s in ['selection','post-only','ownership','transferred','source changed','action scale','physics cadence','model changed']):return 'scientific_or_ownership_decision'
 if any(s in text for s in ['ram','out of memory','storage','cuda error: out of memory']):return 'resource_constraint'
 if any(s in text for s in ['publication','serializ','json','file','path','no such','stale','i/o']):return 'engineering'
 return 'engineering_requires_diagnosis'

def issue(root,error,*,kind=None,blocked=None,continuable=None,evidence=None):
 root=Path(root);key=hashlib.sha256((str(root)+'|'+str(error)).encode()).hexdigest()[:20];iid='B_recovery_'+key;dest=ISSUES/(iid+'.json')
 if dest.exists():return read(dest)
 now=time.time();kind=kind or classify(error)
 row=dict(issue_id=iid,node='B',task=root.name,unit='stage_or_dependency',reported_at=utc(),reported_at_unix=now,error=error,
  kind=kind,attempted_repairs=[],decision_required='Resolve only the stated scientific/ownership dependency, or provide a concrete engineering correction; ACK is not a decision.',
  blocked_tasks=blocked or [root.name],continuable_tasks=continuable or [],analysis_response_due_at=__import__('datetime').datetime.fromtimestamp(now+1800,__import__('datetime').timezone.utc).isoformat(),
  analysis_response_due_unix=now+1800,status='reported',evidence=evidence or [],unchanged_blind_retry=False,
  response_path=str(ISSUES/(iid+'_DECISION.json')),executor_thread='01a0b9c5-1e4b-7b73-9336-229e6df349a2')
 new_json(dest,row)
 new_json(OUTBOX/(iid+'.json'),dict(event_id=iid,kind='analysis_decision_needed',target_thread_id=THREAD,node='B',synthetic=False,
  issue=ref(dest),message=f"B 自主恢复问题 {iid}：读取 {dest}。原结果保留；若需决策，将具体可执行决定写入 {row['response_path']}。普通 ACK 不重置30分钟时限；B继续依赖无关的已授权任务。",utc=utc()))
 return row

def repair_gate(issue_path,fix_record,units,terminal_status_by_unit,budget_remaining):
 """CPU precondition for a later executor's documented corrected continuation."""
 row=read(issue_path)
 if not fix_record.get('change') or not fix_record.get('evidence') or fix_record.get('science_changed') is not False:raise ValueError('documented engineering correction required')
 if len(row.get('attempted_repairs',[]))>=2:raise ValueError('same-fault corrected restart cap reached')
 if any(terminal_status_by_unit.get(u)=='complete' for u in units):raise ValueError('legal terminal cannot replay')
 if len(set(units))!=len(units) or len(units)>budget_remaining:raise ValueError('unique unit/budget gate')
 row['attempted_repairs'].append(dict(fix=fix_record,units=units,utc=utc()));atomic_json(issue_path,row)
 return row
