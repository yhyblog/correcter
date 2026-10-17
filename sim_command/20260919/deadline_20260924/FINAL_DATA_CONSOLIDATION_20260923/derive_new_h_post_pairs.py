exec(open('/tmp/derive_l11_post_pairs_paper.py').read())
newrows=load('/tmp/FINAL_CROSSBASE_H_SWEEP_VALID_EPISODES.csv')
newgroups=defaultdict(dict)
for row in newrows:
 if row['method'] in ['N','R','Post']:
  x=norm(row);newgroups[(x['model'],x['H'],x['method'])][x['source_id']]=x
newans=[]
for model,h in sorted(set((k[0],k[1]) for k in newgroups)):
 for method in ['N','R']:
  a=newgroups[(model,h,'Post')];b=newgroups[(model,h,method)];assert len(a)==len(b)==500
  newans.append(compare(a,b,f'{model} H{h} Post–{method}'))
json.dump({'scope':'new L11 Post H scans only; fixed existing 500 sources per model', 'interval_method':'Pointwise95 normal approximation using paired difference with fixed-task-stratified sample variance; exact two-sided McNemar exploratory, unadjusted. No bootstrap or new evaluation.', 'comparisons':newans,'sources':[{'canonical_valid_episode_csv':'/tmp/FINAL_CROSSBASE_H_SWEEP_VALID_EPISODES.csv','canonical_cell_checks':'/tmp/FINAL_CROSSBASE_H_SWEEP_DATA.json'}]},open('/tmp/FINAL_CROSSBASE_POST_PAIRED_STATS.json','w'),ensure_ascii=False,indent=2)
for x in newans: print(x)
