"""Actual saved B11 fields only; fixed parent holdout and upstream GAF windows."""
import json
import time
from pathlib import Path
import paths
from paths import ROOT,CAMPAIGN
from qio import read,new_json,atomic_json,utc,sha


def inverse_commands(commands,q01,q99,eps):
    import numpy as np
    delta=np.asarray(q99,np.float32)-np.asarray(q01,np.float32)
    delta=np.where(delta==0,np.float32(eps),delta)
    return (np.asarray(commands,np.float32)-np.asarray(q01,np.float32))*np.float32(2)/delta-np.float32(1)


def main():
    import numpy as np
    import torch
    from safetensors.numpy import load_file
    from guided_action_flow.training.critic_dataset import build_action_chunk_dataset
    torch.set_num_threads(2)
    start=time.monotonic();holdout=read(ROOT/'config/HOLDOUT.json');base=read(ROOT/'config/BASE.json')
    assert sha(ROOT/'config/HOLDOUT.json')==paths.SUPPLEMENT_SHA
    train=set(holdout['training_parents']);dev=set(holdout['holdout_parents'])
    assert len(train)==15 and len(dev)==2 and not train&dev
    assert sorted(train|dev)[:2]==sorted(dev)
    test=read(ROOT/'config/TEST_SOURCES_V1.json')['rows']
    test_ids={(s['task'],s['env_seed']) for s in test}
    checkpoint=Path(base['checkpoint']);post=read(checkpoint/'policy_postprocessor.json')['steps'][0]
    assert post['config']['norm_map']['ACTION']=='QUANTILES'
    normalizer=checkpoint/post['state_file'];stats=load_file(normalizer)
    q01=stats['action.q01'][:4];q99=stats['action.q99'][:4];eps=post['config']['eps']
    ns=sha(normalizer)
    new_json(ROOT/'data/ACTION_BINDING.json',dict(utc=utc(),normalizer_path=str(normalizer),sha256=ns,
        q01=q01.tolist(),q99=q99.tolist(),eps=eps,
        input='saved transition.normalized_actions[0] is executed bounded physical command',
        output='canonical internal clean policy coordinate: 2*(command-q01)/(q99-q01)-1',
        saturated_commands='inverse boundary coordinate; preclip magnitude is not identifiable from executed command',
        online='GAF clean=x_t-t*v_t first10x4 uses same native policy coordinates',
        fitted_on_holdout=False,new_transform_fit=False))
    indices=CAMPAIGN/'results/B/B11_COMMON_POOL_VIEWS_CPU_V1/indices'
    episodes={'train':[],'development':[]};provenance={'train':[],'development':[]}
    excluded=[];identities=set();parent_sources={};candidate_counts={'train':0,'development':0}
    for parent in sorted(train|dev):
        split='development' if parent in dev else 'train'
        files=sorted((indices/parent).glob('*.json'))
        if not files:raise ValueError('missing frozen parent '+parent)
        for index_path in files:
            idx=read(index_path)
            if 'sequence_bindings' not in idx:continue
            starts=idx['windows']['GAF'];candidate_counts[split]+=len(starts)
            if not starts:continue
            root=Path(idx['root']);n=idx['controls'];bind=idx['sequence_bindings']
            try:
                if idx['parent']!=parent or idx['synthetic'] is not False or idx['split']!='train':raise ValueError('input identity/origin')
                if idx['outcome'] not in (0,1):raise ValueError('complete outcome unavailable')
                sig=idx['input_signatures']
                if sig['normalizer_sha256']!=ns:raise ValueError('frozen normalizer mismatch')
                identity=(sig['normalizer_sha256'],sig['preprocessing_sha256'],sig['encoder_sha256'])
                identities.add(identity)
                lang=np.fromfile(bind['language_ref']['path'],dtype='<f4')
                if lang.shape!=(2048,) or not np.isfinite(lang).all():raise ValueError('actual language payload missing/nonfinite')
                transitions=[read(root/bind['transition_template'].format(step=i)) for i in range(n)]
                states=[];commands=[];success=[];obs_refs=[]
                for i,t in enumerate(transitions):
                    if t['step']!=i or t['next_step']!=i+1 or t['synthetic'] is not False or t['split']!='train':raise ValueError('transition identity/order')
                    if (idx['task'],t['seed']) in test_ids:raise ValueError('test environment identity overlap')
                    if t['source']['parent_episode_id']!=parent:raise ValueError('parent field mismatch')
                    if i<n-1 and (t['terminated'] or t['truncated']):raise ValueError('window crosses terminal')
                    if len(t['successes'])!=1 or type(t['successes'][0]) is not bool:raise ValueError('actual success flag missing')
                    state=np.asarray(t['proprioception'],np.float32);command=np.asarray(t['normalized_actions'][0],np.float32)
                    if state.shape!=(4,) or command.shape!=(4,) or not np.isfinite(state).all() or not np.isfinite(command).all():raise ValueError('actual state/action missing or nonfinite')
                    if (np.abs(command)>1).any():raise ValueError('executed command outside Box')
                    actual_obs=root/bind['observation_template'].format(step=i)
                    next_obs=root/bind['observation_template'].format(step=i+1)
                    if Path(t['observation_ref']['path'])!=actual_obs or Path(t['next_observation_ref']['path'])!=next_obs:raise ValueError('observation reference not genuine branch sequence')
                    # The accepted B11 index already binds all payloads. Read real endpoints,
                    # not RGB pixels or per-frame hashes, to retain the actual observation ABI.
                    if i in (0,n-1):
                        observed=read(actual_obs)
                        if not np.array_equal(np.asarray(observed['proprio'],np.float32),state):raise ValueError('actual observation/proprio mismatch')
                    states.append(state);commands.append(command);success.append(t['successes'][0]);obs_refs.append(t['observation_ref'])
                last_obs=read(root/bind['observation_template'].format(step=n))
                if len(last_obs['proprio'])!=4 or not np.isfinite(last_obs['proprio']).all():raise ValueError('actual terminal observation missing')
                obs_refs.append(transitions[-1]['next_observation_ref'])
                if bool(any(success))!=bool(idx['outcome']):raise ValueError('terminal outcome mismatch')
                if starts!=list(range(n-9)):raise ValueError('eligible window indices unexpectedly filtered')
                seed=transitions[0]['seed'];parent_sources.setdefault(parent,dict(task=idx['task'],env_seed=seed,source=idx['source']))
                if parent_sources[parent]['env_seed']!=seed:raise ValueError('parent crossed env identity')
                ep=dict(state=np.asarray(states,np.float32),action_policy=inverse_commands(commands,q01,q99,eps),
                    success=success,task_features=lang)
                if not np.isfinite(ep['action_policy']).all():raise ValueError('inverse action coordinate nonfinite')
                episodes[split].append(ep)
                provenance[split].append(dict(parent_id=parent,source_id=idx['source'],task=idx['task'],
                    physical_attempt_id=idx['physical_attempt_id'],branch=index_path.stem,root=str(root),index=str(index_path),
                    global_split='train',internal_gaf_split=split,env_seed=seed,controls=n,window_count=len(starts),
                    observation_refs=obs_refs,language_ref=bind['language_ref'],index_targets=idx['windows']['GAF_targets']))
            except (OSError,KeyError,TypeError,ValueError,IndexError) as e:
                excluded.append(dict(parent_id=parent,index=str(index_path),candidate_windows=len(starts),reason=str(e),type=type(e).__name__))
        atomic_json(ROOT/'data/PROGRESS.json',dict(utc=utc(),last_parent=parent,
            branches={k:len(v) for k,v in episodes.items()},excluded_branches=len(excluded)))
    if len(identities)!=1:raise ValueError('feature identities differ across genuine data')
    summaries={}
    for split in ['train','development']:
        if not episodes[split]:raise ValueError('no legal genuine '+split+' inputs')
        data=build_action_chunk_dataset(episodes[split],action_horizon=10,gamma=.99,
            task_feature_source='episode',task_feature_dim=2048)
        targets=torch.tensor([y for p in provenance[split] for y in p['index_targets']],dtype=torch.float32)
        if data['targets'].shape!=targets.shape or not torch.allclose(data['targets'],targets,rtol=0,atol=1e-7):raise ValueError('upstream success-to-go disagrees with accepted view')
        parents=sorted({p['parent_id'] for p in provenance[split]})
        data.update(split=split,parent_ids=parents,synthetic_only=False,feature_identities=list(next(iter(identities))),
            original_global_split='train',gaf_internal_holdout=True,action_binding='ACTION_BINDING.json')
        out=ROOT/'data'/(split+'.pt')
        with out.open('xb') as f:torch.save(data,f)
        for p in provenance[split]:p.pop('index_targets')
        new_json(ROOT/'data'/(split+'_PROVENANCE.json'),provenance[split])
        summaries[split]=dict(path=str(out),actual_windows=len(data['targets']),candidate_windows=candidate_counts[split],
            parent_ids=parents,parent_count=len(parents),physical_branches=len(episodes[split]),
            tasks=sorted({p['task'] for p in provenance[split]}),bytes=out.stat().st_size,
            shapes={k:list(data[k].shape) for k in ['obs_features','action_chunks','task_features','targets']})
    new_json(ROOT/'data/MATERIALIZATION_RESULT.json',dict(status='READY',utc=utc(),elapsed_seconds=time.monotonic()-start,
        genuine_inputs=True,synthetic=False,model_calls=0,hardware_queries=0,summaries=summaries,excluded=excluded,
        parent_source_identities=parent_sources,train_holdout_parent_overlap=[],test_environment_identity_overlap=[],
        original_global_split_unchanged=True,future_parents_included=False,normalizer_ref=dict(path=str(normalizer),sha256=ns),
        limitation='15 train and 2 internal parent-holdout; overlapping windows/branches are not independent parents; limited existing pool'))
    print(json.dumps(summaries,indent=2))

if __name__=='__main__':main()
