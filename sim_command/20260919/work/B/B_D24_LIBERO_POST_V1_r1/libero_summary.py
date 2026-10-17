"""Terminal publication with honest missingness and valid-pair denominators."""
import csv
import json
from pathlib import Path
import d24_common as d


def summarize(batch_path):
    cfg=d.load(batch_path);out=d.R/cfg['batch_id'];baseline=d.load(cfg['baseline_index'])
    test={};development=[];claims=set();planned=[]
    for job in cfg['jobs']:
        root=Path(job['output']);jc=d.load(job['config']);planned.extend(jc['episodes'])
        claims.update(p.stem for p in (root/'episode_claims').glob('*.json'))
        for filename,target in (('episodes.jsonl',test),('development.jsonl',development)):
            path=root/filename
            if not path.exists():continue
            for line in path.read_text().splitlines():
                row=json.loads(line)
                if isinstance(target,list):target.append(row)
                else:
                    if row['source_id'] in target:raise ValueError('Duplicate Post source')
                    target[row['source_id']]=row
    valid={sid:r for sid,r in test.items() if r['status']=='complete' and type(r.get('success')) is bool}
    groups=[];taskrows=[]
    for suite in ('libero_spatial','libero_object','libero_goal','libero_10'):
        n={r['source_id']:r for r in baseline if r['suite']==suite}
        post={sid:r for sid,r in valid.items() if r['suite']==suite}
        pair=sorted(set(n)&set(post));ids={r['source_id'] for r in planned if suite in r['source_id']}
        wins=sum(post[s]['success'] and not n[s]['success'] for s in pair)
        losses=sum(n[s]['success'] and not post[s]['success'] for s in pair)
        groups.append(dict(suite=suite,N_valid=len(n),N_successes=sum(r['success'] for r in n.values()),
            Post_valid=len(post),Post_successes=sum(r['success'] for r in post.values()),paired_valid=len(pair),
            paired_N_successes=sum(n[s]['success'] for s in pair),paired_Post_successes=sum(post[s]['success'] for s in pair),
            Post_only=wins,N_only=losses,paired_difference_pp=100*(wins-losses)/len(pair) if pair else None,
            technical_failures=sum(test[s]['status']=='technical_failure' for s in ids&set(test)),
            execution_unknown=len((ids&claims)-set(test)),unstarted=len(ids-claims)))
        for task in range(10):
            ps=[s for s in pair if post[s]['task_id']==task];nr=[r for r in n.values() if r['task_id']==task]
            pr=[r for r in post.values() if r['task_id']==task]
            taskrows.append(dict(suite=suite,task_id=task,N_valid=len(nr),N_successes=sum(r['success'] for r in nr),
                Post_valid=len(pr),Post_successes=sum(r['success'] for r in pr),paired_valid=len(ps),
                paired_N_successes=sum(n[s]['success'] for s in ps),paired_Post_successes=sum(post[s]['success'] for s in ps)))
    fit=d.load(out/'FIT_RESULT.json') if (out/'FIT_RESULT.json').exists() else None
    fit_progress=d.load(out/'FIT_PROGRESS.json') if (out/'FIT_PROGRESS.json').exists() else {}
    summary=dict(status='complete' if len(valid)==400 else 'partial',at_utc=d.utc(),run_id=cfg['run_id'],
        method='Post-operator-transfer-native-LIBERO',Full_method=False,D_or_G0_present=False,groups=groups,
        development_planned=160,development_recorded=len(development),
        development_valid=sum(r['status']=='complete' for r in development),
        development_successes=sum(r['success'] is True for r in development),
        development_technical_failures=sum(r['status']=='technical_failure' for r in development),
        physical_attempts_claimed=len(claims),prior_B_physical_attempts=4727,cumulative_B_attempts=4727+len(claims),
        optimizer_updates=(fit or fit_progress).get('optimizer_updates',0),base_model_updates=0,fit_result=fit,
        interventions=sum(r.get('interventions',0) for r in test.values()),
        policy_calls=sum(r.get('queries',0) for r in test.values()),
        total_policy_and_corrector_seconds=sum(r.get('inference_seconds',0) for r in test.values()),
        total_corrector_seconds=sum(r.get('corrector_seconds',0) for r in test.values()),
        total_episode_wall_seconds=sum(r.get('elapsed_seconds',0) for r in test.values()),
        adaptation=cfg['adaptation'],baseline_index=cfg['baseline_index'],
        source_protocol='same frozen400 reset/policy seeds and actual random reset as N; not official fixed initial-state benchmark',
        missingness='technical failure and unknown excluded from success denominators, never written as failure',
        holder_policy='all holders off throughout entire wave, including CPU-fit barrier and finished GPUs',
        training_scope='official pi05 frozen; 32 new development parents, 24 fit/8 descriptive validation; no test-based selection')
    d.atomic(out/'N_POST_SUMMARY.json',summary)
    with (out/'N_POST_TASKS.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(taskrows[0]));writer.writeheader();writer.writerows(taskrows)
    lines=['# Native LIBERO Post operator transfer','',
        'Frozen official pi05/norm, H10/K5, XYZ/gripper correction only. No D/G0, not Full. New native development only.',
        '', '| Suite | N successes/valid | Post successes/valid | Paired n | Difference pp |',
        '|---|---:|---:|---:|---:|']
    for g in groups:lines.append('| %s | %d/%d | %d/%d | %d | %s |'%(g['suite'],g['N_successes'],g['N_valid'],
        g['Post_successes'],g['Post_valid'],g['paired_valid'],g['paired_difference_pp']))
    lines.extend(['','Actual random resets reuse frozen N sources, not the official fixed-initial-state protocol.',
        'Training, development, missing sources, costs, fixed intervention rule and metric are in the JSON.'])
    (out/'N_POST_SUMMARY.md').write_text('\n'.join(lines)+'\n')
    return summary


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True)
    print(json.dumps(summarize(p.parse_args().batch),indent=2))
