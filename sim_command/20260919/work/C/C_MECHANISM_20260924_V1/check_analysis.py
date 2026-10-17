"""Small synthetic paired-outcome check; never writes into real scientific results."""
import tempfile
from pathlib import Path
import paths,common,analyze
from common import write,uid

def main():
    root=Path(tempfile.mkdtemp(prefix='mechanism_analysis_check_'))
    common.ROOT=root;analyze.ROOT=root
    sources=[dict(source_id=f's{i}',task='fixture',split='test') for i in range(3)]
    write(root/'SOURCES.json',sources);jobs=[];aliases=[]
    for s in sources:
        folder=root/'pool'/s['source_id']/'cut005';write(folder/'FINAL_SCORE.json',dict(source=s,cut=5,score=dict(G0=.2,D5=.3,risk=.4,nod=.1)))
        write(folder/'snapshot/STATE.json',dict(cut=5))
        meta=root/'metadata'/s['source_id'];p=lambda prob,gain:dict(candidate_mean_probability=prob,mean_gain=gain)
        write(meta,dict(predictions={'L11':dict(base=p(.25,0),corrected=p(.75,.5),probe_plus=p(.8,.55),probe_minus=p(.2,-.05))}))
        for rep in range(4):
            for suffix in ['native10','deploy10']:
                for arm,C,success in [('continue',10,False),('R',10,False),('L11',10,True),('probe_plus',10,True),('probe_minus',10,False),('R',5,True)]:
                    j=dict(id=uid(s['source_id'],rep,suffix,arm,C),kind='branch',source=s,rep=rep,arm=arm,C=C,suffix=suffix,bank_meta=str(meta));jobs.append(j)
                    r=dict(job=j,status='complete',success=success,cut=5,steps=100,interventions=0,policy_calls=10,inference_seconds=1.,rpc_seconds=1.,monitors=0,action_gradients=0)
                    write(common.terminal_path(j),r)
    broken=dict(id='broken',kind='branch',source=sources[0],rep=0,arm='L00',C=10,suffix='native10');jobs.append(broken)
    write(common.terminal_path(broken),dict(job=broken,status='technical_failure',success=None))
    write(root/'JOBS_local.json',jobs);write(root/'ALIASES.json',aliases)
    for phase in ['budget','cost']:
        j=dict(id=phase,kind='closed',source=sources[0],H=10,trigger='G0',threshold=.05,method='Post');write(root/('JOBS_'+phase+'.json'),[j])
        write(common.terminal_path(j),dict(job=j,status='complete',success=True,steps=99,interventions=1,policy_calls=9,inference_seconds=1.,rpc_seconds=2.,monitors=5,action_gradients=1,warm_timing_samples={'plan':[.1,.2]}))
    result=analyze.main()
    assert result['real_units']['technical_failure']==1 and result['technical_missing_imputed'] is False
    import csv
    rows=list(csv.DictReader((root/'analysis/CD_LOCAL_EFFECTS.csv').open()))
    final=[r for r in rows if r['arm']=='L11' and r['suffix']=='native10'][0]
    assert float(final['mean'])==1 and float(final['rescue'])==1 and float(final['harm'])==0 and int(final['parents'])==3
    metrics=list(csv.DictReader((root/'analysis/C_PREDICTION_METRICS.csv').open()))
    assert float(metrics[0]['brier'])==.0625 and float(metrics[0]['novel_direction_accuracy'])==1
    print('PASS: known paired gain/rescue/harm, source cluster count, Brier, novel-direction ranking, technical failure excluded, all chart exporters. Synthetic output:',root)

if __name__=='__main__':main()
