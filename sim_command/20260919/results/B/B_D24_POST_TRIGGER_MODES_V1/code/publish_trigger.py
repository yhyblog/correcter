"""CPU-only saved-row publication after each cell and at terminal completion."""
import argparse
import csv
import io
import json
from pathlib import Path
from collections import Counter
import numpy as np
from paths import ROOT, CAMPAIGN
from qio import read, atomic_json, utc


def cell_key(cell): return f"Post_{cell['mode']}_H{cell['H']}"

def write_csv(path, rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    stream=io.StringIO(); writer=csv.DictWriter(stream,fieldnames=fields)
    writer.writeheader()
    writer.writerows({k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in rows)
    temporary=path.with_name(path.name+'.tmp'); temporary.write_text(stream.getvalue()); temporary.replace(path)


def distributions(values):
    if not values:return dict(count=0,mean=None,median=None,p95=None,maximum=None)
    return dict(count=len(values),mean=float(np.mean(values)),median=float(np.median(values)),
                p95=float(np.percentile(values,95)),maximum=int(max(values)))


def publish(only_cell=None):
    cfg=read(ROOT/'config/CONFIG.json'); source_rows=read(ROOT/'config/TEST_SOURCES_V1.json')['rows']
    sources={x['source_id']:x for x in source_rows}; tasks=sorted({x['task'] for x in source_rows})
    schedule={(x['H'],x['source_id']):x['selected_cut'] for x in read(ROOT/'config/RANDOM_ONCE_SCHEDULE_V1.json')['rows']}
    selected=[c for c in cfg['cells'] if only_cell is None or cell_key(c)==only_cell]
    if not selected:raise ValueError('unknown cell')
    dest=ROOT if only_cell is None else ROOT/'cell_publications'/only_cell
    dest.mkdir(parents=True,exist_ok=True)
    episodes=[]; interventions=[]; cells=[]; missing=[]; task_rows=[]; resources=[]; arrays={}; attempts=0; init_failures=0
    for cell in selected:
        mode,H=cell['mode'],cell['H']; key=cell_key(cell); pattern=f'Post_{mode}_H{H:02d}_*'
        by={}; entered={p.parent.name for p in (ROOT/'runs').glob(pattern+'/episodes/*/ENTERED.json')}
        initial_errors=0
        for p in (ROOT/'runs').glob(pattern+'/RESULT.json'):
            job=read(p)
            if job.get('exceptions') and not job.get('episodes'):initial_errors+=1
        init_failures+=initial_errors
        for p in sorted((ROOT/'runs').glob(pattern+'/episodes/*/RESULT.json')):
            e=read(p); sid=e['source_id']; src=sources[sid]
            assert e['method']=='Post' and e['mode']==mode and e['H']==H and sid not in by
            assert all(e[k]==src[k] for k in ['task','ordinal','env_seed','policy_seed'])
            assert e['planned_random_cut']==(schedule[(H,sid)] if mode=='Random-once' else None)
            if e['status']=='complete':
                cuts=e['intervention_cuts']; assert type(e['success']) is bool and len(cuts)==e['interventions']
                assert e['first_cut']==(cuts[0] if cuts else None) and e['last_cut']==(cuts[-1] if cuts else None)
                if mode=='Random-once':assert len(cuts)<=1 and (not cuts or cuts==[schedule[(H,sid)]])
                assert all(y-x>=15 for x,y in zip(cuts,cuts[1:]))
            else:assert e['success'] is None
            by[sid]=e
            row={k:v for k,v in e.items() if not isinstance(v,(list,dict))}
            row.update(result_path=str(p),monitor_log=str(p.parent/'events.jsonl'),
                       intervention_cuts=e.get('intervention_cuts',[]),commitments=e.get('commitments',[]),
                       shadow_G0=[dict(step=x['step'],gate=x.get('gate'),legal=x.get('legal_cut')) for x in e.get('events',[]) if x.get('shadow_G0')])
            row.update({'counter_'+k:v for k,v in e.get('counters',{}).items()});episodes.append(row)
            commitments={x['cut']:x for x in e.get('commitments',[])}
            for ev in e.get('events',[]):
                if not ev.get('intervention_executed'):continue
                cm=commitments.get(ev['step'],{})
                interventions.append(dict(source_id=sid,task=src['task'],env_seed=src['env_seed'],policy_seed=src['policy_seed'],
                    branch='Post',mode=mode,H=H,cut=ev['step'],intervention_index=ev['intervention_index'],
                    first_cut=e['first_cut'],last_cut=e['last_cut'],planned_random_cut=e['planned_random_cut'],
                    candidate_seed=ev['seed'],G0=ev.get('gate'),G0_is_shadow=mode=='Random-once',
                    commit_until=ev['commit_until'],committed_steps=cm.get('committed_steps'),
                    restored_at=cm.get('restored_at'),restored_H=cm.get('restored_H'),
                    old_tail_discarded=True,generation=ev['generation'],result_path=str(p)))
        valid={sid:e for sid,e in by.items() if e['status']=='complete'}
        failed=set(by)-set(valid); unknown=entered-set(by); unstarted=set(sources)-entered
        for sid in sorted(set(sources)-set(valid)):
            missing.append(dict(branch='Post',mode=mode,H=H,source_id=sid,
                classification='technical_failure' if sid in failed else 'execution_unknown' if sid in unknown else 'unstarted'))
        cnt=Counter(); succ_cnt=Counter(); costs=Counter(); trigger_counts=[]; cut_counts=Counter(); first_counts=Counter(); no_trigger=Counter(); shadow=Counter()
        for e in by.values():
            cnt.update(e.get('counters',{}))
            if e.get('success') is True:succ_cnt.update(e.get('counters',{}))
            for name in ['elapsed_seconds','elapsed_control_seconds','reset_seconds','environment_seconds','inference_seconds','context_seconds','monitor_seconds']:
                costs[name]+=e.get(name,0)
            if e['status']=='complete':
                trigger_counts.append(e['interventions']);cut_counts.update(e['intervention_cuts'])
                if e['first_cut'] is not None:first_counts[e['first_cut']]+=1
                if e['interventions']==0:no_trigger[e['no_intervention_reason']]+=1
            if mode=='Random-once':
                for name in ['contexts','D_forward','G0_forward']:shadow[name]+=e.get('counters',{}).get(name,0)
        successes=sum(e['success'] for e in valid.values()); complete=len(valid)==500
        result=dict(cell=key,branch='Post',method='Post',mode=mode,H=H,planned=500,entered_episodes=len(entered),
                    valid=len(valid),successes=successes,technical_failures=len(failed),execution_unknown=len(unknown),
                    unstarted=len(unstarted),complete=complete,success_rate=successes/len(valid) if valid else None,
                    trigger_zero=sum(x==0 for x in trigger_counts),trigger_once=sum(x==1 for x in trigger_counts),
                    trigger_multiple=sum(x>=2 for x in trigger_counts),intervention_distribution=distributions(trigger_counts),
                    first_cut_histogram=dict(first_counts),all_cut_histogram=dict(cut_counts),no_intervention_reasons=dict(no_trigger))
        for field in ['trigger_zero','trigger_once','trigger_multiple']:
            result[field+'_proportion']=result[field]/len(valid) if valid else None
        cells.append(result);arrays[(mode,H)]=valid
        resources.append(dict(cell=key,mode=mode,H=H,saved_episode_counters=dict(cnt),
            successful_episode_counters=dict(succ_cnt),all_calls_per_success={k:v/successes if successes else None for k,v in cnt.items()},
            successful_episode_calls_per_success={k:v/successes if successes else None for k,v in succ_cnt.items()},
            timing_sums_seconds=dict(costs),shadow_counters=dict(shadow),
            shadow_context_monitor_seconds=(costs['context_seconds']+costs['monitor_seconds']) if mode=='Random-once' else 0,
            shadow_costs_are_included_in_total=True,minimum_deployment_cost_claim=False))
        for task in tasks:
            ids=[x['source_id'] for x in source_rows if x['task']==task];ev=[valid[sid] for sid in ids if sid in valid]
            task_rows.append(dict(branch='Post',mode=mode,H=H,task=task,planned=10,valid=len(ev),successes=sum(e['success'] for e in ev),
                technical_failures=sum(sid in failed for sid in ids),execution_unknown=sum(sid in unknown for sid in ids),
                unstarted=sum(sid in unstarted for sid in ids),interventions=sum(e['interventions'] for e in ev)))
        attempts+=len(entered)+initial_errors
    assert attempts<=cfg['stage_attempt_cap'] and cfg['planned_prior_attempts']+attempts<=cfg['node_cumulative_attempt_cap']
    # Reuse original G0-once Post results; there is no cross-node compute wait.
    control=CAMPAIGN/'results/A/A_D24_MAIN_ONCE_V1/FINAL_EPISODES.csv';once={}
    with control.open() as f:
        for x in csv.DictReader(f):
            if x['method']!='Post' or x['status']!='complete':continue
            x=dict(x,H=int(x['H']),success=x['success']=='True',env_seed=int(x['env_seed']),policy_seed=int(x['policy_seed']))
            once[(x['H'],x['source_id'])]=x
    canonical=[s['source_id'] for task in tasks for s in sorted((x for x in source_rows if x['task']==task),key=lambda x:x['ordinal'])]
    indices=np.random.default_rng(20260921).integers(0,10,size=(2000,50,10));paired=[]
    for cell in selected:
        mode,H=cell['mode'],cell['H'];left=arrays[(mode,H)];ids=[sid for sid in canonical if sid in left and (H,sid) in once]
        for sid in ids:
            assert all(int(left[sid][k])==int(once[(H,sid)][k])==sources[sid][k] for k in ['env_seed','policy_seed'])
        diff=np.asarray([int(left[sid]['success'])-int(once[(H,sid)]['success']) for sid in ids],float);ci=None
        if len(ids)==500:
            samples=diff.reshape(50,10)[np.arange(50)[None,:,None],indices].mean(axis=(1,2))*100
            ci=np.quantile(samples,[.025,.975]).tolist()
        paired.append(dict(branch='Post',mode=mode,H=H,contrast=mode+' - G0-once',paired_valid=len(ids),
            left_successes=sum(left[sid]['success'] for sid in ids),right_successes=sum(once[(H,sid)]['success'] for sid in ids),
            rescued=int((diff>0).sum()),harmed=int((diff<0).sum()),
            both_success=sum(left[sid]['success'] and once[(H,sid)]['success'] for sid in ids),
            both_failure=sum(not left[sid]['success'] and not once[(H,sid)]['success'] for sid in ids),
            difference_pp=float(diff.mean()*100) if len(ids) else None,pointwise95_CI_pp=ci,
            bootstrap_seed=20260921,bootstrap_replicates=2000,shared_draws=True,
            significant_claim=False,Holm_scope='No significance claim; any later testing requires 15-comparison correction per mode across ABC',
            denominator='all common valid sources; never filter by actual intervention',
            CI_note='fixed50 tasks,within-task10-source resamples; conditional/no retraining uncertainty' if ci else 'incomplete paired cell; no CI'))
    complete=all(x['complete'] for x in cells)
    report=dict(status='complete' if complete else 'partial',at_utc=utc(),task_id=cfg['task_id'],branch='Post',
        terminal_publication=True,cell_publication=only_cell,cells=cells,attempts=attempts,
        prior_B_attempts=cfg['planned_prior_attempts'],cumulative_B_attempts=cfg['planned_prior_attempts']+attempts if only_cell is None else None,
        cumulative_counter_scope='entire new stage' if only_cell is None else 'cell-only; no node cumulative claim',
        stage_attempt_cap=cfg['stage_attempt_cap'],node_cumulative_attempt_cap=cfg['node_cumulative_attempt_cap'],
        environment_initialization_failures=init_failures,entered_episodes=sum(x['entered_episodes'] for x in cells),
        training_updates=0,missing_sources=len(missing),paired=paired,method_frozen=str(ROOT/'METHOD_FROZEN.json'),
        final_episodes=str(dest/'FINAL_EPISODES.csv'),final_pairs=str(dest/'FINAL_PAIRED.json'),
        resource_summary=str(dest/'RESOURCE_SUMMARY.json'),A_waits_for_B=False,
        interpretation='Executable strategies; once trigger rates can differ, not a pure timing effect at equal realized intervention count. Multi costs are measured. Pointwise CIs only.',
        cross_host_timing_not_strictly_comparable=True)
    write_csv(dest/'FINAL_EPISODES.csv',episodes);write_csv(dest/'INTERVENTIONS.csv',interventions)
    write_csv(dest/'FINAL_CELLS.csv',cells);write_csv(dest/'FINAL_TASKS.csv',task_rows);write_csv(dest/'FINAL_PAIRED.csv',paired)
    atomic_json(dest/'FINAL_PAIRED.json',paired);atomic_json(dest/'FINAL_MISSING.json',missing)
    worker_counts=[]
    if only_cell is None:
        for p in sorted((ROOT/'chain/workers').glob('*/WORKER_EXIT.json')):
            x=read(p);worker_counts.append(dict(worker=p.parent.name,reference=str(p),method_counts=x.get('method_counts'),numeric=x.get('numeric'),fatal=x.get('fatal')))
    atomic_json(dest/'RESOURCE_SUMMARY.json',dict(cells=resources,worker_actual_counts=worker_counts,
        accounting='saved episode counters include technical rows; worker totals also preserve interrupted episode calls',
        occupancy_accounted_separately=True,concurrent_episode_wall_sums_are_not_node_wall_time=True))
    atomic_json(dest/'FINAL_SUMMARY.json',report)
    text=['B Post trigger modes: saved terminal evidence.','', '| H | Mode | Success/valid | Technical/unknown/unstarted |',
          '|---|---|---:|---:|']
    text += [f"| {x['H']} | {x['mode']} | {x['successes']}/{x['valid']} | {x['technical_failures']}/{x['execution_unknown']}/{x['unstarted']} |" for x in cells]
    text += ['',report['interpretation'],'Paired statistics, full trigger histories and actual costs are in FINAL_PAIRED, INTERVENTIONS and RESOURCE_SUMMARY. Random shadow D/G0/context cost remains included. No new training; no rerun of original controls.','']
    (dest/'REPORT.md').write_text('\n'.join(text));(dest/'FINAL_SUMMARY.md').write_text('\n'.join(text))
    atomic_json(dest/'READY.json',dict(at_utc=utc(),status=report['status'],summary=str(dest/'FINAL_SUMMARY.json')))
    if only_cell is None:
        atomic_json(CAMPAIGN/'receipts/B/B_D24_POST_TRIGGER_MODES_V1_RESULT.json',dict(report,result_root=str(ROOT),chain_result=str(ROOT/'chain/CHAIN_RESULT.json')))
    return dict(status=report['status'],cell=only_cell,attempts=attempts,valid=sum(x['valid'] for x in cells))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--cell');args=parser.parse_args()
    print(json.dumps(publish(args.cell)))
