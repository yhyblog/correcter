"""CPU-only merged source tables, paired outcomes, cuts and all attempt costs."""
import csv, importlib.util, json, sys
from collections import Counter
from queue_common import *
from inventory import inventory

def csvfile(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False,allow_nan=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
    os.replace(temp,path)

def paired(ours,old):
    ids=sorted(set(ours)&set(old));rescued=sum(ours[s]['success'] and not old[s]['success'] for s in ids);harmed=sum(old[s]['success'] and not ours[s]['success'] for s in ids)
    return dict(paired_valid=len(ids),rescued=rescued,harmed=harmed,difference_pp=100*(rescued-harmed)/len(ids) if ids else None,missing_imputed=False)

def export(root):
    root=Path(root);inv=inventory(root);dest=ROOT/'tables'/root.name;dest.mkdir(parents=True,exist_ok=True)
    rows=[];cells=[];cuts=[];methodsets={};costs=Counter();encoder=Counter();numeric=Counter()
    for uid,definition in inv['expected'].items():
        raw=inv['states'].get(uid,{});good=policy.legal_terminal(raw);s=definition['source'];cell=definition.get('cell_id',definition['method']+'_H30')
        status=raw.get('status','unknown_entered' if uid in inv['claims'] else 'not_started')
        row=dict(unit_id=uid,cell_id=cell,H=definition['H'],method=definition['method'],source_id=s['source_id'],task=s['task'],status=status,success=raw['success'] if good else None,attempts=len(inv['claims'].get(uid,{})),result_path=raw.get('result_path'),log_derived=raw.get('log_derived',False),interventions=raw.get('interventions'),first_cut=raw.get('first_cut'))
        rows.append(row)
        if not good:continue
        if root==X:
            from_source=['reset_seed','policy_seed'];triggered=[e for e in raw.get('events',[]) if e.get('trigger')]
            if raw['first_cut']!=(triggered[0]['step'] if triggered else None) or raw['interventions']!=len(triggered):raise ValueError('X first_cut/trigger count')
            last=-10
            for e in triggered:
                if e['step']-last<10 or e['commit_until']!=e['step']+10 or not e['legal_cut'] or not e['gate']>.05 or e['restore_native_K']!=10 or e['Q_acceptance_gate']:raise ValueError('X C10 cut contract')
                last=e['step'];cuts.append(dict(unit_id=uid,cell_id=cell,method=row['method'],**e))
            enc=raw['encoder_counters'];factor=1 if row['method']=='Post' else 3
            if enc.get('Q_ensemble_forward_calls',0)!=factor*len(triggered) or enc.get('action_gradient_calls',0)!=factor*len(triggered):raise ValueError('X Q/gradient call accounting')
            if raw['counters']['policy_flow_calls']!=10*raw['counters']['policy_queries']:raise ValueError('X NFE call accounting')
        else:
            if (raw['control_hz'],raw['physics_hz'],raw['action_scale'],raw['H'],raw['mode'])!=(30,400,.015,row['H'],'G0-multi'):raise ValueError('pi05 physical contract')
            triggered=[e for e in raw['events'] if e.get('intervention_executed')];xs=[e['step'] for e in triggered]
            if xs!=raw['intervention_cuts'] or len(xs)!=raw['interventions'] or raw['first_cut']!=(xs[0] if xs else None) or any(b-a<10 for a,b in zip(xs,xs[1:])):raise ValueError('pi05 C10/first_cut')
            for e in triggered:
                if not e['old_tail_discarded'] or e['restore_native_H']!=row['H'] or e['commit_until']!=e['step']+10:raise ValueError('pi05 cut contract')
                cuts.append(dict(unit_id=uid,cell_id=cell,method=row['method'],**e))
        methodsets.setdefault((row['H'],row['method']),{})[s['source_id']]=raw
    for key in sorted({r['cell_id'] for r in rows}):
        group=[r for r in rows if r['cell_id']==key];good=[r for r in group if r['status']=='complete' and type(r['success']) is bool]
        cells.append(dict(cell_id=key,H=group[0]['H'],method=group[0]['method'],planned=len(group),valid=len(good),successes=sum(r['success'] for r in good),success_rate=sum(r['success'] for r in good)/len(good) if good else None,technical=sum(r['status']=='technical_failure' for r in group),unknown=sum(r['status']=='unknown_entered' for r in group),unstarted=sum(r['status']=='not_started' for r in group),interventions=sum(r['interventions'] or 0 for r in good)))
    for r in inv['attempts']:
        costs.update(r.get('counters') or {});encoder.update(r.get('encoder_counters') or {});numeric.update(r.get('numeric_counters') or {})
    worker_records=[];loading=[];worker_totals=Counter();worker_returns=Counter();worker_methods=Counter();worker_encoder=Counter();encoder_meter_entered=Counter();encoder_meter_returned=Counter()
    for run in runs(root):
        if root==X:
            patterns=['stages/evaluate/workers/*/CLIENT_RESULT.json','stages/evaluate/workers/*/encoder/RESULT.json']
        else:patterns=['chains/evaluate/workers/*/WORKER_EXIT.json']
        for pattern in patterns:
            for p in run.glob(pattern):
                r=read(p);worker_records.append(dict(path=str(p),record=r))
                if root==P:
                    worker_totals.update(r.get('numeric',{}).get('entered',{}));worker_returns.update(r.get('numeric',{}).get('returned',{}));worker_methods.update(r.get('method_counts') or {})
                else:
                    worker_totals.update(r.get('counters') or {})
                    worker_encoder.update(r.get('counts') or {})
                    encoder_meter_entered.update(r.get('meter',{}).get('entered',{}));encoder_meter_returned.update(r.get('meter',{}).get('returned',{}))
        for pattern in ['stages/evaluate/workers/*/MODEL_READY.json','stages/evaluate/workers/*/encoder/READY.json','chains/evaluate/workers/*/MODEL_READY.json']:
            for p in run.glob(pattern):loading.append(dict(path=str(p),record=read(p)))
    pairs=[];refs=[]
    if root==X:
        prior=read(C/'work/C/C_D24_MW_VELOCITY_V1_r2/MW_VELOCITY_BATCH.json');p=Path(prior['baseline_index']);baseline={r['source_id']:r for r in read(p)['xvla']};refs.append(str(p))
        for (H,m),ours in methodsets.items():
            pairs.append(dict(H=H,method=m,reference='N',**paired(ours,baseline)))
            for name,oldroot in [('oldQ_once',C/'results/C/C_D24_XVLA_AUX_RETRAIN_V1'),('oldQ_multi',C/'results/C/C_D24_XVLA_MULTI_EVAL_V1')]:
                old={}
                for p in (oldroot/'evaluation'/m).glob('*/RESULT.json'):
                    r=read(p)
                    if policy.legal_terminal(r):old[r['source_id']]=r
                pairs.append(dict(H=H,method=m,reference=name,**paired(ours,old)));refs.append(str(oldroot/'evaluation'/m))
    else:
        # Reuse the established, read-only baseline source definitions. Import in
        # this short separate CPU process so scientific module globals stay local.
        sys.path.insert(0,str(P/'code'))
        spec=importlib.util.spec_from_file_location('pi05_report_refs',P/'code/report.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        baseline,evidence=mod.references();refs=evidence
        for (H,m),ours in methodsets.items():
            for (rh,name),old in baseline.items():
                if rh==H:pairs.append(dict(H=H,method=m,reference=name,**paired(ours,old)))
    csvfile(dest/'SOURCE_TERMINALS.csv',rows);csvfile(dest/'CELLS.csv',cells);csvfile(dest/'MISSING.csv',[r for r in rows if type(r['success']) is not bool]);csvfile(dest/'PAIRED.csv',pairs);csvfile(dest/'CUTS.csv',cuts)
    csvfile(dest/'POST_PAPER_CELLS.csv',[r for r in cells if r['method']=='Post']);csvfile(dest/'POST_PAPER_PAIRED.csv',[r for r in pairs if r['method']=='Post']);csvfile(dest/'VELOCITY_OTHER_WORK_CELLS.csv',[r for r in cells if r['method']=='Velocity'])
    atomic_json(dest/'ALL_ATTEMPT_COSTS.json',dict(utc=utc(),episode_counters=dict(costs),episode_encoder=dict(encoder),episode_numeric=dict(numeric),whole_worker_entered=dict(worker_totals),whole_worker_returned=dict(worker_returns),whole_worker_methods=dict(worker_methods),whole_worker_encoder=dict(worker_encoder),encoder_meter_entered=dict(encoder_meter_entered),encoder_meter_returned=dict(encoder_meter_returned),worker_records=worker_records,loading=loading,attempts=[{k:r.get(k) for k in ['unit_id','status','success','result_path','counters','encoder_counters','numeric_counters','elapsed_seconds','error','technical_failure']} for r in inv['attempts']],unknown_costs_not_imputed=True,holder_runtime_separate=True,all8_holders_off_during_formal=True))
    summary=dict(utc=utc(),task_id=root.name,expected=len(rows),valid=sum(type(r['success']) is bool for r in rows),missing=sum(type(r['success']) is not bool for r in rows),cells=cells,runs=list(map(str,runs(root))),source_exact=True,claim_attempts=sum(len(r) for r in inv['claims'].values()),Post_paper=True,Velocity_other_work=True,baseline_references=refs,paired_intervals='Original per-task report retains its intervals; merged exact pairs here are descriptive.',original_results_unchanged=True)
    atomic_json(dest/'SUMMARY.json',summary);return summary

if __name__=='__main__':print(json.dumps(export(Path(sys.argv[1])),ensure_ascii=False))
