"""Finite observer's CPU-only, optional derived-table merge; never admits science."""
import csv,fcntl,io,math,traceback
from pathlib import Path
from paths import ROOT,CAMPAIGN,ORIGINAL
from qio import read,atomic_json,utc,ref

REMOTE={
 'B':CAMPAIGN/'results/B/B_D24_PI05_SELECTED_H20_H30_V1',
 'C':CAMPAIGN/'results/C/C_D24_PI05_SELECTED_H40_H50_V1'}

def write_csv(path,rows):
 keys=list(dict.fromkeys(k for row in rows for k in row));out=io.StringIO()
 w=csv.DictWriter(out,fieldnames=keys);w.writeheader();w.writerows(rows)
 temp=path.with_suffix('.csv.tmp');temp.write_text(out.getvalue());temp.replace(path)

def normalize_row(row,node,selection,path):
 """Map published aliases, retaining identity checks and raw source columns."""
 method=row.get('method');h=int(row.get('H',0))
 if method not in ['Post','Velocity'] or h not in dict(A=[10],B=[20,30],C=[40,50])[node]:raise ValueError('export node/H/method identity')
 losses={row[k] for k in ['resolved_loss','selected_loss','loss'] if row.get(k) not in [None,'','SELECTED']}
 if not selection or losses!={selection['chosen_loss']} or int(row.get('fit_seed',0))!=9101:raise ValueError('export selection identity not established')
 planned=int(row['planned_episodes']);valid=int(row['valid']);successes=int(row['successes'])
 if planned!=500 or not 0<=successes<=valid<=planned:raise ValueError('export counts')
 rate=float(row['success_rate']) if row.get('success_rate') else None
 if valid and (rate is None or not math.isfinite(rate) or not math.isclose(rate,successes/valid,abs_tol=1e-12,rel_tol=0)):raise ValueError('export success rate/count conflict')
 flags=[str(row[k]).lower() for k in ['complete','full_cell_complete'] if row.get(k) not in [None,'']]
 if any(v not in ['true','false'] for v in flags) or len(set(flags))>1:raise ValueError('export complete flags conflict')
 complete=bool(flags and flags[0]=='true')
 if complete and (valid!=planned or any(int(row.get(k) or 0)!=0 for k in ['technical_failures','unknown_entered','user_cancelled','unstarted','not_started'])):raise ValueError('export complete/count conflict')
 result=dict(row,owner=node,derived_source=str(path),resolved_loss=selection['chosen_loss'],complete=str(complete))
 if 'complete' not in row:result['complete_field_source']='full_cell_complete' if flags else 'unknown'
 if 'resolved_loss' not in row:result['resolved_loss_field_source']='selected_loss' if row.get('selected_loss') else 'loss'
 return result

def merge():
 # Independent CPU observers may notice the same remote publication. This
 # host-local export lock is unrelated to the scientific reservation.
 with Path('/tmp/corrector_A_fullq_post_led_merge.lock').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return dict(status='existing_CPU_merge_in_progress')
  return merge_unlocked()

def merge_unlocked():
 folder=ROOT/'aggregate';folder.mkdir(exist_ok=True)
 selection=read(ORIGINAL/'SELECTION.json') if (ORIGINAL/'SELECTION_LOCK.json').exists() else None
 rows=[];velocity=[];sources=[];missing=[];rejected=[]
 for node,directory in dict(A=ROOT,**REMOTE).items():
  p=directory/'MAIN_CELLS.csv'
  if not p.exists():p=directory/'FINAL_CELLS.csv'
  if not p.exists():missing.append(dict(node=node,path=str(p)));continue
  try:
   with p.open(newline='') as f:data=list(csv.DictReader(f))
   # A's primary export deliberately excludes Velocity. Retain its existing
   # separate publication only in the other-work output, never the paper plot.
   extra=directory/'other_work/VELOCITY_CELLS.csv'
   extra_used=node=='A' and extra.exists() and not any(r.get('stage')=='MAIN' and r.get('method')=='Velocity' for r in data)
   inputs=[(row,p) for row in data]
   if extra_used:
    with extra.open(newline='') as f:inputs.extend((row,extra) for row in csv.DictReader(f) if row.get('method')=='Velocity')
   accepted=[]
   for row,source in inputs:
    if row.get('stage')!='MAIN':continue
    accepted.append(normalize_row(row,node,selection,source))
   for row in accepted:(rows if row['method']=='Post' else velocity).append(row)
   sources.append(ref(p))
   if extra_used:sources.append(ref(extra))
  except Exception as error:rejected.append(dict(node=node,path=str(p),error=str(error)))
 seen=set()
 for row in rows+velocity:
  key=(row['method'],int(row['H']))
  if key in seen:raise ValueError('duplicate primary cell export')
  seen.add(key)
 write_csv(folder/'SELECTED_Q_MAIN_CELLS.csv',rows)
 other=folder/'other_work';other.mkdir(exist_ok=True);write_csv(other/'VELOCITY_MAIN_CELLS.csv',velocity)
 atomic_json(folder/'STATUS.json',dict(utc=utc(),scientific_compute=0,chosen_loss=selection['chosen_loss'] if selection else None,fit_seed=9101,known_cells=sum(r.get('complete','').lower()=='true' for r in rows),listed_cells=len(rows),known_cells_meaning='complete cells only for terminal observer gate',expected_cells=5,current_paper_methods=['Post'],Velocity_selection_weight=0,Velocity_current_paper_final_tables_figures=False,missing=missing,rejected=rejected,sources=sources,no_cross_node_runtime_barrier=True))
 # This is the same approved CPU paper-figure publication environment.
 if selection and rows:
  import matplotlib;matplotlib.use('Agg')
  import matplotlib.pyplot as plt
  fig,ax=plt.subplots(figsize=(6,3.8),layout='constrained')
  for method in ['Post']:
   valid=sorted([r for r in rows if r['method']==method and r.get('complete','').lower()=='true'],key=lambda r:int(r['H']))
   ax.plot([int(r['H']) for r in valid],[float(r['success_rate'])*100 for r in valid],marker='o',label=method)
  ax.set(xlabel='Native horizon H',ylabel='Success (%)',xticks=[10,20,30,40,50],ylim=(0,100),title='Selected '+selection['chosen_loss']+' / fit9101 / G0-multi')
  ax.legend();ax.grid(alpha=.2)
  for ext in ['png','pdf']:fig.savefig(folder/('SELECTED_Q_H_CURVES.'+ext),dpi=180)
  plt.close(fig)
 return dict(rows=len(rows),missing=len(missing),rejected=len(rejected))

if __name__=='__main__':
 try:print(merge())
 except Exception as e:
  atomic_json(ROOT/'aggregate_error.json',dict(utc=utc(),publication_error=True,scientific_workers_must_continue=True,error=str(e),traceback=traceback.format_exc()));raise
