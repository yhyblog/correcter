"""C durable terminal rows and same-source N/Post comparisons; no execution."""
import csv
import math
from pathlib import Path
import random
import d24_common as d


def read_rows(jobs):
    rows={}
    for job in jobs:
        for p in (Path(job['output'])/'episodes').glob('*/RESULT.json'):
            row=d.load(p);sid=row['source_id']
            if sid in rows:raise ValueError('Duplicate scientific terminal '+sid)
            rows[sid]=row
    return rows


def valid(rows):
    return {sid:r for sid,r in rows.items() if r.get('status')=='complete' and type(r.get('success')) is bool}


def wilson(w,n):
    if not n:return None
    z=1.959963984540054;p=w/n;den=1+z*z/n
    c=(p+z*z/(2*n))/den;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [100*max(0,c-h),100*min(1,c+h)]


def paired(new,old):
    ids=sorted(set(new)&set(old));n=len(ids)
    wins=sum(new[s]['success'] and not old[s]['success'] for s in ids)
    losses=sum(old[s]['success'] and not new[s]['success'] for s in ids)
    bytask={}
    for sid in ids:
        bytask.setdefault(new[sid]['task'],[]).append(int(new[sid]['success'])-int(old[sid]['success']))
    ci=None
    if bytask:
        groups=[(sum(v),len(v)) for k,v in sorted(bytask.items())];rng=random.Random(20260922)
        boot=[]
        for _ in range(2000):
            sample=rng.choices(groups,k=len(groups))
            boot.append(100*sum(v[0] for v in sample)/sum(v[1] for v in sample))
        boot.sort();ci=[boot[49],boot[1949]]
    return dict(paired_valid=n,rescued=wins,harmed=losses,
        new_successes=sum(new[s]['success'] for s in ids),old_successes=sum(old[s]['success'] for s in ids),
        difference_pp=100*(wins-losses)/n if n else None,task_cluster_bootstrap_95_ci_pp=ci,
        uncertainty='descriptive paired task-cluster percentile bootstrap, 2000 draws, seed20260922; fixed-source missingness retained')


def summarize(path):
    cfg=d.load(path);out=d.R/cfg['batch_id'];nindex=d.load(cfg['baseline_index'])
    postcfg=d.load(cfg['post_batch']);groups=[];tasks=[]
    for kind in ('smolvla','xvla'):
        jobs=[j for j in cfg['jobs'] if j['kind']==kind]
        rows=read_rows(jobs);v=valid(rows)
        n={r['source_id']:r for r in nindex[kind]}
        post=valid(read_rows([j for j in postcfg['jobs'] if j['kind']==kind]))
        planned=[s for j in jobs for s in d.load(j['config'])['episodes']]
        claims={p.stem.split('__')[0] for p in (d.R/'unit_claims'/kind).glob('*.json')}
        g=dict(base=kind,method='Full-Velocity-transfer',planned=len(planned),entered=len(claims),valid=len(v),
            successes=sum(r['success'] for r in v.values()),technical_failures=sum(r.get('status')=='technical_failure' for r in rows.values()),
            unknown=len(claims-set(rows)),unstarted=len(planned)-len(claims),
            success_rate_pct=100*sum(r['success'] for r in v.values())/len(v) if v else None,
            success_wilson95_pct=wilson(sum(r['success'] for r in v.values()),len(v)),
            N_valid=len(n),N_successes=sum(r['success'] for r in n.values()),
            Post_valid=len(post),Post_successes=sum(r['success'] for r in post.values()),
            versus_N=paired(v,n),versus_Post=paired(v,post),
            interventions=sum(r.get('interventions',0) for r in rows.values()),
            policy_calls=sum(r.get('queries',0) for r in rows.values()),flow_calls=sum(r.get('flow_calls',0) for r in rows.values()),
            action_gradients=sum(r.get('action_gradients',0) for r in rows.values()),
            total_episode_seconds=sum(r.get('elapsed_seconds',0) for r in rows.values()),
            total_base_inference_seconds=sum(r.get('inference_seconds',0) for r in rows.values()),
            total_corrector_seconds=sum(r.get('corrector_seconds',0) for r in rows.values()),
            missing=[dict(source_id=s['source_id'],status=rows[s['source_id']]['status'] if s['source_id'] in rows else
                          'unknown' if s['source_id'] in claims else 'unstarted') for s in planned if s['source_id'] not in v])
        groups.append(g)
        d.atomic(out/(kind+'_SUMMARY.json'),g)
        for task in sorted({s['task'] for s in planned}):
            vv={s:r for s,r in v.items() if r['task']==task}
            tasks.append(dict(base=kind,task=task,Velocity_valid=len(vv),Velocity_successes=sum(r['success'] for r in vv.values()),
                N_valid=sum(r['task']==task for r in n.values()),N_successes=sum(r['success'] and r['task']==task for r in n.values()),
                Post_valid=sum(r['task']==task for r in post.values()),Post_successes=sum(r['success'] and r['task']==task for r in post.values())))
    result=dict(task_id='C_D24_MW_VELOCITY_V1',at_utc=d.utc(),status='complete' if all(g['valid']==500 for g in groups) else 'partial',groups=groups,
        model_optimizer_updates=0,head_optimizer_updates=0,development_attempts=0,
        prior_technical_attempts=8,planned_total_physical_attempt_cap=1008,
        prior_failures_preserved=str(d.R/'D24_C_MW_VELOCITY_r1/SUMMARY.json'),
        protocol='B fixed500 per base, unchanged source/seeds/native Mesa/physics, H50/H30 K10 NFE10, G0>.05 once, C10',
        adaptation='Smol native velocity/Euler; X velocity-reparameterized native clean-prediction remixer (not Euler); native mean/std+true clamp, independent own radius',
        transfer='frozen pi05 external features/PCA/D/G0/Q with historical five-task training coverage',
        runtime='C8H100; whole-wave holders off; sampled GPU utilization in gpu_metrics.jsonl; cross-host raw time does not establish algorithm speed advantage',
        cost_note='base inference time includes synchronous gradient RPC; corrector time overlaps it; do not add these totals',
        source_manifest=str(d.W/'MW_VELOCITY_BATCH.json'))
    d.atomic(out/'SUMMARY.json',result)
    with (out/'TASKS.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(tasks[0]));writer.writeheader();writer.writerows(tasks)
    lines=['| Base | N success/valid | Post success/valid | Velocity success/valid | V−N paired pp | V−Post paired pp |',
           '|---|---:|---:|---:|---:|---:|']
    for g in groups:
        fmt=lambda v:'unknown' if v is None else f'{v:+.2f}'
        lines.append(f"| {g['base']} | {g['N_successes']}/{g['N_valid']} | {g['Post_successes']}/{g['Post_valid']} | {g['successes']}/{g['valid']} | {fmt(g['versus_N']['difference_pp'])} | {fmt(g['versus_Post']['difference_pp'])} |")
    lines+=['','Technical failures, unknown and unstarted rows are excluded from valid denominators. Paired counts and uncertainty are in SUMMARY.json.',
            '',result['adaptation']+'. '+result['transfer']+'.', '',result['runtime']+'.']
    (out/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
    d.atomic(d.C/'receipts/C/C_D24_MW_VELOCITY_V1_RESULT_r2.json',dict(result,summary_path=str(out/'SUMMARY.json'),whole_task_complete=result['status']=='complete'))
    return result
