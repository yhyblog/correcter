import ast,csv,json
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
P=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
A0=P/'results/A/A_D24_CROSSBASE_H_SWEEP_V1'; A=P/'results/A/A_D24_CROSSBASE_H_SWEEP_V1_RECOVERY_r2'
B=P/'results/B/B_D24_CROSSBASE_H_SWEEP_V1/recovery/velocity_r3'; C=P/'results/C/C_D24_CROSSBASE_H_SWEEP_V1'
def rd(p): return list(csv.DictReader(p.open()))
def js(p): return json.loads(p.read_text())
def counters(r,k):
 s=r.get(k,'')
 if not s:return {}
 try:return json.loads(s)
 except json.JSONDecodeError:return ast.literal_eval(s)
# Use exact valid index; join only terminal export, never the attempted-cost summary.
aindex=rd(A/'COMBINED_VALID_EPISODES.csv'); amap={r['result_path']:r for path in [A0/'FINAL_EPISODES.csv',A/'FINAL_EPISODES.csv'] for r in rd(path) if r['status']=='complete' and r.get('valid')=='True'}
arows=[]
for r in aindex:
 q=amap[r['result_path']]
 assert all(r[k]==q[k] for k in r), (r['unit_id'],'A join mismatch')
 arows.append(q)
rows_by_node={'A':arows,'B':rd(B/'FINAL_EPISODES.csv'),'C':[r for r in rd(C/'FINAL_EPISODES.csv') if r['H'] in ('20','30')]}
expected={f'D24_MW_t{t:02d}_e{e:02d}' for t in range(50) for e in range(10)}
fields={'sampling_calls':('counters','policy_queries'),'flow_calls':('counters','policy_flow_calls'),'natural_sampling_calls':('counters','natural_queries'),'candidate_sampling_calls':('counters','candidate_queries'),'action_gradient_calls':('encoder_counters','action_gradient_calls'),'Q_ensemble_forward_calls':('encoder_counters','Q_ensemble_forward_calls'),'Q_member_forward_calls':('encoder_counters','Q_member_forward_calls'),'D_forward_calls':('encoder_counters','D_forward_calls'),'G0_forward_calls':('encoder_counters','G0_forward_calls')}
cmap={'sampling_calls':'sampling_calls','flow_calls':'flow_calls','action_gradient_calls':'action_gradient_calls','Q_ensemble_forward_calls':'Q_ensemble_forward','Q_member_forward_calls':'Q_member_forward','D_forward_calls':'D_forward','G0_forward_calls':'G0_forward'}
allcells=[]; node_status={}; records=[]
for node,rows in rows_by_node.items():
 root={'A':A,'B':B,'C':C}[node]; result=js(root/'RESULT.json');summary=js(root/'FINAL_SUMMARY.json')
 assert len(rows)==4000
 node_status[node]={'terminal_utc':result.get('utc',result.get('at_utc')),'terminal_status':result['status'],'all_owned_descendants_exited':result['all_owned_descendants_exited'],'valid':4000,'total_episode_attempts':{'A':4381,'B':4384,'C':4000}[node],'preserved_technical_failure_attempts':{'A':381,'B':384,'C':0}[node],'terminal_result':str(root/'RESULT.json'),'source_index':str(root/('COMBINED_VALID_EPISODES.csv' if node=='A' else 'FINAL_EPISODES.csv'))}
 groups=defaultdict(list)
 for r in rows:groups[(r['model'],r['method'],int(r['H']))].append(r)
 for (model,method,h),selected in sorted(groups.items()):
  assert len(selected)==500 and len({r['unit_id'] for r in selected})==500 and {r['source_id'] for r in selected}==expected
  assert all(r['status']=='complete' and r['success'] in ('True','False') for r in selected)
  if node=='A':assert all(r['valid']=='True' for r in selected)
  if node=='C':assert all(r['disposition']=='valid' for r in selected)
  assert len({r['task'] for r in selected})==50
  assert set(Counter(r['task'] for r in selected).values())=={10}
  for r in selected:
   taskno=int(r['source_id'].split('_t')[1].split('_')[0]); ep=int(r['source_id'].split('_e')[1]); assert int(r.get('reset_seed',r.get('env_seed')))==24100000+taskno*1000+ep; assert int(r['policy_seed'])==34100000+taskno*1000+ep
   assert r['mode']==('native' if method=='N' else 'G0-multi')
   if method in ('Post','Velocity'):
    assert r.get('Q_loss',r.get('loss'))=='L11' and r.get('Q_fit_seed',r.get('fit_seed'))=='9101'
   if method!='N':assert r['C']=='10'
   if node!='C': assert r['raw_plan_length']=='50'
  success=sum(r['success']=='True' for r in selected); interventions=sum(int(r['interventions']) for r in selected)
  sums=Counter(); explicit=Counter(); structural=Counter(); missing=Counter(); gradients_check=True
  for r in selected:
   nr=int(r['interventions']); dc={k:counters(r,k) for k in ('counters','encoder_counters')} if node!='C' else {}
   rowcost={}
   for name,(container,key) in fields.items():
    value=(float(r[cmap[name]]) if name in cmap and r.get(cmap[name],'')!='' else None) if node=='C' else dc[container].get(key)
    if value is not None: explicit[name]+=1
    elif name in ('action_gradient_calls','Q_ensemble_forward_calls','Q_member_forward_calls') and (method in ('N','R') or nr==0):value=0;structural[name]+=1
    elif name in ('D_forward_calls','G0_forward_calls') and method=='N':value=0;structural[name]+=1
    else:missing[name]+=1
    if value is not None:sums[name]+=value
    rowcost[name]=value
   assert rowcost['flow_calls']==10*rowcost['sampling_calls']
   records.append({'node':node,'model':model,'method':method,'H':h,'unit_id':r['unit_id'],'source_id':r['source_id'],'task':r['task'],'success':r['success']=='True','interventions':nr,'sampling_calls':rowcost['sampling_calls'],'flow_calls':rowcost['flow_calls'],'action_gradient_calls':rowcost['action_gradient_calls'],'result_path':r['result_path']})
  costs={n:{'known_total':sums[n],'explicit_rows':explicit[n],'structural_zero_rows':structural[n],'unknown_rows':missing[n],'mean_per_valid_episode':sums[n]/500 if not missing[n] else None} for n in fields}
  costs['interventions']={'known_total':interventions,'explicit_rows':500,'structural_zero_rows':0,'unknown_rows':0,'mean_per_valid_episode':interventions/500}
  row={'node':node,'model':model,'method':method,'H':h,'mode':'native' if method=='N' else 'G0-multi','Q_loss':'L11' if method in ('Post','Velocity') else None,'Q_fit_seed':9101 if method in ('Post','Velocity') else None,'Q_members':[1041,1042,1043,1044] if method in ('Post','Velocity') else [],'raw_plan_length':50 if model=='SmolVLA' else 30,'C':10 if method!='N' else None,'NFE':10,'planned':500,'valid':500,'unique_sources':500,'unique_units':500,'task_count':50,'per_task_count':10,'successes':success,'success_rate':success/500,'success_percent':success/5,'sampling_mean':costs['sampling_calls']['mean_per_valid_episode'],'flow_mean':costs['flow_calls']['mean_per_valid_episode'],'interventions_mean':interventions/500,'action_gradients_mean':costs['action_gradient_calls']['mean_per_valid_episode'],'all_sources_match':True,'identity_checks_pass':True,'flow_equals_10_sampling_every_episode':True,'costs':costs,'source_csv':node_status[node]['source_index'],'cost_export_sources':[str(A0/'FINAL_EPISODES.csv'),str(A/'FINAL_EPISODES.csv')] if node=='A' else [str(root/'FINAL_EPISODES.csv')],'terminal_result':str(root/'RESULT.json'),'terminal_utc':node_status[node]['terminal_utc']}
  allcells.append(row)
