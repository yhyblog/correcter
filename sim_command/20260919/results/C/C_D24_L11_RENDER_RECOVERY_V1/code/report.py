"""One scientific result per key, immutable attempt lineage and complete costs."""
import csv,json,collections
from pathlib import Path
from paths import ROOT,TASK,CONFIG
from qio import read,atomic_json,utc,ref
OLD=ROOT.parent/'C_D24_L11_RETEST_V1'
COST_KEYS=('sampling_calls','flow_calls','action_gradient_calls','Q_ensemble_forward','Q_member_forward','D_forward','G0_forward')
def result_path(u):
    return ROOT/('evaluation/'+u['method'] if u['model']=='X-VLA' else 'pi_evaluation/'+u['cell_id'])/u['source_id']/'RESULT.json'
def table(path,rows):
    rows=list(rows);fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def counters(r):
    c=r.get('counters',{});e=r.get('encoder_counters',{});q=e.get('Q_ensemble_forward_calls',c.get('Q_ensemble_forward'))
    return dict(sampling_calls=c.get('policy_queries',c.get('sampling')),flow_calls=c.get('policy_flow_calls',c.get('flow')),action_gradient_calls=e.get('action_gradient_calls',c.get('action_gradients')),Q_ensemble_forward=q,Q_member_forward=q*4 if q is not None else None,D_forward=e.get('D_forward_calls',c.get('D_forward')),G0_forward=e.get('G0_forward_calls',c.get('G0_forward')))
