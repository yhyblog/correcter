"""Actual C results only, strict fixed-source pairs, no scientific execution."""
import csv,math,random,json
from collections import Counter
from pathlib import Path
from paths import ROOT,CAMPAIGN,TASK
from qio import read,atomic_json,utc

def paired(new,old):
    ids=sorted(set(new)&set(old));bytask={}
    for sid in ids:bytask.setdefault(new[sid]['task'],[]).append(int(new[sid]['success'])-int(old[sid]['success']))
    rescued=sum(new[s]['success'] and not old[s]['success'] for s in ids);harmed=sum(old[s]['success'] and not new[s]['success'] for s in ids)
    ci=None
    if ids:
        groups=[(sum(v),len(v)) for _,v in sorted(bytask.items())];rng=random.Random(20260922);samples=[]
        for _ in range(2000):
            sample=rng.choices(groups,k=len(groups));samples.append(100*sum(x[0] for x in sample)/sum(x[1] for x in sample))
        samples.sort();ci=[samples[49],samples[1949]]
    return dict(paired_valid=len(ids),rescued=rescued,harmed=harmed,difference_pp=100*(rescued-harmed)/len(ids) if ids else None,
        new_successes=sum(new[s]['success'] for s in ids),reference_successes=sum(old[s]['success'] for s in ids),task_cluster_bootstrap_95_CI_pp=ci,
        interval_method='paired task cluster bootstrap, 2000 draws, seed20260922; no imputation')

def valid(rows):return {s:r for s,r in rows.items() if r.get('status')=='complete' and type(r.get('success')) is bool}