# preserve valid outcome matched identities, including failed scientific outcomes.
assert len(allcells)==24 and sum(c['valid'] for c in allcells)==12000
out={'checked_utc':datetime.now(timezone.utc).isoformat(),'status':'all_24_new_cells_complete','new_cells':24,'valid_episodes':12000,'expected_per_cell':500,'H10_reused_excluded':True,'fixed_loss':'L11 = BCE + gain + 0.5 pair','fit_seed':9101,'Q_members':[1041,1042,1043,1044],'nodes':node_status,'cells':allcells,'metric_definition':'Mean costs aggregate only the 500 unique valid terminal episodes in each cell, including successes and scientific failures. Technical-failure attempts are excluded from these means and retained separately. Sampling is returned policy_queries; flow=NFE10*sampling.','sparse_counter_policy':'Explicit_rows and structural_zero_rows are separate. A zero-intervention episode cannot execute a correction gradient; N/R cannot execute Q/action-gradient. Missing nonstructural values are left unknown, never filled as zero.','caveats':['No new blind test: fixed already revealed MT50 500-source set. No selection or calibration on these values.','Frozen per-model L11 fit9101 and native10 D/G0 heads; no per-H retraining/calibration.','SmolVLA raw50, X-VLA raw30; natural H independent of correction C10.','Velocity remains other-work data, excluded from Post paper.','A publication retried on CPU; publication attempts are not scientific episode attempts. B r2 startup failure consumed no episode and is preserved; r3 terminates complete.','No new compute, hardware query, large hashes, weights/images or whole-event logs read.'],'valid_episode_records_file':'/tmp/FINAL_CROSSBASE_H_SWEEP_VALID_EPISODES.csv','aggregation_script':'/tmp/aggregate_final_crossbase.py'}
Path('/tmp/FINAL_CROSSBASE_H_SWEEP_DATA.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
flatkeys=['node','model','method','H','Q_loss','Q_fit_seed','planned','valid','successes','success_percent','sampling_mean','flow_mean','interventions_mean','action_gradients_mean','source_csv','terminal_utc']
with open('/tmp/FINAL_CROSSBASE_H_SWEEP_DATA.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=flatkeys,extrasaction='ignore');w.writeheader();w.writerows(allcells)
with open('/tmp/FINAL_CROSSBASE_H_SWEEP_VALID_EPISODES.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
lines=['# Final cross-backbone H sweep','',f"All 24 new cells complete, 12000 unique valid terminal units. Checked {out['checked_utc']}.",'','| Model | Method | H | Successes / valid | SR (%) | Policy calls | Flow calls | Interventions | Action gradients |','|---|---|---:|---:|---:|---:|---:|---:|---:|']
for c in allcells:lines.append(f"| {c['model']} | {c['method']} | {c['H']} | {c['successes']} / 500 | {c['success_percent']:.1f} | {c['sampling_mean']:.3f} | {c['flow_mean']:.3f} | {c['interventions_mean']:.3f} | {c['action_gradients_mean']:.3f} |")
lines+=['',out['metric_definition'],'',out['sparse_counter_policy'],'','A: 4381 attempts, 4000 valid, 381 preserved technical failures. B: 4384 attempts, 4000 valid, 384 preserved technical failures; zero-episode r2 launch failure also preserved. C: 4000 attempts/valid, no technical failures.','']
for n,v in node_status.items():lines.append(f"- {n}: {v['terminal_utc']}, {v['terminal_status']}; {v['terminal_result']}")
lines+=['']+['- '+x for x in out['caveats']]
Path('/tmp/FINAL_CROSSBASE_H_SWEEP_DATA.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines[:30]))
