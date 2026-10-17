"""C multi: real terminals, strict same-source pairs and complete worker costs."""
import csv,json,random
from collections import Counter
from pathlib import Path
from paths import ROOT,CAMPAIGN,TASK,HEADS,PREVIOUS
from qio import read,atomic_json,utc
from operational_hook import consume

def paired(new,old):
    ids=sorted(set(new)&set(old));bytask={}
    for sid in ids:bytask.setdefault(new[sid]['task'],[]).append(int(new[sid]['success'])-int(old[sid]['success']))
    rescued=sum(new[s]['success'] and not old[s]['success'] for s in ids)
    harmed=sum(old[s]['success'] and not new[s]['success'] for s in ids);ci=None
    if ids:
        groups=[(sum(v),len(v)) for _,v in sorted(bytask.items())];rng=random.Random(20260922);samples=[]
        for _ in range(2000):
            sample=rng.choices(groups,k=len(groups));samples.append(100*sum(x[0] for x in sample)/sum(x[1] for x in sample))
        samples.sort();ci=[samples[49],samples[1949]]
    return dict(paired_valid=len(ids),rescued=rescued,harmed=harmed,difference_pp=100*(rescued-harmed)/len(ids) if ids else None,
        new_successes=sum(new[s]['success'] for s in ids),reference_successes=sum(old[s]['success'] for s in ids),
        task_cluster_bootstrap_95_CI_pp=ci,interval_method='pointwise paired task cluster bootstrap,2000 draws,seed20260922; no imputation')

def valid(rows):return {s:r for s,r in rows.items() if r.get('status')=='complete' and type(r.get('success')) is bool}

def write_csv(path,rows):
    with Path(path).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def totals(rows,key):
    counts=Counter()
    for r in rows:counts.update(r.get(key,{}))
    return dict(counts)

def validate_episode(row,source):
    assert all(row[k]==source[k] for k in ['task','source_id','reset_seed','policy_seed'])
    triggers=[e for e in row.get('events',[]) if e['trigger']]
    assert row['interventions']==len(triggers) and row['first_cut']==(triggers[0]['step'] if triggers else None)
    lock=0
    for e in row.get('events',[]):
        assert e['step']>=lock and e['step']%5==0
        if e['trigger']:
            assert e['legal_cut'] and e['gate']>.05 and e['queue_age']==5 and e['step']+10<=300
            assert e['commit_until']==e['step']+10 and e['restore_native_K']==10 and not e['Q_acceptance_gate']
            lock=e['commit_until']
    if row['status']=='complete':
        factor={'R':0,'Post':1,'Velocity':3}[row['method']]
        enc=row['encoder_counters'];counts=row['counters']
        assert enc.get('Q_ensemble_forward_calls',0)==enc.get('action_gradient_calls',0)==factor*len(triggers)
        assert counts['policy_flow_calls']==10*counts['policy_queries']
        assert counts.get('candidate_queries',0)==(2 if row['method']=='Velocity' else 1)*len(triggers)

