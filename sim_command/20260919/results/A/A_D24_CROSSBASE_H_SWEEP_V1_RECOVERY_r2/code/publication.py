"""Derived exports never abort a scientific worker. Original terminals are immutable."""
import csv,io,os,time,traceback
from pathlib import Path
from collections import Counter
from paths import ROOT,TASK,EVENT_PREFIX,CONFIG
from qio import read,new_json,atomic_json,utc,ref
from admission import frozen_units,unit_hash,cell_id
from publication_data import finite_values
_CACHE={}

def table(path,rows,fields):
    text=io.StringIO();w=csv.DictWriter(text,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    temp=Path(str(path)+'.pending');temp.write_text(text.getvalue());os.replace(temp,path)

def summarize():
    rows=[];cells={};missing=[];claims={};technical=[]
    for uid,u in frozen_units().items():
        key=unit_hash(u);ep=ROOT/'episodes'/key;cp=ROOT/'unit_claims'/(key+'.json')
        if cp.exists():claims[uid]=read(cp)
        if uid not in _CACHE and (ep/'RESULT.json').exists():
            x=read(ep/'SUMMARY_ROW.json' if (ep/'SUMMARY_ROW.json').exists() else ep/'RESULT.json')
            for f in ('unit_id','source_id','method','mode','H','Q_loss','Q_fit_seed'):
                if x[f]!=u[f]:raise ValueError('result/manifest mismatch '+f)
            if x['reset_seed']!=u['env_seed'] or x['policy_seed']!=u['policy_seed']:raise ValueError('seed mismatch')
            _CACHE[uid]=dict(x,result_path=str(ep/'RESULT.json'))
        x=_CACHE.get(uid);cid=cell_id(u)
        if cid not in cells:cells[cid]=dict(cell_id=cid,model='SmolVLA',H=u['H'],raw_plan_length=50,C=u['C'],method=u['method'],mode=u['mode'],Q_loss=u['Q_loss'],Q_fit_seed=u['Q_fit_seed'],current_paper=u['current_paper'],planned=0,attempts=0,valid=0,successes=0,technical_failures=0,unentered=0,inflight=0,interventions=0,policy_queries=0,policy_flow_calls=0,monitor_calls=0,Q_ensemble_forward_calls=0,Q_member_forward_calls=0,action_gradient_calls=0,elapsed_seconds_sum=0.,cost_unknown={})
        c=cells[cid];c['planned']+=1;c['attempts']+=uid in claims
        if x:
            if uid not in claims or x['claim']!=claims[uid]:raise ValueError('terminal without exact claim')
            valid=x['status']=='complete' and type(x['success']) is bool
            out={k:v for k,v in x.items() if k not in ('events','claim')};out['valid']=valid;rows.append(out)
            if valid:c['valid']+=1;c['successes']+=int(x['success'])
            else:c['technical_failures']+=1;technical.append(dict(unit_id=uid,status=x['status'],error=x.get('error'),result_path=x['result_path']))
            # All entered work is billed, including partial/technical outcomes.
            for name,bag in [('interventions',x),('elapsed_seconds_sum',{'elapsed_seconds_sum':x.get('elapsed_seconds')}),('policy_queries',x.get('counters',{})),('policy_flow_calls',x.get('counters',{})),('monitor_calls',x.get('encoder_counters',{})),('Q_ensemble_forward_calls',x.get('encoder_counters',{})),('Q_member_forward_calls',x.get('encoder_counters',{})),('action_gradient_calls',x.get('encoder_counters',{}))]:
                value=bag.get(name)
                if value is None:c['cost_unknown'][name]=c['cost_unknown'].get(name,0)+1
                else:c[name]+=value
            if not valid:missing.append(dict(unit_id=uid,reason=x['status'],result_path=x['result_path']))
        elif uid in claims:
            c['inflight']+=1;missing.append(dict(unit_id=uid,reason='entered_without_terminal'))
        else:
            c['unentered']+=1;missing.append(dict(unit_id=uid,reason='not_entered'))
    for c in cells.values():
        c['success_rate']=c['successes']/c['valid'] if c['valid'] else None
        c['complete']=c['valid']==c['planned'];c['sum_episode_time_is_not_wave_wall']=True
    summary=dict(task_id=TASK,run_id=CONFIG['run_id'],scope='only_original_incomplete_units',previous_valid_preserved=2061,previous_stage_attempts=CONFIG['previous_stage_attempts'],original_stage_cumulative_attempts=CONFIG['previous_stage_attempts']+len(claims),utc=utc(),cells=cells,actual_attempts=len(claims),valid_new=sum(c['valid'] for c in cells.values()),technical_missing=len(technical),entered_without_terminal=sum(c['inflight'] for c in cells.values()),unentered=sum(c['unentered'] for c in cells.values()),compute_complete=all(c['complete'] for c in cells.values()),new_training_updates=0,H10_rerun=0,prior_A_attempts=CONFIG['prior_A_attempts'],A_cumulative_attempts=CONFIG['prior_A_attempts']+len(claims),Velocity_current_paper=False)
    return summary,rows,missing,technical

def publish(terminal=False,force=False):
    sp=ROOT/'PUBLICATION_STATE.json';old=read(sp) if sp.exists() else dict(attempts=0)
    try:
        s,rows,missing,technical=summarize()
        fields=['cell_id','model','H','raw_plan_length','C','method','mode','Q_loss','Q_fit_seed','planned','attempts','valid','successes','success_rate','technical_failures','inflight','unentered','interventions','policy_queries','policy_flow_calls','monitor_calls','Q_ensemble_forward_calls','Q_member_forward_calls','action_gradient_calls','elapsed_seconds_sum','cost_unknown','complete','current_paper']
        cells=list(s['cells'].values());table(ROOT/'FINAL_CELLS.csv',cells,fields)
        table(ROOT/'POST_PAPER_CELLS.csv',[x for x in cells if x['method'] in ('N','R','Post')],fields)
        table(ROOT/'VELOCITY_OTHER_WORK_CELLS.csv',[x for x in cells if x['method']=='Velocity'],fields)
        table(ROOT/'FINAL_EPISODES.csv',rows,['unit_id','source_id','task','reset_seed','policy_seed','model','H','raw_plan_length','C','method','mode','Q_loss','Q_fit_seed','status','valid','success','steps','interventions','first_cut','elapsed_seconds','counters','encoder_counters','error','result_path'])
        atomic_json(ROOT/'MISSING_UNITS.json',dict(utc=utc(),units=missing));atomic_json(ROOT/'TECHNICAL_FAILURES.json',dict(utc=utc(),units=technical))
        atomic_json(ROOT/'SUMMARY.json',s)
        if terminal:atomic_json(ROOT/'FINAL_SUMMARY.json',s)
        atomic_json(ROOT/'PUBLICATION.json',dict(utc=utc(),status='published',cells=str(ROOT/'FINAL_CELLS.csv'),episodes=str(ROOT/'FINAL_EPISODES.csv'),Post=str(ROOT/'POST_PAPER_CELLS.csv'),Velocity_other_work=str(ROOT/'VELOCITY_OTHER_WORK_CELLS.csv'),missing=str(ROOT/'MISSING_UNITS.json'),scientific_compute=0))
        for key,c in s['cells'].items():
            ep=ROOT/'outbox'/(key+'.json')
            if c['complete'] and not ep.exists():new_json(ep,dict(event_id=EVENT_PREFIX+'_'+key,kind='cell_terminal',synthetic=False,result=str(ROOT/'PUBLICATION.json'),summary=c,utc=utc()))
        from combined_publication import publish_combined
        publish_combined(s,rows,terminal,table)
        state=dict(status='published',attempts=old.get('attempts',0)+1,valid_new=s['valid_new'],utc=utc(),publication=str(ROOT/'PUBLICATION.json'))
    except Exception as exc:
        state=dict(status='publication_error',attempts=old.get('attempts',0)+1,error=repr(exc),traceback=traceback.format_exc(),utc=utc(),science_workers_must_continue=True)
        new_json(ROOT/'publication_errors'/(str(time.time_ns())+'.json'),state)
    atomic_json(sp,finite_values(state));return state
