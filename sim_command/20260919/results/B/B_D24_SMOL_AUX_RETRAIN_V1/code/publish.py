"""Publish only saved actual rows; unknown/technical/unstarted remain missing."""
import csv
import io
import json
from collections import Counter
from pathlib import Path
import numpy as np
import paths
from paths import ROOT,CAMPAIGN
from qio import read,atomic_json,utc,ref

def csv_write(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row));stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields)
    writer.writeheader();writer.writerows({k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in rows)
    temp=path.with_suffix('.csv.tmp');temp.write_text(stream.getvalue());temp.replace(path)

def publish():
    cfg=read(ROOT/'config/CONFIG.json');sources=read(CAMPAIGN/'work/B/B_D24_E8_POST_V1_r1/POST_SOURCES.json')['sources']
    source_index={s['source_id']:s for s in sources};baseline=read(CAMPAIGN/'work/B/B_D24_E8_POST_V1_r1/VALID_N_INDEX.json')['smolvla']
    old={r['source_id']:r for r in baseline if r['status']=='complete'}
    data=read(ROOT/'DATA_SUMMARY.json') if (ROOT/'DATA_SUMMARY.json').exists() else None
    fit=read(ROOT/'FIT_SUMMARY.json') if (ROOT/'FIT_SUMMARY.json').exists() else None
    claims=[read(p) for p in (ROOT/'claims/attempts').glob('*.json')];by_claim={x['identity']:x for x in claims}
    recorded=read(ROOT/'ATTEMPT_COUNTER.json')['reserved_attempts'] if (ROOT/'ATTEMPT_COUNTER.json').exists() else 0
    assert recorded<=4000 and cfg['planned_prior_attempts']+recorded<=20000
    collection_rows=[read(p) for p in (ROOT/'collection').glob('*/*/RESULT.json')]
    collection_initialization_failures=[read(p) for p in (ROOT/'collection').glob('*/INITIALIZATION_FAILURE.json')]
    collection_status=Counter(r['status'] for r in collection_rows)
    cells=[];paired=[];episodes=[];missing=[];costs=[]
    for method in ['R','Post','Velocity']:
        rows={}
        for p in sorted((ROOT/'evaluation'/method).glob('*/RESULT.json')):
            r=read(p);sid=r['source_id'];assert sid not in rows
            assert all(r[k]==source_index[sid][k] for k in ['task','reset_seed','policy_seed'])
            if r['status']=='complete':assert type(r['success']) is bool and r['interventions'] in [0,1]
            else:assert r['success'] is None
            rows[sid]=r
            flat={k:v for k,v in r.items() if k!='events'};flat['result_path']=str(p);episodes.append(flat)
        claimed={x['source_id'] for x in claims if x.get('phase')=='evaluate' and x.get('method')==method}
        valid={sid:r for sid,r in rows.items() if r['status']=='complete'};technical={sid for sid,r in rows.items() if r['status']=='technical_failure'}
        unknown=claimed-set(rows);truncated={sid for sid,r in rows.items() if r['status']=='budget_truncated'}
        cnt=Counter();enc=Counter()
        for row in rows.values():cnt.update(row.get('counters',{}));enc.update(row.get('encoder_counters',{}))
        successes=sum(r['success'] for r in valid.values())
        cell=dict(method=method,planned=500,valid=len(valid),successes=successes,technical=len(technical),execution_unknown=len(unknown),
            budget_truncated=len(truncated),unstarted=500-len(claimed),success_rate=successes/len(valid) if valid else None,
            trigger_zero=sum(r['interventions']==0 for r in valid.values()),trigger_once=sum(r['interventions']==1 for r in valid.values()),
            policy_and_environment_counters=dict(cnt),external_encoder_and_auxiliary_counters=dict(enc))
        cells.append(cell);costs.append(dict(method=method,measured_costs_per_success={k:v/successes if successes else None for k,v in dict(cnt+enc).items()}))
        for sid in sorted(set(source_index)-set(valid)):
            missing.append(dict(method=method,source_id=sid,status=rows[sid]['status'] if sid in rows else 'execution_unknown' if sid in claimed else 'unstarted'))
        ids=sorted(set(valid)&set(old));wins=sum(valid[s]['success'] and not old[s]['success'] for s in ids);losses=sum(old[s]['success'] and not valid[s]['success'] for s in ids)
        ci=None
        if len(valid)==500 and ids:
            rng=np.random.default_rng(20260922);draws=np.zeros(2000)
            for task in sorted({source_index[s]['task'] for s in ids}):
                diff=np.asarray([int(valid[s]['success'])-int(old[s]['success']) for s in ids if source_index[s]['task']==task])
                draws+=diff[rng.integers(0,len(diff),size=(2000,len(diff)))].sum(1)
            ci=(np.quantile(draws/len(ids),[.025,.975])*100).tolist()
        paired.append(dict(contrast=method+' - N',paired_valid=len(ids),rescued=wins,harmed=losses,
            new_successes=sum(valid[s]['success'] for s in ids),N_successes=sum(old[s]['success'] for s in ids),
            difference_pp=100*(wins-losses)/len(ids) if ids else None,pointwise95_CI_pp=ci,
            bootstrap='fixed tasks, resample common valid sources within task;2000 draws',seed=20260922,
            denominator='all common valid; no trigger conditioning; four historical N unknown remain absent',
            interpretation='complete base-specific adaptation package on previously revealed sources; single8-member seed group; no significance claim'))
    fits=[read(p) for p in (ROOT/'fits').glob('*/RESULT.json')];updates=sum(x['updates'] for x in fits)
    reserved_updates=sum(read(p)['reserved_update_cap'] for p in (ROOT/'claims/fits').glob('*.json'))
    assert updates<=reserved_updates<=32000
    external=[read(p) for p in sorted((ROOT/'runs').glob('*/encoder/RESULT.json'))]
    native=[read(p) for p in sorted((ROOT/'runs').glob('*/CLIENT_RESULT.json'))]
    all_complete=bool(fit and fit['status']=='complete' and all(c['valid']==500 for c in cells))
    report=dict(task_id=cfg['task_id'],run_id=cfg['run_id'],status='complete' if all_complete else 'scientific_gap' if fit and fit['scientific_gaps'] else 'partial',
        at_utc=utc(),attempts=recorded,attempt_cap=4000,prior_B_attempts=cfg['planned_prior_attempts'],cumulative_B_attempts=cfg['planned_prior_attempts']+recorded,
        cumulative_B_cap=20000,collection_attempts=sum(x.get('phase')=='collect' for x in claims),evaluation_attempts=sum(x.get('phase')=='evaluate' for x in claims),
        collection_status_counts=dict(collection_status),collection_initialization_failures=collection_initialization_failures,
        optimizer_updates=updates,reserved_update_cap=reserved_updates,base_updates=0,external_encoder_updates=0,
        data_summary=str(ROOT/'DATA_SUMMARY.json') if data else None,fit_summary=str(ROOT/'FIT_SUMMARY.json') if fit else None,
        cells=cells,N_reused=dict(valid=len(old),successes=sum(x['success'] for x in old.values()),unknown=500-len(old)),
        paired_comparisons=str(ROOT/'PAIRED_COMPARISONS.json'),scientific_gaps=fit['scientific_gaps'] if fit else [],
        runtime_scope='frozen Smol050000, external pi05 encoder, new Smol D/G0/Q; Mesa80Hz/.01/K10; supplementary revealed-source adaptation',
        external_encoder_parameters_and_memory_separately_reported=True,suffix_repeats_not_independent_parents=True,
        normal_only_or_technical_not_failure_labels=True,holders='alloff throughout formal family,restoreafterexit',A_waits_for_B=False)
    atomic_json(ROOT/'FINAL_SUMMARY.json',report);atomic_json(ROOT/'FINAL_MISSING.json',missing);atomic_json(ROOT/'PAIRED_COMPARISONS.json',paired)
    atomic_json(ROOT/'RESOURCE_SUMMARY.json',dict(external_encoder_processes=external,native_processes=native,costs_per_success=costs,
        episode_wall_sums_not_node_wall_time=True,occupancy_cost_excluded=True))
    csv_write(ROOT/'FINAL_EPISODES.csv',episodes);csv_write(ROOT/'FINAL_CELLS.csv',cells);csv_write(ROOT/'PAIRED_COMPARISONS.csv',paired)
    old_summary=CAMPAIGN/'results/B/B_D24_EXTENSION_REMAINDER_V1/r1/D24_E8_MW_POST_r1/N_POST_SUMMARY.json'
    atomic_json(ROOT/'FROZEN_HEAD_TRANSFER_REFERENCE.json',dict(label='frozen pi05 auxiliary heads directly transferred to Smol, historical retained',
        Post_summary=ref(old_summary),Post=[x for x in read(old_summary)['groups'] if x['model']=='smolvla'],
        Velocity_owner='C',Velocity_summary=ref(CAMPAIGN/'results/C/C_D24_MW_VELOCITY_V1/D24_C_MW_VELOCITY_r2/smolvla_SUMMARY.json'),overwrites_old_results=False))
    lines=['SmolVLA-specific auxiliary adaptation: '+report['status'],'',
        '| Method | Success / valid | Technical / unknown / unstarted |','|---|---:|---:|']
    lines+=['| '+c['method']+' | '+str(c['successes'])+'/'+str(c['valid'])+' | '+str(c['technical'])+'/'+str(c['execution_unknown'])+'/'+str(c['unstarted'])+' |' for c in cells]
    lines+=['','Old N is reused, not rerun. Missing outcomes are excluded. This is a complete adaptation package on previously revealed test sources, not a new unseen validation. External encoder parameters, memory and calls are separate in RESOURCE_SUMMARY.']
    (ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    atomic_json(CAMPAIGN/'receipts/B/B_D24_SMOL_AUX_RETRAIN_V1_RESULT_r1.json',dict(report,result_root=str(ROOT)))
    return report

if __name__=='__main__':print(json.dumps(publish()))
