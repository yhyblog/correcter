"""Exclusive, source-exact remote ownership after an immutable dev choice."""
from pathlib import Path
from paths import ROOT,ORIGINAL,PREVIOUS,TRANSFER_ROOT,PRIOR_EVIDENCE_ROOTS,EVIDENCE_ROOTS,CAMPAIGN,TASK,AUTH_SHA,POST_OVERRIDE_SHA,EVENT_PREFIX
from qio import read,new_json,sha,ref,utc,same_process

def original_exit_verified():
 rows=[]
 for root in PRIOR_EVIDENCE_ROOTS:
  result=read(root/'RESULT.json');manager=read(root/'chain/MANAGER_STARTED.json')['process'];end=read(root/'chain/MANAGER_EXIT.json')
  if not result['all_owned_descendants_exited'] or not end['all_owned_processes_exited'] or same_process(manager):raise RuntimeError('prior formal family has not exited: '+str(root))
  lifecycle=read(root/'chain/LIFECYCLE_STARTED.json')['process']
  if same_process(lifecycle):raise RuntimeError('prior lifecycle still running: '+str(root))
  rows.append(dict(root=str(root),manager_identity=manager,manager_exit=ref(root/'chain/MANAGER_EXIT.json'),whole_family_exit=ref(root/'RESULT.json')))
 return dict(prior_families=rows,normal_stop_request=ref(PREVIOUS/'POST_LED_DISPATCH_STOP_REQUEST.json'),reason='V1 metadata drain; V2 single-manager normal SIGTERM on explicit Post-only override; every admitted terminal preserved')

def publish_transfer():
 from selection import locked_selection
 choice=locked_selection();evidence=original_exit_verified()
 target=TRANSFER_ROOT/'TRANSFER_READY.json'
 if target.exists():
  prior=read(target)
  if prior['selection']['sha256']!=sha(ORIGINAL/'SELECTION.json'):raise ValueError('transfer selection changed')
  return prior
 frozen=read(CAMPAIGN/'deadline_20260924/FULL_Q_AUTORUN_OWNERSHIP_PLAN_V2.json')
 owner_jobs={};nodes={};excluded=[]
 for owner,Hs in [('B',[20,30]),('C',[40,50])]:
  jobs=[];units=[]
  for original_ref in frozen['owners'][owner]:
   j=read(original_ref['path'])
   if sha(original_ref['path'])!=original_ref['sha256'] or j['stage']!='MAIN' or j['H'] not in Hs or j['fit_seed']!=9101 or j['loss']!='SELECTED':raise ValueError('remote frozen job identity')
   jid=j['job_id'];job_claimed=any((root/'claims'/(jid+'.json')).exists() for root in EVIDENCE_ROOTS)
   remaining=[]
   for source in j['sources']:
    uid=j['cell_id']+'__'+source['source_id']
    claimed=job_claimed or any((root/'unit_claims'/(uid+'.json')).exists() for root in EVIDENCE_ROOTS)
    if claimed:excluded.append(dict(owner=owner,job_id=jid,unit_id=uid,source=source,reason='A_claimed_or_dispatched_remains_A'));continue
    remaining.append(source);units.append(dict(unit_id=uid,job_id=jid,cell_id=j['cell_id'],source_id=source['source_id'],source=source,method=j['method'],H=j['H'],mode=j['mode'],fit_seed=9101))
   if remaining:jobs.append(dict(original_ref,owner=owner,cell_id=j['cell_id'],method=j['method'],H=j['H'],mode=j['mode'],sources=remaining,source_ids=[s['source_id'] for s in remaining],unit_ids=[j['cell_id']+'__'+s['source_id'] for s in remaining]))
  if len({u['unit_id'] for u in units})!=len(units) or len(units)>2000:raise ValueError('remote ownership duplicates/cap')
  owner_jobs[owner]=jobs;nodes[owner]=dict(task_id=f'{owner}_D24_PI05_SELECTED_'+('_'.join('H'+str(h) for h in Hs))+'_V1',Hs=Hs,jobs=jobs,units=units,first_count=len(units),attempt_cap=2200,original_results=str(ORIGINAL),no_A_runtime_exit_barrier=True)
 if any(u['unit_id'] in {v['unit_id'] for v in nodes['C']['units']} for u in nodes['B']['units']):raise ValueError('cross-owner overlap')
 if excluded:raise RuntimeError('unexpected transferred-H A claims; explicit reconciliation needed before ownership publication')
 row=dict(schema='corrector_A_full_Q_source_exact_transfer_v2',status='TRANSFER_READY',utc=utc(),task_id=TASK,execution_run=EVENT_PREFIX,authorization_sha256=AUTH_SHA,Post_selection_override_sha256=POST_OVERRIDE_SHA,Post_only=True,Velocity_selection_weight=0,Velocity_current_paper_final_tables_figures=False,selection=ref(ORIGINAL/'SELECTION.json'),selection_lock=ref(ORIGINAL/'SELECTION_LOCK.json'),chosen_loss=choice['chosen_loss'],fixed_fit_seed=9101,ensemble=choice['ensemble'],owners=owner_jobs,nodes=nodes,excluded_A_units=excluded,old_manager_cannot_dispatch=True,old_exit_evidence=evidence,A_new_manager_contains_remote_jobs=False,A_continuation_job_index=ref(ROOT/'JOB_INDEX.json'),ownership_plan=ref(CAMPAIGN/'deadline_20260924/FULL_Q_AUTORUN_OWNERSHIP_PLAN_V2.json'),source_units_total=sum(n['first_count'] for n in nodes.values()))
 new_json(target,row)
 new_json(ROOT/'outbox/transfer_ready.json',dict(event_id=EVENT_PREFIX+'_transfer_ready',kind='transfer_ready',synthetic=False,result=str(target),utc=utc()))
 return row
