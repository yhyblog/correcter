"""Export actual current L11 outcomes/costs without changing old L01 results."""
import csv
import hashlib
import io
import json
from collections import Counter
import paths
from paths import ROOT,CONFIG,CAMPAIGN
from qio import read,atomic_json,utc,ref

def write_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r));stream=io.StringIO();w=csv.DictWriter(stream,fieldnames=fields or ['unit_id','status']);w.writeheader()
    w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)
    temp=path.with_suffix('.tmp');temp.write_text(stream.getvalue());temp.replace(path)

def main():
    units=read(ROOT/'SOURCE_INDEX.json')['units'];rows=[];missing=[];cells=[]
    for u in units:
        ep=ROOT/'episodes'/hashlib.sha256(u['unit_id'].encode()).hexdigest();p=ep/'SUMMARY_ROW.json'
        if p.exists():
            r=read(p)
            if r['unit_id']!=u['unit_id']:raise ValueError('result identity mismatch')
            for k in ['source_id','method','policy_seed','task']:assert r[k]==u[k]
            assert r.get('env_seed',r.get('reset_seed'))==u['env_seed']
            if r['status']=='complete':assert isinstance(r['success'],bool)
            else:assert r['success'] is None
            row={**u,**r}
            row.update(result_path=str(ep/'RESULT.json'),summary_path=str(p),current_paper=u['current_paper']);rows.append(row)
            if r['status']!='complete':missing.append(dict(unit_id=u['unit_id'],status=r['status'],success=None,result_path=str(ep/'RESULT.json')))
        else:
            status='execution_unknown' if (ep/'ENTERED.json').exists() else 'unstarted'
            missing.append(dict(unit_id=u['unit_id'],status=status,success=None))
    for key in sorted({(u['model'],u['method'],u['H']) for u in units}):
        actual=[r for r in rows if (r['model'],r['method'],r['H'])==key];valid=[r for r in actual if r['status']=='complete'];success=sum(r['success'] for r in valid);costs={}
        for field in ['counters','numeric_counters','encoder_counters']:
            total=Counter()
            for r in actual:total.update(r.get(field,{}))
            costs[field]=dict(total)
        cells.append(dict(model=key[0],method=key[1],H=key[2],loss='L11',fit_seed=9101,planned=500,valid=len(valid),successes=success,success_rate=success/len(valid) if valid else None,missing=500-len(valid),current_paper=key[1]=='Post',actual_costs=costs,sum_episode_wall_seconds=sum(r.get('elapsed_seconds',0) for r in actual),wall_sum_is_not_GPU_hours=True))
    attempts=read(ROOT/'ATTEMPT_COUNTER.json')['reserved_attempts'] if (ROOT/'ATTEMPT_COUNTER.json').exists() else 0
    summary=dict(task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],status='complete' if not missing else 'partial',utc=utc(),planned=len(units),attempts=attempts,valid=sum(c['valid'] for c in cells),missing=len(missing),cells=cells,selected_loss='L11',fit_seed=9101,new_training_updates=0,new_collection=0,cumulative_B_attempts=CONFIG['planned_prior_attempts']+attempts,attempt_cap=CONFIG['stage_attempt_cap'],node_cap=CONFIG['node_cumulative_attempt_cap'],missing_not_failure=True,old_L01_results_preserved=True,revealed_source_retest=True,independent_new_blind_test=False,occupancy_cost_excluded=True,concurrency=[{**read(p),'phase':p.parent.name} for p in (ROOT/'phases').glob('*/CONCURRENCY.json')])
    prior=read(ROOT/'PRIOR_ATTEMPTS.json')['units'];by_key={r['unit_id']:r for r in rows};chains=[]
    prior_costs=Counter()
    for item in prior:
        chain=dict(item);r=by_key.get(item['scientific_key'])
        for previous in item['prior_attempts']:
            raw=previous['raw_row']
            for field in ['sampling_calls','flow_calls','elapsed_seconds']:
                if raw.get(field):prior_costs[field]+=float(raw[field])
        chain['recovery_attempt']=dict(attempt_ordinal=2,owner='B',run_id=CONFIG['run_id'],
            status=r['status'] if r else 'unstarted_or_execution_unknown',
            scientific_valid=bool(r and r['status']=='complete'),
            raw_result_path=r['result_path'] if r else None,
            summary_path=r['summary_path'] if r else None,
            success=r['success'] if r else None,
            actual_costs={k:r.get(k) for k in ['counters','numeric_counters','sampling_calls','flow_calls','elapsed_seconds']} if r else None)
        chains.append(chain)
    atomic_json(ROOT/'ATTEMPT_LINEAGE.json',dict(scientific_units=chains,prior_raw_results_unchanged=True))
    summary.update(attempt_lineage=ref(ROOT/'ATTEMPT_LINEAGE.json'),prior_A_quality_held_attempts=len(prior),
        prior_A_raw_costs=dict(prior_costs),prior_A_costs_excluded_from_B_new_costs=True,
        engineering_repair=ref(ROOT/'REPAIR.json'),
        observation_evidence=[str(p) for p in (ROOT/'episodes').glob('*/observation_evidence/frame_step_*.json')])
    atomic_json(ROOT/'FINAL_SUMMARY.json',summary);atomic_json(ROOT/'FINAL_MISSING.json',missing)
    write_csv(ROOT/'FINAL_EPISODES.csv',rows);write_csv(ROOT/'FINAL_CELLS.csv',cells);write_csv(ROOT/'FINAL_MISSING.csv',missing)
    write_csv(ROOT/'VALID_EPISODES.csv',[r for r in rows if r['status']=='complete'])
    write_csv(ROOT/'POST_PAPER.csv',[r for r in rows if r['method']=='Post' and r['status']=='complete']);write_csv(ROOT/'VELOCITY_OTHER_WORK.csv',[r for r in rows if r['method']=='Velocity' and r['status']=='complete'])
    atomic_json(CAMPAIGN/CONFIG['result_receipt'],dict(summary,root=str(ROOT),final_summary=ref(ROOT/'FINAL_SUMMARY.json'),cleanup=ref(ROOT/'chain/CHAIN_RESULT.json'),A_waits_for_B=False))
    (ROOT/'REPORT.md').write_text('# B L11 H30 rendering-path recovery\n\nStatus: '+summary['status']+'; valid '+str(summary['valid'])+'/'+str(len(units))+'; missing '+str(summary['missing'])+'.\n\nFixed L11/fit9101 and all original scientific keys/seeds. Independent physical environment processes share only model RPC. The previous A quality-held attempts and their raw costs remain in ATTEMPT_LINEAGE.json. Completed B 2500 units were excluded. Post and Velocity export separately; missing outcomes are not scientific failures. See REPAIR.json and bounded actual RGB attribution. Actual concurrent branch timing and summed episode wall seconds are not GPU hours.\n')
    print(json.dumps({k:summary[k] for k in ['status','valid','missing','attempts']}))

if __name__=='__main__':main()
