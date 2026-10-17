"""First-entry-only admission for the explicitly authorized 453-source remainder."""
from pathlib import Path

from paths import ROOT, SOURCE_SHA
from qio import read, sha, new_json, utc


def observed_source_ids():
    old = Path(read(ROOT / 'config/CONFIG.json')['old_run'])
    roots = [old.with_name('A_D24_E3_VLA_CORRECTOR_V1'), old, ROOT]
    seen = set()
    for root in roots:
        seen.update(p.parent.name for p in (root / 'runs').glob('*/ENTERED.json'))
        seen.update(p.stem for p in (root / 'claims').glob('*.json'))
    return seen


def select_unstarted(manifest, original, seen):
    allowed = manifest['rows']
    assert len(allowed) == manifest['pending_count'] == 453
    all_rows = {row['source_id']: row for row in original['rows']}
    excluded = set(manifest['excluded_entered_source_ids'])
    assert len(all_rows) == 500 and len(excluded) == 47
    assert {r['source_id'] for r in allowed} == set(all_rows) - excluded
    assert all(row == all_rows[row['source_id']] for row in allowed)
    return [row for row in allowed if row['source_id'] not in seen]


def freeze_source_admission():
    manifest_path = ROOT / 'config/TEST_SOURCES_V1.json'
    if sha(manifest_path) != SOURCE_SHA:
        raise RuntimeError('Authorized remainder manifest changed')
    manifest = read(manifest_path)
    original = read(ROOT / 'config/ORIGINAL_TEST_SOURCES_V1.json')
    seen = observed_source_ids()
    excluded = set(manifest['excluded_entered_source_ids'])
    if not excluded <= seen:
        raise RuntimeError('Prior entered evidence missing')
    eligible = select_unstarted(manifest, original, seen)
    cfg = read(ROOT / 'config/CONFIG.json')
    if cfg['prior_continuation_attempts'] + len(eligible) > cfg['continuation_attempt_cap']:
        raise RuntimeError('Continuation attempt cap')
    if cfg['prior_A_D24_episodes'] + len(eligible) > cfg['A_attempt_cap']:
        raise RuntimeError('Cumulative A attempt cap')
    new_json(ROOT / 'SOURCE_ADMISSION.json', dict(
        utc=utc(), command_type='continuation_of_unstarted_sources',
        manifest_sha256=SOURCE_SHA, eligible_count=len(eligible), rows=eligible,
        excluded_prior47=sorted(excluded),
        additionally_skipped_entered_or_claimed=sorted(seen - excluded),
        no_replacements=True, retry_allowance=0, budget_reset=False))


def sources_for_slot(slot):
    original = read(ROOT / 'config/ORIGINAL_TEST_SOURCES_V1.json')['rows']
    all_tasks = sorted({r['task'] for r in original})
    seen = observed_source_ids()
    rows = [r for r in read(ROOT / 'SOURCE_ADMISSION.json')['rows'] if r['source_id'] not in seen]
    remaining_tasks = {r['task'] for r in rows}
    selected = {i: t for i, t in enumerate(all_tasks) if i % 8 == slot and t in remaining_tasks}
    sources = {t: sorted([r for r in rows if r['task'] == t], key=lambda r: r['ordinal'])
               for t in selected.values()}
    return selected, sources


def claim_source(source, slot):
    if source['source_id'] in observed_source_ids():
        raise RuntimeError('Source already entered/claimed; do not replay')
    new_json(ROOT / 'claims' / (source['source_id'] + '.json'), dict(
        utc=utc(), source=source, worker=slot,
        claim_type='continuation_of_unstarted_sources', first_entry_only=True,
        additional_retry_allowed=False))
