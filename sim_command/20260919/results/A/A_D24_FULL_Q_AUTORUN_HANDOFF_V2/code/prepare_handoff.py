"""Freeze only original, never-entered A units after the original family exits."""
import copy,json
from pathlib import Path
from paths import ROOT,ORIGINAL,CAMPAIGN,TASK,AUTH_SHA
from qio import read,new_json,ref,sha,utc

def remaining_sources(job,claims):
 return [s for s in job['sources'] if job['cell_id']+'__'+s['source_id'] not in claims]

def prepare():
 final=read(ORIGINAL/'RESULT.json');exit=read(ORIGINAL/'chain/MANAGER_EXIT.json')
 assert final['all_owned_descendants_exited'] and final['publication_completed'] and exit['all_owned_processes_exited']
 assert final['raw_lifecycle_exit']==0 and exit['fatal'] is None
 old_claims={p.stem:read(p) for p in (ORIGINAL/'unit_claims').glob('*.json')}
 old_good={}
 for p in (ORIGINAL/'runs').glob('*/episodes/*/RESULT.json'):
  q=p.with_name('SUMMARY_ROW.json');d=read(q if q.exists() else p)
  assert d['status']=='complete' and type(d['success']) is bool
  assert d['unit_id'] not in old_good
  old_good[d['unit_id']]=dict(path=str(p),source_id=d['source_id'],cell_id=d['cell_id'],stage=d['stage'])
 assert set(old_claims)==set(old_good) and len(old_good)==1546
 assert all(v['stage']=='DEV' for v in old_good.values())
 ownership=read(CAMPAIGN/'deadline_20260924/FULL_Q_AUTORUN_OWNERSHIP_PLAN_V2.json')
 index=read(ORIGINAL/'JOB_INDEX.json');idx={j['job_id']:j for j in index['jobs']}
 cfg=copy.deepcopy(read(ORIGINAL/'config/CONFIG.json'))
 cfg['cells']=[c for c in cfg['cells'] if c['stage'] in ['DEV','ABLATION','ONCE'] or c['stage']=='MAIN' and c['H']==10]
 cfg.update(task_id=TASK,run_stage='unentered_DEV_completion_then_selected_A_only',planned_episodes=5600,planned_prior_attempts=16442,max_episodes=4354,new_first_evaluations=4054,remaining_DEV_first_cap=854,post_selection_first_cap=3200,post_selection_attempt_cap=3500,original_authorization_attempt_cap=10100,original_attempts=1546,new_training_updates=0,training_root=str(ORIGINAL/'training'))
 new_json(ROOT/'config/CONFIG.json',cfg);cfgsha=sha(ROOT/'config/CONFIG.json')
 rows=[];stage_counts={};exclusions=[]
 for owned in ownership['owners']['A']:
  assert owned==idx[owned['job_id']]
  j=read(owned['path']);sources=remaining_sources(j,old_claims)
  assert j['stage']!='MAIN' or j['H']==10
  if not sources:exclusions.append(dict(job_id=j['job_id'],reason='all_sources_have_valid_original_terminal'));continue
  original=copy.deepcopy(j);j['sources']=sources;j['configuration_sha256']=cfgsha
  j.update(original_job_ref=owned,original_configuration_sha256=original['configuration_sha256'],continuation_task_id=TASK,unentered_only=True)
  path=ROOT/'jobs'/(j['job_id']+'.json');new_json(path,j)
  rows.append(dict(job_id=j['job_id'],path=str(path),sha256=sha(path)))
  stage_counts[j['stage']]=stage_counts.get(j['stage'],0)+len(sources)
 assert stage_counts=={'DEV':854,'ABLATION':1200,'MAIN':1000,'ONCE':1000},stage_counts
 new_json(ROOT/'JOB_INDEX.json',dict(jobs=rows,first_evaluations=4054,stage_first_evaluations=stage_counts,job_count=len(rows),job_chunk_maximum=5,no_completed_unit_replay=True,original_index=ref(ORIGINAL/'JOB_INDEX.json')))
 new_json(ROOT/'RESUME_PLAN.json',dict(utc=utc(),task_id=TASK,authorization_sha256=AUTH_SHA,old_first_attempts=1546,old_valid=1546,original_prior_D24_attempts=14896,prior_A_attempts=16442,remaining_DEV_first=854,remaining_A_tests_first=3200,new_attempt_cap=4354,post_selection_attempt_cap=3500,cumulative_cap=27000,job_count=len(rows),stage_counts=stage_counts,completed_original_units=old_good,excluded_jobs=exclusions,old_terminal=ref(ORIGINAL/'RESULT.json'),old_manager_exit=ref(ORIGINAL/'chain/MANAGER_EXIT.json'),normal_stop_already_completed=True,signal_needed=False,no_retry_or_new_initial_state=True))
 new_json(ROOT/'ORDERED_STAGES.json',dict(utc=utc(),stages=[dict(stage='ORIGINAL_EXIT',state='verified'),dict(stage='DEV_UNENTERED',first_max=854,training_updates=0),dict(stage='SELECTION',source=str(ORIGINAL/'SELECTION.json'),lock=str(ORIGINAL/'SELECTION_LOCK.json'),rule='original dev-only common loss, fixed fit9101'),dict(stage='TRANSFER',path=str(ROOT/'TRANSFER_READY.json'),B_H=[20,30],C_H=[40,50]),dict(stage='ABLATION',first_max=1200),dict(stage='MAIN_H10',methods=['Post','Velocity'],first_max=1000),dict(stage='ONCE_H10',methods=['Post','Velocity'],first_max=1000),dict(stage='CPU_INCREMENTAL_TABLES',wait_for_BC=False)],formal_workers=24,workers_per_GPU=3,old_12h_end_not_extended=True))
 return dict(job_count=len(rows),stage_counts=stage_counts)

if __name__=='__main__':print(json.dumps(prepare()))
