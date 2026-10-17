"""Publish actual entered outcomes and costs, without turning gaps into successes."""
import csv
import json
from pathlib import Path
import d24_common as d

def publish():
    rows=[];batch=d.load(d.W/'BATCH.json')
    for job in batch['jobs']:
        out=Path(job['output'])
        for phase in ['development','Full-Post','Full-Velocity']:
            p=out/(phase+'.jsonl')
            if p.exists():rows.extend(json.loads(line) for line in p.read_text().splitlines() if line.strip())
    summary={}
    for phase in ['development','Full-Post','Full-Velocity']:
        selected=[r for r in rows if r['phase']==phase];valid=[r for r in selected if r['status']=='complete' and type(r['success']) is bool]
        claims=list((d.R/'workers').glob('*/episode_claims/'+phase+'__*.json'))
        summary[phase]=dict(entered=len(claims),published=len(selected),valid=len(valid),successes=sum(r['success'] for r in valid),
            success_rate=sum(r['success'] for r in valid)/len(valid) if valid else None,
            technical_failures=sum(r['status']!='complete' for r in selected),unpublished_entered=len(claims)-len(selected),
            sampling_calls=sum(r['sampling_calls'] for r in selected),flow_calls=sum(r['flow_calls'] for r in selected),
            feature_calls=sum(r['feature_calls'] for r in selected),interventions=sum(r['interventions'] for r in selected),
            true_G0_triggered=sum(r.get('G0_triggered') is True for r in selected),steps=sum(r['steps'] for r in selected))
    gap=d.load(d.R/'SCIENTIFIC_GAP.json') if (d.R/'SCIENTIFIC_GAP.json').exists() else None
    fit=d.load(d.R/'FIT_SUMMARY.json') if (d.R/'FIT_SUMMARY.json').exists() else None
    complete=all(summary[p]['valid']==400 for p in ['Full-Post','Full-Velocity'])
    status='COMPLETE_FULL_NATIVE' if complete else 'SCIENTIFIC_GAP' if gap else 'PARTIAL_OR_FAILED'
    result=dict(utc=d.utc(),task_id=d.TASK,status=status,phases=summary,scientific_gap=gap,
        development_cumulative_attempts=160+summary['development']['entered'],development_cumulative_cap=200,
        additional_attempt_cap=1000,actual_new_physical_attempts=sum(v['entered'] for v in summary.values()),
        actual_small_network_updates=fit.get('optimizer_updates') if fit else (d.load(d.R/'FIT_PROGRESS.json').get('updates') if (d.R/'FIT_PROGRESS.json').exists() else 0),
        no_test_based_selection=True,Full_claimed=complete,remaining475_closed=True,
        original_B_operator_results_unmodified=True,protocol='D2/age2/G0 old3-fresh3_then_native5/C5/nativeK5; once .05; rotation frozen',
        existing_source_method_replays=0,base_SFT_updates=0)
    if result['development_cumulative_attempts']>200 or result['actual_new_physical_attempts']>1000:raise RuntimeError('Actual attempt cap exceeded')
    d.atomic(d.R/'FINAL_SUMMARY.json',result)
    keys=['phase','source_id','parent_id','branch','suite','task_id','split','reset_seed','policy_seed','status','success','steps',
          'sampling_calls','flow_calls','feature_calls','interventions','G0_triggered','cut_step','elapsed_seconds','inference_seconds','environment_seconds','monitor_seconds','corrector_seconds','technical_failure']
    with (d.R/'PER_EPISODE.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        for row in rows:
            out={k:row.get(k) for k in keys}
            if isinstance(out['technical_failure'],dict):out['technical_failure']=json.dumps(out['technical_failure'])
            writer.writerow(out)
    resource=dict(utc=d.utc(),actual_new_attempts=result['actual_new_physical_attempts'],phases=summary,
        small_network_updates=result['actual_small_network_updates'],base_SFT_updates=0,
        summed_saved_episode_host_seconds=sum(r.get('elapsed_seconds') or 0 for r in rows),
        all_holders_off_formal_wave=True,auxiliary_holder_calls=0,hardware_monitoring_separate='gpu_metrics.jsonl',
        cost_note='Sampling counter includes base plus guided; feature-only calls do not sample; sums are not makespan or GPU seconds.')
    d.atomic(d.R/'RESOURCE_SUMMARY.json',resource)
    (d.R/'REPORT.md').write_text('本任务：'+status+'。\n\n协议为原生K5/raw10/NFE10；D2在age2成熟；G0标签为fresh3后恢复K5减old队列余3后恢复K5的真实终局收益，阈值.05、最多一次；纠偏C5、旋转不动。\n\n'
        +'开发已用160，本轮已进入'+str(summary['development']['entered'])+'次，累计'+str(result['development_cumulative_attempts'])+'/200；不重置额度、不替换父源。\n\n'
        +'Full-Post有效'+str(summary['Full-Post']['valid'])+'/400；Full-Velocity有效'+str(summary['Full-Velocity']['valid'])+'/400。技术失败及未发布进入项分列于FINAL_SUMMARY.json，缺失不作科学失败。\n\n'
        +('科学缺口：'+json.dumps(gap['reasons'],ensure_ascii=False)+'；没有扩大开发、改变阈值或以全零触发冒称Full。\n\n' if gap else '')
        +'Q仅使用既有真实同parent/cut的a0和方向候选；不把扰动结果当old/fresh标签。G0标签为每支一次的带噪声终局差，不是双repeat成功概率。主方法时距已适配为D2/old3/C5，B原算子版结果保持独立。\n')
    return result

if __name__=='__main__':print(json.dumps(publish(),indent=2))
