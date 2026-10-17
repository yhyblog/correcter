"""Train-only descriptive diagnostics; never load a bundle, model, PCA or simulator.

The 600-source package is checked against both independently sealed children,
including every common array one key at a time. The bundle's development paths
are never opened. Source-task multinomial bootstrap matches train300 exactly.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/native10_training_20260916'
DEFAULT_DEST = OUT / 'progress_audits/train600_direction_v1'
BOOTSTRAPS = 10000
BOOTSTRAP_SEED = 2026091621
PAIRS = [(1,2),(3,4),(5,6),(7,8),(11,12)]
DIAGNOSTIC_KEYS = ('outcomes','control_outcomes','control_valid','raw_actions',
    'candidate_weights','gain_weights','pair_indices','pair_weights','alias_indices',
    'episode_id','task','cut_step','split','round','planned_slot_id')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''): h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def dump(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def count(values):
    return dict(sorted(Counter(map(str,values)).items()))


def sealed_train(path, *, rounds, parent_seal=None):
    path=Path(path).resolve()
    if parent_seal is None:
        seal_path=path/'complete.json';seal=read(seal_path)
        expected={name:seal['files'][name] for name in ('arrays.npz','metadata.json','rows.json')}
        if set(seal['files']) != set(expected): raise ValueError('Unexpected child file set')
    else:
        seal_path=Path(parent_seal);seal=read(seal_path)
        if path != seal_path.parent/'train': raise ValueError('Only the train bundle subdirectory may be opened')
        expected={name:seal['files']['train/'+name] for name in ('arrays.npz','metadata.json','rows.json')}
    if seal['status']!='complete': raise ValueError('Unsealed train packet')
    for name,digest in expected.items():
        if sha(path/name)!=digest: raise ValueError('Changed train packet: '+name)
    metadata=read(path/'metadata.json');rows=read(path/'rows.json');n=300*len(rounds)
    if (metadata['purpose']!='train' or metadata['selected_rounds']!=rounds
            or metadata['planned_episode_count']!=n or metadata['complete_critic_groups']!=n
            or len(rows)!=n or len(metadata['records'])!=n): raise ValueError('Incomplete/nontrain packet')
    if any(r['split']!='train' or r['round'] not in rounds for r in rows): raise ValueError('Nontrain source')
    if any(r['status']!='complete' for r in metadata['records']): raise ValueError('Missing critic labels')
    ids=[r['episode_id'] for r in rows];slots=[r.get('planned_slot_id',r['episode_id']) for r in rows]
    if len(set(ids))!=n or len(set(slots))!=n: raise ValueError('Repeated whole source')
    with np.load(path/'arrays.npz',allow_pickle=False) as a:
        arrays={k:a[k].copy() for k in DIAGNOSTIC_KEYS}
    if arrays['episode_id'].tolist()!=ids or arrays['planned_slot_id'].tolist()!=slots: raise ValueError('Row identity drift')
    if arrays['outcomes'].shape!=(n,13,4) or arrays['outcomes'].dtype!=np.bool_: raise ValueError('Wrong suffix labels')
    if arrays['control_outcomes'].shape!=(n,4) or not arrays['control_valid'].all(): raise ValueError('Missing separate normal control')
    if not np.array_equal(arrays['pair_indices'],np.broadcast_to(PAIRS,(n,5,2))): raise ValueError('Changed registered direction pairs')
    return dict(path=path,metadata=metadata,rows=rows,arrays=arrays,
                evidence=dict(path=str(path),seal_path=str(seal_path),seal_sha256=sha(seal_path),files=expected))


def verify_concatenation(children, combined):
    if combined['rows'] != children[0]['rows']+children[1]['rows']: raise ValueError('Union rows differ from children')
    if combined['metadata']['records'] != children[0]['metadata']['records']+children[1]['metadata']['records']:
        raise ValueError('Union source provenance differs from children')
    bindings=combined['metadata']['source_bindings']
    for i,child in enumerate(children,1):
        binding=bindings['round'+str(i)+'_train']
        if Path(binding['path']).resolve()!=child['path'] or binding['seal_sha256']!=child['evidence']['seal_sha256']:
            raise ValueError('Union child seal binding changed')
    verified=[]
    with np.load(children[0]['path']/'arrays.npz',allow_pickle=False) as a, np.load(children[1]['path']/'arrays.npz',allow_pickle=False) as b, np.load(combined['path']/'arrays.npz',allow_pickle=False) as c:
        if set(a.files)!=set(b.files) or set(c.files)!=set(a.files)|{'raw_deltas'}: raise ValueError('Unexpected union array keys')
        for key in sorted(a.files):
            x,y,z=a[key],b[key],c[key]
            if x.dtype!=y.dtype or z.dtype!=x.dtype or not np.array_equal(z[:300],x) or not np.array_equal(z[300:],y):
                raise ValueError('Union array differs from children: '+key)
            verified.append(key)
        expected=c['raw_actions']-c['raw_actions'][:,0:1]
        if not np.array_equal(c['raw_deltas'],expected): raise ValueError('Union raw deltas inconsistent')
    return dict(status='passed',rows_exact=True,records_exact=True,common_arrays_exact=verified,
                raw_deltas_exact=True,source_count=600,distinct_planned_slot_count=600)


def build_analysis(rows, metadata, arrays):
    names = metadata['candidate_order'] + ['continue_native10']
    outcomes = np.concatenate([arrays['outcomes'], arrays['control_outcomes'][:, None]], axis=1).astype(np.int8)
    means = outcomes.mean(axis=2)
    sources = []
    for i, (row, record) in enumerate(zip(rows, metadata['records'])):
        assert record['episode_id'] == row['episode_id']
        aliases = arrays['alias_indices'][i]
        representative = list(dict.fromkeys(aliases.tolist()))
        nonbase = [j for j in representative if j != aliases[0]]
        # alias indices are canonical candidate-slot indices; verify the meaning.
        for j, alias in enumerate(aliases):
            assert np.array_equal(arrays['raw_actions'][i, j], arrays['raw_actions'][i, alias])
            assert np.array_equal(outcomes[i, j], outcomes[i, alias])
        unique_pairs = {tuple(sorted((int(aliases[p]), int(aliases[n])))) for p, n in PAIRS if aliases[p] != aliases[n]}
        assert np.isclose(arrays['candidate_weights'][i].sum(), len(representative), atol=1e-6)
        assert np.isclose(arrays['gain_weights'][i].sum(), len(nonbase), atol=1e-6)
        assert np.isclose(arrays['pair_weights'][i].sum(), len(unique_pairs), atol=1e-6)
        mask = np.asarray(record['candidate_metadata']['clearance_mask'], dtype=bool)
        assert mask.shape == (10, 4)
        selection = record['cut_selection']
        rule = row['cut_rule']
        registered = 'first_alarm' if rule['kind'] == 'first_alarm' else 'scheduled' + str(rule['step'])
        paired_differences = outcomes[i, nonbase] - outcomes[i, 0]
        gain = means[i, nonbase] - means[i, 0]
        directional = [outcomes[i, a] - outcomes[i, b] for a, b in sorted(unique_pairs)]
        source = dict(episode_id=row['episode_id'], task=row['task'], registered_cut=registered,
            requested_cut=selection['requested_cut'], actual_cut=selection['actual_cut'],
            selection_category=selection['selection_kind'], selection_reason=selection['selection_reason'],
            unique_raw_groups=len(representative), nonbase_unique_groups=len(nonbase), unique_direction_pairs=len(unique_pairs),
            mean_label_values_unique_raw=count(means[i, representative]),
            gain_mean_positive_groups=int((gain > 0).sum()), gain_mean_negative_groups=int((gain < 0).sum()),
            gain_mean_zero_groups=int((gain == 0).sum()),
            nonalias_any_paired_discordance=bool(np.any(paired_differences)),
            nonalias_any_mean_difference=bool(np.any(gain)),
            any_candidate_mean_benefit=bool(np.any(gain > 0)), any_candidate_mean_harm=bool(np.any(gain < 0)),
            unique_nonbase_discordant_slots=int(np.count_nonzero(paired_differences)),
            unique_direction_discordant_slots=sum(int(np.count_nonzero(x)) for x in directional),
            unique_direction_nonzero_mean_pairs=sum(bool(np.mean(x)) for x in directional),
            named_nonbase_discordant_slots=int(np.count_nonzero(outcomes[i, 1:13] - outcomes[i, 0])),
            mutable_fraction_per_dimension=mask.mean(axis=0).tolist(),
            zero_xyz=not bool(mask[:, :3].any()), zero_gripper=not bool(mask[:, 3].any()),
            channel_fallback={k:bool(v['fallback']) for k,v in record['candidate_metadata']['channels'].items()},
            outcomes={name:outcomes[i,j].astype(int).tolist() for j,name in enumerate(names)},
            successes={name:int(outcomes[i,j].sum()) for j,name in enumerate(names)})
        source.update(round=int(row['round']), planned_slot_id=row.get('planned_slot_id',row['episode_id']),
            both_candidate_mean_benefit_and_harm=bool(np.any(gain > 0) and np.any(gain < 0)),
            any_candidate_paired_rescue=bool(np.any(paired_differences > 0)),
            any_candidate_paired_harm=bool(np.any(paired_differences < 0)),
            unique_direction_any_paired_discordance=any(bool(np.any(x)) for x in directional),
            unique_direction_any_mean_difference=any(bool(np.mean(x)) for x in directional),
            all_four_suffix_outcomes_identical_by_arm=bool(np.all(outcomes[i] == outcomes[i,:,0,None])))
        sources.append(source)
    tasks = arrays['task']

    def summarize(indices, group_name):
        indices = np.asarray(indices, dtype=int)
        n = len(indices)
        # Deterministic posthoc diagnostic CI. Source is the resampling unit;
        # observed task counts in each group are held fixed, not reweighted.
        rng = np.random.default_rng(BOOTSTRAP_SEED)
        boot = np.zeros((BOOTSTRAPS, len(names)), dtype=np.float64)
        for task in sorted(set(tasks[indices])):
            local = indices[tasks[indices] == task]
            weights = rng.multinomial(len(local), np.full(len(local), 1/len(local)), size=BOOTSTRAPS)
            boot += weights @ means[local] / n

        def compare(j, k):
            delta = outcomes[indices, j] - outcomes[indices, k]
            source_delta = delta.mean(axis=1)
            return dict(sources=n, paired_slots=4*n, net_gain_pp=float(100*delta.mean()),
                source_ci95_pp=(100*np.quantile(boot[:,j]-boot[:,k],[.025,.975])).tolist(),
                rescues=int((delta > 0).sum()), harms=int((delta < 0).sum()),
                positive_sources=int((source_delta > 0).sum()), negative_sources=int((source_delta < 0).sum()),
                zero_sources=int((source_delta == 0).sum()))
        selected = [sources[i] for i in indices]
        info = {key:sum(int(s[key]) for s in selected) for key in (
            'unique_raw_groups','nonbase_unique_groups','unique_direction_pairs',
            'gain_mean_positive_groups','gain_mean_negative_groups','gain_mean_zero_groups',
            'nonalias_any_paired_discordance','nonalias_any_mean_difference',
            'any_candidate_mean_benefit','any_candidate_mean_harm','unique_nonbase_discordant_slots',
            'unique_direction_discordant_slots','unique_direction_nonzero_mean_pairs',
            'named_nonbase_discordant_slots','zero_xyz','zero_gripper',
            'both_candidate_mean_benefit_and_harm','any_candidate_paired_rescue','any_candidate_paired_harm',
            'unique_direction_any_paired_discordance','unique_direction_any_mean_difference',
            'all_four_suffix_outcomes_identical_by_arm')}
        info['mutable_fraction_per_dimension'] = np.mean([s['mutable_fraction_per_dimension'] for s in selected], axis=0).tolist()
        info['raw_group_histogram'] = count(s['unique_raw_groups'] for s in selected)
        info['channel_fallback_sources'] = {k:sum(s['channel_fallback'][k] for s in selected) for k in ('xyz','gripper')}
        arms = {name:dict(successes=int(outcomes[indices,j].sum()),slots=4*n,
            success_rate=float(means[indices,j].mean()), source_ci95=(np.quantile(boot[:,j],[.025,.975])).tolist())
            for j,name in enumerate(names)}
        return dict(group=group_name,sources=n,episode_ids=[sources[i]['episode_id'] for i in indices],
            task_counts=count(tasks[indices]),actual_cut_counts=count(s['actual_cut'] for s in selected),
            selection_categories=count(s['selection_category'] for s in selected),information=info,arms=arms,
            correction_vs_a0={names[j]:compare(j,0) for j in range(1,13)},
            interruption=compare(0,13),system_vs_normal={names[j]:compare(j,13) for j in (9,10,11)},
            system_all_corrections_vs_normal={names[j]:compare(j,13) for j in range(1,13)},
            direction_positive_vs_negative={names[p]+'__minus__'+names[nn]:dict(**compare(p,nn),
                raw_distinct_sources=int((arrays['alias_indices'][indices,p] != arrays['alias_indices'][indices,nn]).sum()))
                for p,nn in PAIRS})

    def population(indices, label):
        indices=list(indices)
        total=summarize(indices,label)
        groups={}
        for key in ('task','registered_cut','selection_category','actual_cut','requested_cut','selection_reason'):
            groups[key]={str(value):summarize([i for i in indices if sources[i][key]==value],str(value))
                for value in sorted({sources[i][key] for i in indices},key=lambda x:(str(type(x)),x))}
            assert sum(g['sources'] for g in groups[key].values())==len(indices)
        keys=('task','registered_cut','requested_cut','actual_cut','selection_category','selection_reason')
        cross=Counter(tuple(sources[i][k] for k in keys) for i in indices)
        crossings=[dict(zip(keys,values),sources=n) for values,n in sorted(cross.items(),key=lambda x:repr(x[0]))]
        assert sum(x['sources'] for x in crossings)==len(indices)
        info=total['information']
        assert sum(info[k] for k in ('gain_mean_positive_groups','gain_mean_negative_groups','gain_mean_zero_groups'))==info['nonbase_unique_groups']
        return dict(total=total,groups=groups,cut_cross_counts=crossings,per_source=[sources[i] for i in indices])
    return {**{f'round{r}':population([i for i,s in enumerate(sources) if s['round']==r],f'all_train_round{r}') for r in (1,2)},
            'combined':population(range(len(rows)),'all_train_round1_and_round2')}


def subset_equal(old,new,path='root'):
    """Complete old output regression, while allowing explicitly added metrics."""
    if isinstance(old,dict):
        if not isinstance(new,dict) or not set(old)<=set(new): raise AssertionError(path)
        for key,value in old.items(): subset_equal(value,new[key],path+'.'+key)
    elif isinstance(old,list):
        if not isinstance(new,list) or len(old)!=len(new): raise AssertionError(path)
        for i,(a,b) in enumerate(zip(old,new)): subset_equal(a,b,path+f'[{i}]')
    elif old!=new: raise AssertionError(path+f': {old!r} != {new!r}')


def teacher_provenance(children):
    result={}
    for r,child in enumerate(children,1):
        expected={'critic_'+str(i) for i in (range(1041,1045) if r==1 else range(4))}
        provenance=child['metadata']['records'][0]['provenance'];models=provenance['model_hashes']
        if {k for k in models if k.startswith('critic_')}!=expected: raise ValueError('Wrong generation teacher member IDs')
        for record in child['metadata']['records']:
            if record['provenance']['model_hashes']!=models or record['provenance']['protocol_sha256']!=provenance['protocol_sha256']:
                raise ValueError('Mixed teacher identities within round')
        result['round'+str(r)]=dict(label='old v3 members 1041–1044' if r==1 else 'round1 selected B200 members 0–3',
            model_hashes=models,collection_protocol_sha256=provenance['protocol_sha256'],sources=300,
            input_dataset_seal_sha256=child['evidence']['seal_sha256'])
    for key in ('vla','d','g0','implementation'):
        if result['round1']['model_hashes'][key]!=result['round2']['model_hashes'][key]: raise ValueError('Fixed generation dependency changed')
    result['interpretation']='Different rounds have different sources/cuts and generation teachers; between-round differences do not identify a teacher effect.'
    return result


def ledger_snapshot():
    p=OUT/'budget/attempts.jsonl';data=p.read_bytes()
    return dict(path=str(p),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),records=len(data.splitlines()))


def main(destination=DEFAULT_DEST):
    started=time.monotonic();before=ledger_snapshot();script_before=sha(__file__)
    children=[sealed_train(OUT/'datasets'/f'round{r}_train_full_v1',rounds=[r]) for r in (1,2)]
    combined=sealed_train(OUT/'input_bundles/final_train600_input_v1/train',rounds=[1,2],
        parent_seal=OUT/'input_bundles/final_train600_input_v1/complete.json')
    concat=verify_concatenation(children,combined);teachers=teacher_provenance(children)
    diagnostics=build_analysis(combined['rows'],combined['metadata'],combined['arrays'])
    old_path=OUT/'progress_audits/round1_train300_v1';old=read(old_path/'result.json');oldseal=read(old_path/'complete.json')
    for name,digest in oldseal['files'].items():
        if sha(old_path/name)!=digest: raise ValueError('Changed old round1 diagnostic')
    for key in ('total','groups','per_source'): subset_equal(old[key],diagnostics['round1'][key],key)
    after=ledger_snapshot()
    if before!=after or script_before!=sha(__file__): raise ValueError('Budget ledger or script changed during readonly analysis')
    result=dict(schema='native10_train600_descriptive_direction_diagnostics_v1',status='passed',
        utc=datetime.now(timezone.utc).isoformat(),purpose='train',rounds=[1,2],
        inputs={**{f'round{r}':c['evidence'] for r,c in enumerate(children,1)},'combined_train':combined['evidence']},
        concatenation_check=concat,teacher_provenance=teachers,script_path=str(Path(__file__).resolve()),script_sha256=script_before,
        old_round1_regression=dict(status='passed',all_total_group_per_source_fields_exact=True,
            result_path=str(old_path/'result.json'),result_sha256=sha(old_path/'result.json'),seal_sha256=sha(old_path/'complete.json'),
            original_script_path=str(Path(__file__).with_name('summarize_train300_v1.py')),
            original_script_sha256=sha(Path(__file__).with_name('summarize_train300_v1.py'))),
        diagnostic_ci=dict(seed=BOOTSTRAP_SEED,resamples=BOOTSTRAPS,unit='whole source',task_stratified=True,
            group_weight='observed source counts; per round 60/task, combined 120/task',multiplicity_adjustment=False,
            status='posthoc training-distribution uncertainty; not independent validation or a selection rule'),
        definitions=old['definitions'],diagnostics=diagnostics,ledger_before=before,ledger_after=after,ledger_unchanged=True,
        development_outcomes_read=False,calibration_or_heldout_read=False,model_loads=0,model_predictions_computed=False,
        pca_calls=0,new_simulator_attempts=0,optimizer_updates=0,scientific_parameters_changed=False,
        environment=dict(python=sys.version,executable=str(Path(sys.executable).resolve()),numpy=np.__version__,
            platform=platform.platform(),cpu_threads={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS')}),
        elapsed_seconds=time.monotonic()-started)
    destination=Path(destination).resolve()
    if not destination.is_relative_to((OUT/'progress_audits').resolve()): raise ValueError('Output must be a new progress_audits version')
    destination.mkdir(parents=True,exist_ok=False)
    dump(destination/'result.json',result)
    names=combined['metadata']['candidate_order']+['continue_native10']
    sources=diagnostics['combined']['per_source']
    with (destination/'per_source.csv').open('x',newline='') as stream:
        fields=[k for k in sources[0] if not isinstance(sources[0][k],(dict,list))]+[n+'_successes' for n in names]
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for source in sources: writer.writerow({**{k:source[k] for k in fields if k in source},**{n+'_successes':source['successes'][n] for n in names}})
    dump(destination/'complete.json',dict(status='complete',files={p.name:sha(p) for p in destination.iterdir() if p.is_file()},
        role='train_distribution_diagnostics_only',script_sha256=script_before,ledger_sha256=before['sha256']))
    print(json.dumps(dict(path=str(destination),seal_sha256=sha(destination/'complete.json'),status='passed',sources=600,
        round1_regression='all fields exact',ledger_unchanged=True),ensure_ascii=False))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,default=DEFAULT_DEST)
    main(parser.parse_args().destination)
