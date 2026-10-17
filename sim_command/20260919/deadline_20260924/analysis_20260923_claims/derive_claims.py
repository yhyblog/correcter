"""CPU-only summaries of completed, selected Post experiments; no new evaluations.

Intervals condition on the fixed MT50 tasks and fitted models. Resample the ten
paired initial states within each of the fifty tasks. H cells reuse initial
states; they are never pooled as independent samples.
"""
from pathlib import Path
import csv
import json
from collections import Counter
import numpy as np
from scipy.stats import binomtest

ROOT = Path('/mnt/bn/arnold-recommend/yaohaoyang/Corrector/sim_command/20260919')
OUT = Path(__file__).parent
SOURCES = []
HS = [10, 20, 30, 40, 50]

def csv_rows(relative):
    path = ROOT / relative
    SOURCES.append(str(path))
    return list(csv.DictReader(path.open()))

def complete(row):
    return row.get('status') == 'complete' and str(row.get('success')).lower() in ('true', 'false')

def success(row):
    assert complete(row)
    return int(str(row['success']).lower() == 'true')

def index(rows):
    result = {r['source_id']: r for r in rows}
    assert len(result) == len(rows) == 500
    assert set(Counter(r['task'] for r in rows).values()) == {10}
    assert len(set(r['task'] for r in rows)) == 50
    return result

post_rows = []
for rel in [
    'results/A/A_D24_FULL_Q_AUTORUN_POST_LED_V1/FINAL_EPISODES.csv',
    'results/B/B_D24_PI05_SELECTED_H20_H30_V1/H20_r1/FINAL_EPISODES.csv',
    'results/B/B_D24_QUOTA_INDEPENDENT_QUEUE_V1/waves/H20_01/FINAL_EPISODES.csv',
    'results/B/B_D24_PI05_SELECTED_H20_H30_V1/H30_r1/FINAL_EPISODES.csv',
    'results/C/C_D24_PI05_SELECTED_H40_H50_V1/FINAL_EPISODES.csv',
]:
    post_rows.extend(r for r in csv_rows(rel) if complete(r) and r['method'] == 'Post' and r.get('stage') == 'MAIN' and r['mode'] == 'G0-multi')
assert all(r['loss'] == 'L01' and r['fit_seed'] == '9101' for r in post_rows)
post = {h: index([r for r in post_rows if int(r['H']) == h]) for h in HS}
r_rows = csv_rows('results/C/C_D24_R_TRIGGER_MODES_V1/FINAL_EPISODES.csv')
replan = {h: index([r for r in r_rows if complete(r) and r['mode'] == 'G0-multi' and int(r['H']) == h]) for h in HS}
native = {}
for h in HS:
    rows = []
    for path in sorted((ROOT / 'deadline_20260924/A/runs').glob(f'N_H{h}_*/RESULT.json')):
        SOURCES.append(str(path))
        data = json.loads(path.read_text())
        assert data['status'] == 'complete' and data['technical_failures'] == 0
        rows.extend(data['episodes'])
    native[h] = index(rows)

def compare(left, right, label, h, comparison_family):
    assert left.keys() == right.keys()
    keys = sorted(left, key=lambda k: (left[k]['task'], k))
    for k in keys:
        for field in ('task', 'env_seed', 'policy_seed', 'action_dim', 'control_hz'):
            assert str(left[k][field]) == str(right[k][field]), (label, h, k, field)
        assert float(left[k]['action_scale']) == float(right[k]['action_scale'])
    a = np.array([success(left[k]) for k in keys])
    b = np.array([success(right[k]) for k in keys])
    delta = (a - b).reshape(50, 10)
    rescued = int(np.sum((a == 1) & (b == 0)))
    harmed = int(np.sum((a == 0) & (b == 1)))
    rng = np.random.default_rng(20260923)
    bootstrap = delta[np.arange(50)[None, :, None], rng.integers(0, 10, size=(5000, 50, 10))].mean(axis=(1, 2)) * 100
    task_delta = delta.sum(axis=1)
    result = dict(comparison=label, H=h, family=comparison_family, paired_n=len(keys), left_success=int(a.sum()), right_success=int(b.sum()), delta_pp=float((a-b).mean()*100), rescued=rescued, harmed=harmed, equal=int((a==b).sum()), ci95_low_pp=float(np.quantile(bootstrap, .025)), ci95_high_pp=float(np.quantile(bootstrap, .975)), exact_mcnemar_p=float(binomtest(rescued, rescued+harmed, .5).pvalue) if rescued+harmed else 1.0, task_better=int((task_delta>0).sum()), task_equal=int((task_delta==0).sum()), task_worse=int((task_delta<0).sum()))
    task_rows = [dict(comparison=label, H=h, task=left[keys[i*10]]['task'], left_success=int(a[i*10:(i+1)*10].sum()), right_success=int(b[i*10:(i+1)*10].sum())) for i in range(50)]
    return result, task_rows

comparisons, task_rows = [], []
for h in HS:
    for base, label in [(native, 'Post-minus-N'), (replan, 'Post-minus-R')]:
        row, tasks = compare(post[h], base[h], label, h, label)
        comparisons.append(row)
        task_rows.extend(tasks)
for h in [20, 30, 50]:
    row, tasks = compare(post[h], native[10], 'Post-longH-minus-N-H10', h, 'exploratory-cross-H')
    comparisons.append(row)
    task_rows.extend(tasks)

# Five same-H tests per baseline; three explicitly exploratory cross-H tests.
for family in sorted({r['family'] for r in comparisons}):
    members = sorted([r for r in comparisons if r['family'] == family], key=lambda r: r['exact_mcnemar_p'])
    running = 0.
    for rank, row in enumerate(members):
        running = max(running, min(1., (len(members)-rank)*row['exact_mcnemar_p']))
        row['holm_family_p'] = running

def write_csv(path, rows):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

write_csv(OUT / 'main_pairs.csv', comparisons)
write_csv(OUT / 'task_pairs.csv', task_rows)
metadata = dict(scope='Selected Post L01/fit9101 multi; frozen MT50 tasks and fitted models; no LIBERO or Velocity', bootstrap='5000 within-task paired resamples, ten sources per task, seed20260923; pointwise percentile95 intervals', significance='Exact two-sided McNemar; Holm separately for five Post-N, five Post-R, three exploratory cross-H; no claim about training-seed uncertainty or unseen tasks', source_files=sorted(set(SOURCES)), comparisons=comparisons)
(OUT / 'main_pairs.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
for row in comparisons:
    print(f"{row['comparison']:26} H{row['H']:2}: {row['left_success']}/{row['paired_n']} vs {row['right_success']}/{row['paired_n']}; delta {row['delta_pp']:+.1f}pp; rescue/harm {row['rescued']}/{row['harmed']}; CI [{row['ci95_low_pp']:.1f},{row['ci95_high_pp']:.1f}]; p={row['exact_mcnemar_p']:.5g}; Holm={row['holm_family_p']:.5g}; tasks +/- {row['task_better']}/{row['task_worse']}")
