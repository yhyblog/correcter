"""Development-only E6 calibration and saved-result reporting; no model calls."""
from collections import Counter, defaultdict
from paths import ROOT
from qio import read,new_json,sha,utc

def ensure_threshold():
    if (ROOT/'phases/THRESHOLD.json').exists():return True
    if (ROOT/'E6_CALIBRATION_BLOCKED.json').exists():return False
    try:
        jobs=[read(p) for p in (ROOT/'jobs').glob('E6_DEV_*.json')]
        episodes=[]
        for job in jobs:
            p=ROOT/'runs'/job['job_id']/'RESULT.json'
            if not p.exists():raise ValueError('development job missing complete result: '+job['job_id'])
            result=read(p)
            if result['status']!='complete':raise ValueError('development technical failure; no partial calibration')
            episodes.extend(result['episodes'])
        expected={s['parent_episode_id'] for s in read(ROOT/'config/E6_SOURCES.json')['development']}
        if len(episodes)!=100 or {e['parent_episode_id'] for e in episodes}!=expected:raise ValueError('100 fixed development parents required')
        keys=('parent_episode_id','source_id','split','eligible_scores','g0_intervened','causal_D5_action_alignment_verified','compared_windows')
        traces=[{k:e[k] for k in keys} for e in episodes]
        phase=ROOT/'phases'
        new_json(phase/'DEVELOPMENT_TRACES.json',traces)
        identities=[read(p)['DG0'] for p in (ROOT/'chain/workers').glob('*/AUXILIARY_IDENTITY.json')]
        if not identities or any(x!=identities[0] for x in identities):raise ValueError('same frozen D/G0 identity required')
        manifest=dict(synthetic=False,split='development',horizon=5,downstream='R',
            episodes=dict(path=str(phase/'DEVELOPMENT_TRACES.json'),sha256=sha(phase/'DEVELOPMENT_TRACES.json')),
            frozen_D_identity=identities[0],source_table_sha256=sha(ROOT/'config/E6_SOURCES.json'),
            selection_outcome_labels_included=False,utc=utc())
        new_json(phase/'DEVELOPMENT_MANIFEST.json',manifest)
        from calibrate_e6 import calibrate
        result=calibrate(phase/'DEVELOPMENT_MANIFEST.json',phase/'THRESHOLD.json')
        new_json(phase/'THRESHOLD_READY.json',dict(utc=utc(),threshold=result,source_table_sha256=manifest['source_table_sha256'],test_entry_before_freeze=False))
        return True
    except Exception as error:
        import traceback
        new_json(ROOT/'E6_CALIBRATION_BLOCKED.json',dict(utc=utc(),reason=str(error),traceback=traceback.format_exc(),test_admitted=False))
        return False

def final_e6(summary):
    rows=[]
    for p in (ROOT/'runs').glob('*/RESULT.json'):
        job=read(p)
        for ep in job['episodes']:
            row={k:v for k,v in ep.items() if k not in ('events','plans')}
            row['result_path']=str(p.parent/'episodes'/ep['source_id']/'RESULT.json')
            rows.append(row)
    new_json(ROOT/'E6_EPISODES.json',rows)
    test=[r for r in rows if r['split']=='test' and r['status']=='complete']
    paired=defaultdict(dict)
    for row in test:paired[row['source_id']][row['method']]=row['success']
    outcomes=Counter('both_success' if x['G0'] and x['D5'] else 'G0_only' if x['G0'] else 'D5_only' if x['D5'] else 'both_failure'
        for x in paired.values() if set(x)=={'G0','D5'})
    cells={}
    for method in ('DEV','G0','D5'):
        selected=[r for r in rows if r['method']==method]
        valid=[r for r in selected if r['status']=='complete']
        cells[method]=dict(attempts=len(selected),terminal_episodes=len(valid),successes=sum(r['success'] is True for r in valid),
            technical_failures=len(selected)-len(valid),interventions=sum(r['interventions'] for r in valid),
            alarm_episodes=sum(r['interventions']>0 for r in valid) if method!='DEV' else None,
            sampling_calls=sum(r['sampling_calls'] for r in valid),flow_calls=sum(r['flow_calls'] for r in valid),
            elapsed_episode_seconds=sum(r['elapsed_seconds'] for r in selected))
    complete=len(rows)==200 and len(test)==100 and cells['DEV']['terminal_episodes']==100
    new_json(ROOT/'E6_FINAL_SUMMARY.json',dict(status='complete' if complete else 'partial_or_failed',utc=utc(),
        cells=cells,paired_test_sources=sum(set(v)=={'G0','D5'} for v in paired.values()),paired_outcomes=dict(outcomes),
        threshold=read(ROOT/'phases/THRESHOLD.json') if (ROOT/'phases/THRESHOLD.json').exists() else None,
        renderer='same A NVIDIA EGL in both arms',downstream='R',H=10,C=10,max_interventions=1,
        training_coverage='frozen historical five tasks',test_identity='five tasks ordinals10..19; not the A main-table first10',
        optimizer_updates=0,callback_next='continue ready E3 units under existing authorization; do not rerun E6'))
