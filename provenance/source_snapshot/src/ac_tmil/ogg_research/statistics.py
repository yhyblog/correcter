from __future__ import annotations

from collections import defaultdict
import numpy as np


def estimate(rows, key, bootstraps=10000, seed=29015):
    """One row per source, with all paired replicates aggregated inside it."""
    rows = [row for row in rows if row.get(key) is not None]
    if not rows:
        return dict(mean=None, interval=None, sources=0)
    if len({r['case_id'] for r in rows}) != len(rows):
        raise ValueError('Source duplicated in bootstrap input')
    strata = defaultdict(list)
    for row in rows:
        strata[row['task']].append(row[key])
    rng = np.random.default_rng(seed)
    totals = np.zeros(bootstraps)
    for _, values in sorted(strata.items()):
        values = np.asarray(values)
        totals += values[rng.integers(0, len(values), size=(bootstraps, len(values)))].sum(axis=1)
    return dict(mean=float(np.mean([r[key] for r in rows])),
                interval=np.quantile(totals / len(rows), [.025, .975]).tolist(), sources=len(rows))


def split_half_gain(successes, candidates):
    outcomes = np.asarray(successes, dtype=np.float64)
    if outcomes.shape != (6, 8) or not np.isin(outcomes, [0, 1]).all():
        raise ValueError('Expected six candidates and eight binary paired suffix outcomes')
    if candidates[0] != 0:
        raise ValueError('a0 must win ties')
    rows = []
    for selected_half, evaluation_half in [(slice(0, 4), slice(4, 8)), (slice(4, 8), slice(0, 4))]:
        means = outcomes[candidates, selected_half].mean(axis=1)
        choice = candidates[int(np.argmax(means))]
        gain = float((outcomes[choice, evaluation_half] - outcomes[0, evaluation_half]).mean())
        rows.append(dict(selected=choice, gain=gain))
    return dict(gain=float(np.mean([r['gain'] for r in rows])), halves=rows)
