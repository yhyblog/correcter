"""CPU recovery export: eligible result once per key, old raw costs retained separately."""
import csv,io,os,traceback
from pathlib import Path
from collections import defaultdict,Counter
from paths import ROOT,TASK,ORIGINAL
from qio import read,new_json,atomic_json,utc
from admission import frozen_units

_CACHE={}
def cached(p):
    if str(p) not in _CACHE:_CACHE[str(p)]=read(p)
    return _CACHE[str(p)]

def records():
    rows=[];old=[]
    for u in frozen_units().values():
        prior=Path(u['prior_result']);raw=cached(prior)
        if raw['unit_id']!=u['unit_id']:raise ValueError('prior attempt identity mismatch')
        old.append(dict(raw,result_path=str(prior),scientific_eligible=False,disposition='quality_hold_pre_Q_path_divergence',reused=False,recovery=False))
        p=ROOT/'episodes'/u['uid_hash']/'RESULT.json'
        if p.exists():
            row=cached(p)
            for k in ('unit_id','source_id','env_seed','policy_seed','method','mode','H'):
                if row[k]!=u[k]:raise ValueError('recovery result identity mismatch:'+k)
            valid=row['status']=='complete' and row.get('observation_integrity')=='process_isolated_actual_frames' and isinstance(row.get('success'),bool)
            rows.append(dict(row,result_path=str(p),reused=False,recovery=True,scientific_eligible=valid,disposition='recovered_terminal' if valid else 'technical_missing'))
    for u in read(ROOT/'REUSED_UNITS.json'):
        p=Path(u['original_source']['result_path']);row=cached(p)
        if row['status']!='complete' or row['success']!=u['success'] or row['loss']!='L11' or row['fit_seed']!=9101:raise ValueError('reused valid L11 identity mismatch')
        rows.append(dict(row,unit_id=u['unit_id'],cell_id=f"L11_{u['method']}_{u['mode']}_H{u['H']}",result_path=str(p),reused=True,recovery=False,scientific_eligible=True,disposition='original_valid_exact_reuse'))
    if len({x['unit_id'] for x in rows})!=len(rows):raise ValueError('duplicate eligible scientific keys')
    return rows,old

def write_csv(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row));buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=keys);w.writeheader();w.writerows(rows)
    tmp=path.with_name(path.name+'.update.'+str(os.getpid()));tmp.write_text(buf.getvalue());tmp.replace(path)

def cost(rows,name,nested=False):
    values=[x.get('counters',{}).get(name) if nested else x.get(name) for x in rows]
    return sum(x for x in values if x is not None),sum(x is None for x in values)

