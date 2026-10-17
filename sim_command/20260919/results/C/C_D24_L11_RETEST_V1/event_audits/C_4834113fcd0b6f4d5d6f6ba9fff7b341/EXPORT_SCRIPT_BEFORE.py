"""CPU-only full-manifest L11 export. Raw runs and terminal outcomes stay immutable."""
import argparse,collections,csv,json,os,subprocess,sys,time
from pathlib import Path
BASE=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
ROOT=BASE/'results/C/C_D24_L11_RETEST_V1'
RUNS=[ROOT]+[ROOT/'continuations'/x for x in ['r2','r3','r4','r5']]
OUT=ROOT/'task_summary';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(RUNS[-1]/'code'))
from qio import read,new_json,atomic_json,ref,utc,process_identity,same_process

def destination(run,u):
    return run/'evaluation'/u['method']/u['source_id']/'RESULT.json' if u['model']=='X-VLA' else run/'pi_evaluation'/u['cell_id']/u['source_id']/'RESULT.json'
def table(name,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w',newline='') as stream:
        w=csv.DictWriter(stream,fields);w.writeheader();w.writerows(rows)
def export():
    units=read(ROOT/'UNIT_INDEX.json');protected=set(read(RUNS[1]/'RECOVERY_PLAN.json')['protected_completed_ids'])
    episodes=[];cuts=[];attempts=[];pairs=[];costs=collections.defaultdict(list)
    for u in units:
        terminal=[];claims=[]
        for run in RUNS:
            cp=run/'claims/units'/(u['storage_key']+'.json')
            if cp.exists():claims.append(dict(run=str(run),claim=read(cp)))
            p=destination(run,u)
            if not p.exists():continue
            v=read(p);terminal.append((run,p,v))
            c=v.get('counters',{});e=v.get('encoder_counters',{})
            row=dict(unit_id=u['unit_id'],run=str(run),attempt=v.get('claim',{}).get('attempt',v.get('attempt_index')),status=v.get('status'),success=v.get('success'),steps=v.get('steps'),result_path=str(p),elapsed_seconds=v.get('elapsed_seconds'),sampling_calls=c.get('policy_queries',c.get('sampling')),flow_calls=c.get('policy_flow_calls',c.get('flow')),action_gradient_calls=e.get('action_gradient_calls',c.get('action_gradients')),Q_ensemble_forward=e.get('Q_ensemble_forward_calls',c.get('Q_ensemble_forward')),D_forward=e.get('D_forward_calls',c.get('D_forward')),G0_forward=e.get('G0_forward_calls',c.get('G0_forward')))
            attempts.append(row)
            for k in ['sampling_calls','flow_calls','action_gradient_calls','Q_ensemble_forward','D_forward','G0_forward']:
                if row[k] is not None:costs[k].append(row[k])
        valid=[t for t in terminal if t[2].get('status')=='complete' and type(t[2].get('success')) is bool and not (t[0]==ROOT and u['unit_id'] in protected)]
        assert len(valid)<=1,('duplicate valid terminal',u['unit_id'])
        selected=valid[0] if valid else terminal[-1] if terminal else None
        if u['unit_id'] in protected:disposition='render_integrity_unverified'
        elif valid:disposition='valid'
        elif selected and selected[2].get('status')=='technical_failure':disposition='technical_missing'
        elif claims:disposition='unknown_entered'
        else:disposition='not_entered'
        v=selected[2] if selected else {};p=selected[1] if selected else None
        row=dict(unit_id=u['unit_id'],cell_id=u['cell_id'],model=u['model'],method=u['method'],H=u['H'],source_id=u['source_id'],env_seed=u['env_seed'],policy_seed=u['policy_seed'],mode='G0-multi',loss='L11',fit_seed=9101,current_paper=u['current_paper'],disposition=disposition,success=v.get('success') if valid else None,raw_recorded_success=v.get('success'),attempt_count=len(claims),steps=v.get('steps'),first_cut=v.get('first_cut'),interventions=v.get('interventions'),result_path=str(p) if p else None,old_L01_path=u['original_source']['result_path'])
        episodes.append(row)
        if valid:
            old=read(u['original_source']['result_path'])
            if old.get('status')=='complete' and type(old.get('success')) is bool:
                pairs.append(dict(unit_id=u['unit_id'],cell_id=u['cell_id'],new_success=v['success'],old_L01_success=old['success'],rescued=v['success'] and not old['success'],harmed=old['success'] and not v['success']))
            for event in v.get('events',[]):
                if event.get('trigger',event.get('intervention_executed',False)):
                    cuts.append(dict(unit_id=u['unit_id'],cell_id=u['cell_id'],cut=event['step'],first_cut=v['first_cut'],intervention_index=event.get('intervention_index'),commit_until=event.get('commit_until'),C10_steps_executed=event.get('C10_steps_executed',min(10,v['steps']-event['step'])),C10_complete=event.get('C10_complete',v['steps']>=event['step']+10),native_restore_step=event.get('native_restore_step'),source_result=str(p)))
    cells=[]
    for cell in sorted({u['cell_id'] for u in units}):
        rows=[r for r in episodes if r['cell_id']==cell];n=collections.Counter(r['disposition'] for r in rows);s=sum(r['success'] is True for r in rows);paired=[r for r in pairs if r['cell_id']==cell]
        cells.append(dict(cell_id=cell,model=rows[0]['model'],method=rows[0]['method'],H=rows[0]['H'],planned=len(rows),valid=n['valid'],successes=s,success_rate_among_valid=s/n['valid'] if n['valid'] else None,full500_success_rate=s/500 if n['valid']==500 else None,technical_missing=n['technical_missing'],unknown_entered=n['unknown_entered'],not_entered=n['not_entered'],render_integrity_unverified=n['render_integrity_unverified'],current_paper=rows[0]['current_paper'],paired_L01=len(paired),paired_difference_pp=100*sum(int(r['new_success'])-int(r['old_L01_success']) for r in paired)/len(paired) if paired else None))
    nclaims=sum(e['attempt_count'] for e in episodes);assert nclaims<=2750 and len(episodes)==2500 and all(c['planned']==500 for c in cells)
    table('EPISODES.csv',episodes);table('ATTEMPTS_ALL.csv',attempts);table('CELLS.csv',cells);table('CUTS.csv',cuts);table('PAIRED_L01.csv',pairs)
    table('POST_CURRENT_PAPER.csv',[c for c in cells if c['current_paper']]);table('VELOCITY_OTHER_WORK.csv',[c for c in cells if not c['current_paper']])
    summary=dict(utc=utc(),task_id='C_D24_L11_RETEST_V1',expected_units=2500,claims=nclaims,attempt_cap=2750,observed_terminal_attempts=len(attempts),missing_attempt_terminals=nclaims-len(attempts),cells=cells,dispositions=dict(collections.Counter(e['disposition'] for e in episodes)),known_attempt_costs={k:dict(observed_sum=sum(v),reported_attempts=len(v),unknown_attempts=nclaims-len(v)) for k,v in costs.items()},cost_scope='All raw terminal attempts, including retained technical attempts; absent per-episode costs are unknown, not zero. Worker model-loading/encoder overhead remains in raw worker results.',complete=all(c['valid']==500 for c in cells),no_valid_source_replays=True,old_L01_unchanged=True,not_blind_retest=True,Post_and_Velocity_separate=True,run_results=[str(r/'RESULT.json') for r in RUNS],new_GPU_calls=0,new_scientific_units=0)
    atomic_json(OUT/'SUMMARY.json',summary)
    lines=['# C L11 全任务汇总','', '固定 L11 / fit9101；原计划五格各500。已公开源重测，非独立盲测。旧L01保留；Post与Velocity分表。','', '| Cell | 有效/500 | 成功 | 技术缺项 | 未知 | 未进入 | 渲染未核实 |','|---|---:|---:|---:|---:|---:|---:|']
    lines += [f"| {c['cell_id']} | {c['valid']}/500 | {c['successes']} | {c['technical_missing']} | {c['unknown_entered']} | {c['not_entered']} | {c['render_integrity_unverified']} |" for c in cells]
    lines += ['',f'累计准入 {nclaims}/2750；技术失败、未知、未执行与22条首波渲染未核实记录均不计为任务失败或成功。有效子集成功率不能当作完整500源成功率。', '', 'ATTEMPTS_ALL.csv保留每次原始尝试及成本；缺失成本为null。正式全波关闭holder，模型共享轮转时间包含等待；占卡与科学预算分开。','']
    (OUT/'REPORT.md').write_text('\n'.join(lines));return summary

def watch():
    import fcntl
    with (OUT/'CPU_EXPORT.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);new_json(OUT/'PROCESS.json',dict(utc=utc(),process=process_identity(),CPU_only=True,new_GPU_calls=0))
        final=RUNS[-1]
        while time.time()<1790175600:
            if (final/'RESULT.json').exists():break
            time.sleep(15)
        result=export();new_json(OUT/'EXPORT_TERMINAL.json',dict(utc=utc(),summary=ref(OUT/'SUMMARY.json'),final_run_terminal=(final/'RESULT.json').exists(),all500_complete=result['complete'],new_GPU_calls=0,no_recursive_wakeup=True))
        atomic_json(BASE/'receipts/C/C_D24_L11_RETEST_V1_TASK_EXPORT.json',dict(utc=utc(),summary=ref(OUT/'SUMMARY.json'),report=str(OUT/'REPORT.md'),scientific_task_complete=result['complete']))
def start():
    if (OUT/'PROCESS.json').exists():print('EXISTING_EXPORT_OWNER');return
    with (OUT/'CPU_EXPORT.log').open('ab') as log:
        p=subprocess.Popen(['/usr/bin/python','-B',str(Path(__file__).resolve()),'watch'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    print('CPU_EXPORT_WATCH',p.pid)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['now','watch','start']);a=p.parse_args()
    if a.action=='now':
        v=export();print(json.dumps({k:v[k] for k in ['utc','claims','dispositions','complete']},ensure_ascii=False))
    elif a.action=='watch':watch()
    else:start()
