"""C source-exact local publications. Missing outcomes are never failures."""
import csv,json,sys,traceback
from collections import Counter
import paths
from paths import ROOT,CAMPAIGN,TASK
from qio import read,atomic_json,utc,ref
from publication_data import load_evidence,finite_values
from analysis_tools import write_csv,read_csv,compact,costs,pair

def references():
    out={};evidence=[]
    configs=[('R_multi',CAMPAIGN/'results/C/C_D24_R_TRIGGER_MODES_V1/FINAL_EPISODES.csv','G0-multi'),
             ('R_once',CAMPAIGN/'results/C/C_D24_R_H40_H50_V1/EPISODES.csv',None),
             ('old_Q',CAMPAIGN/'results/A/A_D24_MAIN_ONCE_V1/FINAL_EPISODES.csv',None)]
    for name,p,mode in configs:
        if not p.exists():continue
        evidence.append(ref(p))
        for r in read_csv(p):
            if r['H'] not in [40,50] or r['status']!='complete' or (mode and r.get('mode')!=mode):continue
            key=(r['H'],name+'_'+r.get('method',r.get('branch','R')))
            if name=='old_Q' and r.get('method') not in ['Post','Velocity','N']:continue
            out.setdefault(key,{})[r['source_id']]=r
    for H in [40,50]:
        for p in sorted((CAMPAIGN/'deadline_20260924/A/runs').glob(f'N_H{H}_*/RESULT.json')):
            for r in read(p)['episodes']:
                if r['status']=='complete':out.setdefault((H,'N'),{})[r['source_id']]=r
        if (H,'N') not in out and (H,'old_Q_N') in out:out[H,'N']=out[H,'old_Q_N']
    return out,evidence

