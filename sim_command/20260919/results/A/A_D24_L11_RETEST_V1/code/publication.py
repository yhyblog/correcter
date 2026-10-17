"""CPU export of lawful L11 terminal units. No selection or scientific launch."""
import csv,io,os,time,traceback
from pathlib import Path
from collections import defaultdict,Counter
from paths import ROOT,TASK
from qio import read,new_json,atomic_json,utc
from admission import frozen_units

_CACHE={}
def records():
 units=frozen_units();rows=[]
 for u in units.values():
  p=ROOT/'episodes'/u['uid_hash']/'RESULT.json'
  if p.exists():
   if str(p) not in _CACHE:_CACHE[str(p)]=read(p)
   row=_CACHE[str(p)]
   if row['unit_id']!=u['unit_id']:raise ValueError('scientific unit identity mismatch')
   rows.append(dict(row,result_path=str(p),reused=False))
 for u in read(ROOT/'REUSED_UNITS.json'):
  p=Path(u['original_source']['result_path'])
  if str(p) not in _CACHE:_CACHE[str(p)]=read(p)
  raw=_CACHE[str(p)]
  if raw['status']!='complete' or raw['success']!=u['success'] or raw['loss']!='L11' or raw['fit_seed']!=9101:raise ValueError('reused exact terminal identity')
  rows.append(dict(raw,unit_id=u['unit_id'],cell_id=f"L11_{u['method']}_{u['mode']}_H{u['H']}",result_path=str(p),reused=True))
 if len({r['unit_id'] for r in rows})!=len(rows):raise ValueError('duplicate published unit')
 return rows

def write_csv(path,rows):
 keys=list(dict.fromkeys(k for row in rows for k in row));buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=keys);w.writeheader();w.writerows(rows)
 temp=path.with_name(path.name+'.update.'+str(os.getpid()));temp.write_text(buf.getvalue());temp.replace(path)

def export():
 rows=records();groups=defaultdict(list)
 entered=Counter(u['cell_id'] for u in frozen_units().values() if (ROOT/'unit_claims'/(u['uid_hash']+'.json')).exists())
 for r in rows:groups[r['cell_id']].append(r)
 cells=[]
 for method in ['Post','Velocity']:
  for mode,h in [('G0-multi',10),('G0-multi',30),('G0-once',10)]:
   cid=f'L11_{method}_{mode}_H{h}';rs=groups[cid];valid=[r for r in rs if r['status']=='complete'];reused=sum(r['reused'] for r in valid);new=[r for r in rs if not r['reused']]
   cells.append(dict(cell_id=cid,method=method,mode=mode,H=h,loss='L11',fit_seed=9101,planned=500,valid=len(valid),new_valid=len(valid)-reused,reused_valid=reused,successes=sum(r['success'] is True for r in valid),success_rate=sum(r['success'] is True for r in valid)/len(valid) if valid else None,technical_failures=sum(r['status']!='complete' for r in new),attempts=entered[cid],inflight=entered[cid]-len(new),unentered=(450 if h==10 and mode=='G0-multi' else 500)-entered[cid],sampling_calls=sum(r.get('sampling_calls',0) for r in valid),flow_calls=sum(r.get('flow_calls',0) for r in valid),action_gradients=sum(r.get('counters',{}).get('action_gradients',0) for r in valid),interventions=sum(r.get('interventions',0) for r in valid),elapsed_seconds_sum=sum(r.get('elapsed_seconds',0) for r in valid),sum_episode_time_is_not_wave_wall=True,complete=len(valid)==500,reused_overlap_selection=True if reused else False,current_paper=method=='Post'))
 counter=read(ROOT/'ATTEMPT_COUNTER.json') if (ROOT/'ATTEMPT_COUNTER.json').exists() else {'count':0}
 validnew=[r for r in rows if r['status']=='complete' and not r['reused']]
 summary=dict(utc=utc(),task_id=TASK,cells={c['cell_id']:c for c in cells},actual_attempts=counter['count'],local_new_attempts=counter['count'],valid_new=len(validnew),valid_total=sum(r['status']=='complete' for r in rows),technical_missing=sum(r['status']!='complete' and not r['reused'] for r in rows),unentered=2900-counter['count'],compute_complete=len(validnew)==2900,prior_A_attempts=20496,A_cumulative_attempts=20496+counter['count'],new_training_updates=0,reused_valid=100,selection_fixed='explicit user L11/fit9101',Velocity_current_paper=False)
 write_csv(ROOT/'ALL_CELLS.csv',cells);write_csv(ROOT/'POST_PAPER_CELLS.csv',[c for c in cells if c['method']=='Post']);write_csv(ROOT/'VELOCITY_OTHER_WORK_CELLS.csv',[c for c in cells if c['method']=='Velocity'])
 fields=['unit_id','source_id','task','env_seed','policy_seed','method','mode','H','loss','fit_seed','status','success','steps','interventions','sampling_calls','flow_calls','elapsed_seconds','reused','result_path']
 write_csv(ROOT/'EPISODES.csv',[{k:r.get(k) for k in fields} for r in rows])
 atomic_json(ROOT/'SUMMARY.json',summary);atomic_json(ROOT/'FINAL_SUMMARY.json',summary)
 atomic_json(ROOT/'PUBLICATION.json',dict(utc=utc(),scientific_compute=0,status='published',results=str(ROOT/'EPISODES.csv'),Post=str(ROOT/'POST_PAPER_CELLS.csv'),Velocity_other_work=str(ROOT/'VELOCITY_OTHER_WORK_CELLS.csv'),cost_scope='new L11 actual results plus explicitly tagged exact L11 reuse; no L01 cost substitution'))
 for cell in cells:
  ep=ROOT/'outbox'/(cell['cell_id']+'.json')
  if cell['complete'] and not ep.exists():new_json(ep,dict(event_id=TASK+'_'+cell['cell_id'],kind='cell_terminal',synthetic=False,utc=utc(),summary=cell,result=str(ROOT/'PUBLICATION.json')))
 return summary

def publish(*_,terminal=False,force=False,**kw):
 try:
  s=export();row=dict(status='published',attempts=1,utc=utc(),publication=str(ROOT/'PUBLICATION.json'),valid_new=s['valid_new'])
 except BaseException as e:
  row=dict(status='publication_error',attempts=1,utc=utc(),type=type(e).__name__,message=str(e),traceback=traceback.format_exc(),scientific_workers_must_continue=True)
 atomic_json(ROOT/'PUBLICATION_STATE.json',row)
 return row
