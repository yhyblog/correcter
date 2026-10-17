"""Saved scalar terminal publications; never imports models or environment code."""
import argparse
import csv
import io
import json
import math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import paths
from paths import ROOT,OLD_ROOT,CAMPAIGN,TASK
from qio import read,atomic_json as _atomic_json,utc
from publication_data import load_evidence,merge_event,finite_values,EvidenceConflict,identity

def atomic_json(path,value):return _atomic_json(path,finite_values(value))


def cell_id(x):return f"Velocity_{x['mode']}_H{x['H']}"


def write_csv(path,rows):
    rows=[finite_values(r) for r in rows]
    for r in rows:
        if 'non_finite_null_reasons' in r:r['non_finite_null_reasons']=json.dumps(r['non_finite_null_reasons'],sort_keys=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=keys);w.writeheader();w.writerows(rows)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(s.getvalue());tmp.replace(path)


def paired(left,right,label,H,mode,descriptive_subset=False):
    a={x['source_id']:x for x in left};b={x['source_id']:x for x in right}
    ids=sorted(set(a)&set(b),key=lambda sid:(a[sid]['task'],sid))
    for sid in ids:
        for k in ['task','ordinal','env_seed','policy_seed']:
            if a[sid][k]!=b[sid][k]:raise EvidenceConflict('paired identity mismatch '+sid+' '+k)
    d=np.array([int(a[s]['success'])-int(b[s]['success']) for s in ids],dtype=float)
    ci=[None,None]
    if len(ids)==500 and set(Counter(a[s]['task'] for s in ids).values())=={10}:
        sample=np.random.default_rng(20260921).integers(0,10,size=(2000,50,10))
        estimate=d.reshape(50,10)[np.arange(50)[None,:,None],sample].mean(axis=(1,2))*100
        ci=np.quantile(estimate,[.025,.975]).tolist()
    return dict(H=H,mode=mode,branch='Velocity',comparison=label,paired_valid=len(ids),
        candidate_successes=sum(a[s]['success'] for s in ids),baseline_successes=sum(b[s]['success'] for s in ids),
        rescued=int((d==1).sum()),harmed=int((d==-1).sum()),
        both_success=sum(a[s]['success'] and b[s]['success'] for s in ids),both_failure=sum(not a[s]['success'] and not b[s]['success'] for s in ids),
        difference_pp=float(d.mean()*100) if len(d) else None,CI95_low_pp=ci[0],CI95_high_pp=ci[1],
        CI_null_reason=None if ci[0] is not None else 'Complete50x10 common valid sources unavailable; no outcome imputation',
        uncertainty='Pointwise fixed50 task within-task source bootstrap2000 seed20260921; not fit-seed uncertainty',
        significance_test=None,significance_reason='No local significance claim; planned Holm families require15 contrasts across A/B/C per mode',
        descriptive_jointly_triggered_subset=descriptive_subset)


