"""CPU tables; immutable raw scientific terminals commit before optional export."""
import argparse,sys,traceback
import paths
from paths import ROOT,ORIGINAL,CAMPAIGN,TASK,POST_OVERRIDE_SHA
from qio import read,atomic_json,utc,ref
from publication_data import load_evidence,finite_values,EvidenceConflict
from analysis_tools import write_csv,pair,compact,costs

def publish_report(cell=None,terminal=False):
 cfg=read(ROOT/'config/CONFIG.json');jobs,attempts,claims,selected=load_evidence(only=cell)
 target=ROOT if terminal else ROOT/'cells'/cell;target.mkdir(parents=True,exist_ok=True)
 rows=[compact(r) for r in selected];cells=[];resources={};groups={}
 selection=read(ROOT/'SELECTION.json') if (ROOT/'SELECTION.json').exists() else None
 for c in cfg['cells']:
  if cell and c['cell_id']!=cell:continue
  key=c['cell_id'];data=[r for r in rows if r['cell_id']==key];good=[r for r in data if r['status']=='complete'];n=len(good);groups[key]=good;ints=[r['interventions'] for r in good]
  cells.append(dict(c,resolved_loss=selection['chosen_loss'] if c['loss']=='SELECTED' and selection else c['loss'],valid=n,successes=sum(r['success'] for r in good),success_rate=sum(r['success'] for r in good)/n if n else None,complete=n==c['planned_episodes'],interventions_mean=sum(ints)/n if n else None,interventions_max=max(ints) if ints else None,multiple_proportion=sum(i>=2 for i in ints)/n if n else None,technical_failures=sum(r['status']=='technical_failure' for r in data),user_cancelled=sum(r['status']=='user_cancelled' for r in data),unstarted=c['planned_episodes']-sum(x['cell_id']==key for x in claims)))
  resources[key]=costs(data)
 other=target/'other_work';other.mkdir(exist_ok=True)
 write_csv(target/'TECHNICAL_EPISODES_ALL_METHODS.csv',rows);write_csv(target/'TECHNICAL_CELLS_ALL_METHODS.csv',cells)
 write_csv(target/'FINAL_EPISODES.csv',[r for r in rows if r['method']=='Post']);write_csv(target/'FINAL_CELLS.csv',[r for r in cells if r['method']=='Post'])
 write_csv(other/'VELOCITY_EPISODES.csv',[r for r in rows if r['method']=='Velocity']);write_csv(other/'VELOCITY_CELLS.csv',[r for r in cells if r['method']=='Velocity'])
 atomic_json(target/'PAPER_SCOPE.json',dict(Post_only=True,Velocity_current_paper_final_tables_figures=False,Velocity_other_work=str(other),selection_override_sha256=POST_OVERRIDE_SHA,technical_summary_includes_all_authorized_experiments=True))
 train=read(ROOT/'TRAINING_COMPLETE.json') if (ROOT/'TRAINING_COMPLETE.json').exists() else None
 if terminal:
  for stage in ['DEV','ABLATION','MAIN','ONCE']:write_csv(ROOT/(stage+'_CELLS.csv'),[r for r in cells if r['stage']==stage and r['method']=='Post'])
  train_rows=[]
  for p in (ORIGINAL/'training').glob('s*_m*/L*/RESULT.json'):train_rows.append(read(p))
  write_csv(ROOT/'TRAIN_FITS.csv',train_rows)
  if selection:write_csv(ROOT/'DEVELOPMENT_SELECTION.csv',selection['scores'])
  pairs=[]
  for seed in [9101,9102,9103]:
   for method in ['Post']:
    baseline=f'ABLATION_L11_s{seed}_{method}_H10'
    for loss in ['L00','L10','L01']:
     key=f'ABLATION_{loss}_s{seed}_{method}_H10'
     if len(groups.get(key,[]))==len(groups.get(baseline,[]))==50:pairs.append(pair(groups[baseline],groups[key],name=baseline+' minus '+key))
  for method in ['Post']:
   m=f'MAIN_SELECTED_{method}_H10';o=f'ONCE_SELECTED_{method}_H10'
   if len(groups.get(m,[]))==len(groups.get(o,[]))==500:pairs.append(pair(groups[m],groups[o],name=method+' selected Q multi minus once H10'))
  write_csv(ROOT/'PAIRED.csv',pairs)
  external_paths={'VLA-Corrector':CAMPAIGN/'results/A/A_D24_E3_UNSTARTED_CONTINUATION_V1/COMBINED_EPISODES.json','GAF-v1 adapted':CAMPAIGN/'results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/EPISODES.json'}
  e3=[];comparisons=[]
  for name,p in external_paths.items():
   data=read(p);data=data['rows'] if isinstance(data,dict) else data
   e3.append(dict(method=name,H=10,valid=len(data),successes=sum(r['success'] for r in data),scope='unchanged external result'))
   for method in ['Post']:
    ours=groups.get(f'MAIN_SELECTED_{method}_H10',[])
    if len(ours)==500:comparisons.append(pair(ours,data,name=method+' selected-Q G0-multi minus '+name))
  for method in ['Post']:
   ours=groups.get(f'MAIN_SELECTED_{method}_H10',[])
   if ours:e3.append(dict(method=method,H=10,loss=selection['chosen_loss'] if selection else None,valid=len(ours),successes=sum(r['success'] for r in ours),scope='new selected-Q result'))
  write_csv(ROOT/'E3_COMPARISON.csv',e3);write_csv(ROOT/'E3_PAIRED.csv',comparisons)
  costrows=[]
  for c in cells:
   if c['stage'] not in ['MAIN','ONCE']:continue
   for metric,value in resources[c['cell_id']]['costs'].items():costrows.append(dict(cell_id=c['cell_id'],method=c['method'],H=c['H'],mode=c['mode'],metric=metric,**value))
  write_csv(ROOT/'E5_COSTS.csv',[r for r in costrows if r['method']=='Post']);write_csv(ROOT/'other_work/VELOCITY_E5_COSTS.csv',[r for r in costrows if r['method']=='Velocity'])
  atomic_json(ROOT/'E5_PARAMETERS.json',dict(Q_per_member=7058,Q_deployment_four_members=28232,train_fits=48,optimizer_updates=0,original_optimizer_updates=train['training_updates'] if train else None,architecture_unchanged=True,training_and_inference_cost_separate=True,source_parameter_reference=str(CAMPAIGN/'results/A/A_D24_OURS_E5_REPORT_V1/PARAMETER_COUNTS.json')))
  # Tables always exist even if a missing cell prevents a complete curve.
  import matplotlib;matplotlib.use('Agg')
  import matplotlib.pyplot as plt
  for method,directory in [('Post',ROOT),('Velocity',ROOT/'other_work')]:
   fig,ax=plt.subplots(figsize=(5,3.5),layout='constrained')
   rs=sorted([c for c in cells if c['stage']=='MAIN' and c['method']==method and c['complete']],key=lambda r:r['H'])
   ax.plot([c['H'] for c in rs],[100*c['success_rate'] for c in rs],'o-');ax.set(title=method+' / Post-selected Q / G0-multi',xlabel='Native horizon H',ylabel='Success (%)',xticks=[10,20,30,40,50],ylim=(0,100));ax.grid(alpha=.2)
   for ext in ['png','pdf']:fig.savefig(directory/('SELECTED_Q_H_CURVES.'+ext),dpi=180)
   plt.close(fig)
  (ROOT/'MASTER_UPDATE.md').write_text('# Complete Q loss selection\n\nFresh full7058 Q; fixed train600 and preprocessing. Four losses share per-fit/member initialization and batch indices. Selection uses Post-only complete repeated development across five tasks and three fits, final fit9101; Velocity has zero selection weight. Velocity inherits Post configuration and is stored only under other_work for a different paper. Current-paper FINAL tables and figures contain Post only. All-method technical summaries preserve the full authorized experiment record. Test50 is a previously exposed supplementary ablation; three fits are not 150 independent initial states. Selected-Q main and once share the same chosen Q. Old results, failures and cancelled opportunities remain separate.\n\nNo N/R/E6/external replay. Full LIBERO gap remains unchanged. E3 preserves 8 VLA log-derived outcomes with missing historical costs. E5 episode seconds are sums, not wave duration; loading/cleanup and failed attempts are separate. Null is not zero.\n')
 summary=dict(task_id=TASK,utc=utc(),valid=sum(c['valid'] for c in cells),actual_attempts=len(claims),technical_failures=sum(r['status']=='technical_failure' for r in attempts),stage_planned=5600,cells=cells,compute_complete=terminal and all(c['complete'] for c in cells),training_updates=0,original_training_updates=train['training_updates'] if train else None,new_collection=0,current_paper_methods=['Post'],Velocity_separate_other_work=True,selection_override_sha256=POST_OVERRIDE_SHA,chosen_loss=selection['chosen_loss'] if selection else None)
 atomic_json(target/'RESOURCE_SUMMARY.json',dict(utc=utc(),cells=resources,actual_attempts=len(claims),prior_A_attempts=14896,A_cumulative_attempts=14896+len(claims),failed_attempts=[compact(r) for r in attempts if r['status']!='complete'],loading_and_lifecycle_separate=str(ROOT/'chain'),training_separate=str(ORIGINAL/'training'),unknown_inflight_cost_not_zero=True))
 atomic_json(target/'FINAL_SUMMARY.json',finite_values(summary));atomic_json(target/'PUBLICATION.json',dict(status='published',utc=utc(),cell=cell,terminal=terminal,scientific_compute=0,valid=summary['valid'],artifacts=[ref(target/n) for n in ['FINAL_EPISODES.csv','FINAL_CELLS.csv','RESOURCE_SUMMARY.json','FINAL_SUMMARY.json']]))
 return summary

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--cell');p.add_argument('--terminal',action='store_true');p.add_argument('--error-json',required=True);a=p.parse_args()
 try:publish_report(a.cell,a.terminal)
 except BaseException as e:
  code=2 if isinstance(e,EvidenceConflict) else 3 if isinstance(e,OSError) else 1
  atomic_json(a.error_json,dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc(),publication_error=True,scientific_workers_must_continue=code==1));sys.exit(code)
