"""Read actual B candidate labels/329-vectors; never interpret perturbations as G0."""
import json
from pathlib import Path
import numpy as np
import d24_common as d

def prepare():
    batch=d.load(d.W/'BATCH.json');groups={};invalid=[]
    for job in batch['source_post_jobs']:
        for line in (Path(job['output'])/'development.jsonl').read_text().splitlines():
            row=json.loads(line)
            if row['status']!='complete' or type(row['success']) is not bool or not row.get('cut_data'):
                invalid.append(dict(source=row['source_id'],reason='missing actual cut or terminal outcome'));continue
            with np.load(row['cut_data'],allow_pickle=False) as z:
                feature=z['feature'].copy();ref=z['reference'].copy();candidate=z['candidate'].copy()
            if feature.shape!=(329,) or candidate.shape!=(10,7) or ref.shape!=(10,7):raise ValueError('Native Q fields')
            groups.setdefault(row['parent_id'],[]).append((row,feature,ref,candidate))
    data=[]
    for parent,rows in sorted(groups.items()):
        rows=sorted(rows,key=lambda x:x[0]['candidate_id'])
        if [x[0]['candidate_id'] for x in rows]!=list(range(5)):
            invalid.append(dict(parent=parent,reason='incomplete actual a0/two direction pairs'));continue
        base=rows[0]
        if any(x[0]['intervention_step']!=20 or x[0]['split']!=base[0]['split'] or x[0]['reset_seed']!=base[0]['reset_seed']
               or x[0]['policy_seed']!=base[0]['policy_seed'] for x in rows):raise ValueError('Q parent/cut/seed group')
        # Narrow real common-cut check, no pixels/full simulator-state proof.
        if any(not np.allclose(x[1],base[1],rtol=1e-5,atol=1e-5) or not np.allclose(x[2],base[2],rtol=1e-5,atol=1e-6) for x in rows):
            invalid.append(dict(parent=parent,reason='actual candidate cut/reference does not align'));continue
        a=np.stack([x[3][:5] for x in rows]);actual=np.clip(a,-1,1)
        aliases=np.array([[np.array_equal(x,y) for y in actual] for x in actual])
        cw=1./aliases.sum(1);gw=cw.copy();gw[0]=0
        for i in range(1,5):
            if aliases[0,i]:gw[i]=0
        pw=np.array([float(not aliases[a,b]) for a,b in [(1,2),(3,4)]],np.float32)
        data.append(dict(parent=parent,split=base[0]['split'],feature=base[1],actions=a,reference=base[2][:5],
            outcomes=np.array([float(x[0]['success']) for x in rows],np.float32),cw=cw,gw=gw,pw=pw))
    if not data:raise RuntimeError('No complete native Q parent')
    arrays={key:np.stack([row[key] for row in data]) for key in ['feature','actions','reference','outcomes','cw','gw','pw']}
    arrays['train']=np.asarray([x['split']=='adapt_train' for x in data]);arrays['parents']=np.asarray([x['parent'] for x in data])
    train=arrays['outcomes'][arrays['train']]
    gain=train[:,1:]-train[:,:1]
    pair=np.stack((train[:,1]-train[:,2],train[:,3]-train[:,4]),1)
    status=dict(utc=d.utc(),source_attempts=160,valid_parents=len(data),train_parents=int(arrays['train'].sum()),
        validation_parents=int((~arrays['train']).sum()),actual_train_successes=int(train.sum()),actual_train_outcomes=int(train.size),
        nonzero_train_gain_labels=int(np.count_nonzero(gain)),nonzero_train_pair_labels=int(np.count_nonzero(pair)),
        invalid=invalid,label_repeat_count=1,old_fresh_G0_labels_provided=False,test_read=False)
    status['Q_L11_supervision_ready']=bool(len(np.unique(train))>1 and np.any(gain!=0) and np.any(pair!=0))
    np.savez_compressed(str(d.R/'Q_DEVELOPMENT.npz'),**arrays)
    d.atomic(d.R/'Q_DATA_STATUS.json',status);print(json.dumps(status,indent=2))
    return status

if __name__=='__main__':prepare()