def generate(only=None,terminal=False,destination=None):
    cfg=read(ROOT/'config/CONFIG.json');stamp=utc()
    jobs,all_attempts,claims,raw=load_evidence(only)
    if len(claims)>5500 or cfg['planned_prior_attempts']+len(claims)>18000:raise EvidenceConflict('attempt cap exceeded')
    sources={x['source_id']:x for x in read(ROOT/'config/TEST_SOURCES_V1.json')['rows']}
    seen=set();groups=defaultdict(list);ep_rows=[];interventions=[]
    for ep in raw:
        ident=(ep['mode'],ep['H'],ep['source_id'])
        if ident in seen:raise EvidenceConflict('duplicate terminal identity')
        seen.add(ident)
        if ep['source_id'] not in sources:raise EvidenceConflict('noncohort source')
        for k in ['task','ordinal','env_seed','policy_seed']:
            if ep[k]!=sources[ep['source_id']][k]:raise EvidenceConflict('source drift')
        row={k:v for k,v in ep.items() if not isinstance(v,(dict,list))}
        row['intervention_cuts_json']=json.dumps(ep.get('intervention_cuts'))
        row.update({'counter_'+k:v for k,v in ep.get('counters',{}).items()})
        ep_rows.append(row)
        if ep['status']=='complete':
            if type(ep['success']) is not bool or ep.get('technical_failure') is not None:raise EvidenceConflict('bad valid outcome')
            cuts=ep['intervention_cuts']
            if len(cuts)!=ep['interventions'] or ep['first_cut']!=(cuts[0] if cuts else None) or ep['last_cut']!=(cuts[-1] if cuts else None):raise EvidenceConflict('cut summary lost')
            if ep['mode']=='Random-once' and (len(cuts)>1 or any(t!=ep['planned_random_cut'] for t in cuts)):raise EvidenceConflict('random schedule violated')
            groups[cell_id(ep)].append(ep)
        for event in ep.get('events',[]):
            row=merge_event(ep,event)
            row.update(member_benefits_json=json.dumps(event.get('member_benefits')),result_path=ep['result_path'])
            interventions.append(row)
    old=defaultdict(list)
    with (CAMPAIGN/'results/A/A_D24_MAIN_ONCE_V1/FINAL_EPISODES.csv').open() as f:
        for x in csv.DictReader(f):
            if x['method']!='Velocity':continue
            for k in ['H','ordinal','env_seed','policy_seed','interventions']:x[k]=int(x[k])
            x['success']={'True':True,'False':False}[x['success']]
            old[x['H']].append(x)
    cells=[];pair_rows=[];subset_rows=[];resources={};histograms={}
    for c in cfg['cells']:
        key=cell_id(c)
        if only and only!=key:continue
        valid=groups[key];s=sum(x['success'] for x in valid);n=len(valid)
        attempted=[x for x in claims if x['mode']==c['mode'] and x['H']==c['H']]
        allrows=[x for x in all_attempts if cell_id(x)==key]
        unique_rows=[x for x in raw if cell_id(x)==key]
        unique_entered={identity(x) for x in attempted}
        saved_attempt_ids={(*identity(x),x['attempt_index']) for x in allrows}
        counts=[x['interventions'] for x in valid];dist=Counter(counts)
        costs={}
        for metric in ['policy_calls','sampling_calls','flow_calls','elapsed_seconds','inference_seconds','environment_seconds','steps']:
            def value(x):
                counter={'policy_calls':'sampling','sampling_calls':'sampling','flow_calls':'flow'}.get(metric)
                v=x.get('counters',{}).get(counter,x.get(metric)) if counter else x.get(metric)
                return float(v) if isinstance(v,(int,float)) and math.isfinite(float(v)) else None
            known=[v for x in allrows if (v:=value(x)) is not None]
            successful=[v for x in valid if x['success'] and (v:=value(x)) is not None]
            complete_cost=len(known)==len(attempted)
            costs[metric]=dict(recorded_attempts=len(known),physical_attempts=len(attempted),sum_recorded=math.fsum(known),
                sum_all=math.fsum(known) if complete_cost else None,
                unknown_reason=None if complete_cost else 'Missing/non-finite attempt cost; recorded subtotal is not total',
                mean_all=math.fsum(known)/len(known) if known and complete_cost else None,
                mean_success_only=math.fsum(successful)/s if s and len(successful)==s else None,
                all_cost_per_success=math.fsum(known)/s if s and complete_cost else None)
        costc=Counter()
        for x in allrows:costc.update(x.get('counters',{}))
        histogram=dict(first_cuts=dict(Counter(str(x['first_cut']) for x in valid)),all_cuts=dict(Counter(str(t) for x in valid for t in x['intervention_cuts'])),
            interventions=dict(Counter(str(v) for v in counts)),no_intervention_reasons=dict(Counter(str(x.get('no_intervention_reason')) for x in valid if x['interventions']==0)),
            random_dispositions=dict(Counter(str(x.get('random_schedule_disposition')) for x in valid if x['mode']=='Random-once')))
        histograms[key]=histogram
        row=dict(cell=key,branch='Velocity',mode=c['mode'],H=c['H'],planned=500,attempts=len(attempted),valid=n,successes=s,
            success_rate_pct=100*s/n if n else None,technical_failures=sum(x['status']=='technical_failure' for x in allrows),
            entered_without_result=len(attempted)-len(saved_attempt_ids),entered_unique_units=len(unique_entered),unstarted=500-len(unique_entered),complete=n==500,
            corrected_retry_attempts=sum(x['attempt']==1 for x in attempted),unresolved_failed_units=sum(x['status']!='complete' for x in unique_rows),
            interventions_zero=dist[0],interventions_once=dist[1],interventions_ge2=sum(v for k,v in dist.items() if k>=2),
            zero_fraction=dist[0]/n if n else None,once_fraction=dist[1]/n if n else None,ge2_fraction=sum(v for k,v in dist.items() if k>=2)/n if n else None,
            interventions_mean=float(np.mean(counts)) if n else None,interventions_median=float(np.median(counts)) if n else None,
            interventions_p95=float(np.quantile(counts,.95)) if n else None,interventions_max=max(counts) if n else None,
            policy_calls=costs['policy_calls']['sum_all'],flow_calls=costs['flow_calls']['sum_all'],
            policy_calls_mean_success_only=costs['policy_calls']['mean_success_only'],all_policy_calls_per_success=costs['policy_calls']['all_cost_per_success'],
            actual_Q_ensemble_calls=costc['Q_ensemble_forward'],actual_Q_member_calls=4*costc['Q_ensemble_forward'],actual_action_gradients=costc['action_gradients'],
            actual_sampling_counter=costc['sampling'],actual_flow_counter=costc['flow'],
            shadow_contexts=costc['contexts'] if c['mode']=='Random-once' else 0,shadow_D_calls=costc['D_forward'] if c['mode']=='Random-once' else 0,
            shadow_G0_calls=costc['G0_forward'] if c['mode']=='Random-once' else 0,shadow_elapsed_included=True)
        cells.append(row);resources[key]=dict(costs=costs,all_entered_episode_counters=costc,
            scope='All original and corrected physical attempts are charged once; successful-only means use unique valid terminal outcomes; unknown attempt costs remain null; resident loads/job initialization separate')
        if n:
            pair_rows.append(paired(valid,old[c['H']],c['mode']+' - G0-once',c['H'],c['mode']))
            subset_rows.append(paired([x for x in valid if x['interventions']>0],[x for x in old[c['H']] if x['interventions']>0],
                c['mode']+' - G0-once, jointly triggered only',c['H'],c['mode'],True))
    dest=Path(destination) if destination else (ROOT/'cells'/only if only else ROOT)
    dest.resolve().relative_to(ROOT.resolve());dest.mkdir(parents=True,exist_ok=True)
    write_csv(dest/'FINAL_CELLS.csv',cells);write_csv(dest/'FINAL_EPISODES.csv',ep_rows);write_csv(dest/'INTERVENTIONS.csv',interventions)
    attempt_rows=[]
    for ep in all_attempts:
        ar={k:v for k,v in ep.items() if not isinstance(v,(dict,list))};ar.update({'counter_'+k:v for k,v in ep.get('counters',{}).items()});attempt_rows.append(ar)
    write_csv(dest/'ALL_ATTEMPTS.csv',attempt_rows)
    write_csv(dest/'FINAL_PAIRED.csv',pair_rows);write_csv(dest/'JOINTLY_TRIGGERED_DESCRIPTIVE.csv',subset_rows)
    atomic_json(dest/'INTERVENTION_HISTOGRAMS.json',dict(utc=stamp,cells=histograms))
    numeric=Counter();jobtime=0.
    for job in jobs:numeric.update(job.get('numeric_delta',{}));jobtime+=job.get('environment_initialization_seconds',0)
    loads=[]
    for p in sorted(list((OLD_ROOT/'chain/workers').glob('*/WORKER_EXIT.json'))+list((ROOT/'chain/workers').glob('*/WORKER_EXIT.json'))):
        x=read(p);loads.append(dict(path=str(p),numeric=x.get('numeric'),fatal=x.get('fatal')))
    atomic_json(dest/'RESOURCE_SUMMARY.json',dict(utc=stamp,cells=resources,job_numeric_delta=numeric,
        job_environment_initialization_seconds=jobtime,worker_initialization_and_failed_calls=loads,
        actual_stage_attempts=len(claims),prior_D24_attempts=cfg['planned_prior_attempts'],stage_cap=5500,node_cap=18000,
        holder_policy='all8off entire formal wave',occupancy_auxiliary_holder_calls=0,
        timing_notes='Shadow D/G0 retained in actual episode elapsed. Not random-strategy minimum deployment cost. Summed parallel times are not makespan/GPU kernel time.',
        local_significance_claim=False,global_Holm_families='15 Random-once comparisons and15 G0-multi comparisons require A/B/C combined publication'))
    summary=dict(task_id=TASK,utc=stamp,terminal=terminal,cell=only,cells=cells,valid=sum(x['valid'] for x in cells),
        attempts=len(claims),successes=sum(x['successes'] for x in cells),technical_failures=sum(x['technical_failures'] for x in cells),
        entered_without_result=sum(x['entered_without_result'] for x in cells),complete=all(x['complete'] for x in cells),
        prior_D24_attempts=cfg['planned_prior_attempts'],node_cumulative_attempts=cfg['planned_prior_attempts']+len(claims),
        independent_source_identities=500,optimizer_updates=0,baseline_replays=0,
        old_preserved_valid=510,old_physical_attempts=518,recovery_physical_attempts=sum(Path(x['claim_path']).is_relative_to(ROOT) for x in claims),
        unstarted_unique_units=sum(x['unstarted'] for x in cells),unresolved_failed_units=sum(x['unresolved_failed_units'] for x in cells),
        compute_complete=all(x['complete'] for x in cells),publication_pending=False)
    atomic_json(dest/'FINAL_SUMMARY.json',summary)
    lines=['# Velocity trigger-mode terminal results','',f'Snapshot {stamp}; branch Velocity; original500 sources (ordinal0..9), no new initial states.','',
        '| Mode | H | Success / valid | Technical | Unstarted | >=2 interventions |','|---|---:|---:|---:|---:|---:|']
    for c in cells:lines.append(f"| {c['mode']} | {c['H']} | {c['successes']}/{c['valid']} | {c['technical_failures']} | {c['unstarted']} | {c['interventions_ge2']} |")
    lines += ['', 'Model/numerics: same frozen pi05 MT50 SFT030000, historical five-task D/G0/Q, 30/400Hz, scale .015, H/C10/raw50/NFE10, G0 > .05. Random replaces timing condition only; no resampling or forcing early-terminal sources. Multi removes total count cap only; C10 and history/cut legality remain.',
        'FINAL_PAIRED uses every common valid source against saved G0-once. Pointwise fixed-task bootstrap2000 seed20260921; no fit-seed uncertainty. No local significance/partial-family Holm claim. Jointly-triggered rows are descriptive only and do not replace full strategy denominators.',
        'Random keeps shadow context/D/G0 calls, included in total elapsed; this is not minimum random-policy deployment cost. Actual trigger counts differ: this is policy effectiveness, not a strictly equal-count pure timing causal effect. Multi costs must be reported with efficacy.',
        'Per-event cuts/seed/shadow gate/C10 execution/native restoration are in INTERVENTIONS.csv and original episode RESULT/events. No first_cut overwrite. Missing/technical outcomes remain unknown.',
        '原518次尝试保留，510个完整终局不重跑。FINAL_EPISODES以唯一(source,H,mode)为单位；ALL_ATTEMPTS保留原8中断与其一次纠正，不扩独立样本分母。',
        'Cross-branch same-mode Post−R and Velocity−R are to be joined from node-owned terminal tables by analysis when available; there is no cross-node runtime dependency. No B/C experiment is launched here.']
    (dest/'REPORT.md').write_text('\n'.join(lines)+'\n')
    atomic_json(dest/'PUBLICATION.json',dict(task_id=TASK,utc=stamp,cell=only,terminal=terminal,summary=str(dest/'FINAL_SUMMARY.json'),
        episode_csv=str(dest/'FINAL_EPISODES.csv'),paired_csv=str(dest/'FINAL_PAIRED.csv'),interventions_csv=str(dest/'INTERVENTIONS.csv'),
        resource_summary=str(dest/'RESOURCE_SUMMARY.json'),report=str(dest/'REPORT.md'),compute_complete=summary['compute_complete'],scientific_compute_this_publication=0))
    return summary


if __name__=='__main__':
    import sys,traceback
    p=argparse.ArgumentParser();p.add_argument('--cell');p.add_argument('--terminal',action='store_true');p.add_argument('--destination');p.add_argument('--error-json');a=p.parse_args()
    try:
        summary=generate(a.cell,a.terminal,a.destination);print(json.dumps({k:v for k,v in summary.items() if k!='cells'},allow_nan=False))
    except BaseException as error:
        code=2 if isinstance(error,EvidenceConflict) else 3 if isinstance(error,OSError) else 1
        info=dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc(),utc=utc(),exit_class=code,
            classification={1:'ordinary_publication_error',2:'scientific_evidence_conflict',3:'storage_or_IO_failure'}[code])
        if a.error_json:atomic_json(Path(a.error_json),info)
        print(info['traceback'],file=sys.stderr);sys.exit(code)
