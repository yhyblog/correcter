"""CPU-only terminal reconciliation; never launches or modifies scientific units."""
import collections
import csv
import datetime
import json
from pathlib import Path

import numpy as np

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919/results/C/C_MECHANISM_20260924_V1')
OUT = ROOT / 'analysis'


def read(p):
    return json.loads(p.read_text())


def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def csvwrite(name, rows):
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def paired_interval(values, parents):
    # Independent implementation: resample whole parent episodes, retain cut/draw weights.
    groups = collections.defaultdict(list)
    for value, parent in zip(values, parents):
        groups[parent].append(value)
    names = sorted(groups)
    totals = np.asarray([sum(groups[p]) for p in names])
    sizes = np.asarray([len(groups[p]) for p in names])
    rng = np.random.default_rng(9252026)
    samples = np.empty(1000)
    for i in range(len(samples)):
        ix = rng.choice(len(names), len(names), replace=True)
        samples[i] = totals[ix].sum() / sizes[ix].sum()
    lo, hi = np.quantile(samples, [.025, .975])
    return dict(mean=float(np.mean(values)), lo=float(lo), hi=float(hi), rows=len(values), parents=len(names))


def main():
    problems = []
    stage_counts = {}
    real = {}
    collection = {}
    ids = set()
    max_restore_difference = 0.
    for phase in ['collect', 'score', 'banks', 'local', 'budget', 'cost']:
        jobs = read(ROOT / f'JOBS_{phase}.json')
        count = collections.Counter()
        for j in jobs:
            if j['id'] in ids:
                problems.append(['duplicate_manifest_id', j['id']])
            ids.add(j['id'])
            p = ROOT / 'units' / j['id'] / 'RESULT.json'
            if not p.exists():
                count['missing'] += 1
                problems.append(['missing', j['id']])
                continue
            r = read(p)
            if r['job'] != j:
                problems.append(['job_mismatch', j['id']])
            count[r['status']] += 1
            if r['status'] != 'complete':
                problems.append(['noncomplete', j['id'], r['status']])
            if phase == 'collect':
                collection[j['source']['source_id']] = r
            if phase in ['local', 'budget', 'cost']:
                if type(r.get('success')) is not bool:
                    problems.append(['nonboolean_scientific_outcome', j['id']])
                if not 0 < r['steps'] <= 300 or r.get('remaining_budget_reissued') is not False:
                    problems.append(['budget_violation', j['id']])
                if phase == 'local':
                    max_restore_difference = max(max_restore_difference, r['restored_image_mean_abs_difference'])
                    if r['original_episode_budget'] != 300:
                        problems.append(['local_budget', j['id']])
                thin = {k: r.get(k) for k in ['success', 'steps', 'cut', 'interventions', 'policy_calls', 'inference_seconds', 'monitors', 'action_gradients']}
                thin.update(job=j, phase=phase)
                real[j['id']] = thin
        stage_counts[phase] = dict(planned=len(jobs), actual=dict(count))
        official = read(ROOT / 'stages' / f'{phase}.json')
        if dict(count) != official['counts'] or len(jobs) != official['planned']:
            problems.append(['stage_count_mismatch', phase])
        print(phase, stage_counts[phase], flush=True)

    aliases = read(ROOT / 'ALIASES.json')
    all_rows = dict(real)
    bank_cache = {}
    for a in aliases:
        j = a['job']; original = real[a['reuse_unit']]; other = original['job']
        if j['id'] in ids or j['id'] in all_rows:
            problems.append(['alias_duplicate_id', j['id']])
        for key in ['source', 'state', 'suffix', 'C', 'rep']:
            if j[key] != other[key]:
                problems.append(['alias_context_mismatch', j['id'], key])
        def prefix(job):
            key = job['bank_path']
            if key not in bank_cache:
                with np.load(key, allow_pickle=False) as z:
                    bank_cache[key] = {k: z[k] for k in z.files}
            return bank_cache[key][job['arm']][:job['C']]
        if not np.array_equal(prefix(j), prefix(other)):
            problems.append(['alias_actions_differ', j['id']])
        all_rows[j['id']] = dict(original, job=j, alias_of=a['reuse_unit'])

    with (OUT / 'VALID_OUTCOMES.csv').open() as f:
        exported = list(csv.DictReader(f))
    seen = set()
    for x in exported:
        if x['unit'] in seen:
            problems.append(['duplicate_export', x['unit']])
        seen.add(x['unit'])
        r = all_rows.get(x['unit'])
        if r is None:
            problems.append(['unexpected_export', x['unit']]); continue
        if x['success'] != str(r['success']) or x['source'] != r['job']['source']['source_id']:
            problems.append(['export_outcome_mismatch', x['unit']])
        for key in ['steps', 'interventions', 'policy_calls', 'inference_seconds']:
            if abs(float(x[key]) - r[key]) > 1e-9:
                problems.append(['export_number_mismatch', x['unit'], key])
    if seen != set(all_rows):
        problems.append(['export_set_mismatch', len(seen), len(all_rows)])

    sources = read(ROOT / 'SOURCES.json')
    source_counts = collections.Counter(s['split'] for s in sources)
    cuts = collections.Counter(); skipped = collections.Counter()
    for s in sources:
        reached = {read(p)['cut'] for p in (ROOT / 'pool' / s['source_id']).glob('cut*/snapshot/STATE.json')}
        cuts[s['split']] += len(reached)
        for c in s['cuts']:
            if c not in reached:
                cr = collection[s['source_id']]
                if cr['steps'] > c:
                    problems.append(['unexplained_missing_cut', s['source_id'], c])
                skipped[(s['split'], cr['terminal_reason'])] += 1

    local = {}
    closed = collections.defaultdict(dict)
    for r in all_rows.values():
        j = r['job']; source = j['source']['source_id']
        if j['kind'] == 'branch':
            key = (source, r['cut'], j['rep'], j['C'], j['suffix'])
            arm_map = local.setdefault(key, {})
            if j['arm'] in arm_map:
                problems.append(['duplicate_pair_key', str(key), j['arm']])
            arm_map[j['arm']] = int(r['success'])
        else:
            key = (r['phase'], j['H'], j['trigger'], j['threshold'], j['method'])
            closed[key][source] = r

    contrasts = []
    for suffix in ['native10', 'deploy10']:
        rows = [(k, v) for k, v in local.items() if k[3:] == (10, suffix)]
        for target in ['R', 'L00', 'L01', 'L10', 'reverse', 'random_sign_mean', 'no_metric', 'unified', 'grad2', 'grad4', 'radius05', 'radius2']:
            values = []; parents = []
            for k, v in rows:
                baseline = np.mean([v['sign0'], v['sign1'], v['sign2']]) if target == 'random_sign_mean' else v[target]
                values.append(v['L11'] - baseline); parents.append(k[0])
            contrasts.append(dict(suffix=suffix, contrast='L11 - ' + target, **paired_interval(values, parents)))
    csvwrite('REVIEW_PAIRED_CONTRASTS.csv', contrasts)

    closed_stats = []
    for key, rs in closed.items():
        vals = list(rs.values())
        closed_stats.append(dict(phase=key[0], H=key[1], trigger=key[2], threshold=key[3], method=key[4], n=len(vals), successes=sum(r['success'] for r in vals), success_rate=float(np.mean([r['success'] for r in vals])), interventions=float(np.mean([r['interventions'] for r in vals])), policy_calls=float(np.mean([r['policy_calls'] for r in vals])), inference_seconds=float(np.mean([r['inference_seconds'] for r in vals]))))
    csvwrite('REVIEW_CLOSED_COUNTS.csv', closed_stats)
    with (OUT / 'BE_SUCCESS_COST.csv').open() as f:
        be = list(csv.DictReader(f))
    for expected, actual in zip(be, closed_stats):
        for a, b in [('mean', 'success_rate'), ('actual_interventions', 'interventions'), ('policy_calls', 'policy_calls'), ('inference_seconds', 'inference_seconds'), ('n', 'n')]:
            if abs(float(expected[a]) - actual[b]) > 1e-9:
                problems.append(['closed_table_mismatch', str(actual), a])

    comparisons = []
    for h in [10, 20, 30]:
        a = closed['cost', h, 'G0', .05, 'Post']; b = closed['cost', h, 'G0', .05, 'R']
        parents = sorted(a)
        comparisons.append(dict(contrast=f'Post H{h} - R H{h}', **paired_interval([int(a[s]['success']) - int(b[s]['success']) for s in parents], parents)))
        b = closed['cost', 5, 'none', None, 'N']
        comparisons.append(dict(contrast=f'Post H{h} - Native H5', **paired_interval([int(a[s]['success']) - int(b[s]['success']) for s in parents], parents)))
    csvwrite('REVIEW_CLOSED_CONTRASTS.csv', comparisons)

    periodic = [closed['budget', 10, 'periodic', p, 'R'] for p in [50, 20, 10]]
    periodic_identical = all(all(periodic[0][s][k] == r[s][k] for k in ['success', 'steps', 'interventions', 'policy_calls']) for r in periodic[1:] for s in periodic[0])
    final = read(ROOT / 'RESULT.json'); process = read(ROOT / 'PROCESS.json')
    result = dict(
        terminal_status=final['status'], lifecycle_exit=final['lifecycle_exit'],
        stage_counts=stage_counts, total_real_units=len(ids), real_evaluation_units=len(real),
        reused_aliases=len(aliases), exported_evaluation_rows=len(exported),
        source_counts=dict(source_counts), unique_cuts=dict(cuts),
        uncaptured_cuts=[dict(split=k[0], reason=k[1], count=v) for k, v in sorted(skipped.items())],
        restore_max_current_image_mean_abs_difference=max_restore_difference,
        periodic_arm_interventions={str(p):dict(collections.Counter(r['interventions'] for r in closed['budget', 10, 'periodic', p, 'R'].values())) for p in [50, 20, 10]},
        periodic_outcomes_steps_and_calls_identical=periodic_identical,
        terminal_utc=datetime.datetime.fromtimestamp(final['time'], datetime.timezone.utc).isoformat(),
        formal_elapsed_hours=(final['time']-process['time'])/3600,
        arithmetic_and_record_issues=problems,
        inference='All recorded outcomes are reconciled; completion alone does not establish all scientific claims.',
        caveats=[
            'The 774 A rows are 258 unique test cuts times three estimands, not independent states.',
            'Periodic schedules collapse to a single t=5 intervention because future legal queue phases do not coincide with (t-5) mod period=0.',
            'One-step bank timing includes objective construction; multi-step timing reuses it. Do not compare these as complete end-to-end operator costs.',
            'Intervals are unadjusted 95% parent-cluster bootstrap intervals; contrasts are descriptive, not model/threshold selection.',
            'The 100 test parents belong to five auxiliary-training tasks; no unseen-task or weight-transfer claim.'
        ]
    )
    write('TERMINAL_VERIFICATION.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
