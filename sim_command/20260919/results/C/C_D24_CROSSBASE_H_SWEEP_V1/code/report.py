"""Finite H sweep tables; unknown/technical outcomes never become failures."""
import csv,collections,json,itertools
from pathlib import Path
from paths import ROOT,TASK,CONFIG
from qio import read,atomic_json,utc,ref
COST_KEYS=('sampling_calls','sampling_entered','flow_calls','action_gradient_calls','Q_ensemble_forward','Q_member_forward','D_forward','G0_forward','visual_encoder_calls','language_encoder_calls','policy_seconds','encoder_seconds','environment_seconds')
def table(path,rows):
    rows=list(rows);fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def costs(r):
    c=r.get('counters',{});e=r.get('encoder_counters')
    e=e if isinstance(e,dict) else {}
    return dict(sampling_calls=c.get('policy_queries'),sampling_entered=c.get('policy_queries_entered'),flow_calls=c.get('policy_flow_calls'),action_gradient_calls=e.get('action_gradient_calls'),Q_ensemble_forward=e.get('Q_ensemble_forward_calls'),Q_member_forward=e.get('Q_member_forward_calls'),D_forward=e.get('D_forward_calls'),G0_forward=e.get('G0_forward_calls'),visual_encoder_calls=e.get('visual_encoder_calls'),language_encoder_calls=e.get('language_encoder_calls'),policy_seconds=c.get('policy_seconds'),encoder_seconds=e.get('encoder_seconds'),environment_seconds=c.get('environment_seconds'))
