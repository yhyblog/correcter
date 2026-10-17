"""Terminal-only CPU aggregation and fixed-task paired bootstrap; no model imports."""
import csv
import io
import math
from collections import Counter
from pathlib import Path
import numpy as np
from paths import ROOT, CAMPAIGN
from qio import read, atomic_json, utc

def csv_write(path, rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    s=io.StringIO(newline='');writer=csv.DictWriter(s,fieldnames=keys)
    writer.writeheader();writer.writerows(rows)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(s.getvalue());tmp.replace(path)

def main():
    sources=[s for s in read(ROOT/'config/TEST_SOURCES_V1.json')['rows'] if s['ordinal']<10]
    tasks=sorted({s['task'] for s in sources})
    expected={s['source_id']:s for s in sources}
    rows=[];maps={40:{},50:{}}
    for p in sorted((ROOT/'runs').glob('*/episodes/*/RESULT.json')):
        x=read(p);H=x['H'];sid=x['source_id']
        if H not in maps or sid in maps[H]:raise ValueError('Duplicate or wrong R source')
        if x['method']!='R' or any(x[k]!=expected[sid][k] for k in ('task','env_seed','policy_seed','ordinal')):
            raise ValueError('Source identity changed')
        if (x['control_hz'],x['physics_hz'],x['action_scale'],x['max_interventions'])!=(30,400,.015,1):
            raise ValueError('Physical/G0 contract changed')
        if x['status']=='complete':
            if type(x['success']) is not bool or x['interventions'] not in (0,1):raise ValueError('Invalid terminal')
            if any(not math.isfinite(x[k]) or x[k]<0 for k in ('elapsed_seconds','environment_seconds','inference_seconds')):
                raise ValueError('Nonfinite core cost')
        maps[H][sid]=x
        row={k:v for k,v in x.items() if not isinstance(v,(dict,list))}
        row.update(result_path=str(p),**{'counter_'+k:v for k,v in x['counters'].items()})
        rows.append(row)
    claims=[read(p) for p in (ROOT/'unit_claims').glob('*.json')]
    if len(claims)>1100 or 1013+len(claims)>2400:raise ValueError('C attempt cap exceeded')
    cells={};task_rows=[]
    for H in (40,50):
        records=list(maps[H].values());valid=[x for x in records if x['status']=='complete']
        attempted=[x for x in claims if x['H']==H]
        technical=sum(x['status']=='technical_failure' for x in records)
        cell=dict(H=H,method='R',planned=500,attempts=len(attempted),valid=len(valid),
            successes=sum(x['success'] for x in valid),technical_failures=technical,
            unknown_entered=max(0,len(attempted)-len(records)),not_started=500-len(attempted),
            complete=len(valid)==500,terminal_success_rate=sum(x['success'] for x in valid)/len(valid) if valid else None,
            success_rate_scope='valid terminals only; technical/unknown/not-started excluded, not false',
            interventions=dict(Counter(str(x['interventions']) for x in valid)),
            elapsed_seconds=sum(x['elapsed_seconds'] for x in records),
            inference_seconds=sum(x.get('inference_seconds',0.) for x in records),
            environment_seconds=sum(x['environment_seconds'] for x in records),
            flow_calls=sum(x.get('flow_calls',0) for x in records),policy_calls=sum(x.get('policy_calls',0) for x in records))
        cells['R_H'+str(H)]=cell
        atomic_json(ROOT/'cells'/('R_H'+str(H)+'_SUMMARY.json'),dict(utc=utc(),terminal=True,**cell))
        for task in tasks:
            values=[x for x in records if x['task']==task];good=[x for x in values if x['status']=='complete']
            entered=sum(x['source']['task']==task for x in attempted)
            task_rows.append(dict(H=H,method='R',task=task,planned=10,attempts=entered,valid=len(good),
                successes=sum(x['success'] for x in good),technical_failures=sum(x['status']=='technical_failure' for x in values),
                unknown_entered=entered-len(values),not_started=10-entered))
    refs={(h,m):{} for h in (40,50) for m in ('N','Post','Velocity')}
    ap=CAMPAIGN/'results/A/A_D24_MAIN_ONCE_V1/FINAL_EPISODES.csv'
    with ap.open() as f:
        for x in csv.DictReader(f):
            H=int(x['H']);m=x['method']
            if (H,m) not in refs:continue
            for k in ('H','ordinal','env_seed','policy_seed'):x[k]=int(x[k])
            x['success']={'True':True,'False':False}[x['success']]
            refs[H,m][x['source_id']]=x
    for H in (40,50):
        for p in (CAMPAIGN/'deadline_20260924/A/runs').glob(f'N_H{H}_*/RESULT.json'):
            for x in read(p)['episodes']:refs[H,'N'][x['source_id']]=x
    for key,index in refs.items():
        if set(index)!=set(expected) or any(x['status']!='complete' for x in index.values()):
            raise ValueError('Frozen comparison cell incomplete: '+str(key))
        for sid,x in index.items():
            if any(x[k]!=expected[sid][k] for k in ('task','env_seed','policy_seed','ordinal')):raise ValueError('Paired source seed mismatch')
    rng=np.random.default_rng(20260921)
    samples=rng.integers(0,10,size=(2000,50,10))
    paired=[]
    order=[s['source_id'] for task in tasks for s in sorted((s for s in sources if s['task']==task),key=lambda x:x['ordinal'])]
    for H in (40,50):
        good={sid:x for sid,x in maps[H].items() if x['status']=='complete'}
        for label,left,right in [('R-N',good,refs[H,'N']),('Post-R',refs[H,'Post'],good),('Velocity-R',refs[H,'Velocity'],good)]:
            common=[sid for sid in order if sid in left and sid in right]
            differences=np.array([int(left[sid]['success'])-int(right[sid]['success']) for sid in common],dtype=float)
            interval=None
            if len(common)==500:
                matrix=differences.reshape(50,10)
                means=matrix[np.arange(50)[None,:,None],samples].mean(axis=(1,2))*100
                interval=np.quantile(means,[.025,.975]).tolist()
            paired.append(dict(H=H,comparison=label,paired_valid=len(common),left_successes=sum(left[s]['success'] for s in common),
                right_successes=sum(right[s]['success'] for s in common),rescued=int((differences==1).sum()),harmed=int((differences==-1).sum()),
                delta_percentage_points=float(differences.mean()*100) if len(common) else None,
                bootstrap95_low_percentage_points=interval[0] if interval else None,
                bootstrap95_high_percentage_points=interval[1] if interval else None,
                CI_missing_reason=None if interval else 'Complete 50x10 paired cell unavailable; no missingness imputation',
                replicates=2000,seed=20260921,method='fixed 50 tasks; resample 10 sources within each task; shared draws across cells'))
    summary=dict(task_id='C_D24_R_H40_H50_V1',utc=utc(),terminal=True,cells=cells,
        planned=1000,attempts=len(claims),valid=sum(x['valid'] for x in cells.values()),
        prior_C_attempts=1013,cumulative_C_attempts=1013+len(claims),stage_cap=1100,cumulative_cap=2400,
        training_updates=0,optimizer_updates=0,automatic_retries=0,
        paired_statistics='PAIRED_COMPARISONS.csv',cross_host_run=True,
        timing_limitation='A comparisons ran on another host; holder conditions differ. No controlled same-host speed claim.',
        bootstrap_scope='Pointwise percentile intervals conditional on fixed 50 tasks/sources; no multiplicity adjustment, training-seed or task-population uncertainty.')
    atomic_json(ROOT/'SUMMARY.json',summary)
    csv_write(ROOT/'EPISODES.csv',rows);csv_write(ROOT/'TASK_RESULTS.csv',task_rows);csv_write(ROOT/'PAIRED_COMPARISONS.csv',paired)
    atomic_json(ROOT/'PAIRED_COMPARISONS.json',dict(utc=utc(),comparisons=paired,source_table=str(ROOT/'config/TEST_SOURCES_V1.json'),
        existing_A_main=str(ap),existing_N=str(CAMPAIGN/'deadline_20260924/A/runs'),existing_A_results_modified=False))
    text=['# C R_H40 / R_H50 terminal results','',
          'Frozen π0.5-MT50 SFT030000 and A-main scientific code; NVIDIA EGL, corner2 480×480, 30/400 Hz, action scale 0.015, raw50/NFE10, natural G0 > 0.05, at most one C10 replan. Historical five-task D/G0 coverage is unchanged.','']
    for key,c in cells.items():text.append(f"- {key}: {c['successes']}/{c['valid']} valid; technical={c['technical_failures']}, unknown={c['unknown_entered']}, not-started={c['not_started']}.")
    text+=['','Paired R−N, Post−R and Velocity−R comparisons are in PAIRED_COMPARISONS.csv; all use the same source/seed identities. Fixed-task within-task bootstrap: 2000 replicates, numpy.default_rng(20260921), pointwise 95% percentile intervals. Missing results are never failures.','',summary['timing_limitation'],'','No prior Velocity, N or Post evaluation was replayed. No model fit or threshold selection occurred.']
    (ROOT/'REPORT.md').write_text('\n'.join(text)+'\n')
    print(f"Terminal aggregation: {summary['valid']}/1000 valid; {summary['attempts']} physical attempts")

if __name__=='__main__':main()
