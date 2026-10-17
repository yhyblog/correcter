"""Publish actual outcomes; Post is primary, Velocity remains separately exported."""
import csv,json
from pathlib import Path
import paths
from paths import ROOT,CONFIG,CAMPAIGN
from qio import read,atomic_json,utc,ref
def csv_write(path,rows):
 fields=sorted({k for r in rows for k in r})
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def publish():
 jobs=[read(x['path']) for x in read(ROOT/'JOB_INDEX.json')['jobs']];expected={j['cell_id']+'__'+s['source_id']:(j,s) for j in jobs for s in j['sources']}
 claims={p.stem:read(p) for p in (ROOT/'unit_claims').glob('*.json')};rows={};raw=[]
 for p in (ROOT/'runs').glob('*/episodes/*/RESULT.json'):
  r=read(p);uid=r['unit_id'];assert uid in expected and uid not in rows
  j,s=expected[uid];assert all(r[k]==s[k] for k in ['source_id','task','env_seed','policy_seed'])
  if r['status']=='complete':assert type(r['success']) is bool
  else:assert r['success'] is None
  row={k:v for k,v in r.items() if k not in ['plans','events']};row.update(result_path=str(p),current_paper=r['method']=='Post',selected_loss=CONFIG['selected_loss'])
  rows[uid]=row;raw.append(dict(unit_id=uid,result=ref(p),status=r['status']))
 for uid,(j,s) in expected.items():
  if uid not in rows:rows[uid]=dict(unit_id=uid,source_id=s['source_id'],method=j['method'],H=j['H'],task=s['task'],status='execution_unknown' if uid in claims else 'unstarted',success=None,current_paper=j['method']=='Post')
 cells=[]
 for method in ['Post','Velocity']:
  rs=[r for r in rows.values() if r['method']==method];valid=[r for r in rs if r['status']=='complete'];success=sum(r['success'] is True for r in valid)
  cells.append(dict(method=method,H=CONFIG['H'],planned=len(rs),valid=len(valid),successes=success,success_rate=success/len(valid) if valid else None,missing=len(rs)-len(valid),current_paper=method=='Post'))
 summary=dict(status='complete' if all(c['missing']==0 for c in cells) else 'partial',at_utc=utc(),task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],cells=cells,
  attempts=len(claims),current_run_attempts=len(claims),cumulative_B_attempts=CONFIG['planned_prior_attempts']+len(claims),
  selected_loss=CONFIG['selected_loss'],fit_seed=9101,selection=CONFIG['selection_sha256'],new_training_updates=0,new_collection=0,missing_not_failure=True)
 atomic_json(ROOT/'FINAL_SUMMARY.json',summary);atomic_json(ROOT/'RESULT_INDEX.json',dict(rows=raw));csv_write(ROOT/'FINAL_CELLS.csv',cells);csv_write(ROOT/'FINAL_EPISODES.csv',list(rows.values()))
 csv_write(ROOT/'POST_PAPER_EPISODES.csv',[r for r in rows.values() if r['method']=='Post']);csv_write(ROOT/'VELOCITY_OTHER_WORK.csv',[r for r in rows.values() if r['method']=='Velocity'])
 atomic_json(ROOT/'RESOURCE_SUMMARY.json',dict(occupancy_cost_excluded=True,worker_exits=[read(p) for p in (ROOT/'chain/workers').glob('*/WORKER_EXIT.json')],actual_loads=[read(p) for p in (ROOT/'chain/workers').glob('*/MODEL_READY.json')]))
 (ROOT/'MASTER_UPDATE.md').write_text('\n'.join([f"pi05 H{CONFIG['H']} chosen {CONFIG['selected_loss']} fit9101; Post primary; Velocity separate."]+[f"{c['method']}: {c['successes']}/{c['valid']} valid; {c['missing']} missing." for c in cells])+'\n')
 atomic_json(CAMPAIGN/CONFIG['result_receipt'],dict(summary,result_root=str(ROOT)))
 print(json.dumps(summary))
if __name__=='__main__':publish()
