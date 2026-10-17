import json,csv,math,hashlib
from pathlib import Path
from collections import defaultdict
R=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
sources=[]
def load(p):
 p=Path(p);sources.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 return list(csv.DictReader(p.open())) if p.suffix=='.csv' else json.loads(p.read_text())
def norm(row,model=None):
 x=dict(row);x['model']=x.get('model') or model or 'pi05';x['success']=str(x['success']).lower()=='true';x['H']=int(x['H']);return x
roll=load(R/'deadline_20260924/L11_FINAL_ROLLUP_20260923/FINAL_ROLLUP.json')
post=defaultdict(dict)
for s in roll['sources']:
 for row in load(s['path']):
  if row.get('method')!='Post':continue
  x=norm(row); key=(x['model'],x['H'],x['mode']);sid=x['source_id']
  assert sid not in post[key],(key,sid)
  post[key][sid]=x
print('post',[(k,len(v),sum(x['success'] for x in v.values())) for k,v in post.items()])
N=defaultdict(dict)
for p in sorted((R/'deadline_20260924/A/runs').glob('N_H*/RESULT.json')):
 for row in load(p)['episodes']:
  x=norm(row);assert not x.get('technical_failure');N[x['H']][x['source_id']]=x
Rs=defaultdict(dict)
for row in load(R/'results/C/C_D24_R_TRIGGER_MODES_V1/FINAL_EPISODES.csv'):
 if row.get('method')=='R' and row.get('mode')=='G0-multi':
  x=norm(row);Rs[x['H']][x['source_id']]=x
G={x['source_id']:norm(x) for x in load(R/'results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/EPISODES.json')}
V={x['source_id']:norm(x) for x in load(R/'results/A/A_D24_E3_UNSTARTED_CONTINUATION_V1/COMBINED_EPISODES.json')['rows']}

def compare(a,b,name):
 ids=sorted(set(a)&set(b));ts=defaultdict(list); rescued=harmed=0;assert len(ids)
 for sid in ids:
  x,y=a[sid],b[sid];assert x['task']==y['task']
  for k in ['env_seed','policy_seed']:
   if x.get(k) not in (None,'') and y.get(k) not in (None,''):assert str(x[k])==str(y[k]),(name,sid,k,x[k],y[k])
  d=int(x['success'])-int(y['success']);ts[x['task']].append(d);rescued+=d==1;harmed+=d==-1
 n=len(ids);diff=(rescued-harmed)/n
 var=0
 for v in ts.values():
  nt=len(v);mean=sum(v)/nt
  assert nt>=2
  s2=sum((x-mean)**2 for x in v)/(nt-1)
  var+=(nt/n)**2*s2/nt
 se=math.sqrt(var);nd=rescued+harmed
 p=min(1.,2*sum(math.comb(nd,k) for k in range(min(rescued,harmed)+1))/2**nd) if nd else 1.
 return dict(comparison=name,n=n,task_count=len(ts),a_success=sum(a[i]['success'] for i in ids),b_success=sum(b[i]['success'] for i in ids),rescued=rescued,harmed=harmed,difference_pp=100*diff,paired_normal_95ci_pp=[100*(diff-1.959963984540054*se),100*(diff+1.959963984540054*se)],mcnemar_exact_two_sided_p=p)
ans=[]
for h in [10,20,30,40,50]:
 p=post[('pi05',h,'G0-multi')];assert len(p)==len(N[h])==len(Rs[h])==500
 ans+=[compare(p,N[h],f'pi05 H{h} Post–N'),compare(p,Rs[h],f'pi05 H{h} Post–R')]
ans.append(compare(post[('pi05',10,'G0-multi')],post[('pi05',10,'G0-once')],'pi05 H10 Post multi–once'))
ans.append(compare(post[('pi05',10,'G0-multi')],V,'pi05 H10 Post–VLA-Corrector'))
ans.append(compare(post[('pi05',10,'G0-multi')],G,'pi05 H10 Post–GAF'))
# Holm separate families for five H Post-N and five H Post-R.
for suffix in ['Post–N','Post–R']:
 group=sorted([x for x in ans if x['comparison'].endswith(suffix)],key=lambda x:x['mcnemar_exact_two_sided_p']); running=0
 for i,x in enumerate(group):
  running=max(running,(len(group)-i)*x['mcnemar_exact_two_sided_p']);x['holm_five_H_p']=min(1,running)
for x in ans:print(x)
rows=[]
for task in sorted({x['task'] for x in N[10].values()}):
 row={'task':task}
 for h in [10,20,30,40,50]:
  for method,table in [('N',N[h]),('R',Rs[h]),('Post',post[('pi05',h,'G0-multi')])]:
   rr=[x for x in table.values() if x['task']==task];assert len(rr)==10
   row[f'{method}_H{h}_success']=sum(x['success'] for x in rr)
  row[f'Post_minus_N_H{h}_pp']=10*(row[f'Post_H{h}_success']-row[f'N_H{h}_success'])
  row[f'Post_minus_R_H{h}_pp']=10*(row[f'Post_H{h}_success']-row[f'R_H{h}_success'])
 rows.append(row)
json.dump({'scope':'final L11 Post fit9101 only; historical N/R/external baselines reused; selected 50 of main500 revealed', 'interval_method':'Pointwise 95% normal approximation for paired source difference, fixed-task stratified sample variance, no multiplicity correction for CI; exact two-sided McNemar with separate Holm across five Post-N/five Post-R tests. No bootstrap; no new evaluation.','comparisons':ans,'sources':sources},open('/tmp/FINAL_L11_POST_PAIRED_STATS.json','w'),ensure_ascii=False,indent=2)
with open('/tmp/FINAL_L11_POST_PER_TASK.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
