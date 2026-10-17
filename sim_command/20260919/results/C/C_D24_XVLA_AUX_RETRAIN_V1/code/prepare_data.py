"""Actual collection -> train-only normalization/PCA and correctly masked labels."""
import json
from collections import Counter
from pathlib import Path
import numpy as np
import torch
import paths
from paths import ROOT
from qio import read,atomic_json,utc
from common import parent_path,boundary
from corrector.critic import STATE_KEYS,observed_features
from experiments.native10_training_20260916.training import fit_pca

def context(bank,cut):
    return dict(history=bank['features'][-5:].astype(np.float32),history_mask=np.ones(5,bool),
        proprio=bank['props'][-5:].astype(np.float32),proprio_mask=np.ones(5,bool),past_actions=bank['prefix_actions'][-4:].astype(np.float32),
        language=bank['language'].astype(np.float32),remaining=np.float32((300-cut)/300))

def main():
    boundary(admission=True);torch.set_num_threads(4)
    destination=ROOT/'dataset';manifest=read(ROOT/'SOURCE_MANIFEST.json');trajectories=[];parents=[];counts=Counter();cut_counts=Counter()
    for source in manifest['parents']:
        folder=parent_path(source);completed=folder/'RESULT.json'
        if not folder.exists():counts['parent_unstarted']+=1;continue
        parent=read(completed) if completed.exists() else {}
        counts['parent_complete' if completed.exists() else 'parent_partial']+=1
        counts['normal_only']+=int(parent.get('normal_only',False))
        bank_path=folder/'BANK.npz';rows={}
        for candidate in ['old','a0','local_plus','local_minus']:
            for repeat in [0,1]:
                ep=folder/(candidate+'_r'+str(repeat));rp=ep/'RESULT.json'
                if not rp.exists():continue
                row=read(rp);rows[(candidate,repeat)]=row;counts['rollout_'+row['status']]+=1
                if row['status']!='complete':continue
                counts['success' if row['success'] else 'failure']+=1
                with np.load(ep/'trajectory.npz',allow_pickle=False) as z:
                    length=len(z['spatial']);assert len(z['actions'])==length-1
                    assert z['spatial'].shape==(length,4096) and z['proprio'].shape==(length,4)
                # Prefix replay uses the same stored encoding; its windows are
                # included only once, instead of multiplying identical rows.
                minimum=4 if candidate=='old' and repeat==0 else max(4,source['cut'])
                trajectories.append(dict(path=str(ep/'trajectory.npz'),source_id=source['source_id'],split=source['split'],
                    task=source['task'],candidate=candidate,repeat=repeat,length=length,minimum_step=minimum,
                    cut=source['cut'],unique_observation_start=0 if candidate=='old' and repeat==0 else source['cut']+1))
        if not bank_path.exists():continue
        with np.load(bank_path,allow_pickle=False) as z:bank={k:z[k].copy() for k in z.files}
        cut_counts[(source['split'],source['cut'])]+=1
        qnames=['a0','local_plus','local_minus'];outcomes=np.full((3,2),-1,np.float32)
        for i,name in enumerate(qnames):
            for r in [0,1]:
                row=rows.get((name,r))
                if row and row['status']=='complete':outcomes[i,r]=float(row['success'])
        valid=outcomes>=0;repeats=valid.sum(1);labels=np.where(valid,outcomes,0).sum(1)/np.maximum(repeats,1)
        actions=np.stack([np.clip(bank[n][:10],-1,1) for n in qnames]).astype(np.float32)
        groups=[]
        for i,a in enumerate(actions):
            prior=next((j for j in range(i) if np.array_equal(actions[j],a)),None);groups.append(i if prior is None else groups[prior])
        multiplicity=Counter(groups[i] for i in range(3) if repeats[i]>0)
        cw=np.asarray([1/multiplicity[groups[i]] if repeats[i] else 0 for i in range(3)],np.float32)
        gw=np.asarray([0]+[cw[i] if repeats[0]==repeats[i]==2 and groups[i]!=groups[0] else 0 for i in [1,2]],np.float32)
        pair=np.float32(repeats[1]==repeats[2]==2 and groups[1]!=groups[2])
        old=[rows.get(('old',r)) for r in [0,1]]
        gvalid=bool(repeats[0]==2 and all(x and x['status']=='complete' and not x.get('normal_only') for x in old))
        gain=np.float32(labels[0]-np.mean([x['success'] for x in old])) if gvalid else np.float32(0)
        local=[]
        for name in ['old','a0','local_plus','local_minus']:
            path=folder/(name+'_r0')/'trajectory.npz';row=rows.get((name,0))
            if not row or row['status']!='complete' or not path.exists():local=[];break
            with np.load(path,allow_pickle=False) as z:
                cut=source['cut'];T=len(z['actions']);ii=np.minimum(cut+np.arange(1,6),T);ai=np.minimum(cut+np.arange(5),max(0,T-1))
                mask=cut+np.arange(1,6)<=T
                if not mask.all():local=[];break
                local.append(dict(actions=z['actions'][ai].copy(),targets=z['spatial'][ii].astype(np.float32),future_mask=mask,
                    target_proprio=z['proprio'][ii].copy(),target_proprio_mask=mask.copy()))
        parents.append(dict(source=source,state=context(bank,source['cut']),old_five=bank['old_next_five'].copy(),
            actions=actions,outcomes=outcomes,labels=labels,candidate_weights=cw,gain_weights=gw,pair_weight=pair,
            G0_valid=gvalid,G0_target=gain,local=local,aliases=groups,repeats=repeats))
    total=sum(t['length'] for t in trajectories)
    if not total:raise RuntimeError('no actual trajectory data')
    shapes={'states':(total,4096),'proprio':(total,4),'actions':(total,4)}
    maps={k:np.lib.format.open_memmap(destination/(k+'.npy'),mode='w+',dtype=np.float16 if k=='states' else np.float32,shape=v) for k,v in shapes.items()}
    train_indices=[];dev_indices=[];sum_x=np.zeros(4096,np.float64);sum_sq=np.zeros(4096,np.float64);sum_delta=np.zeros(4096,np.float64);n=nd=0;offset=0
    languages=[]
    for ti,t in enumerate(trajectories):
        boundary();t['offset']=offset
        with np.load(t['path'],allow_pickle=False) as z:
            states=z['spatial'];length=t['length'];maps['states'][offset:offset+length]=states
            maps['proprio'][offset:offset+length]=z['proprio'];maps['actions'][offset:offset+length-1]=z['actions'];maps['actions'][offset+length-1]=0
            languages.append(z['language'].astype(np.float32))
            indices=train_indices if t['split']=='train' else dev_indices
            indices.extend((ti,s) for s in range(t['minimum_step'],length-5))
            if t['split']=='train':
                unique=states[t['unique_observation_start']:].astype(np.float64)
                sum_x+=unique.sum(0);sum_sq+=np.square(unique).sum(0);n+=len(unique)
                start=max(5,t['unique_observation_start']);delta=states[start:].astype(np.float64)-states[start-5:len(states)-5].astype(np.float64) if start<len(states) else np.empty((0,4096))
                sum_delta+=np.square(delta).sum(0);nd+=len(delta)
            offset+=length
    for x in maps.values():x.flush()
    if n==0 or nd==0 or not train_indices:raise RuntimeError('no valid train dynamics windows')
    mean=sum_x/n;std=np.sqrt(np.maximum(sum_sq/n-mean**2,0)).clip(.01);delta=np.maximum(np.sqrt(sum_delta/nd),std*.01)
    norm=dict(mean=mean.tolist(),std=std.tolist(),delta_scale=delta.tolist(),fit_split='train',observations=n,delta_windows=nd)
    atomic_json(destination/'NORMALIZATION.json',norm)
    np.save(destination/'languages.npy',np.stack(languages));np.save(destination/'train_windows.npy',np.asarray(train_indices,np.int64));np.save(destination/'dev_windows.npy',np.asarray(dev_indices,np.int64))
    atomic_json(destination/'TRAJECTORIES.json',trajectories)
    def pack(split):
        selected=[p for p in parents if p['source']['split']==split]
        if not selected:return None
        values={k:torch.as_tensor(np.stack([p['state'][k] for p in selected])) for k in STATE_KEYS}
        for k in ['old_five','actions','outcomes','labels','candidate_weights','gain_weights','pair_weight','G0_valid','G0_target','repeats']:
            values[k]=torch.as_tensor(np.stack([p[k] for p in selected]))
        values['parent_ids']=[p['source']['source_id'] for p in selected];values['tasks']=[p['source']['task'] for p in selected]
        torch.save(values,destination/(split+'_parents.pt'))
        local=[p for p in selected if len(p['local'])==4]
        if local:
            loc={k:torch.as_tensor(np.stack([np.stack([p['state'][k]]*4) for p in local])) for k in STATE_KEYS}
            for k in ['actions','targets','future_mask','target_proprio','target_proprio_mask']:
                loc[k]=torch.as_tensor(np.stack([np.stack([x[k] for x in p['local']]) for p in local]))
            torch.save(loc,destination/(split+'_local.pt'))
        return values
    train=pack('train');dev=pack('development')
    if train is None:raise RuntimeError('no reached training parents')
    g=train['G0_valid'];targets=train['G0_target'][g];G0_ready=bool(len(targets)>1 and targets.min()!=targets.max())
    qi=train['candidate_weights'][:,0]>0;Q_ready=bool(qi.sum()>16 and train['pair_weight'][qi].sum()>0 and train['gain_weights'][qi].sum()>0)
    if Q_ready:
        with torch.no_grad():
            visual,language,_=observed_features({k:train[k][qi] for k in STATE_KEYS},torch.tensor(mean,dtype=torch.float32),torch.tensor(std,dtype=torch.float32))
            preprocessing=dict(norm_mean=torch.tensor(mean,dtype=torch.float32),norm_std=torch.tensor(std,dtype=torch.float32),residual_scale=torch.tensor([.15,.15,.15,.4]))
            for name,v,width in [('visual',visual,16),('language',language,8)]:
                for suffix,tensor in zip(['center','basis','scale'],fit_pca(v,width)):preprocessing[name+'_'+suffix]=tensor
        torch.save(preprocessing,destination/'Q_PREPROCESSING.pt')
    report=dict(status='complete',at_utc=utc(),planned_parents=250,counts=dict(counts),reached_parents=len(parents),
        cut_counts=[dict(split=k[0],cut=k[1],parents=v) for k,v in sorted(cut_counts.items())],
        train_windows=len(train_indices),dev_windows=len(dev_indices),train_reached_parents=len(train['parent_ids']),
        dev_reached_parents=len(dev['parent_ids']) if dev else 0,unique_parent_ids=True,
        G0_eligible_train_parents=int(g.sum()),G0_target_histogram=dict(Counter(map(str,targets.tolist()))),
        G0_nonzero_targets=int((targets!=0).sum()),G0_ready=G0_ready,
        Q_absolute_train_parents=int(qi.sum()),Q_identifiable_gain_labels=int((train['gain_weights']>0).sum()),
        Q_identifiable_pairs=int((train['pair_weight']>0).sum()),Q_nonzero_observed_gains=int((((train['labels']-train['labels'][:,:1])!=0)&(train['gain_weights']>0)).sum()),Q_ready=Q_ready,
        D_ready=True,normalization_train_only=True,PCA_train_only=True,base_updates=0,external_encoder_updates=0,
        missing_labels_not_failure=True,technical_failures_not_training_targets=True,
        scientific_gaps=([] if G0_ready else ['G0 target missing or constant; stop R/Post/Velocity'])+([] if Q_ready else ['Q candidate supervision/PCA coverage missing; stop Post/Velocity']))
    atomic_json(ROOT/'DATA_SUMMARY.json',report);print(json.dumps(report))

if __name__=='__main__':main()
