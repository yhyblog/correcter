"""CPU reconciliation of this task's claims, labels, fits and paired outcomes."""
import json,hashlib,sys,random,csv
from collections import Counter
from pathlib import Path
import numpy as np
import torch
R=Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_D24_XVLA_AUX_RETRAIN_V1')
sys.path.insert(0,str(R/'code'))
from paths import CAMPAIGN
from qio import read,new_json,sha,utc
from common import parent_path
EID='C_71bcb1a80a10790e1ca4fde9ce9cfd99'

def compare(a,b):
    ids=sorted(set(a)&set(b));changes=np.asarray([int(a[s]['success'])-int(b[s]['success']) for s in ids])
    totals=Counter();sizes=Counter()
    for s,d in zip(ids,changes):totals[a[s]['task']]+=int(d);sizes[a[s]['task']]+=1
    tasks=sorted(sizes);rng=random.Random(20260922);draws=[]
    for _ in range(2000):
        sample=rng.choices(range(len(tasks)),k=len(tasks))
        draws.append(100*sum(totals[tasks[i]] for i in sample)/sum(sizes[tasks[i]] for i in sample))
    draws.sort()
    return dict(paired_valid=len(ids),rescued=int((changes==1).sum()),harmed=int((changes==-1).sum()),
        difference_pp=float(100*changes.mean()),task_cluster_bootstrap_95_CI_pp=[draws[49],draws[1949]])

