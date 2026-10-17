"""Read durable rows and publish actual N/Post denominators and paired counts."""
import argparse
import csv
import json
from pathlib import Path
import d24_common as d


def summarize(batch_path):
    cfg=d.load(batch_path)
    out=d.R/cfg['batch_id']
    baselines=d.load(cfg['baseline_index'])
    groups,task_rows=[],[]
    for model in ('smolvla','xvla'):
        jobs=[job for job in cfg['jobs'] if job['kind']==model]
        rows,claimed={},set()
        for job in jobs:
            p=Path(job['output'])
            claimed.update(q.stem for q in (p/'episode_claims').glob('*.json'))
            log=p/'episodes.jsonl'
            for line in log.read_text().splitlines() if log.exists() else []:
                row=json.loads(line)
                sid=row['source_id']
                if sid in rows:
                    raise ValueError('Duplicate Post source: '+sid)
                rows[sid]=row
        planned=[row for job in jobs for row in d.load(job['config'])['episodes']]
        valid={sid:row for sid,row in rows.items() if row['status']=='complete' and type(row.get('success')) is bool}
        baseline={row['source_id']:row for row in baselines[model]}
        paired=sorted(set(valid)&set(baseline))
        wins=sum(valid[sid]['success'] and not baseline[sid]['success'] for sid in paired)
        losses=sum(baseline[sid]['success'] and not valid[sid]['success'] for sid in paired)
        group=dict(model=model,method='Full-Post-transfer',planned=len(planned),physical_claims=len(claimed),
            valid=len(valid),successes=sum(row['success'] for row in valid.values()),
            technical_failures=sum(row['status']=='technical_failure' for row in rows.values()),
            execution_unknown=len(claimed-set(rows)),unstarted=len(planned)-len(claimed),
            N_valid=len(baseline),N_successes=sum(row['success'] for row in baseline.values()),
            paired_valid=len(paired),Post_only=wins,N_only=losses,
            paired_Post_successes=sum(valid[sid]['success'] for sid in paired),
            paired_N_successes=sum(baseline[sid]['success'] for sid in paired),
            paired_success_difference_pp=100*(wins-losses)/len(paired) if paired else None,
            base_policy_calls=sum(row.get('queries',0) for row in rows.values()),
            interventions=sum(row.get('interventions',0) for row in rows.values()),
            total_inference_seconds=sum(row.get('inference_seconds',0) for row in rows.values()),
            total_corrector_seconds=sum(row.get('corrector_seconds',0) for row in rows.values()),
            total_episode_wall_seconds=sum(row.get('elapsed_seconds',0) for row in rows.values()),
            correction_training='unchanged historical pi05 five-task D/G0/Q',
            base_training='Smol fixed050000' if model=='smolvla' else 'X fixed30000;49unique train tasks',
            missing_sources=[dict(source_id=row['source_id'],disposition=(rows[row['source_id']]['status'] if row['source_id'] in rows else
                'execution_unknown' if row['source_id'] in claimed else 'unstarted')) for row in planned if row['source_id'] not in valid])
        groups.append(group)
        for task in sorted({row['task'] for row in planned}):
            pids=[sid for sid in paired if valid[sid]['task']==task]
            post=[row for row in valid.values() if row['task']==task]
            n=[row for row in baseline.values() if row['task']==task]
            task_rows.append(dict(model=model,task=task,N_n=len(n),N_success=sum(row['success'] for row in n),
                Post_n=len(post),Post_success=sum(row['success'] for row in post),paired_n=len(pids),
                paired_N_success=sum(baseline[sid]['success'] for sid in pids),
                paired_Post_success=sum(valid[sid]['success'] for sid in pids)))
    result=dict(status='complete' if all(g['valid']==500 for g in groups) else 'partial',at_utc=d.utc(),
        run_id=cfg['run_id'],groups=groups,optimizer_updates=0,
        source_policy='same frozen500 D24_MW per base; never replace missing sources; reuse valid N without replay',
        protocol='native H50/H30 K10 NFE10, actual baseline MW physics; true G0>.05 once; fresh base replan then C10 Post',
        disclosure='Frozen pi05 feature/D/G0/Q transfer, including original pi05 action metric; full trigger/queue mechanism, not base-specific retraining',
        holder_policy='whole formal wave all holders off; sum episode wall time is not aggregate GPU duration',
        baseline_index=cfg['baseline_index'],new_development_attempts=0,post_rows_scope='all durable completed/failed rows; unknown stays missing')
    d.atomic(out/'N_POST_SUMMARY.json',result)
    with (out/'N_POST_TASKS.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(task_rows[0]))
        writer.writeheader();writer.writerows(task_rows)
    lines=['# E8 Smol/X N versus Full-Post transfer','',
        '| Base | N success / valid | Post success / valid | Paired n | Paired difference (pp) |',
        '|---|---:|---:|---:|---:|']
    for g in groups:
        lines.append('| %s | %s/%s | %s/%s | %s | %s |' % (g['model'],g['N_successes'],g['N_valid'],
            g['successes'],g['valid'],g['paired_valid'],g['paired_success_difference_pp']))
    lines.extend(['','Frozen pi05 visual/language/D/G0/Q modules transferred to native Smol/X actions. '
        'No base retraining, new development, or N replay. Native base renderer/physics/queue remain as in N. '
        'Technical failure, unknown and unstarted counts remain separate in JSON.'])
    (out/'N_POST_SUMMARY.md').write_text('\n'.join(lines)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True)
    print(json.dumps(summarize(p.parse_args().batch),indent=2))
