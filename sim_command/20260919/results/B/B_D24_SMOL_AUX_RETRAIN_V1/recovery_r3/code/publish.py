"""Merge only actual valid predecessor results; retain all physical failures."""
import csv
import io
import json
from collections import Counter
from pathlib import Path
import numpy as np
import paths
from paths import ROOT,ARTIFACTS,CAMPAIGN,CONFIG
from qio import read,atomic_json,utc,ref

def csv_write(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row));stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields)
    writer.writeheader();writer.writerows({k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in rows)
    temp=path.with_suffix('.csv.tmp');temp.write_text(stream.getvalue());temp.replace(path)

def totals(rows,key):
    result=Counter()
    for row in rows:result.update(row.get(key,{}))
    return dict(result)

def contrast(current,other,sources,label,complete):
    ids=sorted(set(current)&set(other));wins=sum(current[s]['success'] and not other[s]['success'] for s in ids)
    losses=sum(other[s]['success'] and not current[s]['success'] for s in ids);ci=None
    if complete and ids:
        rng=np.random.default_rng(20260922);draws=np.zeros(2000)
        for task in sorted({sources[s]['task'] for s in ids}):
            delta=np.asarray([int(current[s]['success'])-int(other[s]['success']) for s in ids if sources[s]['task']==task])
            draws+=delta[rng.integers(0,len(delta),size=(2000,len(delta)))].sum(1)
        ci=(np.quantile(draws/len(ids),[.025,.975])*100).tolist()
    return dict(contrast=label,paired_valid=len(ids),rescued=wins,harmed=losses,
        new_successes=sum(current[s]['success'] for s in ids),reference_successes=sum(other[s]['success'] for s in ids),
        difference_pp=100*(wins-losses)/len(ids) if ids else None,pointwise95_CI_pp=ci,
        bootstrap='fixed tasks; resample common valid sources within task;2000 draws seed20260922',
        no_trigger_conditioning=True,missing_not_failure=True,independent_fit_groups=1,descriptive=True)

def publish():
    index=read(ROOT/'SOURCE_INDEX.json');sources=read(index['full_sources']['path'])['sources'];source_map={s['source_id']:s for s in sources}
    retained={(x['method'],x['source_id']):x['result']['path'] for x in index.get('retained',[])}
    historical=[read(x['previous_result']['path']) for x in index.get('known_interrupted',[])]
    claims=[read(p) for p in (ROOT/'claims/attempts').glob('*.json')]
    current_attempts=read(ROOT/'ATTEMPT_COUNTER.json')['reserved_attempts'] if (ROOT/'ATTEMPT_COUNTER.json').exists() else 0
    attempts=CONFIG.get('carried_stage_attempts',0)+current_attempts
    assert current_attempts<=CONFIG['stage_attempt_cap'] and attempts<=CONFIG['original_stage_attempt_cap']
    assert CONFIG['planned_prior_attempts']+current_attempts<=CONFIG['node_cumulative_attempt_cap']
    N=read(CAMPAIGN/'work/B/B_D24_E8_POST_V1_r1/VALID_N_INDEX.json')['smolvla'];N={x['source_id']:x for x in N if x['status']=='complete'}
    cells=[];episodes=[];missing=[];paired=[];costs=[];valid_sets={}
    for method in ['R','Post','Velocity']:
        rows={sid:dict(read(path),result_path=path,retained_from_prior=True) for (m,sid),path in retained.items() if m==method}
        for p in sorted((ROOT/'evaluation'/method).glob('*/RESULT.json')):
            row=read(p);sid=row['source_id'];assert sid not in rows,'completed prior unit replayed'
            rows[sid]=dict(row,result_path=str(p),retained_from_prior=False)
        for sid,row in rows.items():
            assert all(row[k]==source_map[sid][k] for k in ['task','reset_seed','policy_seed'])
            if row['status']=='complete':
                assert type(row['success']) is bool
                cuts=[e['step'] for e in row['events'] if e['trigger']]
                assert len(cuts)==row['interventions'] and all(b-a>=10 for a,b in zip(cuts,cuts[1:]))
                assert row['first_cut']==(cuts[0] if cuts else None)
                if CONFIG['mode']=='once':assert len(cuts)<=1
            else:assert row['success'] is None
            episodes.append(dict({k:v for k,v in row.items() if k!='events'},absolute_cut_sequence=[e['step'] for e in row['events'] if e['trigger']],mode=CONFIG['mode']))
        valid={sid:x for sid,x in rows.items() if x['status']=='complete'};valid_sets[method]=valid
        claimed={x['source_id'] for x in claims if x.get('method')==method}|{sid for m,sid in retained if m==method}
        technical=sum(x['status']=='technical_failure' for x in rows.values());truncated=sum(x['status']=='budget_truncated' for x in rows.values())
        unknown=claimed-set(rows);successes=sum(x['success'] for x in valid.values());n=len(valid)
        intervention_values=np.asarray([x['interventions'] for x in valid.values()])
        cell=dict(method=method,mode=CONFIG['mode'],planned=500,valid=n,successes=successes,success_rate=successes/n if n else None,
            technical=technical,budget_truncated=truncated,execution_unknown=len(unknown),unstarted=500-len(claimed),
            trigger_zero=int((intervention_values==0).sum()),trigger_once=int((intervention_values==1).sum()),trigger_multiple=int((intervention_values>1).sum()),
            intervention_count=int(intervention_values.sum()),interventions_mean=float(intervention_values.mean()) if n else None,
            interventions_max=int(intervention_values.max()) if n else None,valid_policy_environment_counters=totals(valid.values(),'counters'),
            valid_encoder_auxiliary_counters=totals(valid.values(),'encoder_counters'))
        cells.append(cell)
        for sid in sorted(set(source_map)-set(valid)):missing.append(dict(method=method,source_id=sid,status=rows[sid]['status'] if sid in rows else 'execution_unknown' if sid in claimed else 'unstarted'))
        actual=Counter(cell['valid_policy_environment_counters']);actual.update(cell['valid_encoder_auxiliary_counters'])
        faults=[x for x in rows.values() if x['status']!='complete']+[x for x in historical if x['method']==method]
        costs.append(dict(method=method,valid_episode_costs=dict(actual),per_valid_episode={k:v/n if n else None for k,v in actual.items()},
            per_success={k:v/successes if successes else None for k,v in actual.items()},
            technical_or_truncated_physical_costs=dict(policy_environment=totals(faults,'counters'),encoder_auxiliary=totals(faults,'encoder_counters'))))
        paired.append(contrast(valid,N,source_map,method+' '+CONFIG['mode']+' - N',n==500))
    if CONFIG['mode']=='multi':
        once_rows=read(Path(CONFIG['predecessor_root'])/'VALID_RESULT_INDEX.json')['rows']
        for method in ['R','Post','Velocity']:
            baseline={x['source_id']:read(x['result']['path']) for x in once_rows if x['method']==method}
            paired.append(contrast(valid_sets[method],baseline,source_map,method+' multi - same-head once',len(valid_sets[method])==500))
    fitted=read(ARTIFACTS/'FIT_SUMMARY.json');complete=all(x['valid']==500 for x in cells)
    report=dict(task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],mode=CONFIG['mode'],status='complete' if complete else 'partial',at_utc=utc(),
        attempts=attempts,current_run_attempts=current_attempts,carried_stage_attempts=CONFIG.get('carried_stage_attempts',0),attempt_cap=CONFIG['original_stage_attempt_cap'],
        cumulative_B_attempts=CONFIG['planned_prior_attempts']+current_attempts,cumulative_B_cap=20000,
        collection_attempts=read(ARTIFACTS/'FINAL_SUMMARY.json')['collection_attempts'] if CONFIG['mode']=='once' else 0,
        optimizer_updates=fitted['total_updates'] if CONFIG['mode']=='once' else 0,new_optimizer_updates=0,new_collection_attempts=0,
        fixed_reused_heads=ref(ARTIFACTS/'FIT_SUMMARY.json'),data_summary=ref(ARTIFACTS/'DATA_SUMMARY.json'),
        cells=cells,N_reused=dict(valid=len(N),successes=sum(x['success'] for x in N.values()),unknown=500-len(N)),
        historical_interrupted_attempts=len(historical),historical_interrupted_status_counts=dict(Counter(x['status'] for x in historical)),
        historical_attempts_preserved=True,scientific_gaps=fitted['scientific_gaps'],all_owned_descendants_exited_before_publication=True,
        A_waits_for_B=False,interpretation='same fixed Smol auxiliary heads; revealed-source supplementary adaptation; local gain repeated in multi is not a calibrated global value',
        baseline_N_rerun=False,external_encoder_cost_separately_reported=True)
    atomic_json(ROOT/'FINAL_SUMMARY.json',report);atomic_json(ROOT/'FINAL_MISSING.json',missing);atomic_json(ROOT/'PAIRED.json',paired)
    atomic_json(ROOT/'PAIRED_COMPARISONS.json',paired)
    valid_index=[dict(method=method,source_id=sid,result=ref(row['result_path'])) for method,rows in valid_sets.items() for sid,row in rows.items()]
    atomic_json(ROOT/'VALID_RESULT_INDEX.json',dict(mode=CONFIG['mode'],rows=valid_index,complete=complete,at_utc=utc()))
    costs_root=[ROOT]+([ARTIFACTS] if CONFIG['mode']=='once' else [])
    external=[read(p) for root in costs_root for p in sorted((root/'runs').glob('*/encoder/RESULT.json'))]
    native=[read(p) for root in costs_root for p in sorted((root/'runs').glob('*/CLIENT_RESULT.json'))]
    atomic_json(ROOT/'RESOURCE_SUMMARY.json',dict(costs=costs,external_encoder_processes=external,native_processes=native,
        fixed_heads=ref(ARTIFACTS/'FIT_SUMMARY.json'),training_updates_this_run=0,occupancy_cost_excluded=True,
        prior_startup_failure_root=CONFIG.get('prior_startup_failure_root'),startup_failures_separate_from_scientific_attempts=True,
        parameters_include_entire_loaded_external_model=True,episode_wall_sums_not_node_wall_time=True))
    csv_write(ROOT/'FINAL_EPISODES.csv',episodes);csv_write(ROOT/'FINAL_CELLS.csv',cells);csv_write(ROOT/'PAIRED.csv',paired)
    lines=['Smol '+CONFIG['mode']+' evaluation: '+report['status'],'',
        '| Method | Success/valid | Technical | Unknown | Unstarted |','|---|---:|---:|---:|---:|']
    lines+=['| '+x['method']+' | '+str(x['successes'])+'/'+str(x['valid'])+' | '+str(x['technical'])+' | '+str(x['execution_unknown'])+' | '+str(x['unstarted'])+' |' for x in cells]
    lines+=['','Old N and frozen-head transfer results are retained. Missing outcomes are excluded. Same-head once and multi remain separate. External encoder costs and technical work are reported separately. Only analysis updates the shared master.']
    (ROOT/'MASTER_UPDATE.md').write_text('\n'.join(lines)+'\n')
    (ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    atomic_json(CAMPAIGN/CONFIG['result_receipt'],dict(report,result_root=str(ROOT),final_summary=ref(ROOT/'FINAL_SUMMARY.json')))
    if CONFIG['mode']=='once':atomic_json(ARTIFACTS/'LATEST_RESULT.json',dict(run_id=CONFIG['run_id'],result_root=str(ROOT),summary=ref(ROOT/'FINAL_SUMMARY.json'),at_utc=utc()))
    print(json.dumps(dict(status=report['status'],mode=CONFIG['mode'],current_run_attempts=current_attempts,cumulative_B_attempts=report['cumulative_B_attempts'],valid=sum(x['valid'] for x in cells))))

if __name__=='__main__':publish()