def main():
    torch.set_num_threads(2)
    event=read(CAMPAIGN/'persistent_queue/nodes/C/wakeup/outbox'/(EID+'.json'))
    assert event['job']['task_id']==R.name and not event['synthetic']
    assert sha(event['job']['claim_identity']['path'])==event['job']['claim_identity']['sha256']
    claim=read(R/'CLAIM.json');cfg=read(R/'config/CONFIG.json')
    for k in ['config','method_frozen','CPU_check']:assert sha(claim[k]['path'])==claim[k]['sha256']
    for k in ['source_manifest','test_sources','method_frozen']:assert sha(cfg[k]['path'])==cfg[k]['sha256']
    assert claim['authorization_sha256']==sha(CAMPAIGN/'deadline_20260924/PER_BASE_AUXILIARY_TRAINING_AUTHORIZATION_V1.json')
    result=read(R/'RESULT.json');assert result==event['result'] and result['status']=='complete'
    claims={}
    for p in (R/'claims/attempts').glob('*.json'):
        row=read(p);assert p.stem==hashlib.sha256(row['identity'].encode()).hexdigest();assert row['identity'] not in claims
        claims[row['identity']]=dict(row,path=str(p))
    assert len(claims)==3430 and {r['number'] for r in claims.values()}==set(range(1,3431))
    assert read(R/'ATTEMPT_COUNTER.json')['reserved_attempts']==3430
    parent_claims={read(p)['identity']:read(p) for p in (R/'claims/parents').glob('*.json')}
    manifest=read(R/'SOURCE_MANIFEST.json');parents=manifest['parents'];assert len(parent_claims)==len(parents)==250
    consumed=set();outcomes=Counter();gains={};normal=Counter();cuts=Counter();parent_rows=[]
    for source in parents:
        sid=source['source_id'];assert parent_claims[sid]['source']==source
        folder=parent_path(source);parent=read(folder/'RESULT.json');assert parent['status']=='complete' and parent['source']==source
        normal_only=parent['normal_only'];normal[source['split']]+=int(normal_only)
        expected=[('old',0)] if normal_only else [(c,r) for c in ['old','a0','local_plus','local_minus'] for r in [0,1]]
        actual=list(folder.glob('*/RESULT.json'));assert len(actual)==len(expected)==parent['real_rollouts'];rows={}
        for candidate,repeat in expected:
            ep=folder/(candidate+'_r'+str(repeat));row=read(ep/'RESULT.json');ident=f'{sid}/{candidate}/{repeat}'
            assert ident in claims and row['claim']==claims[ident]['path'] and read(ep/'ENTERED.json')['claim']==row['claim']
            assert claims[ident]['phase']=='collect' and claims[ident]['source_id']==sid
            assert row['status']=='complete' and type(row['success']) is bool and row['source_id']==sid and row['task']==source['task']
            assert row['candidate']==candidate and row['repeat']==repeat and row['split']==source['split'] and row['cut']==source['cut']
            assert row['suffix_seed']==source['suffix_policy_seeds'][repeat] and 0<row['steps']<=300
            assert row['physics']==dict(timestep=.0025,frame_skip=5,action_scale=.01)
            assert Path(row['trajectory']).is_file();consumed.add(ident);outcomes['success' if row['success'] else 'failure']+=1;rows[candidate,repeat]=row
        if normal_only:
            assert rows['old',0]['normal_only'] and rows['old',0]['steps']<=source['cut']
        else:
            bank=read(folder/'BANK.json');assert bank['fresh_plan_count']==1 and bank['old_queue_age']==5 and bank['old_remaining_native_commands']==5
            gain=sum(int(rows['a0',r]['success'])-int(rows['old',r]['success']) for r in [0,1])/2
            gains[sid]=gain;cuts[source['split'],source['cut']]+=1
        parent_rows.append(dict(source_id=sid,split=source['split'],cut=source['cut'],normal_only=normal_only,real_rollouts=len(expected),G0_target=gains.get(sid)))
    assert sum(normal.values())==10 and outcomes==Counter(success=1589,failure=341)
    data=read(R/'DATA_SUMMARY.json');train=torch.load(R/'dataset/train_parents.pt',map_location='cpu',weights_only=True)
    dev=torch.load(R/'dataset/development_parents.pt',map_location='cpu',weights_only=True)
    for split,values in [('train',train),('development',dev)]:
        ids=[p['source_id'] for p in parents if p['split']==split and p['source_id'] in gains]
        assert values['parent_ids']==ids and bool(values['G0_valid'].all())
        np.testing.assert_array_equal(values['G0_target'].numpy(),[gains[s] for s in ids])
    hist=dict(Counter(map(str,train['G0_target'].tolist())));assert hist==data['G0_target_histogram'] and len(hist)>1
    assert int((train['gain_weights']>0).sum())==data['Q_identifiable_gain_labels']==372
    assert int((train['pair_weight']>0).sum())==data['Q_identifiable_pairs']==186
    trajectories=read(R/'dataset/TRAJECTORIES.json');window_counts={}
    for name,split in [('train','train'),('dev','development')]:
        windows=np.load(R/'dataset'/(name+'_windows.npy'));window_counts[name]=len(windows)
        for ti in np.unique(windows[:,0]):
            t=trajectories[int(ti)];times=windows[windows[:,0]==ti,1]
            assert t['split']==split and times.min()>=max(4,t['minimum_step']) and times.max()+5<t['length']
        assert len(windows)==data[name+'_windows']
    assert read(R/'dataset/NORMALIZATION.json')['fit_split']=='train'
    fit=read(R/'FIT_SUMMARY.json');assert fit['updates']==32000 and len(fit['members'])==8
    for kind in ['D','G0','Q']:
        for seed in cfg[kind+'_seeds']:
            name=f'{kind}_{seed}';row=read(R/'fits'/name/'RESULT.json');assert fit['members'][name]==row
            fc=read(R/'claims/fits'/(name+'.json'));assert fc['kind']==kind and fc['seed']==seed and fc['reserved_update_cap']==4000
            assert row['status']=='complete' and row['updates']==4000 and row['initialization']=='from scratch' and row['all_parameters_trained']
            assert Path(row['checkpoint']).is_file() and row['history'][-1]['updates']==4000
            if kind=='Q':assert row['parameters']==7058
    ranking=read(R/'models/Q_selected/ranking.json')
    for i,seed in enumerate(cfg['Q_seeds']):
        assert ranking['model_hashes'][str(i)]==sha(R/'models/Q_selected/models/refit'/f'member_{i}'/'selected.pt')==sha(R/'fits'/f'Q_{seed}'/'final.pt')
    sources=read(R/'config/TEST_SOURCES.json')['sources'];methods={};groups=[];first_cuts={}
    for method in ['R','Post','Velocity']:
        results=list((R/'evaluation'/method).glob('*/RESULT.json'));assert len(results)==500;byid={};counters=Counter();encoder=Counter()
        for source in sources:
            sid=source['source_id'];ep=R/'evaluation'/method/sid;row=read(ep/'RESULT.json');ident=method+'/'+sid
            assert row['claim']==claims[ident]['path'] and read(ep/'ENTERED.json')['claim']==row['claim'] and claims[ident]['phase']=='evaluate'
            assert row['status']=='complete' and type(row['success']) is bool and all(row[k]==v for k,v in source.items()) and row['method']==method
            assert row['physics']==dict(timestep=.0025,frame_skip=5,action_scale=.01) and 0<row['steps']<=300
            trigger=[e for e in row['events'] if e['trigger']];assert len(trigger)==row['interventions'] and len(trigger)<=1
            assert row['first_cut']==(trigger[0]['step'] if trigger else None)
            for e in trigger:
                assert e['legal_cut'] and e['gate']>.05 and e['step']%5==0 and e['queue_age']==5 and e['commit_until']==e['step']+10
                assert e['restore_native_K']==10 and not e['Q_acceptance_gate']
                if method=='Velocity':
                    gu=e['guidance'];assert gu['flow_calls']==10 and len(gu['updates'])==3
                    np.testing.assert_allclose([u['tau'] for u in gu['updates']],[.3,.2,.1],atol=1e-5)
                    assert all(u['action_only_backward'] and u['native_inverse_normalization'] and u['true_clamp'] for u in gu['updates'])
                if method in ['Post','Velocity']:assert e['matching']['other_directions_used'] is False
            n=row['interventions'];ec=row['encoder_counters'];pc=row['counters'];gradient=(0 if method=='R' else 1 if method=='Post' else 3)*n
            assert ec.get('action_gradient_calls',0)==ec.get('Q_ensemble_forward_calls',0)==gradient
            assert ec.get('Q_member_forward_calls',0)==gradient*4 and pc.get('candidate_queries',0)==n*(2 if method=='Velocity' else 1)
            assert pc['policy_flow_calls']==pc['policy_queries']*10 and ec['D_forward_calls']==ec['G0_forward_calls']==ec['monitor_calls']*2
            byid[sid]=row;consumed.add(ident);counters.update(pc);encoder.update(ec)
        methods[method]=byid;first_cuts[method]={s:r['first_cut'] for s,r in byid.items()}
        groups.append(dict(method=method,valid=500,successes=sum(r['success'] for r in byid.values()),trigger_once=sum(r['interventions'] for r in byid.values()),
            policy_calls=counters['policy_queries'],flow_calls=counters['policy_flow_calls'],Q_calls=encoder.get('Q_ensemble_forward_calls',0),gradient_calls=encoder.get('action_gradient_calls',0)))
    assert first_cuts['R']==first_cuts['Post']==first_cuts['Velocity']
    assert consumed==set(claims) and sum(g['valid'] for g in groups)==1500
    old=read(CAMPAIGN/'work/C/C_D24_MW_VELOCITY_V1_r2/MW_VELOCITY_BATCH.json')
    baseline={x['source_id']:x for x in read(old['baseline_index'])['xvla']};references={'N':baseline,'R':methods['R']}
    for arm,batch in [('Post',read(old['post_batch'])),('Velocity',old)]:
        refs={}
        for job in batch['jobs']:
            if job['kind']=='xvla':
                for p in (Path(job['output'])/'episodes').glob('*/RESULT.json'):
                    v=read(p)
                    if v['status']=='complete':refs[v['source_id']]=v
        references[arm+'_frozen_pi05_heads']=refs
    paired=read(R/'PAIRED_COMPARISONS.json');independent={}
    for key,record in paired.items():
        method,ref=key.split('_vs_');ref=method+'_'+ref if ref=='frozen_pi05_heads' else ref
        checked=compare(methods[method],references[ref])
        for k,v in checked.items():np.testing.assert_allclose(v,record[k],atol=1e-12,rtol=0)
        independent[key]=checked
    csv_rows=list(csv.DictReader((R/'FINAL_EPISODES.csv').open()));assert len(csv_rows)==1500
    assert len({(x['method'],x['source_id']) for x in csv_rows})==1500
    for x in csv_rows:assert (x['success']=='True')==methods[x['method']][x['source_id']]['success'] and x['status']=='complete'
    audit=dict(status='passed',utc=utc(),event_id=EID,task_id=R.name,claim_matches_event=True,small_input_seals_match=True,
        parent_claims=250,collection_rollouts=1930,normal_only_parents=dict(normal),collection_outcomes=dict(outcomes),
        independent_parent_labels_checked=len(gains),G0_train_eligible=len(train['parent_ids']),G0_dev_eligible=len(dev['parent_ids']),G0_target_histogram=hist,
        Q_identifiable_gain_labels=372,Q_identifiable_pairs=186,window_counts=window_counts,
        training_members=8,updates_per_member=4000,total_updates=32000,base_updates=0,external_encoder_updates=0,
        selected_Q_matches_all4_fixed4000_members=True,evaluation=groups,same_first_trigger_cuts_across_arms=True,
        attempt_claims=3430,all_claims_have_one_terminal=True,unknown_claims=0,technical_failures=0,retries=0,cumulative_C_attempts=10443,
        old_completed_replays=0,N_reused_without_execution=True,independent_paired_comparisons=independent,
        review_scope='Current task small per-source terminal/claim records, prepared parent labels/window indexes, fit receipts and small Q exports; no simulator replay, full state/RGB audit, large weight hash or GPU probe',
        limitation='Train-only PCA/norm checked through sealed split lineage, saved train labels/window indices and implementation; no full re-encoding or feature-statistic recomputation',
        statistical_interpretation='All reported paired intervals include zero; no established benefit of Full over R or N; revealed500 adaptation comparison')
    new_json(R/'evidence/SCIENTIFIC_TERMINAL_AUDIT.json',audit)
    with (R/'COLLECTION_PARENTS.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(parent_rows[0]));writer.writeheader();writer.writerows(parent_rows)
    print(json.dumps({k:audit[k] for k in ['status','parent_claims','collection_rollouts','training_members','total_updates','evaluation','attempt_claims','unknown_claims','technical_failures']}))

if __name__=='__main__':main()
