"""Read completed evidence only: E3 multi-primary pairing and E5 cost revision."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
import paths
from paths import CAMPAIGN
from qio import read,atomic_json,utc,ref
from analysis_tools import write_csv,pair,costs

def main():
    out=ROOT/'summaries';out.mkdir(exist_ok=True)
    baseline=read(ROOT/'config/COMPLETED_MULTI_BASELINES.json')['rows']
    vpath=CAMPAIGN/'results/A/A_D24_E3_UNSTARTED_CONTINUATION_V1/COMBINED_EPISODES.json'
    gpath=CAMPAIGN/'results/A/A_D24_GAF_INTERNAL_HOLDOUT_V1/EPISODES.json'
    external={'VLA-Corrector':read(vpath)['rows'],'GAF-v1 adapted':read(gpath)}
    index=read(ROOT/'SOURCE_INDEX.json')['source_sets']['Random'];ids={r['source_id'] for r in index}
    e3=[];paired=[];e5=[];costtable=[];resource={};inputs=[vpath,gpath,ROOT/'config/COMPLETED_MULTI_BASELINES.json']
    for name,rows in external.items():
        assert len(rows)==500 and {r['source_id'] for r in rows}==ids and all(r['status']=='complete' for r in rows)
        e3.append(dict(method=name,H=10,valid=500,successes=sum(r['success'] for r in rows),success_rate=sum(r['success'] for r in rows)/500,scope='unchanged native external method',log_derived=sum('log' in str(r.get('record_origin','')).lower() for r in rows)))
        for method in ['R','Post','Velocity']:
            ours=[r for r in baseline if r['method']==method and r['H']==10]
            p=pair(ours,rows,name=method+' G0-multi minus '+name);p.update(ours=method,external=name);paired.append(p)
    for method in ['R','Post','Velocity']:
        for H in [10,20,30,40,50]:
            rows=[r for r in baseline if r['method']==method and r['H']==H]
            assert len(rows)==500 and {r['source_id'] for r in rows}==ids
            resource[method+'_H'+str(H)]=costs(rows)
            c=resource[method+'_H'+str(H)];n=c['valid'];success=c['successes'];ints=[r['interventions'] for r in rows]
            row=dict(method=method,mode='G0-multi',H=H,valid=n,successes=success,success_rate=success/n,intervention_mean=sum(ints)/n,at_least2_proportion=sum(i>=2 for i in ints)/n,intervention_max=max(ints),failure_costs_excluded_from_valid_denominator=True)
            for metric,value in c['costs'].items():
                costtable.append(dict(method=method,H=H,metric=metric,**value))
                for field in ('total','mean_per_valid','all_valid_cost_per_success','known'):
                    row[metric+'_'+field]=value[field]
            e5.append(row)
            if H==10:e3.append(dict(method=method+' G0-multi',H=10,valid=n,successes=success,success_rate=success/n,scope='new main method; explicit post-observation revision',log_derived=0))
    resource_paths={
        'Velocity':CAMPAIGN/'results/A/A_D24_VELOCITY_TRIGGER_MODES_V1_RECOVERY_r3/RESOURCE_SUMMARY.json',
        'Post':CAMPAIGN/'results/B/B_D24_POST_TRIGGER_MODES_V1/recovery_r3/RESOURCE_SUMMARY.json',
        'R':CAMPAIGN/'results/C/C_D24_R_TRIGGER_MODES_V1/RESOURCE_SUMMARY.json'}
    physical={}
    for method,path in resource_paths.items():
        d=read(path);inputs.append(path)
        physical[method]=dict(source=ref(path),scope='entire previous trigger wave, Random-once + G0-multi; preserves failure and retry costs, never folded into valid500 denominator',original=d)
    parameters=CAMPAIGN/'results/A/A_D24_OURS_E5_REPORT_V1/PARAMETER_COUNTS.json';params=read(parameters);inputs.append(parameters)
    assert params['total_added_unique_network_parameters']==11912530
    atomic_json(out/'E5_PARAMETERS.json',dict(added_unique_network_parameters=11912530,multi_new_parameters=0,new_training_updates=0,inherited_count=ref(parameters),scientific_compute=0))
    write_csv(out/'E3_COMPARISON.csv',e3);write_csv(out/'E3_PAIRED.csv',paired);atomic_json(out/'E3_PAIRED.json',paired)
    write_csv(out/'E5_MULTI_COSTS.csv',e5);write_csv(out/'E5_COST_FIELD_COVERAGE.csv',costtable)
    atomic_json(out/'E5_RESOURCE_VALID_ONLY.json',resource);atomic_json(out/'E5_PHYSICAL_OVERHEAD_SEPARATE.json',physical)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'R':'#325d88','Post':'#b57921','Velocity':'#855c91'}
    fig,axes=plt.subplots(1,2,figsize=(10,3.5),layout='constrained',sharex=True)
    for ax,ext in zip(axes,external):
        rows=[next(x for x in paired if x['external']==ext and x['ours']==method) for method in colors]
        for y,row in enumerate(rows):
            x=row['difference_pp'];ax.errorbar(x,y,xerr=[[x-row['CI95_low_pp']],[row['CI95_high_pp']-x]],fmt='o',color=colors[row['ours']],capsize=4)
            ax.annotate(f"{x:+.1f} pp",(x,y),xytext=(0,10),textcoords='offset points',ha='center',fontsize=9)
        ax.axvline(0,color='#666666',lw=.8);ax.set(yticks=range(3),yticklabels=list(colors),xlabel='Paired success difference (percentage points)',title='Ours G0-multi minus '+ext,ylim=(-.6,2.6));ax.grid(axis='x',alpha=.18)
    fig.suptitle('H10, same 500 test sources; pointwise 95% paired intervals',fontsize=11)
    for ext in ['png','pdf','svg']:fig.savefig(out/('E3_MULTI_PAIRED.'+ext),dpi=180)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.5),layout='constrained')
    for method,color in colors.items():
        rows=sorted([r for r in e5 if r['method']==method],key=lambda r:r['H'])
        for ax,field in zip(axes,['sampling_calls_mean_per_valid','sampling_calls_all_valid_cost_per_success']):ax.plot([r['H'] for r in rows],[r[field] for r in rows],marker={'R':'o','Post':'s','Velocity':'^'}[method],color=color,label=method)
    for ax,title in zip(axes,['Policy samplings per valid episode','All valid policy samplings / successes']):
        ax.set(xlabel='Native horizon H',ylabel=title,xticks=[10,20,30,40,50]);ax.set_ylim(bottom=0);ax.grid(alpha=.18);ax.legend()
    fig.suptitle('G0-multi, 500 valid episodes per cell; retries charged separately',fontsize=11)
    for ext in ['png','pdf','svg']:fig.savefig(out/('E5_MULTI_POLICY_COST.'+ext),dpi=180)
    plt.close(fig)
    note='''# E3/E5 multi-primary CPU update

Existing results only. G0-multi is an explicit method revision after seeing once/multi outcomes; all old once results remain the cap ablation. No new external evaluations, model calls, sampling, fitting, collection or hardware queries were performed for this report.

E3 compares the same 500 source/env/policy seeds at H10. Pointwise 95% intervals resample source within each of the fixed 50 tasks, 2000 draws, seed20260921; they do not include training seed or population-of-tasks uncertainty. External methods retain native behavior and different training data. GAF is the adapted variant. VLA-Corrector includes eight accepted log-derived successes with missing sampling/flow/elapsed evidence; no missing cost is imputed.

E5 separates per-valid-episode means from all valid cost divided by the number of successes. Velocity counts its second full guided sample. All technical failures and corrections remain in the separately referenced physical resource logs. Saved encoder counts exist at whole-worker/job granularity; unavailable valid500 per-episode encoder totals remain null, while contexts, D/G0/Q/action-gradient and sampling/flow are reported from saved counters. No extra probe or reconstruction is used. Reported elapsed times include host/rendering differences and parallelism; sums are not node makespan or GPU kernel time and do not establish a controlled latency ranking.

Added small-network parameters remain 11,912,530 (11.91M); changing multiplicity adds no parameters or updates. Full LIBERO remains SCIENTIFIC_GAP; no Full result has been fabricated. This note is for analysis to incorporate into the shared master; the shared master and raw inputs are unchanged.
'''
    (out/'MASTER_UPDATE.md').write_text(note)
    atomic_json(out/'CPU_RESULT.json',dict(status='complete',utc=utc(),scientific_compute=0,new_episode=0,training_updates=0,large_weight_hashes=0,E3_comparisons=len(paired),E5_cells=len(e5),added_parameters=11912530,inputs=[ref(p) for p in inputs],artifacts=[ref(p) for p in sorted(out.iterdir()) if p.suffix in ('.csv','.md','.png','.pdf','.svg')]))
    print(json.dumps(dict(status='complete',E3_pairs=len(paired),E5_cells=len(e5),output=str(out))))

if __name__=='__main__':main()
