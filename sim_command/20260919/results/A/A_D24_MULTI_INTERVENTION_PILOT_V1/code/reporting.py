"""Publish the four primary arms immediately, before optional Velocity finishes."""
from collections import Counter
from paths import ROOT
from qio import read,new_json,atomic_json,utc

def summarize(chain):
    rows=[read(p) for p in (ROOT/'runs').glob('*/RESULT.json')]
    arms=read(ROOT/'config/CONFIG.json')['methods'];cells={};byarm={}
    for arm in arms:
        selected=[r for r in rows if r['method']==arm];valid=[r for r in selected if r['status']=='complete']
        byarm[arm]={r['source_id']:r for r in valid}
        counts=Counter('3+' if r['interventions']>=3 else str(r['interventions']) for r in valid)
        cells[arm]=dict(planned=20,entered=len(selected),completed=len(valid),successes=sum(r['success'] for r in valid),
            technical_failures=len(selected)-len(valid),success_rate=sum(r['success'] for r in valid)/20 if len(valid)==20 else None,
            intervention_distribution={k:counts[k] for k in ('0','1','2','3+')},
            sampling_calls=sum(r.get('sampling_calls',r.get('counters',{}).get('sampling',0)) for r in selected),
            flow_calls=sum(r.get('flow_calls',r.get('counters',{}).get('flow',0)) for r in selected),
            episode_wall_seconds_sum=sum(r['elapsed_seconds'] for r in selected))
    comparisons={}
    for lhs,rhs in [('R_multi','R_once'),('Post_multi','Post_once'),('Post_multi','R_multi'),('Velocity_multi','Velocity_once')]:
        ids=sorted(set(byarm[lhs])&set(byarm[rhs]));rescue=[];harm=[]
        for key in ids:
            a,b=byarm[lhs][key]['success'],byarm[rhs][key]['success']
            if a and not b:rescue.append(key)
            if b and not a:harm.append(key)
        comparisons[lhs+'-'+rhs]=dict(paired_complete=len(ids),rescued=rescue,harmed=harm,
            success_count_delta=len(rescue)-len(harm),percentage_point_delta=5*(len(rescue)-len(harm)) if len(ids)==20 else None)
    result=dict(utc=utc(),task_id='A_D24_MULTI_INTERVENTION_PILOT_V1',revision=2,n=20,repeat=0,
        interpretation='previously revealed old disassemble development initial states only; not MT50 confirmation',
        cells=cells,comparisons=comparisons,actual_completed_job_count=len(rows),technical_failures_not_scored_zero=True)
    atomic_json(ROOT/'SUMMARY.json',result)
    lines=['旧 20 初态 · repeat0 · 单次／多次干预开发测试','',
        '| 方法 | 完成 | 成功数/20 | 成功率 | 干预次数 0/1/2/3+ | 采样调用 |',
        '|---|---:|---:|---:|---|---:|']
    for arm,cell in cells.items():
        rate='待完成' if cell['success_rate'] is None else '%.1f%%'%(100*cell['success_rate'])
        lines.append('| '+arm+' | '+str(cell['completed'])+' | '+str(cell['successes'])+' | '+rate+' | '+
            '/'.join(str(cell['intervention_distribution'][k]) for k in ('0','1','2','3+'))+' | '+str(cell['sampling_calls'])+' |')
    lines+=['','每条成功对应 5 个百分点；技术失败单列。仅旧已揭晓 disassemble 初态，不推广为全 MT50 结果。']
    for label,comparison in comparisons.items():
        lines.append(label+': '+str(comparison['percentage_point_delta'])+' pp；救回 '+str(len(comparison['rescued']))+'，损害 '+str(len(comparison['harmed']))+'，已配对 '+str(comparison['paired_complete']))
    (ROOT/'LIVE_TABLE.md').write_text('\n'.join(lines)+'\n')
    primary=all(cells[x]['completed']==20 for x in arms[:4])
    if primary and not (ROOT/'PRIMARY_RESULT.json').exists():
        new_json(ROOT/'PRIMARY_RESULT.json',result)
        new_json(ROOT/'outbox/primary_complete.json',dict(event_id='D24_A_pilot_R_Post20_complete_r2',node='A',
            kind='R_Post_primary_table_complete',synthetic=False,summary=str(ROOT/'PRIMARY_RESULT.json'),table=str(ROOT/'LIVE_TABLE.md'),utc=utc()))
    return result