def aggregate_cost(rows):return {k:dict(known_total=sum(r[k] for r in rows if r.get(k) is not None),known_rows=sum(r.get(k) is not None for r in rows),unknown_rows=sum(r.get(k) is None for r in rows)) for k in COST_KEYS}
def main():
    units=read(ROOT/'UNIT_INDEX.json');rows=[];cuts=[];errors=[];attempts=[]
    assert len(units)==4000 and len({u['unit_id'] for u in units})==4000
    for u in units:
        p=ROOT/'evaluation'/u['cell_id']/u['source_id']/'RESULT.json';r=read(p) if p.exists() else {}
        cp=ROOT/'claims/units'/(u['storage_key']+'.json');entered=cp.exists();valid=r.get('status')=='complete' and type(r.get('success')) is bool
        if r and (r.get('unit_id')!=u['unit_id'] or r.get('H')!=u['H'] or r.get('loss')!=u['Q_loss'] or r.get('fit_seed')!=u['Q_fit_seed']):errors.append(dict(unit_id=u['unit_id'],kind='identity'))
        disposition='valid' if valid else 'technical_incomplete' if r.get('status')=='technical_failure' else 'unknown_entered' if entered else 'not_entered'
        row=dict(unit_id=u['unit_id'],cell_id=u['cell_id'],model='X-VLA',method=u['method'],mode=u['mode'],H=u['H'],C=u['C'],loss=u['Q_loss'],fit_seed=u['Q_fit_seed'],source_id=u['source_id'],task=u['task'],env_seed=u['env_seed'],policy_seed=u['policy_seed'],repeat=None,disposition=disposition,status=r.get('status','not_entered'),success=r['success'] if valid else None,steps=r.get('steps'),interventions=r.get('interventions'),first_cut=r.get('first_cut'),elapsed_seconds=r.get('elapsed_seconds'),result_path=str(p),claim_path=str(cp) if entered else None,current_paper=u['current_paper'],reused_H10=False,attempts=int(entered),**costs(r));rows.append(row)
        if entered:attempts.append(dict(**row,claim=read(cp)))
        triggered=[];locked=0
        for event in r.get('events',[]):
            t=event['step']
            if t<locked or t%5 or event['queue_age']<=0 or event['old_queue_remaining']<5 or event['history_frames']<5 or event['history_actions']<4 or t+10>300:errors.append(dict(unit_id=u['unit_id'],kind='illegal_monitor',step=t))
            if event['trigger']:
                triggered.append(t);locked=t+10
                if event['gate']<=.05 or event['commit_until']!=locked or event['C']!=10 or event['restore_normal_H']!=u['H']:errors.append(dict(unit_id=u['unit_id'],kind='cut_contract',step=t))
                expected=min(10,max(0,r['steps']-t))
                if event['commitment_executed']!=expected:errors.append(dict(unit_id=u['unit_id'],kind='commitment_count',step=t))
                if r['steps']>locked and (event['restored_at_step']!=locked or not event['new_natural_sample'] or not event['intervention_tail_discarded']):errors.append(dict(unit_id=u['unit_id'],kind='native_H_not_restored',step=t))
                cuts.append(dict(unit_id=u['unit_id'],source_id=u['source_id'],H=u['H'],method=u['method'],**event))
        if r and (r.get('first_cut')!=(triggered[0] if triggered else None) or r['interventions']!=len(triggered)):errors.append(dict(unit_id=u['unit_id'],kind='first_cut_count'))
        if r and u['method']=='N' and (r.get('events') or r['interventions'] or any((r.get('encoder_counters') or {}).values())):errors.append(dict(unit_id=u['unit_id'],kind='N_auxiliary_call'))
        if r and u['method']=='R' and any((r.get('encoder_counters') or {}).get(k,0) for k in ('Q_ensemble_forward_calls','Q_member_forward_calls','action_gradient_calls')):errors.append(dict(unit_id=u['unit_id'],kind='R_Q_call'))
    cells=[]
    for cell in sorted({r['cell_id'] for r in rows}):
        rs=[r for r in rows if r['cell_id']==cell];vr=[r for r in rs if r['disposition']=='valid'];cnt=collections.Counter(r['disposition'] for r in rs)
        cells.append(dict(cell_id=cell,model='X-VLA',method=rs[0]['method'],H=rs[0]['H'],mode=rs[0]['mode'],loss=rs[0]['loss'],fit_seed=rs[0]['fit_seed'],planned=len(rs),valid=len(vr),successes=sum(r['success'] for r in vr),task_failures=sum(not r['success'] for r in vr),success_rate=sum(r['success'] for r in vr)/len(vr) if vr else None,technical_incomplete=cnt['technical_incomplete'],unknown_entered=cnt['unknown_entered'],not_entered=cnt['not_entered'],current_paper=rs[0]['current_paper'],reused_H10=False,interventions=sum(r['interventions'] or 0 for r in vr)))
    reused=read(ROOT/'REUSED_H10.json')['rows']
    for m in ('N','Post','R','Velocity'):
        rs=[r for r in reused if r['method']==m]
        cells.append(dict(cell_id=f'X-VLA_{m}_H10',model='X-VLA',method=m,H=10,mode='native' if m=='N' else 'G0-multi',loss='L11' if m in ('Post','Velocity') else None,fit_seed=9101 if m in ('Post','Velocity') else None,planned=500,valid=500,successes=sum(r['success'] for r in rs),task_failures=sum(not r['success'] for r in rs),success_rate=sum(r['success'] for r in rs)/500,technical_incomplete=0,unknown_entered=0,not_entered=0,current_paper=m!='Velocity',reused_H10=True))
    groups=collections.defaultdict(dict)
    for r in reused+[r for r in rows if r['disposition']=='valid']:groups[(r['method'],r['H'])][r['source_id']]=r
    pairs=[]
    def pair(left,right,kind):
        x=groups[left];y=groups[right];shared=sorted(set(x)&set(y));values=collections.Counter((x[s]['success'],y[s]['success']) for s in shared)
        pairs.append(dict(kind=kind,left_method=left[0],left_H=left[1],right_method=right[0],right_H=right[1],common_valid=len(shared),left_only=len(set(x)-set(y)),right_only=len(set(y)-set(x)),both_success=values[True,True],left_only_success=values[True,False],right_only_success=values[False,True],both_task_fail=values[False,False],right_minus_left_success=(values[False,True]-values[True,False])/len(shared) if shared else None))
    for m in ('N','Post','R','Velocity'):
        for a,b in itertools.combinations((10,20,30),2):pair((m,a),(m,b),'across_H_common_valid')
    for h in (10,20,30):
        for m in ('Post','R','Velocity'):pair(('N',h),(m,h),'same_H_vs_N')
        pair(('R',h),('Post',h),'same_H_Post_vs_R')
    workers=[]
    for pat in ('*/workers/*/CLIENT_RESULT.json','*/workers/*/encoder/RESULT.json','*/workers/*/MODEL_READY.json','*/workers/*/encoder/READY.json'):
        workers.extend(dict(path=str(p),record=read(p)) for p in (ROOT/'chains/evaluate/stages').glob(pat))
    cost=dict(utc=utc(),all_new_entered_attempt_costs=aggregate_cost(attempts),new_valid_result_costs=aggregate_cost([r for r in rows if r['disposition']=='valid']),workers=workers,episode_worker_counts_overlap_do_not_sum=True,unknown_is_zero=False,shared_model_loads_separate=True,occupancy='all eight holders off entire wave; wall time includes cooperative environment scheduling, loading and RPC waits',utilization_summary=str(ROOT/'chains/evaluate/UTILIZATION_SUMMARY.json'))
    atomic_json(ROOT/'COSTS.json',cost);atomic_json(ROOT/'CUT_PROTOCOL_AUDIT.json',dict(utc=utc(),errors=errors,valid=not errors,cuts=len(cuts)))
    for name,data in [('FINAL_EPISODES',rows+reused),('FINAL_CELLS',cells),('CUTS',cuts),('PAIRED',pairs),('ATTEMPTS',attempts),('CURRENT_PAPER',[r for r in cells if r['current_paper']]),('VELOCITY_OTHER_WORK',[r for r in cells if not r['current_paper']]),('UNFINISHED',[r for r in rows if r['disposition']!='valid'])]:table(ROOT/(name+'.csv'),data)
    atomic_json(ROOT/'UNFINISHED_UNITS.json',dict(utc=utc(),units=[r for r in rows if r['disposition']!='valid'],not_failures=True))
    summary=dict(utc=utc(),task_id=TASK,expected=4000,valid=sum(r['disposition']=='valid' for r in rows),H10_reused=2000,attempts=len(attempts),prior_C_attempts=19457,cumulative_C_attempts=19457+len(attempts),stage_attempt_cap=4400,node_attempt_cap=25150,cells=cells,cut_protocol_errors=len(errors),valid_terminal_replays=0,new_training_updates=0,new_collection=0,revealed_fixed_sources=True,independent_blind_test=False,auxiliary_calibration='frozen native10-trained heads evaluated at H20/H30, no per-H calibration')
    atomic_json(ROOT/'FINAL_SUMMARY.json',summary)
    lines=['# C X-VLA H sweep','','固定原500源、raw30/NFE10、自然H10/20/30。H10仅复用；Post/Velocity固定L11/fit9101，D/G0沿用native10训练模块。本扫描不宣称独立盲测或逐H重新校准。','','| Cell | 有效/计划 | 成功 | 技术未完 | 未进入 |','|---|---:|---:|---:|---:|']
    lines += [f"| {r['cell_id']} | {r['valid']}/{r['planned']} | {r['successes']} | {r['technical_incomplete']+r['unknown_entered']} | {r['not_entered']} |" for r in cells]
    lines += ['', 'N/R/Post见CURRENT_PAPER.csv；Velocity单独保存。成功率分母仅含合法终局，技术故障、未知和未进入不计任务失败。PAIRED.csv仅使用共同有效源。', '', '所有新尝试与调用成本见ATTEMPTS.csv和COSTS.json；原H10尝试链保留原路径。正式整波关闭所有holder，墙钟包含模型加载、CPU调度和RPC等待；实际并发/利用率另存，不把192逻辑上下文写成192同时模型推理。']
    (ROOT/'REPORT.md').write_text('\n'.join(lines)+'\n');return summary
if __name__=='__main__':print(json.dumps(main(),ensure_ascii=False))
