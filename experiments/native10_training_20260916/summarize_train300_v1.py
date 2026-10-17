"""Descriptive diagnostics from sealed round1 TRAIN labels only; no model fit."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/native10_training_20260916'
DATA = OUT / 'datasets/round1_train_full_v1'
DEST = OUT / 'progress_audits/round1_train300_v1'
BOOTSTRAPS = 10000
BOOTSTRAP_SEED = 2026091621
PAIRS = [(1, 2), (3, 4), (5, 6), (7, 8), (11, 12)]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def count(values):
    return dict(sorted(Counter(map(str, values)).items()))


def main():
    started = time.monotonic()
    seal = json.loads((DATA / 'complete.json').read_text())
    for name, expected in seal['files'].items():
        assert sha(DATA / name) == expected, name
    metadata = json.loads((DATA / 'metadata.json').read_text())
    rows = json.loads((DATA / 'rows.json').read_text())
    with np.load(DATA / 'arrays.npz', allow_pickle=False) as archive:
        arrays = {name: archive[name].copy() for name in (
            'outcomes', 'control_outcomes', 'control_valid', 'raw_actions',
            'candidate_weights', 'gain_weights', 'pair_indices', 'pair_weights',
            'alias_indices', 'episode_id', 'task', 'cut_step', 'split', 'round')}
    assert metadata['purpose'] == 'train' and metadata['selected_rounds'] == [1]
    assert metadata['planned_episode_count'] == metadata['complete_critic_groups'] == 300
    assert len(rows) == len(metadata['records']) == len(set(arrays['episode_id'])) == 300
    assert all(row['split'] == 'train' and row['round'] == 1 for row in rows)
    assert all(row['status'] == 'complete' for row in metadata['records'])
    assert [r['episode_id'] for r in rows] == arrays['episode_id'].tolist()
    assert arrays['outcomes'].shape == (300, 13, 4) and arrays['control_valid'].all()
    assert np.array_equal(arrays['pair_indices'], np.broadcast_to(PAIRS, (300, 5, 2)))
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
            'named_nonbase_discordant_slots','zero_xyz','zero_gripper')}
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
            direction_positive_vs_negative={names[p]+'__minus__'+names[nn]:dict(**compare(p,nn),
                raw_distinct_sources=int((arrays['alias_indices'][indices,p] != arrays['alias_indices'][indices,nn]).sum()))
                for p,nn in PAIRS})

    all_indices = list(range(300))
    total = summarize(all_indices, 'all_train_round1')
    groups = {}
    for key in ('task','registered_cut','selection_category','actual_cut'):
        groups[key] = {str(value):summarize([i for i,s in enumerate(sources) if s[key] == value], str(value))
                       for value in sorted({s[key] for s in sources},key=lambda x:(str(type(x)),x))}
        assert sum(g['sources'] for g in groups[key].values()) == 300
    assert total['information']['gain_mean_positive_groups'] + total['information']['gain_mean_negative_groups'] + total['information']['gain_mean_zero_groups'] == total['information']['nonbase_unique_groups']
    result = dict(schema='native10_round1_train300_descriptive_direction_diagnostics_v1',utc=datetime.now(timezone.utc).isoformat(),
        input_dataset=str(DATA),input_seal_sha256=sha(DATA/'complete.json'),script_sha256=sha(__file__),
        purpose='train',round=1,development_outcomes_read=False,model_predictions_computed=False,
        new_simulator_attempts=0,optimizer_updates=0,scientific_parameters_changed=False,
        diagnostic_ci=dict(seed=BOOTSTRAP_SEED,resamples=BOOTSTRAPS,unit='whole source',task_stratified=True,
            group_weight='observed source counts; all-train has exactly60/task',multiplicity_adjustment=False,
            status='posthoc training-distribution uncertainty; not an independent validation or selection rule'),
        definitions=dict(unique_groups='source-local raw ten-command aliases; controls separate',
            mean_label='mean of four paired binary suffix outcomes',
            informative='non-a0 raw-distinct candidate with different paired outcome / different four-repeat mean, separately counted',
            directions='five registered +/- pairs; unordered alias-equivalent pairs deduplicated in information totals',
            inference_limit='empirical candidate benefit/harm is descriptive; no oracle winner or deployable upper bound claimed'),
        total=total,groups=groups,per_source=sources,elapsed_seconds=time.monotonic()-started)
    DEST.mkdir(parents=True, exist_ok=False)
    dump(DEST/'result.json',result)
    with (DEST/'per_source.csv').open('x',newline='') as stream:
        fields=['episode_id','task','registered_cut','requested_cut','actual_cut','selection_category','selection_reason',
                'unique_raw_groups','unique_direction_pairs','zero_xyz','zero_gripper',
                'nonalias_any_paired_discordance','nonalias_any_mean_difference','any_candidate_mean_benefit','any_candidate_mean_harm'] + [n+'_successes' for n in names]
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for s in sources:writer.writerow({**{k:s[k] for k in fields if k in s},**{n+'_successes':s['successes'][n] for n in names}})
    dump(DEST/'complete.json',dict(status='complete',files={p.name:sha(p) for p in DEST.iterdir() if p.is_file()},
        input_seal_sha256=result['input_seal_sha256'],script_path=str(Path(__file__).resolve()),script_sha256=result['script_sha256']))
    print(json.dumps(dict(path=str(DEST),sources=300,information=total['information'],
        primary_successes={n:total['arms'][n]['successes'] for n in ('continue_native10','a0','velocity','direct','post')},
        simulator_attempts=0,optimizer_updates=0),ensure_ascii=False))


if __name__ == '__main__':
    main()
