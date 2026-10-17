import csv,json,collections,pathlib
b=pathlib.Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
np=b/'work/B/B_D24_E8_POST_V1_r1/VALID_N_INDEX.json'
rp=b/'deadline_20260924/FINAL_DATA_CONSOLIDATION_20260923/SMOL_R_H10_CALLS.json'
pp=b/'deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_EPISODES.csv'
xp=b/'results/C/C_D24_CROSSBASE_H_SWEEP_V1/FINAL_EPISODES.csv'
n=json.load(open(np)); task_map={r['source_id']:r['task'] for r in n['xvla']}; assert len(task_map)==500
rows=[]
def add(model,method,src,success,calls,interventions,source_table,result_path='',task=None,elapsed=None):
 assert type(success)==bool
 assert task is None or task==task_map[src]
 rows.append(dict(model=model,H=10,method=method,mode='native' if method=='N' else 'G0-multi',loss='L11' if method=='Post' else '',fit_seed=9101 if method=='Post' else '',source_id=src,task=task_map[src],success=success,sampling_calls=float(calls),interventions='' if interventions is None else float(interventions),elapsed_seconds='' if elapsed is None else float(elapsed),valid=True,source_table=str(source_table),result_path=result_path))
for nk,model in [('smolvla','SmolVLA'),('xvla','X-VLA')]:
 for r in n[nk]:
  assert r['K']==10 and r['H']==(50 if nk=='smolvla' else 30)
  add(model,'N',r['source_id'],r['success'],r['queries'],0,np,r['origin_rows'],r['task'],r['elapsed_seconds'])
smol_r=json.load(open(rp))
assert len(smol_r['result_files'])==500
for p in smol_r['result_files']:
 r=json.load(open(p));assert r['method']=='R' and r['trigger_mode']=='G0-multi' and r['status']=='complete' and r.get('Q_assets') is None
 add('SmolVLA','R',r['source_id'],r['success'],r['counters']['policy_queries'],r['interventions'],rp,p,r['task'],r['elapsed_seconds'])
for r in csv.DictReader(open(xp)):
 if r['model']=='X-VLA' and r['H']=='10' and r['method']=='R':
  assert r['status']=='complete' and r['success'] in ['True','False']
  add('X-VLA','R',r['source_id'],r['success']=='True',r['sampling_calls'],r['interventions'],xp,r['result_path'],r['task'] or None,r['elapsed_seconds'])
for r in csv.DictReader(open(pp)):
 if r['model'] in ['SmolVLA','X-VLA'] and r['method']=='Post' and r['H']=='10' and r['mode']=='G0-multi':
  assert r['loss']=='L11' and r['fit_seed']=='9101' and r['success'] in ['True','False']
  add(r['model'],'Post',r['source_id'],r['success']=='True',r['sampling_calls'],r['interventions'],pp,r['result_path'],None,r['elapsed_seconds'])
assert len(rows)==2996
assert len({(r['model'],r['method'],r['source_id']) for r in rows})==2996
rows.sort(key=lambda r:(r['model'],['N','R','Post'].index(r['method']),r['source_id']))
expected={('SmolVLA','N'):(496,234,9688),('SmolVLA','R'):(500,245,10275),('SmolVLA','Post'):(500,250,10191),('X-VLA','N'):(500,403,6132),('X-VLA','R'):(500,412,6701),('X-VLA','Post'):(500,411,6706)}
summary=[]
for (model,method),vals in expected.items():
 rr=[r for r in rows if r['model']==model and r['method']==method]
 act=(len(rr),sum(r['success'] for r in rr),sum(r['sampling_calls'] for r in rr));assert act==vals,(model,method,act,vals)
 summary.append(dict(model=model,H=10,method=method,valid=act[0],successes=act[1],success_rate=act[1]/act[0],sampling_calls_total=act[2],sampling_calls_mean=act[2]/act[0]))
task_summary=[]
for model,method in expected:
 for task in sorted(set(task_map.values())):
  rr=[r for r in rows if r['model']==model and r['method']==method and r['task']==task]
  task_summary.append(dict(model=model,H=10,method=method,task=task,valid=len(rr),successes=sum(r['success'] for r in rr),sampling_calls_total=sum(r['sampling_calls'] for r in rr),sampling_calls_mean=sum(r['sampling_calls'] for r in rr)/len(rr)))
missing=sorted(set(task_map)-{r['source_id'] for r in rows if r['model']=='SmolVLA' and r['method']=='N'})
def writecsv(p,rs):
 with open(p,'w') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
writecsv('/tmp/POST_H10_CROSSBASE_EPISODES.csv',rows)
writecsv('/tmp/POST_H10_CROSSBASE_TASKS.csv',task_summary)
audit=dict(scope='Existing final H10 N/R/Post-multi, no simulation/model evaluation performed; Post L11 fit9101.',rows=len(rows),sources=[str(x) for x in (np,rp,pp,xp)],task_mapping_source=str(np),task_mapping='Exact source_id-to-task from 500 X-VLA N valid records, cross-checked where other input rows have task names.',H_normalization='VALID_N_INDEX.H is raw predicted chunk (Smol50/X30), K is execution horizon10; output H is execution horizon.',Q_free_R='Smol R historical container has Q_loss=L01 but Q_assets=null, method R, no Q; reused Q-independent baseline.',missing_smol_N=[dict(source_id=s,task=task_map[s],success=None,reason='Absent from accepted VALID_N_INDEX; unknown outcome, excluded from valid denominator.') for s in missing],summary=summary,task_summary_csv='/tmp/POST_H10_CROSSBASE_TASKS.csv',extraction_script='/tmp/extract_post_h10_crossbase.py')
json.dump(audit,open('/tmp/POST_H10_CROSSBASE_SOURCES.json','w'),ensure_ascii=False,indent=2)
print(json.dumps(dict(rows=len(rows),summary=summary,missing=audit['missing_smol_N']),indent=2))
