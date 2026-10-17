"""Post-led resumption preserving all admitted units from both prior families."""
import copy,json
from paths import ROOT,ORIGINAL,PREVIOUS,PRIOR_EVIDENCE_ROOTS,CAMPAIGN,TASK,AUTH_SHA,POST_OVERRIDE_SHA
from qio import read,new_json,ref,sha,utc

def remaining_sources(job,claims):
 return [s for s in job['sources'] if job['cell_id']+'__'+s['source_id'] not in claims]

def prepare():
 claims={};good={};prior_terminals=[]
 for root in PRIOR_EVIDENCE_ROOTS:
  final=read(root/'RESULT.json');end=read(root/'chain/MANAGER_EXIT.json')
  assert final['all_owned_descendants_exited'] and end['all_owned_processes_exited'] and end['fatal'] is None
  assert final['raw_lifecycle_exit']==0
  prior_terminals.append(ref(root/'RESULT.json'))
  for p in (root/'unit_claims').glob('*.json'):
   assert p.stem not in claims;claims[p.stem]=read(p)
  for p in (root/'runs').glob('*/episodes/*/RESULT.json'):
   q=p.with_name('SUMMARY_ROW.json');d=read(q if q.exists() else p)
   assert d['status']=='complete' and type(d['success']) is bool and d['stage']=='DEV'
   assert d['unit_id'] not in good
   good[d['unit_id']]=dict(path=str(p),source_id=d['source_id'],cell_id=d['cell_id'],stage=d['stage'])
 assert set(claims)==set(good) and 1546<=len(good)<2400
 assert not (ORIGINAL/'SELECTION.json').exists() and not (PREVIOUS/'TRANSFER_READY.json').exists()
 old_continuation=len(claims)-1546;remaining_DEV=2400-len(claims);remaining_first=remaining_DEV+3200
 ownership=read(CAMPAIGN/'deadline_20260924/FULL_Q_AUTORUN_OWNERSHIP_PLAN_V2.json')
 idx={j['job_id']:j for j in read(ORIGINAL/'JOB_INDEX.json')['jobs']}
 cfg=copy.deepcopy(read(PREVIOUS/'config/CONFIG.json'))
 cfg.update(task_id=TASK,run_stage='Post_only_selection_unentered_resume',planned_prior_attempts=14896+len(claims),max_episodes=4500-old_continuation,new_first_evaluations=remaining_first,remaining_DEV_first_cap=remaining_DEV,post_selection_first_cap=3200,post_selection_attempt_cap=3500,original_attempts=len(claims),selection_method='Post',Velocity_selection_weight=0,Post_selection_override_sha256=POST_OVERRIDE_SHA,current_paper_methods=['Post'],Velocity_other_work=True,new_training_updates=0)
 new_json(ROOT/'config/CONFIG.json',cfg);digest=sha(ROOT/'config/CONFIG.json');rows=[];counts={}
 for owned in ownership['owners']['A']:
  assert owned==idx[owned['job_id']];old=read(owned['path']);sources=remaining_sources(old,claims)
  assert old['stage']!='MAIN' or old['H']==10
  if not sources:continue
  j=copy.deepcopy(old);j['sources']=sources;j['configuration_sha256']=digest
  j.update(original_job_ref=owned,original_configuration_sha256=old['configuration_sha256'],continuation_task_id=TASK,unentered_only=True)
  path=ROOT/'jobs'/(j['job_id']+'.json');new_json(path,j);rows.append(dict(job_id=j['job_id'],path=str(path),sha256=sha(path)))
  counts[j['stage']]=counts.get(j['stage'],0)+len(sources)
 assert counts==dict(DEV=remaining_DEV,ABLATION=1200,MAIN=1000,ONCE=1000)
 new_json(ROOT/'JOB_INDEX.json',dict(jobs=rows,first_evaluations=remaining_first,stage_first_evaluations=counts,job_count=len(rows),job_chunk_maximum=5,no_completed_unit_replay=True,original_index=ref(ORIGINAL/'JOB_INDEX.json')))
 new_json(ROOT/'RESUME_PLAN.json',dict(utc=utc(),task_id=TASK,authorization_sha256=AUTH_SHA,Post_selection_override_sha256=POST_OVERRIDE_SHA,old_first_attempts=len(claims),old_valid=len(good),original_prior_D24_attempts=14896,prior_A_attempts=14896+len(claims),remaining_DEV_first=remaining_DEV,remaining_A_tests_first=3200,new_first=remaining_first,new_attempt_cap=4500-old_continuation,post_selection_attempt_cap=3500,cumulative_cap=27000,job_count=len(rows),stage_counts=counts,completed_original_units=good,prior_terminals=prior_terminals,original_1546_preserved=True,previous_continuation_first=old_continuation,no_retry_or_new_initial_state=True,normal_stop_reason='Post-only user override; prior manager had joint scoring cached'))
 new_json(ROOT/'ORDERED_STAGES.json',dict(utc=utc(),task_id=TASK,stages=[dict(stage='PRIOR_FAMILY_EXIT',state='verified'),dict(stage='DEV_UNENTERED',first_max=remaining_DEV,training_updates=0),dict(stage='POST_ONLY_SELECTION',source=str(ORIGINAL/'SELECTION.json'),lock=str(ORIGINAL/'SELECTION_LOCK.json'),Post_weight=1,Velocity_weight=0,fixed_fit_seed=9101),dict(stage='TRANSFER',path=str(PREVIOUS/'TRANSFER_READY.json'),B_H=[20,30],C_H=[40,50]),dict(stage='ABLATION',first_max=1200),dict(stage='MAIN_H10',methods=['Post','Velocity'],first_max=1000),dict(stage='ONCE_H10',methods=['Post','Velocity'],first_max=1000),dict(stage='CPU_TABLES',current_paper=['Post'],other_work=['Velocity'],wait_for_BC=False)],formal_workers=24,workers_per_GPU=3,old_12h_end_not_extended=True))
 return dict(job_count=len(rows),stage_counts=counts,old_valid=len(good),prior_A_attempts=14896+len(claims))

if __name__=='__main__':print(json.dumps(prepare()))
