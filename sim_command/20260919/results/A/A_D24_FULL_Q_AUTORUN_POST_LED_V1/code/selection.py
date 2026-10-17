"""Immutable dev-only loss choice and complete-Q ensemble resolution."""
from pathlib import Path
from fractions import Fraction
import copy
from paths import ROOT,ORIGINAL,SELECTION_ROOT,EVIDENCE_ROOTS,CAMPAIGN,TASK,POST_OVERRIDE_SHA,EVENT_PREFIX
from qio import read,new_json,utc,sha,ref

LOSSES=['L00','L10','L01','L11']
AUX={'L00':0,'L10':1,'L01':1,'L11':2}

def choose_development(rows,source_rows):
 expected={r['source_id']:r for r in source_rows};tasks=sorted({r['task'] for r in source_rows});scores=[];totals={}
 if len(expected)!=100 or len(tasks)!=5:raise ValueError('development identity')
 for loss in LOSSES:
  score=Fraction(0,1);successes=0
  for fit in [9101,9102,9103]:
   for method in ['Post']:
    cell=f'DEV_{loss}_s{fit}_{method}_H10';chosen=[r for r in rows if r['cell_id']==cell and r['status']=='complete']
    if len(chosen)!=100 or {r['source_id'] for r in chosen}!=set(expected):raise ValueError('incomplete development cell '+cell)
    for row in chosen:
     if type(row['success']) is not bool:raise ValueError('nonboolean outcome')
     for k in ['task','env_seed','policy_seed']:
      if row[k]!=expected[row['source_id']][k]:raise ValueError('dev source mismatch')
    for task in tasks:
     rs=[r for r in chosen if r['task']==task]
     if len(rs)!=20:raise ValueError('dev task denominator')
     ns=sum(r['success'] for r in rs);score+=Fraction(ns,20*15);successes+=ns
     scores.append(dict(loss=loss,fit_seed=fit,method=method,task=task,successes=ns,valid=20,success_rate=ns/20))
  totals[loss]=dict(successes=successes,valid=300,equal_weight_score=float(score),score_numerator=score.numerator,score_denominator=score.denominator)
 best=min(LOSSES,key=lambda loss:(-Fraction(totals[loss]['score_numerator'],totals[loss]['score_denominator']),AUX[loss],LOSSES.index(loss)))
 return dict(chosen_loss=best,fixed_fit_seed=9101,scores=scores,loss_scores=totals,selection_rule='Post only: equal five tasks x three fit seeds; exact fraction; fewer auxiliary terms then L00,L10,L01,L11; deployment fit9101 fixed in advance',Post_only=True,selection_method='Post',Velocity_selection_weight=0,Post_selection_override_sha256=POST_OVERRIDE_SHA,Post_development_valid=1200,selection_valid=1200,development_valid=sum(r['status']=='complete' for r in rows),Velocity_development_valid=sum(r['status']=='complete' and '_Velocity_' in r['cell_id'] for r in rows),development_technical_missing=0,test_used=False,Velocity_inherits_Post_configuration=True,Velocity_current_paper_final_tables_figures=False,Velocity_separate_other_work=True,current_paper_methods=['Post'])

def make_selection():
 override=CAMPAIGN/'deadline_20260924/POST_LED_SELECTION_OVERRIDE_V1.json'
 if sha(override)!=POST_OVERRIDE_SHA:raise ValueError('Post-only override changed')
 if (SELECTION_ROOT/'SELECTION.json').exists():return locked_selection()
 from publication_data import load_evidence
 _,_,_,rows=load_evidence()
 # No test scores participate: admission of all later stages requires this lock.
 chosen=choose_development([r for r in rows if r['stage']=='DEV'],read(ROOT/'SOURCE_INDEX.json')['source_sets']['DEV'])
 e=read(ROOT/'ENSEMBLES.json')['ensembles'][f"{chosen['chosen_loss']}_s9101"]
 plan=read(ROOT/'RESUME_PLAN.json')
 chosen.update(task_id=ORIGINAL.name,execution_task_id=TASK,execution_run=EVENT_PREFIX,status='selected_locked',utc=utc(),ensemble=e,weights=e['members'],preprocessing='frozen train-only fields retained per member; see preprocessing_evidence',source_table=str(ORIGINAL/'SOURCE_INDEX.json'),training_complete=ref(ORIGINAL/'TRAINING_COMPLETE.json'),no_test_based_change=True,development_evidence_roots=[str(p) for p in EVIDENCE_ROOTS],original_valid_DEV=plan['old_valid'],unentered_DEV_continuation=plan['remaining_DEV_first'],selection_override=ref(override))
 new_json(SELECTION_ROOT/'SELECTION.json',chosen)
 new_json(SELECTION_ROOT/'SELECTION_LOCK.json',dict(selection=ref(SELECTION_ROOT/'SELECTION.json'),utc=utc(),immutable=True))
 new_json(ROOT/'outbox/selection_locked.json',dict(event_id=EVENT_PREFIX+'_selection_locked',synthetic=False,kind='selection_locked',result=str(SELECTION_ROOT/'SELECTION.json'),utc=utc()))
 return chosen

def locked_selection():
 if not (ROOT/'SELECTION.json').is_file() or not (ROOT/'SELECTION_LOCK.json').is_file():raise FileNotFoundError('complete immutable dev selection is not published')
 lock=read(ROOT/'SELECTION_LOCK.json');row=read(ROOT/'SELECTION.json')
 if sha(ROOT/'SELECTION.json')!=lock['selection']['sha256'] or row['status']!='selected_locked' or row['test_used'] or row['fixed_fit_seed']!=9101:raise ValueError('selection lock changed')
 if row.get('Post_only') is not True or row.get('Velocity_selection_weight')!=0 or row.get('Post_selection_override_sha256')!=POST_OVERRIDE_SHA or row.get('Post_development_valid')!=1200:raise ValueError('joint/partial/non-Post selection forbidden for new formal admission')
 return row

def engine_config(job):
 cfg=copy.deepcopy(read(ROOT/'config/CONFIG.json'));key=job['ensemble_key']
 if key=='SELECTED':key=locked_selection()['ensemble']['key']
 e=read(ROOT/'ENSEMBLES.json')['ensembles'][key]
 cfg.update(critic_assets=e['assets'],selected_model=dict(member_hashes=e['member_hashes'],ensemble=e),loss=e['loss'],fit_seed=e['fit_seed'])
 return cfg