def export():
    rows,old=records();groups=defaultdict(list)
    for row in rows:groups[row['cell_id']].append(row)
    entered=Counter(u['cell_id'] for u in frozen_units().values() if (ROOT/'unit_claims'/(u['uid_hash']+'.json')).exists());cells=[]
    for method in ('Post','Velocity'):
        for mode in ('G0-multi','G0-once'):
            cid=f'L11_{method}_{mode}_H10';rs=groups[cid];valid=[x for x in rs if x['scientific_eligible']];new=[x for x in rs if not x['reused']];reused=sum(x['reused'] for x in valid);unknown={}
            costs={}
            for k,nested in [('sampling_calls',False),('flow_calls',False),('action_gradients',True),('interventions',False),('elapsed_seconds',False)]:
                total,missing=cost(valid,k,nested);costs['elapsed_seconds_sum' if k=='elapsed_seconds' else k]=total if missing==0 else None
                if missing:unknown[k]=dict(missing_records=missing,known_subtotal=total,reason='not recorded; not imputed')
            cells.append(dict(cell_id=cid,method=method,mode=mode,H=10,loss='L11',fit_seed=9101,planned=500,valid=len(valid),new_valid=len(valid)-reused,reused_valid=reused,successes=sum(x['success'] is True for x in valid),success_rate=sum(x['success'] is True for x in valid)/len(valid) if valid else None,technical_failures=sum(not x['scientific_eligible'] for x in new),attempts=entered[cid],inflight=entered[cid]-len(new),unentered=(450 if mode=='G0-multi' else 500)-entered[cid],complete=len(valid)==500,current_paper=method=='Post',reused_overlap_selection=bool(reused),sum_episode_time_is_not_wave_wall=True,cost_unknown=unknown,**costs))
    counter=read(ROOT/'ATTEMPT_COUNTER.json') if (ROOT/'ATTEMPT_COUNTER.json').exists() else {'count':0}
    validnew=[x for x in rows if x['scientific_eligible'] and not x['reused']]
    summary=dict(utc=utc(),task_id=TASK,cells={c['cell_id']:c for c in cells},actual_attempts=counter['count'],local_new_attempts=counter['count'],new_scientific_units=0,recovered_valid=len(validnew),valid_new=len(validnew),valid_total=sum(x['scientific_eligible'] for x in rows),technical_missing=sum(not x['scientific_eligible'] and not x['reused'] for x in rows),unentered=1900-counter['count'],compute_complete=len(validnew)==1900,prior_A_attempts=23396,A_cumulative_attempts=23396+counter['count'],new_training_updates=0,reused_valid=100,old_raw_attempts_preserved=1900,old_H30_transferred_to_B=True,selection_fixed='explicit user L11/fit9101 unchanged',Velocity_current_paper=False)
    write_csv(ROOT/'ALL_CELLS.csv',cells);write_csv(ROOT/'POST_PAPER_CELLS.csv',[c for c in cells if c['method']=='Post']);write_csv(ROOT/'VELOCITY_OTHER_WORK_CELLS.csv',[c for c in cells if c['method']=='Velocity'])
    fields=['unit_id','source_id','task','env_seed','policy_seed','method','mode','H','loss','fit_seed','status','success','steps','interventions','sampling_calls','flow_calls','elapsed_seconds','reused','recovery','scientific_eligible','disposition','result_path']
    write_csv(ROOT/'EPISODES.csv',[{k:x.get(k) for k in fields} for x in rows]);write_csv(ROOT/'ALL_RAW_ATTEMPTS.csv',[{k:x.get(k) for k in fields} for x in old+rows])
    write_csv(ROOT/'OLD_QUALITY_HOLD_COST.csv',[{k:x.get(k) for k in fields} for x in old])
    missing=[dict(unit_id=u['unit_id'],source_id=u['source_id'],cell_id=u['cell_id'],reason='technical_missing' if any(x['unit_id']==u['unit_id'] and not x['scientific_eligible'] for x in rows) else 'entered_without_terminal' if (ROOT/'unit_claims'/(u['uid_hash']+'.json')).exists() else 'unentered') for u in frozen_units().values() if u['unit_id'] not in {x['unit_id'] for x in validnew}]
    atomic_json(ROOT/'MISSING_UNITS.json',missing);atomic_json(ROOT/'SUMMARY.json',summary);atomic_json(ROOT/'FINAL_SUMMARY.json',summary)
    atomic_json(ROOT/'PUBLICATION.json',dict(utc=utc(),scientific_compute=0,status='published',results=str(ROOT/'EPISODES.csv'),Post=str(ROOT/'POST_PAPER_CELLS.csv'),Velocity_other_work=str(ROOT/'VELOCITY_OTHER_WORK_CELLS.csv'),all_raw_attempts=str(ROOT/'ALL_RAW_ATTEMPTS.csv'),prior_costs=str(ROOT/'OLD_QUALITY_HOLD_COST.csv'),lineage=str(ROOT/'ATTEMPT_LINEAGE.jsonl'),cost_scope='actual recovery plus explicitly tagged valid reuse; prior quality-held raw costs retained separately, not erased or mixed into current success denominators'))
    for cell in cells:
        ep=ROOT/'outbox'/(cell['cell_id']+'.json')
        if cell['complete'] and not ep.exists():new_json(ep,dict(event_id=TASK+'_'+cell['cell_id'],kind='cell_terminal',synthetic=False,utc=utc(),summary=cell,result=str(ROOT/'PUBLICATION.json')))
    return summary

def publish(*_,**kw):
    try:
        s=export();row=dict(status='published',attempts=1,utc=utc(),publication=str(ROOT/'PUBLICATION.json'),valid_new=s['valid_new'])
    except BaseException as e:row=dict(status='publication_error',attempts=1,utc=utc(),type=type(e).__name__,message=str(e),traceback=traceback.format_exc(),scientific_workers_must_continue=True)
    atomic_json(ROOT/'PUBLICATION_STATE.json',row);return row
