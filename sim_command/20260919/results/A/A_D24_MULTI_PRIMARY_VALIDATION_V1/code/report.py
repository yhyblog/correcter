"""Bounded, CPU-only stage/cell/terminal publication."""
import argparse
import json
import sys
import traceback
from pathlib import Path
import paths
from paths import ROOT,CAMPAIGN,TASK
from qio import read,atomic_json,utc,ref
from publication_data import load_evidence,finite_values,EvidenceConflict
from analysis_tools import write_csv,read_csv,pair,holm,compact,costs

def publish_report(cell=None,terminal=False):
    cfg=read(ROOT/'config/CONFIG.json');jobs,attempts,claims,selected=load_evidence(only=cell)
    target=ROOT if terminal else ROOT/'cells'/cell;target.mkdir(parents=True,exist_ok=True)
    rows=[compact(r) for r in selected];cells=[];resources={};groups={}
    for c in cfg['cells']:
        if cell and c['cell_id']!=cell:continue
        key=c['cell_id'];data=[r for r in rows if r['cell_id']==key];good=[r for r in data if r['status']=='complete'];n=len(good)
        groups[key]=good;ints=[r['interventions'] for r in good]
        cells.append(dict(c,valid=n,successes=sum(r['success'] for r in good),success_rate=sum(r['success'] for r in good)/n if n else None,complete=n==c['planned_episodes'],interventions_mean=sum(ints)/n if n else None,interventions_max=max(ints) if ints else None,multiple_proportion=sum(i>=2 for i in ints)/n if n else None,technical_failures=sum(r['status']!='complete' for r in data),unstarted=c['planned_episodes']-sum(x['cell_id']==key for x in claims)))
        resources[key]=costs(data)
    write_csv(target/'FINAL_EPISODES.csv',rows);write_csv(target/'FINAL_CELLS.csv',cells)
    paired=[]
    if terminal:
        e6=['E6_G0-multi_R_H10','E6_D5-multi_R_H10']
        if all(len(groups.get(k,[]))==50 for k in e6):paired.append(pair(groups[e6[0]],groups[e6[1]],name='E6 G0-multi minus D5-multi'))
        for seed in (9101,9102,9103):
            for method in ('Post','Velocity'):
                base=f'E1_L11_s{seed}_{method}_H10'
                for loss in ('L00','L01','L10'):
                    key=f'E1_{loss}_s{seed}_{method}_H10'
                    if len(groups.get(key,[]))==len(groups.get(base,[]))==50:paired.append(pair(groups[base],groups[key],name=base+' minus '+key))
        baselines=read(ROOT/'config/COMPLETED_MULTI_BASELINES.json')['rows'];random_pairs=[]
        for c in cfg['cells']:
            if c['stage']!='Random' or len(groups.get(c['cell_id'],[]))!=500:continue
            base=[r for r in baselines if r['method']==c['method'] and r['H']==c['H']]
            row=pair(groups[c['cell_id']],base,name=c['cell_id']+' minus G0-multi');row.update(method=c['method'],H=c['H']);random_pairs.append(row)
        holm(random_pairs);paired+=random_pairs
        write_csv(target/'PAIRED.csv',paired);atomic_json(target/'PAIRED.json',paired)
        import matplotlib;matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(1,3,figsize=(12,3.5),layout='constrained')
        for ax,method in zip(axes,['R','Post','Velocity']):
            for mode in ['G0-multi','Random-multi']:
                xs=[];ys=[]
                for H in [10,20,30,40,50]:
                    data=[r for r in baselines if r['method']==method and r['H']==H] if mode=='G0-multi' else groups.get(f'Random_multi_{method}_H{H}',[])
                    if len(data)==500:xs.append(H);ys.append(100*sum(r['success'] for r in data)/500)
                ax.plot(xs,ys,'o-',label=mode)
            ax.set(title=method,xlabel='Native horizon H',ylabel='Success (%)',ylim=(0,100));ax.legend()
        for ext in ('png','pdf','svg'):fig.savefig(target/('RANDOM_MULTI_H_CURVES.'+ext),dpi=180)
        plt.close(fig)
        lines=['# Multi-primary validation','',f'Valid {sum(c["valid"] for c in cells)}/8800; physical entered {len(claims)}; prior A attempts14376 preserved.','',
        'This is an explicit method revision after viewing once/multi results. Old results and failures are retained. No training or collection. E1 retains Mesa/30Hz/400Hz/.015 and its 48 fixed checkpoints; three fits are not 150 independent states. E6 reuses the original dev threshold, whose episode alarm match is not a multi-count match. Random-multi uses p=.5 at each actual legal point; comparison with Random-once is not a pure cap effect. Full LIBERO remains a scientific gap.','',
        'Per-episode costs exclude technical attempts; RESOURCE_SUMMARY retains physical failures separately. Elapsed episode sums are not end-to-end wall time. CPU E3/E5 updates are in summaries/. Shared master is edited by analysis only.']
        (ROOT/'MASTER_UPDATE.md').write_text('\n'.join(lines)+'\n')
    summary=dict(task_id=TASK,utc=utc(),valid=sum(c['valid'] for c in cells),actual_attempts=len(claims),technical_failures=sum(r['status']!='complete' for r in attempts),stage_planned=8800,cells=cells,compute_complete=terminal and all(c['complete'] for c in cells),training_updates=0,new_collection=0)
    atomic_json(target/'RESOURCE_SUMMARY.json',dict(utc=utc(),cells=resources,actual_attempts=len(claims),prior_A_attempts=14376,A_cumulative_attempts=14376+len(claims),failed_attempts=[compact(r) for r in attempts if r['status']!='complete'],loading_and_lifecycle_separate=str(ROOT/'chain'),unknown_inflight_cost_not_zero=True))
    atomic_json(target/'FINAL_SUMMARY.json',finite_values(summary))
    atomic_json(target/'PUBLICATION.json',dict(status='published',utc=utc(),cell=cell,terminal=terminal,scientific_compute=0,valid=summary['valid'],artifacts=[ref(target/n) for n in ['FINAL_EPISODES.csv','FINAL_CELLS.csv','RESOURCE_SUMMARY.json','FINAL_SUMMARY.json']]))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cell');p.add_argument('--terminal',action='store_true');p.add_argument('--error-json',required=True);a=p.parse_args()
    try:publish_report(a.cell,a.terminal)
    except BaseException as e:
        code=2 if isinstance(e,EvidenceConflict) else 3 if isinstance(e,OSError) else 1
        atomic_json(a.error_json,dict(type=type(e).__name__,message=str(e),traceback=traceback.format_exc(),publication_error=True,scientific_workers_must_continue=code==1));sys.exit(code)
