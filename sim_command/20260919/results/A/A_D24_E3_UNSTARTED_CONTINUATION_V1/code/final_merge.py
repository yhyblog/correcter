"""Publish fixed-source results with old process failures and missing costs explicit."""
from pathlib import Path

from paths import ROOT
from qio import read, new_json, utc


def publish_combined():
    cfg = read(ROOT / 'config/CONFIG.json')
    old = Path(cfg['old_run'])
    original = read(ROOT / 'config/ORIGINAL_TEST_SOURCES_V1.json')['rows']
    outcomes = {}
    for directory, origin in [(old / 'runs', 'r2_original_RESULT'),
                              (ROOT / 'RECOVERED_RESULTS', 'r2_saved_terminal_log_CPU_recovery'),
                              (ROOT / 'runs', 'unstarted_continuation_first_entry')]:
        for path in sorted(directory.glob('*/RESULT.json')):
            value = read(path)
            sid = value['source_id']
            if sid in outcomes:
                raise RuntimeError('Duplicate scientific source in final merge: ' + sid)
            outcomes[sid] = dict(value, record_origin=origin, result_path=str(path))
    planned = {r['source_id']: r for r in original}
    if not set(outcomes) <= set(planned):
        raise RuntimeError('Unexpected scientific source')
    for sid, value in outcomes.items():
        if any(value[k] != planned[sid][k] for k in ('task', 'ordinal', 'env_seed', 'policy_seed')):
            raise RuntimeError('Scientific source identity differs')
    valid = [r for r in outcomes.values() if r['status'] == 'complete' and type(r['success']) is bool]
    missing = sorted(set(planned) - {r['source_id'] for r in valid})
    new_exits = [read(p) for p in (ROOT / 'chain/workers').glob('*/WORKER_EXIT.json')]
    summary = dict(
        utc=utc(), method='VLA-Corrector', H=10, planned_scientific_sources=500,
        valid_scientific_episodes=len(valid), successes=sum(r['success'] for r in valid),
        success_rate_on_valid=sum(r['success'] for r in valid) / len(valid) if valid else None,
        missing_or_technical_source_ids=missing, complete=not missing,
        r2_original_structured_results=39,
        recovered_original_terminal_results=sum(r['record_origin'] == 'r2_saved_terminal_log_CPU_recovery' for r in valid),
        new_continuation_results=sum(r['record_origin'] == 'unstarted_continuation_first_entry' for r in valid),
        old_r2_runtime_worker_failures=8, old_V1_pre_model_nonzero_worker_exits=8,
        current_worker_failures=sum(bool(x.get('fatal') or x.get('cleanup')) for x in new_exits),
        failure_count_scope='Process/publication failures separate from scientific terminal outcomes; never whole-wave technical zero.',
        resource_completeness=False,
        resource_missing_reason='Eight recovered r2 terminal records lack exact sampling/flow/time; retained as null, not zero.',
        prior_A_D24_physical_attempts=cfg['prior_A_D24_episodes'],
        new_physical_attempts=len(list((ROOT / 'runs').glob('*/ENTERED.json'))),
        continuation_command_is_not_retry=True, old_retry_remaining=0,
        native_repeated_intervention=True, our_G0_once_applied=False,
        training_data='Existing epoch30 corrector training; not the common-final-pool training comparison.')
    new_json(ROOT / 'COMBINED_EPISODES.json', dict(utc=utc(), rows=list(outcomes.values()), missing=missing))
    new_json(ROOT / 'COMBINED_FINAL_SUMMARY.json', summary)
    return summary
