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
    summary=dict(task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],status='complete' if not missing else 'partial',utc=utc(),attempts=attempts,valid=sum(c['valid'] for c in cells),missing=len(missing),cells=cells,selected_loss='L11',fit_seed=9101,new_training_updates=0,new_collection=0,cumulative_B_attempts=CONFIG['planned_prior_attempts']+attempts,attempt_cap=2750,node_cap=24750,missing_not_failure=True,old_L01_results_preserved=True,revealed_source_retest=True,independent_new_blind_test=False,occupancy_cost_excluded=True,concurrency=[{**read(p),'phase':p.parent.name} for p in (ROOT/'phases').glob('*/CONCURRENCY.json')])
    atomic_json(ROOT/'FINAL_SUMMARY.json',summary);atomic_json(ROOT/'FINAL_MISSING.json',missing)
    write_csv(ROOT/'FINAL_EPISODES.csv',rows);write_csv(ROOT/'FINAL_CELLS.csv',cells);write_csv(ROOT/'FINAL_MISSING.csv',missing)
    write_csv(ROOT/'POST_PAPER.csv',[r for r in rows if r['method']=='Post']);write_csv(ROOT/'VELOCITY_OTHER_WORK.csv',[r for r in rows if r['method']=='Velocity'])
    atomic_json(CAMPAIGN/CONFIG['result_receipt'],dict(summary,root=str(ROOT),final_summary=ref(ROOT/'FINAL_SUMMARY.json'),cleanup=ref(ROOT/'chain/CHAIN_RESULT.json'),A_waits_for_B=False))
    (ROOT/'REPORT.md').write_text('# B L11 retest\n\nStatus: '+summary['status']+'; valid '+str(summary['valid'])+'/2500; missing '+str(summary['missing'])+'.\n\nFixed L11/fit9101, existing revealed sources. Post and Velocity exported separately. Original L01 results retained. Actual concurrent branch timing must not be interpreted as summed GPU hours.\n')
    print(json.dumps({k:summary[k] for k in ['status','valid','missing','attempts']}))

if __name__=='__main__':main()
