"""Frozen CPU table lookup; no draw from Python, NumPy or policy RNG streams."""
from paths import ROOT
from qio import read, sha

_schedule = None


def selected_cut(source, H, mode):
    global _schedule
    if mode == 'G0-multi':
        return None
    if mode != 'Random-once':
        raise ValueError('Unreleased trigger mode')
    if _schedule is None:
        cfg = read(ROOT / 'config/CONFIG.json')
        p = ROOT / 'config/RANDOM_ONCE_SCHEDULE_V1.json'
        if sha(p) != cfg['random_schedule_sha256']:
            raise ValueError('Frozen random schedule changed')
        rows = read(p)['rows']
        _schedule = {(x['source_id'], x['H']): x for x in rows}
        if len(rows) != 2500 or len(_schedule) != 2500:
            raise ValueError('Random schedule must have 2500 unique source/H entries')
    row = _schedule[source['source_id'], H]
    if row['task'] != source['task'] or row['ordinal'] != source['ordinal']:
        raise ValueError('Random schedule source mismatch')
    cut = row['selected_cut']
    if cut not in range(5, 291, 5) or not 0 < cut % H <= H - 5:
        raise ValueError('Random schedule has an illegal potential slot')
    return cut
