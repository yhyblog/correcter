"""Narrow reconciliation of the ten original gaps; no simulator or model import."""
import datetime
import hashlib
import json
from pathlib import Path

W = Path(__file__).resolve().parent
C = W.parents[2]
R = C / 'results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1'


def load(p):
    return json.loads(Path(p).read_text())


def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')


def main():
    oldw = C / 'work/B/B_D24_SPRINT_V1_r1'
    recovery = C / 'work/B/B_D24_RECOVERY_V1_r1'
    original = load(oldw / 'GPU_N_BATCH.json')
    mw_sources = load(C / 'work/B/B_D24_E8_POST_V1_r1/POST_SOURCES.json')['sources']
    mw_n = load(C / 'work/C/C_D24_MW_VELOCITY_V1_r2/VALID_N_INDEX.json')
    libero_n = load(C / 'work/B/B_D24_LIBERO_POST_V1_r1/N_VALID_BASELINE.json')
    configs = [load(j['config']) for j in original['jobs']]
    originals = {s['source_id']: (s, cfg) for cfg in configs for s in cfg['episodes']}
    mw_missing = {s['source_id'] for s in mw_sources} - {r['source_id'] for r in mw_n['smolvla']}
    lib_sources = {s['source_id'] for cfg in configs if cfg['kind'] == 'pi05_libero' for s in cfg['episodes']}
    lib_missing = lib_sources - {r['source_id'] for r in libero_n}
    assert len(mw_missing) == 4 and len(lib_missing) == 6
    batches = [oldw / 'GPU_N_BATCH.json', oldw / 'LIBERO_REPAIR_BATCH.json',
               recovery / 'BASELINE_BATCH.json', recovery / 'LIBERO_UNSTARTED_BATCH.json']
    jobs = []
    for bp in batches:
        bc = load(bp)
        terminal = C / 'results/B/B_D24_SPRINT_V1/r1' / bc['batch_id'] / 'RESULT.json'
        tr = load(terminal)
        assert tr['all_owned_descendants_exited'] is True
        for job in bc['jobs']:
            jc = load(job['config'])
            jobs.append((job, jc, terminal))
    gaps = []
    for sid in sorted(mw_missing | lib_missing):
        source, old = originals[sid]
        claims, terminals, searched = [], [], []
        for job, jc, terminal in jobs:
            if not any(s['source_id'] == sid for s in jc['episodes']):
                continue
            op = Path(job['output'])
            cp = op / 'episode_claims' / (sid + '.json')
            if cp.exists():
                claims.append(dict(path=str(cp), record=load(cp), exit_evidence=str(terminal)))
            for name in ('episodes.jsonl', 'worker.log', 'client.log', 'server.log'):
                fp = op / name
                if not fp.exists():
                    continue
                matches = []
                with fp.open() as f:
                    for line_no, line in enumerate(f, 1):
                        if sid not in line:
                            continue
                        matches.append(line_no)
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if row.get('source_id') == sid and row.get('method') == 'N':
                            terminals.append(dict(path=str(fp), line=line_no, row=row, job=job['job_id']))
                searched.append(dict(path=str(fp), matching_lines=matches))
        complete = [r for r in terminals if r['row'].get('status') == 'complete' and type(r['row'].get('success')) is bool]
        assert not complete, 'A recoverable terminal appeared; preserve and reconcile it before any retry'
        assert len(claims) == 1, (sid, len(claims))
        failed = [r for r in terminals if r['row'].get('status') == 'technical_failure']
        eligible = bool(failed)
        if eligible:
            unique = {json.dumps(r['row'], sort_keys=True) for r in failed}
            assert len(unique) == 1 and failed[0]['row']['success'] is None
            assert sid in lib_missing
        gaps.append(dict(source=source, base=old['kind'], suite=old.get('suite'),
                         old_config=next(j['config'] for j in original['jobs'] if j['job_id'] == old['job_id']),
                         historical_physical_attempts=len(claims), historical_corrected_episode_retries=0,
                         claims=claims, terminal_evidence=terminals, searched_logs=searched,
                         disposition='eligible_one_corrected_retry' if eligible else 'unknown_do_not_replay',
                         eligible_for_C_attempt=eligible, success=None,
                         reason='One recorded physical technical failure from transient CONTROL read / dependent websocket loss; old family exited; no previous per-source retry.' if eligible else 'Consumed claim but no unique complete or explicit failed terminal in the scoped logs; completion remains unknown.'))
    assert sum(g['eligible_for_C_attempt'] for g in gaps) == 5
    disposition = dict(task_id='C_D24_BASELINE_GAPS_E8_TABLES_V1', at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       status='reconciled_before_admission', original_gaps=10, recovered_from_logs=0, eligible_corrected_slots=5,
                       unknown_not_replayed=5, exhausted_retry_slots=0, new_attempts_so_far=0,
                       previous_C_attempts=1008, C_new_attempt_cap=10, C_cumulative_cap=2400, entries=gaps,
                       no_success_replay=True, no_baseline_outcome_selection=True,
                       old_initial_LIBERO_launch='Three initial suite clients failed at EGL import before any episode claim. The r2 label was their first physical source attempt, not a consumed source retry.',
                       cross_host_exit_note='Use B-published terminal and DRAIN evidence; never interpret B PIDs in C /proc.')
    save(R / 'N_GAP_DISPOSITION.json', disposition)
    save(R / 'RECOVERED_N.json', dict(status='none_uniquely_recoverable', records=[], log_scope='ten original missing source slots only'))
    new_jobs = []
    run = 'D24_C_N_GAPS_r1'
    for i, gap in enumerate(g for g in gaps if g['eligible_for_C_attempt']):
        source = gap['source']
        old = load(gap['old_config'])
        sid = source['source_id']
        jid = 'C_N_gap_' + sid.removeprefix('D24_LIBERO_') + '_r1'
        out = R / 'jobs' / jid
        out.mkdir(parents=True, exist_ok=False)
        prior = next(e for e in gap['terminal_evidence'] if e['path'].endswith('episodes.jsonl'))
        prior_path = R / 'prior_failures' / (sid + '.json')
        save(prior_path, dict(prior, original_claim=gap['claims'][0]['path']))
        jc = dict(old, job_id=jid, run_id=run, output=str(out), port=28610+i, episodes=[source],
                  NFE=10, attempt=2, retry_of=str(prior_path), new_task_id=disposition['task_id'],
                  original_config=gap['old_config'], original_task_constructor_seed=next(s['reset_seed'] for s in old['episodes'] if s['task_id']==source['task_id']),
                  original_claim=gap['claims'][0]['path'], original_exit_evidence=gap['claims'][0]['exit_evidence'],
                  fixed_correction='bounded live CONTROL metadata reread, no cached authorization fallback',
                  no_corrector=True, automatic_retry=False)
        path = W / 'configs' / (jid + '.json')
        save(path, jc)
        runtime_dir = '/tmp/corrector_C_N_gaps/' + jid
        new_jobs.append(dict(job_id=jid, kind='pi05_libero_N', config=str(path), output=str(out), gpus=[i], timeout_seconds=2400,
                             argv=['/usr/bin/python','-B',str(W/'libero_job.py'),'--config',str(path)],
                             env=dict(XDG_RUNTIME_DIR=runtime_dir, PYTHONDONTWRITEBYTECODE='1', VLA_RENDERER='mesa')))
    save(W / 'N_GAP_BATCH.json', dict(task_id=disposition['task_id'], batch_id=run, run_id=run, kind='gpu', max_workers=5,
         jobs=new_jobs, physical_rollout_attempts=5, automatic_retry=False, hold_idle=False,
         formal_holder_policy='all eight holders off throughout the whole five-job wave',
         concurrency_reason='Only five eligible independent original slots; remaining five unknown cannot replay.',
         budget=dict(prior_C=1008, planned_new_C=5, expected_C_max=1013, task_cap=10, cumulative_cap=2400)))
    print(json.dumps(dict(disposition=str(R/'N_GAP_DISPOSITION.json'), eligible=5, unknown=5, recovered=0,
                          batch=str(W/'N_GAP_BATCH.json'))))


if __name__ == '__main__':
    main()
