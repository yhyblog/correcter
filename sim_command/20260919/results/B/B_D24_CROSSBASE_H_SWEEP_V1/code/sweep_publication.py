"""Publish all fixed sweep cells, preserving technical missingness and raw costs."""
import csv
import hashlib
import io
import json
from collections import Counter
import paths
from paths import ROOT, CONFIG, CAMPAIGN
from qio import read, atomic_json, ref, utc


def write_csv(path, rows):
    fields=list(dict.fromkeys(k for row in rows for k in row)) or ['unit_id','status']
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
    writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)
    temp=path.with_suffix('.tmp');temp.write_text(stream.getvalue());temp.replace(path)


def summarize(units, rows):
    cells=[]
    for method in CONFIG['methods']:
        for horizon in CONFIG['horizons']:
            planned=[u for u in units if u['method']==method and u['H']==horizon]
            observed=[r for r in rows if r['method']==method and r['H']==horizon]
            valid=[r for r in observed if r['status']=='complete']
            totals={}
            for field in ['counters','encoder_counters']:
                counts=Counter()
                for row in observed:counts.update(row.get(field,{}))
                totals[field]=dict(counts)
            successes=sum(r['success'] for r in valid)
            cells.append(dict(model='SmolVLA',method=method,H=horizon,raw_plan_length=50,
                commitment_C=None if method=='N' else 10,mode='native' if method=='N' else 'G0-multi',
                Q_loss='L11' if method in ('Post','Velocity') else None,
                Q_fit_seed=9101 if method in ('Post','Velocity') else None,
                planned=len(planned),valid=len(valid),successes=successes,
                success_rate=successes/len(valid) if valid else None,missing=len(planned)-len(valid),
                paper_role='Post_primary' if method=='Post' else 'baseline' if method in ('N','R') else 'other_work',
                actual_costs=totals,interventions=sum(r.get('interventions',0) for r in observed),
                sum_episode_wall_seconds=sum(r.get('elapsed_seconds',0) for r in observed),
                wall_sum_is_not_GPU_hours=True))
    return cells


def main():
    units=read(ROOT/'SOURCE_INDEX.json')['units'];rows=[];missing=[]
    for unit in units:
        ep=ROOT/'episodes'/hashlib.sha256(unit['unit_id'].encode()).hexdigest();path=ep/'SUMMARY_ROW.json'
        if not path.exists():
            missing.append(dict(unit_id=unit['unit_id'],method=unit['method'],H=unit['H'],source_id=unit['source_id'],
                status='execution_unknown' if (ep/'ENTERED.json').exists() else 'unstarted',success=None))
            continue
        result=read(path)
        for field in ['unit_id','source_id','method','H','mode','env_seed','policy_seed','Q_loss','Q_fit_seed']:
            if result[field]!=unit[field]:raise ValueError('publication identity mismatch '+field)
        if result['status']=='complete':
            if not isinstance(result['success'],bool):raise ValueError('terminal success must be boolean')
        elif result['success'] is not None:raise ValueError('technical outcome is not scientific failure')
        row={**unit,**result,'result_path':str(ep/'RESULT.json'),'summary_path':str(path)};rows.append(row)
        if row['status']!='complete':missing.append({k:row.get(k) for k in ['unit_id','source_id','method','H','status','success','error','result_path']})
        if row['method']=='N' and (row['interventions'] or row.get('encoder_counters') or row.get('counters',{}).get('candidate_queries')):
            raise ValueError('N used auxiliary scientific path')
        if row['method']=='R' and any(row.get('encoder_counters',{}).get(k) for k in ['Q_ensemble_forward_calls','Q_member_forward_calls','action_gradient_calls']):
            raise ValueError('R called Q/gradient')
    if len({r['unit_id'] for r in rows})!=len(rows):raise ValueError('duplicate scientific output')
    cells=summarize(units,rows);attempts=read(ROOT/'ATTEMPT_COUNTER.json')['reserved_attempts'] if (ROOT/'ATTEMPT_COUNTER.json').exists() else 0
    summary=dict(task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],utc=utc(),status='complete' if not missing else 'partial',
        planned=len(units),valid=sum(c['valid'] for c in cells),missing=len(missing),attempts=attempts,
        cumulative_B_attempts=CONFIG['planned_prior_attempts']+attempts,attempt_cap=CONFIG['stage_attempt_cap'],node_cap=CONFIG['node_cumulative_attempt_cap'],
        cells=cells,selected_loss='L11',fit_seed=9101,new_training_updates=0,new_collection=0,
        H10_reused_not_rerun=True,H10_reuse_policy=ref(ROOT/'H10_REUSE_POLICY.json'),
        missing_not_failure=True,revealed_sources=True,test_based_selection=False,
        normal_H_separate_from_C10=True,N_no_monitor_or_Q=True,R_no_Q_or_action_gradient=True,
        occupancy_cost_excluded=True,external_encoder_costs_separately_recorded=True,
        phase_results=read(ROOT/'PHASE_RESULTS.json') if (ROOT/'PHASE_RESULTS.json').exists() else [],
        concurrency=[{**read(p),'phase':p.parent.name} for p in (ROOT/'phases').glob('*/CONCURRENCY.json')],
        model_readiness=[ref(p) for p in (ROOT/'phases').glob('*/*/MODEL_READY.json') if p.parent.name.startswith(('model_','encoder_'))],
        missing_file=str(ROOT/'FINAL_MISSING.json'),repair=ref(ROOT/'METHOD_FROZEN.json'))
    atomic_json(ROOT/'FINAL_SUMMARY.json',summary);atomic_json(ROOT/'FINAL_MISSING.json',missing)
    write_csv(ROOT/'FINAL_EPISODES.csv',rows);write_csv(ROOT/'FINAL_CELLS.csv',cells);write_csv(ROOT/'FINAL_MISSING.csv',missing)
    valid=[r for r in rows if r['status']=='complete'];write_csv(ROOT/'VALID_EPISODES.csv',valid)
    write_csv(ROOT/'POST_PAPER.csv',[r for r in valid if r['method']=='Post'])
    write_csv(ROOT/'BASELINES.csv',[r for r in valid if r['method'] in ('N','R')])
    write_csv(ROOT/'VELOCITY_OTHER_WORK.csv',[r for r in valid if r['method']=='Velocity'])
    atomic_json(CAMPAIGN/CONFIG['result_receipt'],dict(summary,root=str(ROOT),final_summary=ref(ROOT/'FINAL_SUMMARY.json'),cleanup=ref(ROOT/'chain/CHAIN_RESULT.json'),A_waits_for_B=False))
    lines=['# B SmolVLA H40/H50 sweep','',f"Status: {summary['status']}; valid {summary['valid']}/{len(units)}; missing {len(missing)}.",'',
        'Normal H changes; raw50, C10, Mesa/80Hz/.01, source seeds, native sampling/candidate stream, per-base D/G0/L11 Q remain fixed. No H10 rerun, training or collection.',
        'N has no monitoring/correction. R uses G0 and C10 with no Q or action gradient. Post is primary; Velocity is for other work. No test-based selection.',
        'Each cell uses only actual valid terminals as denominator. Unstarted/unknown/technical outcomes remain missing. Compare H on intersected valid original sources.',
        'Actual branch snapshots and episode wall-time sums are not continuous utilization guarantees or GPU hours. See raw counters, phase files and cleanup/occupancy records.','']
    lines.extend(f"- {c['method']} H{c['H']}: {c['successes']}/{c['valid']} valid; missing {c['missing']}." for c in cells)
    (ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:summary[k] for k in ['status','valid','missing','attempts']}))


if __name__=='__main__':main()