def main():
    units=read(OLD/'UNIT_INDEX.json');recovery={u['unit_id']:u for u in read(ROOT/'UNIT_INDEX.json')}
    protected=set(read(ROOT/'PROTECTED_VALID_UNITS.json')['unit_ids'])
    oldrows={r['unit_id']:r for r in csv.DictReader((OLD/'task_summary/EPISODES.csv').open())}
    if len(units)!=2500 or len(protected)!=736 or set(recovery)&protected or set(recovery)|protected!={u['unit_id'] for u in units}:raise RuntimeError('scientific coverage changed')
    rows=[];cuts=[];errors=[];pairs=collections.defaultdict(collections.Counter);newattempts=[]
    for original in units:
        uid=original['unit_id'];u=recovery.get(uid,original);preserved=uid in protected
        p=Path(oldrows[uid]['result_path']) if preserved else result_path(u)
        r=read(p) if p.exists() else {};claimp=ROOT/'claims/units'/(u['storage_key']+'.json')
        valid=r.get('status')=='complete' and type(r.get('success')) is bool
        if preserved and not valid:raise RuntimeError('protected result no longer terminal')
        disposition='valid' if valid else 'technical_missing' if r.get('status')=='technical_failure' else 'unknown_entered' if claimp.exists() else 'not_entered'
        row=dict(unit_id=uid,cell_id=u['cell_id'],model=u['model'],method=u['method'],H=u['H'],source_id=u['source_id'],task=u['task'],env_seed=u['env_seed'],policy_seed=u['policy_seed'],mode=u['mode'],loss='L11',fit_seed=9101,current_paper=u['current_paper'],disposition=disposition,success=r.get('success') if valid else None,raw_recorded_success=r.get('success'),preserved_prior_valid=preserved,attempt_count=int(oldrows[uid]['attempt_count'])+int(not preserved and claimp.exists()),steps=r.get('steps'),first_cut=r.get('first_cut'),interventions=r.get('interventions'),elapsed_seconds=r.get('elapsed_seconds'),result_path=str(p) if p.exists() else None,old_L01_path=u['original_source']['result_path'],**counters(r))
        rows.append(row)
        if not preserved and claimp.exists():
            claim=read(claimp);newattempts.append(dict(unit_id=uid,run=str(ROOT),attempt=claim['lifetime_attempt'],recovery_attempt=claim['attempt'],status=r.get('status','unknown_entered'),success=r.get('success'),steps=r.get('steps'),result_path=str(p) if p.exists() else None,elapsed_seconds=r.get('elapsed_seconds'),**counters(r)))
        triggered=[e for e in r.get('events',[]) if e.get('trigger',e.get('intervention_executed',False))]
        cut_steps=[e['step'] for e in triggered]
        if valid and (r.get('first_cut')!=(cut_steps[0] if cut_steps else None) or r.get('interventions')!=len(cut_steps) or any(b<a+10 for a,b in zip(cut_steps,cut_steps[1:]))):errors.append(dict(unit_id=uid,kind='first_cut_or_C10_reentry',source=str(p)))
        for e in triggered:
            executed=e.get('C10_steps_executed',min(10,max(0,r.get('steps',0)-e['step'])))
            cuts.append(dict(unit_id=uid,model=u['model'],method=u['method'],H=u['H'],cut=e['step'],first_cut=r.get('first_cut'),intervention_index=e.get('intervention_index'),commit_until=e.get('commit_until'),C10_steps_executed=executed,C10_complete=e.get('C10_complete',executed==10),C10_accounting='recorded' if 'C10_steps_executed' in e else 'derived from cut and terminal step',native_restore_step=e.get('native_restore_step'),restore_not_executed_reason=e.get('restore_not_executed_reason'),detail_source=str(p)))
        if valid:
            prev=read(Path(row['old_L01_path']))
            if prev.get('status')=='complete' and type(prev.get('success')) is bool:
                pair=pairs[u['cell_id']];pair['paired_valid']+=1;pair['L11_successes']+=r['success'];pair['L01_successes']+=prev['success'];pair['rescued']+=int(r['success'] and not prev['success']);pair['harmed']+=int(prev['success'] and not r['success'])
    cellrows=[]
    for cell in sorted({r['cell_id'] for r in rows}):
        items=[r for r in rows if r['cell_id']==cell];c=collections.Counter(r['disposition'] for r in items);valid=c['valid'];success=sum(r['success'] is True for r in items)
        cellrows.append(dict(cell_id=cell,model=items[0]['model'],method=items[0]['method'],H=items[0]['H'],planned=len(items),valid=valid,successes=success,success_rate=success/valid if valid else None,technical=c['technical_missing'],unknown=c['unknown_entered'],not_entered=c['not_entered'],current_paper=items[0]['current_paper'],preserved_valid=sum(r['preserved_prior_valid'] for r in items)))
    pairrows=[dict(cell_id=k,comparison='L11_vs_historical_L01_same_source',**dict(v),difference_pp=100*(v['L11_successes']-v['L01_successes'])/v['paired_valid']) for k,v in pairs.items()]
    oldattempts=list(csv.DictReader((OLD/'task_summary/ATTEMPTS_ALL.csv').open()));allattempts=oldattempts+newattempts
    # Old held results retain raw costs but never enter scientific denominators.
    def cost_summary(items):
        return {k:dict(recorded_sum=sum(float(r[k]) for r in items if r.get(k) not in ('',None)),missing_records=sum(r.get(k) in ('',None) for r in items)) for k in COST_KEYS}
    workerpaths=[]
    for pattern in ('*/workers/*/CLIENT_RESULT.json','*/workers/*/encoder/RESULT.json','*/model_*/SERVER_RESULT.json','*/branch_*/CLIENT_RESULT.json'):
        workerpaths.extend((ROOT/'chains/evaluate/stages').glob(pattern))
    workers=[dict(path=str(p),result=read(p)) for p in workerpaths]
    costs=dict(utc=utc(),recovery_episode_costs=cost_summary(newattempts),all_historical_and_recovery_attempt_costs=cost_summary(allattempts),usable_scientific_result_costs=cost_summary([r for r in rows if r['disposition']=='valid']),worker_results=workers,original_worker_cost_audits=str(OLD/'event_audits/C_4834113fcd0b6f4d5d6f6ba9fff7b341'),missing_is_zero=False,worker_and_episode_counters_overlap_do_not_add=True,occupancy='holders off complete formal wave; model/RPC/CPU scheduling wait included in wall time')
    atomic_json(ROOT/'COSTS.json',costs)
    for name,data in [('EPISODES',rows),('CELLS',cellrows),('CUTS',cuts),('PAIRED_L01',pairrows),('ATTEMPTS_ALL',allattempts),('POST_CURRENT_PAPER',[r for r in cellrows if r['current_paper']]),('VELOCITY_OTHER_WORK',[r for r in cellrows if not r['current_paper']])]:table(ROOT/(name+'.csv'),data)
    atomic_json(ROOT/'CUT_PROTOCOL_AUDIT.json',dict(utc=utc(),errors=errors,valid=not errors,actual_cuts=len(cuts),C10_no_reentry=True if not errors else None))
    valid=sum(r['disposition']=='valid' for r in rows);newvalid=sum(r['disposition']=='valid' and not r['preserved_prior_valid'] for r in rows)
    summary=dict(utc=utc(),task_id=TASK,loss='L11',fit_seed=9101,expected=2500,recovery_planned=1764,recovery_valid=newvalid,preserved_valid=736,valid=valid,task_complete=valid==2500 and not errors,attempts_this_recovery=len(newattempts),attempts_prior_C=17693,cumulative_C_attempts=17693+len(newattempts),stage_attempt_cap=2000,node_attempt_cap=20750,cells=cellrows,pairs=pairrows,costs=str(ROOT/'COSTS.json'),cut_protocol_errors=len(errors),unique_usable_result_per_key=True,old_L01_preserved=True,old_raw_and_failures_preserved=True,valid_terminal_replays=0,new_training_updates=0,new_collection=0,revealed_fixed_sources=True,independent_blind_test=False)
    atomic_json(ROOT/'FINAL_SUMMARY.json',summary)
    lines=['# C L11 恢复汇总','','固定 L11 / fit9101。保留旧 L01、旧失败和原始成本；736 条原有效结果不重跑，1764 条仅按授权清单恢复。源此前已公开，不称独立盲测。','','| Cell | 有效/计划 | 成功 | 技术缺项 | 未知 | 未进入 |','|---|---:|---:|---:|---:|---:|']
    lines += [f"| {r['cell_id']} | {r['valid']}/{r['planned']} | {r['successes']} | {r['technical']} | {r['unknown']} | {r['not_entered']} |" for r in cellrows]
    lines += ['', 'Post 为当前论文结果，Velocity 另表保存。成功率分母为有效终局；未知、技术故障与未进入不计任务失败。','', 'ATTEMPTS_ALL.csv 保留历次尝试链；EPISODES.csv 每个科学 key 仅选一个有效结果。COSTS.json 同时记录恢复成本、全部尝试成本和 worker 原始计数，不重复相加。墙钟包含共享模型 RPC 排队与 CPU 调度；正式整波所有 holder 关闭。','']
    (ROOT/'REPORT.md').write_text('\n'.join(lines));return summary
if __name__=='__main__':print(json.dumps(main(),ensure_ascii=False))
