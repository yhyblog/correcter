from pathlib import Path
import csv,json,datetime,hashlib,collections
P=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919');D=P/'deadline_20260924/L11_FINAL_ROLLUP_20260923';D.mkdir(exist_ok=True);now=datetime.datetime.now(datetime.timezone.utc).isoformat()
files=[('A_recovery',P/'results/A/A_D24_L11_RENDER_RECOVERY_V1/EPISODES.csv'),('B_original_valid',P/'results/B/B_D24_L11_RETEST_V1/recovery_queue/merged/EPISODES.csv'),('B_H30_recovery',P/'results/B/B_D24_L11_RENDER_RECOVERY_V1/FINAL_EPISODES.csv'),('C_audited_merged',P/'results/C/C_D24_L11_RENDER_RECOVERY_V1/EPISODES.csv')]
def js(s):return json.loads(s) if s and s not in ['null','None'] else {}
def number(s):
 if s is None or s in ['', 'null','None']:return None
 return float(s)
def boolean(s):
 if str(s).lower() in ['true','1']:return True
 if str(s).lower() in ['false','0']:return False
 raise ValueError(('unknown_success',s))
rows=[];sources=[]
for label,f in files:
 with f.open() as h: data=list(csv.DictReader(h))
 sources.append({'label':label,'path':str(f),'rows':len(data),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
 for x in data:
  counters=js(x.get('counters'));enc=js(x.get('encoder_counters'));uid=x['unit_id'];method=x['method'];model=x.get('model') or uid.split('|')[0];samples=number(x.get('sampling_calls'))
  if samples is None:samples=number(counters.get('policy_queries',counters.get('sampling')))
  flows=number(x.get('flow_calls'))
  if flows is None:flows=number(counters.get('policy_flow_calls',counters.get('flow')))
  grad=number(x.get('action_gradient_calls'))
  if grad is None:grad=number(enc.get('action_gradient_calls',counters.get('action_gradients')))
  row={'unit_id':uid,'model':model,'method':method,'mode':x['mode'],'H':int(x['H']),'loss':'L11','fit_seed':9101,'source_id':x['source_id'],'success':boolean(x['success']),'sampling_calls':samples,'flow_calls':flows,'interventions':number(x.get('interventions')),'action_gradients':grad,'elapsed_seconds':number(x.get('elapsed_seconds')),'reused_ablation50':boolean(x.get('reused') or 'false'),'preserved_prior_valid':boolean(x.get('preserved_prior_valid') or 'false'),'source_table':str(f),'result_path':x['result_path'],'input_group':label}
  rows.append(row)
ids=[x['unit_id'] for x in rows];assert len(ids)==len(set(ids))==8000
expected=[]
for name in ['NEW_UNITS.jsonl','REUSED_UNITS.jsonl']:
 for s in (P/f'deadline_20260924/L11_RETEST_V1/prepared_by_analysis/{name}').read_text().splitlines():expected.append(json.loads(s)['unit_id'])
assert set(ids)==set(expected),(len(set(expected)-set(ids)),len(set(ids)-set(expected)))
assert sum(x['reused_ablation50'] for x in rows)==100
cellgroups=collections.defaultdict(list)
for x in rows:cellgroups[(x['model'],x['method'],x['mode'],x['H'])].append(x)
cells=[]
for (model,method,mode,h),g in sorted(cellgroups.items()):
 assert len(g)==500
 c={'model':model,'method':method,'mode':mode,'H':h,'loss':'L11','fit_seed':9101,'valid':len(g),'successes':sum(x['success'] for x in g),'success_rate':sum(x['success'] for x in g)/len(g),'reused_ablation50':sum(x['reused_ablation50'] for x in g),'preserved_prior_valid':sum(x['preserved_prior_valid'] for x in g),'technical_missing':0}
 for key in ['sampling_calls','flow_calls','interventions','action_gradients','elapsed_seconds']:
  vals=[x[key] for x in g if x[key] is not None];c[key+'_known_count']=len(vals);c[key+'_observed_sum']=sum(vals);c[key+'_mean']=sum(vals)/len(g) if len(vals)==len(g) else None
 cells.append(c)
# Only paired current-result arithmetic; no new simulation or statistical-model selection.
h10pairs={}
for method in ['Post','Velocity']:
 bymode={mode:{x['source_id']:x for x in rows if x['model']=='pi05' and x['method']==method and x['H']==10 and x['mode']==mode} for mode in ['G0-multi','G0-once']}
 mu=bymode['G0-multi'];once=bymode['G0-once'];assert set(mu)==set(once) and len(mu)==500
 rescued=sum(mu[k]['success'] and not once[k]['success'] for k in mu);harmed=sum(once[k]['success'] and not mu[k]['success'] for k in mu)
 h10pairs[method]={'paired':500,'multi_successes':sum(x['success'] for x in mu.values()),'once_successes':sum(x['success'] for x in once.values()),'rescued_by_multi':rescued,'harmed_by_multi':harmed,'difference_pp':(rescued-harmed)/5}
for f,data in [(D/'FINAL_EPISODES.csv',rows),(D/'FINAL_CELLS.csv',cells)]:
 with f.open('w') as h:
  w=csv.DictWriter(h,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
rollup={'at_utc':now,'status':'all_planned_L11_scientific_units_complete','valid_unique':8000,'new_units_unique':7900,'ablation_exact_reuse':100,'cells':cells,'cell_count':len(cells),'missing':0,'duplicate_unit_keys':0,'expected_manifest_exact_coverage':True,'H10_multi_once_paired':h10pairs,'sources':sources,'raw_invalid_attempts_excluded_not_deleted':True,'scientific_calls_by_analysis':0,'current_paper':'Post_only','Velocity':'other_work','new_experiment_admissions_this_turn':0}
(D/'FINAL_ROLLUP.json').write_text(json.dumps(rollup,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'valid':8000,'cells':[{k:x[k] for k in ['model','method','mode','H','successes','valid','sampling_calls_mean','interventions_mean']} for x in cells],'H10_paired':h10pairs,'outputs':str(D)},ensure_ascii=False))