def main():
    consume(ROOT,"report")
    sources=read(ROOT/'config/TEST_SOURCES.json')['sources'];index={s['source_id']:s for s in sources}
    assert len(sources)==len(index)==500
    prior=read(CAMPAIGN/'work/C/C_D24_MW_VELOCITY_V1_r2/MW_VELOCITY_BATCH.json')
    baseline={r['source_id']:r for r in read(prior['baseline_index'])['xvla']}
    assert set(index)==set(baseline) and sum(r['success'] for r in baseline.values())==403
    final=[];groups=[];pairs={};methods={};cells=[];episode_encoder=Counter();all_rows=[]
    for method in ['Post','Velocity']:
        rows={p.parent.name:read(p) for p in (ROOT/'evaluation'/method).glob('*/RESULT.json')}
        for sid,row in rows.items():validate_episode(row,index[sid])
        good=valid(rows);methods[method]=good;all_rows.extend(rows.values())
        once=valid({p.parent.name:read(p) for p in (HEADS/'evaluation'/method).glob('*/RESULT.json')})
        assert len(once)==500
        pairs[method+'_newQ_multi_vs_oldQ_once']=paired(good,once);pairs[method+'_multi_vs_N']=paired(good,baseline)
        old_multi=valid({p.parent.name:read(p) for p in (PREVIOUS/'evaluation'/method).glob('*/RESULT.json')})
        pairs[method+'_newQ_multi_vs_oldQ_multi']=paired(good,old_multi)
        entered=sum((ROOT/'evaluation'/method/sid/'ENTERED.json').exists() for sid in index)
        counts=totals(good.values(),'counters');enc=totals(good.values(),'encoder_counters')
        episode_encoder.update(totals(rows.values(),'encoder_counters'))
        successes=sum(r['success'] for r in good.values());triggers=Counter(str(r['interventions']) for r in good.values())
        calls=dict(counts,**enc);calls['interventions']=sum(r['interventions'] for r in good.values())
        group=dict(method=method,mode='G0-multi',planned=500,entered=entered,valid=len(good),successes=successes if good else None,
            success_rate=successes/len(good) if good else None,technical=sum(r['status']=='technical_failure' for r in rows.values()),
            budget_truncated=sum(r['status']=='budget_truncated' for r in rows.values()),unknown=entered-len(rows),unstarted=500-entered,
            intervention_histogram=dict(triggers),total_interventions=calls['interventions'],
            trigger_zero=sum(r['interventions']==0 for r in good.values()),trigger_once=sum(r['interventions']==1 for r in good.values()),
            trigger_multi=sum(r['interventions']>1 for r in good.values()),
            policy_and_runtime_counters=counts,external_encoder_and_heads_counters=enc,
            per_valid_episode={k:v/len(good) for k,v in calls.items()} if good else None,
            all_valid_cost_per_success={k:v/successes for k,v in calls.items()} if successes else None,
            nonvalid_costs=dict(policy=totals([r for r in rows.values() if r['status']!='complete'],'counters'),
                               encoder=totals([r for r in rows.values() if r['status']!='complete'],'encoder_counters')),
            total_valid_episode_seconds=sum(r['elapsed_seconds'] for r in good.values()))
        groups.append(group)
        pn=pairs[method+'_multi_vs_N'];po=pairs[method+'_newQ_multi_vs_oldQ_once']
        cells.append(dict(method=method,mode='G0-multi',valid=len(good),successes=group['successes'],success_rate=group['success_rate'],
            technical=group['technical'],unknown=group['unknown'],unstarted=group['unstarted'],
            difference_vs_N_pp=pn['difference_pp'],N_rescued=pn['rescued'],N_harmed=pn['harmed'],N_paired95CI_pp=json.dumps(pn['task_cluster_bootstrap_95_CI_pp']),
            difference_vs_once_pp=po['difference_pp'],once_rescued=po['rescued'],once_harmed=po['harmed'],once_paired95CI_pp=json.dumps(po['task_cluster_bootstrap_95_CI_pp']),
            interventions=group['total_interventions'],multi_episodes=group['trigger_multi'],policy_queries=counts.get('policy_queries',0),
            policy_flow_calls=counts.get('policy_flow_calls',0),visual_encoder_calls=enc.get('visual_encoder_calls',0),language_encoder_calls=enc.get('language_encoder_calls',0),
            D_calls=enc.get('D_forward_calls',0),G0_calls=enc.get('G0_forward_calls',0),Q_calls=enc.get('Q_ensemble_forward_calls',0),action_gradient_calls=enc.get('action_gradient_calls',0)))
        for sid,s in index.items():
            row=rows.get(sid,{});is_entered=(ROOT/'evaluation'/method/sid/'ENTERED.json').exists()
            final.append(dict(method=method,mode='G0-multi',source_id=sid,task=s['task'],reset_seed=s['reset_seed'],policy_seed=s['policy_seed'],
                status=row.get('status','execution_unknown' if is_entered else 'unstarted'),success=row.get('success'),steps=row.get('steps'),
                interventions=row.get('interventions'),first_cut=row.get('first_cut'),cuts=json.dumps([e['step'] for e in row.get('events',[]) if e['trigger']]),
                elapsed_seconds=row.get('elapsed_seconds'),N_success=baseline[sid]['success'],once_success=once[sid]['success'],
                policy_queries=row.get('counters',{}).get('policy_queries'),flow_calls=row.get('counters',{}).get('policy_flow_calls'),
                Q_calls=row.get('encoder_counters',{}).get('Q_ensemble_forward_calls',0) if row else None,
                language_calls=row.get('encoder_counters',{}).get('language_encoder_calls',0) if row else None,
                result_path=str(ROOT/'evaluation'/method/sid/'RESULT.json') if row else None))
    methods['R']=valid({p.parent.name:read(p) for p in (PREVIOUS/'evaluation/R').glob('*/RESULT.json')})
    assert len(methods['R'])==500
    pairs['Post_multi_vs_R_multi']=paired(methods['Post'],methods['R'])
    pairs['Velocity_multi_vs_R_multi']=paired(methods['Velocity'],methods['R'])
    atomic_json(ROOT/'PAIRED.json',pairs);write_csv(ROOT/'FINAL_EPISODES.csv',final);write_csv(ROOT/'FINAL_CELLS.csv',cells)
    write_csv(ROOT/'POST_PAPER_CELLS.csv',[r for r in cells if r['method']=='Post'])
    write_csv(ROOT/'VELOCITY_OTHER_WORK_CELLS.csv',[r for r in cells if r['method']=='Velocity'])
    atomic_json(ROOT/'POST_PAPER_PAIRED.json',{k:v for k,v in pairs.items() if k.startswith('Post_')})
    atomic_json(ROOT/'VELOCITY_OTHER_WORK_PAIRED.json',{k:v for k,v in pairs.items() if k.startswith('Velocity_')})
    workers=[];encoder_counts=Counter();native_counts=Counter()
    for out in sorted((ROOT/'stages/evaluate/workers').glob('*')):
        er=read(out/'encoder/RESULT.json') if (out/'encoder/RESULT.json').exists() else None
        nr=read(out/'CLIENT_RESULT.json') if (out/'CLIENT_RESULT.json').exists() else None
        ready=read(out/'MODEL_READY.json') if (out/'MODEL_READY.json').exists() else None
        workers.append(dict(worker=out.name,encoder=er,native=nr,native_ready=ready))
        if er:encoder_counts.update(er['counts'])
        if nr:native_counts.update(nr['counters'])
    valid_total=sum(g['valid'] for g in groups)
    reconciled=(len(workers)==24 and all(w['encoder'] and w['native'] and w['encoder']['status']==w['native']['status']=='complete' for w in workers))
    if reconciled:
        for k,v in encoder_counts.items():
            if not k.endswith('seconds'):assert abs(v-episode_encoder.get(k,0))<1e-6,(k,v,episode_encoder.get(k))
    resource=dict(task_id=TASK,utc=utc(),workers=workers,encoder_totals=dict(encoder_counts),native_totals=dict(native_counts),
        episode_encoder_calls_reconciled_with_workers=reconciled,external_frozen_encoder_sampling=0,new_optimizer_updates=64000,
        base_parameters=879482456,external_loaded_parameters=4143404816,new_D_G0_Q_parameters=11912530,
        external_visual_active_submodule_parameters=None,external_parameter_note='loaded full external model includes unused sampling components; active visual submodule count unavailable',
        cost_note='Per-method begin language call included. Cache shared across worker tasks; cache ownership affects language call attribution. RPC/guided times overlap; not additive wall time.',
        utilization=read(ROOT/'chains/evaluate/UTILIZATION_SUMMARY.json') if (ROOT/'chains/evaluate/UTILIZATION_SUMMARY.json').exists() else None,
        formal_stage=read(ROOT/'stages/evaluate/RESULT.json') if (ROOT/'stages/evaluate/RESULT.json').exists() else None,
        occupancy_restoration=read(ROOT/'chains/evaluate/RESTORATION.json') if (ROOT/'chains/evaluate/RESTORATION.json').exists() else None,
        occupancy='all holders off for formal wave; 15s observations do not certify continuous GPU utilization')
    resource['training']=read(ROOT/'CANDIDATES_READY.json')
    resource['training_wave']=read(ROOT/'chains/train/RESULT.json')
    resource['training_utilization']=read(ROOT/'chains/train/UTILIZATION_SUMMARY.json') if (ROOT/'chains/train/UTILIZATION_SUMMARY.json').exists() else None
    atomic_json(ROOT/'RESOURCE_SUMMARY.json',resource)
    attempts=read(ROOT/'ATTEMPT_COUNTER.json')['reserved_attempts'] if (ROOT/'ATTEMPT_COUNTER.json').exists() else 0
    assert attempts<=1100 and 11943+attempts<=14000
    summary=dict(task_id=TASK,utc=utc(),status='complete' if valid_total==1000 else 'partial',mode='G0-multi',evaluation_valid=valid_total,
        attempts=attempts,cumulative_C_attempts=11943+attempts,stage_attempt_cap=1100,cumulative_cap=14000,groups=groups,
        new_training_updates=64000,new_collection_attempts=0,N_reused=dict(valid=500,successes=403,new_rollouts=0),old_completed_replays=0,
        fixed_heads=str(ROOT/'SELECTION_CONSUMED.json'),selected_loss=read(ROOT/'SELECTION_CONSUMED.json')['chosen_loss'],training_candidates=str(ROOT/'CANDIDATES_READY.json'),R_reused=dict(valid=500,new_rollouts=0),pairs=str(ROOT/'PAIRED.json'),resources=str(ROOT/'RESOURCE_SUMMARY.json'),
        interpretation='A dev-selected full-Q loss at fit9101, own X data and four weights; reused revealed test sources. NewQ multi versus oldQ once changes both Q and trigger count, not a pure count effect.',
        environment='unchanged E8 Mesa80Hz/.01/rawH30/nativeK10/NFE10',Post_metric='unchanged frozen pi05 S squared; Velocity native X inverse normalization/clean head')
    summary.update(selection_criterion='Post-only complete development; fixed fit9101',paper_primary='Post',Velocity_current_paper=False,Velocity_other_work_results='VELOCITY_OTHER_WORK_CELLS.csv')
    atomic_json(ROOT/'FINAL_SUMMARY.json',summary)
    lines=['X-VLA 完整 Q 损失选择后的 G0-multi：C 结果交付','',summary['interpretation'],'',
        '| 方法 | 成功 / 有效 | 多次干预回合 | 干预总数 | 相对旧Q once 救回 / 损害 |','|---|---:|---:|---:|---:|']
    for g in [r for r in groups if r['method']=='Post']:
        p=pairs[g['method']+'_newQ_multi_vs_oldQ_once'];lines.append(f"| {g['method']} | {g['successes']} / {g['valid']} | {g['trigger_multi']} | {g['total_interventions']} | {p['rescued']} / {p['harmed']} |")
    lines+=['', '本篇只呈现Post；Velocity沿用同一Post所选配置，另存VELOCITY_OTHER_WORK文件，不进入本篇最终表图。', '',f'本轮 {attempts}/1100 attempts；C累计 {11943+attempts}/14000。完整Q训练64000更新；新采集、N/R重跑均为0。',
        '', 'PAIRED.json 提供与旧Q once、旧Q multi、N及复用R-multi的逐源配对；旧Q once比较不能解释为纯次数收益。区间为pointwise任务聚类bootstrap，2000次seed20260922，不能把包含零的区间写成已确立收益。',
        '', 'FINAL_SUMMARY.json 分列每有效回合与所有有效成本/成功数；技术开销另列。RESOURCE_SUMMARY.json 含完整外部编码成本、常驻参数显存、调用、时间及真实GPU利用率。',
        '', '继承Mesa80Hz/.01、nativeK10、G0>.05、每5步监测、合法cut、C10禁止重入；仅替换完整重训且由A开发集锁定选择的专属Q。Post仍为既有pi05 S²坐标，Velocity保留X内部Jacobian。',
        '', '全部原once、旧L11 multi、旧失败及新4000步final权重保留；未完成和未知不当作失败。整波holder全停，整族退出后恢复。共享主表仅由分析端更新。']
    (ROOT/'MASTER_UPDATE.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(status=summary['status'],attempts=attempts,evaluation_valid=valid_total)))

if __name__=='__main__':main()
