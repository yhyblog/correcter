"""CPU publication of each finished cell and the finite task's terminal summary."""
import argparse
import collections
import csv
import json
import os
from pathlib import Path
import numpy as np
import paths
from paths import ROOT, CAMPAIGN
from qio import read, atomic_json, utc

TASK='C_D24_R_TRIGGER_MODES_V1'
COUNT_FIELDS=['sampling','flow','contexts','D_forward','G0_forward','interventions','action_gradients','Q_ensemble_forward']


def csv_write(path, rows, fields=None):
    fields=fields or list(dict.fromkeys(k for row in rows for k in row))
    temp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    with temp.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    temp.replace(path)


def truth(x):
    if x in (True,'True'):return True
    if x in (False,'False'):return False
    raise ValueError('Missing outcome is not a failure')


def validate_baselines():
    sources=read(ROOT/'config/TEST_SOURCES_V1.json')['rows'];source_map={s['source_id']:s for s in sources}
    rows=read(ROOT/'config/G0_ONCE_BASELINES.json')['rows'];baseline={}
    assert len(rows)==2500
    for row in rows:
        h=int(row['H']);sid=row['source_id'];key=(h,sid)
        assert h in (10,20,30,40,50) and key not in baseline and row['status']=='complete'
        truth(row['success']);assert row['task']==source_map[sid]['task']
        for field in ['env_seed','policy_seed','ordinal']:assert int(row[field])==source_map[sid][field]
        baseline[key]=row
    assert set(baseline)=={(h,s['source_id']) for h in (10,20,30,40,50) for s in sources}
    return baseline


def compare(left,right,sources):
    ordered=sorted(sources,key=lambda s:(s['task'],s['ordinal']))
    common=[s for s in ordered if s['source_id'] in left and s['source_id'] in right]
    a=np.array([truth(left[s['source_id']]['success']) for s in common],dtype=np.int64)
    b=np.array([truth(right[s['source_id']]['success']) for s in common],dtype=np.int64)
    n=len(common);delta=(a-b)
    result=dict(paired_valid=n,left_successes=int(a.sum()),right_successes=int(b.sum()),
                rescued=int(((a==1)&(b==0)).sum()),harmed=int(((a==0)&(b==1)).sum()),
                both_success=int(((a==1)&(b==1)).sum()),both_failed=int(((a==0)&(b==0)).sum()),
                delta_pp=float(delta.mean()*100) if n else None,bootstrap95_low_pp=None,bootstrap95_high_pp=None,
                replicates=2000,bootstrap_seed=20260921,CI_missing_reason=None,comparison_scope='all common valid sources')
    if n==500:
        draws=np.random.default_rng(20260921).integers(0,10,size=(2000,50,10))
        differences=delta.reshape(50,10)
        simulated=np.take_along_axis(np.broadcast_to(differences,(2000,50,10)),draws,axis=2).mean((1,2))*100
        low,high=np.quantile(simulated,[.025,.975]);result.update(bootstrap95_low_pp=float(low),bootstrap95_high_pp=float(high))
    else:result['CI_missing_reason']='Incomplete paired coverage; no imputation or resampling of missing outcomes'
    both=[s['source_id'] for s in common if int(left[s['source_id']].get('interventions',0))>0 and int(right[s['source_id']].get('interventions',0))>0]
    result['both_actually_triggered_descriptive_n']=len(both)
    result['both_actually_triggered_descriptive_delta_pp']=100*sum(int(truth(left[s]['success']))-int(truth(right[s]['success'])) for s in both)/len(both) if both else None
    return result


