"""Terminal native Velocity counts, missingness, costs and paired comparisons."""
import csv
import json
import math
from pathlib import Path
import d24_common as d


def paired(candidate, baseline):
    ids=sorted(set(candidate)&set(baseline));n=len(ids)
    wins=sum(candidate[s]['success'] and not baseline[s]['success'] for s in ids)
    losses=sum(baseline[s]['success'] and not candidate[s]['success'] for s in ids)
    m=wins+losses;difference=(wins-losses)/n if n else None
    se=math.sqrt((m/n-difference**2)/(n-1)) if n and n>1 else None
    return dict(paired_valid=n,candidate_successes=sum(candidate[s]['success'] for s in ids),
        baseline_successes=sum(baseline[s]['success'] for s in ids),candidate_only=wins,baseline_only=losses,
        difference_pp=100*difference if n else None,
        normal95_CI_pp=[100*(difference-1.96*se),100*(difference+1.96*se)] if se is not None else None,
        exact_McNemar_two_sided_p=min(1.,2*sum(math.comb(m,k) for k in range(min(wins,losses)+1))/2**m) if m else 1.)


def summarize(batch_path):
    cfg=d.load(batch_path);out=d.R/cfg['batch_id'];rows={};claims=set();planned=[]
    for job in cfg['jobs']:
        root=Path(job['output']);jc=d.load(job['config']);planned.extend(jc['episodes'])
        claims.update(p.stem for p in (root/'episode_claims').glob('*.json'))
        p=root/'episodes.jsonl'
        if not p.exists():continue
        for line in p.read_text().splitlines():
            row=json.loads(line)
            if row['source_id'] in rows:raise ValueError('Duplicate Velocity source')
            rows[row['source_id']]=row
    valid={s:r for s,r in rows.items() if r['status']=='complete' and type(r.get('success')) is bool}
    n={r['source_id']:r for r in d.load(cfg['baseline_index'])}
    post={r['source_id']:r for r in d.load(cfg['post_index'])}
    groups=[];taskrows=[]
    for suite in ('libero_spatial','libero_object','libero_goal','libero_10'):
        nv={s:r for s,r in n.items() if r['suite']==suite};pv={s:r for s,r in post.items() if r['suite']==suite}
        vv={s:r for s,r in valid.items() if r['suite']==suite}
        groups.append(dict(suite=suite,N_valid=len(nv),N_successes=sum(r['success'] for r in nv.values()),
            Post_valid=len(pv),Post_successes=sum(r['success'] for r in pv.values()),
            Velocity_valid=len(vv),Velocity_successes=sum(r['success'] for r in vv.values()),
            versus_N=paired(vv,nv),versus_Post=paired(vv,pv)))
        for task in range(10):
            taskrows.append(dict(suite=suite,task_id=task,
                N_valid=sum(r['task_id']==task for r in nv.values()),N_successes=sum(r['task_id']==task and r['success'] for r in nv.values()),
                Post_valid=sum(r['task_id']==task for r in pv.values()),Post_successes=sum(r['task_id']==task and r['success'] for r in pv.values()),
                Velocity_valid=sum(r['task_id']==task for r in vv.values()),Velocity_successes=sum(r['task_id']==task and r['success'] for r in vv.values())))
    total_queries=sum(r.get('queries',0) for r in rows.values());guided_calls=sum(r.get('guided_flow_calls',0) for r in rows.values())
    result=dict(status='complete' if len(valid)==400 else 'partial',at_utc=d.utc(),run_id=cfg['run_id'],
        method='Velocity-operator-transfer-native-LIBERO',Full_method=False,D_or_G0_present=False,
        Velocity_valid=len(valid),Velocity_successes=sum(r['success'] for r in valid.values()),
        technical_failures=sum(r['status']=='technical_failure' for r in rows.values()),
        execution_unknown=len(claims-set(rows)),unstarted=len(planned)-len(claims),physical_attempts=len(claims),
        prior_B_physical_attempts=5287,cumulative_B_attempts=5287+len(claims),
        new_development_rollouts=0,new_optimizer_updates=0,base_model_updates=0,cumulative_B_small_network_updates=238000,
        groups=groups,versus_N=paired(valid,n),versus_Post=paired(valid,post),
        nonzero_interventions=sum(r.get('interventions',0) for r in rows.values()),
        base_policy_calls=total_queries,guided_policy_calls=guided_calls,total_policy_calls=total_queries+guided_calls,
        flow_gradient_calls=sum(r.get('flow_gradient_calls',0) for r in rows.values()),
        total_policy_and_corrector_seconds=sum(r.get('inference_seconds',0) for r in rows.values()),
        total_corrector_seconds=sum(r.get('corrector_seconds',0) for r in rows.values()),
        total_episode_wall_seconds=sum(r.get('elapsed_seconds',0) for r in rows.values()),
        frozen_head=cfg['frozen_head_ready'],protocol=cfg['velocity_protocol'],
        baseline_index=cfg['baseline_index'],post_index=cfg['post_index'],
        source_protocol='same original400 random-reset sources and policy seeds; official weights/norm H10/K5/NFE10; not official fixed initial states',
        scientific_limitations='head has only5 negative training candidates, validation40/40 successes; no test-guided selection; four head initializations are not four independent dataset fits',
        missingness='technical and unknown stay missing, never success=false; valid paired subsets only',
        holder_policy='all holders off until entire wave drains, including early-finished GPUs')
    d.atomic(out/'N_POST_VELOCITY_SUMMARY.json',result)
    with (out/'N_POST_VELOCITY_TASKS.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(taskrows[0]));writer.writeheader();writer.writerows(taskrows)
    lines=['# Native LIBERO N / Post / Velocity','',
        'Post/Velocity operator transfer with frozen native small head; no D/G0, not Full. No new fitting or development.',
        '', '| Suite | N success/valid | Post success/valid | Velocity success/valid | V minus N pp (paired) |',
        '|---|---:|---:|---:|---:|']
    for g in groups:lines.append('| %s | %d/%d | %d/%d | %d/%d | %s |'%(g['suite'],g['N_successes'],g['N_valid'],g['Post_successes'],g['Post_valid'],
        g['Velocity_successes'],g['Velocity_valid'],g['versus_N']['difference_pp']))
    lines.extend(['','Same original random-reset seeds, not official fixed initial states. All valid results retained; no test-driven tuning.',
        'Counts, costs, missingness, paired uncertainty, frozen guidance and head provenance are in the JSON.'])
    (out/'N_POST_VELOCITY_SUMMARY.md').write_text('\n'.join(lines)+'\n')
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True)
    print(json.dumps(summarize(p.parse_args().batch),indent=2))