def main():
    sources=read(ROOT/'config/TEST_SOURCES.json')['sources'];source_index={s['source_id']:s for s in sources}
    prior=read(CAMPAIGN/'work/C/C_D24_MW_VELOCITY_V1_r2/MW_VELOCITY_BATCH.json')
    baseline={r['source_id']:r for r in read(prior['baseline_index'])['xvla']}
    assert len(baseline)==500 and sum(r['success'] for r in baseline.values())==403
    frozen={}
    for name,batch in [('Post',read(prior['post_batch'])),('Velocity',prior)]:
        rows={}
        for job in batch['jobs']:
            if job['kind']!='xvla':continue
            for p in (Path(job['output'])/'episodes').glob('*/RESULT.json'):
                r=read(p);rows[r['source_id']]=r
        frozen[name]=valid(rows)
    data=read(ROOT/'DATA_SUMMARY.json') if (ROOT/'DATA_SUMMARY.json').exists() else None
    fits=read(ROOT/'FIT_SUMMARY.json') if (ROOT/'FIT_SUMMARY.json').exists() else None
    if fits is None:
        members={p.parent.name:read(p) for p in (ROOT/'fits').glob('*/RESULT.json')}
        fits=dict(status='not_completed',members=members,updates=sum(x['updates'] for x in members.values()),D_ready=False,G0_ready=False,Q_ready=False)
        atomic_json(ROOT/'FIT_SUMMARY.json',fits)
    collection=list((ROOT/'collection').glob('*/RESULT.json'))
    collection_rows=[read(p) for p in (ROOT/'collection').glob('*/*/RESULT.json')]
    if data is None:
        data=dict(status='not_prepared',planned_parents=250,counts=dict(Counter(r['status'] for r in collection_rows)),
            completed_parents=len(collection),technical_failures=sum(r['status']=='technical_failure' for r in collection_rows),missing_not_failure=True)
        atomic_json(ROOT/'DATA_SUMMARY.json',data)
    final_rows=[];groups=[];pairs={};methods={}
    for method in ['R','Post','Velocity']:
        rows={p.parent.name:read(p) for p in (ROOT/'evaluation'/method).glob('*/RESULT.json')};good=valid(rows);methods[method]=good
        for sid,row in rows.items():
            s=source_index[sid]
            assert all(row[k]==s[k] for k in ['task','reset_seed','policy_seed'])
            assert row['interventions'] in (0,1)
            for e in row.get('events',[]):
                if e['trigger']:assert e['legal_cut'] and e['gate']>.05 and e['commit_until']==e['step']+10
        counts=Counter();encoder=Counter()
        for r in rows.values():counts.update(r.get('counters',{}));encoder.update(r.get('encoder_counters',{}))
        entered=sum((ROOT/'evaluation'/method/s['source_id']/'ENTERED.json').exists() for s in sources)
        groups.append(dict(method=method,planned=500,entered=entered,valid=len(good),successes=sum(r['success'] for r in good.values()) if good else None,
            success_rate=sum(r['success'] for r in good.values())/len(good) if good else None,
            technical=sum(r['status']=='technical_failure' for r in rows.values()),budget_truncated=sum(r['status']=='budget_truncated' for r in rows.values()),
            unknown=entered-len(rows),unstarted=500-entered,trigger_zero=sum(r['interventions']==0 for r in good.values()),
            trigger_once=sum(r['interventions']==1 for r in good.values()),policy_and_runtime_counters=dict(counts),external_encoder_and_heads_counters=dict(encoder),
            total_episode_seconds=sum(r['elapsed_seconds'] for r in rows.values())))
        pairs[method+'_vs_N']=paired(good,baseline)
        if method in frozen:pairs[method+'_vs_frozen_pi05_heads']=paired(good,frozen[method])
        for s in sources:
            r=rows.get(s['source_id'],{});p=ROOT/'evaluation'/method/s['source_id']/'ENTERED.json'
            final_rows.append(dict(method=method,source_id=s['source_id'],task=s['task'],reset_seed=s['reset_seed'],policy_seed=s['policy_seed'],
                status=r.get('status','execution_unknown' if p.exists() else 'unstarted'),success=r.get('success'),steps=r.get('steps'),
                interventions=r.get('interventions'),first_cut=r.get('first_cut'),elapsed_seconds=r.get('elapsed_seconds'),
                policy_queries=r.get('counters',{}).get('policy_queries'),policy_flow_calls=r.get('counters',{}).get('policy_flow_calls'),
                visual_encoder_calls=r.get('encoder_counters',{}).get('visual_encoder_calls'),D_calls=r.get('encoder_counters',{}).get('D_forward_calls'),
                G0_calls=r.get('encoder_counters',{}).get('G0_forward_calls'),Q_calls=r.get('encoder_counters',{}).get('Q_ensemble_forward_calls'),
                action_gradient_calls=r.get('encoder_counters',{}).get('action_gradient_calls'),N_success=baseline[s['source_id']]['success'],
                result_path=str(ROOT/'evaluation'/method/s['source_id']/'RESULT.json') if r else None))
    pairs['Post_vs_R']=paired(methods['Post'],methods['R']);pairs['Velocity_vs_R']=paired(methods['Velocity'],methods['R'])
    atomic_json(ROOT/'PAIRED_COMPARISONS.json',pairs)
    with (ROOT/'FINAL_EPISODES.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(final_rows[0]));writer.writeheader();writer.writerows(final_rows)
    attempts=read(ROOT/'ATTEMPT_COUNTER.json')['reserved_attempts'] if (ROOT/'ATTEMPT_COUNTER.json').exists() else 0
    assert attempts<=4000 and fits['updates']<=32000
    external=[]
    for p in (ROOT/'stages').glob('*/workers/*/encoder/RESULT.json'):external.append(dict(path=str(p),**read(p)))
    result=dict(task_id=TASK,utc=utc(),status='complete' if sum(g['valid'] for g in groups)==1500 and fits['updates']==32000 and len(collection)==250 else 'partial_or_scientific_gap',
        base='X-VLA030000',collection_parents_complete=len(collection),collection_real_rollouts=len(collection_rows),evaluation_valid=sum(g['valid'] for g in groups),
        attempts=attempts,cumulative_C_attempts=7013+attempts,stage_attempt_cap=4000,cumulative_cap=11900,fit_updates=fits['updates'],
        N_reused=dict(valid=500,successes=403,new_rollouts=0),groups=groups,
        frozen_head_transfer={m:dict(valid=len(v),successes=sum(r['success'] for r in v.values()),heads='frozen pi05 historical heads') for m,v in frozen.items()},
        data_summary=str(ROOT/'DATA_SUMMARY.json'),fit_summary=str(ROOT/'FIT_SUMMARY.json'),
        external_feature_costs=external,base_training_updates=0,external_encoder_training_updates=0,old_completed_replays=0,
        interpretation='Complete X-specific adaptation package including fresh-C10 G0 target; revealed500 supplementary adaptation evaluation, not unseen validation',
        environment='same E8 Mesa llvmpipe, 80Hz/.01, H30 K10 NFE10, actual observed agent_pos and RGB',
        Post_metric='inherited pi05 clean-coordinate scale; Velocity keeps native X inverse normalization and clean-head bridge',
        occupancy='all holders off throughout formal wave; restore after whole family exit; sampled utilization is not continuous guarantee',
        cost_note='RPC time overlaps native guided inference. Sum episode times is not wall throughput; external frozen encoder footprint included separately.')
    atomic_json(ROOT/'FINAL_SUMMARY.json',result)
    lines=['X-VLA specific auxiliary adaptation','',result['interpretation']+'.','',
        '| Arm | Success / valid | Technical | Unstarted |','|---|---:|---:|---:|','| N (reused) | 403 / 500 | 0 | 0 |']
    for g in groups:lines.append(f"| {g['method']} | {g['successes'] if g['successes'] is not None else '—'} / {g['valid']} | {g['technical']} | {g['unstarted']} |")
    lines+=['',f"Collection parents: {len(collection)}/250; rollouts: {len(collection_rows)}; total new attempts: {attempts}/4000; optimizer updates: {fits['updates']}/32000.",
        '',result['Post_metric']+'.', '',result['occupancy']+'. '+result['cost_note'],
        '', 'Missing, truncated and technical rows stay unknown. G0 all-constant targets or absent Q supervision block the affected evaluations. Fixed step4000 only; no test-based selection.']
    (ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:result[k] for k in ['status','attempts','fit_updates','evaluation_valid','collection_parents_complete']}))

if __name__=='__main__':main()
