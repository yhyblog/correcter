"""Publish saved scientific outcomes; keep user cancellation distinct from failure."""
import json
from pathlib import Path
from collections import Counter
import paths
from paths import ROOT,CONFIG,CAMPAIGN
from qio import read,atomic_json,ref,utc
from report_utils import csv_write,contrast,totals

def publish():
    index=read(ROOT/'SOURCE_INDEX.json');sources=read(index['full_sources']['path'])['sources'];source_map={s['source_id']:s for s in sources}
    claim_rows=[read(p) for p in (ROOT/'claims/attempts').glob('*.json')]
    current=read(ROOT/'ATTEMPT_COUNTER.json')['reserved_attempts'] if (ROOT/'ATTEMPT_COUNTER.json').exists() else 0
    assert current<=CONFIG['stage_attempt_cap'] and current+CONFIG['planned_prior_attempts']<=20000
    assert current+CONFIG.get('carried_stage_attempts',0)<=CONFIG['original_stage_attempt_cap']
    N=read(CAMPAIGN/'work/B/B_D24_E8_POST_V1_r1/VALID_N_INDEX.json')['smolvla']
    N={x['source_id']:x for x in N if x['status']=='complete'}
    cells=[];episodes=[];missing=[];pairs=[];valid_index=[];costs=[]
    for method in CONFIG['methods']:
        rows={}
        for retained in index.get('retained',[]):
            if retained['method']!=method:continue
            r=read(retained['result']['path'])
            rows[r['source_id']]=dict(r,result_path=retained['result']['path'],retained_from_prior=True,
                status=retained.get('disposition',r['status']),original_status=r['status'])
        for p in sorted((ROOT/'evaluation'/method).glob('*/RESULT.json')):
            r=read(p);assert r['source_id'] not in rows,'no prior completed or cancelled unit replay'
            rows[r['source_id']]=dict(r,result_path=str(p),retained_from_prior=False)
        claimed={r['source_id'] for r in claim_rows if r.get('method')==method}|set(rows)
        valid={}
        for sid,r in rows.items():
            assert all(r[k]==source_map[sid][k] for k in ['task','reset_seed','policy_seed'])
            cuts=[e['step'] for e in r['events'] if e['trigger']]
            if r['status']=='complete':
                assert type(r['success']) is bool and r['steps']>0 and len(cuts)==r['interventions']
                assert all(b-a>=10 for a,b in zip(cuts,cuts[1:])) and r['first_cut']==(cuts[0] if cuts else None)
                valid[sid]=r
                valid_index.append(dict(method=method,source_id=sid,result=ref(r['result_path'])))
            else:assert r['success'] is None
            episodes.append(dict({k:v for k,v in r.items() if k!='events'},absolute_cut_sequence=cuts))
        success=sum(r['success'] for r in valid.values());unknown=claimed-set(rows)
        counts=Counter(r['status'] for r in rows.values());interventions=[r['interventions'] for r in valid.values()]
        cell=dict(method=method,mode='multi',planned=500,valid=len(valid),successes=success,success_rate=success/len(valid) if valid else None,
            technical=counts['technical_failure'],budget_truncated=counts['budget_truncated'],user_cancelled=counts['user_cancelled'],
            execution_unknown=len(unknown),unstarted=500-len(claimed),trigger_zero=sum(n==0 for n in interventions),
            trigger_once=sum(n==1 for n in interventions),trigger_multiple=sum(n>1 for n in interventions),intervention_count=sum(interventions),
            interventions_mean=sum(interventions)/len(interventions) if interventions else None,
            valid_policy_environment_counters=totals(valid.values(),'counters'),valid_encoder_auxiliary_counters=totals(valid.values(),'encoder_counters'))
        cells.append(cell)
        for sid in sorted(set(source_map)-set(valid)):
            missing.append(dict(method=method,source_id=sid,status=rows[sid]['status'] if sid in rows else 'execution_unknown' if sid in claimed else 'unstarted',success=None))
        pairs.append(contrast(valid,N,source_map,method+' new multi - frozen N',len(valid)==500))
        if method=='R':
            once_index=read(Path(CONFIG['once_reference_root'])/'VALID_RESULT_INDEX.json')['rows']
            once={r['source_id']:read(r['result']['path']) for r in once_index if r['method']=='R'}
            pairs.append(contrast(valid,once,source_map,'R multi - same D/G0 R once',len(valid)==500))
        faults=[r for r in rows.values() if r['status']!='complete']
        costs.append(dict(method=method,valid_policy_environment=totals(valid.values(),'counters'),valid_encoder=totals(valid.values(),'encoder_counters'),
            cancelled_or_technical_policy_environment=totals(faults,'counters'),cancelled_or_technical_encoder=totals(faults,'encoder_counters')))
    complete=all(r['valid']==500 for r in cells)
    report=dict(status='complete' if complete else 'partial',at_utc=utc(),task_id=CONFIG['task_id'],run_id=CONFIG['run_id'],mode='multi',cells=cells,
        attempts=current+CONFIG.get('carried_stage_attempts',0),current_run_attempts=current,cumulative_B_attempts=CONFIG['planned_prior_attempts']+current,
        new_collection_attempts=0,new_optimizer_updates=0,baseline_N_rerun=False,selected_loss=CONFIG.get('selected_loss'),fit_seed=CONFIG.get('selected_fit_seed'),
        selected_Q_assets=CONFIG.get('selected_Q_assets'),selection_lock=CONFIG.get('selection_lock'),
        scientific_scope='Q-free R continuation' if CONFIG['methods']==['R'] else 'new full Q; frozen Smol D/G0/native bridge; old Q results are historical',
        current_pending_valid=sum(r['status']=='complete' and not r['retained_from_prior'] for r in episodes),
        all_owned_descendants_exited_before_publication=True,missing_not_failure=True,A_waits_for_B=False)
    atomic_json(ROOT/'FINAL_SUMMARY.json',report);atomic_json(ROOT/'FINAL_MISSING.json',missing);atomic_json(ROOT/'PAIRED.json',pairs)
    atomic_json(ROOT/'VALID_RESULT_INDEX.json',dict(mode='multi',rows=valid_index,complete=complete,at_utc=utc()))
    atomic_json(ROOT/'RESOURCE_SUMMARY.json',dict(costs=costs,occupancy_cost_excluded=True,new_training_updates=0,
        external_encoder_processes=[read(p) for p in sorted((ROOT/'runs').glob('*/encoder/RESULT.json'))],
        native_processes=[read(p) for p in sorted((ROOT/'runs').glob('*/CLIENT_RESULT.json'))]))
    csv_write(ROOT/'FINAL_CELLS.csv',cells);csv_write(ROOT/'FINAL_EPISODES.csv',episodes);csv_write(ROOT/'PAIRED.csv',pairs)
    (ROOT/'MASTER_UPDATE.md').write_text('\n'.join([report['scientific_scope'],'']+[r['method']+': '+str(r['successes'])+'/'+str(r['valid'])+' valid; '+str(r['user_cancelled'])+' user-cancelled; '+str(r['unstarted'])+' unstarted.' for r in cells])+'\n')
    atomic_json(CAMPAIGN/CONFIG['result_receipt'],dict(report,result_root=str(ROOT)))
    print(json.dumps(dict(status=report['status'],valid=sum(r['valid'] for r in cells),current_attempts=current)))

if __name__=='__main__':publish()
