"""Immutable dev-only loss choice and complete-Q ensemble resolution."""
from pathlib import Path
from fractions import Fraction
import copy
from paths import ROOT,TASK
from qio import read,new_json,utc,sha,ref

LOSSES=['L00','L10','L01','L11']
AUX={'L00':0,'L10':1,'L01':1,'L11':2}

def publish_ensembles():
 if (ROOT/'TRAINING_COMPLETE.json').exists():return read(ROOT/'TRAINING_COMPLETE.json')
 cfg=read(ROOT/'config/TRAIN.json');ensembles={};fits=[]
 for loss in LOSSES:
  for seed in cfg['fit_seeds']:
   key=f'{loss}_s{seed}';assets=ROOT/'ensembles'/key;hashes={};members=[]
   for member in cfg['members']:
    directory=ROOT/'training'/f's{seed}_m{member}'
    result=read(directory/loss/'RESULT.json')
    if result['status']!='complete' or result['updates']!=4000 or result['trainable_parameters']!=7058:raise ValueError('incomplete full-Q member')
    path=Path(result['checkpoint']);digest=sha(path)
    if digest!=result['checkpoint_sha256']:raise ValueError('new Q checkpoint changed')
    target=assets/'models/refit'/f'member_{member}'/'selected.pt';target.parent.mkdir(parents=True,exist_ok=True);target.symlink_to(path)
    hashes[str(member)]=digest;members.append(dict(member=member,checkpoint=str(path),sha256=digest,preprocessing_evidence=str(directory/'INPUT_READY.json')));fits.append(result)
   new_json(assets/'ranking.json',dict(horizon=10,model_hashes=hashes,loss=loss,fit_seed=seed,training='all7058 fresh; fixed4000',members=members))
   ensembles[key]=dict(key=key,loss=loss,fit_seed=seed,assets=str(assets),member_hashes=hashes,members=members,ranking=ref(assets/'ranking.json'))
 new_json(ROOT/'ENSEMBLES.json',dict(ensembles=ensembles,utc=utc(),training_updates=sum(r['updates'] for r in fits)))
 result=dict(task_id=TASK,status='complete',fits=48,training_updates=192000,trainable_per_member=7058,all_weights_fresh=True,ensemble_index=str(ROOT/'ENSEMBLES.json'),utc=utc(),results=fits)
 new_json(ROOT/'TRAINING_COMPLETE.json',result)
 new_json(ROOT/'outbox/training_complete.json',dict(event_id=TASK+'_training_complete',synthetic=False,kind='training_complete',result=str(ROOT/'TRAINING_COMPLETE.json'),utc=utc()))
 return result

def choose_development(rows,source_rows):
 expected={r['source_id']:r for r in source_rows};tasks=sorted({r['task'] for r in source_rows});scores=[];totals={}
 if len(expected)!=100 or len(tasks)!=5:raise ValueError('development identity')
 for loss in LOSSES:
  score=Fraction(0,1);successes=0
  for fit in [9101,9102,9103]:
   for method in ['Post','Velocity']:
    cell=f'DEV_{loss}_s{fit}_{method}_H10';chosen=[r for r in rows if r['cell_id']==cell and r['status']=='complete']
    if len(chosen)!=100 or {r['source_id'] for r in chosen}!=set(expected):raise ValueError('incomplete development cell '+cell)
    for row in chosen:
     if type(row['success']) is not bool:raise ValueError('nonboolean outcome')
     for k in ['task','env_seed','policy_seed']:
      if row[k]!=expected[row['source_id']][k]:raise ValueError('dev source mismatch')
    for task in tasks:
     rs=[r for r in chosen if r['task']==task]
     if len(rs)!=20:raise ValueError('dev task denominator')
     ns=sum(r['success'] for r in rs);score+=Fraction(ns,20*30);successes+=ns
     scores.append(dict(loss=loss,fit_seed=fit,method=method,task=task,successes=ns,valid=20,success_rate=ns/20))
  totals[loss]=dict(successes=successes,valid=600,equal_weight_score=float(score),score_numerator=score.numerator,score_denominator=score.denominator)
 best=min(LOSSES,key=lambda loss:(-Fraction(totals[loss]['score_numerator'],totals[loss]['score_denominator']),AUX[loss],LOSSES.index(loss)))
 return dict(chosen_loss=best,fixed_fit_seed=9101,scores=scores,loss_scores=totals,selection_rule='equal five tasks x three fits x Post/Velocity; exact fraction, fewer auxiliary terms then L00,L10,L01,L11',development_valid=2400,development_technical_missing=0,test_used=False)

def make_selection():
 if (ROOT/'SELECTION.json').exists():return locked_selection()
 from publication_data import load_evidence
 _,_,_,rows=load_evidence()
 # No test scores participate: admission of all later stages requires this lock.
 chosen=choose_development([r for r in rows if r['stage']=='DEV'],read(ROOT/'SOURCE_INDEX.json')['source_sets']['DEV'])
 e=read(ROOT/'ENSEMBLES.json')['ensembles'][f"{chosen['chosen_loss']}_s9101"]
 chosen.update(task_id=TASK,status='selected_locked',utc=utc(),ensemble=e,weights=e['members'],preprocessing='frozen train-only fields retained per member; see preprocessing_evidence',source_table=str(ROOT/'SOURCE_INDEX.json'),training_complete=ref(ROOT/'TRAINING_COMPLETE.json'),no_test_based_change=True)
 new_json(ROOT/'SELECTION.json',chosen)
 new_json(ROOT/'SELECTION_LOCK.json',dict(selection=ref(ROOT/'SELECTION.json'),utc=utc(),immutable=True))
 new_json(ROOT/'outbox/selection_locked.json',dict(event_id=TASK+'_selection_locked',synthetic=False,kind='selection_locked',result=str(ROOT/'SELECTION.json'),utc=utc()))
 return chosen

def locked_selection():
 if not (ROOT/'SELECTION.json').is_file() or not (ROOT/'SELECTION_LOCK.json').is_file():raise FileNotFoundError('complete immutable dev selection is not published')
 lock=read(ROOT/'SELECTION_LOCK.json');row=read(ROOT/'SELECTION.json')
 if sha(ROOT/'SELECTION.json')!=lock['selection']['sha256'] or row['status']!='selected_locked' or row['test_used'] or row['fixed_fit_seed']!=9101:raise ValueError('selection lock changed')
 return row

def engine_config(job):
 cfg=copy.deepcopy(read(ROOT/'config/CONFIG.json'));key=job['ensemble_key']
 if key=='SELECTED':key=locked_selection()['ensemble']['key']
 e=read(ROOT/'ENSEMBLES.json')['ensembles'][key]
 cfg.update(critic_assets=e['assets'],selected_model=dict(member_hashes=e['member_hashes'],ensemble=e),loss=e['loss'],fit_seed=e['fit_seed'])
 return cfg
