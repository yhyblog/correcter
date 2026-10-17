"""Aggregate this run's terminal files; never infer a false result from absence."""
import csv,json,math
from collections import Counter,defaultdict
from pathlib import Path
import paths
from paths import ROOT
from qio import read,new_json,atomic_json,utc,ref

def result_path(unit):
    if unit['model']=='X-VLA':return ROOT/'evaluation'/unit['method']/unit['source_id']/'RESULT.json'
    return ROOT/'pi_evaluation'/unit['cell_id']/unit['source_id']/'RESULT.json'
def table(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
    units=read(ROOT/'UNIT_INDEX.json');rows=[];cutrows=[];cost=Counter();cells=defaultdict(list);pairs=defaultdict(Counter)
    for u in units:
        p=result_path(u);result=read(p) if p.exists() else {};claim=ROOT/'claims/units'/(u['storage_key']+'.json')
        valid=result.get('status')=='complete' and type(result.get('success')) is bool
        disposition='valid' if valid else 'technical' if result.get('status')=='technical_failure' else 'unknown_entered' if claim.exists() else 'not_entered'
        c=result.get('counters',{});e=result.get('encoder_counters',{})
        flow=c.get('policy_flow_calls',c.get('flow'));sampling=c.get('policy_queries',c.get('sampling'))
        gradients=e.get('action_gradient_calls',c.get('action_gradients'));qforward=e.get('Q_ensemble_forward_calls',c.get('Q_ensemble_forward'))
        d=e.get('D_forward_calls',c.get('D_forward'));g=e.get('G0_forward_calls',c.get('G0_forward'))
        row=dict(unit_id=u['unit_id'],model=u['model'],source_id=u['source_id'],task=u['task'],env_seed=u['env_seed'],policy_seed=u['policy_seed'],method=u['method'],mode=u['mode'],H=u['H'],loss='L11',fit_seed=9101,current_paper=u['current_paper'],cell_id=u['cell_id'],disposition=disposition,success=result.get('success') if valid else None,steps=result.get('steps'),interventions=result.get('interventions'),first_cut=result.get('first_cut'),sampling_calls=sampling,flow_calls=flow,action_gradient_calls=gradients,Q_ensemble_forward=qforward,D_forward=d,G0_forward=g,elapsed_seconds=result.get('elapsed_seconds'),environment_seconds=result.get('environment_seconds',c.get('environment_seconds')),result_path=str(p) if p.exists() else None,cost_missing_reason=None if result else 'No episode terminal; unknown counts are null',revealed_source_retest=True)
        rows.append(row);cells[u['cell_id']].append(row)
        for key in ['sampling_calls','flow_calls','action_gradient_calls','Q_ensemble_forward','D_forward','G0_forward']:
            if row[key] is not None:cost[key]+=row[key]
        if valid:
            old=read(Path(u['original_source']['result_path']))
            if old.get('status')=='complete' and type(old.get('success')) is bool:
                pair=pairs[u['cell_id']];pair['paired_valid']+=1;pair['new_successes']+=int(result['success']);pair['old_L01_successes']+=int(old['success']);pair['rescued']+=int(result['success'] and not old['success']);pair['harmed']+=int(old['success'] and not result['success'])
        for event in result.get('events',[]):
            trigger=event.get('trigger',event.get('intervention_executed',False))
            if trigger:cutrows.append(dict(unit_id=u['unit_id'],model=u['model'],method=u['method'],H=u['H'],cut=event['step'],first_cut=result.get('first_cut'),intervention_index=event.get('intervention_index'),commit_until=event.get('commit_until'),C10_steps_executed=event.get('C10_steps_executed'),C10_complete=event.get('C10_complete'),native_restore_step=event.get('native_restore_step'),restore_not_executed_reason=event.get('restore_not_executed_reason'),detail_source=str(p)))
    summaries=[]
    for cell,items in cells.items():
        counts=Counter(r['disposition'] for r in items);success=sum(r['success'] is True for r in items);n=counts['valid']
        summaries.append(dict(cell_id=cell,model=items[0]['model'],method=items[0]['method'],H=items[0]['H'],planned=len(items),valid=n,successes=success,success_rate=success/n if n else None,technical=counts['technical'],unknown=counts['unknown_entered'],not_entered=counts['not_entered'],current_paper=items[0]['current_paper']))
    pairrows=[dict(cell_id=k,comparison='L11_vs_historical_L01_same_source',**dict(v),difference_pp=100*(v['new_successes']-v['old_L01_successes'])/v['paired_valid']) for k,v in pairs.items()]
    table(ROOT/'EPISODES.csv',rows);table(ROOT/'CELLS.csv',summaries);table(ROOT/'CUTS.csv',cutrows);table(ROOT/'PAIRED_L01.csv',pairrows)
    table(ROOT/'POST_CURRENT_PAPER.csv',[r for r in summaries if r['current_paper']]);table(ROOT/'VELOCITY_OTHER_WORK.csv',[r for r in summaries if not r['current_paper']])
    summary=dict(utc=utc(),task_id='C_D24_L11_RETEST_V1',loss='L11',fit_seed=9101,expected=len(units),task_expected=2500,previous_attempts=read(ROOT/'DEPENDENCY_EXIT.json')['prior_task_attempts'],deferred_prior_incomplete=175,prior_complete_render_integrity_unverified=22,prior_complete_included=False,task_complete=False,valid=sum(r['valid'] for r in summaries),technical=sum(r['technical'] for r in summaries),unknown=sum(r['unknown'] for r in summaries),not_entered=sum(r['not_entered'] for r in summaries),cells=summaries,costs=dict(cost),cost_scope='Sum of new episode counters; worker model loading/feature overhead retained in worker and encoder results',cost_missing='Absent counters are null, not zero; no L01 costs copied',pairs=pairrows,completed_source_replays=0,new_training_updates=0,new_collection=0,revealed_sources=True,independent_blind_test=False,occupancy='All holders off throughout formal wave; cooperative branch elapsed time includes scheduling wait')
    atomic_json(ROOT/'FINAL_SUMMARY.json',summary)
    lines=['# C L11 正式重测','', '固定 L11 / fit9101，旧 L01 保留。此轮使用已公开过的固定源，不称独立盲测。', '', '本次为 r4 π0.5 首次导入顺序修正接续，最多 1500 次 π0.5 回合，仅执行 r2 尚未进入的单位；此前两波 447+193=640 次全部保留，已完成源和已进行过修正重试的源不再运行；累计上限 2750。另 175 条技术/未知缺项待预算决定，首波 22 条完成记录图像完整性未核实，未重跑且不计入本表。任务总计划仍为 2500，各 cell 原计划 500；本表分母只表示获准接续的子集，不能当作全量成功率。','', '| Cell | 有效 / 计划 | 成功 | 技术缺项 | 未知 | 未进入 |','|---|---:|---:|---:|---:|---:|']
    lines += [f"| {r['cell_id']} | {r['valid']} / {r['planned']} | {r['successes']} | {r['technical']} | {r['unknown']} | {r['not_entered']} |" for r in summaries]
    lines += ['', 'Post 保存于 POST_CURRENT_PAPER.csv；Velocity 保存于 VELOCITY_OTHER_WORK.csv。调用和梯度成本从本轮逐源结果汇总；缺失为 null。模型加载成本保留在各 worker 原始记录。','', '每个模型副本以 batch=1 轮转多个独立环境，保留各源 RNG、C10、动作队列和上下文；墙钟时间包含调度等待。正式整波关闭占卡。','']
    (ROOT/'REPORT.md').write_text('\n'.join(lines));return summary
if __name__=='__main__':print(json.dumps(main(),ensure_ascii=False))