def collect(cell,sources,baseline):
    ep_rows=[];valid=[];events=[];attempts=0;technical=0;unknown=0;not_started=0
    for source in sources:
        sid=source['source_id'];job=cell['cell_id']+'_'+source['task'];out=ROOT/'runs'/job/'episodes'/sid
        claim=ROOT/'unit_claims'/(cell['cell_id']+'__'+sid+'__attempt1.json')
        entered=claim.exists();attempts+=int(entered)
        record=read(out/'RESULT.json') if (out/'RESULT.json').exists() else None
        row=dict(source_id=sid,task=source['task'],ordinal=source['ordinal'],env_seed=source['env_seed'],policy_seed=source['policy_seed'],
                 branch='R',method='R',mode=cell['mode'],H=cell['H'],cell_id=cell['cell_id'],status='unknown_entered' if entered else 'not_started',
                 success=None,claim_path=str(claim) if entered else None,result_path=str(out/'RESULT.json') if record else None)
        if record:
            assert entered and record['source_id']==sid and record['H']==cell['H'] and record['mode']==cell['mode']
            assert record['env_seed']==source['env_seed'] and record['policy_seed']==source['policy_seed']
            row.update({k:v for k,v in record.items() if k not in ['events','plans','counters','arrays']})
            row.update({'counter_'+k:record.get('counters',{}).get(k) for k in COUNT_FIELDS})
            row['shadow_D_forward']=record.get('counters',{}).get('D_forward') if cell['mode']=='Random-once' else 0
            row['shadow_G0_forward']=record.get('counters',{}).get('G0_forward') if cell['mode']=='Random-once' else 0
            if record['status']=='complete' and type(record['success']) is bool and record.get('terminal'):
                valid.append(row)
                for ev in record.get('events',[]):
                    if ev['intervention_executed']:
                        restored=next((x for x in record.get('restorations',[]) if x['step']==ev['commit_until']),None)
                        events.append(dict(source_id=sid,task=source['task'],env_seed=source['env_seed'],policy_seed=source['policy_seed'],
                            branch='R',mode=cell['mode'],H=cell['H'],random_scheduled_cut=record.get('random_scheduled_cut'),
                            intervention_index=ev['intervention_index'],actual_cut=ev['step'],candidate_seed=ev['seed'],
                            shadow_G0=ev['shadow_G0'],gate=ev['gate'],member_benefits=ev.get('member_benefits'),true_G0_trigger=ev['true_G0_trigger'],
                            legal_cut=ev['legal_cut'],commit_until=ev['commit_until'],restore_native_H=ev['restore_native_H'],actual_restore_step=restored['step'] if restored else None,
                            restoration_missing_reason=None if restored else 'episode terminated before native refill',generation=ev['generation']))
            elif record['status']=='technical_failure':technical+=1
            else:unknown+=1
        elif entered:unknown+=1
        else:not_started+=1
        ep_rows.append(row)
    assert len(valid)+technical+unknown+not_started==500
    counts=np.array([x['interventions'] for x in valid],dtype=np.int64)
    successes=sum(truth(x['success']) for x in valid);n=len(valid)
    stats=dict(cell_id=cell['cell_id'],branch='R',mode=cell['mode'],H=cell['H'],planned=500,attempts=attempts,valid=n,successes=successes,
               success_rate=successes/n if n else None,technical_failures=technical,unknown_entered=unknown,not_started=not_started,
               trigger_0=int((counts==0).sum()),trigger_1=int((counts==1).sum()),trigger_ge2=int((counts>=2).sum()),
               intervention_mean=float(counts.mean()) if n else None,intervention_median=float(np.median(counts)) if n else None,
               intervention_p95=float(np.percentile(counts,95)) if n else None,intervention_max=int(counts.max()) if n else None)
    for key in ['trigger_0','trigger_1','trigger_ge2']:stats[key+'_proportion']=stats[key]/n if n else None
    for key in ['policy_calls','flow_calls','elapsed_seconds','inference_seconds','environment_seconds','monitor_seconds','shadow_context_DG0_seconds']+['counter_'+x for x in COUNT_FIELDS]:
        known=[x for x in ep_rows if x.get(key) is not None]
        total=sum(x[key] for x in known);successful=[x for x in valid if truth(x['success']) and x.get(key) is not None]
        stats[key+'_known_total']=total;stats[key+'_known_episodes']=len(known)
        if key in ['policy_calls','flow_calls','counter_action_gradients','counter_Q_ensemble_forward']:
            stats[key+'_successful_total']=sum(x[key] for x in successful)
            stats[key+'_conditional_success_mean']=sum(x[key] for x in successful)/len(successful) if successful else None
            stats[key+'_all_known_divided_by_successes']=total/successes if successes else None
    distribution=dict(cell_id=cell['cell_id'],valid=n,counts=dict(collections.Counter(str(x['interventions']) for x in valid)),
                      first_cuts=dict(collections.Counter(str(x['first_cut']) for x in valid if x['first_cut'] is not None)),
                      all_cuts=dict(collections.Counter(str(t) for x in valid for t in x['intervention_cuts'])),
                      no_intervention_reasons=dict(collections.Counter(x['no_intervention_reason'] for x in valid if x['interventions']==0)),
                      random_schedule_outcomes=dict(collections.Counter(x['random_schedule_outcome'] for x in valid if x.get('random_schedule_outcome'))))
    left={x['source_id']:x for x in valid};right={s['source_id']:baseline[cell['H'],s['source_id']] for s in sources}
    paired=dict(cell_id=cell['cell_id'],branch='R',H=cell['H'],comparison=cell['mode']+' - G0-once',**compare(left,right,sources))
    return stats,ep_rows,events,paired,distribution


