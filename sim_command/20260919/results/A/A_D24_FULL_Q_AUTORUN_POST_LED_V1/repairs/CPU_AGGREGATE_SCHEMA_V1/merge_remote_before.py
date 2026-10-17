"""Finite observer's CPU-only, optional derived-table merge; never admits science."""
import csv,io,traceback
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

def merge():
 folder=ROOT/'aggregate';folder.mkdir(exist_ok=True)
 selection=read(ORIGINAL/'SELECTION.json') if (ORIGINAL/'SELECTION_LOCK.json').exists() else None
 rows=[];velocity=[];sources=[];missing=[];rejected=[]
 for node,directory in dict(A=ROOT,**REMOTE).items():
  p=directory/'MAIN_CELLS.csv'
  if not p.exists():p=directory/'FINAL_CELLS.csv'
  if not p.exists():missing.append(dict(node=node,path=str(p)));continue
  try:
   with p.open(newline='') as f:data=list(csv.DictReader(f))
   for row in data:
    if row.get('stage')!='MAIN':continue
    method=row.get('method');h=int(row.get('H',0))
    if method not in ['Post','Velocity'] or h not in dict(A=[10],B=[20,30],C=[40,50])[node]:raise ValueError('export node/H/method identity')
    loss=row.get('resolved_loss') or row.get('loss');fit=int(row.get('fit_seed',0))
    if not selection or loss!=selection['chosen_loss'] or fit!=9101:raise ValueError('export selection identity not established')
    (rows if method=='Post' else velocity).append(dict(row,owner=node,derived_source=str(p)))
   sources.append(ref(p))
  except Exception as error:rejected.append(dict(node=node,path=str(p),error=str(error)))
 seen=set()
 for row in rows:
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
