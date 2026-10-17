"""CPU statistics on existing source-matched outcomes, no model imports."""
import csv
import json
import math
import os
from pathlib import Path
import numpy as np

def write_csv(path,rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.update')
    fields=list(dict.fromkeys(k for row in rows for k in row)) or ['status']
    with temp.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,allow_nan=False,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    os.replace(temp,path)

def read_csv(path):
    rows=[]
    for row in csv.DictReader(Path(path).open()):
        for k,v in list(row.items()):
            if v in ('True','False'):row[k]=v=='True'
            elif v in ('','None','null'):row[k]=None
            elif k in ('H','ordinal','env_seed','policy_seed','interventions','steps','sampling_calls','flow_calls','policy_calls','first_cut','last_cut') or k.startswith('counter_'):
                row[k]=int(v)
            elif k.endswith('_seconds'):row[k]=float(v)
        rows.append(row)
    return rows

def pair(left,right,*,name):
    l={r['source_id']:r for r in left if r['status']=='complete'};r={x['source_id']:x for x in right if x['status']=='complete'}
    if l.keys()!=r.keys() or len(l)!=len(left) or len(r)!=len(right):raise ValueError('paired source completeness/duplicate mismatch')
    delta=[];by_task={};resc=harm=0
    for sid in sorted(l):
        a,b=l[sid],r[sid]
        for k in ('task','env_seed','policy_seed'):
            if str(a[k])!=str(b[k]):raise ValueError('paired source identity mismatch '+k)
        if type(a['success']) is not bool or type(b['success']) is not bool:raise ValueError('nonboolean scientific outcome')
        d=int(a['success'])-int(b['success']);delta.append(d);by_task.setdefault(a['task'],[]).append(d)
        resc+=d==1;harm+=d==-1
    rng=np.random.default_rng(20260921);draws=np.zeros(2000)
    for task,x in sorted(by_task.items()):
        a=np.asarray(x,float);draws+=a[rng.integers(0,len(a),(2000,len(a)))].sum(axis=1)
    draws*=100/len(delta);n=resc+harm
    p=min(1.,2*sum(math.comb(n,k) for k in range(min(resc,harm)+1))/2**n) if n else 1.
    ci=np.quantile(draws,[.025,.975])
    return dict(comparison=name,paired_valid=len(delta),left_successes=sum(x['success'] for x in l.values()),right_successes=sum(x['success'] for x in r.values()),rescued=resc,harmed=harm,difference_pp=100*sum(delta)/len(delta),CI95_low_pp=float(ci[0]),CI95_high_pp=float(ci[1]),McNemar_exact_p=p,CI_scope='pointwise within-fixed-task source bootstrap 2000 seed20260921; no training-seed uncertainty')

def holm(rows):
    if len(rows)!=15:
        for row in rows:row.update(Holm_15_p=None,Holm_missing_reason='full prespecified 15-comparison family not yet available')
        return
    running=0.
    for i,row in enumerate(sorted(rows,key=lambda x:x['McNemar_exact_p'])):
        running=max(running,min(1.,(15-i)*row['McNemar_exact_p']));row.update(Holm_15_p=running,Holm_missing_reason=None)

def compact(row):
    result={k:v for k,v in row.items() if k not in ('events','plans','arrays','counters','numeric_counters','technical_failure')}
    for k,v in row.get('counters',{}).items():result['counter_'+k]=v
    for k,v in row.get('numeric_counters',{}).items():result['numeric_'+k]=v
    result['technical_failure']=row.get('technical_failure')
    return result

def costs(rows):
    good=[r for r in rows if r['status']=='complete'];success=sum(r['success'] for r in good)
    fields=['sampling_calls','flow_calls','interventions','elapsed_seconds','inference_seconds','environment_seconds','reset_seconds','counter_contexts','counter_D_forward','counter_G0_forward','counter_Q_ensemble_forward','counter_action_gradients','numeric_visual_encoder_forwards','numeric_language_embedding_forwards','numeric_encoder_forward_calls']
    out={}
    for k in fields:
        vals=[r[k] for r in good if isinstance(r.get(k),(int,float)) and math.isfinite(r[k])]
        total=sum(vals)
        out[k]=dict(known=len(vals),valid_denominator=len(good),known_subtotal=total,total=total if len(vals)==len(good) else None,mean_per_valid=total/len(good) if good and len(vals)==len(good) else None,all_valid_cost_per_success=total/success if success and len(vals)==len(good) else None,minimum=min(vals) if vals else None,maximum=max(vals) if vals else None,missing_reason='field not present in saved logs' if len(vals)<len(good) else None)
    return dict(valid=len(good),successes=success,physical_failures=sum(r['status']!='complete' for r in rows),costs=out,elapsed_is_sum_of_episode_seconds_not_wave_wall=True)