def publish(cell_id=None):
    cfg=read(ROOT/'config/CONFIG.json');sources=read(ROOT/'config/TEST_SOURCES_V1.json')['rows'];baseline=validate_baselines()
    cells=[x for x in cfg['cells'] if cell_id is None or x['cell_id']==cell_id]
    assert len(cells)==(1 if cell_id else 10)
    output=ROOT/'cells'/cell_id if cell_id else ROOT;output.mkdir(parents=True,exist_ok=True)
    data=[collect(x,sources,baseline) for x in cells]
    stats=[x[0] for x in data];episodes=[row for x in data for row in x[1]];events=[row for x in data for row in x[2]];pairs=[x[3] for x in data];distributions=[x[4] for x in data]
    csv_write(output/'FINAL_CELLS.csv',stats);csv_write(output/'FINAL_EPISODES.csv',episodes)
    csv_write(output/'INTERVENTIONS.csv',events,fields=None if events else ['source_id','mode','H','actual_cut'])
    csv_write(output/'FINAL_PAIRED.csv',pairs);atomic_json(output/'FINAL_PAIRED.json',dict(comparisons=pairs,pointwise=True,multiplicity_correction=False))
    atomic_json(output/'INTERVENTION_DISTRIBUTIONS.json',dict(cells=distributions))
    attempts=sum(x['attempts'] for x in stats);valid=sum(x['valid'] for x in stats)
    summary=dict(task_id=TASK,utc=utc(),terminal=cell_id is None,scope=cell_id or 'all10cells',planned=len(cells)*500,attempts=attempts,valid=valid,
                 cells={x['cell_id']:x for x in stats},technical_failures=sum(x['technical_failures'] for x in stats),unknown_entered=sum(x['unknown_entered'] for x in stats),
                 not_started=sum(x['not_started'] for x in stats),prior_C_attempts=2013,cumulative_C_attempts=2013+len(list((ROOT/'unit_claims').glob('*.json'))),
                 stage_cap=5500,cumulative_cap=7900,automatic_retries=0,optimizer_updates=0,training_updates=0,
                 bootstrap='fixed50 tasks, resample10 sources within each task,2000 shared draws,seed20260921,pointwise95% percentile; no multiplicity adjustment')
    atomic_json(output/'SUMMARY.json',summary)
    if cell_id:
        atomic_json(output/'PUBLICATION.json',dict(utc=utc(),cell_id=cell_id,status='complete' if valid==500 else 'partial_or_failed',summary=str(output/'SUMMARY.json'),no_analysis_gate=True))
        return summary
    worker_exits=[read(p) for p in (ROOT/'chain/workers').glob('*/WORKER_EXIT.json')]
    resource=dict(task_id=TASK,utc=utc(),attempts=attempts,cumulative_C_attempts=2013+attempts,stage_cap=5500,cumulative_cap=7900,
                  holder_policy='all holders off entire formal wave; restored after all owned formal processes exit',auxiliary_holder_launches=0,
                  model_ready_records=[read(p) for p in (ROOT/'chain/workers').glob('*/MODEL_READY.json')],worker_numeric_counters=[x.get('numeric') for x in worker_exits],
                  per_cell=stats,utilization=read(ROOT/'chain/UTILIZATION_SUMMARY.json') if (ROOT/'chain/UTILIZATION_SUMMARY.json').exists() else None,
                  manager_exit=read(ROOT/'chain/MANAGER_EXIT.json') if (ROOT/'chain/MANAGER_EXIT.json').exists() else None,
                  cost_scope='All actual known calls including shadow context/D/G0; counters on technical failures are retained. Missing costs are not zero. GPU sampling is not continuous busy time. Cross-host and holder conditions differ; no controlled timing claim.')
    atomic_json(output/'RESOURCE_SUMMARY.json',resource)
    cross={m:dict(path=str(CAMPAIGN/'results'/node/task/'FINAL_EPISODES.csv'),available=(CAMPAIGN/'results'/node/task/'FINAL_EPISODES.csv').exists()) for m,node,task in [('Post','B','B_D24_POST_TRIGGER_MODES_V1'),('Velocity','A','A_D24_VELOCITY_TRIGGER_MODES_V1')]}
    atomic_json(output/'CROSS_BRANCH_DEPENDENCIES.json',dict(utc=utc(),purpose='Reuse same-mode Post-R and Velocity-R in final aggregation; no added episodes or runtime barrier',sources=cross))
    lines=['# C R trigger-mode results','',f'Fixed 500 sources × five H × two new modes. Valid {valid}/{len(cells)*500}; technical failures {summary["technical_failures"]}, unknown {summary["unknown_entered"]}, not started {summary["not_started"]}. Historical G0-once is reused. No old evaluation or training was replayed.','',
           '| H | Mode | Successes / valid | Trigger 0 / 1 / ≥2 | Mean interventions | Policy calls, known total |','|---|---|---:|---:|---:|---:|']
    for x in stats:lines.append(f'| {x["H"]} | {x["mode"]} | {x["successes"]} / {x["valid"]} | {x["trigger_0"]} / {x["trigger_1"]} / {x["trigger_ge2"]} | {x["intervention_mean"]} | {x["policy_calls_known_total"]} |')
    lines+=['','| H | Mode − G0-once | Paired | Delta pp | Pointwise 95% CI pp | Rescued / harmed | Both success / both fail |','|---|---|---:|---:|---|---:|---:|']
    for x in pairs:
        delta=f'{x["delta_pp"]:+.1f}' if x['delta_pp'] is not None else 'unavailable'
        interval=f'[{x["bootstrap95_low_pp"]:.1f}, {x["bootstrap95_high_pp"]:.1f}]' if x['bootstrap95_low_pp'] is not None else x['CI_missing_reason']
        lines.append(f'| {x["H"]} | {x["comparison"]} | {x["paired_valid"]} | {delta} | {interval} | {x["rescued"]} / {x["harmed"]} | {x["both_success"]} / {x["both_failed"]} |')
    lines+=['','Intervals condition on the fixed 50 tasks and resample 10 sources within each task, 2000 replicates with NumPy seed 20260921. They are pointwise with no multiplicity adjustment, task-population or training-seed uncertainty. No significance claims or p-values are made.',
            '', 'The main contrasts estimate complete online trigger-policy effects. Random-once and G0-once share an at-most-once limit, but their actual trigger rates can differ; this does not isolate a pure timing effect at equal realized counts. The common-trigger subset is descriptive only. Multi may add calls; improvement is not free.',
            '', 'Random cuts come only from the frozen CPU schedule and are neither shifted nor redrawn after early termination/ineligibility. G0-multi removes only the total intervention cap, retaining strict G0 > .05, mature D5, legal queue age, C10 lock, native-H restore and the 300-step budget. No candidate or natural RNG domains change.',
            '', 'Frozen SFT030000; NVIDIA EGL535, corner2 480×480, control30Hz/physics400Hz, action scale .015, raw50/NFE10. Historical five-task D/G0 and Q assets remain fixed. R uses no Q correction or action gradients.',
            '', 'Random shadow D/G0 forwards and context time remain in measured costs; this is not the minimum deployment cost of a random policy. Counters, success-conditioned costs and all-known-calls per success are in FINAL_CELLS.csv. Missing costs are distinguished from zero. Per-source and per-cut distributions are in FINAL_EPISODES.csv, INTERVENTIONS.csv and INTERVENTION_DISTRIBUTIONS.json.',
            '', 'Eight resident GPU workers run a finite ordered queue; all holders remain off through formal loading, gaps and tails, and restore after the group exits. RESOURCE_SUMMARY.json retains model, call, timing and sampled utilization evidence. Cross-host G0-once comparisons have different runtime conditions and do not justify controlled speed claims.',
            '', 'Same-mode cross-branch Post−R and Velocity−R aggregation uses the other nodes’ new publications when available; CROSS_BRANCH_DEPENDENCIES.json records these inputs. C scientific scheduling has no A/B dependency.',
            '', 'Evidence: METHOD_FROZEN.json; config/TEST_SOURCES_V1.json; config/RANDOM_ONCE_SCHEDULE_V1.json; config/G0_ONCE_BASELINES.json with source provenance; CPU_CHECK.json; per-cell publications under cells/.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cell');p.add_argument('--validate-only',action='store_true');a=p.parse_args()
    if a.validate_only:print('FROZEN_BASELINES_VALID',len(validate_baselines()))
    else:
        s=publish(a.cell);print(json.dumps({k:s[k] for k in ['task_id','scope','planned','attempts','valid','technical_failures','unknown_entered','not_started']}))
