"""Publish saved terminal rows and paired fixed-task inference; no GPU imports."""
from pathlib import Path
from collections import Counter
import csv,io,json
import numpy as np
from paths import ROOT,CAMPAIGN
from qio import read,atomic_json,utc


def csv_write(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r));s=io.StringIO();w=csv.DictWriter(s,fieldnames=fields);w.writeheader();w.writerows(rows);Path(path).write_text(s.getvalue())


def main():
    source_rows=[s for s in read(ROOT/'config/TEST_SOURCES_V1.json')['rows'] if s['ordinal']<10]
    sources={s['source_id']:s for s in source_rows};tasks=sorted({s['task'] for s in source_rows});cfg=read(ROOT/'config/CONFIG.json')
    assert len(sources)==500 and len(tasks)==50
    episodes=[];by={};init_failures=0
    for jobfile in sorted((ROOT/'runs').glob('*/RESULT.json')):
        job=read(jobfile)
        if job.get('exceptions') and not job.get('episodes'):init_failures+=1
    # Episode RESULT is authoritative even if a worker exited before job publication.
    for p in sorted((ROOT/'runs').glob('*/episodes/*/RESULT.json')):
        e=read(p);source=sources[e['source_id']]
        assert e['method']=='R' and e['H'] in (20,30)
        assert all(e[k]==source[k] for k in ['source_id','task','ordinal','env_seed','policy_seed'])
        key=(e['H'],e['source_id']);assert key not in by,'duplicate valid/failed episode'
        if e['status']=='complete':assert type(e['success']) is bool and e['interventions']<=1
        else:assert e['success'] is None
        by[key]=e
        row={k:v for k,v in e.items() if not isinstance(v,(list,dict))}
        row['result_path']=str(p);row.update({'counter_'+k:v for k,v in e.get('counters',{}).items()});episodes.append(row)
    cells=[];task_table=[];missing=[];arrays={}
    for H in [20,30]:
        valid={sid:e for (h,sid),e in by.items() if h==H and e['status']=='complete'}
        failed={sid:e for (h,sid),e in by.items() if h==H and e['status']!='complete'}
        entered={p.parent.name for p in (ROOT/'runs').glob(f'R_H{H}_*/episodes/*/ENTERED.json')}
        unknown=entered-set(valid)-set(failed);unstarted=set(sources)-entered
        for sid in sorted(set(sources)-set(valid)):
            missing.append(dict(H=H,source_id=sid,classification='technical_failure' if sid in failed else 'execution_unknown' if sid in unknown else 'unstarted'))
        counts=Counter();costs=Counter()
        for e in valid.values():
            counts.update(e.get('counters',{}))
            for k in ['elapsed_seconds','elapsed_control_seconds','reset_seconds','environment_seconds','inference_seconds']:costs[k]+=e.get(k,0)
        cell=dict(cell=f'R_H{H}',method='R',H=H,planned=500,entered_episodes=len(entered),valid=len(valid),successes=sum(e['success'] for e in valid.values()),technical_failures=len(failed),execution_unknown=len(unknown),unstarted=len(unstarted),complete=len(valid)==500,success_rate=sum(e['success'] for e in valid.values())/len(valid) if valid else None,counters=dict(counts),timing_sums_seconds=dict(costs))
        cells.append(cell);arrays[('R',H)]=valid
        for task in tasks:
            ids=[x['source_id'] for x in source_rows if x['task']==task];ev=[valid[sid] for sid in ids if sid in valid]
            task_table.append(dict(H=H,method='R',task=task,planned=10,valid=len(ev),successes=sum(e['success'] for e in ev),technical_failures=sum(sid in failed for sid in ids),execution_unknown=sum(sid in unknown for sid in ids),unstarted=sum(sid in unstarted for sid in ids),interventions=sum(e['interventions'] for e in ev)))
        atomic_json(ROOT/f'FINAL_R_H{H}.json',dict(at_utc=utc(),terminal_publication=True,**cell))
    N=CAMPAIGN/'deadline_20260924/A';A=CAMPAIGN/'results/A/A_D24_MAIN_ONCE_V1'
    for H in [20,30]:
        values={}
        for p in sorted((N/'runs').glob(f'N_H{H}_*/RESULT.json')):
            for e in read(p)['episodes']:
                if e['status']=='complete':values[e['source_id']]=e
        arrays[('N',H)]=values
    with (A/'FINAL_EPISODES.csv').open() as f:
        for row in csv.DictReader(f):
            H=int(row['H']);method=row['method']
            if H not in (20,30) or method not in ('Post','Velocity') or row['status']!='complete':continue
            assert row['success'] in ('True','False')
            e=dict(row,success=row['success']=='True',env_seed=int(row['env_seed']),policy_seed=int(row['policy_seed']))
            arrays.setdefault((method,H),{})[e['source_id']]=e
    rng=np.random.default_rng(20260921);indices=rng.integers(0,10,size=(2000,50,10));paired=[]
    canonical_ids=[s['source_id'] for task in tasks for s in sorted((x for x in source_rows if x['task']==task),key=lambda x:x['ordinal'])]
    for H in [20,30]:
        for left,right in [('R','N'),('Post','R'),('Velocity','R')]:
            L,R=arrays[(left,H)],arrays[(right,H)];ids=[sid for sid in canonical_ids if sid in L and sid in R]
            for sid in ids:
                assert all(int(L[sid][k])==int(R[sid][k])==sources[sid][k] for k in ['env_seed','policy_seed'])
            diff=np.asarray([int(L[sid]['success'])-int(R[sid]['success']) for sid in ids],dtype=float)
            ci=None
            if len(ids)==500:
                matrix=diff.reshape(50,10);samples=matrix[np.arange(50)[None,:,None],indices].mean(axis=(1,2))*100;ci=np.quantile(samples,[.025,.975]).tolist()
            paired.append(dict(H=H,contrast=left+'-'+right,left_method=left,right_method=right,paired_valid=len(ids),left_successes=sum(L[sid]['success'] for sid in ids),right_successes=sum(R[sid]['success'] for sid in ids),rescued=int((diff>0).sum()),harmed=int((diff<0).sum()),difference_pp=float(diff.mean()*100) if len(diff) else None,bootstrap95_CI_pp=ci,bootstrap_note='Shared2000 within-task10-source resamples, fixed50 equal-weight tasks, seed20260921; unadjusted percentile95CI' if ci else 'Incomplete paired cell; CI withheld, missing results remain missing'))
    entered_count=sum(c['entered_episodes'] for c in cells);attempts=entered_count+init_failures
    assert attempts<=1100 and 5687+attempts<=16000
    renderer=[]
    for p in sorted((ROOT/'chain/workers').glob('*/renderer_identity.json')):
        row=read(p);assert 'nvidia' in row['GL']['vendor'].lower() and 'nvidia' in row['EGL']['vendor'].lower();renderer.append(dict(worker=p.parent.name,reference=str(p),identity=row))
    complete=all(c['complete'] for c in cells)
    report=dict(status='complete' if complete else 'partial',at_utc=utc(),task_id='B_D24_R_H20_H30_V1',cells=cells,attempts=attempts,entered_episodes=entered_count,environment_initialization_failures=init_failures,prior_B_attempts=5687,cumulative_B_attempts=5687+attempts,stage_attempt_cap=1100,node_cumulative_attempt_cap=16000,training_updates=0,paired=paired,paired_bootstrap_seed=20260921,shared_bootstrap_draws=True,method_reference=str(A/'code/controller.py'),source_reference=str(ROOT/'config/TEST_SOURCES_V1.json'),renderer=renderer,protocol=dict(model='pi05_MT50_SFT030000',normalizer=read(ROOT/'config/BASE.json')['normalizer_ref'],H=[20,30],raw_horizon=50,NFE=10,C=10,max_interventions=1,gate_threshold=.05,D=[241,242],G0=[341,342],control_hz=30,physics_hz=400,action_scale=.015,camera='corner2',RGB=[480,480],holder_policy='all8off_entire_formal_wave',renderer='NVIDIA_EGL'),cross_host_timing_not_strictly_comparable=True,statistical_limits='Conditional on fixed50 tasks and these source identities; no retraining uncertainty or multiplicity correction; degenerate within-task empirical variance possible.',missing_sources=len(missing),A_waits_for_B=False,final_episodes=str(ROOT/'FINAL_EPISODES.csv'),final_tasks=str(ROOT/'FINAL_TASKS.csv'),final_pairs=str(ROOT/'FINAL_PAIRED.json'))
    csv_write(ROOT/'FINAL_EPISODES.csv',episodes);csv_write(ROOT/'FINAL_TASKS.csv',task_table);csv_write(ROOT/'FINAL_CELLS.csv',[{k:v for k,v in x.items() if not isinstance(v,dict)} for x in cells]);csv_write(ROOT/'FINAL_PAIRED.csv',paired)
    atomic_json(ROOT/'FINAL_PAIRED.json',paired);atomic_json(ROOT/'FINAL_MISSING.json',missing);atomic_json(ROOT/'FINAL_SUMMARY.json',report)
    atomic_json(CAMPAIGN/'receipts/B/B_D24_R_H20_H30_V1_RESULT.json',dict(report,result_root=str(ROOT),chain_result=str(ROOT/'chain/CHAIN_RESULT.json')))
    text=['B R-H20/H30 terminal results; saved science only.','', '| H | Success / valid | Technical | Unknown | Unstarted |','|---|---:|---:|---:|---:|']
    text += [f"| {x['H']} | {x['successes']} / {x['valid']} | {x['technical_failures']} | {x['execution_unknown']} | {x['unstarted']} |" for x in cells]
    text += ['', 'Paired R-N, Post-R, Velocity-R and rescued/harmed counts: FINAL_PAIRED.json/CSV. Fixed50-task within-task bootstrap2000/seed20260921, same draws across contrasts. NVIDIA EGL,30/400Hz,.015,H20/30,C10,once1; frozen A science, no new fitting. B-host timing is not strictly comparable to A-host timing.','']
    (ROOT/'FINAL_SUMMARY.md').write_text('\n'.join(text));print(json.dumps(dict(status=report['status'],attempts=attempts,valid=sum(x['valid'] for x in cells),technical=sum(x['technical_failures'] for x in cells))))

if __name__=='__main__':main()