def publish():
    cfg=read(ROOT/'config/CONFIG.json');_,attempts,claims,_=load_evidence()
    rows=[compact(r) for r in attempts];selected=read(ROOT/'SELECTION_CONSUMED.json') if (ROOT/'SELECTION_CONSUMED.json').exists() else None
    transferred=read(ROOT/'TRANSFER_CONSUMED.json') if (ROOT/'TRANSFER_CONSUMED.json').exists() else None
    jobs=[read(r['path']) for r in read(ROOT/'JOB_INDEX.json')['jobs']] if (ROOT/'JOB_INDEX.json').exists() else []
    expected={j['cell_id']+'__'+s['source_id']:(j,s) for j in jobs for s in j['sources']}
    results={r['unit_id']:r for r in rows};entered={c['unit_id']:c for c in claims}
    units=[];cells=[];resource={};cuts=[]
    for uid,(j,s) in expected.items():
        r=results.get(uid);claim=entered.get(uid)
        units.append(dict(unit_id=uid,cell_id=j['cell_id'],H=j['H'],method=j['method'],source_id=s['source_id'],task=s['task'],env_seed=s['env_seed'],policy_seed=s['policy_seed'],status=r['status'] if r else 'unknown_entered' if claim else 'not_started',success=r['success'] if r and r['status']=='complete' else None,result_path=r.get('result_path') if r else None))
    if set(entered)-set(expected) or set(results)-set(entered):raise ValueError('source outside transfer/claim')
    for r in attempts:
        if r['status']!='complete':continue
        if type(r['success']) is not bool or (r['control_hz'],r['physics_hz'],r['action_scale'],r['H'],r['mode']) not in [(30,400,.015,h,'G0-multi') for h in [40,50]]:raise ValueError('terminal or physical contract changed')
        raw=read(r['result_path']);events=raw['events'];triggered=[e for e in events if e.get('intervention_executed')];xs=raw['intervention_cuts']
        if xs!=[e['step'] for e in triggered] or len(xs)!=raw['interventions'] or raw['first_cut']!=(xs[0] if xs else None) or any(b-a<10 for a,b in zip(xs,xs[1:])):raise ValueError('C10/first-cut records mismatch')
        for e in triggered:
            if not e['old_tail_discarded'] or e['restore_native_H']!=r['H'] or e['commit_until']!=e['step']+10:raise ValueError('C10 intervention contract')
            cuts.append(dict(cell_id=r['cell_id'],source_id=r['source_id'],H=r['H'],method=r['method'],**{k:v for k,v in e.items() if not isinstance(v,(dict,list))}))
    for c in cfg['cells']:
        key=c['cell_id'];data=[r for r in rows if r['cell_id']==key];good=[r for r in data if r['status']=='complete'];u=[r for r in units if r['cell_id']==key];n=len(good)
        count=sum(j['cell_id']==key and len(j['sources']) or 0 for j in jobs)
        cells.append(dict(c,selected_loss=selected['chosen_loss'] if selected else None,transferred=count,A_retained_or_not_yet_granted=500-count,attempts=sum(x['cell_id']==key for x in claims),valid=n,successes=sum(r['success'] for r in good),success_rate=sum(r['success'] for r in good)/n if n else None,technical_failures=sum(r['status']=='technical_failure' for r in data),unknown_entered=sum(r['status']=='unknown_entered' for r in u),not_started=sum(r['status']=='not_started' for r in u),complete_transferred=transferred is not None and n==count,full_cell_complete=n==500,interventions=sum(r['interventions'] for r in good),max_interventions=max((r['interventions'] for r in good),default=None),paper_primary=c['method']=='Post'))
        resource[key]=costs(data)
    baseline,baseline_refs=references();pairs=[]
    for c in cells:
        ours=[r for r in rows if r['cell_id']==c['cell_id'] and r['status']=='complete']
        for (H,name),table in baseline.items():
            if H!=c['H'] or name=='old_Q_N':continue
            common=[r for r in ours if r['source_id'] in table]
            if not common:continue
            paired=pair(common,[table[r['source_id']] for r in common],name=c['cell_id']+' minus '+name)
            paired.update(H=H,method=c['method'],cell_id=c['cell_id'],reference=name,complete_500_pairs=len(common)==500,comparison_scope='fixed source outcomes; old-Q once differs in both Q and trigger mode; cross-host runtime is descriptive')
            if len(common)!=500:paired.update(CI95_low_pp=None,CI95_high_pp=None,McNemar_exact_p=None,missing_reason='full500 paired coverage unavailable; no missingness imputation')
            pairs.append(paired)
    numeric=Counter();returned=Counter();method=Counter();loading=[]
    for p in (ROOT/'chains/evaluate/workers').glob('*/WORKER_EXIT.json'):
        r=read(p);numeric.update(r['numeric']['entered']);returned.update(r['numeric']['returned']);method.update(r.get('method_counts') or {})
        ready=p.with_name('MODEL_READY.json')
        if ready.exists():loading.append(read(ready))
    prior=read(ROOT/'PREDECESSOR_EXIT.json')['prior_C_attempts'] if (ROOT/'PREDECESSOR_EXIT.json').exists() else None
    summary=dict(task_id=TASK,utc=utc(),cells=cells,valid=sum(c['valid'] for c in cells),actual_attempts=len(claims),transferred_first_count=len(expected),original_first_maximum=2000,technical_failures=sum(c['technical_failures'] for c in cells),unknown_entered=sum(c['unknown_entered'] for c in cells),not_started=sum(c['not_started'] for c in cells),compute_complete=transferred is not None and all(c['complete_transferred'] for c in cells),prior_C_attempts=prior,cumulative_C_attempts=prior+len(claims) if prior is not None else None,new_training_updates=0,new_collection=0,chosen_loss=selected['chosen_loss'] if selected else None,selection_criterion='complete Post development only; Velocity inherits; fixedfit9101',paper_primary='Post',Velocity_final_paper_included=False)
    write_csv(ROOT/'FINAL_EPISODES.csv',rows);write_csv(ROOT/'FINAL_CELLS.csv',cells);write_csv(ROOT/'SOURCE_TERMINALS.csv',units);write_csv(ROOT/'INTERVENTIONS.csv',finite_values(cuts));write_csv(ROOT/'PAIRED.csv',pairs)
    write_csv(ROOT/'POST_PAPER_CELLS.csv',[r for r in cells if r['method']=='Post']);write_csv(ROOT/'VELOCITY_OTHER_WORK_CELLS.csv',[r for r in cells if r['method']=='Velocity'])
    write_csv(ROOT/'POST_PAPER_PAIRED.csv',[r for r in pairs if r['method']=='Post'])
    atomic_json(ROOT/'RESOURCE_SUMMARY.json',finite_values(dict(utc=utc(),cells=resource,all_worker_numeric_entered=dict(numeric),all_worker_numeric_returned=dict(returned),all_worker_method_counts=dict(method),loading=loading,failed_attempts=[compact(r) for r in attempts if r['status']!='complete'],unknown_inflight_cost_not_zero=True,utilization=str(ROOT/'chains/evaluate/UTILIZATION_SUMMARY.json'),holder_runtime_billed_separately=True,all_formal_holders_off=True,control_plane_extra_GPU_probes=0)))
    atomic_json(ROOT/'FINAL_SUMMARY.json',finite_values(summary))
    atomic_json(ROOT/'BASELINE_REFERENCES.json',dict(files=baseline_refs,N_directory=str(CAMPAIGN/'deadline_20260924/A/runs'),new_baseline_computation=0))
    (ROOT/'MASTER_UPDATE.md').write_text('# C selected π0.5 H40/H50\n\nA Post-only development choice, fixed fit9101; A π0.5 Q and preprocessing. NVIDIA EGL, 30/400 Hz, action scale .015, raw50/NFE10, original source/policy/candidate streams and C10. No N/R or completed-source replay, training or collection.\n\nPost belongs to current paper; Velocity continues as separately labelled other-work results. SOURCE_TERMINALS preserves technical, unknown and unstarted units. A-retained sources remain A-owned. Per-cut data and whole-worker calls include loading and failures separately from valid-episode costs. Cross-host timing and differing occupancy conditions do not support controlled throughput comparisons.\n')
    return summary

if __name__=='__main__':
    try:print(publish())
    except BaseException as e:
        atomic_json(ROOT/'REPORT_ERROR.json',dict(utc=utc(),error=repr(e),traceback=traceback.format_exc(),scientific_results_preserved=True));sys.exit(3)
