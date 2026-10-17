"""CPU union of preserved valid terminals and the finite engineering continuation."""
import csv
from paths import ROOT, ORIGINAL, CONFIG
from qio import read, atomic_json, utc


def merge_cells(old_cells, new_cells):
    combined = []
    costs = ('interventions', 'policy_queries', 'policy_flow_calls', 'monitor_calls',
             'Q_ensemble_forward_calls', 'Q_member_forward_calls', 'action_gradient_calls',
             'elapsed_seconds_sum')
    for key, old in old_cells.items():
        new = new_cells.get(key, {})
        valid = old['valid'] + new.get('valid', 0)
        successes = old['successes'] + new.get('successes', 0)
        if valid > old['planned']:
            raise ValueError('valid outcome duplication')
        row = {k: old[k] for k in ('cell_id', 'model', 'method', 'mode', 'H', 'C',
                                   'raw_plan_length', 'Q_loss', 'Q_fit_seed', 'current_paper')}
        row.update(planned=old['planned'], preserved_valid=old['valid'],
                   continuation_valid=new.get('valid', 0), valid=valid, successes=successes,
                   success_rate=successes / valid if valid else None,
                   complete=valid == old['planned'], pending_unique=old['planned'] - valid,
                   attempts_all_versions=old['attempts'] + new.get('attempts', 0),
                   technical_failure_attempts_all_versions=old['technical_failures'] + new.get('technical_failures', 0))
        row['cost_unknown_attempts'] = {
            k: old['cost_unknown'].get(k, 0) + new.get('cost_unknown', {}).get(k, 0)
            for k in set(old['cost_unknown']) | set(new.get('cost_unknown', {}))}
        for k in costs:
            row[k] = old[k] + new.get(k, 0)
        row['elapsed_sum_is_not_wave_wall'] = True
        combined.append(row)
    return combined


def publish_combined(summary, rows, terminal, table):
    original = read(ORIGINAL / 'FINAL_SUMMARY.json')
    cells = merge_cells(original['cells'], summary['cells'])
    with (ORIGINAL / 'FINAL_EPISODES.csv').open() as f:
        preserved = [r for r in csv.DictReader(f) if r['valid'] == 'True']
    old_ids = {r['unit_id'] for r in preserved}
    if len(old_ids) != 2061 or any(r['unit_id'] in old_ids for r in rows):
        raise ValueError('continuation duplicated a preserved valid terminal')
    new_valid = [r for r in rows if r['valid']]
    union = preserved + new_valid
    if len({r['unit_id'] for r in union}) != len(union):
        raise ValueError('duplicate scientific terminal')
    fields = list(cells[0])
    table(ROOT / 'COMBINED_CELLS.csv', cells, fields)
    table(ROOT / 'COMBINED_POST_PAPER_CELLS.csv', [r for r in cells if r['method'] != 'Velocity'], fields)
    table(ROOT / 'COMBINED_VELOCITY_OTHER_WORK_CELLS.csv', [r for r in cells if r['method'] == 'Velocity'], fields)
    episode_fields = ['unit_id', 'source_id', 'task', 'reset_seed', 'policy_seed', 'model', 'H',
                      'raw_plan_length', 'C', 'method', 'mode', 'Q_loss', 'Q_fit_seed', 'status',
                      'valid', 'success', 'steps', 'interventions', 'first_cut', 'elapsed_seconds', 'result_path']
    table(ROOT / 'COMBINED_VALID_EPISODES.csv', union, episode_fields)
    value = dict(utc=utc(), run_id=CONFIG['run_id'], original_result=str(ORIGINAL / 'RESULT.json'),
                 original_attempts=original['actual_attempts'], new_attempts=summary['actual_attempts'],
                 total_attempts=original['actual_attempts'] + summary['actual_attempts'],
                 stage_attempt_cap=4400, preserved_valid=2061, valid=len(union), planned=4000,
                 pending_unique=4000 - len(union), cells=cells,
                 technical_failure_attempts_preserved=original['technical_missing'],
                 new_technical_failure_attempts=summary['technical_missing'],
                 current_paper_excludes_Velocity=True, original_failures_unmodified=True,
                 compute_complete=len(union) == 4000, scientific_compute=0)
    atomic_json(ROOT / 'COMBINED_SUMMARY.json', value)
    if terminal:
        atomic_json(ROOT / 'COMBINED_FINAL_SUMMARY.json', value)
